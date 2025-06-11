// frontend/src/main.js
import { createApp } from 'vue'
import App from './App.vue'

// 1. 创建一个URLSearchParams实例来解析当前窗口的URL
const urlParams = new URLSearchParams(window.location.search)

// 2. 从URL中获取 'view_mode' 参数，如果不存在，则默认为 'editor'
const initialViewMode = urlParams.get('view_mode') || 'editor'

// 3. 将初始角色作为 prop 传递给 App 组件
const app = createApp(App, { initialViewMode: initialViewMode })

app.mount('#app')
