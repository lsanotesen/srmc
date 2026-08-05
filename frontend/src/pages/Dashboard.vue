<template>
  <div class="dashboard">
    <!-- 顶部标题栏 -->
    <div class="page-header">
      <div class="header-left">
        <div class="header-title-row">
          <h1>服务管理</h1>
          <div class="live-badge">
            <span class="live-dot"></span>
            <span>实时监控中</span>
          </div>
        </div>
        <p class="subtitle">管理和监控所有服务的运行状态</p>
      </div>
      <div class="header-right">
        <div class="header-stat-mini">
          <div class="mini-item">
            <span class="mini-label">运行率</span>
            <span class="mini-value" :class="{ 'text-success': runningPercent > 80, 'text-warning': runningPercent <= 80 && runningPercent > 50, 'text-danger': runningPercent <= 50 }">{{ runningPercent }}%</span>
          </div>
          <div class="mini-divider"></div>
          <div class="mini-item">
            <span class="mini-label">总服务</span>
            <span class="mini-value">{{ stats.total }}</span>
          </div>
        </div>
        <el-input
          v-model="searchKeyword"
          placeholder="搜索服务名称、IP..."
          prefix-icon="Search"
          clearable
          class="header-search"
          @input="filterServices"
        />
        <div class="refresh-btn" @click="loadData" :class="{ 'refreshing': isRefreshing }">
          <el-icon :size="16"><Refresh /></el-icon>
          <span>刷新</span>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card" v-for="card in statCards" :key="card.key">
        <div class="stat-card-inner">
          <div class="stat-card-left">
            <div class="stat-card-label">{{ card.label }}</div>
            <div class="stat-card-value" :style="{ color: card.color }">{{ card.value }}</div>
            <div class="stat-card-bar">
              <div class="stat-bar-fill" :style="{ width: card.percent + '%', background: card.color }"></div>
            </div>
          </div>
          <div class="stat-card-right">
            <div class="stat-card-icon" :style="{ background: card.bgColor, color: card.color }">
              <el-icon :size="24"><component :is="card.icon" /></el-icon>
            </div>
          </div>
        </div>
        <div class="stat-card-footer">
          <span class="stat-card-trend" :class="card.trendClass">
            <el-icon :size="12"><component :is="card.trendIcon" /></el-icon>
            {{ card.trendText }}
          </span>
          <span class="stat-card-hint">较昨日</span>
        </div>
      </div>
    </div>

    <!-- 中间区域：状态分布 + 最近操作 -->
    <div class="middle-section">
      <div class="status-overview-card">
        <div class="card-header">
          <span class="card-title">服务状态分布</span>
        </div>
        <div class="status-bars">
          <div class="status-bar-row" v-for="item in statusBars" :key="item.label">
            <div class="status-bar-label">
              <span class="status-indicator" :style="{ background: item.color }"></span>
              <span>{{ item.label }}</span>
            </div>
            <div class="status-bar-track">
              <div class="status-bar-fill" :style="{ width: item.percent + '%', background: item.color }">
                <span v-if="item.percent > 15" class="bar-text">{{ item.count }}</span>
              </div>
            </div>
            <span class="status-bar-count">{{ item.count }}<template v-if="stats.total"> / {{ stats.total }}</template></span>
          </div>
        </div>
        <div class="status-ring-wrapper">
          <svg class="status-ring" viewBox="0 0 120 120">
            <circle v-for="(seg, idx) in ringSegments" :key="idx"
              cx="60" cy="60" r="48" fill="none"
              :stroke="seg.color" stroke-width="12"
              :stroke-dasharray="seg.dashArray"
              :stroke-dashoffset="seg.dashOffset"
              stroke-linecap="round"
              transform="rotate(-90 60 60)"
              class="ring-segment"
            />
          </svg>
          <div class="ring-center-text">
            <div class="ring-big">{{ stats.total }}</div>
            <div class="ring-small">服务总数</div>
          </div>
        </div>
      </div>

      <div class="activity-card">
        <div class="card-header">
          <span class="card-title">最近操作</span>
          <span class="view-all-btn">查看全部 →</span>
        </div>
        <div class="activity-timeline">
          <div v-for="action in recentActions" :key="action.id" class="timeline-item">
            <div class="timeline-dot-wrapper">
              <div class="timeline-dot" :class="action.result"></div>
              <div class="timeline-line"></div>
            </div>
            <div class="timeline-content">
              <div class="timeline-header">
                <span class="timeline-user">{{ action.user }}</span>
                <el-tag :type="action.result === 'success' ? 'success' : 'danger'" size="small" effect="light" round>
                  {{ action.result === 'success' ? '成功' : '失败' }}
                </el-tag>
              </div>
              <div class="timeline-desc">
                {{ action.type }} <span class="timeline-target">{{ action.target }}</span>
              </div>
              <div class="timeline-time">{{ action.time }}</div>
            </div>
          </div>
          <div v-if="recentActions.length === 0" class="empty-state">
            <el-icon :size="40" color="#cbd5e1"><Clock /></el-icon>
            <p>暂无操作记录</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 服务列表 -->
    <div class="services-section">
      <div class="services-card">
        <div class="card-header services-header">
          <div class="services-header-left">
            <span class="card-title">服务列表</span>
            <span class="services-count">{{ filteredServices.length }} 项服务</span>
          </div>
          <div class="services-header-right">
            <div class="filter-tabs">
              <span class="filter-tab" :class="{ active: statusFilter === 'all' }" @click="statusFilter = 'all'">全部</span>
              <span class="filter-tab" :class="{ active: statusFilter === 'RUNNING' }" @click="statusFilter = 'RUNNING'">
                <span class="tab-dot running"></span>运行中
              </span>
              <span class="filter-tab" :class="{ active: statusFilter === 'STOPPED' }" @click="statusFilter = 'STOPPED'">
                <span class="tab-dot stopped"></span>已停止
              </span>
            </div>
          </div>
        </div>

        <div class="services-table-wrapper">
          <table class="services-table">
            <thead>
              <tr>
                <th class="th-name">服务名称</th>
                <th class="th-code">编码</th>
                <th class="th-type">类型</th>
                <th class="th-env">环境</th>
                <th class="th-ip">服务器地址</th>
                <th class="th-status">状态</th>
                <th class="th-actions">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="svc in paginatedServices" :key="svc.id" class="service-row">
                <td>
                  <div class="svc-name-cell">
                    <div class="svc-status-dot" :class="svc.status.toLowerCase()"></div>
                    <div class="svc-name-info">
                      <span class="svc-name">{{ svc.service_name }}</span>
                      <span class="svc-code-mobile">{{ svc.service_code }}</span>
                    </div>
                  </div>
                </td>
                <td><span class="code-tag">{{ svc.service_code }}</span></td>
                <td><span class="type-badge">{{ svc.service_type || '-' }}</span></td>
                <td>
                  <span class="env-badge" :class="getEnvClass(svc.environment)">{{ getEnvLabel(svc.environment) }}</span>
                </td>
                <td>
                  <div class="ip-cell">
                    <span class="ip-addr">{{ svc.ip || '-' }}</span>
                  </div>
                </td>
                <td>
                  <div class="status-cell">
                    <span class="status-pill" :class="svc.status.toLowerCase()">
                      <span class="pill-dot"></span>
                      {{ getStatusLabel(svc.status) }}
                    </span>
                  </div>
                </td>
                <td>
                  <div class="actions-cell">
                    <button v-if="hasPermission('service:start')" class="action-btn start" :disabled="svc.status === 'RUNNING'" @click="startService(svc)" title="启动">
                      <el-icon :size="14"><VideoPlay /></el-icon>
                    </button>
                    <button v-if="hasPermission('service:stop')" class="action-btn stop" :disabled="svc.status === 'STOPPED'" @click="stopService(svc)" title="停止">
                      <el-icon :size="14"><VideoPause /></el-icon>
                    </button>
                    <button v-if="hasPermission('service:edit-config')" class="action-btn config" title="配置">
                      <el-icon :size="14"><Setting /></el-icon>
                    </button>
                    <button v-if="hasPermission('webshell:login')" class="action-btn shell" :disabled="!svc.server_id" @click="loginToServer(svc)" title="登录">
                      <el-icon :size="14"><Monitor /></el-icon>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="displayServices.length === 0" class="empty-services">
          <el-icon :size="48" color="#cbd5e1"><Monitor /></el-icon>
          <p>暂无服务数据</p>
          <el-button type="primary" round>
            <el-icon class="el-icon--left"><Plus /></el-icon>添加服务
          </el-button>
        </div>

        <div v-else class="table-footer">
          <span class="footer-info">显示 {{ paginationStart }}-{{ paginationEnd }} 共 {{ displayServices.length }} 条</span>
          <div class="footer-pagination">
            <button class="page-btn" :disabled="currentPage === 1" @click="currentPage--">‹</button>
            <span class="page-indicator">{{ currentPage }} / {{ totalPages }}</span>
            <button class="page-btn" :disabled="currentPage >= totalPages" @click="currentPage++">›</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Refresh, Search, Clock, VideoPlay, VideoPause, Setting, Monitor,
  Plus, CircleCheck, CircleClose, TrendCharts, Odometer
} from '@element-plus/icons-vue'

