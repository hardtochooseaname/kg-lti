<script setup>
import { computed } from 'vue';

const props = defineProps({
  // 选中的图元对象
  element: { type: Object, default: null },
  // 从父组件传入的节点颜色，用于标签徽章的配色
  nodeColor: { type: String, default: '#888888' }
});

// --- 计算属性，用于动态展示信息 ---

// 判断是否为节点
const isNode = computed(() => props.element?.group === 'nodes');

// 获取元素的类型或标签，用于徽章显示
const typeLabel = computed(() => {
    if (!props.element) return '';
    return isNode.value
        ? (props.element.data.labels?.[0] || 'Node')
        : props.element.data.label;
});

// 获取徽章的背景色
const badgeColor = computed(() => {
    return isNode.value ? props.nodeColor : '#b0bec5'; // 节点用动态色，关系用固定的浅灰色
});

// 提取并排序属性列表，将id和name/title置顶
const displayAttributes = computed(() => {
    if (!props.element?.data) return [];

    const data = props.element.data;
    // 决定哪些属性需要被特殊对待或过滤
    const priorityKeys = new Set(['id', 'name', 'title']);
    const reservedKeys = new Set(['source', 'target', 'label', 'labels']);

    return Object.entries(data)
        // 过滤掉我们不想直接展示的内部属性
        .filter(([key]) => !reservedKeys.has(key) || priorityKeys.has(key))
        // 自定义排序
        .sort((a, b) => {
            const keyA = a[0];
            const keyB = b[0];
            if (keyA === 'id') return -1; // id 永远第一
            if (keyB === 'id') return 1;
            if (keyA === 'name' || keyA === 'title') return -1; // name/title 第二
            if (keyB === 'name' || keyB === 'title') return 1;
            return a[0].localeCompare(b[0]); // 其他按字母顺序
        })
        .map(([key, value]) => ({
            key,
            value,
            isPriority: priorityKeys.has(key) // 添加一个标志，用于特殊样式
        }));
});
</script>

<template>
  <div class="info-overlay" v-if="element">
    <div class="header">
      <span class="header-title">{{ isNode ? '节点' : '关系' }}</span>
      <span class="badge" :class="isNode ? 'node-badge' : 'edge-badge'" :style="{ backgroundColor: badgeColor }">
        {{ typeLabel }}
      </span>
    </div>

    <hr class="separator" />

    <div class="attributes">
       <div v-for="attr in displayAttributes" :key="attr.key" class="attr-row">
          <span class="key" :class="{ 'priority-key': attr.isPriority }">{{ attr.key }}:</span>
          <span class="value" :title="attr.value">{{ attr.value }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 悬浮框样式 */
.info-overlay {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 280px;
  background-color: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 12px;
  box-shadow: 0 5px 25px rgba(0, 0, 0, 0.1);
  padding: 15px;
  z-index: 1000;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-title {
    font-weight: bold;
    font-size: 1.1em;
    color: #333;
}
.badge {
  padding: 3px 12px;
  font-size: 0.85em;
  font-weight: bold;
  color: white;
}
/* 节点的徽章是椭圆形 */
.node-badge {
  border-radius: 16px;
}
/* 关系的徽章是带圆角的方形 */
.edge-badge {
  border-radius: 4px;
}
.separator {
  border: none;
  border-top: 1px solid #e5e5e5;
  margin: 12px 0;
}
.attributes {
  font-size: 0.9em;
  max-height: 250px;
  overflow-y: auto;
  color: #333;
}
.attr-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 2px;
  border-bottom: 1px solid #f0f0f0;
}
.attr-row:last-child {
  border-bottom: none;
}
.key {
  color: #666;
  margin-right: 15px;
  flex-shrink: 0; /* 防止key被压缩 */
}
/* 优先属性（id, name, title）加粗 */
.priority-key {
  font-weight: bold;
  color: #333;
}
.value {
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis; /* 超出部分显示省略号 */
  max-width: 70%; /* 限制值的最大宽度 */
}
</style>
