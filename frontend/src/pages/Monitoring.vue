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
        <p class="subtitle">实时监控纳管服务器的资源状态、风险排行与活跃告警</p>
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
        <span class="last-updated" v-if="lastUpdatedText">更新于 {{ lastUpdatedText }}</span>
        <div class="refresh-btn" @click="refreshAll" :class="{ spinning: isRefreshing }">
          <el-icon :size="15"><Refresh /></el-icon>
        </div>
      </div>
    </div>

    <!-- ===== KPI 指标卡片 ===== -->
    <div class="kpi-grid">
      <div class="kpi-card" v-for="kpi in kpiCards" :key="kpi.key"
        :class="{ clickable: !!kpi.action }" @click="kpi.action && kpi.action()">
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

    <!-- ===== 全局概览 Tab（深色运维大屏） ===== -->
    <div v-if="activeTab === 'overview'" class="tab-content">
      <div class="screen">
        <div class="screen-grid">
          <!-- 服务器健康分布环形图 -->
          <div class="screen-panel">
            <div class="screen-head">
              <div>
                <div class="screen-title">服务器健康分布</div>
                <div class="screen-sub">按资源采集状态统计 · 分母为全部纳管服务器</div>
              </div>
              <button type="button" class="screen-total clickable" @click="gotoServers()">纳管 {{ ov.total_servers ?? 0 }} 台</button>
            </div>
            <div class="screen-body donut-body">
              <div ref="healthChartRef" class="donut-chart"></div>
              <div class="donut-legend">
                <button v-for="c in healthItems" :key="c.key" class="dl-row"
                  :class="{ dim: !c.count, highlight: c.key === 'nodata' && c.count > 0 }"
                  @click="gotoCategory(c.key)">
                  <span class="dl-dot" :style="{ background: c.color }"></span>
                  <span class="dl-label">{{ c.label }}</span>
                  <span class="dl-count">{{ c.count }}<small>台</small></span>
                  <span class="dl-pct">{{ c.pct }}%</span>
                </button>
              </div>
            </div>
            <div v-if="!ov.total_servers" class="screen-empty">当前范围暂无纳管服务器</div>
          </div>

          <!-- 资源风险 TOP5 横向条形 -->
          <div class="screen-panel">
            <div class="screen-head">
              <div>
                <div class="screen-title">资源风险 TOP5</div>
                <div class="screen-sub">CPU / 内存阈值 {{ thr.cpu }}% · 磁盘阈值 {{ thr.disk }}%</div>
              </div>
              <button type="button" class="screen-total clickable" :class="{ danger: (ov.resource_risk || 0) > 0 }"
                @click="gotoCategory('abnormal')">
                超阈 {{ ov.resource_risk ?? 0 }} 台
              </button>
            </div>
            <div class="screen-body">
              <div v-if="!topRisk.length" class="screen-empty">
                {{ ov.data_servers ? '暂无有效资源指标' : '暂无监控数据' }}
              </div>
              <div v-else class="risk-list">
                <button v-for="(r, i) in topRisk" :key="r.server_id + '-' + r.metric" class="risk-row"
                  @click="gotoServer(r.server_id)">
                  <span class="rk-rank" :class="{ danger: r.over_threshold }">{{ i + 1 }}</span>
                  <div class="rk-main">
                    <div class="rk-top">
                      <span class="rk-name">{{ r.hostname }}</span>
                      <span class="rk-metric">{{ r.metric_label }}</span>
                      <span class="rk-val" :class="{ danger: r.over_threshold }">{{ fmtPct(r.value) }}%</span>
                    </div>
                    <div class="rk-bar">
                      <div class="rk-fill" :class="{ danger: r.over_threshold }" :style="{ width: barW(r.value) }"></div>
                      <span class="rk-thr-line" :style="{ left: barW(r.threshold) }"></span>
                    </div>
                    <div class="rk-foot">
                      <span class="rk-ip">{{ r.ip }}</span>
                      <span class="rk-threshold">阈值 {{ fmtPct(r.threshold) }}%</span>
                    </div>
                  </div>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 活跃告警面板 -->
        <div class="screen-panel alert-screen">
          <div class="screen-head">
            <div>
              <div class="screen-title">活跃告警</div>
              <div class="screen-sub">来源：告警中心（未恢复告警）</div>
            </div>
            <div class="alert-head-right" v-if="ov.alerts && ov.alerts.available">
              <span class="sev-chip critical" :class="{ clickable: canViewAlerts }"
                :title="canViewAlerts ? '查看严重级别活跃告警' : ''"
                @click="canViewAlerts && goOpenAlerts({ severity: 'critical' })">严重 {{ alertSev.critical || 0 }}</span>
              <span class="sev-chip warning" :class="{ clickable: canViewAlerts }"
                :title="canViewAlerts ? '查看警告级别活跃告警' : ''"
                @click="canViewAlerts && goOpenAlerts({ severity: 'warning' })">警告 {{ alertSev.warning || 0 }}</span>
              <span v-if="canViewAlerts" class="screen-link" @click="goOpenAlerts()">查看全部 →</span>
            </div>
          </div>
          <div class="screen-body">
            <div v-if="!ov.alerts" class="screen-empty">告警数据加载中</div>
            <div v-else-if="!ov.alerts.available" class="screen-empty warn">
              <el-icon :size="16"><Warning /></el-icon>
              <span>告警源不可用{{ ov.alerts.error ? '：' + ov.alerts.error : '' }}</span>
            </div>
            <div v-else-if="!alertItems.length" class="screen-empty">暂无活跃告警</div>
            <div v-else class="alert-rows">
              <div v-for="a in alertItems" :key="a.id" class="alert-item" :class="[a.severity, { clickable: canViewAlerts }]"
                :title="canViewAlerts ? '点击查看该告警详情' : ''"
                @click="canViewAlerts && goAlertDetail(a)">
                <span class="ai-sev-bar" :class="a.severity"></span>
                <div class="ai-main">
                  <div class="ai-top">
                    <span class="ai-title">{{ a.title }}</span>
                    <span class="ai-st" :class="a.status">{{ alertStatusLabel(a.status) }}</span>
                    <span class="ai-time">{{ formatRelativeTime(a.last_seen_at) }}</span>
                  </div>
                  <div class="ai-sub">{{ a.service_name }}<template v-if="a.ip"> · {{ a.ip }}</template></div>
                  <div v-if="a.content" class="ai-content">{{ a.content }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== 服务器监控 Tab ===== -->
    <div v-if="activeTab === 'servers'" class="tab-content">
      <!-- 服务器列表：工具条 + 卡片/列表视图 + 分页 -->
      <div class="server-grid" v-loading="loadingServers">
        <div v-if="serverList.length" class="server-toolbar">
          <el-input v-model="searchKeyword" class="srv-search" placeholder="搜索主机名或 IP" clearable />
          <el-select v-model="statusFilter" class="srv-filter">
            <el-option label="全部状态" value="all" />
            <el-option label="异常" value="abnormal" />
            <el-option label="正常" value="normal" />
            <el-option label="有数据" value="hasdata" />
            <el-option label="无数据" value="nodata" />
          </el-select>
          <div class="srv-view-toggle">
            <button class="vt-btn" :class="{ active: viewMode === 'card' }" @click="viewMode = 'card'">卡片</button>
            <button class="vt-btn" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'">列表</button>
          </div>
          <span class="srv-count">共 {{ filteredServers.length }} 台</span>
        </div>

        <div v-if="!serverList.length" class="empty-state">
          <el-icon :size="48" color="#d1d5db"><Platform /></el-icon>
          <p>暂无服务器数据，请先在"服务器管理"中添加服务器</p>
        </div>
        <div v-else-if="!filteredServers.length" class="empty-state">
          <el-icon :size="48" color="#d1d5db"><Platform /></el-icon>
          <p>无匹配的服务器，请调整搜索或筛选条件</p>
        </div>
        <template v-else>
          <!-- 卡片视图 -->
          <div v-if="viewMode === 'card'" class="server-cards">
            <div v-for="srv in pagedServers" :key="srv.id"
              class="server-card"
              :class="{ selected: selectedServer?.id === srv.id, nodata: !srv.has_data }"
              @click="selectServer(srv)">
              <div class="sc-header">
                <div class="sc-info">
                  <h3>{{ srv.hostname || srv.ip }}</h3>
                  <span class="sc-ip">{{ srv.ip }}</span>
                </div>
                <span class="sc-status" :class="srvStatusCls(srv)">{{ srvStatusText(srv) }}</span>
              </div>
              <template v-if="srv.has_data">
                <div class="sc-metrics">
                  <div class="sc-metric" v-for="m in srvMetrics(srv)" :key="m.key">
                    <div class="sc-m-row">
                      <span class="sc-m-label">{{ m.label }}</span>
                      <span class="sc-m-val" :class="m.cls">{{ m.value }}</span>
                    </div>
                    <div class="sc-bar"><div class="sc-bar-fill" :class="m.key" :style="{ width: m.width + '%' }"></div></div>
                  </div>
                </div>
                <div class="sc-net">
                  <span class="sc-m-label">网络</span>
                  <span class="sc-m-val net">↓ {{ srv.network_rx_mb.toFixed(2) }} ↑ {{ srv.network_tx_mb.toFixed(2) }} MB/s</span>
                </div>
              </template>
              <div v-else class="sc-nodata">
                <el-icon :size="15"><Warning /></el-icon>
                <span>暂无监控指标数据</span>
              </div>
            </div>
          </div>

          <!-- 列表视图 -->
          <div v-else class="srv-table-card">
            <table class="srv-table">
              <thead>
                <tr>
                  <th>主机名</th>
                  <th>IP</th>
                  <th>状态</th>
                  <th>CPU</th>
                  <th>内存</th>
                  <th>磁盘</th>
                  <th>网络</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="srv in pagedServers" :key="srv.id"
                  :class="{ selected: selectedServer?.id === srv.id }"
                  @click="selectServer(srv)">
                  <td class="sv-name">{{ srv.hostname || '-' }}</td>
                  <td class="sv-ip">{{ srv.ip }}</td>
                  <td><span class="sc-status" :class="srvStatusCls(srv)">{{ srvStatusText(srv) }}</span></td>
                  <td>{{ srv.has_data ? (srv.cpu_percent || 0).toFixed(1) + '%' : '-' }}</td>
                  <td>{{ srv.has_data ? (srv.memory_percent || 0).toFixed(1) + '%' : '-' }}</td>
                  <td>{{ srv.has_data ? (srv.disk_usage_percent || 0).toFixed(1) + '%' : '-' }}</td>
                  <td class="sv-net">{{ srv.has_data ? `↓ ${srv.network_rx_mb.toFixed(2)} ↑ ${srv.network_tx_mb.toFixed(2)} MB/s` : '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 分页（卡片与列表共用） -->
          <div class="srv-pager">
            <el-pagination background layout="prev, pager, next, sizes, total"
              :page-sizes="[12, 16]" :total="filteredServers.length"
              v-model:current-page="currentPage" v-model:page-size="pageSize" />
          </div>
        </template>
      </div>

      <!-- 选中服务器的详细监控 -->
      <div v-if="selectedServer" class="server-detail" v-loading="loadingMetrics">
        <div class="sd-header">
          <div class="sd-title">
            <h2>{{ selectedServer.hostname }} - 详细监控</h2>
            <span class="sd-ip">{{ selectedServer.ip }}</span>
          </div>
          <div class="sd-actions">
            <button class="back-btn" @click="closeServerDetail">
              <el-icon :size="14"><ArrowLeft /></el-icon>
              <span>返回</span>
            </button>
          </div>
        </div>

        <div v-if="!selectedServer.has_data" class="sd-hint">
          <el-icon :size="14"><Warning /></el-icon>
          <span>该服务器在 Prometheus 中无 Node Exporter 监控数据，下方图表为空</span>
        </div>

        <!-- 资源趋势图表：时间范围切换（复用全局 timeRange 状态与现有指标接口） -->
        <div class="sd-trend-bar">
          <span class="sd-trend-title">资源历史趋势</span>
          <div class="time-range-selector">
            <span v-for="r in timeRanges" :key="r.value" class="time-opt"
              :class="{ active: timeRange === r.value }"
              @click="timeRange = r.value">{{ r.full }}</span>
          </div>
        </div>
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

        <!-- 服务器日志查询（Loki 服务器级容器日志） -->
        <div class="sd-logs">
          <div class="panel-head sd-logs-head">
            <span class="panel-title">服务器日志</span>
            <div class="log-toolbar">
              <select class="log-select" v-model="logRange" @change="loadServerLogs">
                <option value="15m">近 15 分钟</option>
                <option value="1h">近 1 小时</option>
                <option value="6h">近 6 小时</option>
                <option value="24h">近 24 小时</option>
              </select>
              <select class="log-select" v-model="logContainer" @change="loadServerLogs">
                <option value="">全部容器</option>
                <option v-for="c in logContainers" :key="c" :value="c">{{ c }}</option>
              </select>
              <select class="log-select" v-model="logLevel" @change="loadServerLogs">
                <option value="">全部级别</option>
                <option v-for="lv in logLevels" :key="lv" :value="lv">{{ lv }}</option>
              </select>
              <input class="log-input" v-model.trim="logKeyword" placeholder="关键词"
                @keyup.enter="loadServerLogs" />
              <button class="log-btn" @click="loadServerLogs" :disabled="loadingLogs">查询</button>
              <select class="log-select" v-model.number="logLimit" @change="loadServerLogs">
                <option :value="100">100 条</option>
                <option :value="200">200 条</option>
                <option :value="500">500 条</option>
                <option :value="1000">1000 条</option>
              </select>
              <button class="log-refresh" :class="{ spinning: loadingLogs }" @click="loadServerLogs" :disabled="loadingLogs">
                <el-icon :size="14"><Refresh /></el-icon>
              </button>
            </div>
          </div>

          <div v-if="loadingLogs" class="log-state">日志加载中...</div>
          <div v-else-if="!logEnabled" class="log-state">
            <el-icon :size="16"><Warning /></el-icon><span>日志服务未启用</span>
          </div>
          <div v-else-if="logError" class="log-state err">
            <el-icon :size="16"><Warning /></el-icon><span>日志查询失败：{{ logError }}</span>
          </div>
          <div v-else-if="!serverLogs.length" class="log-state">所选条件下暂无日志</div>
          <div v-else class="log-list">
            <div class="log-row" v-for="(l, i) in serverLogs" :key="i">
              <div class="log-meta">
                <span class="log-time">{{ fmtLogTime(l.timestamp) }}</span>
                <span class="log-level" :class="'lv-' + (l.level || 'unknown')">{{ l.level || 'unknown' }}</span>
                <span class="log-cont">{{ l.container }}</span>
              </div>
              <div class="log-msg">{{ l.message }}</div>
            </div>
            <div class="log-count">共显示 {{ serverLogs.length }} 条（单次上限 {{ logLimit }} 条）</div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from '@/utils/axios'
import { ElMessage } from 'element-plus'
import {
  Refresh, Monitor, Odometer, Warning, Platform, ArrowLeft, Bell
} from '@element-plus/icons-vue'
import { useThemeStore } from '../stores/theme'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

// 全站主题：监控中心随 html.dark 切换（浅色/深色共用一套图表 palette）
const themeStore = useThemeStore()
const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
// 告警中心接口要求 service:view；无权限时概览告警区保持只读，不提供跳转
const canViewAlerts = computed(() => userStore.hasPermission('service:view'))

// ===== 状态 =====
const loading = ref(true)
const isRefreshing = ref(false)
const autoRefresh = ref(true)
const lastUpdated = ref(null)
// 自动刷新间隔：Prometheus 查询有网络开销，60s 比 30s 更平稳
const REFRESH_INTERVAL = 60000
const timeRange = ref('1h')
const overview = ref({})   // from /api/monitor/overview（服务器维度聚合）

// Tab & Server states
const activeTab = ref('overview')
const loadingServers = ref(false)
const serverList = ref([])     // from /api/monitor/servers
// 服务器列表：搜索 / 状态筛选 / 视图切换 / 分页（全部复用 serverList，不发生额外请求）
const searchKeyword = ref('')
const statusFilter = ref('all')   // all | abnormal | normal | nodata
const viewMode = ref('card')      // card | list
const pageSize = ref(12)          // 12 或 16
const currentPage = ref(1)
const selectedServer = ref(null)
const loadingMetrics = ref(false)
const serverServices = ref([]) // from /api/monitor/server/{id}/services

// Server logs (Loki) states
const logRange = ref('1h')
const logContainer = ref('')
const logLevel = ref('')
const logKeyword = ref('')
const logLimit = ref(200)
const logContainers = ref([])
const serverLogs = ref([])
const logEnabled = ref(true)
const logError = ref('')
const loadingLogs = ref(false)
const logLevels = ['error', 'warn', 'info', 'debug', 'unknown']

// Chart refs for server detail
const cpuChartRef = ref(null)
const memoryChartRef = ref(null)
const networkChartRef = ref(null)
const diskChartRef = ref(null)
let cpuChart = null
let memoryChart = null
let networkChart = null
let diskChart = null

// 概览大屏图表（服务器健康分布环形图）
const healthChartRef = ref(null)
let healthChart = null
// 缓存最近一次服务器指标，供主题切换时重绘图表
let lastMetrics = {}

let timer = null

const timeRanges = [
  { label: '1h', full: '最近 1 小时', value: '1h' },
  { label: '6h', full: '最近 6 小时', value: '6h' },
  { label: '24h', full: '最近 24 小时', value: '24h' },
  { label: '7d', full: '最近 7 天', value: '7d' }
]

// ===== 计算属性 =====
const lastUpdatedText = computed(() => {
  const d = lastUpdated.value
  if (!d) return ''
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
})

// ===== 全局概览大屏数据 =====
const ov = computed(() => overview.value || {})
const thr = computed(() => ov.value.thresholds || { cpu: 80, memory: 80, disk: 90 })
const topRisk = computed(() => ov.value.top_risk || [])
const alertItems = computed(() => ov.value.alerts?.items || [])
const alertSev = computed(() => ov.value.alerts?.by_severity || {})

// 服务器健康分布（分母 = 全部纳管服务器）
const healthItems = computed(() => {
  const o = ov.value
  const total = o.total_servers || 0
  const p = chartPalette()
  const mk = (key, label, count, color) => ({
    key, label, color,
    count: count || 0,
    pct: total ? Math.round((count || 0) / total * 100) : 0
  })
  return [
    mk('normal', '正常', o.normal, p.statusNormal),
    mk('abnormal', '异常', o.abnormal, p.statusDanger),
    mk('nodata', '无数据', o.nodata, p.statusWarn)
  ]
})

const kpiCards = computed(() => {
  const o = ov.value
  const alertsAvailable = o.alerts ? o.alerts.available !== false : true
  const alertCount = alertsAvailable ? (o.alerts?.open_total ?? 0) : null
  const risk = o.resource_risk || 0
  const coverage = o.total_servers ? Math.round((o.data_servers || 0) / o.total_servers * 100) : 0
  return [
    {
      key: 'servers', label: '纳管服务器', display: o.total_servers ?? 0,
      color: 'var(--mon-accent)', bg: 'var(--app-panel-soft)', icon: Platform,
      sub: `有监控数据 ${o.data_servers ?? 0} 台`, badge: null, badgeClass: '',
      action: () => gotoServers()
    },
    {
      key: 'data', label: '有监控数据', display: o.data_servers ?? 0,
      color: 'var(--mon-success)', bg: 'var(--mon-success-soft)', icon: Odometer,
      sub: o.total_servers ? `覆盖率 ${coverage}%` : '暂无纳管服务器',
      badge: null, badgeClass: '', action: () => gotoCategory('hasdata')
    },
    {
      key: 'risk', label: '资源风险', display: risk,
      color: risk > 0 ? 'var(--mon-danger)' : 'var(--mon-success)',
      bg: risk > 0 ? 'var(--mon-danger-soft)' : 'var(--mon-success-soft)',
      icon: Warning,
      sub: `正常 ${o.normal ?? 0} · 无数据 ${o.nodata ?? 0}`,
      badge: risk > 0 ? '需关注' : '正常', badgeClass: risk > 0 ? 'badge-warn' : 'badge-ok',
      action: () => gotoCategory('abnormal')
    },
    {
      key: 'alerts', label: '活跃告警',
      display: alertCount === null ? '不可用' : alertCount,
      color: alertCount === null ? 'var(--app-text-3)' : alertCount > 5 ? 'var(--mon-danger)' : alertCount > 0 ? 'var(--mon-warn)' : 'var(--mon-success)',
      bg: alertCount === null ? 'var(--app-panel-soft)'
        : alertCount > 5 ? 'var(--mon-danger-soft)' : alertCount > 0 ? 'var(--mon-warn-soft)' : 'var(--mon-success-soft)',
      icon: Bell,
      sub: alertCount === null
        ? '告警源不可用'
        : `严重 ${o.alerts?.by_severity?.critical || 0} · 警告 ${o.alerts?.by_severity?.warning || 0}`,
      badge: null, badgeClass: '',
      action: (alertCount === null || !canViewAlerts.value) ? null : () => goOpenAlerts()
    }
  ]
})

// ===== 方法 =====
const statusLabel = (st) => ({
  RUNNING: '运行中',
  COMPLETED: '已完成',
  INACTIVE: '未启用/已停止',
  STOPPED: '已停止',
  PARTIAL: '部分运行',
  ERROR: '异常',
  FAILED: '异常',
  UNKNOWN: '未知',
}[st] || st || '未知')
const cpuCls = (v) => v > 80 ? 'val-danger' : v > 50 ? 'val-warning' : ''

const fmtPct = (v) => (v == null ? '-' : Number(v).toFixed(1))
const barW = (v) => Math.min(100, Math.max(0, Number(v) || 0)) + '%'
const alertStatusLabel = (s) => ({ ACTIVE: '活动', CONFIRMED: '已确认', RECOVERED: '已恢复' }[s] || s || '-')

const formatRelativeTime = (t) => {
  if (!t) return '-'
  const diff = (Date.now() - new Date(t).getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff/60) + '分钟前'
  if (diff < 86400) return Math.floor(diff/3600) + '小时前'
  return Math.floor(diff/86400) + '天前'
}

// 概览 KPI + 活跃告警（均由 /api/monitor/overview 一次性返回）
const loadOverviewKpi = async () => {
  try {
    const res = await axios.get('/api/monitor/overview')
    overview.value = res.data?.data || {}
  } catch (e) {
    console.error('加载概览数据失败:', e)
  }
}

const loadData = async () => {
  await loadOverviewKpi()
  lastUpdated.value = new Date()
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

// ===== 服务器卡片展示 =====
// 三项百分比指标（CPU/内存/磁盘），统一按百分比阈值着色
const srvMetrics = (s) => [
  { key: 'cpu', label: 'CPU', value: (s.cpu_percent || 0).toFixed(1) + '%', width: Math.min(100, s.cpu_percent || 0), cls: cpuCls(s.cpu_percent) },
  { key: 'mem', label: '内存', value: (s.memory_percent || 0).toFixed(1) + '%', width: Math.min(100, s.memory_percent || 0), cls: cpuCls(s.memory_percent) },
  { key: 'disk', label: '磁盘', value: (s.disk_usage_percent || 0).toFixed(1) + '%', width: Math.min(100, s.disk_usage_percent || 0), cls: cpuCls(s.disk_usage_percent) }
]

// 负载等级取 CPU/内存/磁盘三项最差者
const srvWorst = (s) => Math.max(s.cpu_percent || 0, s.memory_percent || 0, s.disk_usage_percent || 0)
const srvStatusCls = (s) => {
  if (!s.has_data) return 'nodata'
  const m = srvWorst(s)
  return m > 80 ? 'danger' : m > 60 ? 'warning' : 'ok'
}
const srvStatusText = (s) => {
  if (!s.has_data) return '无数据'
  const m = srvWorst(s)
  return m > 80 ? '高负载' : m > 60 ? '中负载' : '正常'
}

// 状态分组：沿用现有卡片状态逻辑（nodata / danger / warning / ok），不新增判定规则
// 「异常」= 有数据且负载非正常（danger/warning）；「正常」= ok；「无数据」= nodata
const SRV_GROUP_RANK = { abnormal: 0, normal: 1, nodata: 2 }
const srvName = (s) => s.hostname || s.ip || ''

// 资源风险判定与概览一致：有数据且任一指标超过监控阈值（阈值来自后端配置）
const srvOverThreshold = (s) => !!s.has_data && (
  (s.cpu_percent || 0) > thr.value.cpu ||
  (s.memory_percent || 0) > thr.value.memory ||
  (s.disk_usage_percent || 0) > thr.value.disk
)

// 筛选分组：与概览「正常 / 异常 / 无数据 / 有监控数据」口径一一对应
const srvFilterGroup = (s) => {
  if (!s.has_data) return 'nodata'
  return srvOverThreshold(s) ? 'abnormal' : 'normal'
}

// 搜索 + 状态筛选：纯前端处理，复用已加载的 serverList，不触发额外请求
const filteredServers = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  const f = statusFilter.value
  const list = serverList.value.filter(s => {
    if (f === 'hasdata' && !s.has_data) return false
    if (f !== 'all' && f !== 'hasdata' && srvFilterGroup(s) !== f) return false
    if (kw && !`${s.hostname || ''} ${s.ip || ''}`.toLowerCase().includes(kw)) return false
    return true
  })
  // 默认优先展示异常主机，其余按主机名排序
  return [...list].sort((a, b) => {
    const ra = SRV_GROUP_RANK[srvFilterGroup(a)] ?? 9
    const rb = SRV_GROUP_RANK[srvFilterGroup(b)] ?? 9
    if (ra !== rb) return ra - rb
    return srvName(a).localeCompare(srvName(b), 'zh-Hans-CN', { numeric: true, sensitivity: 'base' })
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredServers.value.length / pageSize.value)))
const pagedServers = computed(() => {
  const page = Math.min(Math.max(1, currentPage.value), totalPages.value)
  const start = (page - 1) * pageSize.value
  return filteredServers.value.slice(start, start + pageSize.value)
})

// 搜索 / 筛选 / 每页条数变化时回到第 1 页；结果变少时收敛页码
watch([searchKeyword, statusFilter, pageSize], () => { currentPage.value = 1 })
watch(totalPages, (tp) => { if (currentPage.value > tp) currentPage.value = tp })

// ===== 服务器日志（Loki）=====
const fmtLogTime = (ts) => {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

const resetServerLogs = () => {
  logRange.value = '1h'
  logContainer.value = ''
  logLevel.value = ''
  logKeyword.value = ''
  logLimit.value = 200
  logContainers.value = []
  serverLogs.value = []
  logError.value = ''
  logEnabled.value = true
}

const loadServerLogs = async () => {
  if (!selectedServer.value) return
  loadingLogs.value = true
  try {
    const res = await axios.get(`/api/monitor/server/${selectedServer.value.id}/logs`, {
      params: {
        range: logRange.value,
        container: logContainer.value,
        level: logLevel.value,
        keyword: logKeyword.value,
        limit: logLimit.value
      }
    })
    const d = res.data?.data || {}
    logEnabled.value = d.enabled !== false
    logError.value = d.error || ''
    logContainers.value = d.containers || []
    serverLogs.value = d.logs || []
  } catch (e) {
    // 403（缺少 log:view）或 404（无该服务器数据权限）等
    logEnabled.value = true
    logError.value = e?.response?.data?.message || e?.response?.data?.detail || e?.message || '请求失败'
    logContainers.value = []
    serverLogs.value = []
  } finally {
    loadingLogs.value = false
  }
}

const selectServer = async (srv) => {
  selectedServer.value = srv
  resetServerLogs()
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
  await loadServerLogs()
}

// ECharts 实例与 DOM 绑定：Tab 切换或重新选择服务器后 DOM 会重建，
// 旧实例仍指向已移除的节点，会导致图表空白，检测到 DOM 变化时重建实例。
const ensureChart = (inst, el) => {
  if (inst && inst.getDom() !== el) {
    inst.dispose()
    inst = null
  }
  return inst || echarts.init(el)
}

const disposeServerCharts = () => {
  const charts = [cpuChart, memoryChart, networkChart, diskChart]
  charts.forEach(c => c?.dispose())
  cpuChart = memoryChart = networkChart = diskChart = null
}

const closeServerDetail = () => {
  selectedServer.value = null
  serverServices.value = []
  resetServerLogs()
  disposeServerCharts()
}

// ECharts 主题 palette：浅色模式用浅色底可读的配色，深色模式沿用原深色大屏配色
const chartPalette = () => themeStore.theme === 'dark'
  ? {
      axisText: '#94a3b8', axisLine: 'rgba(148,163,184,.28)', splitLine: 'rgba(148,163,184,.12)',
      tooltipBg: '#16202f', tooltipBorder: 'rgba(148,163,184,.2)', tooltipText: '#e2e8f0',
      legend: '#94a3b8',
      cpu: '#3b82f6', cpuArea: 'rgba(59,130,246,0.12)',
      mem: '#a78bfa', memArea: 'rgba(167,139,250,0.12)',
      rx: '#22c55e', rxArea: 'rgba(34,197,94,0.12)',
      tx: '#f59e0b', txArea: 'rgba(245,158,11,0.12)',
      disk: '#f87171', diskArea: 'rgba(248,113,113,0.12)',
      donutBorder: '#111c2e', donutEmpty: '#334155', donutText: '#e2e8f0', donutSub: '#94a3b8',
      statusNormal: '#22c55e', statusDanger: '#ef4444', statusWarn: '#f59e0b'
    }
  : {
      axisText: '#64748b', axisLine: '#cbd5e1', splitLine: '#eef2f7',
      tooltipBg: '#ffffff', tooltipBorder: '#e2e8f0', tooltipText: '#1e293b',
      legend: '#64748b',
      cpu: '#2563eb', cpuArea: 'rgba(37,99,235,0.10)',
      mem: '#7c3aed', memArea: 'rgba(124,58,237,0.10)',
      rx: '#16a34a', rxArea: 'rgba(22,163,74,0.10)',
      tx: '#d97706', txArea: 'rgba(217,119,6,0.10)',
      disk: '#dc2626', diskArea: 'rgba(220,38,38,0.10)',
      donutBorder: '#ffffff', donutEmpty: '#e2e8f0', donutText: '#1e293b', donutSub: '#64748b',
      statusNormal: '#16a34a', statusDanger: '#dc2626', statusWarn: '#d97706'
    }

const chartAxis = (p, opts = {}) => ({
  axisLabel: { color: p.axisText },
  axisLine: { lineStyle: { color: p.axisLine } },
  splitLine: { lineStyle: { color: p.splitLine } },
  nameTextStyle: { color: p.axisText },
  ...opts
})

const chartTooltip = (p, extra = {}) => ({
  backgroundColor: p.tooltipBg,
  borderColor: p.tooltipBorder,
  textStyle: { color: p.tooltipText },
  ...extra
})

const renderServerCharts = (metrics) => {
  // 缓存最近一次指标，供主题切换时重绘
  lastMetrics = metrics || {}
  const p = chartPalette()

  // CPU Chart
  if (cpuChartRef.value) {
    cpuChart = ensureChart(cpuChart, cpuChartRef.value)
    cpuChart.setOption({
      tooltip: chartTooltip(p, { trigger: 'axis', formatter: '{b}<br/>CPU: {c}%' }),
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: chartAxis(p, { type: 'category', boundaryGap: false,
        data: (metrics.cpu || []).map(d => new Date(d[0] * 1000).toLocaleTimeString())
      }),
      yAxis: chartAxis(p, { type: 'value', min: 0, max: 100, name: '%' }),
      series: [{
        type: 'line', smooth: true, showSymbol: false,
        data: (metrics.cpu || []).map(d => d[1]),
        lineStyle: { color: p.cpu, width: 2 },
        areaStyle: { color: p.cpuArea }
      }]
    })
  }
  
  // Memory Chart
  if (memoryChartRef.value) {
    memoryChart = ensureChart(memoryChart, memoryChartRef.value)
    memoryChart.setOption({
      tooltip: chartTooltip(p, { trigger: 'axis', formatter: '{b}<br/>内存: {c}%' }),
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: chartAxis(p, { type: 'category', boundaryGap: false,
        data: (metrics.memory || []).map(d => new Date(d[0] * 1000).toLocaleTimeString())
      }),
      yAxis: chartAxis(p, { type: 'value', min: 0, max: 100, name: '%' }),
      series: [{
        type: 'line', smooth: true, showSymbol: false,
        data: (metrics.memory || []).map(d => d[1]),
        lineStyle: { color: p.mem, width: 2 },
        areaStyle: { color: p.memArea }
      }]
    })
  }
  
  // Network Chart（入站/出站真实历史速率，单位 MB/s）
  if (networkChartRef.value) {
    networkChart = ensureChart(networkChart, networkChartRef.value)
    networkChart.setOption({
      tooltip: chartTooltip(p, { trigger: 'axis', formatter: '{b}<br/>入站: {c[0]} MB/s<br/>出站: {c[1]} MB/s' }),
      legend: { data: ['入站', '出站'], textStyle: { color: p.legend }, top: 0, right: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      xAxis: chartAxis(p, { type: 'category', boundaryGap: false,
        data: (metrics.network_rx || []).map(d => new Date(d[0] * 1000).toLocaleTimeString())
      }),
      yAxis: chartAxis(p, { type: 'value', min: 0, name: 'MB/s' }),
      series: [
        {
          name: '入站', type: 'line', smooth: true, showSymbol: false,
          data: (metrics.network_rx || []).map(d => d[1]),
          lineStyle: { color: p.rx, width: 2 },
          areaStyle: { color: p.rxArea }
        },
        {
          name: '出站', type: 'line', smooth: true, showSymbol: false,
          data: (metrics.network_tx || []).map(d => d[1]),
          lineStyle: { color: p.tx, width: 2 },
          areaStyle: { color: p.txArea }
        }
      ]
    })
  }
  
  // Disk Chart
  if (diskChartRef.value) {
    diskChart = ensureChart(diskChart, diskChartRef.value)
    diskChart.setOption({
      tooltip: chartTooltip(p, { trigger: 'axis', formatter: '{b}<br/>磁盘: {c}%' }),
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: chartAxis(p, { type: 'category', boundaryGap: false,
        data: (metrics.disk || []).map(d => new Date(d[0] * 1000).toLocaleTimeString())
      }),
      yAxis: chartAxis(p, { type: 'value', min: 0, max: 100, name: '%' }),
      series: [{
        type: 'line', smooth: true, showSymbol: false,
        data: (metrics.disk || []).map(d => d[1]),
        lineStyle: { color: p.disk, width: 2 },
        areaStyle: { color: p.diskArea }
      }]
    })
  }
}

const refreshAll = async () => {
  isRefreshing.value = true
  // KPI 卡片在所有 Tab 都可见，始终刷新；其余数据只刷新当前 Tab 用到的部分
  await loadOverviewKpi()
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
      await loadServerLogs()
    }
  } else {
    await nextTick()
    renderHealthChart()
  }
  lastUpdated.value = new Date()
  setTimeout(() => { isRefreshing.value = false }, 500)
}

// ===== 概览大屏联动 =====
const ensureServerList = async () => {
  if (!serverList.value.length) await loadServerList()
}

// 点击风险条目：切到「服务器监控」并定位详情（复用 selectServer）
const gotoServer = async (serverId) => {
  if (serverId == null) return
  await ensureServerList()
  const srv = serverList.value.find(s => s.id === serverId)
  activeTab.value = 'servers'
  if (srv) { await nextTick(); await selectServer(srv) }
}

// 点击健康分布分类：切到「服务器监控」并定位该分类下的首台服务器
const gotoCategory = async (kind) => {
  await ensureServerList()
  const preds = {
    abnormal: srvOverThreshold,
    nodata: (s) => !s.has_data,
    hasdata: (s) => !!s.has_data,
    normal: (s) => s.has_data && !srvOverThreshold(s)
  }
  const pred = preds[kind] || preds.normal
  // 关键：同步把列表筛到该分类，避免只定位详情而列表仍显示全部服务器
  searchKeyword.value = ''
  statusFilter.value = kind in preds ? kind : 'all'
  currentPage.value = 1
  activeTab.value = 'servers'
  const srv = serverList.value.find(pred)
  if (srv) { await nextTick(); await selectServer(srv) }
}

// 概览 → 服务器监控：清空搜索与状态筛选，展示全部服务器
const gotoServers = () => {
  searchKeyword.value = ''
  statusFilter.value = 'all'
  currentPage.value = 1
  activeTab.value = 'servers'
}

// 概览 → 告警中心：活跃 = ACTIVE + CONFIRMED（后端 status 仅支持单值，由告警页合并查询）
const goOpenAlerts = (extra = {}) => {
  if (!canViewAlerts.value) return
  router.push({ path: '/alerts', query: { status: 'OPEN', ...extra } })
}

// 概览 → 告警详情：携带 alert_id，由告警中心加载后定位并打开详情
const goAlertDetail = (a) => {
  if (!canViewAlerts.value || a?.id == null) return
  router.push({ path: '/alerts', query: { status: 'OPEN', alert_id: String(a.id) } })
}

// ===== 概览大屏：服务器健康分布环形图（中心显示纳管总数） =====
const renderHealthChart = () => {
  if (!healthChartRef.value) return
  healthChart = ensureChart(healthChart, healthChartRef.value)
  if (!healthChart) return
  const items = healthItems.value.filter(i => i.count > 0)
  const total = ov.value.total_servers || 0
  const p = chartPalette()
  healthChart.setOption({
    tooltip: chartTooltip(p, { trigger: 'item', formatter: '{b}: {c} 台 ({d}%)' }),
    title: {
      text: String(total), subtext: '纳管服务器', left: 'center', top: '40%',
      textStyle: { color: p.donutText, fontSize: 30, fontWeight: 700 },
      subtextStyle: { color: p.donutSub, fontSize: 12 }
    },
    series: [{
      type: 'pie', radius: ['60%', '84%'], center: ['50%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderColor: p.donutBorder, borderWidth: 2 },
      label: { show: false }, labelLine: { show: false },
      data: items.length
        ? items.map(i => ({ name: i.label, value: i.count, itemStyle: { color: i.color } }))
        : [{ name: '暂无数据', value: 1, itemStyle: { color: p.donutEmpty }, tooltip: { show: false }, silent: true }]
    }]
  }, true)
  healthChart.off('click')
  healthChart.on('click', (p) => {
    const map = { 正常: 'normal', 异常: 'abnormal', 无数据: 'nodata' }
    if (map[p.name]) gotoCategory(map[p.name])
  })
}

const disposeHealthChart = () => { healthChart?.dispose(); healthChart = null }

// Watch autoRefresh
watch(autoRefresh, (v) => {
  if (v) {
    timer = setInterval(refreshAll, REFRESH_INTERVAL)
  } else {
    clearInterval(timer); timer = null
  }
})

// Watch tab switch
watch(activeTab, async (tab) => {
  if (tab === 'servers') {
    // 服务器列表按需加载，避免首次进入页面就等待全量服务器指标
    if (serverList.value.length === 0) loadServerList()
  } else {
    await nextTick()
    renderHealthChart()
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

// Watch theme change - ECharts 颜色不随 CSS 变量自动更新，需按当前主题重绘
watch(() => themeStore.theme, async () => {
  await nextTick()
  if (activeTab.value === 'overview') {
    renderHealthChart()
  } else if (selectedServer.value) {
    renderServerCharts(lastMetrics)
  }
})

const onResize = () => {
  healthChart?.resize()
  cpuChart?.resize(); memoryChart?.resize(); networkChart?.resize(); diskChart?.resize()
}

onMounted(async () => {
  loading.value = true
  // 仅加载概览数据即可结束首屏加载，服务器列表在切换到「服务器监控」时按需加载
  await loadData()
  await nextTick()
  renderHealthChart()
  loading.value = false
  if (autoRefresh.value) timer = setInterval(refreshAll, REFRESH_INTERVAL)
  window.addEventListener('resize', onResize)

  // 从服务器管理页跳转而来：定位到指定服务器详情
  const targetId = Number(route.query.server_id)
  if (targetId) {
    await ensureServerList()
    const target = serverList.value.find(s => Number(s.id) === targetId)
    if (target) {
      activeTab.value = 'servers'
      await nextTick()
      await selectServer(target)
    }
  }
})

onUnmounted(() => {
  clearInterval(timer)
  window.removeEventListener('resize', onResize)
  disposeHealthChart()
  disposeServerCharts()
})
</script>

<style scoped>
/* ===== Base ===== */
.monitoring-page {
  padding: 24px 28px;
  background: #f5f7fa; /* 浅色中性底，去除原有偏蓝灰 */
  min-height: calc(100vh - 60px);
  /* 监控中心语义色（浅色默认，与其余管理页面风格一致） */
  --mon-accent: #0284c7;
  --mon-accent-text: #0369a1;
  --mon-accent-soft: rgba(2,132,199,.1);
  --mon-accent-border: rgba(2,132,199,.35);
  --mon-success: #16a34a;
  --mon-success-text: #15803d;
  --mon-success-soft: rgba(22,163,74,.12);
  --mon-success-border: rgba(22,163,74,.35);
  --mon-danger: #dc2626;
  --mon-danger-text: #b91c1c;
  --mon-danger-soft: rgba(220,38,38,.1);
  --mon-danger-border: rgba(220,38,38,.32);
  --mon-warn: #d97706;
  --mon-warn-text: #b45309;
  --mon-warn-soft: rgba(217,119,6,.12);
  --mon-warn-border: rgba(217,119,6,.35);
  --mon-cpu: #2563eb;
  --mon-mem: #7c3aed;
  --mon-track: #e2e8f0;
  --mon-log-bg: #f8fafc;
}
/* 深色模式：沿用原有深色大屏配色 */
html.dark .monitoring-page {
  background: var(--app-bg); /* 深色沿用原有大屏底色 */
  --mon-accent: #38bdf8;
  --mon-accent-text: #7dd3fc;
  --mon-accent-soft: rgba(56,189,248,.14);
  --mon-accent-border: rgba(56,189,248,.4);
  --mon-success: #22c55e;
  --mon-success-text: #4ade80;
  --mon-success-soft: rgba(34,197,94,.14);
  --mon-success-border: rgba(34,197,94,.24);
  --mon-danger: #ef4444;
  --mon-danger-text: #f87171;
  --mon-danger-soft: rgba(239,68,68,.14);
  --mon-danger-border: rgba(239,68,68,.28);
  --mon-warn: #f59e0b;
  --mon-warn-text: #fcd34d;
  --mon-warn-soft: rgba(245,158,11,.14);
  --mon-warn-border: rgba(245,158,11,.42);
  --mon-cpu: #3b82f6;
  --mon-mem: #a78bfa;
  --mon-track: rgba(148,163,184,.16);
  --mon-log-bg: #0a0f1c;
}

/* ===== Header ===== */
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.header-title-row { display: flex; align-items: center; gap: 10px; }
.header-title-row h1 { font-size: 22px; font-weight: 700; color: var(--app-text); margin: 0; }
.live-badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; color: var(--mon-success-text); background: var(--mon-success-soft); border: 1px solid var(--mon-success-border); letter-spacing: .5px; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--mon-success); animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1;box-shadow:0 0 0 0 var(--mon-success-border)} 50%{opacity:.7;box-shadow:0 0 0 4px rgba(34,197,94,0)} }
.subtitle { font-size: 13px; color: var(--app-text-3); margin: 4px 0 0; }
.header-right { display: flex; align-items: center; gap: 14px; }
.time-range-selector { display: flex; background: var(--app-panel-soft); border: 1px solid var(--app-border); border-radius: 8px; padding: 3px; }
.time-opt { padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; color: var(--app-text-3); cursor: pointer; transition: all .2s; }
.time-opt.active { background: var(--mon-accent-soft); color: var(--mon-accent-text); }
.auto-refresh-toggle { display: flex; align-items: center; gap: 8px; padding: 5px 12px; border-radius: 8px; font-size: 12px; color: var(--app-text-3); cursor: pointer; border: 1px solid var(--app-border); background: var(--app-panel-soft); transition: all .2s; user-select: none; }
.auto-refresh-toggle:hover { border-color: var(--mon-accent-border); }
.toggle-dot { width: 28px; height: 16px; border-radius: 8px; background: var(--mon-track); position: relative; transition: background .2s; }
.toggle-dot.on { background: var(--mon-success); }
.toggle-dot::after { content: ''; position: absolute; top: 2px; left: 2px; width: 12px; height: 12px; border-radius: 50%; background: #fff; transition: transform .2s; }
.toggle-dot.on::after { transform: translateX(12px); }
.refresh-btn { width: 34px; height: 34px; border-radius: 8px; border: 1px solid var(--app-border); background: var(--app-panel-soft); display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--app-text-3); transition: all .2s; }
.refresh-btn:hover { border-color: var(--mon-accent); color: var(--mon-accent-text); }
.refresh-btn.spinning { animation: spin .6s linear; }
.last-updated { font-size: 12px; color: var(--app-text-3); white-space: nowrap; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ===== KPI Grid ===== */
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.kpi-card { background: var(--app-panel); border-radius: 12px; border: 1px solid var(--app-border); padding: 18px 20px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; transition: all .2s; }
.kpi-card.clickable { cursor: pointer; }
.kpi-card:hover { border-color: var(--mon-accent-border); box-shadow: 0 6px 20px var(--app-shadow); }
.kpi-icon-wrap { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.kpi-body { flex: 1; min-width: 0; }
.kpi-label { font-size: 12px; color: var(--app-text-3); font-weight: 500; margin-bottom: 4px; }
.kpi-value { font-size: 26px; font-weight: 800; line-height: 1; letter-spacing: -.5px; }
.kpi-footer { width: 100%; display: flex; justify-content: space-between; align-items: center; padding-top: 10px; border-top: 1px solid var(--app-border); }
.kpi-sub { font-size: 11px; color: var(--app-text-3); }
.kpi-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; }
.badge-ok { background: var(--mon-success-soft); color: var(--mon-success-text); }
.badge-warn { background: var(--mon-danger-soft); color: var(--mon-danger-text); }

/* ===== 概览大屏（深色运维风格） ===== */
.screen { display: flex; flex-direction: column; gap: 16px; }
.screen-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.screen-panel { background: var(--app-panel); border: 1px solid var(--app-border); border-radius: 14px; padding: 18px 20px; display: flex; flex-direction: column; }
/* 深色模式保留原有蓝色光晕装饰 */
html.dark .screen-panel { background: radial-gradient(circle at 18% 0%, var(--mon-accent-soft), transparent 58%), var(--app-panel); }
.screen-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 14px; }
.screen-title { font-size: 15px; font-weight: 700; color: var(--app-text); letter-spacing: .3px; }
.screen-sub { font-size: 11px; color: var(--app-text-3); margin-top: 4px; }
.screen-total { font-size: 12px; font-weight: 600; color: var(--app-text-2); background: var(--app-panel-soft); border: 1px solid var(--app-border); padding: 4px 10px; border-radius: 20px; white-space: nowrap; }
.screen-total.danger { color: var(--mon-danger-text); background: var(--mon-danger-soft); border-color: var(--mon-danger-border); }
.screen-body { flex: 1; min-height: 0; }
.screen-empty { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 40px 16px; font-size: 13px; color: var(--app-text-3); text-align: center; }
.screen-empty.warn { color: var(--mon-warn-text); }

/* 服务器健康分布环形图 */
.donut-body { display: flex; align-items: center; gap: 16px; }
.donut-chart { width: 200px; height: 200px; flex-shrink: 0; }
.donut-legend { flex: 1; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.dl-row { display: flex; align-items: center; gap: 10px; width: 100%; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--app-border); background: var(--app-panel-soft); cursor: pointer; transition: all .15s; text-align: left; }
.dl-row:hover { border-color: var(--mon-accent-border); background: var(--mon-accent-soft); }
.dl-row.dim { opacity: .5; }
.dl-row.highlight { border-color: var(--mon-warn-border); background: var(--mon-warn-soft); }
.dl-dot { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
.dl-label { font-size: 13px; color: var(--app-text-2); font-weight: 500; flex: 1; }
.dl-count { font-size: 18px; font-weight: 800; color: var(--app-text); font-family: 'SF Mono',Monaco,monospace; }
.dl-count small { font-size: 11px; color: var(--app-text-3); margin-left: 2px; font-weight: 600; }
.dl-pct { font-size: 12px; color: var(--app-text-3); width: 44px; text-align: right; font-family: 'SF Mono',Monaco,monospace; }

/* 资源风险 TOP5 横向条形 */
.risk-list { display: flex; flex-direction: column; gap: 10px; }
.risk-row { display: flex; align-items: flex-start; gap: 12px; width: 100%; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--app-border); background: var(--app-panel-soft); cursor: pointer; transition: all .15s; text-align: left; }
.risk-row:hover { border-color: var(--mon-accent-border); background: var(--mon-accent-soft); }
.rk-rank { width: 22px; height: 22px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800; color: var(--app-text-3); background: var(--app-panel-soft); flex-shrink: 0; }
.rk-rank.danger { color: var(--mon-danger-text); background: var(--mon-danger-soft); }
.rk-main { flex: 1; min-width: 0; }
.rk-top { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; }
.rk-name { font-size: 13px; font-weight: 600; color: var(--app-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 52%; }
.rk-metric { font-size: 11px; color: var(--app-text-2); background: var(--app-panel); border: 1px solid var(--app-border); padding: 1px 7px; border-radius: 4px; flex-shrink: 0; }
.rk-val { margin-left: auto; font-size: 15px; font-weight: 800; color: var(--app-text); font-family: 'SF Mono',Monaco,monospace; }
.rk-val.danger { color: var(--mon-danger-text); }
.rk-bar { position: relative; height: 8px; border-radius: 4px; background: var(--app-border); }
.rk-fill { height: 100%; border-radius: 4px; background: var(--mon-accent); transition: width .5s ease; }
.rk-fill.danger { background: var(--mon-danger); }
.rk-thr-line { position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--app-border-strong); border-radius: 1px; }
.rk-foot { display: flex; justify-content: space-between; margin-top: 5px; }
.rk-ip { font-size: 11px; color: var(--app-text-3); font-family: 'SF Mono',Monaco,monospace; }
.rk-threshold { font-size: 11px; color: var(--app-text-3); }

/* 活跃告警 */
.alert-head-right { display: flex; align-items: center; gap: 8px; }
.screen-total.clickable { font-family: inherit; cursor: pointer; transition: color .2s, border-color .2s; }
.screen-total.clickable:hover { color: var(--mon-accent); border-color: var(--mon-accent); }
.sev-chip.clickable { cursor: pointer; transition: filter .2s; }
.sev-chip.clickable:hover { filter: brightness(1.08); }
.screen-link { font-size: 12px; font-weight: 600; color: var(--mon-accent); cursor: pointer; }
.screen-link:hover { text-decoration: underline; }
.alert-item.clickable { cursor: pointer; transition: background .2s, border-color .2s; }
.alert-item.clickable:hover { background: var(--app-hover); border-color: var(--mon-accent); }
.sev-chip { font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 20px; }
.sev-chip.critical { color: var(--mon-danger-text); background: var(--mon-danger-soft); }
.sev-chip.warning { color: var(--mon-warn-text); background: var(--mon-warn-soft); }
.alert-rows { display: flex; flex-direction: column; gap: 8px; max-height: 320px; overflow-y: auto; }
.alert-item { display: flex; gap: 12px; padding: 12px 14px; border-radius: 10px; background: var(--app-panel-soft); border: 1px solid var(--app-border); }
.ai-sev-bar { width: 3px; border-radius: 2px; flex-shrink: 0; background: var(--app-text-3); }
.alert-item.critical .ai-sev-bar { background: var(--mon-danger); }
.alert-item.warning .ai-sev-bar { background: var(--mon-warn); }
.ai-main { flex: 1; min-width: 0; }
.ai-top { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.ai-title { font-size: 13px; font-weight: 600; color: var(--app-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ai-st { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px; flex-shrink: 0; background: var(--app-panel-soft); color: var(--app-text-2); }
.ai-st.ACTIVE { background: var(--mon-danger-soft); color: var(--mon-danger-text); }
.ai-st.CONFIRMED { background: var(--mon-warn-soft); color: var(--mon-warn-text); }
.ai-time { font-size: 11px; color: var(--app-text-3); margin-left: auto; flex-shrink: 0; }
.ai-sub { font-size: 11px; color: var(--app-text-3); }
.ai-content { font-size: 12px; color: var(--app-text-2); margin-top: 4px; line-height: 1.5; word-break: break-word; }

/* ===== Tab Bar ===== */
.tab-bar { display: flex; gap: 8px; margin-bottom: 16px; padding: 0 4px; }
.tab-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--app-border); background: var(--app-panel); cursor: pointer; font-size: 13px; color: var(--app-text-3); transition: all .2s; }
.tab-btn:hover { border-color: var(--mon-accent-border); color: var(--mon-accent-text); }
.tab-btn.active { background: var(--mon-accent-soft); border-color: var(--mon-accent); color: var(--mon-accent-text); font-weight: 600; }
.tab-content { animation: fadeIn .3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

/* ===== Server Grid ===== */
.server-grid { min-height: 200px; }
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 20px; color: var(--app-text-3); text-align: center; }
.empty-state p { margin-top: 12px; font-size: 14px; }
.server-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.server-card { background: var(--app-panel); border-radius: 12px; border: 1px solid var(--app-border); padding: 16px 18px; cursor: pointer; transition: all .2s; }
.server-card:hover { border-color: var(--mon-accent-border); box-shadow: 0 6px 18px var(--app-shadow); }
.server-card.selected { border-color: var(--mon-accent); box-shadow: 0 0 0 3px var(--mon-accent-soft); }
.sc-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid var(--app-border); }
.sc-info { min-width: 0; }
.sc-info h3 { font-size: 15px; font-weight: 700; color: var(--app-text); margin: 0 0 3px; line-height: 1.3; word-break: break-all; }
.sc-ip { font-size: 12px; color: var(--app-text-3); font-family: 'SF Mono',Monaco,monospace; }
.sc-status { font-size: 11px; padding: 3px 9px; border-radius: 12px; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
.sc-status.ok { background: var(--mon-success-soft); color: var(--mon-success-text); }
.sc-status.warning { background: var(--mon-warn-soft); color: var(--mon-warn-text); }
.sc-status.danger { background: var(--mon-danger-soft); color: var(--mon-danger-text); }
.sc-status.nodata { background: var(--app-panel-soft); color: var(--app-text-3); }
.sc-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.sc-metric { min-width: 0; }
.sc-m-row { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; margin-bottom: 5px; }
.sc-m-label { font-size: 11px; color: var(--app-text-3); font-weight: 500; }
.sc-m-val { font-size: 13px; font-weight: 700; color: var(--app-text); font-family: 'SF Mono',Monaco,monospace; }
.sc-m-val.net { font-size: 12px; font-weight: 600; color: var(--app-text-3); }
.sc-bar { height: 5px; background: var(--app-border); border-radius: 3px; overflow: hidden; }
.sc-bar-fill { height: 100%; border-radius: 3px; transition: width .4s; }
.sc-bar-fill.cpu { background: var(--mon-cpu); }
.sc-bar-fill.mem { background: var(--mon-mem); }
.sc-bar-fill.disk { background: var(--mon-warn); }
.sc-net { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--app-border); }
.sc-nodata { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 16px 0; font-size: 12px; color: var(--app-text-3); }

/* ===== Server Toolbar / View / Pager ===== */
.server-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 14px; }
.srv-search { width: 240px; }
.srv-filter { width: 120px; }
.srv-view-toggle { display: inline-flex; padding: 2px; background: var(--app-panel-soft); border: 1px solid var(--app-border); border-radius: 8px; }
.vt-btn { border: none; background: transparent; padding: 5px 14px; font-size: 12px; font-weight: 600; color: var(--app-text-2); border-radius: 6px; cursor: pointer; transition: all .2s; }
.vt-btn:hover { color: var(--mon-accent-text); }
.vt-btn.active { background: var(--app-panel); color: var(--mon-accent-text); box-shadow: 0 1px 3px var(--app-shadow); }
.srv-count { margin-left: auto; font-size: 12px; color: var(--app-text-3); }
.srv-table-card { background: var(--app-panel); border: 1px solid var(--app-border); border-radius: 12px; overflow: hidden; }
.srv-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.srv-table thead th { text-align: left; font-size: 12px; font-weight: 600; color: var(--app-text-3); background: var(--app-panel-soft); padding: 10px 14px; border-bottom: 1px solid var(--app-border); white-space: nowrap; }
.srv-table tbody td { padding: 11px 14px; color: var(--app-text); border-bottom: 1px solid var(--app-border); }
.srv-table tbody tr:last-child td { border-bottom: none; }
.srv-table tbody tr { cursor: pointer; transition: background .15s; }
.srv-table tbody tr:hover { background: var(--app-hover); }
.srv-table tbody tr.selected { background: var(--mon-accent-soft); }
.sv-name { font-weight: 600; }
.sv-ip, .sv-net { color: var(--app-text-3); font-family: 'SF Mono',Monaco,monospace; }
.sv-net { font-size: 12px; }
.srv-pager { display: flex; justify-content: flex-end; margin-top: 16px; }

/* ===== Server Detail ===== */
.server-detail { margin-top: 20px; background: var(--app-panel); border-radius: 12px; border: 1px solid var(--app-border); padding: 20px; }
.sd-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 14px; border-bottom: 1px solid var(--app-border); }
.sd-title h2 { font-size: 18px; font-weight: 700; color: var(--app-text); margin: 0 0 4px; }
.sd-ip { font-size: 13px; color: var(--app-text-3); font-family: 'SF Mono',Monaco,monospace; }
.sd-hint { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding: 10px 14px; background: var(--mon-warn-soft); border: 1px solid var(--mon-warn-border); border-radius: 8px; font-size: 12px; color: var(--mon-warn-text); }
.back-btn { display: flex; align-items: center; gap: 4px; padding: 6px 12px; border-radius: 6px; border: 1px solid var(--app-border); background: var(--app-panel-soft); cursor: pointer; font-size: 12px; color: var(--app-text-3); transition: all .2s; }
.back-btn:hover { border-color: var(--mon-accent); color: var(--mon-accent-text); }
.sd-trend-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.sd-trend-title { font-size: 13px; font-weight: 700; color: var(--app-text); }

/* ===== Charts ===== */
.sd-charts { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 24px; }
.chart-panel { background: var(--app-panel-soft); border-radius: 8px; border: 1px solid var(--app-border); padding: 12px; }
.chart-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.chart-title { font-size: 13px; font-weight: 600; color: var(--app-text); }
.chart-unit { font-size: 11px; color: var(--app-text-3); }
.chart-container { height: 200px; }

/* ===== Server Services ===== */
.sd-services { border-top: 1px solid var(--app-border); padding-top: 16px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; padding: 0 0 12px; }
.panel-title { font-size: 14px; font-weight: 600; color: var(--app-text); display: flex; align-items: center; gap: 8px; }
.data-tbl { width: 100%; border-collapse: collapse; }
.data-tbl thead th { padding: 10px 14px; font-size: 11px; font-weight: 600; color: var(--app-text-3); text-transform: uppercase; letter-spacing: .5px; text-align: left; background: var(--app-panel-soft); border-bottom: 1px solid var(--app-border); white-space: nowrap; }
.data-tbl tbody td { padding: 12px 14px; font-size: 13px; color: var(--app-text-2); border-bottom: 1px solid var(--app-border); vertical-align: middle; }
.st-pill { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
.st-pill.running, .st-pill.completed { background: var(--mon-success-soft); color: var(--mon-success-text); }
.st-pill.inactive { background: var(--app-panel-soft); color: var(--app-text-3); }
.st-pill.stopped { background: var(--mon-danger-soft); color: var(--mon-danger-text); }
.st-pill.partial, .st-pill.unknown { background: var(--mon-warn-soft); color: var(--mon-warn-text); }
.st-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.val-danger { color: var(--mon-danger-text); font-weight: 700; }
.val-warning { color: var(--mon-warn-text); font-weight: 600; }

/* ===== Server Logs ===== */
.sd-logs { margin-top: 20px; border-top: 1px solid var(--app-border); padding-top: 16px; }
.sd-logs-head { padding: 0 0 12px; border-bottom: 1px solid var(--app-border); flex-wrap: wrap; gap: 10px; }
.log-toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.log-select { padding: 5px 10px; border-radius: 6px; border: 1px solid var(--app-border); font-size: 12px; color: var(--app-text-2); background: var(--app-panel-soft); cursor: pointer; outline: none; max-width: 220px; }
.log-select:focus { border-color: var(--mon-accent); }
.log-input { padding: 5px 10px; border-radius: 6px; border: 1px solid var(--app-border); font-size: 12px; color: var(--app-text-2); background: var(--app-panel-soft); outline: none; width: 180px; }
.log-input:focus { border-color: var(--mon-accent); }
.log-btn { padding: 5px 14px; border-radius: 6px; border: 1px solid var(--mon-accent); background: var(--mon-accent-soft); color: var(--mon-accent-text); font-size: 12px; font-weight: 600; cursor: pointer; }
.log-btn:hover:not(:disabled) { background: var(--mon-accent-soft); }
.log-btn:disabled { opacity: .5; cursor: not-allowed; }
.log-refresh { width: 28px; height: 28px; border-radius: 6px; border: 1px solid var(--app-border); background: var(--app-panel-soft); display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--app-text-3); }
.log-refresh:hover:not(:disabled) { border-color: var(--mon-accent); color: var(--mon-accent-text); }
.log-refresh:disabled { opacity: .5; cursor: not-allowed; }
.log-refresh.spinning .el-icon { animation: spin .9s linear infinite; }
.log-state { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 40px 16px; font-size: 13px; color: var(--app-text-3); }
.log-state.err { color: var(--mon-danger-text); }
.log-list { max-height: 460px; overflow-y: auto; background: var(--mon-log-bg); border-radius: 8px; padding: 4px 0; }
.log-row { padding: 6px 14px; border-bottom: 1px solid var(--app-border); }
.log-row:last-child { border-bottom: none; }
.log-meta { display: flex; align-items: center; gap: 10px; margin-bottom: 2px; flex-wrap: wrap; }
.log-time { font-size: 11px; color: var(--app-text-3); font-family: 'SF Mono',Monaco,monospace; white-space: nowrap; }
.log-level { font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 1px 6px; border-radius: 3px; letter-spacing: .3px; }
.lv-error { background: var(--mon-danger-soft); color: var(--mon-danger-text); }
.lv-warn { background: var(--mon-warn-soft); color: var(--mon-warn-text); }
.lv-info { background: var(--mon-accent-soft); color: var(--mon-accent-text); }
.lv-debug { background: var(--app-panel-soft); color: var(--app-text-2); }
.lv-unknown { background: var(--app-panel-soft); color: var(--app-text-2); }
.log-cont { font-size: 11px; color: var(--mon-accent-text); font-family: 'SF Mono',Monaco,monospace; word-break: break-all; }
.log-msg { font-size: 12px; color: var(--app-text); font-family: 'SF Mono',Monaco,monospace; white-space: pre-wrap; word-break: break-word; line-height: 1.5; }
.log-count { padding: 8px 14px 4px; font-size: 11px; color: var(--app-text-3); }

/* ===== Responsive ===== */
@media (max-width: 1400px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 1200px) { .screen-grid { grid-template-columns: 1fr; } }
@media (max-width: 768px) {
  .monitoring-page { padding: 14px; }
  .kpi-grid { grid-template-columns: 1fr; }
  .page-header { flex-direction: column; gap: 12px; }
  .header-right { flex-wrap: wrap; }
  .donut-body { flex-direction: column; }
}
</style>
