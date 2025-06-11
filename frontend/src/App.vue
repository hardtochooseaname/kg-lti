<script setup>
import { ref, onMounted, nextTick } from 'vue'
import GraphViewer from './components/GraphViewer.vue'
import SearchBox from './components/SearchBox.vue'
// InfoDisplay 不再由 App.vue 直接渲染，所以这里可以移除
// import InfoDisplay from './components/InfoDisplay.vue';
import EditorActions from './components/EditorActions.vue'
// import StudentActions from './components/StudentActions.vue';
import AttributeEditor from './components/AttributeEditor.vue'
import * as api from './api.js'

const props = defineProps({
  initialViewMode: { type: String, required: true },
})

const graphViewerRef = ref(null)
const graphElements = ref(null)
const centerNodeIds = ref([])
const selectedElement = ref(null)
const isLoading = ref(true)
const error = ref(null)
const viewMode = ref(props.initialViewMode)
const initialSearchResult = ref(null)
const expansionHistory = ref([])
const expandedNodeIds = ref([])

// --- 所有函数逻辑保持不变 ---
async function fetchInitialGraph(Params = { init: true }) {
  console.log('fetchInitialGraph 参数:', Params)
  isLoading.value = true
  error.value = null
  try {
    var data
    if (Params.init) {
      data = await api.getInitialGraph()
    } else {
      data = await api.getInitialGraph(false)
    }

    if (data && Array.isArray(data.nodes)) {
      graphElements.value = data
      initialSearchResult.value = null
      expansionHistory.value = []
      expandedNodeIds.value = []
      centerNodeIds.value = []
      selectedElement.value = null
    } else {
      throw new Error('从API返回的数据格式无效')
    }
  } catch (e) {
    error.value = `无法加载初始图谱: ${e.message}`
    console.error(e)
  } finally {
    isLoading.value = false
  }
}

onMounted(fetchInitialGraph)

async function handleSearch(searchParams) {
  isLoading.value = true
  error.value = null
  selectedElement.value = null
  try {
    const data = await api.searchSubgraph(searchParams.label, searchParams.keyword)
    graphElements.value = data
    centerNodeIds.value = data.center_node_ids || []
    initialSearchResult.value = JSON.parse(JSON.stringify(data))
    expansionHistory.value = []
    expandedNodeIds.value = []
  } catch (e) {
    error.value = `搜索失败: ${e.message}`
    console.error(e)
  } finally {
    isLoading.value = false
  }
}
async function handleAddNode(nodePayload) {
  try {
    const newNodeResponse = await api.addNode(nodePayload)
    graphElements.value.nodes.push(newNodeResponse)
    await nextTick()
    graphViewerRef.value?.runLayout(false)
    alert('节点添加成功！')
  } catch (e) {
    alert(`添加节点失败: ${e.message}`)
    console.error(e)
  }
}
async function handleAddRelationship(relPayload) {
  try {
    const newRelResponse = await api.addRelationship(relPayload)
    graphElements.value.edges.push(newRelResponse)
    await nextTick()
    graphViewerRef.value?.runLayout(false)
    alert('关系添加成功！')
  } catch (e) {
    alert(`添加关系失败: ${e.message}`)
    console.error(e)
  }
}
async function handleDeleteElement(element) {
  if (!element) return
  const isNode = element.group === 'nodes'
  const elementType = isNode ? '节点' : '关系'
  if (!confirm(`确定要删除这个${elementType} (ID: ${element.data.id}) 吗?`)) return
  try {
    if (isNode) {
      await api.deleteNode(element.data.id)
      graphElements.value.nodes = graphElements.value.nodes.filter(
        (n) => n.data.id !== element.data.id,
      )
      graphElements.value.edges = graphElements.value.edges.filter(
        (e) => e.data.source !== element.data.id && e.data.target !== element.data.id,
      )
    } else {
      await api.deleteRelationship(element.data.id)
      graphElements.value.edges = graphElements.value.edges.filter(
        (e) => e.data.id !== element.data.id,
      )
    }
    selectedElement.value = null
    alert(`${elementType}删除成功！`)
  } catch (e) {
    alert(`删除${elementType}失败: ${e.message}`)
    console.error(e)
  }
}
async function handleUpdateProperty({ key, value }) {
  if (!selectedElement.value || selectedElement.value.group !== 'nodes') return
  const nodeId = selectedElement.value.data.id
  try {
    const updatedNodeResponse = await api.updateNodeProperty(nodeId, { [key]: value })
    const nodeInGraph = graphElements.value.nodes.find((n) => n.data.id === nodeId)
    if (nodeInGraph) {
      if (value === null) {
        delete nodeInGraph.data[key]
      } else {
        Object.assign(nodeInGraph.data, updatedNodeResponse.data)
      }
    }
    selectedElement.value = JSON.parse(JSON.stringify(nodeInGraph))
    alert('属性操作成功！')
  } catch (e) {
    alert(`属性操作失败: ${e.message}`)
  }
}
function handleNodeSelected(nodeJson) {
  selectedElement.value = nodeJson
}
async function handleNodeInteraction(nodeJson) {
  const nodeId = nodeJson.data.id
  const lastExpansion =
    expansionHistory.value.length > 0
      ? expansionHistory.value[expansionHistory.value.length - 1]
      : null
  if (lastExpansion && lastExpansion.parentId === nodeId) {
    const lastAddedIds = new Set(lastExpansion.childrenIds)
    graphElements.value = {
      nodes: graphElements.value.nodes.filter((n) => !lastAddedIds.has(n.data.id)),
      edges: graphElements.value.edges.filter((e) => !lastAddedIds.has(e.data.id)),
    }
    expansionHistory.value.pop()
    expandedNodeIds.value = expandedNodeIds.value.filter((id) => id !== nodeId)
    return
  }
  if (expandedNodeIds.value.includes(nodeId)) {
    return
  }
  try {
    isLoading.value = true
    const expandData = await api.expandNode(nodeId)
    if (!expandData || (!expandData.nodes && !expandData.edges)) {
      expandedNodeIds.value.push(nodeId)
      return
    }
    const newNodes = expandData.nodes || []
    const newEdges = expandData.edges || []
    const existingNodeIds = new Set(graphElements.value.nodes.map((n) => n.data.id))
    const existingEdgeIds = new Set(graphElements.value.edges.map((e) => e.data.id))
    const uniqueNewNodes = newNodes.filter((n) => !existingNodeIds.has(n.data.id))
    const uniqueNewEdges = newEdges.filter((e) => !existingEdgeIds.has(e.data.id))
    if (uniqueNewNodes.length === 0 && uniqueNewEdges.length === 0) {
      expandedNodeIds.value.push(nodeId)
      return
    }
    graphElements.value = {
      nodes: [...graphElements.value.nodes, ...uniqueNewNodes],
      edges: [...graphElements.value.edges, ...uniqueNewEdges],
    }
    const childrenIds = uniqueNewNodes
      .map((n) => n.data.id)
      .concat(uniqueNewEdges.map((e) => e.data.id))
    expansionHistory.value.push({ parentId: nodeId, childrenIds })
    expandedNodeIds.value.push(nodeId)
  } catch (e) {
    alert(`展开节点失败: ${e.message}`)
    console.error('Expand node failed:', e)
  } finally {
    isLoading.value = false
  }
}
function handleEdgeSelected(edgeJson) {
  selectedElement.value = edgeJson
}
function handleBackgroundTapped() {
  selectedElement.value = null
}
function handleUndo() {
  alert('请再次双击最近一次展开的节点来进行撤销。')
}
function handleResetSearch() {
  if (!initialSearchResult.value) {
    alert('没有可以重置的搜索结果。')
    return
  }
  graphElements.value = JSON.parse(JSON.stringify(initialSearchResult.value))
  centerNodeIds.value = initialSearchResult.value.center_node_ids || []
  expansionHistory.value = []
  expandedNodeIds.value = []
}
</script>

