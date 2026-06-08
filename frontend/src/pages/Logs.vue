<template>
  <div class="logs-page">
    <div class="page-header">
      <h2>日志中心</h2>
    </div>
    
    <div class="log-controls">
      <el-select v-model="selectedServiceId" placeholder="选择服务" @change="loadLogs">
        <el-option v-for="service in services" :key="service.id" :label="service.service_name" :value="service.id" />
      </el-select>
      <el-select v-model="lineCount" @change="loadLogs">
        <el-option label="最近100行" :value="100" />
        <el-option label="最近500行" :value="500" />
        <el-option label="最近1000行" :value="1000" />
        <el-option label="全部" :value="0" />
      </el-select>
      <el-input v-model="keyword" placeholder="关键词过滤" @keyup.enter="loadLogs" />
      <el-button @click="loadLogs">刷新</el-button>
      <el-button @click="toggleLiveMode" :type="liveMode ? 'danger' : 'success'">
        {{ liveMode ? '停止实时' : '实时监控' }}
      </el-button>
    </div>
    
    <div class="log-content">
      <pre>{{ logContent }}</pre>
    </div>
    
    <div class="auto-scroll" v-if="autoScroll">
      <el-checkbox v-model="autoScroll">自动滚动</el-checkbox>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import axios from '@/utils/axios'

const services = ref([])
const selectedServiceId = ref('')
const lineCount = ref(100)
const keyword = ref('')
const logContent = ref('')
const liveMode = ref(false)
const autoScroll = ref(true)

let websocket = null

async function loadServices() {
  const response = await axios.get('/api/services')
  if (response.data.code === 0) {
    services.value = response.data.data.filter(s => s.log_path)
  }
}

async function loadLogs() {
  if (!selectedServiceId.value) {
    logContent.value = '请选择一个服务'
    return
  }
  
  try {
    const response = await axios.get(`/api/logs/${selectedServiceId.value}`, {
      params: { lines: lineCount.value, keyword: keyword.value }
    })
    
    if (response.data.code === 0) {
      logContent.value = response.data.data.content || ''
    } else {
      logContent.value = response.data.message
    }
  } catch (error) {
    logContent.value = '加载日志失败'
  }
}

function toggleLiveMode() {
  liveMode.value = !liveMode.value
  
  if (liveMode.value) {
    connectWebSocket()
  } else {
    disconnectWebSocket()
  }
}

function connectWebSocket() {
  if (!selectedServiceId.value) {
    ElMessage.error('请先选择服务')
    liveMode.value = false
    return
  }
  
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  websocket = new WebSocket(`${wsProtocol}//${window.location.host}/api/logs/ws/${selectedServiceId.value}`)
  
  websocket.onopen = () => {
    logContent.value = '正在连接...\n'
  }
  
  websocket.onmessage = (event) => {
    logContent.value += event.data
    if (autoScroll.value) {
      nextTick(() => {
        const preElement = document.querySelector('.log-content pre')
        if (preElement) {
          preElement.scrollTop = preElement.scrollHeight
        }
      })
    }
  }
  
  websocket.onerror = (error) => {
    logContent.value += `\n连接错误: ${error.message}`
    liveMode.value = false
  }
  
  websocket.onclose = () => {
    if (liveMode.value) {
      logContent.value += '\n连接断开，正在重连...'
      setTimeout(connectWebSocket, 3000)
    }
  }
}

function disconnectWebSocket() {
  if (websocket) {
    websocket.close()
    websocket = null
  }
}

watch(selectedServiceId, () => {
  if (liveMode.value) {
    disconnectWebSocket()
    connectWebSocket()
  } else {
    loadLogs()
  }
})

onMounted(() => {
  loadServices()
})

onUnmounted(() => {
  disconnectWebSocket()
})
</script>

<style scoped>
.logs-page {
  padding: 20px;
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
}

.page-header {
  margin-bottom: 20px;
}

.log-controls {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.log-content {
  flex: 1;
  background: #1f2937;
  color: #e5e7eb;
  padding: 20px;
  border-radius: 8px;
  overflow: auto;
}

.log-content pre {
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
  line-height: 1.5;
}

.auto-scroll {
  margin-top: 10px;
}
</style>