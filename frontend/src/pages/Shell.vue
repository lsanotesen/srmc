<template>
  <div class="shell-page">
    <div class="page-header">
      <h2>WebShell</h2>
      <div v-if="targetServiceName" class="target-info">
        <el-tag type="primary" size="large">
          <el-icon name="server" :size="14" />
          {{ targetServiceName }}
        </el-tag>
      </div>
      <el-select v-model="selectedServiceId" placeholder="选择服务" class="service-select">
        <el-option v-for="service in services" :key="service.id" :label="service.service_name" :value="service.id" />
      </el-select>
      <el-button @click="connect" :disabled="!selectedServiceId || connected" type="primary">连接</el-button>
      <el-button @click="disconnect" :disabled="!connected" type="danger">断开</el-button>
    </div>
    
    <div class="terminal-container">
      <div ref="terminalRef" class="terminal"></div>
    </div>
    
    <div class="status-bar" v-if="connected">
      <span class="status connected">已连接</span>
      <span class="host-info">{{ currentHost }}</span>
    </div>
    <div class="status-bar" v-else>
      <span class="status disconnected">未连接</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import { ElMessage } from 'element-plus'
import axios from '@/utils/axios'

const route = useRoute()
const services = ref([])
const selectedServiceId = ref('')
const selectedServerId = ref('')
const terminalRef = ref(null)
const connected = ref(false)
const currentHost = ref('')
const targetServiceName = ref('')

let terminal = null
let websocket = null

async function loadServices() {
  const token = localStorage.getItem('token')
  const response = await axios.get('/api/services', {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (response.data.code === 0) {
    services.value = response.data.data.filter(s => s.work_dir && s.server_id)
    
    if (route.query.serviceId) {
      selectedServiceId.value = parseInt(route.query.serviceId)
      selectedServerId.value = route.query.serverId || ''
      targetServiceName.value = route.query.serviceName || ''
    }
  }
}

function initTerminal() {
  if (!terminalRef.value) return
  
  terminal = new Terminal({
    fontSize: 14,
    fontFamily: 'Monaco, Menlo, monospace',
    theme: {
      background: '#1f2937',
      foreground: '#e5e7eb',
      cursor: '#ffffff',
      selection: '#4b5563'
    }
  })
  
  const fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(terminalRef.value)
  fitAddon.fit()
  
  terminal.onData((data) => {
    if (websocket) {
      websocket.send(data)
    }
  })
  
  window.addEventListener('resize', () => {
    fitAddon.fit()
  })
}

function connect() {
  if (!selectedServiceId.value && !selectedServerId.value) {
    ElMessage.error('请选择服务')
    return
  }
  
  const service = services.value.find(s => s.id === selectedServiceId.value)
  if (service) {
    currentHost.value = `${service.ip}:${service.port || '22'}`
  }
  
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const targetId = selectedServerId.value || selectedServiceId.value
  websocket = new WebSocket(`${wsProtocol}//${window.location.host}/api/shell/ws/${targetId}`)
  
  websocket.onopen = () => {
    connected.value = true
    terminal.write('\r\n[连接中] 正在连接到服务器...\r\n')
  }
  
  websocket.onmessage = (event) => {
    terminal.write(event.data)
  }
  
  websocket.onerror = (error) => {
    terminal.write('\r\n[错误] 连接失败: ' + error.message + '\r\n')
    connected.value = false
  }
  
  websocket.onclose = () => {
    terminal.write('\r\n[断开] 连接已关闭\r\n')
    connected.value = false
    websocket = null
  }
}

function disconnect() {
  if (websocket) {
    websocket.close()
  }
}

watch(selectedServiceId, () => {
  if (connected.value) {
    disconnect()
  }
})

onMounted(async () => {
  await loadServices()
  nextTick(() => {
    initTerminal()
    if (selectedServiceId.value) {
      connect()
    }
  })
})

onUnmounted(() => {
  disconnect()
  if (terminal) {
    terminal.dispose()
  }
})
</script>

<style scoped>
.shell-page {
  padding: 20px;
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.page-header h2 {
  margin: 0;
}

.target-info {
  display: flex;
  align-items: center;
}

.target-info .el-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 14px;
}

.service-select {
  width: 200px;
}

.terminal-container {
  flex: 1;
  background: #1f2937;
  border-radius: 8px;
  overflow: hidden;
}

.terminal {
  width: 100%;
  height: 100%;
}

.status-bar {
  margin-top: 10px;
  padding: 8px 15px;
  background: #f3f4f6;
  border-radius: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status {
  font-weight: bold;
  padding: 4px 12px;
  border-radius: 4px;
}

.status.connected {
  background: #d1fae5;
  color: #065f46;
}

.status.disconnected {
  background: #fee2e2;
  color: #991b1b;
}

.host-info {
  color: #6b7280;
}
</style>