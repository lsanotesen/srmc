import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import http from 'http'
import fs from 'fs'

// 防止浏览器扩展（如 Immersive Translate 等）注入的脚本路径
// 被 SPA fallback 回退到 index.html，导致 MIME 类型错误并引发连环报错
// 对 .js / .wasm / .map 等静态资源请求，若文件不存在则返回 404
function strictAssetsPlugin() {
  const strictExts = /\.(js|mjs|cjs|wasm|map|css|less|scss|sass|svg|png|jpe?g|gif|ico|woff2?|ttf|eot)$/i
  // Vite 内部虚拟模块前缀，这些必须放行给 Vite 处理
  const viteVirtualPrefixes = ['/@vite/', '/node_modules/', '/__vite', '/src/']
  return {
    name: 'strict-assets',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const urlPath = (req.url || '').split('?')[0]
        if (!strictExts.test(urlPath)) {
          return next()
        }
        // Vite 虚拟模块 / src 源码 / node_modules 依赖 → 放行给 Vite 转换管道
        if (viteVirtualPrefixes.some(p => urlPath.startsWith(p))) {
          return next()
        }
        // public 目录下的静态资源 → 放行（Vite 会处理）
        const publicPath = path.join(__dirname, 'public', urlPath)
        if (fs.existsSync(publicPath)) {
          return next()
        }
        // 命中不到 → 404，不回退到 index.html
        res.statusCode = 404
        res.setHeader('Content-Type', 'text/plain')
        res.end('Not Found')
      })
    }
  }
}

export default defineConfig({
  plugins: [vue(), strictAssetsPlugin()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://srmc-backend:8000',
        changeOrigin: true,
        // 开启 WebSocket 升级代理：实时日志 WS 路径为 /api/services/{id}/log/ws，
        // 无法用固定前缀单独匹配（旧规则的 :service_id 被当作字面前缀，永不命中），
        // 故在通用 /api 代理上启用 ws（http 目标同样支持协议升级）
        ws: true,
        // 长连接复用，避免快速点击时连接池耗尽
        agent: new http.Agent({ 
          keepAlive: true, 
          keepAliveMsecs: 30000,
          maxSockets: 100
        })
      },
      '/api/shell/ws': {
        target: 'ws://srmc-backend:8000',
        ws: true,
        changeOrigin: true
      }
    }
  }
})
