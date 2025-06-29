#!/bin/bash

# ==============================================================================
# A more robust script to merge .gitignore files from subdirectories to the root.
# VERSION 3: APPENDS new rules to the existing root .gitignore file.
# It correctly handles negation rules (!) and absolute path rules (/).
# ==============================================================================

# 定义根 .gitignore 文件名
ROOT_GITIGNORE=".gitignore"

# 这是一个好习惯：先备份您可能已经存在的根 .gitignore 文件
if [ -f "$ROOT_GITIGNORE" ]; then
    # 创建一个带有时间戳的备份
    cp "$ROOT_GITIGNORE" "${ROOT_GITIGNORE}.bak.$(date +%F_%T)"
    echo "已备份现有的 .gitignore 文件为 ${ROOT_GITIGNORE}.bak..."
fi

# ---  主要修改点：不再覆盖文件，而是追加一个分隔符注释 ---
# 使用 '>>' 追加内容，而不是 '>' 覆盖，确保原有内容不被删除
echo -e "\n# === Rules auto-appended by script on $(date) ===" >> "$ROOT_GITIGNORE"

# --- 定义一个函数来处理单个 .gitignore 文件 (函数本身无需修改) ---
# 参数1: 源文件路径 (e.g., "frontend/.gitignore")
# 参数2: 路径前缀 (e.g., "frontend")
process_gitignore_file() {
    local source_file=$1
    local prefix=$2

    # 检查源文件是否存在
    if [ ! -f "$source_file" ]; then
        echo "警告: 未找到源文件 '$source_file'，跳过处理。"
        return
    fi

    # 追加一个空行和区域注释到根 .gitignore
    echo "" >> $ROOT_GITIGNORE
    echo "# --- Rules from $source_file ---" >> $ROOT_GITIGNORE

    # 逐行读取源文件
    while IFS= read -r line || [[ -n "$line" ]]; do
        # 跳过空行和注释行
        if [[ -z "$line" ]] || [[ "$line" =~ ^# ]]; then
            continue
        fi

        local processed_line="$line"

        # 核心逻辑：根据规则类型进行处理
        if [[ "$processed_line" == !* ]]; then
            # 1. 处理否定规则 (!)
            local rule_part="${processed_line:1}" # 提取 '!' 后面的部分
            if [[ "$rule_part" == /* ]]; then
                rule_part="${rule_part:1}"
            fi
            echo "!${prefix}/${rule_part}" >> $ROOT_GITIGNORE

        elif [[ "$processed_line" == /* ]]; then
            # 2. 处理以 '/' 开头的规则
            local rule_part="${processed_line:1}" # 提取 '/' 后面的部分
            echo "${prefix}/${rule_part}" >> $ROOT_GITIGNORE

        else
            # 3. 处理所有其他普通规则
            echo "${prefix}/${processed_line}" >> $ROOT_GITIGNORE
        fi
    done < "$source_file"
}

# --- 执行追加 ---
echo "开始向 '$ROOT_GITIGNORE' 追加规则..."
process_gitignore_file "frontend/.gitignore" "frontend"
process_gitignore_file "backend/.gitignore" "backend" # 同样处理后端文件

echo "--------------------------------------------------"
echo "追加完成！"
echo "请检查 '$ROOT_GITIGNORE' 文件，新规则已添加在文件末尾。"
echo "确认无误后，您可以手动删除子目录中的 .gitignore 文件。"