<template>
  <div class="dashboard">
    <div class="page-header">
      <div class="header-left">
        <h1>服务管理</h1>
        <p class="subtitle">实时监控系统服务状态</p>
      </div>
      <div class="header-right">
        <div class="refresh-btn" @click="loadData">
          <el-icon icon="refresh" :size="18" />
          <span>刷新数据</span>
        </div>
      </div>
    </div>

    <div class="stats-section">
      <div class="stats-grid">
        <el-card class="stat-card running-card">
          <div class="stat-icon-wrapper">
            <el-icon icon="play" :size="32" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.running }}</div>
            <div class="stat-label">运行中</div>
          </div>
          <div class="stat-trend positive">
            <span>+12%</span>
            <el-icon icon="trending-up" :size="14" />
          </div>
        </el-card>
        
        <el-card class="stat-card stopped-card">
          <div class="stat-icon-wrapper">
            <el-icon icon="square" :size="32" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.stopped }}</div>
            <div class="stat-label">已停止</div>
          </div>
          <div class="stat-trend negative">
            <span>-5%</span>
            <el-icon icon="trending-down" :size="14" />
          </div>
        </el-card>
        
        <el-card class="stat-card unknown-card">
          <div class="stat-icon-wrapper">
            <el-icon icon="help-center" :size="32" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.unknown }}</div>
            <div class="stat-label">未知状态</div>
          </div>
          <div class="stat-trend neutral">
            <span>0%</span>
          </div>
        </el-card>
        
        <el-card class="stat-card total-card">
          <div class="stat-icon-wrapper">
            <el-icon icon="server" :size="32" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">服务总数</div>
          </div>
          <div class="stat-trend positive">
            <span>+8</span>
            <el-icon icon="plus" :size="14" />
          </div>
        </el-card>
      </div>
    </div>
    
    <div class="charts-section">
      <el-card class="chart-card status-chart-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">服务状态分布</span>
            <el-select v-model="timeRange" class="time-select" placeholder="时间范围">
              <el-option label="今日" value="today" />
              <el-option label="本周" value="week" />
              <el-option label="本月" value="month" />
            </el-select>
          </div>
        </template>
        <div class="status-chart">
          <div class="chart-rings">
            <div class="ring-container">
              <svg class="ring-svg" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="40" fill="none" stroke="#e2e8f0" stroke-width="8" />
                <circle 
                  cx="50" cy="50" r="40" fill="none" 
                  stroke="#22c55e" stroke-width="8"
                  :stroke-dasharray="`${runningPercent * 2.51} 251`"
                  stroke-linecap="round"
                  transform="rotate(-90 50 50)"
                  class="ring-progress running-ring"
                />
              </svg>
              <div class="ring-center">
                <div class="ring-value">{{ runningPercent }}%</div>
                <div class="ring-label">运行中</div>
              </div>
            </div>
          </div>
          <div class="chart-legend">
            <div class="legend-item">
              <span class="legend-color running-color"></span>
              <span class="legend-text">运行中: {{ stats.running }}</span>
            </div>
            <div class="legend-item">
              <span class="legend-color stopped-color"></span>
              <span class="legend-text">已停止: {{ stats.stopped }}</span>
            </div>
            <div class="legend-item">
              <span class="legend-color unknown-color"></span>
              <span class="legend-text">未知: {{ stats.unknown }}</span>
            </div>
          </div>
        </div>
      </el-card>
      
      <el-card class="chart-card activity-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">最近操作</span>
            <el-button type="text" class="view-more">查看全部</el-button>
          </div>
        </template>
        <div class="activity-list">
          <div v-for="action in recentActions" :key="action.id" class="activity-item">
            <div class="activity-icon" :class="action.result">
              <el-icon v-if="action.result === 'success'" icon="check-circle" :size="16" />
              <el-icon v-else icon="x-circle" :size="16" />
            </div>
            <div class="activity-content">
              <div class="activity-title">
                <span class="activity-user">{{ action.user }}</span>
                <span class="activity-action">{{ action.type }}</span>
                <span class="activity-target">{{ action.target }}</span>
              </div>
              <div class="activity-time">{{ action.time }}</div>
            </div>
            <el-tag :type="action.result === 'success' ? 'success' : 'danger'" size="small">
              {{ action.result === 'success' ? '成功' : '失败' }}
            </el-tag>
          </div>
          <div v-if="recentActions.length === 0" class="empty-activity">
            <el-icon icon="clock" :size="48" color="#94a3b8" />
            <p>暂无操作记录</p>
          </div>
        </div>
      </el-card>
    </div>
    
    <div class="services-section">
      <el-card class="services-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">服务状态一览</span>
            <div class="header-actions">
              <el-button type="primary" icon="plus">新增服务</el-button>
              <el-button icon="search" class="search-btn">搜索</el-button>
            </div>
          </div>
        </template>
        <div class="services-table-wrapper">
          <el-table 
            :data="services" 
            border
            class="services-table"
            :header-cell-style="{ background: '#f8fafc', fontWeight: '600', color: '#334155' }"
            :row-style="{ transition: 'all 0.2s' }"
            @row-mouse-enter="(row, column, event) => event.currentTarget.style.backgroundColor = '#f8fafc'"
            @row-mouse-leave="(row, column, event) => event.currentTarget.style.backgroundColor = '#ffffff'"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column prop="service_name" label="服务名称" min-width="180">
              <template #default="scope">
                <div class="service-name-cell">
                  <div class="service-status-dot" :class="scope.row.status.toLowerCase()"></div>
                  <el-icon icon="server" :size="18" class="service-icon" />
                  <span class="service-name-text">{{ scope.row.service_name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="service_code" label="服务编码" min-width="120" />
            <el-table-column prop="service_type" label="服务类型" min-width="100">
              <template #default="scope">
                <el-tag type="info" size="small" class="type-tag">{{ scope.row.service_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="environment" label="环境" min-width="80">
              <template #default="scope">
                <el-tag :type="getEnvType(scope.row.environment)" size="small" class="env-tag">
                  {{ getEnvLabel(scope.row.environment) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="ip" label="IP地址" min-width="140">
              <template #default="scope">
                <span class="ip-text">{{ scope.row.ip }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" min-width="100">
              <template #default="scope">
                <div class="status-badge" :class="scope.row.status.toLowerCase()">
                  <span class="status-dot"></span>
                  <span>{{ getStatusLabel(scope.row.status) }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" align="center">
              <template #default="scope">
                <el-button 
                  size="small" 
                  type="primary" 
                  plain 
                  icon="play" 
                  class="action-btn start-btn"
                  @click="startService(scope.row)"
                  :disabled="scope.row.status === 'RUNNING'"
                >启动</el-button>
                <el-button 
                  size="small" 
                  type="danger" 
                  plain 
                  icon="square" 
                  class="action-btn stop-btn"
                  @click="stopService(scope.row)"
                  :disabled="scope.row.status === 'STOPPED'"
                >停止</el-button>
                <el-button 
                  size="small" 
                  type="info" 
                  plain 
                  icon="settings" 
                  class="action-btn config-btn"
                >配置</el-button>
                <el-button 
                  size="small" 
                  type="success" 
                  plain 
                  icon="terminal" 
                  class="action-btn shell-btn" 
                  @click="loginToServer(scope.row)"
                  :disabled="!scope.row.server_id"
                >登录</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div v-if="services.length === 0" class="empty-services">
          <el-icon icon="server" :size="64" color="#cbd5e1" />
          <p>暂无服务数据</p>
          <el-button type="primary" icon="plus">添加服务</el-button>
        </div>
        <div v-else class="table-footer">
          <span class="table-info">共 {{ services.length }} 条记录</span>
          <el-pagination 
            :total="services.length" 
            :page-size="10"
            layout="prev, pager, next"
            class="pagination"
          />
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import axios from '@/utils/axios'

const router = useRouter()
const stats = ref({ running: 0, stopped: 0, unknown: 0, total: 0 })
const services = ref([])
const recentActions = ref([])
const timeRange = ref('today')

const runningPercent = computed(() => {
  if (stats.value.total === 0) return 0
  return Math.round((stats.value.running / stats.value.total) * 100)
})

const stoppedPercent = computed(() => {
  if (stats.value.total === 0) return 0
  return Math.round((stats.value.stopped / stats.value.total) * 100)
})

const unknownPercent = computed(() => {
  if (stats.value.total === 0) return 0
  return Math.round((stats.value.unknown / stats.value.total) * 100)
})

const getEnvType = (env) => {
  switch (env) {
    case 'production': return 'danger'
    case 'test': return 'warning'
    case 'development': return 'success'
    default: return 'info'
  }
}

const getEnvLabel = (env) => {
  switch (env) {
    case 'production': return '生产环境'
    case 'test': return '测试环境'
    case 'development': return '开发环境'
    default: return env
  }
}

const getStatusLabel = (status) => {
  switch (status) {
    case 'RUNNING': return '运行中'
    case 'STOPPED': return '已停止'
    default: return '未知'
  }
}

const loadData = async () => {
  try {
    const [servicesRes, auditRes] = await Promise.all([
            axios.get('/api/monitor/services'),
            axios.get('/api/audit/logs?limit=5')
        ])
    
    services.value = servicesRes.data.data || []
    
    const statusCounts = { running: 0, stopped: 0, unknown: 0 }
    services.value.forEach(svc => {
      if (svc.status === 'RUNNING') statusCounts.running++
      else if (svc.status === 'STOPPED') statusCounts.stopped++
      else statusCounts.unknown++
    })
    stats.value = {
      ...statusCounts,
      total: services.value.length
    }
    
    recentActions.value = (auditRes.data.data || []).map((log, index) => ({
      id: index + 1,
      user: log.username || '未知用户',
      type: log.action || '操作',
      target: log.service_code || log.server_id || '系统',
      result: log.result || 'success',
      time: log.created_at || ''
    }))
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
  }
}

const startService = (service) => {
  ElMessage.success(`正在启动服务: ${service.service_name}`)
}

const stopService = (service) => {
  ElMessage.warning(`正在停止服务: ${service.service_name}`)
}

function loginToServer(service) {
  if (!service.server_id) {
    ElMessage.warning('该服务未绑定服务器')
    return
  }
  router.push({
    path: '/shell',
    query: {
      serviceId: service.id,
      serviceName: service.service_name,
      serverId: service.server_id
    }
  })
}

let refreshTimer = null

onMounted(() => {
  loadData()
  refreshTimer = setInterval(loadData, 10000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.dashboard {
  min-height: 100%;
  padding: 24px;
  background-color: #f1f5f9;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-left {
  h1 {
    font-size: 24px;
    font-weight: 600;
    color: #1e293b;
    margin: 0 0 8px 0;
  }
  
  .subtitle {
    font-size: 14px;
    color: #64748b;
    margin: 0;
  }
}

.header-right {
  .refresh-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: #ffffff;
    border-radius: 8px;
    color: #64748b;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    
    &:hover {
      background: #f1f5f9;
      color: #3b82f6;
    }
  }
}

.stats-section {
  margin-bottom: 24px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.stat-card {
  position: relative;
  padding: 24px;
  border-radius: 16px;
  border: none;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
  overflow: hidden;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
}

.running-card {
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  border-top: 4px solid #22c55e;
}

.stopped-card {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border-top: 4px solid #ef4444;
}

.unknown-card {
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border-top: 4px solid #f59e0b;
}

.total-card {
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  border-top: 4px solid #3b82f6;
}

.stat-icon-wrapper {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.running-card .stat-icon-wrapper {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.stopped-card .stat-icon-wrapper {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.unknown-card .stat-icon-wrapper {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.total-card .stat-icon-wrapper {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.stat-content {
  margin-bottom: 12px;
}

.stat-value {
  font-size: 36px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 4px;
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: #64748b;
}

.stat-trend {
  position: absolute;
  top: 24px;
  right: 24px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.stat-trend.positive {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}

.stat-trend.negative {
  background: rgba(239, 68, 68, 0.15);
  color: #dc2626;
}

.stat-trend.neutral {
  background: rgba(148, 163, 184, 0.15);
  color: #64748b;
}

.charts-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.chart-card {
  border-radius: 16px;
  border: none;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

.time-select {
  width: 120px;
}

.view-more {
  color: #3b82f6;
  font-size: 13px;
  font-weight: 500;
}

.status-chart-card {
  padding: 24px;
}

.status-chart {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 20px 0;
}

.chart-rings {
  flex: 1;
  display: flex;
  justify-content: center;
}

.ring-container {
  position: relative;
  width: 180px;
  height: 180px;
}

.ring-svg {
  width: 100%;
  height: 100%;
}

.running-ring {
  transition: stroke-dasharray 1s ease;
}

.ring-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.ring-value {
  font-size: 32px;
  font-weight: 700;
  color: #1e293b;
}

.ring-label {
  font-size: 13px;
  color: #64748b;
}

.chart-legend {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.legend-color {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.legend-color.running-color {
  background: #22c55e;
}

.legend-color.stopped-color {
  background: #ef4444;
}

.legend-color.unknown-color {
  background: #f59e0b;
}

.legend-text {
  font-size: 14px;
  color: #475569;
  font-weight: 500;
}

.activity-card {
  padding: 24px;
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.activity-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: #f8fafc;
  border-radius: 12px;
  transition: all 0.3s ease;
}

.activity-item:hover {
  background: #f1f5f9;
  transform: translateX(4px);
}

.activity-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.activity-icon.success {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.activity-icon.failed {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.activity-content {
  flex: 1;
  min-width: 0;
}

.activity-title {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 4px;
}

.activity-user {
  font-weight: 600;
  color: #1e293b;
}

.activity-action {
  color: #64748b;
}

.activity-target {
  color: #3b82f6;
}

.activity-time {
  font-size: 12px;
  color: #94a3b8;
}

.empty-activity {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px;
  color: #94a3b8;
  
  p {
    margin: 12px 0 0 0;
  }
}

.services-section {
  margin-top: 24px;
}

.services-card {
  border-radius: 16px;
  border: none;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.search-btn {
  border-color: #e2e8f0;
  color: #64748b;
}

.services-table-wrapper {
  overflow-x: auto;
}

.services-table {
  margin: 16px 0;
  --el-table-border-color: #e2e8f0;
  
  tr {
    height: 60px;
  }
  
  .el-table__cell {
    padding: 12px 16px;
  }
}

.service-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.service-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  
  &.running {
    background: #22c55e;
    animation: pulse-green 2s infinite;
  }
  
  &.stopped {
    background: #ef4444;
  }
  
  &.unknown {
    background: #f59e0b;
  }
}

@keyframes pulse-green {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.6;
    transform: scale(1.2);
  }
}

.service-icon {
  color: #94a3b8;
}

.service-name-text {
  font-weight: 500;
  color: #1e293b;
}

.type-tag, .env-tag {
  font-weight: 500;
}

.ip-text {
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
  color: #475569;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.running {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.status-badge.stopped {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.status-badge.unknown {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-badge.running .status-dot {
  background: #22c55e;
  animation: pulse-green 2s infinite;
}

.status-badge.stopped .status-dot {
  background: #ef4444;
}

.status-badge.unknown .status-dot {
  background: #f59e0b;
}

.action-btn {
  margin: 0 4px;
  transition: all 0.2s;
  
  &:hover:not(:disabled) {
    transform: translateY(-2px);
  }
}

.start-btn {
  &:hover:not(:disabled) {
    background-color: #dcfce7;
  }
}

.stop-btn {
  &:hover:not(:disabled) {
    background-color: #fee2e2;
  }
}

.config-btn {
  &:hover:not(:disabled) {
    background-color: #dbeafe;
  }
}

.shell-btn {
  &:hover:not(:disabled) {
    background-color: #f0fdf4;
  }
  
  &:disabled {
    opacity: 0.5;
  }
}

.empty-services {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px;
  color: #94a3b8;
  
  p {
    margin: 16px 0 24px 0;
    font-size: 16px;
  }
}

.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-top: 1px solid #e2e8f0;
}

.table-info {
  font-size: 14px;
  color: #64748b;
}

.pagination {
  margin: 0;
  --el-pagination-item-bg-color: #f8fafc;
  --el-pagination-item-active-bg-color: #3b82f6;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .charts-section {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .header-actions {
    flex-direction: column;
  }
}
</style>
