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
      { path: '/projects', name: 'Projects', component: () => import('../pages/Projects.vue') },
      { path: '/services', name: 'Services', component: () => import('../pages/ServicesNew.vue') },
      { path: '/shell', name: 'Shell', component: () => import('../pages/Shell.vue') },
      { path: '/monitoring', name: 'Monitoring', component: () => import('../pages/Monitoring.vue') },
      { path: '/import-services', name: 'ImportServices', component: () => import('../pages/ImportServices.vue') },
      { path: '/subsystems', name: 'Subsystems', component: () => import('../pages/Subsystems.vue') },
      { path: '/service-groups', name: 'ServiceGroups', component: () => import('../pages/ServiceGroups.vue') },
      { path: '/servers', name: 'Servers', component: () => import('../pages/Servers.vue') },
      
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
