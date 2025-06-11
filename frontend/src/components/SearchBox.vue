<script setup>
import { ref, onMounted } from 'vue';
import { getNodeLabels } from '../api.js';

const labels = ref([]);
const selectedLabel = ref('');
const keyword = ref('');
const isLoading = ref(true);

// --- 关键修改 1: 更新emit的事件列表 ---
const emit = defineEmits(['search', 'fetch-full-graph', 'reset-search', 'reset-to-initial']);

onMounted(async () => {
    try {
        const fetchedLabels = await getNodeLabels();
        labels.value = fetchedLabels;
        if (fetchedLabels.length > 0) {
            selectedLabel.value = fetchedLabels[0];
        }
    } catch (error) {
        console.error("Failed to fetch node labels:", error);
    } finally {
        isLoading.value = false;
    }
});

function performSearch() {
    if (!keyword.value.trim()) {
        alert('请输入搜索关键词。');
        return;
    }
    emit('search', {
        label: selectedLabel.value,
        keyword: keyword.value.trim()
    });
    keyword.value = ''
}
</script>

<template>
    <div class="search-box-container">
        <h3>图谱搜索与操作</h3>
        <div v-if="isLoading">正在加载标签...</div>
        <div v-else>
            <div class="search-form">
                <select v-model="selectedLabel">
                    <option v-for="label in labels" :key="label" :value="label">
                        {{ label }}
                    </option>
                </select>
                <input
                    type="text"
                    v-model="keyword"
                    placeholder="输入名称/标题搜索..."
                    @keyup.enter="performSearch"
                />
                <button class="primary-btn" @click="performSearch">查找</button>
            </div>

            <hr class="divider">

            <div class="action-buttons">
                <button class="secondary-btn" @click="emit('reset-search')" title="重置所有展开，恢复到初始搜索结果">重置搜索</button>
                <button class="secondary-btn" @click="emit('reset-to-initial', {init: true})" title="返回初始展示的图谱">返回初始图</button>
                <!-- <button class="secondary-btn" @click="emit('fetch-full-graph', {init: false})" title="加载数据库中的完整图谱">全图</button> -->
            </div>
        </div>
    </div>
</template>

<style scoped>
.search-box-container { padding: 15px; border: 1px solid #eee; border-radius: 8px; background-color: #fafafa; }
h3 { margin-top: 0; margin-bottom: 15px; }
.search-form { display: flex; align-items: center; gap: 10px; }
select, input, button { padding: 8px; border-radius: 4px; border: 1px solid #ccc; font-size: 14px; }
select { flex-shrink: 0; }
input { flex: 1 1 auto; min-width: 80px; }
button { border: none; cursor: pointer; font-weight: bold; transition: background-color 0.2s ease; flex-shrink: 0; }
.primary-btn { background-color: #1890ff; color: white; }
.primary-btn:hover { background-color: #40a9ff; }
.divider { border: none; border-top: 1px solid #e0e0e0; margin: 15px 0; }
.action-buttons { display: flex; justify-content: space-between; gap: 10px; }
.secondary-btn { flex-grow: 1; background-color: #f5f5f5; color: #555; border: 1px solid #d9d9d9; }
.secondary-btn:hover { background-color: #e9e9e9; border-color: #b0b0b0; }
</style>
