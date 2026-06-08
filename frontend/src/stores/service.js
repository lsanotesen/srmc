import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from '@/utils/axios'

export const useServiceStore = defineStore('service', () => {
  const services = ref([])
  const selectedService = ref(null)

  async function getServices(params = {}) {
    const response = await axios.get('/api/services', { params })
    if (response.data.code === 0) {
      services.value = response.data.data
    }
    return response.data
  }

  async function getService(id) {
    const response = await axios.get(`/api/services/${id}`)
    if (response.data.code === 0) {
      selectedService.value = response.data.data
    }
    return response.data
  }

  async function createService(data) {
    const response = await axios.post('/api/services', data)
    return response.data
  }

  async function updateService(id, data) {
    const response = await axios.put(`/api/services/${id}`, data)
    return response.data
  }

  async function deleteService(id) {
    const response = await axios.delete(`/api/services/${id}`)
    return response.data
  }

  async function startService(id) {
    const response = await axios.post(`/api/monitor/start/${id}`)
    return response.data
  }

  async function stopService(id) {
    const response = await axios.post(`/api/monitor/stop/${id}`)
    return response.data
  }

  async function restartService(id) {
    const response = await axios.post(`/api/monitor/restart/${id}`)
    return response.data
  }

  return {
    services,
    selectedService,
    getServices,
    getService,
    createService,
    updateService,
    deleteService,
    startService,
    stopService,
    restartService
  }
})