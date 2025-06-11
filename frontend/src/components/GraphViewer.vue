<script setup>
import { ref, onMounted, watch } from 'vue';
import cytoscape from 'cytoscape';
import InfoDisplay from './InfoDisplay.vue'; // 导入 InfoDisplay 组件

// --- Props, Emits, Expose ---
// 增加了 selectedElement prop，用于接收当前选中的图元
const props = defineProps({
  elements: { type: Object, required: true },
  selectedElement: { type: Object, default: null },
  centerNodeIds: { type: Array, default: () => [] },
  expandedNodeIds: { type: Array, default: () => [] }
});

const emit = defineEmits(['node-selected', 'node-interacted', 'edge-tapped', 'background-tapped']);

defineExpose({ runLayout });

// --- 内部状态 ---
const cyContainer = ref(null);
let cy = null;
let currentLayout = null;

// --- 节点配色逻辑 ---
const FONT_COLOR = '#ffffff';
// 选用了一组更柔和、清晰的颜色
const COLOR_PALETTE = ['#e57373', '#81c784', '#64b5f6', '#ffb74d', '#ba68c8', '#7986cb', '#4db6ac', '#ff8a65', '#a1887f', '#90a4ae'];
const labelColorMap = new Map();
let colorIndex = 0;

function getNodeColor(nodeData) {
  // 兼容处理 cytoscape 对象和普通 js 对象
  const labels = nodeData.data ? nodeData.data('labels') : nodeData.labels;
  if (!labels || labels.length === 0) {
    return '#bdbdbd'; // 为无标签的节点提供一个中性灰色
  }
  const primaryLabel = labels[0];

  if (!labelColorMap.has(primaryLabel)) {
    labelColorMap.set(primaryLabel, COLOR_PALETTE[colorIndex % COLOR_PALETTE.length]);
    colorIndex++;
  }
  return labelColorMap.get(primaryLabel);
}

// --- 生命周期与核心逻辑 ---
onMounted(() => {
  cy = cytoscape({
    container: cyContainer.value,
    style: [
        {
            selector: 'node',
            style: {
                'background-color': (ele) => getNodeColor(ele), // 动态设置背景色
                'label': (ele) => ele.data('name') || ele.data('title') || 'Node',
                'width': '80px',
                'height': '80px',
                'font-size': '12px',
                'text-valign': 'center',
                'text-halign': 'center',
                'color': FONT_COLOR,
                'text-wrap': 'wrap',
                'text-max-width': '70px',
                'text-outline-width': 2,
                'text-outline-color': (ele) => getNodeColor(ele), // 动态设置文字描边色以增强对比
                'border-width': 3,
                'border-color': '#ffffff', // 使用白色边框让节点在背景上更突出
                'transition-property': 'background-color, border-color, border-width, border-style',
                'transition-duration': '0.2s'
            }
        },
        { selector: 'node.search-center', style: { 'border-color': '#e74c3c', 'border-width': 5, 'border-style': 'solid' } },
        { selector: 'node.expanded', style: { 'border-color': '#2ecc71', 'border-style': 'double', 'border-width': 4 } },
        {
            selector: 'edge',
            style: {
                'width': 3,
                'line-color': '#b0bec5',
                'target-arrow-color': '#b0bec5',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier',
                'label': 'data(label)',
                'font-size': '10px',
                'color': '#546e7a',
                'text-rotation': 'autorotate',
                'text-margin-y': -12,
                'transition-property': 'line-color, target-arrow-color',
                'transition-duration': '0.2s'
            }
        },
        { selector: ':selected', style: { 'border-color': '#fdd835', 'border-width': 5 } }
    ]
  });

  // 设置事件监听
  cy.on('tap', 'node', (event) => emit('node-selected', event.target.json()));
  cy.on('dbltap', 'node', (event) => emit('node-interacted', event.target.json()));
  cy.on('tap', 'edge', (event) => emit('edge-tapped', event.target.json()));
  cy.on('tap', (event) => { if (event.target === cy) emit('background-tapped'); });

  // 初始渲染
  updateGraphElements(props.elements, true);
});

// 监听父组件的 elements 数据变化
watch(() => props.elements, (newElements) => {
    updateGraphElements(newElements);
}, { deep: true });

// 监听并高亮搜索的中心节点
watch(() => props.centerNodeIds, (newIds, oldIds) => {
  if (!cy) return;

  if (oldIds && oldIds.length > 0) {
    oldIds.forEach(id => {
      const ele = cy.getElementById(id);
      if (ele && ele.length > 0) ele.removeClass('search-center');
    });
  }

  if (newIds && newIds.length > 0) {
    newIds.forEach(id => {
      const ele = cy.getElementById(id);
      if (ele && ele.length > 0) ele.addClass('search-center');
    });
  }
}, { deep: true });


// 监听已展开节点列表的变化，并更新节点样式
watch(() => props.expandedNodeIds, (newIds, oldIds) => {
    if (!cy) return;
    const oldIdSet = new Set(oldIds || []);
    const newIdSet = new Set(newIds || []);
    const idsToRemoveClass = [...oldIdSet].filter(id => !newIdSet.has(id));
    const idsToAddClass = [...newIdSet].filter(id => !oldIdSet.has(id));

    idsToRemoveClass.forEach(id => {
        const ele = cy.getElementById(id);
        if(ele.length) ele.removeClass('expanded');
    });
    idsToAddClass.forEach(id => {
        const ele = cy.getElementById(id);
        if(ele.length) ele.addClass('expanded');
    });
}, { deep: true });


// 更新图谱元素的函数
function updateGraphElements(elements, fitLayout = false) {
  if (!cy || !elements || !Array.isArray(elements.nodes)) return;

  cy.elements().remove();

  const nodeSet = new Set(elements.nodes.map(n => n.data.id));

  // 只保留合法边：source 和 target 都存在
  const validEdges = elements.edges.filter(e => {
    const { source, target } = e.data;
    return nodeSet.has(source) && nodeSet.has(target);
  });

  const flatElements = [
    ...elements.nodes.map(n => ({ ...n, group: 'nodes' })),
    ...validEdges.map(e => ({ ...e, group: 'edges' }))
  ];

  cy.add(flatElements);

  if (fitLayout) {
    runLayout(true);
  }
}




// 运行布局的函数
function runLayout(fit = true) {
    if (!cy) return;
    if (currentLayout) currentLayout.stop();
    currentLayout = cy.layout({
        name: 'cose',
        animate: 'end',
        animationDuration: 600,
        fit: fit,
        padding: 50,
        randomize: false,
        nodeRepulsion: 400000,
        idealEdgeLength: 180,
    });
    currentLayout.run();
}
</script>

<template>
  <div ref="cyContainer" class="graph-container">
    <InfoDisplay
      :element="selectedElement"
      :node-color="selectedElement?.group === 'nodes' ? getNodeColor(selectedElement.data) : undefined"
    />
  </div>
</template>

<style scoped>
.graph-container {
  width: 100%;
  height: 100%;
  position: relative; /* 这是让内部InfoDisplay绝对定位的关键 */
  background-color: #ffffff; /* 将背景设为白色，与Neo4j Browser风格更接近 */
}
</style>
