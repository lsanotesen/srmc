import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from '@/utils/axios'

export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  const menu = ref([])
  const permissions = ref([])
  const isLoading = ref(false)
  const fetchMenuError = ref(null)

  const permissionSet = computed(() => new Set(permissions.value))

  function hasPermission(permission) {
    if (user.value?.role === 'SUPER_ADMIN' || user.value?.role === 'ADMIN') return true
    return permissionSet.value.has(permission)
  }

  async function login(username, password) {
    const response = await axios.post('/api/auth/login', { username, password })
    if (response.data.code === 0) {
      user.value = response.data.data.user
      token.value = response.data.data.access_token
      localStorage.setItem('token', token.value)
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      fetchMenu().catch(err => console.error('加载菜单失败:', err))
      fetchPermissions().catch(err => console.error('加载权限失败:', err))
    }
    return response.data
  }

  async function fetchMenu() {
    if (isLoading.value) return
    isLoading.value = true
    fetchMenuError.value = null
    try {
      const response = await axios.get('/api/user/menu')
      if (response.data.code === 0) {
        menu.value = response.data.data
      }
    } catch (error) {
      fetchMenuError.value = error
      console.error('加载菜单失败:', error)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchPermissions() {
    try {
      const response = await axios.get('/api/user/permissions')
      if (response.data.code === 0) {
        permissions.value = response.data.data
      }
    } catch (error) {
      console.error('加载权限失败:', error)
    }
  }

  async function fetchUserInfo() {
    try {
      const response = await axios.get('/api/user/info')
      if (response.data.code === 0) {
        user.value = response.data.data
      }
    } catch (error) {
      console.error('获取用户信息失败:', error)
    }
  }

  function logout() {
    user.value = null
    token.value = ''
    permissions.value = []
    localStorage.removeItem('token')
    delete axios.defaults.headers.common['Authorization']
    menu.value = []
    fetchMenuError.value = null
  }

  return { user, token, menu, permissions, isLoading, fetchMenuError, login, logout, fetchMenu, fetchPermissions, fetchUserInfo, hasPermission }
})