import axios from '@/utils/axios'
import { usePermission } from '@/composables/usePermission'

const { hasPermission } = usePermission()

const router = useRouter()
const stats = ref({ running: 0, stopped: 0, unknown: 0, total: 0 })
const services = ref([])
const recentActions = ref([])
const searchKeyword = ref('')
const statusFilter = ref('all')
const isRefreshing = ref(false)
const currentPage = ref(1)
const pageSize = 8

const runningPercent = computed(() => {
  if (stats.value.total === 0) return 0
  return Math.round((stats.value.running / stats.value.total) * 100)
})

const filteredServices = computed(() => {
  let result = services.value
  if (statusFilter.value !== 'all') {
    result = result.filter(s => s.status === statusFilter.value)
  }
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase()
    result = result.filter(s =>
      (s.service_name || '').toLowerCase().includes(kw) ||
      (s.ip || '').toLowerCase().includes(kw) ||
      (s.service_code || '').toLowerCase().includes(kw)
    )
  }
  return result
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredServices.value.length / pageSize)))
const paginationStart = computed(() => (currentPage.value - 1) * pageSize + 1)
const paginationEnd = computed(() => Math.min(currentPage.value * pageSize, filteredServices.value.length))
const paginatedServices = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredServices.value.slice(start, start + pageSize)
})

