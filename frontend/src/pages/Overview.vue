<template>
  <div class="overview-page">
    <!-- 顶部工具栏 -->
    <div class="overview-header">
      <h1>运行总览</h1>
      <div class="header-actions">
        <span class="last-update" v-if="lastUpdate">最后更新：{{ lastUpdate }}</span>
        <el-select v-model="refreshInterval" class="refresh-select" @change="restartAutoRefresh">
          <el-option label="自动刷新：60秒" :value="60000" />
          <el-option label="自动刷新：30秒" :value="30000" />
          <el-option label="自动刷新：5分钟" :value="300000" />
          <el-option label="关闭自动刷新" :value="0" />
        </el-select>
        <el-button :icon="Refresh" @click="loadAll" :loading="loading">刷新</el-button>
      </div>
    </div>

    <!-- 7 张统计卡片 -->
    <div class="stats-grid">
      <div
        v-for="card in statCards"
        :key="card.key"
        class="stat-card"
        :style="{ borderTop: `3px solid ${card.color}` }"
        @click="card.onClick"
      >
        <div class="stat-card-icon" :style="{ backgroundColor: card.color + '15', color: card.color }">
          <el-icon :size="24"><component :is="card.icon" /></el-icon>
        </div>
        <div class="stat-card-body">
          <div class="stat-card-value" :style="{ color: card.color }">{{ card.value }}</div>
          <div class="stat-card-label">{{ card.label }}</div>
        </div>
      </div>
    </div>

    <!-- 项目运行状态 + 停止服务 两列 -->
    <div class="main-grid">
      <!-- 项目运行状态 -->
      <div class="card">
        <div class="card-header">
          <h3>项目运行状态</h3>
          <span v-if="projectLoadError" class="load-error">数据获取失败 <button @click="loadProjects" class="retry-btn">重试</button></span>
        </div>
        <div v-if="projects.length === 0 && !projectLoadError" class="card-empty">
          <span>暂无项目数据</span>
        </div>
        <div v-else class="project-list">
          <div
            v-for="p in projects"
            :key="p.projectId"
            class="project-row"
            @click="goToServices({ project_id: p.projectId })"
          >
            <div class="project-info">
              <span class="project-name">{{ p.projectName }}</span>
              <el-tag
                :type="healthTagType(p.healthStatus)"
                size="small"
                effect="light"
                round
                class="health-tag"
              >{{ p.healthStatus }}</el-tag>
            </div>
            <div class="project-stats" @click.stop>
              <span class="ps-total">共 {{ p.serviceCount }} 服务</span>
              <span class="ps-running" v-if="p.runningCount">运行 {{ p.runningCount }}</span>
              <span
                v-if="p.stoppedCount > 0"
                class="ps-stopped clickable"
                @click="goToServices({ project_id: p.projectId, status: 'STOPPED' })"
              >已停止 {{ p.stoppedCount }}</span>
              <span v-if="p.inactiveCount > 0" class="ps-inactive">未启用 {{ p.inactiveCount }}</span>
              <span
                v-if="p.abnormalCount > 0"
                class="ps-failed clickable"
                @click="goToServices({ project_id: p.projectId, status: 'ABNORMAL' })"
              >异常 {{ p.abnormalCount }}</span>
              <span
                v-if="p.agentOfflineCount > 0"
                class="ps-agent clickable"
                @click="goToServices({ project_id: p.projectId, agent_status: 'offline' })"
              >Agent异常 {{ p.agentOfflineCount }}</span>
              <span v-if="p.unknownCount > 0" class="ps-unknown">未知 {{ p.unknownCount }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 当前停止服务 -->
      <div class="card">
        <div class="card-header">
          <h3>当前停止服务</h3>
          <div class="card-header-actions">
            <span v-if="stoppedLoadError" class="load-error">数据获取失败 <button @click="loadStopped" class="retry-btn">重试</button></span>
            <el-button
              v-if="stoppedItems.length > 0"
              link
              type="primary"
              @click="goToServices({ status: 'STOPPED' })"
            >查看全部 →</el-button>
          </div>
        </div>
        <div v-if="stoppedItems.length === 0 && !stoppedLoadError" class="card-empty">
          <span style="color: #059669;">✓ 当前无停止服务</span>
        </div>
        <table v-else class="stopped-table">
          <thead>
            <tr>
              <th>服务</th>
              <th>项目</th>
              <th>IP</th>
              <th>部署方式</th>
              <th>最后更新</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in stoppedItems" :key="s.id" @click="goToServices({ status: 'STOPPED', project_id: s.project_id })" class="clickable">
              <td class="svc-name">{{ s.func_desc }}</td>
              <td>{{ s.project_name || '-' }}</td>
              <td>{{ s.ip }}</td>
              <td><el-tag size="small" type="info">{{ deployTypeLabel(s.deploy_type) }}</el-tag></td>
              <td class="time-cell">{{ s.last_update || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 服务器状态概览 + 未处理告警 两列 -->
    <div class="main-grid">
      <!-- 服务器状态概览 -->
      <div class="card">
        <div class="card-header">
          <h3>服务器状态</h3>
          <div class="card-header-actions">
            <span v-if="serverLoadError" class="load-error">数据获取失败 <button @click="loadServers" class="retry-btn">重试</button></span>
            <el-button v-if="serverList.length > 0" link type="primary" @click="router.push('/servers')">查看全部 →</el-button>
          </div>
        </div>
        <div v-if="serverList.length === 0 && !serverLoadError" class="card-empty">
          <span>暂无服务器数据</span>
        </div>
        <template v-else>
          <div class="mini-kpis">
            <div class="mini-kpi"><span class="mini-value">{{ serverSummary.total }}</span><span class="mini-label">服务器总数</span></div>
            <div class="mini-kpi"><span class="mini-value">{{ serverSummary.monitored }}</span><span class="mini-label">有监控数据</span></div>
            <div class="mini-kpi"><span class="mini-value">{{ serverSummary.avgCpu }}<small>%</small></span><span class="mini-label">平均 CPU</span></div>
            <div class="mini-kpi"><span class="mini-value">{{ serverSummary.avgMem }}<small>%</small></span><span class="mini-label">平均内存</span></div>
          </div>
          <table class="stopped-table">
            <thead>
              <tr>
                <th>主机</th>
                <th>IP</th>
                <th>CPU</th>
                <th>内存</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in serverTop" :key="s.id" class="clickable" @click="router.push('/servers')">
                <td class="svc-name">{{ s.hostname || '-' }}</td>
                <td>{{ s.ip }}</td>
                <td>{{ fmtServerPct(s.cpu_percent) }}</td>
                <td>{{ fmtServerPct(s.memory_percent) }}</td>
                <td><el-tag size="small" :type="s.hasData ? 'success' : 'info'">{{ s.hasData ? '正常' : '无数据' }}</el-tag></td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>

      <!-- 未处理告警（告警中心 DB 接口，非 Alertmanager） -->
      <div class="card">
        <div class="card-header">
          <h3>未处理告警 <span v-if="alertOpenTotal > 0" class="alert-badge">{{ alertOpenTotal }}</span></h3>
          <div class="card-header-actions">
            <span v-if="alertLoadError" class="load-error">数据获取失败 <button @click="loadAlerts" class="retry-btn">重试</button></span>
            <el-button v-if="openAlerts.length > 0" link type="primary" @click="router.push('/alerts')">查看全部 →</el-button>
          </div>
        </div>
        <div v-if="openAlerts.length === 0 && !alertLoadError" class="card-empty">
          <span style="color: #059669;">✓ 当前无未处理告警</span>
        </div>
        <template v-else>
          <div class="mini-kpis">
            <div class="mini-kpi"><span class="mini-value">{{ alertOpenTotal }}</span><span class="mini-label">未处理</span></div>
            <div class="mini-kpi"><span class="mini-value sev-critical">{{ alertSev.CRITICAL }}</span><span class="mini-label">严重</span></div>
            <div class="mini-kpi"><span class="mini-value sev-warning">{{ alertSev.WARNING }}</span><span class="mini-label">警告</span></div>
          </div>
          <div class="alert-list">
            <div v-for="a in openAlerts" :key="a.id" class="alert-row" @click="router.push('/alerts')">
              <span class="alert-sev-tag" :class="a.severity">{{ formatAlertSev(a.severity) }}</span>
              <div class="alert-body">
                <div class="alert-title">{{ a.title || a.service_name }}</div>
                <div class="alert-meta">{{ a.service_name }} · {{ formatTime(a.last_seen_at) }}</div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- Agent 异常 -->
    <div class="card">
      <div class="card-header">
        <h3>Agent 异常</h3>
        <span v-if="agentLoadError" class="load-error">数据获取失败 <button @click="loadAgentOffline" class="retry-btn">重试</button></span>
      </div>
      <div v-if="agentOfflineItems.length === 0 && !agentLoadError" class="card-empty">
        <span style="color: #059669;">✓ 当前无 Agent 异常</span>
      </div>
      <table v-else class="stopped-table">
        <thead>
          <tr>
            <th>服务</th>
            <th>项目</th>
            <th>IP</th>
            <th>Agent 状态</th>
            <th>最后心跳</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in agentOfflineItems" :key="s.id" class="clickable" @click="goToServices({ agent_status: 'offline', project_id: s.project_id })">
            <td class="svc-name">{{ s.func_desc }}</td>
            <td>{{ s.project_name || '-' }}</td>
            <td>{{ s.ip }}</td>
            <td><el-tag size="small" type="danger">离线</el-tag></td>
            <td class="time-cell">{{ s.last_heartbeat || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { Refresh, Folder, CircleCheck, CircleClose, Warning, QuestionFilled, Monitor, Cpu } from '@element-plus/icons-vue';
import axios from '@/utils/axios';

const router = useRouter();
const loading = ref(false);
const lastUpdate = ref('');
const refreshInterval = ref(60000);
let refreshTimer = null;

// 统计数据
const overview = reactive({
  projectCount: 0,
  serviceCount: 0,
  runningCount: 0,
  stoppedCount: 0,
  inactiveCount: 0,
  agentOfflineCount: 0,
  abnormalCount: 0,
  unknownCount: 0,
});

// 项目列表
const projects = ref([]);
const projectLoadError = ref(false);

// 停止服务
const stoppedItems = ref([]);
const stoppedLoadError = ref(false);

// Agent 异常
const agentOfflineItems = ref([]);
const agentLoadError = ref(false);

// 服务器状态（复用 /api/monitor/servers，组织权限由后端强制）
const serverList = ref([]);
const serverLoadError = ref(false);

// 未处理告警（复用告警中心 DB 接口，非 Alertmanager 实时接口）
const alertOpenTotal = ref(0);
const alertSev = reactive({ CRITICAL: 0, WARNING: 0 });
const openAlerts = ref([]);
const alertLoadError = ref(false);

// 6 张统计卡片配置
const statCards = computed(() => [
  {
    key: 'projectCount',
    label: '项目总数',
    value: overview.projectCount,
    color: '#3b82f6',
    icon: Folder,
    onClick: () => router.push('/projects'),
  },
  {
    key: 'serviceCount',
    label: '服务总数',
    value: overview.serviceCount,
    color: '#6366f1',
    icon: Cpu,
    onClick: () => router.push('/services'),
  },
  {
    key: 'runningCount',
    label: '运行中',
    value: overview.runningCount,
    color: '#059669',
    icon: CircleCheck,
    onClick: () => goToServices({ status: 'RUNNING' }),
  },
  {
    key: 'stoppedCount',
    label: '已停止',
    value: overview.stoppedCount,
    color: '#dc2626',
    icon: CircleClose,
    onClick: () => goToServices({ status: 'STOPPED' }),
  },
  {
    key: 'agentOfflineCount',
    label: 'Agent 异常',
    value: overview.agentOfflineCount,
    color: '#6b7280',
    icon: Monitor,
    onClick: () => goToServices({ agent_status: 'offline' }),
  },
  {
    key: 'abnormalCount',
    label: '服务异常',
    value: overview.abnormalCount,
    color: '#ef4444',
    icon: Warning,
    onClick: () => goToServices({ status: 'ABNORMAL' }),
  },
  {
    key: 'unknownCount',
    label: '状态未知',
    value: overview.unknownCount,
    color: '#d97706',
    icon: QuestionFilled,
    onClick: () => goToServices({ status: 'UNKNOWN' }),
  },
]);

function healthTagType(status) {
  const map = { '异常': 'danger', 'Agent异常': 'info', '状态未知': 'warning', '正常': 'success' };
  return map[status] || 'info';
}

function deployTypeLabel(t) {
  const map = { HOST: 'HOST', PROCESS: 'PROCESS', DOCKER: 'DOCKER', DOCKER_COMPOSE: 'Docker Compose' };
  return map[t] || t || '-';
}

function goToServices(query = {}) {
  router.push({ path: '/services', query });
}

async function loadOverview() {
  try {
    const resp = await axios.get('/api/dashboard/overview');
    if (resp.data.code === 0) {
      Object.assign(overview, resp.data.data);
    }
  } catch (e) {
    console.warn('[overview] load failed:', e.message);
  }
}

async function loadProjects() {
  projectLoadError.value = false;
  try {
    const resp = await axios.get('/api/dashboard/projects');
    if (resp.data.code === 0) {
      projects.value = resp.data.data || [];
    }
  } catch (e) {
    projectLoadError.value = true;
    console.warn('[projects] load failed:', e.message);
  }
}

async function loadStopped() {
  stoppedLoadError.value = false;
  try {
    const resp = await axios.get('/api/dashboard/stopped-services?size=10');
    if (resp.data.code === 0) {
      stoppedItems.value = resp.data.data?.items || [];
    }
  } catch (e) {
    stoppedLoadError.value = true;
    console.warn('[stopped] load failed:', e.message);
  }
}

async function loadAgentOffline() {
  agentLoadError.value = false;
  try {
    const resp = await axios.get('/api/dashboard/agent-offline');
    if (resp.data.code === 0) {
      agentOfflineItems.value = resp.data.data?.items || [];
    }
  } catch (e) {
    agentLoadError.value = true;
    console.warn('[agent-offline] load failed:', e.message);
  }
}

// ===== 服务器状态（复用 /api/monitor/servers） =====
function serverHasData(s) {
  return (s.cpu_percent || 0) > 0 || (s.memory_percent || 0) > 0 || (s.disk_usage_percent || 0) > 0;
}

const serverSummary = computed(() => {
  const list = serverList.value;
  const withData = list.filter(serverHasData);
  const avg = (key) => withData.length
    ? (withData.reduce((acc, s) => acc + (s[key] || 0), 0) / withData.length).toFixed(1)
    : '0.0';
  return {
    total: list.length,
    monitored: withData.length,
    avgCpu: avg('cpu_percent'),
    avgMem: avg('memory_percent'),
  };
});

const serverTop = computed(() =>
  [...serverList.value]
    .sort((a, b) => (b.cpu_percent || 0) - (a.cpu_percent || 0))
    .slice(0, 8)
    .map((s) => ({ ...s, hasData: serverHasData(s) }))
);

function fmtServerPct(v) {
  const n = Number(v);
  return n > 0 ? `${n.toFixed(1)}%` : '-';
}

async function loadServers() {
  serverLoadError.value = false;
  try {
    const resp = await axios.get('/api/monitor/servers');
    if (resp.data.code === 0) {
      serverList.value = resp.data.data || [];
    }
  } catch (e) {
    serverLoadError.value = true;
    console.warn('[servers] load failed:', e.message);
  }
}

// ===== 未处理告警（复用 /api/alerts/records + stats） =====
function formatAlertSev(sev) {
  return { CRITICAL: '严重', WARNING: '警告' }[sev] || sev || '-';
}

function formatTime(t) {
  if (!t) return '-';
  const d = new Date(t);
  return isNaN(d.getTime()) ? String(t) : d.toLocaleString('zh-CN', { hour12: false });
}

async function loadAlerts() {
  alertLoadError.value = false;
  try {
    const [statsResp, activeResp, confirmedResp] = await Promise.all([
      axios.get('/api/alerts/records/stats'),
      axios.get('/api/alerts/records', { params: { status: 'ACTIVE', page_size: 10 } }),
      axios.get('/api/alerts/records', { params: { status: 'CONFIRMED', page_size: 10 } }),
    ]);
    if (statsResp.data.code === 0) {
      const d = statsResp.data.data || {};
      alertOpenTotal.value = d.open_total || 0;
      const sev = d.open_by_severity || {};
      alertSev.CRITICAL = sev.CRITICAL || 0;
      alertSev.WARNING = sev.WARNING || 0;
    }
    const items = [];
    if (activeResp.data.code === 0) items.push(...(activeResp.data.data?.items || []));
    if (confirmedResp.data.code === 0) items.push(...(confirmedResp.data.data?.items || []));
    items.sort((a, b) => new Date(b.last_seen_at || 0) - new Date(a.last_seen_at || 0));
    openAlerts.value = items.slice(0, 10);
  } catch (e) {
    alertLoadError.value = true;
    console.warn('[alerts] load failed:', e.message);
  }
}

async function loadAll() {
  loading.value = true;
  await Promise.all([loadOverview(), loadProjects(), loadStopped(), loadAgentOffline(), loadServers(), loadAlerts()]);
  lastUpdate.value = new Date().toLocaleString('zh-CN', { hour12: false });
  loading.value = false;
}

function startAutoRefresh() {
  stopAutoRefresh();
  if (refreshInterval.value > 0) {
    refreshTimer = setInterval(loadAll, refreshInterval.value);
  }
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

function restartAutoRefresh() {
  startAutoRefresh();
}

onMounted(() => {
  loadAll();
  startAutoRefresh();
});

onBeforeUnmount(() => {
  stopAutoRefresh();
});
</script>

<style scoped>
.overview-page {
  padding: 20px 24px;
  height: 100%;
  overflow-y: auto;
}

.overview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.overview-header h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: var(--app-text);
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.last-update {
  font-size: 13px;
  color: var(--app-text-3);
}
.refresh-select {
  width: 170px;
}

/* 统计卡片网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  background: var(--app-panel);
  border-radius: 12px;
  padding: 18px 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.04);
  border: 1px solid var(--app-border);
  cursor: pointer;
  transition: all 0.2s ease;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.08);
}
.stat-card-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-card-body {
  display: flex;
  flex-direction: column;
}
.stat-card-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
}
.stat-card-label {
  font-size: 13px;
  color: var(--app-text-2);
  margin-top: 2px;
}

/* 主网格 */
.main-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

/* 通用卡片 */
.card {
  background: var(--app-panel);
  border-radius: 12px;
  border: 1px solid var(--app-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  overflow: hidden;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid var(--app-border);
}
.card-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--app-text);
}
.card-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.card-empty {
  padding: 32px;
  text-align: center;
  color: var(--app-text-3);
  font-size: 14px;
}
.load-error {
  font-size: 12px;
  color: #dc2626;
}
.retry-btn {
  background: none;
  border: none;
  color: #3b82f6;
  cursor: pointer;
  font-size: 12px;
  padding: 0;
  margin-left: 4px;
}
.retry-btn:hover { text-decoration: underline; }

/* 项目列表 */
.project-list {
  padding: 8px 0;
  max-height: 400px;
  overflow-y: auto;
}
.project-row {
  padding: 12px 20px;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1px solid #f8fafc;
}
.project-row:last-child { border-bottom: none; }
.project-row:hover { background: var(--app-panel-soft); }
.project-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.project-name {
  font-weight: 600;
  color: var(--app-text);
  font-size: 14px;
}
.health-tag {
  font-size: 12px;
}
.project-stats {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--app-text-2);
}
.ps-running { color: #059669; }
.ps-stopped { color: #dc2626; }
.ps-inactive { color: var(--app-text-2); }
.ps-agent { color: #6b7280; }
.ps-failed { color: #ef4444; }
.ps-unknown { color: #d97706; }
.ps-stopped.clickable,
.ps-failed.clickable,
.ps-agent.clickable {
  cursor: pointer;
  padding: 1px 6px;
  border-radius: 4px;
  transition: background 0.15s;
}
.ps-stopped.clickable:hover { background: #fef2f2; }
.ps-failed.clickable:hover { background: #fef2f2; }
.ps-agent.clickable:hover { background: var(--app-panel-soft); }

/* 表格 */
.stopped-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.stopped-table th {
  text-align: left;
  padding: 10px 16px;
  font-weight: 600;
  color: var(--app-text-2);
  background: var(--app-panel-soft);
  border-bottom: 1px solid var(--app-border);
  font-size: 12px;
}
.stopped-table td {
  padding: 10px 16px;
  border-bottom: 1px solid #f8fafc;
  color: var(--app-text);
}
.stopped-table tr:last-child td { border-bottom: none; }
.stopped-table tr.clickable {
  cursor: pointer;
  transition: background 0.15s;
}
.stopped-table tr.clickable:hover { background: var(--app-panel-soft); }
.svc-name { font-weight: 500; color: var(--app-text); }
.time-cell { color: var(--app-text-3); white-space: nowrap; }

/* 服务器状态 / 未处理告警 迷你 KPI */
.mini-kpis {
  display: flex;
  gap: 28px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--app-border);
}
.mini-kpi {
  display: flex;
  flex-direction: column;
}
.mini-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--app-text);
  line-height: 1.2;
}
.mini-value small { font-size: 12px; font-weight: 600; }
.mini-label {
  font-size: 12px;
  color: var(--app-text-2);
  margin-top: 2px;
}
.sev-critical { color: #dc2626; }
.sev-warning { color: #d97706; }
.alert-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 0 7px;
  background: #fef2f2;
  color: #dc2626;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}

/* 未处理告警列表 */
.alert-list {
  max-height: 320px;
  overflow-y: auto;
  padding: 4px 0;
}
.alert-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 20px;
  border-bottom: 1px solid #f8fafc;
  cursor: pointer;
  transition: background 0.15s;
}
.alert-row:last-child { border-bottom: none; }
.alert-row:hover { background: var(--app-panel-soft); }
.alert-sev-tag {
  flex-shrink: 0;
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 4px;
  white-space: nowrap;
}
.alert-sev-tag.CRITICAL { background: #fef2f2; color: #dc2626; }
.alert-sev-tag.WARNING { background: #fffbeb; color: #d97706; }
.alert-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--app-text);
}
.alert-meta {
  font-size: 12px;
  color: var(--app-text-3);
  margin-top: 2px;
}

/* 响应式：小屏适配 */
@media (max-width: 1200px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
  .main-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
