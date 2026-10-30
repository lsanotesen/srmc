import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// Element Plus 暗色变量（需在 element-plus 基础样式之后、本项目 theme.css 之前引入）
import 'element-plus/theme-chalk/dark/css-vars.css'
// 本项目全站主题变量（浅色默认 / 深色 html.dark），会覆盖上面的 EP 暗色默认值
import './styles/theme.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import router from './router'
import App from './App.vue'
import { useThemeStore } from './stores/theme'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus)

// 初始化主题（从 localStorage 读取并应用到 html 根元素），保证首屏与用户选择一致
useThemeStore()

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 全局遮罩清理：防止 Element Plus 的 v-modal / el-overlay 等遮罩在组件卸载或路由切换后残留
// 原因：append-to-body 对话框、keep-alive 缓存、异常中断等场景下遮罩可能未被正确移除
const OVERLAY_SELECTORS = [
  'body > .v-modal',                    // el-dialog 遮罩
  'body > .el-overlay',                 // el-loading / 全屏 overlay
  'body > .el-message-box__wrapper',    // ElMessageBox
  'body > .el-loading-mask',            // ElLoading.service()
  'body > .el-dialog__wrapper',         // el-dialog 包装层
  'body > .el-drawer__wrapper',         // el-drawer 包装层
]

function cleanupDeadOverlays() {
  document.querySelectorAll(OVERLAY_SELECTORS.join(',')).forEach(el => {
    const style = el.style || {}
    const computed = getComputedStyle(el)
    // 只移除有全屏固定定位的遮罩（不影响局部 loading）
    if (style.position === 'fixed' || computed.position === 'fixed' || !style.position) {
      // 检查是否真的活着：如果有 Vue vnode，跳过（避免卸载正在进行时误删）
      if (!el.__vnode) {
        el.remove()
      }
    }
  })
}

// 启动时立即清理一次（防止刷新后残留）
cleanupDeadOverlays()

// 路由切换时清理（通过 router.afterEach 处理，见 router/index.js）

app.mount('#app')