const displayServices = computed(() => filteredServices.value)

const statCards = computed(() => [
  {
    key: 'running', label: '运行中', value: stats.value.running, color: '#10b981',
    bgColor: 'rgba(16,185,129,0.1)', icon: CircleCheck,
    percent: stats.value.total ? (stats.value.running / stats.value.total * 100) : 0,
    trendIcon: TrendCharts, trendText: '+12%', trendClass: 'trend-up'
  },
  {
    key: 'stopped', label: '已停止', value: stats.value.stopped, color: '#ef4444',
    bgColor: 'rgba(239,68,68,0.1)', icon: CircleClose,
    percent: stats.value.total ? (stats.value.stopped / stats.value.total * 100) : 0,
    trendIcon: TrendCharts, trendText: '-5%', trendClass: 'trend-down'
  },
  {
    key: 'unknown', label: '未知状态', value: stats.value.unknown, color: '#f59e0b',
    bgColor: 'rgba(245,158,11,0.1)', icon: Odometer,
    percent: stats.value.total ? (stats.value.unknown / stats.value.total * 100) : 0,
    trendIcon: TrendCharts, trendText: '0%', trendClass: 'trend-neutral'
  },
  {
    key: 'total', label: '服务总数', value: stats.value.total, color: '#3b82f6',
    bgColor: 'rgba(59,130,246,0.1)', icon: Monitor,
    percent: 100,
    trendIcon: TrendCharts, trendText: '+8', trendClass: 'trend-up'
  }
])

