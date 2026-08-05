<template>
  <div class="monitoring-container">
    <el-row :gutter="20">
      <!-- 系统概览 -->
      <el-col :span="24">
        <el-card class="overview-card">
          <template #header>
            <div class="card-header">
              <span>系统概览</span>
              <el-button type="primary" size="small" @click="refreshData">刷新</el-button>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-label">总服务数</div>
                <div class="stat-value">{{ totalServices }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-label">运行中</div>
                <div class="stat-value running">{{ runningServices }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-label">已停止</div>
                <div class="stat-value stopped">{{ stoppedServices }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-label">告警数</div>
                <div class="stat-value warning">{{ alertCount }}</div>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>

      <!-- 服务器资源监控 -->
      <el-col :span="12">
        <el-card class="resource-card">
          <template #header>
            <div class="card-header">
              <span>CPU使用率</span>
            </div>
          </template>
          <div ref="cpuChartRef" style="height: 300px;"></div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="resource-card">
          <template #header>
            <div class="card-header">
              <span>内存使用率</span>
            </div>
          </template>
          <div ref="memoryChartRef" style="height: 300px;"></div>
        </el-card>
      </el-col>

      <!-- 服务状态列表 -->
      <el-col :span="24">
        <el-card class="services-card">
          <template #header>
            <div class="card-header">
              <span>服务状态</span>
              <el-select v-model="statusFilter" placeholder="状态筛选" style="width: 150px;">
                <el-option label="全部" value=""></el-option>
                <el-option label="运行中" value="RUNNING"></el-option>
                <el-option label="已停止" value="STOPPED"></el-option>
                <el-option label="异常" value="ERROR"></el-option>
              </el-select>
            </div>
          </template>
          <el-table :data="filteredServices" style="width: 100%">
            <el-table-column prop="name" label="服务名称" width="200"></el-table-column>
            <el-table-column prop="ip" label="IP地址" width="150"></el-table-column>
            <el-table-column prop="port" label="端口" width="100"></el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="memory_mb" label="内存(MB)" width="120">
              <template #default="{ row }">
                {{ row.memory_mb?.toFixed(2) || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="cpu_percent" label="CPU(%)" width="100">
              <template #default="{ row }">
                {{ row.cpu_percent?.toFixed(2) || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="uptime_seconds" label="运行时间" width="150">
              <template #default="{ row }">
                {{ formatUptime(row.uptime_seconds) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" @click="viewDetails(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 告警列表 -->
      <el-col :span="24">
        <el-card class="alerts-card">
          <template #header>
            <div class="card-header">
              <span>告警列表</span>
              <el-badge :value="alertCount" class="item">
                <el-button size="small">查看全部</el-button>
              </el-badge>
            </div>
          </template>
          <el-table :data="alerts" style="width: 100%">
            <el-table-column prop="alertname" label="告警名称" width="200"></el-table-column>
            <el-table-column prop="instance" label="实例" width="200"></el-table-column>
            <el-table-column prop="severity" label="级别" width="100">
              <template #default="{ row }">
                <el-tag :type="getSeverityType(row.severity)">{{ row.severity }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="summary" label="摘要"></el-table-column>
            <el-table-column prop="startsAt" label="开始时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.startsAt) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="服务详情" width="800px">
      <div v-if="selectedService">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="服务名称">{{ selectedService.name }}</el-descriptions-item>
          <el-descriptions-item label="IP地址">{{ selectedService.ip }}</el-descriptions-item>
          <el-descriptions-item label="端口">{{ selectedService.port }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(selectedService.status)">{{ selectedService.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="内存使用">{{ selectedService.memory_mb?.toFixed(2) }} MB</el-descriptions-item>
          <el-descriptions-item label="CPU使用">{{ selectedService.cpu_percent?.toFixed(2) }}%</el-descriptions-item>
          <el-descriptions-item label="运行时间" :span="2">{{ formatUptime(selectedService.uptime_seconds) }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

// 数据
const services = ref([])
const alerts = ref([])
const statusFilter = ref('')
const detailDialogVisible = ref(false)
const selectedService = ref(null)
const cpuChartRef = ref(null)
const memoryChartRef = ref(null)
let cpuChart = null
let memoryChart = null
let refreshInterval = null

// 计算属性
const filteredServices = computed(() => {
  if (!statusFilter.value) return services.value
  return services.value.filter(s => s.status === statusFilter.value)
})

const totalServices = computed(() => services.value.length)
const runningServices = computed(() => services.value.filter(s => s.status === 'RUNNING').length)
const stoppedServices = computed(() => services.value.filter(s => s.status === 'STOPPED').length)
const alertCount = computed(() => alerts.value.length)

// 方法
const getStatusType = (status) => {
  const types = {
    'RUNNING': 'success',
    'STOPPED': 'danger',
    'ERROR': 'warning'
  }
  return types[status] || 'info'
}

const getSeverityType = (severity) => {
  const types = {
    'critical': 'danger',
    'warning': 'warning',
    'info': 'info'
  }
  return types[severity] || 'info'
}

const formatUptime = (seconds) => {
  if (!seconds) return '-'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  
  if (days > 0) return `${days}天${hours}小时`
  if (hours > 0) return `${hours}小时${minutes}分钟`
  return `${minutes}分钟`
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const refreshData = async () => {
  try {
    // 获取服务状态
    const servicesRes = await axios.get('/api/metrics/services')
    services.value = servicesRes.data.data || []
    
    // 获取告警信息
    const alertsRes = await axios.get('/api/alerts')
    alerts.value = alertsRes.data.data || []
    
    // 更新图表
    updateCharts()
  } catch (error) {
    console.error('刷新数据失败:', error)
  }
}

const updateCharts = () => {
  // 更新CPU图表
  if (cpuChart) {
    const cpuData = services.value.map(s => ({
      name: s.name,
      value: s.cpu_percent || 0
    }))
    cpuChart.setOption({
      series: [{
        data: cpuData
      }]
    })
  }
  
  // 更新内存图表
  if (memoryChart) {
    const memoryData = services.value.map(s => ({
      name: s.name,
      value: s.memory_mb || 0
    }))
    memoryChart.setOption({
      series: [{
        data: memoryData
      }]
    })
  }
}

const initCharts = () => {
  // 初始化CPU图表
  if (cpuChartRef.value) {
    cpuChart = echarts.init(cpuChartRef.value)
    cpuChart.setOption({
      tooltip: {
        trigger: 'item'
      },
      series: [{
        type: 'pie',
        radius: '70%',
        data: [],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }]
    })
  }
  
  // 初始化内存图表
  if (memoryChartRef.value) {
    memoryChart = echarts.init(memoryChartRef.value)
    memoryChart.setOption({
      tooltip: {
        trigger: 'item'
      },
      series: [{
        type: 'pie',
        radius: '70%',
        data: [],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }]
    })
  }
}

const viewDetails = (service) => {
  selectedService.value = service
  detailDialogVisible.value = true
}

// 生命周期
onMounted(() => {
  initCharts()
  refreshData()
  
  // 定期刷新数据
  refreshInterval = setInterval(refreshData, 30000)
  
  // 监听窗口大小变化
  window.addEventListener('resize', () => {
    cpuChart?.resize()
    memoryChart?.resize()
  })
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
  cpuChart?.dispose()
  memoryChart?.dispose()
})
</script>

<style scoped>
.monitoring-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.overview-card,
.resource-card,
.services-card,
.alerts-card {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 4px;
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 10px;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #303133;
}

.stat-value.running {
  color: #67c23a;
}

.stat-value.stopped {
  color: #f56c6c;
}

.stat-value.warning {
  color: #e6a23c;
}
</style>