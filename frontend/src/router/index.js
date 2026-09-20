import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../pages/Login.vue')
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('../components/Layout.vue'),
    children: [
      { path: '', redirect: '/overview' },
      { path: '/overview', name: 'Overview', component: () => import('../pages/Overview.vue') },
      { path: '/projects', name: 'Projects', component: () => import('../pages/Projects.vue') },
      { path: '/services', name: 'Services', component: () => import('../pages/ServicesNew.vue') },
      { path: '/shell', name: 'Shell', component: () => import('../pages/Shell.vue') },
      { path: '/monitoring', name: 'Monitoring', component: () => import('../pages/Monitoring.vue') },
      { path: '/import-services', name: 'ImportServices', component: () => import('../pages/ImportServices.vue') },
      { path: '/export-services', name: 'ExportServices', component: () => import('../pages/ExportServices.vue') },
      { path: '/subsystems', name: 'Subsystems', component: () => import('../pages/Subsystems.vue') },
      { path: '/service-groups', name: 'ServiceGroups', component: () => import('../pages/ServiceGroups.vue') },
      { path: '/servers', name: 'Servers', component: () => import('../pages/Servers.vue') },
      { path: '/agents', name: 'Agents', component: () => import('../pages/Agents.vue') },
      { path: '/agent-deploy-tasks', name: 'AgentDeployTasks', component: () => import('../pages/AgentDeployTasks.vue') },
      
      { path: '/sql', name: 'SQL', component: () => import('../pages/SQL.vue') },
      { path: '/es', name: 'ES', component: () => import('../pages/ES.vue') },
      { path: '/audit', name: 'Audit', component: () => import('../pages/Audit.vue') },
      { path: '/backup', name: 'Backup', component: () => import('../pages/Backup.vue') },
      { path: '/users', name: 'Users', component: () => import('../pages/Users.vue') },
      { path: '/settings', name: 'Settings', component: () => import('../pages/Settings.vue') },
      { path: '/organization', name: 'Organization', component: () => import('../pages/Organization.vue') },
      { path: '/roles', name: 'RoleManagement', component: () => import('../pages/RoleManagement.vue') },
      { path: '/usage-guide', name: 'UsageGuide', component: () => import('../pages/UsageGuide.vue') }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/overview')
  } else {
    next()
  }
})

// 全局兜底：清理可能残留的全屏遮罩
// 原因：append-to-body 对话框、keep-alive 缓存、异常中断等场景下遮罩可能未被正确移除。
// 注意：直接挂在 <body> 下的遮罩一定是全局的（teleport 到 body），局部 v-loading 不会在 body 直接子级。
// 本项目登录后进入的页面（运行总览等）不会自动弹出全局遮罩，所以路由切换后仍残留在 body 下的遮罩一律视为"卡死遮罩"。
const GLOBAL_OVERLAY_SELECTORS = [
  'body > .v-modal',                    // el-dialog / el-message-box 遮罩
  'body > .el-overlay',                 // el-loading / dialog / message-box 全屏 overlay
  'body > .el-message-box__wrapper',    // ElMessageBox 包装层
  'body > .el-loading-mask',            // ElLoading.service() 全屏 mask
  'body > .el-dialog__wrapper',         // el-dialog 包装层（旧版结构）
  'body > .el-drawer__wrapper',         // el-drawer 包装层
]

function cleanupGlobalOverlays() {
  document.querySelectorAll(GLOBAL_OVERLAY_SELECTORS.join(',')).forEach(el => {
    // 仅清理全屏 fixed 定位的遮罩，避免误伤
    const s = getComputedStyle(el)
    const r = el.getBoundingClientRect()
    const isFullscreen =
      s.position === 'fixed' &&
      r.width >= window.innerWidth * 0.9 &&
      r.height >= window.innerHeight * 0.9
    if (isFullscreen) {
      el.remove()
    }
  })
  // 解除 body 滚动锁（弹窗残留时会留下这个 class）
  document.body.classList.remove('el-popup-parent--hidden', 'el-overflow-hidden')
  document.documentElement.classList.remove('el-overflow-hidden')
}

router.afterEach(() => {
  // 立即清理一次
  cleanupGlobalOverlays()
  // 延迟两次清理：覆盖"路由切换后异步请求/组件挂载才创建出来的卡死遮罩"
  setTimeout(cleanupGlobalOverlays, 1000)
  setTimeout(cleanupGlobalOverlays, 3000)
})

export default router
