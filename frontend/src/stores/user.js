import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from '@/utils/axios'

export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  const menu = ref([])
  const isLoading = ref(false)
  const fetchMenuError = ref(null)

  async function login(username, password) {
    const response = await axios.post('/api/auth/login', { username, password })
    if (response.data.code === 0) {
      user.value = response.data.data.user
      token.value = response.data.data.access_token
      localStorage.setItem('token', token.value)
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      fetchMenu().catch(err => console.error('加载菜单失败:', err))
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

  function logout() {
    user.value = null
    token.value = ''
    localStorage.removeItem('token')
    delete axios.defaults.headers.common['Authorization']
    menu.value = []
    fetchMenuError.value = null
  }

  return { user, token, menu, isLoading, fetchMenuError, login, logout, fetchMenu }
})