<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  element: { type: Object, default: null },
})
const emit = defineEmits(['update-property'])

const selectedKey = ref('')
const selectedValue = ref('')
const newKey = ref('')
const newValue = ref('')

const editableAttributes = computed(() => {
  if (!props.element || props.element.group !== 'nodes') return []
  const reserved = new Set(['id', 'source', 'target', 'label', 'labels', 'name', 'title'])
  return Object.keys(props.element.data).filter((key) => !reserved.has(key))
})

watch(
  () => props.element,
  () => {
    selectedKey.value = ''
    selectedValue.value = ''
  },
)

watch(selectedKey, (key) => {
  if (key) selectedValue.value = props.element.data[key]
})

function handleUpdate() {
  if (!selectedKey.value) {
    alert('请选择要修改的属性')
    return
  }
  if (selectedValue.value === props.element.data[selectedKey.value]) {
    alert('新值与旧值相同')
    return
  }
  emit('update-property', { key: selectedKey.value, value: selectedValue.value })
}

function handleDelete() {
  if (!selectedKey.value) {
    alert('请选择要删除的属性')
    return
  }
  if (confirm(`确定要删除属性 "${selectedKey.value}" 吗？`)) {
    emit('update-property', { key: selectedKey.value, value: null }) // 删除属性即将其值设为null
  }
}

function handleAdd() {
  if (!newKey.value.trim() || !newValue.value.trim()) {
    alert('属性名和值不能为空')
    return
  }
  emit('update-property', { key: newKey.value.trim(), value: newValue.value.trim() })
  newKey.value = ''
  newValue.value = ''
}
</script>

<template>
  <div class="editor-container" v-if="element && element.group === 'nodes'">
    <h4>编辑节点属性</h4>
    <div class="form-section">
      <select v-model="selectedKey">
        <option disabled value="">-- 选择现有属性 --</option>
        <option v-for="key in editableAttributes" :key="key" :value="key">{{ key }}</option>
      </select>
      <input type="text" v-model="selectedValue" placeholder="修改值..." :disabled="!selectedKey" />
      <div class="button-group">
        <button @click="handleUpdate" :disabled="!selectedKey">更新</button>
        <button @click="handleDelete" class="danger-btn" :disabled="!selectedKey">删除</button>
      </div>
    </div>
    <hr />
    <div class="form-section">
      <input type="text" v-model="newKey" placeholder="新属性名" />
      <input type="text" v-model="newValue" placeholder="新属性值" />
      <button @click="handleAdd">添加新属性</button>
    </div>
  </div>
</template>

<style scoped>
.editor-container {
  padding: 15px;
  border: 1px solid #eee;
  border-radius: 8px;
  background-color: #fafafa;
}
h4 {
  margin-top: 0;
}
.form-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.button-group {
  display: flex;
  gap: 10px;
}
.button-group > button {
  flex: 1;
}
select,
input,
button {
  padding: 8px;
  border-radius: 4px;
  border: 1px solid #ccc;
  font-size: 14px;
}
button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}
.danger-btn {
  background-color: #ff4d4f;
  color: white;
}
hr {
  border: none;
  border-top: 1px solid #eee;
  margin: 20px 0;
}
</style>