const statusBars = computed(() => {
  const total = stats.value.total || 1
  return [
    { label: '运行中', count: stats.value.running, percent: Math.round(stats.value.running / total * 100), color: '#10b981' },
    { label: '已停止', count: stats.value.stopped, percent: Math.round(stats.value.stopped / total * 100), color: '#ef4444' },
    { label: '未知', count: stats.value.unknown, percent: Math.round(stats.value.unknown / total * 100), color: '#f59e0b' }
  ]
})

const ringSegments = computed(() => {
  const total = stats.value.total || 1
  const circumference = 2 * Math.PI * 48
  const segments = []
  let offset = 0

  const items = [
    { count: stats.value.running, color: '#10b981' },
    { count: stats.value.stopped, color: '#ef4444' },
    { count: stats.value.unknown, color: '#f59e0b' }
  ]

  for (const item of items) {
    if (item.count === 0) continue
    const len = (item.count / total) * circumference
    const gap = 4
    segments.push({
      color: item.color,
      dashArray: `${Math.max(0, len - gap)} ${circumference}`,
      dashOffset: -offset
    })
    offset += len
  }
  return segments
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
    case 'production': return '生产'
    case 'test': return '测试'
    case 'development': return '开发'
    default: return env || '-'
  }
}

const getEnvClass = (env) => {
  switch (env) {
    case 'production': return 'env-prod'
    case 'test': return 'env-test'
    case 'development': return 'env-dev'
    default: return 'env-default'
  }
}

const getStatusLabel = (status) => {
  switch (status) {
    case 'RUNNING': return '运行中'
    case 'STOPPED': return '已停止'
    default: return '未知'
  }
}

const filterServices = () => {
  currentPage.value = 1
}

const loadData = async () => {
  isRefreshing.value = true
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
    stats.value = { ...statusCounts, total: services.value.length }

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
  } finally {
    setTimeout(() => { isRefreshing.value = false }, 500)
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
    query: { serviceId: service.id, serviceName: service.service_name, serverId: service.server_id }
  })
}

let refreshTimer = null

onMounted(() => {
  loadData()
  refreshTimer = setInterval(loadData, 10000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.dashboard {
  min-height: 100%;
  padding: 28px 32px;
  background-color: #f0f2f5;
}

/* ===== Page Header ===== */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title-row h1 {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
  letter-spacing: -0.3px;
}

.live-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 20px;
  font-size: 12px;
  color: #10b981;
  font-weight: 500;
}

.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  animation: live-pulse 2s ease-in-out infinite;
}

@keyframes live-pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16,185,129,0.4); }
  50% { opacity: 0.7; box-shadow: 0 0 0 4px rgba(16,185,129,0); }
}

