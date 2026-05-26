import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  const menu = ref([])

  async function login(username, password) {
    const response = await axios.post('/api/auth/login', { username, password })
    if (response.data.code === 0) {
      user.value = response.data.data.user
      token.value = response.data.data.access_token
      localStorage.setItem('token', token.value)
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      await fetchMenu()
    }
    return response.data
  }

  async function fetchMenu() {
    const response = await axios.get('/api/user/menu')
    if (response.data.code === 0) {
      menu.value = response.data.data
    }
  }

  function logout() {
    user.value = null
    token.value = ''
    localStorage.removeItem('token')
    delete axios.defaults.headers.common['Authorization']
    menu.value = []
  }

  return { user, token, menu, login, logout, fetchMenu }
})