<template>
  <div class="app-container">
    <div class="graph-pane">
      <div v-if="isLoading" class="loading-overlay">正在加载...</div>
      <div v-else-if="error" class="error-overlay">{{ error }}</div>
      <GraphViewer
        v-else-if="graphElements"
        ref="graphViewerRef"
        :elements="graphElements"
        :center-node-ids="centerNodeIds"
        :expanded-node-ids="expandedNodeIds"
        :selected-element="selectedElement"
        @node-selected="handleNodeSelected"
        @edge-tapped="handleEdgeSelected"
        @background-tapped="handleBackgroundTapped"
        @node-interacted="handleNodeInteraction"
      />
      <div v-else class="loading-overlay">没有可显示的图谱数据。</div>
    </div>

    <div class="control-panel">
      <SearchBox
        @search="handleSearch"
        @undo="handleUndo"
        @reset-search="handleResetSearch"
        @reset-to-initial="(params) => fetchInitialGraph(params)"
        @fetch-full-graph="(params) => fetchInitialGraph(params)"
      />

      <div v-if="viewMode === 'editor'" class="editor-wrapper">
        <EditorActions
          :selected-element="selectedElement"
          @add-node="handleAddNode"
          @add-relationship="handleAddRelationship"
        />
        <AttributeEditor
          v-if="selectedElement && selectedElement.group === 'nodes'"
          :element="selectedElement"
          @update-property="handleUpdateProperty"
        />
        <button
          v-if="selectedElement"
          @click="handleDeleteElement(selectedElement)"
          class="danger-btn full-width"
        >
          删除选中的 {{ selectedElement.group === 'nodes' ? '节点' : '关系' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style>
html,
body {
  font-family: 'Arial', 'Microsoft YaHei', sans-serif;
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background-color: #f0f2f5;
}
#app {
  height: 100%;
  width: 100%;
}
</style>

<style scoped>
.app-container {
  display: flex;
  height: 100%;
  width: 100%;
  box-sizing: border-box;
  padding: 15px;
  gap: 15px;
}
.graph-pane {
  flex-grow: 1;
  min-width: 0;
  position: relative;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  background-color: #ffffff;
}

/* 需求3: 响应式宽度实现 */
.control-panel {
  display: flex;
  flex-direction: column;
  gap: 15px;

  /* 允许面板增长和收缩 */
  flex-grow: 1;
  flex-shrink: 1;

  /* 理想基础尺寸和范围限制 */
  flex-basis: 350px; /* 理想情况下占据350px */
  max-width: 400px; /* 但最大不超过400px */
  min-width: 250px; /* 最小不小于250px */

  background-color: #ffffff;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.08);
  overflow-y: auto;
}

/* 需求4：编辑器组件间隙 */
.editor-wrapper {
  display: flex;
  flex-direction: column;
  gap: 20px; /* 为内部组件（新增图元、编辑属性）创建垂直间距 */
}

/* 其他样式 */
.loading-overlay,
.error-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(255, 255, 255, 0.8);
  font-size: 1.2em;
  z-index: 10;
}
.error-overlay {
  color: #e74c3c;
}

.danger-btn.full-width {
  width: 100%;
  margin-top: 10px;
  padding: 8px 15px;
  font-size: 0.95em;
  background-color: #ff4d4f;
  color: white;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s ease;
  border: none;
}
.danger-btn.full-width:hover {
  background-color: #ff7875;
}
</style>
