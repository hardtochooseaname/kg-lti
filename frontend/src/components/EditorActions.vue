<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  selectedElement: { type: Object, default: null },
})
const emit = defineEmits(['add-node', 'add-relationship'])

const newNodeLabel = ref('Person')
const newNodeName = ref('')
const sourceNodeId = ref('')
const targetNodeId = ref('')
const relType = ref('RELATED_TO')

watch(
  () => props.selectedElement,
  (selection) => {
    if (selection && selection.group === 'nodes') {
      sourceNodeId.value = selection.data.id
    }
  },
)

function handleAddNode() {
  if (!newNodeName.value.trim()) {
    alert('节点名称不能为空')
    return
  }
  emit('add-node', { label: newNodeLabel.value, properties: { name: newNodeName.value } })
  newNodeName.value = ''
}

function handleAddRelationship() {
  if (!sourceNodeId.value || !targetNodeId.value) {
    alert('源和目标ID都不能为空')
    return
  }
  emit('add-relationship', {
    source: sourceNodeId.value,
    target: targetNodeId.value,
    type: relType.value,
  })
  targetNodeId.value = ''
}
</script>

<template>
  <div class="actions-container">
    <h3>新增图元</h3>
    <div class="form-group">
      <h4>添加节点</h4>
      <input type="text" v-model="newNodeLabel" placeholder="节点标签" />
      <input type="text" v-model="newNodeName" placeholder="节点名称" />
      <button @click="handleAddNode">添加节点</button>
    </div>
    <hr />
    <div class="form-group">
      <h4>添加关系</h4>
      <input type="text" v-model="sourceNodeId" placeholder="源节点 ID" />
      <input type="text" v-model="targetNodeId" placeholder="目标节点 ID" />
      <input type="text" v-model="relType" placeholder="关系类型" />
      <button @click="handleAddRelationship">添加关系</button>
    </div>
  </div>
</template>

<style scoped>
/* 样式与 AttributeEditor 类似，保持风格统一 */
.actions-container {
  padding: 15px;
  border: 1px solid #eee;
  border-radius: 8px;
  background-color: #fafafa;
}
h3,
h4 {
  margin-top: 0;
  margin-bottom: 10px;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
input,
button {
  padding: 8px;
  border-radius: 4px;
  border: 1px solid #ccc;
  font-size: 14px;
}
button {
  border: none;
  background-color: #1890ff;
  color: white;
  cursor: pointer;
}
hr {
  border: none;
  border-top: 1px solid #eee;
  margin: 20px 0;
}
</style>
