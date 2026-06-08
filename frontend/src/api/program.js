import axios from '@/utils/axios'

export async function getPrograms(params = {}) {
  const response = await axios.get('/api/programs', { params })
  return response.data
}

export async function getProgram(id) {
  const response = await axios.get(`/api/programs/${id}`)
  return response.data
}

export async function createProgram(data) {
  const response = await axios.post('/api/programs', data)
  return response.data
}

export async function updateProgram(id, data) {
  const response = await axios.put(`/api/programs/${id}`, data)
  return response.data
}

export async function deleteProgram(id) {
  const response = await axios.delete(`/api/programs/${id}`)
  return response.data
}

export async function batchGetStatus(ids) {
  const response = await axios.post('/api/programs/status/batch', ids)
  return response.data
}

export async function startProgram(id) {
  const response = await axios.post(`/api/programs/${id}/start`)
  return response.data
}

export async function stopProgram(id) {
  const response = await axios.post(`/api/programs/${id}/stop`)
  return response.data
}

export async function restartProgram(id) {
  const response = await axios.post(`/api/programs/${id}/restart`)
  return response.data
}

export async function getProgramLog(id, lines = 200) {
  const response = await axios.get(`/api/programs/${id}/log`, { params: { lines } })
  return response.data
}

export async function downloadProgramLog(id) {
  window.open(`/api/programs/${id}/log/download`)
}

export async function exportPrograms() {
  window.open('/api/programs/export')
}

export async function importPrograms(file) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await axios.post('/api/programs/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return response.data
}