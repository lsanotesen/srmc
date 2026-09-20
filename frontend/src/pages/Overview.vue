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

    <!-- 6 张统计卡片 -->
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

async function loadAll() {
  loading.value = true;
  await Promise.all([loadOverview(), loadProjects(), loadStopped(), loadAgentOffline()]);
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
  color: #1e293b;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.last-update {
  font-size: 13px;
  color: #94a3b8;
}
.refresh-select {
  width: 170px;
}

/* 统计卡片网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 18px 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.04);
  border: 1px solid #f1f5f9;
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
  color: #64748b;
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
  background: #fff;
  border-radius: 12px;
  border: 1px solid #f1f5f9;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  overflow: hidden;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid #f1f5f9;
}
.card-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}
.card-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.card-empty {
  padding: 32px;
  text-align: center;
  color: #94a3b8;
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
.project-row:hover { background: #f8fafc; }
.project-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.project-name {
  font-weight: 600;
  color: #1e293b;
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
  color: #64748b;
}
.ps-running { color: #059669; }
.ps-stopped { color: #dc2626; }
.ps-inactive { color: #64748b; }
.ps-agent { color: #6b7280; }
.ps-unknown { color: #d97706; }
.ps-stopped.clickable,
.ps-agent.clickable {
  cursor: pointer;
  padding: 1px 6px;
  border-radius: 4px;
  transition: background 0.15s;
}
.ps-stopped.clickable:hover { background: #fef2f2; }
.ps-agent.clickable:hover { background: #f3f4f6; }

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
  color: #64748b;
  background: #fafbfc;
  border-bottom: 1px solid #f1f5f9;
  font-size: 12px;
}
.stopped-table td {
  padding: 10px 16px;
  border-bottom: 1px solid #f8fafc;
  color: #334155;
}
.stopped-table tr:last-child td { border-bottom: none; }
.stopped-table tr.clickable {
  cursor: pointer;
  transition: background 0.15s;
}
.stopped-table tr.clickable:hover { background: #f8fafc; }
.svc-name { font-weight: 500; color: #1e293b; }
.time-cell { color: #94a3b8; white-space: nowrap; }

/* 响应式：小屏适配 */
@media (max-width: 1200px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
  .main-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