.subtitle {
  font-size: 13px;
  color: #64748b;
  margin: 6px 0 0 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-stat-mini {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.mini-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.mini-label {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.mini-value {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
}

.text-success { color: #10b981; }
.text-warning { color: #f59e0b; }
.text-danger { color: #ef4444; }

.mini-divider {
  width: 1px;
  height: 28px;
  background: #e2e8f0;
}

.header-search {
  width: 220px;
}

.header-search :deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: none;
  border: 1px solid #e2e8f0;
  background: #fff;
}

.header-search :deep(.el-input__wrapper:hover),
.header-search :deep(.el-input__wrapper.is-focus) {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,0.1);
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
}

.refresh-btn:hover {
  background: #f8fafc;
  border-color: #3b82f6;
  color: #3b82f6;
}

.refreshing {
  animation: spin-icon 0.5s linear;
}

@keyframes spin-icon {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ===== Stats Grid ===== */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #e2e8f0;
  transition: all 0.25s ease;
}

.stat-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
  transform: translateY(-2px);
}

.stat-card-inner {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
}

.stat-card-label {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
  margin-bottom: 6px;
}

.stat-card-value {
  font-size: 32px;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 10px;
  letter-spacing: -1px;
}

.stat-card-bar {
  height: 4px;
  background: #f1f5f9;
  border-radius: 2px;
  overflow: hidden;
  width: 100%;
}

.stat-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.8s ease;
}

.stat-card-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-card-footer {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.stat-card-trend {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}

.trend-up { color: #10b981; background: rgba(16,185,129,0.08); }
.trend-down { color: #ef4444; background: rgba(239,68,68,0.08); }
.trend-neutral { color: #64748b; background: rgba(100,116,139,0.08); }

.stat-card-hint {
  font-size: 12px;
  color: #94a3b8;
}

/* ===== Middle Section ===== */
.middle-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.status-overview-card,
.activity-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  border: 1px solid #e2e8f0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.view-all-btn {
  font-size: 13px;
  color: #3b82f6;
  cursor: pointer;
  font-weight: 500;
  transition: color 0.2s;
}

.view-all-btn:hover {
  color: #2563eb;
}

/* Status Bars */
.status-bars {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 24px;
}

.status-bar-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-bar-label {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 70px;
  font-size: 13px;
  color: #475569;
  font-weight: 500;
  flex-shrink: 0;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-bar-track {
  flex: 1;
  height: 24px;
  background: #f1f5f9;
  border-radius: 6px;
  overflow: hidden;
}

.status-bar-fill {
  height: 100%;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: width 0.8s ease;
  min-width: 0;
}

.bar-text {
  font-size: 11px;
  font-weight: 700;
  color: #fff;
}

.status-bar-count {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
  width: 50px;
  text-align: right;
  flex-shrink: 0;
}

/* Status Ring */
.status-ring-wrapper {
  position: relative;
  width: 120px;
  height: 120px;
  margin: 0 auto;
}

.status-ring {
  width: 100%;
  height: 100%;
}

.ring-segment {
  transition: stroke-dasharray 0.8s ease;
}

.ring-center-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.ring-big {
  font-size: 28px;
  font-weight: 800;
  color: #1e293b;
  line-height: 1;
}

.ring-small {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}

/* Activity Timeline */
.activity-timeline {
  display: flex;
  flex-direction: column;
}

.timeline-item {
  display: flex;
  gap: 12px;
  position: relative;
}

.timeline-dot-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 20px;
}

.timeline-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid #10b981;
  background: #fff;
  margin-top: 4px;
  flex-shrink: 0;
  z-index: 1;
}

.timeline-dot.success { border-color: #10b981; }
.timeline-dot.failed { border-color: #ef4444; }

.timeline-line {
  width: 2px;
  flex: 1;
  background: #e2e8f0;
  margin-top: 4px;
}

.timeline-item:last-child .timeline-line {
  display: none;
}

.timeline-content {
  flex: 1;
  padding-bottom: 16px;
  min-width: 0;
}

.timeline-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.timeline-user {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.timeline-desc {
  font-size: 13px;
  color: #64748b;
  margin: 4px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.timeline-target {
  color: #3b82f6;
  font-weight: 500;
}

.timeline-time {
  font-size: 12px;
  color: #94a3b8;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px;
  color: #94a3b8;
}

.empty-state p {
  margin: 12px 0 0;
  font-size: 14px;
}

/* ===== Services Section ===== */
.services-section {
  margin-top: 0;
}

.services-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.services-header {
  padding: 18px 24px;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 0;
}

.services-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.services-count {
  font-size: 13px;
  color: #94a3b8;
  font-weight: 400;
}

.services-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-tabs {
  display: flex;
  gap: 4px;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 3px;
}

.filter-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
  user-select: none;
}

.filter-tab:hover {
  color: #475569;
}

.filter-tab.active {
  background: #fff;
  color: #1e293b;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.tab-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.tab-dot.running { background: #10b981; }
.tab-dot.stopped { background: #ef4444; }

/* Table */
.services-table-wrapper {
  overflow-x: auto;
}

.services-table {
  width: 100%;
  border-collapse: collapse;
}

.services-table thead th {
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  text-align: left;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}

.services-table tbody td {
  padding: 14px 16px;
  font-size: 13px;
  color: #475569;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
}

.service-row {
  transition: background 0.15s;
}

.service-row:hover {
  background: #f8fafc;
}

.svc-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.svc-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.svc-status-dot.running {
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16,185,129,0.15);
  animation: dot-pulse 2s infinite;
}

.svc-status-dot.stopped { background: #ef4444; }
.svc-status-dot.unknown { background: #f59e0b; }

@keyframes dot-pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(16,185,129,0.15); }
  50% { box-shadow: 0 0 0 6px rgba(16,185,129,0); }
}

.svc-name {
  font-weight: 600;
  color: #1e293b;
  font-size: 14px;
}

.svc-code-mobile {
  display: none;
  font-size: 12px;
  color: #94a3b8;
}

.code-tag {
  font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  padding: 3px 8px;
  border-radius: 4px;
}

.type-badge {
  font-size: 12px;
  color: #64748b;
}

.env-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.env-prod { background: #fef2f2; color: #dc2626; }
.env-test { background: #fffbeb; color: #d97706; }
.env-dev { background: #f0fdf4; color: #16a34a; }
.env-default { background: #f1f5f9; color: #64748b; }

.ip-addr {
  font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
  font-size: 13px;
  color: #475569;
}

/* Status Pill */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.status-pill.running {
  background: rgba(16,185,129,0.08);
  color: #10b981;
}

.status-pill.stopped {
  background: rgba(239,68,68,0.08);
  color: #ef4444;
}

.status-pill.unknown {
  background: rgba(245,158,11,0.08);
  color: #f59e0b;
}

.pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.status-pill.running .pill-dot {
  animation: pill-pulse 2s infinite;
}

@keyframes pill-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* Action Buttons */
.actions-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  color: #64748b;
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}

.action-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.action-btn.start { color: #10b981; }
.action-btn.start:hover:not(:disabled) { background: #f0fdf4; border-color: #10b981; }

.action-btn.stop { color: #ef4444; }
.action-btn.stop:hover:not(:disabled) { background: #fef2f2; border-color: #ef4444; }

.action-btn.config { color: #3b82f6; }
.action-btn.config:hover:not(:disabled) { background: #eff6ff; border-color: #3b82f6; }

.action-btn.shell { color: #8b5cf6; }
.action-btn.shell:hover:not(:disabled) { background: #f5f3ff; border-color: #8b5cf6; }

/* Empty */
.empty-services {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 20px;
  color: #94a3b8;
}

.empty-services p {
  margin: 16px 0 24px;
  font-size: 15px;
}

/* Footer */
.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 24px;
  border-top: 1px solid #e2e8f0;
  background: #fafbfc;
}

.footer-info {
  font-size: 13px;
  color: #94a3b8;
}

.footer-pagination {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 16px;
  color: #475569;
  transition: all 0.2s;
}

.page-btn:hover:not(:disabled) {
  background: #f1f5f9;
  border-color: #3b82f6;
  color: #3b82f6;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-indicator {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
  padding: 0 4px;
}

/* ===== Responsive ===== */
@media (max-width: 1400px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 1200px) {
  .middle-section { grid-template-columns: 1fr; }
  .header-stat-mini { display: none; }
}

@media (max-width: 768px) {
  .dashboard { padding: 16px; }
  .stats-grid { grid-template-columns: 1fr; }
  .page-header { flex-direction: column; gap: 16px; }
  .header-right { flex-wrap: wrap; }
}
</style>
