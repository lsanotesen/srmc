<template>
  <div class="alerts-page">
    <div class="page-header">
      <h2>告警中心</h2>
    </div>

    <div class="filter-bar">
      <div class="filter-grid">
        <div class="filter-item w-project">
          <el-select v-model="filters.project_id" placeholder="选择项目" clearable filterable style="width: 100%" @change="handleProjectChange">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </div>
        <div class="filter-item w-subsystem">
          <el-select v-model="filters.subsystem_id" placeholder="选择子系统" clearable filterable :disabled="!filters.project_id" style="width: 100%">
            <el-option v-for="s in subsystems" :key="s.id" :label="s.subsystem_name" :value="s.id" />
          </el-select>
        </div>
        <div class="filter-item w-status">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 100%">
            <el-option label="活跃（活动+已确认）" value="OPEN" />
            <el-option label="活动" value="ACTIVE" />
            <el-option label="已确认" value="CONFIRMED" />
            <el-option label="已恢复" value="RECOVERED" />
          </el-select>
        </div>
        <div class="filter-item w-severity">
          <el-select v-model="filters.severity" placeholder="全部级别" clearable style="width: 100%">
            <el-option label="严重" value="critical" />
            <el-option label="警告" value="warning" />
          </el-select>
        </div>
        <div class="filter-item w-type">
          <el-select v-model="filters.alert_type" placeholder="全部类型" clearable style="width: 100%">
            <el-option label="服务已停止" value="SERVICE_STOPPED" />
            <el-option label="服务运行异常" value="SERVICE_FAILED" />
            <el-option label="服务部分运行" value="SERVICE_PARTIAL" />
          </el-select>
        </div>
        <div class="filter-item w-keyword">
          <el-input v-model="filters.keyword" placeholder="搜索服务/IP/内容" clearable style="width: 100%" />
        </div>
      </div>

      <div class="filter-time-row">
        <div class="filter-item time-item">
          <el-date-picker
            v-model="startTime"
            type="datetime"
            placeholder="选择开始时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
        </div>
        <span class="range-sep">至</span>
        <div class="filter-item time-item">
          <el-date-picker
            v-model="endTime"
            type="datetime"
            placeholder="选择结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
        </div>
        <div class="filter-actions">
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </div>
      </div>
    </div>

    <ListStats :items="statsItems" />

    <el-table :data="records" border v-loading="loading">
      <el-table-column prop="status" label="状态" width="100">
        <template #default="scope">
          <el-tag size="small" :type="statusTagType(scope.row.status)">{{ statusLabel(scope.row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="severity" label="级别" width="90">
        <template #default="scope">
          <el-tag size="small" :type="scope.row.severity === 'critical' ? 'danger' : 'warning'">
            {{ scope.row.severity === 'critical' ? '严重' : '警告' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="alert_type" label="类型" width="130">
        <template #default="scope">{{ typeLabel(scope.row.alert_type) }}</template>
      </el-table-column>
      <el-table-column prop="service_name" label="服务" min-width="160" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.service_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="ip" label="IP" width="140">
        <template #default="scope">{{ scope.row.ip || '-' }}</template>
      </el-table-column>
      <el-table-column label="项目" min-width="140" show-overflow-tooltip>
        <template #default="scope">{{ projectName(scope.row.project_id) }}</template>
      </el-table-column>
      <el-table-column prop="first_seen_at" label="首次发生" width="170">
        <template #default="scope">{{ formatTime(scope.row.first_seen_at) }}</template>
      </el-table-column>
      <el-table-column prop="last_seen_at" label="最近发生" width="170">
        <template #default="scope">{{ formatTime(scope.row.last_seen_at) }}</template>
      </el-table-column>
      <el-table-column prop="confirmer" label="确认人" width="110">
        <template #default="scope">{{ scope.row.confirmed_by_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="scope">
          <el-button link type="primary" size="small" @click="showDetail(scope.row)">详情</el-button>
          <el-button
            v-if="canOperate && scope.row.status === 'ACTIVE'"
            link type="primary" size="small"
            @click="openConfirm(scope.row)"
          >确认</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      :total="total"
      :page-size="pageSize"
      :current-page="currentPage"
      :page-sizes="[20, 50, 100]"
      @current-change="handlePageChange"
      @size-change="handleSizeChange"
      layout="total, sizes, prev, pager, next, jumper"
      class="pagination"
    />

    <!-- 详情 -->
    <el-dialog title="告警详情" v-model="detailVisible" width="680px">
      <el-descriptions :column="1" border v-if="detailRow">
        <el-descriptions-item label="状态">
          <el-tag size="small" :type="statusTagType(detailRow.status)">{{ statusLabel(detailRow.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="级别">{{ detailRow.severity === 'critical' ? '严重' : '警告' }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ typeLabel(detailRow.alert_type) }}</el-descriptions-item>
        <el-descriptions-item label="服务">{{ detailRow.service_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ projectName(detailRow.project_id) }}</el-descriptions-item>
        <el-descriptions-item label="IP">{{ detailRow.ip || '-' }}</el-descriptions-item>
        <el-descriptions-item label="Agent">{{ detailRow.agent_uuid || '-' }}</el-descriptions-item>
        <el-descriptions-item label="首次发生">{{ formatTime(detailRow.first_seen_at) }}</el-descriptions-item>
        <el-descriptions-item label="最近发生">{{ formatTime(detailRow.last_seen_at) }}</el-descriptions-item>
        <el-descriptions-item label="确认人">{{ detailRow.confirmed_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="确认时间">{{ formatTime(detailRow.confirmed_at) }}</el-descriptions-item>
        <el-descriptions-item label="恢复时间">{{ formatTime(detailRow.recovered_at) }}</el-descriptions-item>
        <el-descriptions-item label="处理说明">{{ detailRow.handle_note || '-' }}</el-descriptions-item>
        <el-descriptions-item label="告警详情">
          <pre class="detail-output">{{ detailRow.content || '-' }}</pre>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 确认 -->
    <el-dialog title="确认告警" v-model="confirmVisible" width="520px">
      <el-input
        v-model="confirmNote"
        type="textarea"
        :rows="4"
        maxlength="1000"
        show-word-limit
        placeholder="处理说明（可选）"
      />
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitConfirm">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from '@/utils/axios'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import ListStats from '@/components/ListStats.vue'

const userStore = useUserStore()
const route = useRoute()

// 「活跃」= 活动 + 已确认；后端 /alerts/records 的 status 仅支持单值，故拆两次查询后合并
const OPEN_STATUSES = ['ACTIVE', 'CONFIRMED']
const OPEN_FETCH_SIZE = 100
const openTruncated = ref(false)
const pendingAlertId = ref(null)

const records = ref([])
const total = ref(0)
const stats = ref({ total: 0, by_status: {} })
const lastParams = ref({})
const statsItems = computed(() => {
  const byStatus = stats.value.by_status || {}
  const items = [
    { label: '告警总数', value: `${stats.value.total ?? 0} 条` },
    { label: '活动', value: `${byStatus.ACTIVE || 0} 条` },
    { label: '已确认', value: `${byStatus.CONFIRMED || 0} 条` },
    { label: '已恢复', value: `${byStatus.RECOVERED || 0} 条` }
  ]
  // 是否带筛选（page / page_size 之外的参数即视为筛选条件）
  const filtered = Object.keys(lastParams.value).some(key => key !== 'page' && key !== 'page_size')
  if (filtered) {
    items.push({ label: '筛选结果', value: `${total.value} 条` })
  }
  if (openTruncated.value) {
    items.push({ label: '提示', value: `活跃告警过多，仅合并最近 ${OPEN_FETCH_SIZE * 2} 条` })
  }
  items.push({ label: '本页', value: `${records.value.length} 条` })
  return items
})
const currentPage = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const projects = ref([])
const subsystems = ref([])
const startTime = ref('')
const endTime = ref('')
// 保持查询参数不变：仅当开始与结束时间都选择时才作为时间范围过滤
const dateRange = computed(() => (startTime.value && endTime.value) ? [startTime.value, endTime.value] : [])

const detailVisible = ref(false)
const detailRow = ref(null)

const confirmVisible = ref(false)
const confirmRow = ref(null)
const confirmNote = ref('')
const submitting = ref(false)

const filters = reactive({
  project_id: '',
  subsystem_id: '',
  status: '',
  severity: '',
  alert_type: '',
  keyword: ''
})

// 确认/恢复复用 service:operate（真实码为 service:start/stop/restart），不新增权限码
const canOperate = computed(() =>
  userStore.hasPermission('service:start')
  || userStore.hasPermission('service:stop')
  || userStore.hasPermission('service:restart')
)

const TYPE_LABELS = {
  SERVICE_STOPPED: '服务已停止',
  SERVICE_FAILED: '服务运行异常',
  SERVICE_PARTIAL: '服务部分运行'
}
const typeLabel = (t) => TYPE_LABELS[t] || t || '-'

const statusLabel = (s) => ({ ACTIVE: '活动', CONFIRMED: '已确认', RECOVERED: '已恢复' }[s] || s || '-')
const statusTagType = (s) => ({ ACTIVE: 'danger', CONFIRMED: 'warning', RECOVERED: 'success' }[s] || 'info')

const projectMap = computed(() => {
  const m = {}
  projects.value.forEach(p => { m[p.id] = p.name })
  return m
})
const projectName = (id) => (id && projectMap.value[id]) ? projectMap.value[id] : (id ? `#${id}` : '-')

const formatTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (isNaN(date.getTime())) return value
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

const loadProjects = async () => {
  try {
    const response = await axios.get('/api/projects', { params: { page: 1, size: 100 } })
    if (response.data.code === 0) {
      projects.value = response.data.data.items || []
    }
  } catch (error) {
    // 项目列表加载失败不阻塞告警查询
  }
}

const loadSubsystems = async (projectId) => {
  subsystems.value = []
  if (!projectId) return
  try {
    const response = await axios.get(`/api/projects/${projectId}/subsystems`)
    if (response.data.code === 0) {
      subsystems.value = response.data.data || []
    }
  } catch (error) {
    subsystems.value = []
  }
}

const handleProjectChange = (projectId) => {
  filters.subsystem_id = ''
  loadSubsystems(projectId)
}

const buildParams = (page) => {
  const params = { page, page_size: pageSize.value }
  if (filters.project_id) params.project_id = filters.project_id
  if (filters.subsystem_id) params.subsystem_id = filters.subsystem_id
  // OPEN 由前端拆分两次查询实现，不能作为单值传给后端
  if (filters.status && filters.status !== 'OPEN') params.status = filters.status
  if (filters.severity) params.severity = filters.severity
  if (filters.alert_type) params.alert_type = filters.alert_type
  if (filters.keyword) params.keyword = filters.keyword.trim()
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_time = dateRange.value[0]
    params.end_time = dateRange.value[1]
  }
  return params
}

// 活跃告警：分别拉取 ACTIVE / CONFIRMED 后按最近发生时间合并、再本地分页
async function loadOpenRecords(page = 1) {
  const base = buildParams(page)
  const responses = await Promise.all(OPEN_STATUSES.map(status =>
    axios.get('/api/alerts/records', {
      params: { ...base, page: 1, page_size: OPEN_FETCH_SIZE, status }
    })
  ))
  const itemsOf = (res) => (res.data?.code === 0 ? (res.data.data?.items || []) : [])
  const totalOf = (res) => (res.data?.code === 0 ? (res.data.data?.total || 0) : 0)
  openTruncated.value = responses.some(res => totalOf(res) > OPEN_FETCH_SIZE)
  const merged = responses
    .flatMap(itemsOf)
    .sort((a, b) => new Date(b.last_seen_at || 0) - new Date(a.last_seen_at || 0))
  lastParams.value = { ...base, status: 'OPEN' }
  total.value = merged.length
  currentPage.value = page
  const start = (page - 1) * pageSize.value
  records.value = merged.slice(start, start + pageSize.value)
}

async function loadRecords(page = 1) {
  loading.value = true
  try {
    if (filters.status === 'OPEN') {
      await loadOpenRecords(page)
      return
    }
    openTruncated.value = false
    const params = buildParams(page)
    lastParams.value = params
    const response = await axios.get('/api/alerts/records', { params })
    if (response.data.code === 0) {
      records.value = response.data.data.items || []
      total.value = response.data.data.total || 0
      currentPage.value = page
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '加载告警列表失败')
  } finally {
    loading.value = false
  }
}

// 告警状态统计（全部告警数 / 活动 / 已确认 / 已恢复），复用告警中心统计接口
async function loadStats() {
  try {
    const response = await axios.get('/api/alerts/records/stats')
    if (response.data.code === 0) {
      stats.value = response.data.data || { total: 0, by_status: {} }
    }
  } catch (error) {
    // 统计失败不阻塞列表展示
  }
}

function handleSearch() { loadRecords(1) }

function handleReset() {
  filters.project_id = ''
  filters.subsystem_id = ''
  filters.status = ''
  filters.severity = ''
  filters.alert_type = ''
  filters.keyword = ''
  startTime.value = ''
  endTime.value = ''
  subsystems.value = []
  loadRecords(1)
}

function handlePageChange(page) { loadRecords(page) }

function handleSizeChange(size) {
  pageSize.value = size
  loadRecords(1)
}

function showDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

function openConfirm(row) {
  confirmRow.value = row
  confirmNote.value = row.handle_note || ''
  confirmVisible.value = true
}

async function submitConfirm() {
  if (!confirmRow.value) return
  submitting.value = true
  try {
    const response = await axios.post(`/api/alerts/records/${confirmRow.value.id}/confirm`, {
      note: confirmNote.value
    })
    if (response.data.code === 0) {
      ElMessage.success('已确认')
      confirmVisible.value = false
      loadRecords(currentPage.value)
      loadStats()
    } else {
      ElMessage.error(response.data.message || '确认失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '确认失败')
  } finally {
    submitting.value = false
  }
}

const STATUS_VALUES = ['ACTIVE', 'CONFIRMED', 'RECOVERED']
const SEVERITY_VALUES = ['critical', 'warning']
const TYPE_VALUES = ['SERVICE_STOPPED', 'SERVICE_FAILED', 'SERVICE_PARTIAL']

const firstValue = (raw) => (Array.isArray(raw) ? raw[0] : raw)

const toPositiveInt = (raw) => {
  const n = Number(firstValue(raw))
  return Number.isFinite(n) && n > 0 ? n : null
}

// 兼容 ?status=OPEN / ?status=ACTIVE,CONFIRMED / 重复的 ?status=ACTIVE&status=CONFIRMED
// 后端只接受单值 status，重复参数只会保留最后一个，故这里统一归一化为 OPEN
function normalizeStatusQuery(raw) {
  if (!raw) return ''
  const list = (Array.isArray(raw) ? raw : String(raw).split(','))
    .map(v => String(v).trim().toUpperCase())
    .filter(Boolean)
  if (!list.length) return ''
  if (list.includes('OPEN')) return 'OPEN'
  const valid = [...new Set(list.filter(v => STATUS_VALUES.includes(v)))]
  if (valid.includes('ACTIVE') && valid.includes('CONFIRMED')) return 'OPEN'
  return valid.length === 1 ? valid[0] : ''
}

function initFiltersFromQuery() {
  const q = route.query
  const projectId = toPositiveInt(q.project_id)
  if (projectId) filters.project_id = projectId
  const subsystemId = toPositiveInt(q.subsystem_id)
  if (subsystemId) filters.subsystem_id = subsystemId
  filters.status = normalizeStatusQuery(q.status)
  const severity = String(firstValue(q.severity) || '').trim().toLowerCase()
  if (SEVERITY_VALUES.includes(severity)) filters.severity = severity
  const alertType = String(firstValue(q.alert_type) || '').trim().toUpperCase()
  if (TYPE_VALUES.includes(alertType)) filters.alert_type = alertType
  const keyword = String(firstValue(q.keyword) || '').trim()
  if (keyword) filters.keyword = keyword.slice(0, 100)
  pendingAlertId.value = toPositiveInt(q.alert_id)
}

// 列表加载完成后再定位告警：当前页命中直接打开，否则在活跃范围内补查一次
async function openPendingAlert() {
  const id = pendingAlertId.value
  if (!id) return
  pendingAlertId.value = null
  const hit = records.value.find(r => r.id === id)
  if (hit) {
    showDetail(hit)
    return
  }
  try {
    const responses = await Promise.all(OPEN_STATUSES.map(status =>
      axios.get('/api/alerts/records', { params: { page: 1, page_size: OPEN_FETCH_SIZE, status } })
    ))
    const found = responses
      .flatMap(res => (res.data?.code === 0 ? (res.data.data?.items || []) : []))
      .find(r => r.id === id)
    if (found) {
      showDetail(found)
      return
    }
  } catch (error) {
    // 查询失败按未找到处理
  }
  ElMessage.warning('未找到该告警，可能已恢复或当前账号无权查看')
}

onMounted(async () => {
  initFiltersFromQuery()
  await Promise.all([loadProjects(), loadStats()])
  if (filters.project_id) await loadSubsystems(filters.project_id)
  await loadRecords(1)
  await openPendingAlert()
})
</script>

<style scoped>
.alerts-page {
  padding: 20px;
}
.page-header h2 {
  margin: 0 0 16px;
  font-size: 20px;
  font-weight: 600;
}
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 8px;
  padding: 14px 16px 12px;
  margin-bottom: 16px;
}
/* 取消分组容器，使所有筛选项在同一行内流动；宽度不足时自动换行 */
.filter-grid,
.filter-time-row {
  display: contents;
}
.filter-item {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
/* 按内容分配宽度：项目/子系统适中，状态/级别/类型更窄，关键词加宽 */
.filter-item.w-project,
.filter-item.w-subsystem { width: 160px; }
.filter-item.w-status,
.filter-item.w-severity { width: 120px; }
.filter-item.w-type { width: 120px; }
.filter-item.w-keyword { width: 200px; }
.time-item {
  width: 200px;
  min-width: 0;
}
.range-sep {
  /* 与 32px 高的日期控件垂直居中对齐 */
  align-self: flex-end;
  height: 32px;
  line-height: 32px;
  font-size: 13px;
  color: var(--el-text-color-placeholder, #a8abb2);
}
.filter-actions {
  display: flex;
  gap: 10px;
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.detail-output {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
}
</style>
