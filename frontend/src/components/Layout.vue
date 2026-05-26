<template>
  <el-container class="layout-container">
    <el-aside width="200px" class="aside">
      <div class="logo">
        <h2>SRMC</h2>
        <p>服务资源管理中心</p>
      </div>
      <el-menu :default-active="activeMenu" class="menu" router>
        <el-menu-item v-for="item in menu" :key="item.id" :index="item.path">
          <el-icon :component="getIcon(item.icon)" />
          <span>{{ item.name }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-menu mode="horizontal" :default-active="activeMenu">
            <el-menu-item v-for="item in breadcrumb" :key="item.path" :index="item.path" router>
              {{ item.name }}
            </el-menu-item>
          </el-menu>
        </div>
        <div class="header-right">
          <el-dropdown>
            <span class="user-info">
              <el-icon component="User" />
              {{ user?.username }}
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../stores/user'
import { 
  Dashboard, Server, Computer, FileText, Terminal, Database, 
  Search, FileSearch, Users, Settings, User 
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const user = computed(() => userStore.user)
const menu = computed(() => userStore.menu)

const activeMenu = computed(() => route.path)

const breadcrumb = computed(() => {
  const path = route.path
  const items = [{ name: '首页', path: '/' }]
  if (path !== '/') {
    const menuItem = menu.value.find(item => item.path === path)
    if (menuItem) {
      items.push({ name: menuItem.name, path: path })
    }
  }
  return items
})

const iconMap = {
  dashboard: Dashboard,
  server: Server,
  computer: Computer,
  'file-text': FileText,
  terminal: Terminal,
  database: Database,
  search: Search,
  'file-search': FileSearch,
  users: Users,
  settings: Settings
}

function getIcon(iconName) {
  return iconMap[iconName] || Server
}

async function logout() {
  userStore.logout()
  router.push('/login')
}

onMounted(async () => {
  if (userStore.token && !userStore.menu.length) {
    await userStore.fetchMenu()
  }
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.aside {
  background: #1f2937;
  color: #fff;
}

.logo {
  padding: 20px;
  text-align: center;
  border-bottom: 1px solid #374151;
}

.logo h2 {
  margin: 0;
  font-size: 24px;
}

.logo p {
  margin: 5px 0 0;
  font-size: 12px;
  color: #9ca3af;
}

.menu {
  border-right: none;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.header-left {
  flex: 1;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.main {
  padding: 20px;
  overflow: auto;
}
</style>