import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],

  // server部分是我们为开发服务器添加的配置
  server: {
    // 这是解决问题的关键配置
    // 允许来自任何源的跨域请求。
    // 这会让Vite服务器在响应头中加入 Access-Control-Allow-Origin: *
    cors: true,
    host: true,

    allowedHosts: [
      // 你需要在这里填入你当前启动的ngrok域名
      // 从你的报错信息看，这次的域名是下面这个
      '3214-132-232-235-155.ngrok-free.app',
    ],

    // --- 核心：反向代理配置 ---
    proxy: {
      // 规则1: 当请求路径以 /api 开头时
      '/api': {
        // 将请求转发到这个目标地址
        target: 'http://127.0.0.1:5000',
        // 允许跨域
        changeOrigin: true,
      },
      // 规则2: 当请求路径是 /lti_launch 时
      '/lti_launch': {
        // 也将请求转发到这个目标地址
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
