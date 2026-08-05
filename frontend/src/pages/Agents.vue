<template>
  <div class="agents-page">
    <div class="page-header">
      <h1>Agent 管理</h1>
      <div class="actions">
        <el-button v-if="hasPermission('agent:manage')" type="success" @click="batchControl('start')" :disabled="!selectedAgents.length">
          批量启动 ({{ selectedAgents.length }})
        </el-button>
        <el-button v-if="hasPermission('agent:manage')" type="warning" @click="batchControl('restart')" :disabled="!selectedAgents.length">
          批量重启 ({{ selectedAgents.length }})
        </el-button>
        <el-button v-if="hasPermission('agent:manage')" type="danger" @click="batchControl('stop')" :disabled="!selectedAgents.length">
          批量停止 ({{ selectedAgents.length }})
        </el-button>
        <el-button type="primary" @click="loadAgents">刷新</el-button>
      </div>
    </div>

    <div class="search-bar">
      <el-input v-model="searchKeyword" placeholder="搜索主机名或IP" class="search-input" @keyup.enter="loadAgents" />
      <el-select v-model="statusFilter" placeholder="状态筛选" clearable class="status-select">
        <el-option label="在线" value="online" />
        <el-option label="离线" value="offline" />
      </el-select>
      <el-button type="primary" @click="loadAgents">搜索</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <div class="table-wrapper">
      <el-table 
        :data="agents" 
        border 
        fit 
        :header-cell-style="{ 'white-space': 'nowrap' }"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="hostname" label="主机名" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP地址" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="scope">
            <el-tag :type="scope.row.is_online ? 'success' : 'danger'">
              {{ scope.row.is_online ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="CPU" width="75">
          <template #default="scope">
            <span>{{ formatPercent(scope.row.metrics?.cpu_percent) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="内存" width="75">
          <template #default="scope">
            <span>{{ formatPercent(scope.row.metrics?.memory_percent) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="磁盘" width="75">
          <template #default="scope">
            <span>{{ formatPercent(scope.row.metrics?.disk_percent) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Load" width="75">
          <template #default="scope">
            <span>{{ formatLoad(scope.row.metrics?.load1) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="系统" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ scope.row.os || '--' }} ({{ scope.row.cpu_cores || 0 }}核)</span>
          </template>
        </el-table-column>
        <el-table-column label="内存总量" width="95" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ formatMemory(scope.row.memory_total) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Agent版本" width="100" show-overflow-tooltip>
          <template #default="scope">
            <span>v{{ scope.row.agent_version || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最后心跳" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ formatDateTime(scope.row.last_heartbeat) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" align="center">
          <template #default="scope">
            <div class="action-buttons">
              <div class="action-btn view-btn" @click="viewAgent(scope.row)">
                <span>详情</span>
              </div>
              <div class="action-btn edit-btn" @click="viewAgentServices(scope.row)">
                <span>服务</span>
              </div>
              <div v-if="hasPermission('agent:manage')" class="action-btn start-btn" @click="controlAgent(scope.row, 'start')">
                <span>启动</span>
              </div>
              <div v-if="hasPermission('agent:manage')" class="action-btn restart-btn" @click="controlAgent(scope.row, 'restart')">
                <span>重启</span>
              </div>
              <div v-if="hasPermission('agent:manage')" class="action-btn stop-btn" @click="controlAgent(scope.row, 'stop')">
                <span>停止</span>
              </div>
              <div v-if="hasPermission('agent:manage')" class="action-btn config-btn" @click="openConfigDialog(scope.row)">
                <span>配置</span>
              </div>
              <div v-if="hasPermission('agent:manage')" class="action-btn delete-btn" @click="deleteAgent(scope.row)">
                <span>删除</span>
              </div>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog title="Agent 详情" v-model="showDetailDialog" width="600px">
      <div v-if="selectedAgent" class="agent-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="主机名">{{ selectedAgent.hostname }}</el-descriptions-item>
          <el-descriptions-item label="IP地址">{{ selectedAgent.ip }}</el-descriptions-item>
          <el-descriptions-item label="操作系统">{{ selectedAgent.os }}</el-descriptions-item>
          <el-descriptions-item label="内核版本">{{ selectedAgent.kernel }}</el-descriptions-item>
          <el-descriptions-item label="架构">{{ selectedAgent.arch }}</el-descriptions-item>
          <el-descriptions-item label="CPU型号">{{ selectedAgent.cpu_model }}</el-descriptions-item>
          <el-descriptions-item label="CPU核心">{{ selectedAgent.cpu_cores }}</el-descriptions-item>
          <el-descriptions-item label="内存总量">{{ formatMemory(selectedAgent.memory_total) }}</el-descriptions-item>
          <el-descriptions-item label="Agent版本">{{ selectedAgent.agent_version }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="selectedAgent.is_online ? 'success' : 'danger'">
              {{ selectedAgent.is_online ? '在线' : '离线' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="最后心跳" :span="2">
            {{ selectedAgent.last_heartbeat ? formatDateTime(selectedAgent.last_heartbeat) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="UUID" :span="2">{{ selectedAgent.uuid }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="selectedAgent.capabilities && selectedAgent.capabilities.length > 0" style="margin-top: 20px;">
          <h4>能力列表</h4>
          <div class="capabilities">
            <el-tag v-for="cap in selectedAgent.capabilities" :key="cap" size="small">{{ cap }}</el-tag>
          </div>
        </div>
        <div v-if="selectedAgent.tags && selectedAgent.tags.length > 0" style="margin-top: 10px;">
          <h4>标签</h4>
          <div class="tags">
            <el-tag v-for="tag in selectedAgent.tags" :key="tag" size="small" type="info">{{ tag }}</el-tag>
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog title="Agent 服务列表" v-model="showServicesDialog" width="800px">
      <div v-if="agentServices.length > 0">
        <el-table :data="agentServices" border>
          <el-table-column type="index" label="序号" width="80" />
          <el-table-column prop="name" label="服务名称" min-width="150" />
          <el-table-column prop="deploy_type" label="部署方式" min-width="120">
            <template #default="scope">
              <el-tag :type="getDeployType(scope.row.deploy_type).type">
                {{ getDeployType(scope.row.deploy_type).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="port" label="端口" width="100" />
          <el-table-column prop="docker_name" label="容器名称" min-width="150" />
        </el-table>
      </div>
      <div v-else style="text-align: center; padding: 40px;">
        <p>该 Agent 暂无关联服务</p>
      </div>
    </el-dialog>

    <el-dialog title="Agent 控制配置" v-model="showConfigDialog" width="500px">
      <el-form :model="configForm" label-width="120px" style="padding: 10px;">
        <el-form-item label="主机名">
          <span>{{ configForm.hostname }}</span>
        </el-form-item>
        <el-form-item label="IP地址">
          <span>{{ configForm.ip }}</span>
        </el-form-item>
        <el-form-item label="SSH端口">
          <el-input v-model="configForm.ssh_port" type="number" placeholder="默认 22" />
        </el-form-item>
        <el-form-item label="SSH用户名">
          <el-input v-model="configForm.ssh_username" placeholder="请输入 SSH 用户名" />
        </el-form-item>
        <el-form-item label="SSH密码">
          <el-input v-model="configForm.ssh_password" type="password" placeholder="请输入 SSH 密码" show-password />
        </el-form-item>
        <el-form-item label="服务名">
          <el-input v-model="configForm.service_name" placeholder="默认 srmc-agent" />
        </el-form-item>
        <div v-if="configForm.ssh_username" style="margin-top: 10px; padding: 10px; background: #f5f7fa; border-radius: 4px;">
          <el-tag type="success" size="small">✓ 已配置 SSH 凭据</el-tag>
          <span style="margin-left: 10px; font-size: 13px; color: #606266;">可通过 SSH 远程控制该 Agent</span>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="showConfigDialog = false">取消</el-button>
        <el-button type="primary" @click="saveConfig">保存配置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePermission } from '@/composables/usePermission'

const { hasPermission } = usePermission()

const agents = ref([])
const searchKeyword = ref('')
const statusFilter = ref('')
const showDetailDialog = ref(false)
const showServicesDialog = ref(false)
const showConfigDialog = ref(false)
const selectedAgent = ref(null)
const agentServices = ref([])
const selectedAgents = ref([])
const configForm = ref({
  agent_uuid: '',
  hostname: '',
  ip: '',
  ssh_port: 22,
  ssh_username: '',
  ssh_password: '',
  service_name: 'srmc-agent'
})

const loadAgents = async () => {
  try {
    const response = await fetch('/api/agents/', {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
    })
    const data = await response.json()
    if (data.code === 0) {
      let result = data.data
      if (searchKeyword.value) {
        const keyword = searchKeyword.value.toLowerCase()
        result = result.filter(a => 
          a.hostname.toLowerCase().includes(keyword) || 
          a.ip.toLowerCase().includes(keyword)
        )
      }
      if (statusFilter.value) {
        result = result.filter(a => 
          statusFilter.value === 'online' ? a.is_online : !a.is_online
        )
      }
      agents.value = result
      
      for (const agent of agents.value) {
        if (agent.is_online) {
          await loadAgentMetrics(agent.uuid)
        }
      }
    } else {
      ElMessage.error('加载失败')
    }
  } catch (error) {
    ElMessage.error('加载失败')
  }
}

const loadAgentMetrics = async (agent_uuid) => {
  try {
    const response = await fetch(`/api/agents/${agent_uuid}/metrics/`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
    })
    const data = await response.json()
    if (data.code === 0) {
      const agent = agents.value.find(a => a.uuid === agent_uuid)
      if (agent) {
        agent.metrics = data.data.system || {}
        agent.docker_containers = data.data.docker_containers || []
        agent.compose_projects = data.data.compose_projects || []
      }
    }
  } catch (error) {
    console.error('加载 Agent 指标失败:', error)
  }
}

const resetFilters = () => {
  searchKeyword.value = ''
  statusFilter.value = ''
  loadAgents()
}

const handleSelectionChange = (selection) => {
  selectedAgents.value = selection
}

const getToken = () => localStorage.getItem('token')

const controlAgent = async (agent, action) => {
  const actionLabels = { start: '启动', stop: '停止', restart: '重启', status: '状态' }
  try {
    await ElMessageBox.confirm(
      `确定要${actionLabels[action]} Agent "${agent.hostname} (${agent.ip})" 吗？`,
      '操作确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const response = await fetch(`/api/agents/${agent.uuid}/control`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}` 
      },
      body: JSON.stringify({ action })
    })
    const data = await response.json()
    if (data.code === 0 && data.data.success) {
      ElMessage.success(data.data.message)
      loadAgents()
    } else {
      ElMessage.error(data.data.message || '操作失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('控制 Agent 失败:', error)
    }
  }
}

const batchControl = async (action) => {
  if (!selectedAgents.value.length) return
  
  const actionLabels = { start: '启动', stop: '停止', restart: '重启' }
  try {
    await ElMessageBox.confirm(
      `确定要批量${actionLabels[action]} ${selectedAgents.value.length} 个 Agent 吗？`,
      '批量操作确认',
      {
        confirmButtonText: '确定执行',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const agent_uuids = selectedAgents.value.map(a => a.uuid)
    const response = await fetch('/api/agents/batch-control', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}` 
      },
      body: JSON.stringify({ action, agent_uuids })
    })
    const data = await response.json()
    if (data.code === 0) {
      const result = data.data
      const message = `总共 ${result.total} 个 Agent，成功 ${result.success} 个，失败 ${result.failed} 个`
      if (result.failed === 0) {
        ElMessage.success(message)
      } else {
        ElMessage.warning(message)
        // 显示失败详情
        const failedAgents = result.results.filter(r => !r.success)
        if (failedAgents.length > 0) {
          console.warn('失败详情:', failedAgents)
        }
      }
      loadAgents()
    } else {
      ElMessage.error(data.message || '批量操作失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量控制失败:', error)
    }
  }
}

const openConfigDialog = (agent) => {
  configForm.value = {
    agent_uuid: agent.uuid,
    hostname: agent.hostname,
    ip: agent.ip,
    ssh_port: agent.ssh_port || 22,
    ssh_username: agent.ssh_username || '',
    ssh_password: '',
    service_name: agent.service_name || 'srmc-agent'
  }
  showConfigDialog.value = true
}

const saveConfig = async () => {
  try {
    const response = await fetch(`/api/agents/${configForm.value.agent_uuid}/config`, {
      method: 'PUT',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}` 
      },
      body: JSON.stringify({
        ssh_port: configForm.value.ssh_port,
        ssh_username: configForm.value.ssh_username,
        ssh_password: configForm.value.ssh_password,
        service_name: configForm.value.service_name
      })
    })
    const data = await response.json()
    if (data.code === 0) {
      ElMessage.success('配置保存成功')
      showConfigDialog.value = false
      loadAgents()
    } else {
      ElMessage.error(data.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error('保存配置失败')
  }
}

const viewAgent = (agent) => {
  selectedAgent.value = agent
  showDetailDialog.value = true
}

const viewAgentServices = async (agent) => {
  try {
    const response = await fetch(`/api/agents/${agent.uuid}/services/`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
    })
    const data = await response.json()
    if (data.code === 0) {
      agentServices.value = data.data
      showServicesDialog.value = true
    } else {
      ElMessage.error('加载服务列表失败')
    }
  } catch (error) {
    ElMessage.error('加载服务列表失败')
  }
}

const deleteAgent = async (agent) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 Agent "${agent.hostname} (${agent.ip})" 吗？删除后，关联的服务将自动解除关联。如果误删，重启 Agent 后会自动重新注册。`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
    
    const response = await fetch(`/api/agents/${agent.uuid}/`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
    })
    const data = await response.json()
    if (data.code === 0) {
      ElMessage.success('Agent 删除成功')
      loadAgents()
    } else {
      ElMessage.error(data.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除 Agent 失败:', error)
    }
  }
}

const formatMemory = (bytes) => {
  if (!bytes) return '-'
  if (bytes >= 1024 * 1024 * 1024) {
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
  } else if (bytes >= 1024 * 1024) {
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
  } else if (bytes >= 1024) {
    return (bytes / 1024).toFixed(2) + ' KB'
  }
  return bytes + ' B'
}

const formatPercent = (value) => {
  if (value === undefined || value === null || isNaN(value)) return '--'
  return value.toFixed(1) + '%'
}

const formatLoad = (value) => {
  if (value === undefined || value === null || isNaN(value)) return '--'
  return value.toFixed(2)
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const getDeployType = (type) => {
  const types = {
    'HOST': { label: '主机部署', type: 'info' },
    'DOCKER': { label: 'Docker容器', type: 'success' },
    'DOCKER_COMPOSE': { label: 'Docker Compose', type: 'warning' }
  }
  return types[type] || { label: type, type: 'default' }
}

onMounted(() => {
  loadAgents()
  setInterval(loadAgents, 10000)
})
</script>

<style scoped>
.agents-page {
  padding: 20px;
}

.table-wrapper {
  overflow-x: auto;
  width: 100%;
  min-width: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  margin: 0;
}

.actions {
  display: flex;
  gap: 10px;
}

.search-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  align-items: center;
}

.search-input {
  width: 200px;
}

.status-select {
  width: 120px;
}

.agent-detail {
  padding: 10px;
}

.capabilities, .tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 4px;
}

.action-btn {
  width: 56px;
  height: 28px;
  border-radius: 4px;
  font-weight: 500;
  font-size: 13px;
  transition: all 0.25s ease;
  border: none;
  color: #fff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
  padding: 0;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  outline: none;
  text-align: center;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    filter: brightness(1.1);
  }

  &:active {
    transform: translateY(0);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
  }
}

.view-btn {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
}

.edit-btn {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
}

.start-btn {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.restart-btn {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}

.stop-btn {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.config-btn {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
}

.delete-btn {
  background: linear-gradient(135deg, #9ca3af 0%, #6b7280 100%);
}

/* 批量按钮禁用样式 */
.el-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>