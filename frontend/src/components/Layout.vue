<template>
  <div class="layout-container">
    <el-aside :width="isCollapse ? '64px' : '250px'" class="aside">
      <div class="logo" :class="{ 'logo-collapsed': isCollapse }">
        <div class="logo-icon">
          <el-icon name="server" :size="28" />
        </div>
        <div v-if="!isCollapse" class="logo-text">
          <h2>SRMC</h2>
          <p>服务资源管理中心</p>
        </div>
      </div>

      <div class="collapse-btn" @click="isCollapse = !isCollapse">
        <el-icon :name="isCollapse ? 'chevron-right' : 'chevron-left'" :size="18" />
      </div>

      <el-menu
        :default-active="activeMenu"
        class="menu"
        router
        :collapse="isCollapse"
        :unique-opened="true"
        background-color="#0f172a"
        text-color="#cbd5e1"
        active-text-color="#60a5fa"
        :collapse-transition="true"
      >
        <template v-for="item in menu" :key="item.id">
          <el-sub-menu v-if="item.children && item.children.length > 0" :index="item.id">
            <template #title>
              <el-icon :name="getIconName(item.icon)" :size="20" />
              <span>{{ item.name }}</span>
            </template>
            <el-menu-item v-for="child in item.children" :key="child.id" :index="child.path">
              <el-icon :name="getIconName(child.icon)" :size="18" />
              <span>{{ child.name }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.path">
            <el-icon :name="getIconName(item.icon)" :size="20" />
            <span>{{ item.name }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container class="main-container">
      <el-header class="header">
        <div class="header-left">
          <div class="breadcrumb">
            <el-breadcrumb separator="/">
              <el-breadcrumb-item v-for="item in breadcrumb" :key="item.path" :to="item.path">
                {{ item.name }}
              </el-breadcrumb-item>
            </el-breadcrumb>
          </div>
        </div>
        <div class="header-right">
          <div class="header-actions">
            <el-button
              icon="bell"
              class="header-btn"
              circle
              :badge="3"
              badge-type="danger"
            ></el-button>
            <el-button
              icon="refresh"
              class="header-btn"
              circle
              @click="handleRefresh"
            ></el-button>
          </div>
          <el-dropdown trigger="click">
            <div class="user-info">
              <div class="avatar">
                <el-icon name="user" :size="20" />
              </div>
              <div v-if="user" class="user-detail">
                <span class="user-name">{{ user.username }}</span>
                <span class="user-role">{{ user.role }}</span>
              </div>
              <el-icon name="chevron-down" :size="16" />
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item icon="user">个人中心</el-dropdown-item>
                <el-dropdown-item icon="settings">账户设置</el-dropdown-item>
                <el-divider style="margin: 4px 0;" />
                <el-dropdown-item icon="logout" @click="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <keep-alive>
              <component :is="Component" />
            </keep-alive>
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const isCollapse = ref(false)
const user = computed(() => userStore.user)
const menu = computed(() => {
  if (userStore.menu.length > 0) {
    return userStore.menu
  }
  return [
    { id: 'dashboard', name: 'Dashboard', icon: 'dashboard', path: '/dashboard', children: [] },
    {
      id: 'project-services',
      name: '项目服务管理',
      icon: 'folder-opened',
      path: '',
      children: [
        { id: 'projects', name: '项目列表', icon: 'folder', path: '/projects' },
        { id: 'services', name: '服务管理', icon: 'server', path: '/services' },
        { id: 'subsystems', name: '子系统管理', icon: 'folder', path: '/subsystems' },
        { id: 'service-groups', name: '程序分类管理', icon: 'folder', path: '/service-groups' }
      ]
    },
    { id: 'servers', name: '服务器管理', icon: 'computer', path: '/servers', children: [] },
    { id: 'logs', name: '日志中心', icon: 'file-text', path: '/logs', children: [] },
    { id: 'audit', name: '审计日志', icon: 'file-search', path: '/audit', children: [] },
    { id: 'users', name: '用户管理', icon: 'users', path: '/users', children: [] },
    { id: 'settings', name: '系统设置', icon: 'settings', path: '/settings', children: [] }
  ]
})
const activeMenu = computed(() => route.path)

const breadcrumb = computed(() => {
  const path = route.path
  const items = [{ name: '首页', path: '/' }]
  if (path !== '/') {
    let found = false
    for (const item of menu.value) {
      if (item.path === path) {
        items.push({ name: item.name, path: path })
        found = true
        break
      }
      if (item.children) {
        const child = item.children.find(c => c.path === path)
        if (child) {
          items.push({ name: item.name, path: item.path || '#' })
          items.push({ name: child.name, path: path })
          found = true
          break
        }
      }
    }
    if (!found) {
      items.push({ name: route.name || '页面', path: path })
    }
  }
  return items
})

const iconNameMap = {
  dashboard: 'house',
  server: 'server',
  cpu: 'cpu',
  computer: 'monitor',
  'file-text': 'file-text',
  terminal: 'terminal',
  database: 'database',
  search: 'search',
  'file-search': 'search',
  users: 'users',
  settings: 'settings',
  plus: 'plus',
  'folder-opened': 'folder-opened',
  folder: 'folder'
}

function getIconName(iconName) {
  return iconNameMap[iconName] || 'server'
}

async function logout() {
  userStore.logout()
  router.push('/login')
}

function handleRefresh() {
  window.location.reload()
}

onMounted(() => {
  if (userStore.token && !userStore.menu.length) {
    userStore.fetchMenu().catch(err => {
      console.error('Layout 加载菜单失败:', err)
    })
  }
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: #f1f5f9;
}

.aside {
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  color: #fff;
  position: relative;
  flex-shrink: 0;
  box-shadow: 4px 0 20px rgba(0, 0, 0, 0.15);
  transition: width 0.3s ease;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(0, 0, 0, 0.1);
}

.logo-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
}

.logo-text h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.logo-text p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #94a3b8;
}

.logo-collapsed {
  justify-content: center;
  padding: 20px;
}

.collapse-btn {
  position: absolute;
  right: -12px;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 48px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 0 12px 12px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  cursor: pointer;
  z-index: 100;
  transition: all 0.3s ease;
}

.collapse-btn:hover {
  background: #334155;
  color: #fff;
}

.menu {
  padding: 16px 8px;
  border-right: none;
}

.menu :deep(.el-menu-item) {
  margin: 4px 8px;
  border-radius: 10px;
  padding: 14px 16px;
  transition: all 0.3s ease;
}

.menu :deep(.el-menu-item:hover) {
  background: rgba(96, 165, 250, 0.15);
}

.menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.3) 0%, rgba(139, 92, 246, 0.3) 100%);
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.2);
}

.menu :deep(.el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 24px;
  background: linear-gradient(180deg, #3b82f6 0%, #8b5cf6 100%);
  border-radius: 0 4px 4px 0;
}

.main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  height: 64px;
}

.header-left {
  flex: 1;
}

.breadcrumb :deep(.el-breadcrumb__item) {
  font-size: 14px;
}

.breadcrumb :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  color: #334155;
  font-weight: 600;
}

.breadcrumb :deep(.el-breadcrumb__item:not(:last-child) .el-breadcrumb__inner) {
  color: #64748b;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.header-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  transition: all 0.3s ease;
}

.header-btn:hover {
  background: #f1f5f9;
  color: #334155;
  border-color: #cbd5e1;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.user-info:hover {
  background: #f8fafc;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 600;
}

.user-detail {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.user-role {
  font-size: 12px;
  color: #94a3b8;
}

.main-content {
  flex: 1;
  padding: 24px;
  overflow: auto;
  background: #f1f5f9;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
