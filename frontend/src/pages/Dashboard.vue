<template>
  <div class="dashboard">
    <div class="stats-grid">
      <el-card class="stat-card">
        <div class="stat-icon running">
          <el-icon component="Play" />
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.running }}</div>
          <div class="stat-label">运行中</div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-icon stopped">
          <el-icon component="Stop" />
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.stopped }}</div>
          <div class="stat-label">已停止</div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-icon unknown">
          <el-icon component="Help" />
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.unknown }}</div>
          <div class="stat-label">未知</div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-icon total">
          <el-icon component="Server" />
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">服务总数</div>
        </div>
      </el-card>
    </div>
    
    <div class="charts-row">
      <el-card title="服务状态分布" class="chart-card">
        <div class="status-chart">
          <div class="chart-bar" :style="{ height: runningPercent + '%', background: '#10b981' }">
            <span>运行中</span>
          </div>
          <div class="chart-bar" :style="{ height: stoppedPercent + '%', background: '#ef4444' }">
            <span>已停止</span>
          </div>
          <div class="chart-bar" :style="{ height: unknownPercent + '%', background: '#f59e0b' }">
            <span>未知</span>
          </div>
        </div>
      </el-card>
      
      <el-card title="最近操作" class="recent-actions">
        <el-timeline>
          <el-timeline-item v-for="action in recentActions" :key="action.id" :timestamp="action.time">
            <el-card size="small">
              <div class="action-content">
                <span class="action-user">{{ action.user }}</span>
                <span class="action-type">{{ action.type }}</span>
                <span class="action-target">{{ action.target }}</span>
              </div>
              <div class="action-result" :class="action.result">{{ action.result }}</div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </div>
    
    <div class="services-table">
      <el-card title="服务状态一览">
        <el-table :data="services" border>
          <el-table-column prop="service_name" label="服务名称" />
          <el-table-column prop="service_code" label="服务编码" />
          <el-table-column prop="service_type" label="服务类型" />
          <el-table-column prop="environment" label="环境" />
          <el-table-column prop="ip" label="IP" />
          <el-table-column prop="status" label="状态">
            <template #default="scope">
              <el-tag :type="getStatusType(scope.row.status)">{{ scope.row.status }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Play, Stop, Help, Server } from '@element-plus/icons-vue'
import axios from 'axios'

const stats = ref({ running: 0, stopped: 0, unknown: 0, total: 0 })
const services = ref([])
const recentActions = ref([])

const runningPercent = computed(() => {
  return stats.value.total > 0 ? (stats.value.running / stats.value.total * 100).toFixed(0) : 0
})

const stoppedPercent = computed(() => {
  return stats.value.total > 0 ? (stats.value.stopped / stats.value.total * 100).toFixed(0) : 0
})

const unknownPercent = computed(() => {
  return stats.value.total > 0 ? (stats.value.unknown / stats.value.total * 100).toFixed(0) : 0
})

function getStatusType(status) {
  switch (status) {
    case 'RUNNING': return 'success'
    case 'STOPPED': return 'danger'
    default: return 'warning'
  }
}

async function refreshData() {
  try {
    const response = await axios.get('/api/monitor/status')
    if (response.data.code === 0) {
      stats.value = {
        running: response.data.data.running,
        stopped: response.data.data.stopped,
        unknown: response.data.data.unknown,
        total: response.data.data.total
      }
      services.value = response.data.data.results
    }
    
    const auditResponse = await axios.get('/api/audit', { params: { limit: 5 } })
    if (auditResponse.data.code === 0) {
      recentActions.value = auditResponse.data.data.items.map(item => ({
        id: item.id,
        user: item.username,
        type: item.action,
        target: item.service_code || item.ip || '系统',
        result: item.result,
        time: item.created_at
      }))
    }
  } catch (error) {
    console.error('Failed to refresh data:', error)
  }
}

let timer = null

onMounted(() => {
  refreshData()
  timer = setInterval(refreshData, 10000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 20px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 24px;
}

.stat-icon.running {
  background: linear-gradient(135deg, #10b981, #059669);
}

.stat-icon.stopped {
  background: linear-gradient(135deg, #ef4444, #dc2626);
}

.stat-icon.unknown {
  background: linear-gradient(135deg, #f59e0b, #d97706);
}

.stat-icon.total {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #1f2937;
}

.stat-label {
  color: #6b7280;
  font-size: 14px;
}

.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.chart-card {
  height: 250px;
}

.status-chart {
  display: flex;
  justify-content: space-around;
  align-items: flex-end;
  height: 150px;
  padding: 20px;
}

.chart-bar {
  width: 80px;
  border-radius: 8px 8px 0 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding-top: 10px;
  color: #fff;
  font-size: 12px;
  transition: height 0.5s ease;
}

.recent-actions {
  height: 250px;
  overflow-y: auto;
}

.action-content {
  display: flex;
  gap: 10px;
  margin-bottom: 5px;
}

.action-user {
  font-weight: bold;
}

.action-type {
  color: #6366f1;
}

.action-target {
  color: #6b7280;
}

.action-result {
  font-size: 12px;
}

.action-result.success {
  color: #10b981;
}

.action-result.failed {
  color: #ef4444;
}

.services-table {
  margin-top: 20px;
}
</style>