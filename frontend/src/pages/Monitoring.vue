<template>
  <div class="monitoring-page" v-loading="loading" element-loading-text="加载监控数据...">
    <!-- ===== 顶部导航栏 ===== -->
    <div class="page-header">
      <div class="header-left">
        <div class="header-title-row">
          <h1>监控中心</h1>
          <div class="live-badge" v-if="autoRefresh">
            <span class="live-dot"></span>
            <span>LIVE</span>
          </div>
        </div>
        <p class="subtitle">实时监控所有服务的运行状态、资源使用和告警信息</p>
      </div>
      <div class="header-right">
        <div class="time-range-selector">
          <span v-for="r in timeRanges" :key="r.value"
            class="time-opt" :class="{ active: timeRange === r.value }"
            @click="timeRange = r.value">{{ r.label }}</span>
        </div>
        <div class="auto-refresh-toggle" @click="autoRefresh = !autoRefresh">
          <span class="toggle-dot" :class="{ on: autoRefresh }"></span>
          <span>自动刷新</span>
        </div>
        <div class="refresh-btn" @click="refreshAll" :class="{ spinning: isRefreshing }">
          <el-icon :size="15"><Refresh /></el-icon>
        </div>
      </div>
    </div>

    <!-- ===== KPI 指标卡片 ===== -->
    <div class="kpi-grid">
      <div class="kpi-card" v-for="kpi in kpiCards" :key="kpi.key" @click="kpi.action && kpi.action()">
        <div class="kpi-icon-wrap" :style="{ background: kpi.bg, color: kpi.color }">
          <el-icon :size="22"><component :is="kpi.icon" /></el-icon>
        </div>
        <div class="kpi-body">
          <div class="kpi-label">{{ kpi.label }}</div>
          <div class="kpi-value" :style="{ color: kpi.color }">{{ kpi.display }}</div>
        </div>
        <div class="kpi-footer">
          <span class="kpi-sub" v-if="kpi.sub">{{ kpi.sub }}</span>
          <span class="kpi-badge" v-if="kpi.badge" :class="kpi.badgeClass">{{ kpi.badge }}</span>
        </div>
      </div>
    </div>

    <!-- ===== Tab 切换 ===== -->
    <div class="tab-bar">
      <button class="tab-btn" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">
        <el-icon :size="16"><Monitor /></el-icon>
        <span>全局概览</span>
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'servers' }" @click="activeTab = 'servers'">
        <el-icon :size="16"><Platform /></el-icon>
        <span>服务器监控</span>
      </button>
    </div>

    <!-- ===== 全局概览 Tab ===== -->
    <div v-if="activeTab === 'overview'" class="tab-content">

    <!-- ===== 中间区域：服务状态图 + 告警面板 ===== -->
    <div class="mid-section">
      <!-- 左：服务状态概览 -->
      <div class="panel">
        <div class="panel-head">
          <span class="panel-title">服务状态概览</span>
          <span class="panel-total">共 {{ overview.total || 0 }} 个服务</span>
        </div>
        <div class="status-overview">
          <!-- SVG 环形图 -->
          <div class="ring-wrap">
            <svg class="ring-svg" viewBox="0 0 140 140">
              <circle v-for="(seg, i) in ringSegs" :key="i"
                cx="70" cy="70" r="54" fill="none"
                :stroke="seg.color" stroke-width="14"
                :stroke-dasharray="seg.dashArray"
                :stroke-dashoffset="seg.dashOffset"
                stroke-linecap="round"
                transform="rotate(-90 70 70)"
                class="ring-seg" />
            </svg>
            <div class="ring-center">
              <div class="ring-num">{{ overview.health_rate || 0 }}<small>%</small></div>
              <div class="ring-label">健康率</div>
            </div>
          </div>
          <!-- 状态条形图 -->
          <div class="status-bars">
            <div class="sbar-row" v-for="b in statusBars" :key="b.label">
              <div class="sbar-label">
                <span class="sbar-dot" :style="{ background: b.color }"></span>
                <span>{{ b.label }}</span>
              </div>
              <div class="sbar-track">
                <div class="sbar-fill" :style="{ width: b.pct + '%', background: b.color }"></div>
              </div>
              <span class="sbar-num">{{ b.count }}</span>
            </div>
          </div>
          <!-- 资源仪表盘 -->
          <div class="gauges-row">
            <div class="gauge-item">
              <div ref="cpuGaugeRef" class="gauge-chart"></div>
              <div class="gauge-label">CPU 平均使用率</div>
            </div>
            <div class="gauge-item">
              <div ref="memGaugeRef" class="gauge-chart"></div>
              <div class="gauge-label">内存平均使用</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右：告警面板 -->
      <div class="panel alert-panel">
        <div class="panel-head">
          <span class="panel-title">
            实时告警
            <span class="alert-count-badge" v-if="overview.active_alerts">{{ overview.active_alerts }}</span>
          </span>
          <div class="alert-filter-tabs">
            <span v-for="f in alertFilters" :key="f.value"
              class="af-tab" :class="{ active: alertFilter === f.value }"
              @click="alertFilter = f.value">{{ f.label }}</span>
          </div>
        </div>
        <div class="alert-list">
          <div v-for="(a, i) in filteredAlerts" :key="i" class="alert-row" :class="a.severity">
            <div class="alert-sev-bar"></div>
            <div class="alert-body">
              <div class="alert-top">
                <span class="alert-name">{{ a.alertname }}</span>
                <span class="alert-sev-tag" :class="a.severity">{{ a.severity }}</span>
                <span class="alert-time">{{ formatRelativeTime(a.startsAt) }}</span>
              </div>
              <div class="alert-msg">{{ a.summary || a.alertname }}</div>
              <div class="alert-inst" v-if="a.instance">{{ a.instance }}</div>
            </div>
          </div>
          <div v-if="filteredAlerts.length === 0" class="alert-empty">
            <el-icon :size="36" color="#d1d5db"><Bell /></el-icon>
            <p>{{ alerts.length ? '没有匹配的告警' : '暂无活跃告警' }}</p>
          </div>
        </div>
      </div>
    </div>
    </div>

    <!-- ===== 服务器监控 Tab ===== -->
    <div v-if="activeTab === 'servers'" class="tab-content">
      <!-- 服务器列表网格 -->
      <div class="server-grid" v-loading="loadingServers">
        <div v-if="!serverList.length" class="empty-state">
          <el-icon :size="48" color="#d1d5db"><Platform /></el-icon>
          <p>暂无服务器数据，请先在"服务器管理"中添加服务器</p>
        </div>
        <div v-else class="server-cards">
          <div v-for="srv in serverList" :key="srv.id" 
            class="server-card" 
            :class="{ selected: selectedServer?.id === srv.id }"
            @click="selectServer(srv)">
            <div class="sc-header">
              <div class="sc-info">
                <h3>{{ srv.hostname }}</h3>
                <span class="sc-ip">{{ srv.ip }}</span>
              </div>
              <span class="sc-status" :class="srv.cpu_percent > 80 ? 'danger' : srv.cpu_percent > 50 ? 'warning' : 'ok'">
                {{ srv.cpu_percent > 80 ? '高负载' : srv.cpu_percent > 50 ? '中负载' : '正常' }}
              </span>
            </div>
            <div class="sc-metrics">
              <div class="sc-metric">
                <span class="sc-m-label">CPU</span>
                <span class="sc-m-val" :class="cpuCls(srv.cpu_percent)">{{ srv.cpu_percent.toFixed(1) }}%</span>
                <div class="sc-bar"><div class="sc-bar-fill cpu" :style="{ width: Math.min(100, srv.cpu_percent) + '%' }"></div></div>
              </div>
              <div class="sc-metric">
                <span class="sc-m-label">内存</span>
                <span class="sc-m-val" :class="memCls(srv.memory_percent * 10)">{{ srv.memory_percent.toFixed(1) }}%</span>
                <div class="sc-bar"><div class="sc-bar-fill mem" :style="{ width: Math.min(100, srv.memory_percent) + '%' }"></div></div>
              </div>
              <div class="sc-metric">
                <span class="sc-m-label">网络</span>
                <span class="sc-m-val net">↓{{ srv.network_rx_mb.toFixed(2) }} ↑{{ srv.network_tx_mb.toFixed(2) }} MB/s</span>
              </div>
              <div class="sc-metric">
                <span class="sc-m-label">磁盘</span>
                <span class="sc-m-val disk">{{ srv.disk_usage_percent.toFixed(1) }}%</span>
                <div class="sc-bar"><div class="sc-bar-fill disk" :style="{ width: Math.min(100, srv.disk_usage_percent) + '%' }"></div></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 选中服务器的详细监控 -->
      <div v-if="selectedServer" class="server-detail" v-loading="loadingMetrics">
        <div class="sd-header">
          <div class="sd-title">
            <h2>{{ selectedServer.hostname }} - 详细监控</h2>
            <span class="sd-ip">{{ selectedServer.ip }}</span>
          </div>
          <div class="sd-actions">
            <button class="back-btn" @click="selectedServer = null">
              <el-icon :size="14"><ArrowLeft /></el-icon>
              <span>返回</span>
            </button>
          </div>
        </div>

        <!-- 资源趋势图表 -->
        <div class="sd-charts">
          <div class="chart-panel">
            <div class="chart-head">
              <span class="chart-title">CPU 使用率</span>
              <span class="chart-unit">%</span>
            </div>
            <div ref="cpuChartRef" class="chart-container"></div>
          </div>
          <div class="chart-panel">
            <div class="chart-head">
              <span class="chart-title">内存使用率</span>
              <span class="chart-unit">%</span>
            </div>
            <div ref="memoryChartRef" class="chart-container"></div>
          </div>
          <div class="chart-panel">
            <div class="chart-head">
              <span class="chart-title">网络流量</span>
              <span class="chart-unit">MB/s</span>
            </div>
            <div ref="networkChartRef" class="chart-container"></div>
          </div>
          <div class="chart-panel">
            <div class="chart-head">
              <span class="chart-title">磁盘使用率</span>
              <span class="chart-unit">%</span>
            </div>
            <div ref="diskChartRef" class="chart-container"></div>
          </div>
        </div>

        <!-- 该服务器上的服务列表 -->
        <div class="sd-services">
          <div class="panel-head">
            <span class="panel-title">服务器上的服务 ({{ serverServices.length }})</span>
          </div>
          <table class="data-tbl">
            <thead>
              <tr>
                <th>服务名称</th>
                <th>端口</th>
                <th>检查类型</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="svc in serverServices" :key="svc.service_id">
                <td>{{ svc.service_name }}</td>
                <td>{{ svc.port || '-' }}</td>
                <td>{{ svc.check_type }}</td>
                <td>
                  <span class="st-pill" :class="(svc.status||'unknown').toLowerCase()">
                    <span class="st-dot"></span>{{ statusLabel(svc.status) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ===== 服务详情列表 (仅在全局概览显示) ===== -->
    <div v-if="activeTab === 'overview'" class="svc-panel">
      <div class="panel-head svc-head">
        <div class="svc-head-left">
          <span class="panel-title">服务监控详情</span>
          <span class="svc-cnt">{{ filteredServices.length }} 项</span>
        </div>
        <div class="svc-head-right">
          <div class="filter-tabs">
            <span v-for="f in svcFilters" :key="f.value"
              class="ft-tab" :class="{ active: svcFilter === f.value }"
              @click="svcFilter = f.value">
              <span class="ft-dot" v-if="f.dot" :style="{ background: f.dot }"></span>
              {{ f.label }}
            </span>
          </div>
          <div class="sort-select">
            <select v-model="sortBy">
              <option value="name">按名称</option>
              <option value="status">按状态</option>
              <option value="cpu">按 CPU</option>
              <option value="memory">按内存</option>
            </select>
          </div>
        </div>
      </div>

      <div class="tbl-wrap">
        <table class="data-tbl">
          <thead>
            <tr>
              <th>服务</th>
              <th>地址</th>
              <th>状态</th>
              <th>CPU</th>
              <th>内存</th>
              <th>运行时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in pagedServices" :key="s.service_id || s.id" class="svc-tr">
              <td>
                <div class="name-cell">
                  <span class="status-dot" :class="(s.status||'unknown').toLowerCase()"></span>
                  <div>
                    <div class="svc-name">{{ s.name || s.service_name || s.func_desc || '-' }}</div>
                    <div class="svc-sub">{{ s.deploy_type || 'HOST' }}</div>
                  </div>
                </div>
              </td>
              <td>
                <span class="addr-text">{{ s.ip }}<template v-if="s.port">:{{ s.port }}</template></span>
              </td>
              <td>
                <span class="st-pill" :class="(s.status||'unknown').toLowerCase()">
                  <span class="st-dot"></span>{{ statusLabel(s.status) }}
                </span>
              </td>
              <td>
                <div class="bar-cell">
                  <div class="mini-bar"><div class="mini-fill cpu" :style="{ width: cpuBarW(s.cpu_percent) }"></div></div>
                  <span class="bar-val" :class="cpuCls(s.cpu_percent)">{{ fmtCpu(s.cpu_percent) }}</span>
                </div>
              </td>
              <td>
                <div class="bar-cell">
                  <div class="mini-bar"><div class="mini-fill mem" :style="{ width: memBarW(s.memory_mb) }"></div></div>
                  <span class="bar-val" :class="memCls(s.memory_mb)">{{ fmtMem(s.memory_mb) }}</span>
                </div>
              </td>
              <td><span class="uptime">{{ fmtUptime(s.uptime_seconds) }}</span></td>
              <td>
                <div class="act-cell">
                  <button class="act-btn start" :disabled="s.status==='RUNNING'" @click="ctrlService(s,'start')" title="启动">
                    <el-icon :size="13"><VideoPlay /></el-icon>
                  </button>
                  <button class="act-btn stop" :disabled="s.status==='STOPPED'" @click="ctrlService(s,'stop')" title="停止">
                    <el-icon :size="13"><VideoPause /></el-icon>
                  </button>
                  <button class="act-btn restart" @click="ctrlService(s,'restart')" title="重启">
                    <el-icon :size="13"><Refresh /></el-icon>
                  </button>
                  <button class="act-btn detail" @click="showDetail(s)" title="详情">
                    <el-icon :size="13"><View /></el-icon>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!services.length && !metrics.length" class="tbl-empty">
          <el-icon :size="44" color="#d1d5db"><Monitor /></el-icon>
          <p>暂无服务数据</p>
        </div>
      </div>

      <div v-if="filteredServices.length > pageSize" class="tbl-foot">
        <span class="foot-info">显示 {{ pgStart }}-{{ pgEnd }} / 共 {{ filteredServices.length }} 条</span>
        <div class="foot-pager">
          <button class="pg-btn" :disabled="page===1" @click="page--">‹</button>
          <span class="pg-ind">{{ page }} / {{ totalPg }}</span>
          <button class="pg-btn" :disabled="page>=totalPg" @click="page++">›</button>
        </div>
      </div>
    </div>

    <!-- ===== 详情弹窗 ===== -->
    <el-dialog v-model="dlgVisible" title="服务监控详情" width="680px" destroy-on-close>
      <div v-if="cur" class="dlg">
        <div class="dlg-head">
          <div class="dlg-title-row">
            <h3>{{ cur.name || cur.service_name || '-' }}</h3>
            <span class="st-pill" :class="(cur.status||'unknown').toLowerCase()">
              <span class="st-dot"></span>{{ statusLabel(cur.status) }}
            </span>
          </div>
          <p class="dlg-sub">{{ cur.ip }}<template v-if="cur.port">:{{ cur.port }}</template></p>
        </div>
        <div class="dlg-grid">
          <div class="dlg-card">
            <div class="dlg-card-label">CPU 使用率</div>
            <div class="dlg-card-val" :class="cpuCls(cur.cpu_percent)">{{ fmtCpu(cur.cpu_percent) }}</div>
            <div class="dlg-card-bar"><div class="dlg-bar-fill cpu" :style="{ width: cpuBarW(cur.cpu_percent) }"></div></div>
          </div>
          <div class="dlg-card">
            <div class="dlg-card-label">内存使用</div>
            <div class="dlg-card-val" :class="memCls(cur.memory_mb)">{{ fmtMem(cur.memory_mb) }}</div>
            <div class="dlg-card-bar"><div class="dlg-bar-fill mem" :style="{ width: memBarW(cur.memory_mb) }"></div></div>
          </div>
          <div class="dlg-card">
            <div class="dlg-card-label">运行时间</div>
            <div class="dlg-card-val">{{ fmtUptime(cur.uptime_seconds) }}</div>
          </div>
          <div class="dlg-card">
            <div class="dlg-card-label">部署方式</div>
            <div class="dlg-card-val">{{ cur.deploy_type || 'HOST' }}</div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import {
  Refresh, Monitor, VideoPlay, VideoPause, View,
  Cpu, Odometer, Warning, CircleCheck, Platform, ArrowLeft, Bell
} from '@element-plus/icons-vue'

// ===== 状态 =====
const loading = ref(true)
const isRefreshing = ref(false)
const autoRefresh = ref(true)
const timeRange = ref('1h')
const overview = ref({})
const services = ref([])   // from /api/monitor/status
const metrics = ref([])    // from /api/metrics/services
const alerts = ref([])
const alertFilter = ref('all')
const svcFilter = ref('')
const sortBy = ref('name')
const page = ref(1)
const pageSize = 10
const dlgVisible = ref(false)
const cur = ref(null)

// Tab & Server states
const activeTab = ref('overview')
const loadingServers = ref(false)
const serverList = ref([])     // from /api/monitor/servers
const selectedServer = ref(null)
const loadingMetrics = ref(false)
const serverServices = ref([]) // from /api/monitor/server/{id}/services

// Chart refs for server detail
const cpuChartRef = ref(null)
const memoryChartRef = ref(null)
const networkChartRef = ref(null)
const diskChartRef = ref(null)
let cpuChart = null
let memoryChart = null
let networkChart = null
let diskChart = null

// Chart refs
const cpuGaugeRef = ref(null)
const memGaugeRef = ref(null)
let cpuGauge = null
let memGauge = null
let timer = null

const timeRanges = [
  { label: '1h', value: '1h' },
  { label: '6h', value: '6h' },
  { label: '24h', value: '24h' },
  { label: '7d', value: '7d' }
]

// ===== 计算属性 =====
const kpiCards = computed(() => {
  const o = overview.value
  const hr = o.health_rate ?? 100
  return [
    {
      key: 'health', label: '服务健康率', display: hr + '%',
      color: hr >= 90 ? '#10b981' : hr >= 70 ? '#f59e0b' : '#ef4444',
      bg: hr >= 90 ? 'rgba(16,185,129,.1)' : hr >= 70 ? 'rgba(245,158,11,.1)' : 'rgba(239,68,68,.1)',
      icon: CircleCheck,
      sub: `${o.running || 0}/${o.total || 0} 运行中`,
      badge: hr >= 90 ? '正常' : '异常', badgeClass: hr >= 90 ? 'badge-ok' : 'badge-warn'
    },
    {
      key: 'alerts', label: '活跃告警', display: o.active_alerts ?? 0,
      color: (o.active_alerts||0) > 5 ? '#ef4444' : (o.active_alerts||0) > 0 ? '#f59e0b' : '#10b981',
      bg: (o.active_alerts||0) > 5 ? 'rgba(239,68,68,.1)' : (o.active_alerts||0) > 0 ? 'rgba(245,158,11,.1)' : 'rgba(16,185,129,.1)',
      icon: Warning,
      sub: `Critical: ${o.alert_critical||0}  Warning: ${o.alert_warning||0}`,
      badge: null
    },
    {
      key: 'cpu', label: '平均 CPU', display: (o.avg_cpu||0).toFixed(1) + '%',
      color: (o.avg_cpu||0) > 80 ? '#ef4444' : (o.avg_cpu||0) > 50 ? '#f59e0b' : '#3b82f6',
      bg: (o.avg_cpu||0) > 80 ? 'rgba(239,68,68,.1)' : (o.avg_cpu||0) > 50 ? 'rgba(245,158,11,.1)' : 'rgba(59,130,246,.1)',
      icon: Cpu,
      sub: (o.avg_cpu||0) > 80 ? '负载偏高' : '负载正常',
      badge: null
    },
    {
      key: 'mem', label: '平均内存', display: (o.avg_memory||0).toFixed(0) + ' MB',
      color: (o.avg_memory||0) > 1024 ? '#ef4444' : (o.avg_memory||0) > 512 ? '#f59e0b' : '#8b5cf6',
      bg: (o.avg_memory||0) > 1024 ? 'rgba(239,68,68,.1)' : (o.avg_memory||0) > 512 ? 'rgba(245,158,11,.1)' : 'rgba(139,92,246,.1)',
      icon: Odometer,
      sub: (o.avg_memory||0) > 1024 ? '内存紧张' : '内存充足',
      badge: null
    }
  ]
})

const ringSegs = computed(() => {
  const o = overview.value
  const total = o.total || 1
  const circ = 2 * Math.PI * 54
  const segs = []
  let off = 0
  const items = [
    { count: o.running || 0, color: '#10b981' },
    { count: o.stopped || 0, color: '#ef4444' },
    { count: o.unknown || 0, color: '#f59e0b' }
  ]
  for (const it of items) {
    if (!it.count) continue
    const len = (it.count / total) * circ
    segs.push({ color: it.color, dashArray: `${Math.max(0, len - 4)} ${circ}`, dashOffset: -off })
    off += len
  }
  return segs
})

const statusBars = computed(() => {
  const o = overview.value
  const t = o.total || 1
  return [
    { label: '运行中', count: o.running || 0, pct: Math.round((o.running||0)/t*100), color: '#10b981' },
    { label: '已停止', count: o.stopped || 0, pct: Math.round((o.stopped||0)/t*100), color: '#ef4444' },
    { label: '未知', count: o.unknown || 0, pct: Math.round((o.unknown||0)/t*100), color: '#f59e0b' }
  ]
})

const alertFilters = [
  { label: '全部', value: 'all' },
  { label: 'Critical', value: 'critical' },
  { label: 'Warning', value: 'warning' }
]

const filteredAlerts = computed(() => {
  if (alertFilter.value === 'all') return alerts.value.slice(0, 10)
  return alerts.value.filter(a => a.severity === alertFilter.value).slice(0, 10)
})

const svcFilters = computed(() => [
  { label: '全部', value: '', dot: null },
  { label: '运行中', value: 'RUNNING', dot: '#10b981' },
  { label: '已停止', value: 'STOPPED', dot: '#ef4444' },
  { label: '异常', value: 'UNKNOWN', dot: '#f59e0b' }
])

// Merge services (status) + metrics (CPU/mem)
const mergedServices = computed(() => {
  const mMap = {}
  metrics.value.forEach(m => { mMap[m.service_id] = m })
  return services.value.map(s => {
    const m = mMap[s.service_id] || {}
    return {
      ...s,
      name: s.service_name || s.service_code || m.name || '-',
      cpu_percent: m.cpu_percent || 0,
      memory_mb: m.memory_mb || 0,
      uptime_seconds: m.uptime_seconds || 0,
      deploy_type: m.deploy_type || 'HOST'
    }
  })
})

const filteredServices = computed(() => {
  let r = mergedServices.value
  if (svcFilter.value) r = r.filter(s => s.status === svcFilter.value)
  // sort
  if (sortBy.value === 'cpu') r = [...r].sort((a, b) => (b.cpu_percent||0) - (a.cpu_percent||0))
  else if (sortBy.value === 'memory') r = [...r].sort((a, b) => (b.memory_mb||0) - (a.memory_mb||0))
  else if (sortBy.value === 'status') r = [...r].sort((a, b) => {
    const order = { RUNNING: 0, STOPPED: 1, UNKNOWN: 2 }
    return (order[a.status]||2) - (order[b.status]||2)
  })
  return r
})

const totalPg = computed(() => Math.max(1, Math.ceil(filteredServices.value.length / pageSize)))
const pgStart = computed(() => (page.value - 1) * pageSize + 1)
const pgEnd = computed(() => Math.min(page.value * pageSize, filteredServices.value.length))
const pagedServices = computed(() => {
  const s = (page.value - 1) * pageSize
  return filteredServices.value.slice(s, s + pageSize)
})

// ===== 方法 =====
const statusLabel = (st) => ({ RUNNING: '运行中', STOPPED: '已停止', ERROR: '异常', UNKNOWN: '未知' }[st] || st || '未知')
const fmtCpu = (v) => v != null ? v.toFixed(1) + '%' : '-'
const fmtMem = (v) => v != null ? (v >= 1024 ? (v/1024).toFixed(1)+'GB' : v.toFixed(0)+'MB') : '-'
const fmtUptime = (s) => {
  if (!s) return '-'
  const d = Math.floor(s/86400), h = Math.floor((s%86400)/3600), m = Math.floor((s%3600)/60)
  return d > 0 ? `${d}天${h}时` : h > 0 ? `${h}时${m}分` : `${m}分`
}
const cpuBarW = (v) => Math.min(100, v || 0) + '%'
const memBarW = (v) => Math.min(100, (v||0)/2048*100) + '%'
const cpuCls = (v) => v > 80 ? 'val-danger' : v > 50 ? 'val-warning' : ''
const memCls = (v) => v > 1024 ? 'val-danger' : v > 512 ? 'val-warning' : ''

const formatRelativeTime = (t) => {
  if (!t) return '-'
  const diff = (Date.now() - new Date(t).getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff/60) + '分钟前'
  if (diff < 86400) return Math.floor(diff/3600) + '小时前'
  return Math.floor(diff/86400) + '天前'
}

const loadData = async () => {
  try {
    const [overviewRes, statusRes, metricsRes, alertsRes] = await Promise.all([
      axios.get('/api/monitor/overview'),
      axios.get('/api/monitor/status'),
      axios.get('/api/metrics/services'),
      axios.get('/api/alerts')
    ])
    overview.value = overviewRes.data?.data || {}
    services.value = statusRes.data?.data?.results || []
    metrics.value = metricsRes.data?.data || []
    alerts.value = (alertsRes.data?.data || []).sort((a, b) => new Date(b.startsAt) - new Date(a.startsAt))
  } catch (e) {
    console.error('加载监控数据失败:', e)
  }
}

// ===== 服务器监控方法 =====
const loadServerList = async () => {
  loadingServers.value = true
  try {
    const res = await axios.get('/api/monitor/servers')
    serverList.value = res.data?.data || []
  } catch (e) {
    console.error('加载服务器列表失败:', e)
  } finally {
    loadingServers.value = false
  }
}

const selectServer = async (srv) => {
  selectedServer.value = srv
  loadingMetrics.value = true
  
  try {
    // 并行加载指标和服务列表
    const [metricsRes, servicesRes] = await Promise.all([
      axios.get(`/api/monitor/server/${srv.id}/metrics`, { params: { time_range: timeRange.value } }),
      axios.get(`/api/monitor/server/${srv.id}/services`)
    ])
    
    // 渲染图表
    await nextTick()
    renderServerCharts(metricsRes.data?.data || {})
    
    // 设置服务列表
    serverServices.value = servicesRes.data?.data?.services || []
  } catch (e) {
    console.error('加载服务器详情失败:', e)
    ElMessage.error('加载服务器监控数据失败')
  } finally {
    loadingMetrics.value = false
  }
}

const renderServerCharts = (metrics) => {
  // CPU Chart
  if (cpuChartRef.value) {
    if (!cpuChart) cpuChart = echarts.init(cpuChartRef.value)
    cpuChart.setOption({
      tooltip: { trigger: 'axis', formatter: '{b}<br/>CPU: {c}%' },
      grid: { left: 50, right: 20, top: 10, bottom: 30 },
      xAxis: { type: 'category', boundaryGap: false,
        data: (metrics.cpu || []).map(d => new Date(d[0] * 1000).toLocaleTimeString())
      },
      yAxis: { type: 'value', min: 0, max: 100, name: '%' },
      series: [{
        type: 'line', smooth: true, showSymbol: false,
        data: (metrics.cpu || []).map(d => d[1]),
        lineStyle: { color: '#3b82f6', width: 2 },
        areaStyle: { color: 'rgba(59,130,246,0.1)' }
      }]
    })
  }
  
  // Memory Chart
  if (memoryChartRef.value) {
    if (!memoryChart) memoryChart = echarts.init(memoryChartRef.value)
    memoryChart.setOption({
      tooltip: { trigger: 'axis', formatter: '{b}<br/>内存: {c}%' },
      grid: { left: 50, right: 20, top: 10, bottom: 30 },
      xAxis: { type: 'category', boundaryGap: false,
        data: (metrics.memory || []).map(d => new Date(d[0] * 1000).toLocaleTimeString())
      },
      yAxis: { type: 'value', min: 0, max: 100, name: '%' },
      series: [{
        type: 'line', smooth: true, showSymbol: false,
        data: (metrics.memory || []).map(d => d[1]),
        lineStyle: { color: '#8b5cf6', width: 2 },
        areaStyle: { color: 'rgba(139,92,246,0.1)' }
      }]
    })
  }
  
  // Network Chart
  if (networkChartRef.value) {
    if (!networkChart) networkChart = echarts.init(networkChartRef.value)
    networkChart.setOption({
      tooltip: { trigger: 'axis', formatter: '{b}<br/>接收: {c[0]} MB/s<br/>发送: {c[1]} MB/s' },
      grid: { left: 50, right: 20, top: 10, bottom: 30 },
      xAxis: { type: 'category', boundaryGap: false,
        data: (metrics.network_rx || []).map(d => new Date(d[0] * 1000).toLocaleTimeString())
      },
      yAxis: { type: 'value', min: 0, name: 'MB/s' },
      series: [
        {
          name: '接收', type: 'line', smooth: true, showSymbol: false,
          data: (metrics.network_rx || []).map(d => d[1]),
          lineStyle: { color: '#10b981', width: 2 },
          areaStyle: { color: 'rgba(16,185,129,0.1)' }
        },
        {
          name: '发送', type: 'line', smooth: true, showSymbol: false,
          data: (metrics.network_tx || []).map(d => d[1]),
          lineStyle: { color: '#f59e0b', width: 2 },
          areaStyle: { color: 'rgba(245,158,11,0.1)' }
        }
      ]
    })
  }
  
  // Disk Chart
  if (diskChartRef.value) {
    if (!diskChart) diskChart = echarts.init(diskChartRef.value)
    diskChart.setOption({
      tooltip: { trigger: 'axis', formatter: '{b}<br/>磁盘: {c}%' },
      grid: { left: 50, right: 20, top: 10, bottom: 30 },
      xAxis: { type: 'category', boundaryGap: false,
        data: (metrics.disk || []).map(d => new Date(d[0] * 1000).toLocaleTimeString())
      },
      yAxis: { type: 'value', min: 0, max: 100, name: '%' },
      series: [{
        type: 'line', smooth: true, showSymbol: false,
        data: (metrics.disk || []).map(d => d[1]),
        lineStyle: { color: '#ef4444', width: 2 },
        areaStyle: { color: 'rgba(239,68,68,0.1)' }
      }]
    })
  }
}

const refreshAll = async () => {
  isRefreshing.value = true
  await loadData()
  updateGauges()
  if (activeTab.value === 'servers') {
    await loadServerList()
    if (selectedServer.value) {
      // 重新加载当前选中服务器的数据
      const srv = selectedServer.value
      try {
        const metricsRes = await axios.get(`/api/monitor/server/${srv.id}/metrics`, { params: { time_range: timeRange.value } })
        await nextTick()
        renderServerCharts(metricsRes.data?.data || {})
      } catch (e) { console.error('刷新服务器数据失败:', e) }
    }
  }
  page.value = 1
  setTimeout(() => { isRefreshing.value = false }, 500)
}

const ctrlService = async (svc, op) => {
  const id = svc.service_id || svc.id
  const labels = { start: '启动', stop: '停止', restart: '重启' }
  try {
    const res = await axios.post(`/api/monitor/${op}/${id}`)
    if (res.data?.code === 0) {
      ElMessage.success(`${svc.service_name || svc.name} ${labels[op]}成功`)
      setTimeout(loadData, 2000)
    } else {
      ElMessage.error(res.data?.message || `${labels[op]}失败`)
    }
  } catch { ElMessage.error(`${labels[op]}请求失败`) }
}

const showDetail = (s) => { cur.value = s; dlgVisible.value = true }

const initGauges = () => {
  if (cpuGaugeRef.value) {
    cpuGauge = echarts.init(cpuGaugeRef.value)
    cpuGauge.setOption({
      series: [{
        type: 'gauge', radius: '90%', center: ['50%', '55%'],
        startAngle: 200, endAngle: -20, min: 0, max: 100,
        progress: { show: true, width: 12, itemStyle: { color: '#3b82f6' } },
        axisLine: { lineStyle: { width: 12, color: [[1, '#f1f5f9']] } },
        axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
        pointer: { show: false },
        anchor: { show: false },
        title: { show: false },
        detail: {
          valueAnimation: true, fontSize: 22, fontWeight: 700,
          offsetCenter: [0, '10%'], formatter: '{value}%',
          color: '#1e293b'
        },
        data: [{ value: 0 }]
      }]
    })
  }
  if (memGaugeRef.value) {
    memGauge = echarts.init(memGaugeRef.value)
    memGauge.setOption({
      series: [{
        type: 'gauge', radius: '90%', center: ['50%', '55%'],
        startAngle: 200, endAngle: -20, min: 0, max: 2048,
        progress: { show: true, width: 12, itemStyle: { color: '#8b5cf6' } },
        axisLine: { lineStyle: { width: 12, color: [[1, '#f1f5f9']] } },
        axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
        pointer: { show: false },
        anchor: { show: false },
        title: { show: false },
        detail: {
          valueAnimation: true, fontSize: 22, fontWeight: 700,
          offsetCenter: [0, '10%'], formatter: '{value}MB',
          color: '#1e293b'
        },
        data: [{ value: 0 }]
      }]
    })
  }
}

const updateGauges = () => {
  const o = overview.value
  if (cpuGauge) {
    const v = o.avg_cpu || 0
    const color = v > 80 ? '#ef4444' : v > 50 ? '#f59e0b' : '#3b82f6'
    cpuGauge.setOption({ series: [{ progress: { itemStyle: { color } }, data: [{ value: v }] }] })
  }
  if (memGauge) {
    const v = o.avg_memory || 0
    const color = v > 1024 ? '#ef4444' : v > 512 ? '#f59e0b' : '#8b5cf6'
    memGauge.setOption({ series: [{ progress: { itemStyle: { color } }, data: [{ value: v }] }] })
  }
}

// Watch autoRefresh
watch(autoRefresh, (v) => {
  if (v) {
    timer = setInterval(refreshAll, 30000)
  } else {
    clearInterval(timer); timer = null
  }
})

// Watch tab switch
watch(activeTab, (tab) => {
  if (tab === 'servers' && serverList.value.length === 0) {
    loadServerList()
  }
})

// Watch timeRange change - reload server metrics if viewing a server
watch(timeRange, async () => {
  if (activeTab.value === 'servers' && selectedServer.value) {
    try {
      const metricsRes = await axios.get(`/api/monitor/server/${selectedServer.value.id}/metrics`, { params: { time_range: timeRange.value } })
      await nextTick()
      renderServerCharts(metricsRes.data?.data || {})
    } catch (e) { console.error('重新加载指标失败:', e) }
  }
})

onMounted(async () => {
  loading.value = true
  await Promise.all([
    loadData(),
    loadServerList()
  ])
  await nextTick()
  initGauges()
  updateGauges()
  loading.value = false
  if (autoRefresh.value) timer = setInterval(refreshAll, 30000)
  window.addEventListener('resize', () => { 
    cpuGauge?.resize(); memGauge?.resize()
    cpuChart?.resize(); memoryChart?.resize(); networkChart?.resize(); diskChart?.resize()
  })
})

onUnmounted(() => {
  clearInterval(timer)
  cpuGauge?.dispose(); memGauge?.dispose()
  cpuChart?.dispose(); memoryChart?.dispose(); networkChart?.dispose(); diskChart?.dispose()
})
</script>

<style scoped>
/* ===== Base ===== */
.monitoring-page { padding: 24px 28px; background: #f0f2f5; min-height: calc(100vh - 60px); }

/* ===== Header ===== */
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.header-title-row { display: flex; align-items: center; gap: 10px; }
.header-title-row h1 { font-size: 22px; font-weight: 700; color: #0f172a; margin: 0; }
.live-badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; color: #10b981; background: rgba(16,185,129,.08); border: 1px solid rgba(16,185,129,.2); letter-spacing: .5px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #10b981; animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(16,185,129,.4)} 50%{opacity:.7;box-shadow:0 0 0 4px rgba(16,185,129,0)} }
.subtitle { font-size: 13px; color: #64748b; margin: 4px 0 0; }
.header-right { display: flex; align-items: center; gap: 14px; }
.time-range-selector { display: flex; background: #f1f5f9; border-radius: 8px; padding: 3px; }
.time-opt { padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; color: #64748b; cursor: pointer; transition: all .2s; }
.time-opt.active { background: #fff; color: #1e293b; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.auto-refresh-toggle { display: flex; align-items: center; gap: 8px; padding: 5px 12px; border-radius: 8px; font-size: 12px; color: #64748b; cursor: pointer; border: 1px solid #e2e8f0; background: #fff; transition: all .2s; user-select: none; }
.auto-refresh-toggle:hover { border-color: #cbd5e1; }
.toggle-dot { width: 28px; height: 16px; border-radius: 8px; background: #cbd5e1; position: relative; transition: background .2s; }
.toggle-dot.on { background: #10b981; }
.toggle-dot::after { content: ''; position: absolute; top: 2px; left: 2px; width: 12px; height: 12px; border-radius: 50%; background: #fff; transition: transform .2s; }
.toggle-dot.on::after { transform: translateX(12px); }
.refresh-btn { width: 34px; height: 34px; border-radius: 8px; border: 1px solid #e2e8f0; background: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; color: #64748b; transition: all .2s; }
.refresh-btn:hover { border-color: #3b82f6; color: #3b82f6; background: #eff6ff; }
.refresh-btn.spinning { animation: spin .6s linear; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ===== KPI Grid ===== */
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.kpi-card { background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 18px 20px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; cursor: pointer; transition: all .2s; }
.kpi-card:hover { border-color: #cbd5e1; box-shadow: 0 4px 12px rgba(0,0,0,.06); transform: translateY(-2px); }
.kpi-icon-wrap { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.kpi-body { flex: 1; min-width: 0; }
.kpi-label { font-size: 12px; color: #64748b; font-weight: 500; margin-bottom: 4px; }
.kpi-value { font-size: 26px; font-weight: 800; line-height: 1; letter-spacing: -.5px; }
.kpi-footer { width: 100%; display: flex; justify-content: space-between; align-items: center; padding-top: 10px; border-top: 1px solid #f1f5f9; }
.kpi-sub { font-size: 11px; color: #94a3b8; }
.kpi-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; }
.badge-ok { background: rgba(16,185,129,.08); color: #10b981; }
.badge-warn { background: rgba(239,68,68,.08); color: #ef4444; }

/* ===== Mid Section ===== */
.mid-section { display: grid; grid-template-columns: 1.1fr .9fr; gap: 14px; margin-bottom: 20px; }
.panel { background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; }
.panel-head { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #f1f5f9; }
.panel-title { font-size: 14px; font-weight: 600; color: #1e293b; display: flex; align-items: center; gap: 8px; }
.panel-total { font-size: 12px; color: #94a3b8; }

/* Status Overview */
.status-overview { padding: 20px; }
.ring-wrap { position: relative; width: 140px; height: 140px; margin: 0 auto 20px; }
.ring-svg { width: 100%; height: 100%; }
.ring-seg { transition: stroke-dasharray .8s ease; }
.ring-center { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); text-align: center; }
.ring-num { font-size: 28px; font-weight: 800; color: #1e293b; line-height: 1; }
.ring-num small { font-size: 14px; font-weight: 600; }
.ring-label { font-size: 11px; color: #94a3b8; margin-top: 4px; }

.status-bars { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
.sbar-row { display: flex; align-items: center; gap: 10px; }
.sbar-label { display: flex; align-items: center; gap: 6px; width: 60px; font-size: 12px; color: #475569; font-weight: 500; flex-shrink: 0; }
.sbar-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.sbar-track { flex: 1; height: 18px; background: #f1f5f9; border-radius: 5px; overflow: hidden; }
.sbar-fill { height: 100%; border-radius: 5px; transition: width .8s ease; }
.sbar-num { font-size: 13px; color: #64748b; font-weight: 600; width: 36px; text-align: right; flex-shrink: 0; }

.gauges-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.gauge-item { text-align: center; }
.gauge-chart { height: 120px; }
.gauge-label { font-size: 11px; color: #94a3b8; margin-top: -8px; }

/* Alert Panel */
.alert-panel { display: flex; flex-direction: column; }
.alert-count-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 20px; height: 20px; border-radius: 10px; background: #ef4444; color: #fff; font-size: 11px; font-weight: 700; padding: 0 6px; }
.alert-filter-tabs { display: flex; gap: 3px; background: #f1f5f9; border-radius: 6px; padding: 2px; }
.af-tab { padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; color: #64748b; cursor: pointer; transition: all .15s; }
.af-tab.active { background: #fff; color: #1e293b; box-shadow: 0 1px 2px rgba(0,0,0,.06); }
.alert-list { flex: 1; overflow-y: auto; max-height: 420px; }
.alert-row { display: flex; border-bottom: 1px solid #f8fafc; transition: background .15s; }
.alert-row:hover { background: #fafbfc; }
.alert-sev-bar { width: 3px; flex-shrink: 0; }
.alert-row.critical .alert-sev-bar { background: #ef4444; }
.alert-row.warning .alert-sev-bar { background: #f59e0b; }
.alert-row.info .alert-sev-bar { background: #3b82f6; }
.alert-body { flex: 1; padding: 12px 16px; min-width: 0; }
.alert-top { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.alert-name { font-size: 13px; font-weight: 600; color: #1e293b; }
.alert-sev-tag { font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 3px; text-transform: uppercase; letter-spacing: .3px; }
.alert-sev-tag.critical { background: #fef2f2; color: #dc2626; }
.alert-sev-tag.warning { background: #fffbeb; color: #d97706; }
.alert-sev-tag.info { background: #eff6ff; color: #2563eb; }
.alert-time { font-size: 11px; color: #94a3b8; margin-left: auto; }
.alert-msg { font-size: 12px; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.alert-inst { font-size: 11px; color: #94a3b8; font-family: 'SF Mono',Monaco,monospace; margin-top: 2px; }
.alert-empty { display: flex; flex-direction: column; align-items: center; padding: 50px 20px; color: #94a3b8; }
.alert-empty p { margin: 10px 0 0; font-size: 13px; }

/* ===== Service Panel ===== */
.svc-panel { background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; }
.svc-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 20px; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; gap: 10px; }
.svc-head-left { display: flex; align-items: center; gap: 10px; }
.svc-cnt { font-size: 12px; color: #94a3b8; }
.svc-head-right { display: flex; align-items: center; gap: 10px; }
.filter-tabs { display: flex; gap: 3px; background: #f1f5f9; border-radius: 7px; padding: 2px; }
.ft-tab { display: flex; align-items: center; gap: 5px; padding: 5px 12px; border-radius: 5px; font-size: 12px; font-weight: 500; color: #64748b; cursor: pointer; transition: all .15s; user-select: none; }
.ft-tab.active { background: #fff; color: #1e293b; box-shadow: 0 1px 2px rgba(0,0,0,.06); }
.ft-dot { width: 6px; height: 6px; border-radius: 50%; }
.sort-select { padding: 5px 10px; border-radius: 6px; border: 1px solid #e2e8f0; font-size: 12px; color: #475569; background: #fff; cursor: pointer; outline: none; }
.sort-select:focus { border-color: #3b82f6; }

.tbl-wrap { overflow-x: auto; }
.data-tbl { width: 100%; border-collapse: collapse; }
.data-tbl thead th { padding: 10px 14px; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: .5px; text-align: left; background: #f8fafc; border-bottom: 1px solid #e2e8f0; white-space: nowrap; }
.data-tbl tbody td { padding: 12px 14px; font-size: 13px; color: #475569; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
.svc-tr { transition: background .12s; }
.svc-tr:hover { background: #f8fafc; }

.name-cell { display: flex; align-items: center; gap: 10px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot.running { background: #10b981; box-shadow: 0 0 0 3px rgba(16,185,129,.15); animation: dot-p 2s infinite; }
.status-dot.stopped { background: #ef4444; }
.status-dot.unknown { background: #f59e0b; }
@keyframes dot-p { 0%,100%{box-shadow:0 0 0 3px rgba(16,185,129,.15)} 50%{box-shadow:0 0 0 6px rgba(16,185,129,0)} }
.svc-name { font-weight: 600; color: #1e293b; font-size: 13px; }
.svc-sub { font-size: 11px; color: #94a3b8; }
.addr-text { font-family: 'SF Mono',Monaco,monospace; font-size: 12px; color: #475569; }

.st-pill { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
.st-pill.running { background: rgba(16,185,129,.08); color: #10b981; }
.st-pill.stopped { background: rgba(239,68,68,.08); color: #ef4444; }
.st-pill.unknown { background: rgba(245,158,11,.08); color: #f59e0b; }
.st-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.st-pill.running .st-dot { animation: st-p 2s infinite; }
@keyframes st-p { 0%,100%{opacity:1} 50%{opacity:.4} }

.bar-cell { display: flex; align-items: center; gap: 8px; }
.mini-bar { width: 60px; height: 6px; background: #f1f5f9; border-radius: 3px; overflow: hidden; }
.mini-fill { height: 100%; border-radius: 3px; transition: width .6s ease; }
.mini-fill.cpu { background: #3b82f6; }
.mini-fill.mem { background: #8b5cf6; }
.bar-val { font-size: 12px; font-weight: 500; font-family: 'SF Mono',Monaco,monospace; }
.val-danger { color: #ef4444; font-weight: 700; }
.val-warning { color: #f59e0b; font-weight: 600; }
.uptime { font-size: 12px; color: #64748b; }

.act-cell { display: flex; gap: 3px; }
.act-btn { width: 28px; height: 28px; border-radius: 5px; border: 1px solid #e2e8f0; background: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all .15s; color: #64748b; }
.act-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 2px 6px rgba(0,0,0,.06); }
.act-btn:disabled { opacity: .3; cursor: not-allowed; }
.act-btn.start { color: #10b981; }
.act-btn.start:hover:not(:disabled) { background: #f0fdf4; border-color: #10b981; }
.act-btn.stop { color: #ef4444; }
.act-btn.stop:hover:not(:disabled) { background: #fef2f2; border-color: #ef4444; }
.act-btn.restart { color: #3b82f6; }
.act-btn.restart:hover:not(:disabled) { background: #eff6ff; border-color: #3b82f6; }
.act-btn.detail { color: #8b5cf6; }
.act-btn.detail:hover:not(:disabled) { background: #f5f3ff; border-color: #8b5cf6; }

.tbl-empty { display: flex; flex-direction: column; align-items: center; padding: 50px 20px; color: #94a3b8; }
.tbl-empty p { margin: 12px 0 0; font-size: 14px; }
.tbl-foot { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; border-top: 1px solid #e2e8f0; background: #fafbfc; }
.foot-info { font-size: 12px; color: #94a3b8; }
.foot-pager { display: flex; align-items: center; gap: 6px; }
.pg-btn { width: 28px; height: 28px; border-radius: 5px; border: 1px solid #e2e8f0; background: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 14px; color: #475569; transition: all .15s; }
.pg-btn:hover:not(:disabled) { background: #f1f5f9; border-color: #3b82f6; color: #3b82f6; }
.pg-btn:disabled { opacity: .35; cursor: not-allowed; }
.pg-ind { font-size: 12px; color: #64748b; font-weight: 500; }

/* ===== Dialog ===== */
.dlg { padding: 4px 0; }
.dlg-head { margin-bottom: 20px; padding-bottom: 14px; border-bottom: 1px solid #e2e8f0; }
.dlg-title-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.dlg-title-row h3 { font-size: 18px; font-weight: 700; color: #1e293b; margin: 0; }
.dlg-sub { font-size: 13px; color: #64748b; margin: 0; font-family: 'SF Mono',Monaco,monospace; }
.dlg-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.dlg-card { padding: 16px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; }
.dlg-card-label { font-size: 11px; color: #64748b; margin-bottom: 6px; font-weight: 500; }
.dlg-card-val { font-size: 22px; font-weight: 700; color: #1e293b; }
.dlg-card-bar { height: 4px; background: #e2e8f0; border-radius: 2px; margin-top: 10px; overflow: hidden; }
.dlg-bar-fill { height: 100%; border-radius: 2px; transition: width .6s; }
.dlg-bar-fill.cpu { background: #3b82f6; }
.dlg-bar-fill.mem { background: #8b5cf6; }

/* ===== Tab Bar ===== */
.tab-bar { display: flex; gap: 8px; margin-bottom: 16px; padding: 0 4px; }
.tab-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 8px; border: 1px solid #e2e8f0; background: #fff; cursor: pointer; font-size: 13px; color: #64748b; transition: all .2s; }
.tab-btn:hover { border-color: #3b82f6; color: #3b82f6; }
.tab-btn.active { background: #eff6ff; border-color: #3b82f6; color: #3b82f6; font-weight: 600; }
.tab-content { animation: fadeIn .3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

/* ===== Server Grid ===== */
.server-grid { min-height: 200px; }
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 20px; color: #94a3b8; text-align: center; }
.empty-state p { margin-top: 12px; font-size: 14px; }
.server-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.server-card { background: #fff; border-radius: 12px; border: 2px solid #e2e8f0; padding: 16px; cursor: pointer; transition: all .2s; }
.server-card:hover { border-color: #3b82f6; box-shadow: 0 4px 12px rgba(59,130,246,.1); }
.server-card.selected { border-color: #3b82f6; background: #eff6ff; }
.sc-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.sc-info h3 { font-size: 15px; font-weight: 600; color: #1e293b; margin: 0 0 4px; }
.sc-ip { font-size: 12px; color: #64748b; font-family: 'SF Mono',Monaco,monospace; }
.sc-status { font-size: 11px; padding: 3px 8px; border-radius: 12px; font-weight: 600; }
.sc-status.ok { background: #d1fae5; color: #065f46; }
.sc-status.warning { background: #fef3c7; color: #92400e; }
.sc-status.danger { background: #fee2e2; color: #991b1b; }
.sc-metrics { display: flex; flex-direction: column; gap: 10px; }
.sc-metric { display: flex; flex-direction: column; gap: 4px; }
.sc-m-label { font-size: 11px; color: #64748b; font-weight: 500; }
.sc-m-val { font-size: 13px; font-weight: 600; color: #1e293b; }
.sc-m-val.net { font-size: 11px; color: #475569; }
.sc-m-val.disk { font-size: 13px; font-weight: 600; }
.sc-bar { height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; }
.sc-bar-fill { height: 100%; border-radius: 2px; transition: width .4s; }
.sc-bar-fill.cpu { background: #3b82f6; }
.sc-bar-fill.mem { background: #8b5cf6; }
.sc-bar-fill.disk { background: #ef4444; }

/* ===== Server Detail ===== */
.server-detail { margin-top: 20px; background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 20px; }
.sd-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 14px; border-bottom: 1px solid #e2e8f0; }
.sd-title h2 { font-size: 18px; font-weight: 700; color: #1e293b; margin: 0 0 4px; }
.sd-ip { font-size: 13px; color: #64748b; font-family: 'SF Mono',Monaco,monospace; }
.back-btn { display: flex; align-items: center; gap: 4px; padding: 6px 12px; border-radius: 6px; border: 1px solid #e2e8f0; background: #fff; cursor: pointer; font-size: 12px; color: #475569; transition: all .2s; }
.back-btn:hover { background: #f1f5f9; border-color: #3b82f6; color: #3b82f6; }

/* ===== Charts ===== */
.sd-charts { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 24px; }
.chart-panel { background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; padding: 12px; }
.chart-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.chart-title { font-size: 13px; font-weight: 600; color: #1e293b; }
.chart-unit { font-size: 11px; color: #64748b; }
.chart-container { height: 200px; }

/* ===== Server Services ===== */
.sd-services { border-top: 1px solid #e2e8f0; padding-top: 16px; }

/* ===== Responsive ===== */
@media (max-width: 1400px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 1200px) { .mid-section { grid-template-columns: 1fr; } }
@media (max-width: 768px) {
  .monitoring-page { padding: 14px; }
  .kpi-grid { grid-template-columns: 1fr; }
  .page-header { flex-direction: column; gap: 12px; }
  .header-right { flex-wrap: wrap; }
  .dlg-grid { grid-template-columns: 1fr; }
}
</style>
