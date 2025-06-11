from flask import Flask, redirect, request, jsonify, send_from_directory, make_response # 移除了 session
from neo4j import GraphDatabase, basic_auth
import os
from dotenv import load_dotenv # 保留 dotenv
import mimetypes
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_cors import CORS

# 允许所有静态资源跨域被加载

# --- Flask 应用初始化 ---
app = Flask(__name__)
# CORS(app, 
#      resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173", "http://132.232.235.155:5173"]}}, 
#      supports_credentials=True
# )
# app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
# app.secret_key = os.urandom(24) # 如果不使用 session 或 LTI，可以不需要

# CORS(app, resources={r"/static/*": {"origins": "*"}})


# @app.after_request
# def allow_iframe(response):
#     # 允许 iframe 嵌入
#     response.headers['X-Frame-Options'] = 'ALLOWALL'
#     return response


# --- Neo4j 连接配置 ---
load_dotenv()
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "neo4j_password") # 请确保这里是你的实际密码

# --- Neo4j Driver 初始化 ---
# 描述: 创建一个全局的 Neo4j driver 实例用于后续的数据库会话。
# 参数: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
# 影响: 应用启动时会尝试连接 Neo4j。
try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=basic_auth(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity() # 应用启动时验证连接
    app.logger.info("Successfully connected to Neo4j.")
except Exception as e:
    app.logger.error(f"Failed to connect to Neo4j: {e}", exc_info=True)
    driver = None # 标记 driver 无效

def get_db_session():
    """
    主要功能: 从全局 driver 获取一个新的 Neo4j数据库会话。
    工作逻辑: 调用 driver.session()。
    参数: 无。
    返回: Neo4j session 对象。
    影响: 每次调用都会创建一个新的会话，使用完毕后应关闭。
    """
    if not driver:
        raise ConnectionError("Neo4j driver not initialized or connection failed.")
    return driver.session()

# --- 辅助函数 ---

def serialize_node_for_cytoscape(node):
    """
    主要功能: 将 Neo4j 节点对象转换为 Cytoscape.js 前端兼容的字典格式。
    工作逻辑: 提取节点的 element_id 作为 'id', 标签列表作为 'labels', 
              并复制节点的所有其他属性。如果缺少 'name' 或 'title'，
              则尝试使用第一个标签或 "Node" 作为默认显示名称。
    参数: 
        node (neo4j.graph.Node): Neo4j 节点对象。
    返回: 
        dict: 包含 {"data": {...node_attributes...}} 的字典。
    影响: 无副作用，纯数据转换。
    """
    if not node:
        app.logger.warning("serialize_node_for_cytoscape: Received a None node object.")
        return None # 或者根据需要处理

    node_data = {
        "id": str(node.element_id),
        "labels": list(node.labels)
    }
    # 复制节点属性
    for key in node.keys():
        node_data[key] = node[key]
    
    if 'name' not in node_data and 'title' not in node_data:
        if node.labels:
            node_data['name'] = list(node.labels)[0]
        else:
            node_data['name'] = "Node" # 默认名称
            
    return {"data": node_data}


def serialize_relationship_for_cytoscape(rel):
    """
    主要功能: 将 Neo4j 关系对象转换为 Cytoscape.js 前端兼容的字典格式。
    工作逻辑: 提取关系的 element_id, 源/目标节点的 element_id, 类型和所有属性。
              包含对关系对象及其端点节点的有效性检查。
    参数:
        rel (neo4j.graph.Relationship): Neo4j 关系对象。
    返回:
        dict: 包含 {"data": {...relationship_attributes...}} 的字典。
    影响: 如果关系对象无效，会记录错误并抛出 ValueError。
    """
    if rel is None:
        app.logger.error("serialize_relationship_for_cytoscape: Received a None relationship object for serialization.")
        raise ValueError("Cannot serialize a None relationship object.")

    if not hasattr(rel, 'start_node') or rel.start_node is None or \
       not hasattr(rel.start_node, 'element_id') or not rel.start_node.element_id:
        app.logger.error(f"serialize_relationship_for_cytoscape: Relationship (element_id: {getattr(rel, 'element_id', 'N/A')}) has invalid start_node or start_node.element_id.")
        raise ValueError("Relationship has invalid start_node information.")

    if not hasattr(rel, 'end_node') or rel.end_node is None or \
       not hasattr(rel.end_node, 'element_id') or not rel.end_node.element_id:
        app.logger.error(f"serialize_relationship_for_cytoscape: Relationship (element_id: {getattr(rel, 'element_id', 'N/A')}) has invalid end_node or end_node.element_id.")
        raise ValueError("Relationship has invalid end_node information.")

    properties = {}
    try:
        for key in rel.keys():
            properties[key] = rel[key]
    except Exception as e_props:
        app.logger.warning(f"serialize_relationship_for_cytoscape: Could not access relationship properties for rel (element_id: {getattr(rel, 'element_id', 'N/A')}). Error: {e_props}")

    return {
        "data": {
            "id": str(rel.element_id),
            "source": str(rel.start_node.element_id),
            "target": str(rel.end_node.element_id),
            "label": rel.type,
            **properties
        }
    }



def is_student_role(roles_str, ext_roles_str=None):
    """
    根据 LTI roles 和 ext_roles 参数判断用户的有效角色和权限。
    参数:
        roles_str (str): LTI 'roles' 参数的值 (逗号分隔的字符串)。
        ext_roles_str (str, 可选): LTI 'ext_roles' 参数的值 (逗号分隔的字符串)。
    """
    app.logger.info(f"Role_Debug: Input roles_str: '{roles_str}'")
    app.logger.info(f"Role_Debug: Input ext_roles_str: '{ext_roles_str}'")

    raw_roles = []
    if roles_str:
        raw_roles.extend([r.strip().lower() for r in roles_str.split(',') if r.strip()])
    if ext_roles_str:
        raw_roles.extend([r.strip().lower() for r in ext_roles_str.split(',') if r.strip()])
    
    unique_roles = sorted(list(set(raw_roles))) # 去重并排序，方便查看和调试
    app.logger.info(f"Role_Debug: All unique roles (lowercase): {unique_roles}")

    # 初始化权限和角色标志
    is_admin = False
    is_instructor = False
    is_student = False # Canvas 中 'Learner' 对应学生

    # 定义各种角色的关键词 (小写)
    # 你可以根据需要扩展这些，特别是 URN 格式
    # 参考: https://www.imsglobal.org/spec/lti/v1p3/mend/core#role-vocabularies
    
    # 系统级/机构级管理员角色
    admin_sys_keywords = [
        'urn:lti:sysrole:ims/lis/sysadmin',
        'urn:lti:sysrole:ims/lis/administrator' # 有些 LMS 可能用这个
    ]
    # 机构级管理员/教师/学生 (通常用于区分机构身份，而不是课程内角色)
    admin_inst_keywords = ['urn:lti:instrole:ims/lis/administrator']
    instructor_inst_keywords = ['urn:lti:instrole:ims/lis/instructor']
    student_inst_keywords = ['urn:lti:instrole:ims/lis/student']

    # 上下文/课程级角色 (这些通常更重要，用来决定在当前课程中的权限)
    instructor_context_keywords = [
        'instructor', # 简写
        'urn:lti:role:ims/lis/instructor',
        'urn:lti:role:ims/lis/contentdeveloper', # 内容开发者
        'urn:lti:role:ims/lis/teachingassistant', # 助教的变体
        'urn:lti:role:ims/lis/mentor' # 也可能是编辑者
    ]
    student_context_keywords = [
        'learner', # 简写，Canvas常用
        'student', # 简写
        'urn:lti:role:ims/lis/learner',
        'urn:lti:role:ims/lis/student', # 有些LMS可能用这个作为上下文角色
        'urn:lti:role:ims/lis/mentee',
        'urn:lti:role:ims/lis/member', # 普通成员
        'urn:lti:role:ims/lis/prospectivemember'
    ]
    
    # 检查角色
    for role in unique_roles:
        if role in admin_sys_keywords or role in admin_inst_keywords:
            is_admin = True
        if role in instructor_context_keywords or role in instructor_inst_keywords:
            is_instructor = True
        if role in student_context_keywords or role in student_inst_keywords:
            is_student = True

    # ---- 在这里填充你的角色判断和权限设置逻辑 ----
    # 优先级：管理员 > 教师 > 学生
    # 你可以根据你的应用需求调整这个优先级

    effective_role = "Unknown"
    can_edit = False # 默认无编辑权限

    if is_admin:
        effective_role = "Administrator"
        can_edit = True # 管理员通常有所有权限
        app.logger.info("Role_Debug: User identified as Administrator.")
        return False
    elif is_instructor:
        effective_role = "Instructor"
        can_edit = True # 教师有编辑权限
        app.logger.info("Role_Debug: User identified as Instructor.")
        return False
    elif is_student:
        effective_role = "Student"
        can_edit = False # 学生默认只读 (根据你的需求)
        app.logger.info("Role_Debug: User identified as Student.")
        return True
    # else:
    #     # 如果上面主要角色都没匹配上，可以检查是否是普通用户等
    #     if 'urn:lti:sysrole:ims/lis/user' in unique_roles:
    #         effective_role = "User" # 普通认证用户，可能权限更低
    #         app.logger.info("Role_Debug: User identified as a generic User (no specific major role).")
    #     else:
    #         app.logger.warning(f"Role_Debug: Could not determine a primary effective role for roles: {unique_roles}")


    # # 你可以在这里添加更复杂的逻辑，例如：
    # # - 如果一个用户同时是教师也是学生（在不同的上下文中），你当前如何处理？
    # #   上面的逻辑会优先将他/她识别为教师（如果 is_admin 为 False）。
    # # - 特定的自定义角色处理等。

    # permissions = {
    #     'is_admin': is_admin,
    #     'is_instructor': is_instructor,
    #     'is_student': is_student,
    #     'can_edit': can_edit, # 这是最终的编辑权限标志
    #     'effective_role': effective_role, # 用户在你的应用中被赋予的主要角色
    #     'all_roles_detected': unique_roles # 存储所有检测到的角色，方便调试或未来使用
    # }
    # app.logger.info(f"Role_Debug: Determined permissions: {permissions}")
    # return permissions

# --- API 端点 ---




# @app.route('/')
# def index_page():
#     """
#     主要功能: 提供知识图谱应用的前端 HTML 页面。
#     工作逻辑: 渲染 templates/index.html 文件。
#     参数: 无。
#     返回: 渲染后的 HTML 页面。
#     影响: 用户访问根路径时会看到此页面。
#     """
#     return render_template('index.html')

# @app.route('/stu')
# def index_student_page():
#     """
#     主要功能: 提供知识图谱应用的前端 HTML 页面。
#     工作逻辑: 渲染 templates/index.html 文件。
#     参数: 无。
#     返回: 渲染后的 HTML 页面。
#     影响: 用户访问根路径时会看到此页面。
#     """
#     return render_template('index-student.html')


# backend/app.py

# ... (保留你其他的Python代码，如 get_db_session, determine_user_role 等) ...
# 注意：你之前的 is_student_role 函数现在应该返回 'student' 或 'editor' 这样的字符串

@app.route('/')
def direct_access_page():
    """为本地直接开发提供一个默认视图，例如编辑器视图"""
    # 在直接访问时，我们可以默认一个角色，比如 'editor'
    return redirect(f"http://132.232.235.155:5173/?view_mode=editor")

@app.route('/lti_launch', methods=['POST'])
def lti_launch():
    """
    处理LTI启动请求，判断用户角色，并渲染带有角色信息的单页应用外壳。
    """
    # 假设你的角色判断函数现在返回 'student' 或 'editor'
    # 为了安全，默认角色可以是 'student'
    view_mode = 'student' 

    if request.form:
        roles_param = request.form.get('roles', '')
        ext_roles_param = request.form.get('ext_roles')

        if not is_student_role(roles_param, ext_roles_param):
            view_mode = 'editor'
    
    print(f"LTI Launch: Determined view mode is '{view_mode}'")

    # --- 关键修改：不再渲染模板，而是重定向 ---
    # 获取前端的访问地址（即你的ngrok/cloudflare隧道地址）
    # X-Forwarded-Host 头由代理（如ngrok, cloudflare tunnel）设置
    frontend_host = request.headers.get('X-Forwarded-Host') or request.host.replace('5000', '5173')
    
    # 构造带参数的重定向URL
    # 注意我们使用 https
    redirect_url = f"https://{frontend_host}?view_mode={view_mode}"
    
    app.logger.info(f"Redirecting LTI launch to: {redirect_url}")
    
    return redirect(redirect_url)



# backend/app.py

@app.route('/api/graph', methods=['GET'])
def get_full_graph_data():
    """
    主要功能: 根据 'init' 参数决定加载初始图谱还是全图。
    工作逻辑: 
        - init=true (默认): 只加载带init:1属性的节点及其1跳邻居。
        - init=false: 加载数据库中的所有节点和关系。
    参数 (URL Query):
        init (str): 'true' 或 'false'。默认为 'true'。
    """
    db = None
    try:
        # 1. 获取 init 查询参数，并设定默认值
        # request.args.get('init', 'true') 表示如果URL中没有init参数，则默认为 'true'
        # .lower() == 'true' 将其转换为布尔值
        load_init_only = request.args.get('init', 'true').lower() == 'true'
        
        db = get_db_session()
        
        # 2. 根据参数动态构建节点查询语句
        if load_init_only:
            app.logger.info("Loading initial graph (init=true).")
            init_nodes_query = "MATCH (n) WHERE n.init = '1' OR n.init = 1 RETURN n"
        else:
            app.logger.info("Loading FULL graph (init=false).")
            init_nodes_query = "MATCH (n) RETURN n"
            
        init_nodes_result = db.run(init_nodes_query)
        
        # --- 后续的数据处理逻辑与您提供的代码完全一致，因为它们足够健壮 ---
        
        nodes_dict = {}
        init_node_ids = set() # 在全图模式下，这将包含所有节点的ID
        for record in init_nodes_result:
            node = record["n"]
            serialized_node = serialize_node_for_cytoscape(node)
            if serialized_node and node.element_id not in nodes_dict:
                nodes_dict[node.element_id] = serialized_node
                init_node_ids.add(node.element_id)
        
        if not init_node_ids:
            return jsonify({"nodes": [], "edges": []})
        
        # 在全图模式下，这个查询会获取所有的关系
        # 在初始图模式下，它只获取与init节点相连的关系
        neighbor_query = """
            MATCH (start_n)-[r]-(end_n)
            WHERE elementId(start_n) IN $node_ids
            RETURN r, start_n, end_n 
        """
        # 注意：我稍微优化了您的查询，不再需要 OR elementId(end_n)，
        # 并且返回了完整的start_n和end_n节点对象，这样可以避免N+1查询问题。
        
        edges_result = list(db.run(neighbor_query, node_ids=list(init_node_ids)))
        
        edges_list = []
        processed_rel_ids = set()
        
        for record in edges_result:
            relationship_obj = record["r"]
            start_node = record["start_n"]
            end_node = record["end_n"]
            
            # 确保两个端点都在我们的节点字典中
            if start_node.element_id not in nodes_dict:
                nodes_dict[start_node.element_id] = serialize_node_for_cytoscape(start_node)
            if end_node.element_id not in nodes_dict:
                nodes_dict[end_node.element_id] = serialize_node_for_cytoscape(end_node)

            # 添加关系
            if relationship_obj.element_id not in processed_rel_ids:
                edges_list.append(serialize_relationship_for_cytoscape(relationship_obj))
                processed_rel_ids.add(relationship_obj.element_id)
                
        app.logger.info(f"Loaded {len(nodes_dict)} nodes and {len(edges_list)} edges")
        return jsonify({"nodes": list(nodes_dict.values()), "edges": edges_list})
        
    except Exception as e:
        app.logger.error(f"Unexpected error in get_full_graph_data: {str(e)}", exc_info=True)
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if db:
            db.close()



@app.route('/api/nodes', methods=['POST'])
def create_new_node():
    """
    主要功能: 在 Neo4j 中创建一个新节点。
    工作逻辑:接收包含节点标签和属性的 JSON 数据。
              构造并执行 CREATE Cypher 查询。
              返回新创建节点序列化后的数据和 HTTP 201。
    参数 (来自请求JSON body):
        label (str, 可选): 节点的标签，默认为 "Node"。
        properties (dict, 可选): 节点的属性键值对。
    返回:
        JSON: 成功时为序列化后的新节点数据。
        失败时为错误信息 JSON 和相应的 HTTP 状态码。
    影响: 对数据库进行写操作 (创建节点)。
    """
    db = None
    try:
        data = request.json
        node_label = data.get('label', 'Node').strip()
        if not node_label: node_label = 'Node' # 确保标签不为空
        properties = data.get('properties', {})

        if not properties.get('name') and not properties.get('title'):
            properties['name'] = f"New {node_label}"

        db = get_db_session()
        
        prop_placeholders = ", ".join([f"{key}: ${key}" for key in properties.keys()])
        query = f"CREATE (n:{node_label} {{{prop_placeholders}}}) RETURN n"
        
        app.logger.info(f"Executing node creation: {query} with params {properties}")
        result = db.run(query, **properties).single()
        
        if result and result["n"]:
            new_node_cytoscape = serialize_node_for_cytoscape(result["n"])
            return jsonify(new_node_cytoscape), 201
        else:
            app.logger.error("Failed to create node or 'n' not returned.")
            return jsonify({"error": "Failed to create node in DB"}), 500
    except ConnectionError as ce:
        app.logger.error(f"Neo4j connection error in create_new_node: {str(ce)}", exc_info=True)
        return jsonify({"error": f"Database connection error: {str(ce)}"}), 503  
    except Exception as e:
        app.logger.error(f"Error in create_new_node: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        if db:
            db.close()


@app.route('/api/nodes/<node_id>', methods=['PUT'])
def update_existing_node(node_id):
    """
    主要功能: 更新 Neo4j 中已存在节点的属性。
    工作逻辑: 接收节点 elementId 和要更新的属性。
              构造并执行 MATCH...SET Cypher 查询。
              返回更新后节点序列化后的数据和 HTTP 200。
    参数 (路径参数):
        node_id (str): 要更新节点的 elementId。
    参数 (来自请求JSON body):
        properties (dict): 包含要更新的属性及其新值的字典。
    返回:
        JSON: 成功时为序列化后的更新节点数据。
        失败时为错误信息 JSON 和相应的 HTTP 状态码。
    影响: 对数据库进行写操作 (更新节点属性)。
    """
    db = None
    try:
        data = request.json
        properties_to_update = data.get('properties', {})

        if not node_id:
            return jsonify({"error": "Node ID is required"}), 400
        if not properties_to_update:
            return jsonify({"error": "No properties provided for update"}), 400

        db = get_db_session()
        
        set_clauses = [f"n.{key} = ${key}" for key in properties_to_update.keys()]
        if not set_clauses:
            return jsonify({"error": "No valid properties to update"}), 400

        query_params = {"node_id": node_id, **properties_to_update}
        query = f"""
            MATCH (n) WHERE elementId(n) = $node_id
            SET {', '.join(set_clauses)}
            RETURN n
        """
        app.logger.info(f"Executing node update: {query} with params {query_params}")
        result = db.run(query, **query_params).single()
        
        if result and result["n"]:
            updated_node_cytoscape = serialize_node_for_cytoscape(result["n"])
            return jsonify(updated_node_cytoscape), 200
        else:
            app.logger.warning(f"Node not found or update failed for ID: {node_id}")
            return jsonify({"error": "Node not found or update failed"}), 404
    except ConnectionError as ce:
        app.logger.error(f"Neo4j connection error in update_existing_node: {str(ce)}", exc_info=True)
        return jsonify({"error": f"Database connection error: {str(ce)}"}), 503  
    except Exception as e:
        app.logger.error(f"Error in update_existing_node: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        if db:
            db.close()


@app.route('/api/nodes/<node_id>', methods=['DELETE'])
def delete_existing_node(node_id):
    """
    主要功能: 从 Neo4j 中删除一个节点及其所有关联关系。
    工作逻辑: 接收节点 elementId。
              执行 DETACH DELETE Cypher 查询。
              返回成功消息和 HTTP 200。
    参数 (路径参数):
        node_id (str): 要删除节点的 elementId。
    返回:
        JSON: 成功或失败的信息。
    影响: 对数据库进行写操作 (删除节点和关系)。
    """
    db = None
    try:
        if not node_id:
            return jsonify({"error": "Node ID is required"}), 400
            
        db = get_db_session()
        app.logger.info(f"Executing node deletion for ID: {node_id}")
        db.run("MATCH (n) WHERE elementId(n) = $node_id DETACH DELETE n", node_id=node_id)
        return jsonify({"message": f"Node {node_id} and its relationships deleted successfully"}), 200
    except ConnectionError as ce:
        app.logger.error(f"Neo4j connection error in delete_existing_node: {str(ce)}", exc_info=True)
        return jsonify({"error": f"Database connection error: {str(ce)}"}), 503          
    except Exception as e:
        app.logger.error(f"Error in delete_existing_node: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        if db:
            db.close()


@app.route('/api/relationships', methods=['POST'])
def create_new_relationship():
    """
    主要功能: 在 Neo4j 中创建两个已存在节点之间的新关系。
    工作逻辑: 接收源/目标节点的 elementId, 关系类型和属性。
              构造并执行 MATCH...CREATE Cypher 查询。
              返回新创建关系序列化后的数据和 HTTP 201。
    参数 (来自请求JSON body):
        source (str): 源节点的 elementId。
        target (str): 目标节点的 elementId。
        type (str, 可选): 关系类型，默认为 "RELATED_TO"。
        properties (dict, 可选): 关系的属性。
    返回:
        JSON: 成功时为序列化后的新关系数据。
        失败时为错误信息 JSON 和相应的 HTTP 状态码。
    影响: 对数据库进行写操作 (创建关系)。
    """
    db = None
    try:
        data = request.json
        source_node_id = data.get('source')
        target_node_id = data.get('target')
        relationship_type = data.get('type', 'RELATED_TO').upper().strip()
        if not relationship_type: relationship_type = "RELATED_TO"
        properties = data.get('properties', {})

        app.logger.info(f"Backend: Add relationship request. Data: {data}")

        if not source_node_id or not target_node_id:
            app.logger.warning("Backend: Source or Target ID missing.")
            return jsonify({"error": "Source and target node IDs are mandatory"}), 400

        db = get_db_session()
        
        prop_cypher_part = ""
        if properties:
            prop_list = [f"{key}: ${key}" for key in properties.keys()]
            if prop_list:
                prop_cypher_part = "{" + ", ".join(prop_list) + "}"
        
        # 使用占位符构建 CREATE 部分，属性在 query_params 中传递
        cypher_create_rel_part = f"CREATE (a)-[r_new:{relationship_type} {prop_cypher_part}]->(b)"
        
        query = f"""
            MATCH (a), (b)
            WHERE elementId(a) = $source_id AND elementId(b) = $target_id
            {cypher_create_rel_part}
            RETURN r_new, a, b 
        """ # a, b 在 RETURN 中是为了潜在的更丰富的对象信息，但主要依赖 r_new
        query_params = {"source_id": source_node_id, "target_id": target_node_id, **properties}
        
        app.logger.info(f"Executing relationship creation: \n{query} \nwith params: {query_params}")
        result_record = db.run(query, **query_params).single()
        
        r_new_from_record = result_record.get("r_new") if result_record else None

        if r_new_from_record is not None:
            created_relationship = r_new_from_record
            app.logger.info(f"Relationship object obtained, proceeding with serialization for element_id: {created_relationship.element_id}")
            new_rel_cytoscape = serialize_relationship_for_cytoscape(created_relationship)
            app.logger.info(f"Relationship serialized: {new_rel_cytoscape}")
            return jsonify(new_rel_cytoscape), 201
        else:
            log_message = "Failed to obtain created relationship details from DB ('r_new' was None or not in result)."
            if result_record:
                log_message += f" Record content: {dict(result_record)}"
            else:
                log_message += " Query returned no records."
            app.logger.warning(f"Backend: {log_message}")
            
            # 检查节点是否存在，以提供更准确的反馈
            source_exists = db.run("MATCH (n) WHERE elementId(n) = $id RETURN count(n) > 0 AS exists", id=source_node_id).single()['exists']
            target_exists = db.run("MATCH (n) WHERE elementId(n) = $id RETURN count(n) > 0 AS exists", id=target_node_id).single()['exists']
            app.logger.warning(f"Backend: Node existence - Source '{source_node_id}': {source_exists}, Target '{target_node_id}': {target_exists}")
            
            error_detail = "Ensure both source and target nodes exist."
            if not source_exists: error_detail = "Source node not found."
            elif not target_exists: error_detail = "Target node not found."
            elif result_record is None: error_detail = "Query did not return expected record (MATCH might have failed)."

            return jsonify({"error": f"Failed to create relationship. {error_detail}"}), 500
    except ConnectionError as ce:
        app.logger.error(f"Neo4j connection error in create_new_relationship: {str(ce)}", exc_info=True)
        return jsonify({"error": f"Database connection error: {str(ce)}"}), 503  
    except ValueError as ve: # 通常来自序列化函数
        app.logger.error(f"Data processing error in create_new_relationship: {str(ve)}", exc_info=True)
        return jsonify({"error": f"Data processing error: {str(ve)}"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error in create_new_relationship: {str(e)}", exc_info=True)
        return jsonify({"error": f"An unexpected server error occurred: {str(e)}"}), 500
    finally:
        if db:
            db.close()


@app.route('/api/relationships/<relationship_id>', methods=['DELETE'])
def delete_existing_relationship(relationship_id):
    """
    主要功能: 从 Neo4j 中删除一个已存在的关系。
    工作逻辑: 接收关系 elementId。
              执行 MATCH...DELETE Cypher 查询。
              返回成功消息和 HTTP 200。
    参数 (路径参数):
        relationship_id (str): 要删除关系的 elementId。
    返回:
        JSON: 成功或失败的信息。
    影响: 对数据库进行写操作 (删除关系)。
    """
    db = None
    try:
        if not relationship_id:
            return jsonify({"error": "Relationship ID is required"}), 400
            
        db = get_db_session()
        app.logger.info(f"Executing relationship deletion for ID: {relationship_id}")
        # 直接删除关系，不需要 DETACH，因为关系没有进一步的依赖
        db.run("MATCH ()-[r]->() WHERE elementId(r) = $rel_id DELETE r", rel_id=relationship_id)
        return jsonify({"message": f"Relationship {relationship_id} deleted successfully"}), 200
    except ConnectionError as ce:
        app.logger.error(f"Neo4j connection error in delete_existing_relationship: {str(ce)}", exc_info=True)
        return jsonify({"error": f"Database connection error: {str(ce)}"}), 503  
    except Exception as e:
        app.logger.error(f"Error in delete_existing_relationship: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        if db:
            db.close()


# --- 在 app.py 中添加以下两个新的路由 ---

# --- 在 app.py 中添加这个新的 API 路由 ---

@app.route('/api/schema/labels', methods=['GET'])
def get_node_labels():
    """
    主要功能: 动态地从 Neo4j 数据库获取所有存在的节点标签。
    工作逻辑: 执行 'CALL db.labels()' 查询，处理结果并返回一个包含所有标签字符串的列表。
    参数: 无。
    返回:
        JSON: 一个包含所有节点标签的数组，例如 ["Person", "Movie", "Organization"]。
    影响: 对数据库进行一次轻量级的读操作。
    """
    db = None
    try:
        db = get_db_session()
        query = "CALL db.labels()"
        app.logger.info(f"Executing schema query: {query}")
        
        results = db.run(query)
        
        # 从结果中提取标签字符串
        labels = [record["label"] for record in results]
        
        app.logger.info(f"Fetched node labels from DB: {labels}")
        return jsonify(labels)

    except Exception as e:
        app.logger.error(f"Error in get_node_labels: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch node labels from database."}), 500
    finally:
        if db:
            db.close()

# --- 在 app.py 的 API 端点部分添加这个新函数 ---

@app.route('/api/search', methods=['GET'])
def search_subgraph():
    """
    主要功能: 
        根据用户提供的一个节点标签和一个关键词，搜索匹配的中心节点，
        并返回由这些中心节点及其直接邻居（1跳邻域）构成的子图数据。
        (此版本采用了与用户原有 get_full_graph_data 函数相同的、经过验证的稳健查询模式)
    """
    db = None
    try:
        SEARCHABLE_PROPERTIES = {
            'Movie': 'title', 'Person': 'name', 'Organization': 'name', 'default': 'name'
        }
        label = request.args.get('label')
        keyword = request.args.get('keyword', '').strip()
        
        if not label or not keyword:
            return jsonify({"error": "Label and keyword parameters are required."}), 400

        property_to_search = SEARCHABLE_PROPERTIES.get(label.capitalize(), SEARCHABLE_PROPERTIES['default'])
        
        db = get_db_session()
        
        # --- 步骤 1: 查找并序列化所有匹配的中心节点 ---
        center_nodes_query = f"""
            MATCH (n:{label})
            WHERE toLower(n.{property_to_search}) CONTAINS toLower($keyword)
            RETURN n
        """
        center_nodes_result = db.run(center_nodes_query, keyword=keyword)
        
        nodes_dict = {}
        center_node_ids = set()
        for record in center_nodes_result:
            node = record["n"]
            if node.element_id not in nodes_dict:
                nodes_dict[node.element_id] = serialize_node_for_cytoscape(node)
                center_node_ids.add(node.element_id)

        if not center_node_ids:
            return jsonify({"nodes": [], "edges": [], "center_node_ids": []})
            
        # --- 步骤 2: 查找与这些中心节点相连的所有关系及其两端节点 ---
        # 这个查询会返回中心节点、关系、以及邻居节点
        neighbor_query = """
            MATCH (start_node)-[r]-(end_node)
            WHERE elementId(start_node) IN $node_ids
            RETURN start_node, r, end_node
        """
        edges_result = db.run(neighbor_query, node_ids=list(center_node_ids))
        
        edges_list = []
        processed_rel_ids = set()
        
        for record in edges_result:
            start_node = record["start_node"]
            relationship_obj = record["r"]
            end_node = record["end_node"]

            # --- 步骤 3: 确保所有涉及的节点（包括邻居）都被序列化 ---
            # 如果起始节点不在字典中（理论上它应该在），则添加
            if start_node.element_id not in nodes_dict:
                nodes_dict[start_node.element_id] = serialize_node_for_cytoscape(start_node)

            # 如果结束节点（邻居）不在字典中，则添加
            if end_node.element_id not in nodes_dict:
                nodes_dict[end_node.element_id] = serialize_node_for_cytoscape(end_node)
            
            # --- 步骤 4: 添加关系 ---
            if relationship_obj.element_id not in processed_rel_ids:
                # 调用你已有的、功能正常的序列化函数
                serialized_edge = serialize_relationship_for_cytoscape(relationship_obj)
                edges_list.append(serialized_edge)
                processed_rel_ids.add(relationship_obj.element_id)
        
        app.logger.info(f"Search for '{keyword}' found {len(nodes_dict)} total nodes and {len(edges_list)} edges.")

        return jsonify({
            "nodes": list(nodes_dict.values()), 
            "edges": edges_list,
            "center_node_ids": list(center_node_ids)
        })

    except Exception as e:
        app.logger.error(f"Error in search_subgraph: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred during search."}), 500
    finally:
        if db:
            db.close()


# backend/app.py

# backend/app.py

# backend/app.py

# backend/app.py

# backend/app.py

# backend/app.py

# 确保在文件顶部导入了 neo4j 的数据类型，以便在类型检查时使用
from neo4j.graph import Relationship, Node

# ... (你其他的app.py代码) ...

# backend/app.py

@app.route('/api/expand/<node_id>', methods=['GET'])
def expand_node(node_id):
    """
    获取指定节点的1跳邻域数据，用于交互式展开。
    (最终修正版：在Cypher中获取所有原始数据，Python只做拼接，零依赖)
    """
    db = None
    try:
        if not node_id:
            return jsonify({"error": "Node ID is required."}), 400

        db = get_db_session()
        
        # 1. 查询语句现在明确返回所有需要的原始数据，不再返回对象
        query = """
            MATCH (startNode)-[r]-(neighbor)
            WHERE elementId(startNode) = $node_id
            RETURN
              elementId(r) AS rel_id,
              type(r) AS rel_type,
              properties(r) AS rel_props,
              elementId(startNode) AS source_id,
              elementId(neighbor) AS neighbor_id,
              labels(neighbor) AS neighbor_labels,
              properties(neighbor) AS neighbor_props
        """
        results = db.run(query, node_id=node_id).data()
        
        nodes_dict = {}
        edges_list = []
        
        # 2. 直接用查询返回的字典数据来构建前端需要的JSON
        for record in results:
            neighbor_id = record['neighbor_id']
            
            # 如果邻居节点还没被处理过，就构建它的JSON对象
            if neighbor_id not in nodes_dict:
                node_data = {
                    "id": neighbor_id,
                    "labels": record['neighbor_labels'],
                    **record['neighbor_props']
                }
                # 确保节点有 'name' 或 'title' 用于显示
                if 'name' not in node_data and 'title' not in node_data:
                    node_data['name'] = node_data['labels'][0] if node_data['labels'] else 'Node'
                
                nodes_dict[neighbor_id] = {"data": node_data}

            # 构建边的JSON对象
            edge_data = {
                "data": {
                    "id": record['rel_id'],
                    "source": record['source_id'],
                    "target": record['neighbor_id'],
                    "label": record['rel_type'],
                    **record['rel_props']
                }
            }
            edges_list.append(edge_data)

        app.logger.info(f"Expansion for node {node_id} will return {len(nodes_dict)} nodes and {len(edges_list)} edges.")

        return jsonify({
            "nodes": list(nodes_dict.values()), 
            "edges": edges_list
        })

    except Exception as e:
        app.logger.error(f"Error in expand_node: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred during node expansion."}), 500
    finally:
        if db:
            db.close()




if __name__ == '__main__':
    # 确保 NEO4J_PASSWORD 已在 .env 文件或环境变量中正确设置
    if NEO4J_PASSWORD == "neo4j_password" or not NEO4J_PASSWORD: # 检查是否为默认或未设置
        print("警告: Neo4j 密码可能未正确配置或仍为默认值。请检查 .env 文件或环境变量。")
    
    # 移除 LTI 特定的 consumers 和 lti_launch 路由 (根据用户要求精简)
    app.run(debug=True, port=5000, host="0.0.0.0") # 之前建议 5001，这里改回 5000