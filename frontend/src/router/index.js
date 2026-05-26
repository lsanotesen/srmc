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
      { path: '', name: 'Dashboard', component: () => import('../pages/Dashboard.vue') },
      { path: '/dashboard', name: 'Dashboard', component: () => import('../pages/Dashboard.vue') },
      { path: '/services', name: 'Services', component: () => import('../pages/Services.vue') },
      { path: '/servers', name: 'Servers', component: () => import('../pages/Servers.vue') },
      { path: '/logs', name: 'Logs', component: () => import('../pages/Logs.vue') },
      { path: '/shell', name: 'Shell', component: () => import('../pages/Shell.vue') },
      { path: '/sql', name: 'SQL', component: () => import('../pages/SQL.vue') },
      { path: '/es', name: 'ES', component: () => import('../pages/ES.vue') },
      { path: '/audit', name: 'Audit', component: () => import('../pages/Audit.vue') },
      { path: '/users', name: 'Users', component: () => import('../pages/Users.vue') },
      { path: '/settings', name: 'Settings', component: () => import('../pages/Settings.vue') }
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
    next('/dashboard')
  } else {
    next()
  }
})

export default router