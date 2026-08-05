<template>
  <div class="layout-container">
    <el-aside :width="isCollapse ? '64px' : '250px'" class="aside">
      <div class="logo" :class="{ 'logo-collapsed': isCollapse }">
        <div class="logo-icon">
          🖥️
        </div>
        <div v-if="!isCollapse" class="logo-text">
          <h2>SRMC</h2>
          <p>服务资源管理中心</p>
        </div>
      </div>

      <div class="collapse-btn" :class="{ 'collapse-btn-collapsed': isCollapse }" @click="isCollapse = !isCollapse">
        <span class="collapse-icon">{{ isCollapse ? '›' : '‹' }}</span>
      </div>

      <el-menu
        :default-active="activeMenu"
        class="menu"
        router
        :collapse="isCollapse"
        :unique-opened="true"
        background-color="transparent"
        text-color="#666666"
        active-text-color="#1890ff"
        :collapse-transition="true"
      >
        <template v-for="item in menu" :key="item.id">
          <el-sub-menu v-if="item.children && item.children.length > 0" :index="item.id">
            <template #title>
              <el-icon :size="18"><component :is="getIconComponent(item.icon)" /></el-icon>
              <span>{{ item.name }}</span>
            </template>
            <el-menu-item v-for="child in item.children" :key="child.id" :index="child.path">
              <el-icon :size="18"><component :is="getIconComponent(child.icon)" /></el-icon>
              <span>{{ child.name }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.path">
            <el-tooltip :content="item.name" placement="right" :disabled="!isCollapse">
              <el-icon :size="18"><component :is="getIconComponent(item.icon)" /></el-icon>
            </el-tooltip>
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
                <el-dropdown-item icon="book-open" @click="goToUsageGuide">使用说明</el-dropdown-item>
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
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 初始化时直接从localStorage读取折叠状态，避免刷新时闪烁
const savedCollapse = localStorage.getItem('sidebarCollapse')
const isCollapse = ref(savedCollapse !== null ? savedCollapse === 'true' : false)

// 监听折叠状态变化并保存到localStorage
watch(isCollapse, (newValue) => {
  localStorage.setItem('sidebarCollapse', String(newValue))
})

onMounted(async () => {
  if (userStore.token && !userStore.menu.length) {
    await userStore.fetchMenu().catch(err => {
      console.error('Layout 加载菜单失败:', err)
    })
  }
  if (userStore.token && !userStore.user) {
    await userStore.fetchUserInfo().catch(err => {
      console.error('Layout 获取用户信息失败:', err)
    })
  }
  if (userStore.token && !userStore.permissions.length) {
    await userStore.fetchPermissions().catch(err => {
      console.error('Layout 加载权限失败:', err)
    })
  }
})
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
    { id: 'agents', name: 'Agent管理', icon: 'cpu', path: '/agents', children: [] },
    {
      id: 'permission',
      name: '权限管理',
      icon: 'lock',
      path: '',
      children: [
        { id: 'organization', name: '组织管理', icon: 'office-building', path: '/organization' },
        { id: 'roles', name: '角色管理', icon: 'user', path: '/roles' },
        { id: 'users', name: '用户管理', icon: 'users', path: '/users' }
      ]
    },
    { id: 'audit', name: '审计日志', icon: 'file-search', path: '/audit', children: [] },
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
  dashboard: 'DataBoard',
  server: 'Folder',
  cpu: 'Cpu',
  computer: 'Monitor',
  'file-text': 'FileText',
  terminal: 'Terminal',
  database: 'Database',
  search: 'Search',
  'file-search': 'Search',
  users: 'User',
  settings: 'Setting',
  'folder-opened': 'FolderOpened',
  folder: 'Folder',
  'office-building': 'OfficeBuilding',
  lock: 'Lock',
  default: 'Folder'
}

function getIconComponent(iconName) {
  if (!iconName || iconName === '') {
    return iconNameMap.default
  }
  return iconNameMap[iconName] || iconNameMap.default
}

async function logout() {
  userStore.logout()
  router.push('/login')
}

function handleRefresh() {
  window.location.reload()
}

function goToUsageGuide() {
  router.push('/usage-guide')
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: #f1f5f9;
}

.aside {
  background: #ffffff;
  color: #333333;
  position: relative;
  flex-shrink: 0;
  border-right: 1px solid #e8e8e8;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
  background: #ffffff;
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
  color: #1e293b;
}

.logo-text p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}

.logo-collapsed {
  justify-content: center;
  padding: 20px;
}

.collapse-btn {
  position: absolute;
  right: -18px;
  top: 50%;
  transform: translateY(-50%);
  width: 36px;
  height: 36px;
  background: #ffffff;
  border: 1px solid #d9d9d9;
  border-left: none;
  border-radius: 0 6px 6px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 100;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.collapse-btn:hover {
  background: #f5f5f5;
  border-color: #bfbfbf;
}

.collapse-icon {
  font-size: 20px;
  font-weight: bold;
  line-height: 1;
  color: #666666;
  margin: 0;
  padding: 0;
  margin-left: -4px;
}

.collapse-btn:hover .collapse-icon {
  color: #333333;
}

.collapse-btn-collapsed {
  right: auto;
  left: -18px;
  border-left: 1px solid #d9d9d9;
  border-right: none;
  border-radius: 6px 0 0 6px;
}

.collapse-btn-collapsed .collapse-icon {
  color: #666666;
  margin-left: 0;
  margin-right: -4px;
}

.collapse-btn-collapsed:hover .collapse-icon {
  color: #333333;
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
  background: #f5f5f5;
}

.menu :deep(.el-menu-item.is-active) {
  background: #e6f7ff;
  color: #1890ff;
}

.menu :deep(.el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 24px;
  background: #1890ff;
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
