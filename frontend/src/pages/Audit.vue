<template>
  <div class="audit-page">
    <div class="page-header">
      <h2>审计日志</h2>
    </div>

    <div class="filter-bar">
      <el-select v-model="filters.project_id" placeholder="项目" clearable filterable style="width: 160px" @change="handleProjectChange">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-select v-model="filters.subsystem_id" placeholder="子系统" clearable filterable style="width: 160px" :disabled="!filters.project_id">
        <el-option v-for="s in subsystems" :key="s.id" :label="s.subsystem_name" :value="s.id" />
      </el-select>
      <el-input v-model="filters.service_name" placeholder="服务名称" clearable style="width: 200px" />
      <el-input v-model="filters.username" placeholder="操作用户" clearable style="width: 120px" />
      <el-select v-model="filters.action" placeholder="操作类型" clearable style="width: 120px">
        <el-option label="启动" value="SERVICE_START" />
        <el-option label="停止" value="SERVICE_STOP" />
        <el-option label="重启" value="SERVICE_RESTART" />
        <el-option label="发布" value="SERVICE_IMPORT" />
        <el-option label="编辑" value="SERVICE_UPDATE" />
        <el-option label="新增" value="SERVICE_CREATE" />
        <el-option label="删除" value="SERVICE_DELETE" />
      </el-select>
      <el-select v-model="filters.result" placeholder="操作结果" clearable style="width: 120px">
        <el-option label="成功" value="success" />
        <el-option label="失败" value="failed" />
        <el-option label="部分成功" value="partial" />
      </el-select>
      <el-date-picker
        v-model="dateRange"
        type="datetimerange"
        range-separator="至"
        start-placeholder="开始时间"
        end-placeholder="结束时间"
        value-format="YYYY-MM-DD HH:mm:ss"
        style="width: 400px"
      />
      <el-button type="primary" @click="handleSearch">查询</el-button>
      <el-button @click="handleReset">重置</el-button>
    </div>

    <ListStats :items="statsItems" />

    <el-table :data="logs" border v-loading="loading">
      <el-table-column prop="created_at" label="操作时间" width="180">
        <template #default="scope">
          {{ formatTime(scope.row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="username" label="操作用户" width="120" />
      <el-table-column prop="project_name" label="项目" min-width="140" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.project_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="subsystem_name" label="子系统" min-width="140" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.subsystem_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="service_name" label="服务" min-width="180" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.service_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="action" label="操作类型" width="110">
        <template #default="scope">
          <el-tag size="small" :type="getActionTagType(scope.row.action)">
            {{ getActionLabel(scope.row.action) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="result" label="操作结果" width="110">
        <template #default="scope">
          <el-tag :type="getResultTagType(scope.row.result)" size="small">
            {{ getResultLabel(scope.row.result) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="详情" width="90" align="center">
        <template #default="scope">
          <el-button link type="primary" size="small" @click="showDetail(scope.row)">查看</el-button>
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

    <el-dialog title="操作详情" v-model="detailVisible" width="640px">
      <el-descriptions :column="1" border v-if="detailRow">
        <el-descriptions-item label="操作时间">{{ formatTime(detailRow.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="操作用户">{{ detailRow.username }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ detailRow.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="子系统">{{ detailRow.subsystem_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="服务">{{ detailRow.service_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="操作类型">{{ getActionLabel(detailRow.action) }}</el-descriptions-item>
        <el-descriptions-item label="操作结果">
          <el-tag :type="getResultTagType(detailRow.result)" size="small">
            {{ getResultLabel(detailRow.result) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="耗时">{{ detailRow.duration != null ? detailRow.duration + ' ms' : '-' }}</el-descriptions-item>
        <el-descriptions-item label="详细信息">
          <pre class="detail-output">{{ detailRow.output || '-' }}</pre>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import axios from '@/utils/axios'
import ListStats from '@/components/ListStats.vue'

const route = useRoute()

const logs = ref([])
const total = ref(0)
const totalAll = ref(0)
const appliedFiltered = ref(false)
const statsItems = computed(() => {
  const items = [{ label: '日志总数', value: `${totalAll.value} 条` }]
  if (appliedFiltered.value) {
    items.push({ label: '筛选结果', value: `${total.value} 条` })
  }
  items.push({ label: '本页', value: `${logs.value.length} 条` })
  return items
})
const currentPage = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const projects = ref([])
const subsystems = ref([])
const dateRange = ref([])

const detailVisible = ref(false)
const detailRow = ref(null)

const filters = reactive({
  project_id: '',
  subsystem_id: '',
  service_id: '',
  service_name: '',
  username: '',
  action: '',
  result: ''
})

const ACTION_LABELS = {
  SERVICE_START: '启动',
  SERVICE_STOP: '停止',
  SERVICE_RESTART: '重启',
  SERVICE_CREATE: '新增',
  SERVICE_UPDATE: '编辑',
  SERVICE_DELETE: '删除',
  SERVICE_IMPORT: '发布',
  IMPORT_REVERT: '发布回滚'
}

const getActionLabel = (action) => ACTION_LABELS[action] || action || '-'

const getActionTagType = (action) => {
  if (action === 'SERVICE_START') return 'success'
  if (action === 'SERVICE_STOP') return 'warning'
  if (action === 'SERVICE_RESTART') return 'primary'
  if (action === 'SERVICE_DELETE') return 'danger'
  return 'info'
}

const getResultLabel = (result) => {
  if (result === 'success') return '成功'
  if (result === 'failed') return '失败'
  if (result === 'partial') return '部分成功'
  return result || '-'
}

const getResultTagType = (result) => {
  if (result === 'success') return 'success'
  if (result === 'failed') return 'danger'
  if (result === 'partial') return 'warning'
  return 'info'
}

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
    // 项目列表加载失败不阻塞记录查询
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
  const params = { page, limit: pageSize.value }
  if (filters.project_id) params.project_id = filters.project_id
  if (filters.subsystem_id) params.subsystem_id = filters.subsystem_id
  if (filters.service_id) params.service_id = filters.service_id
  if (filters.service_name) params.service_name = filters.service_name.trim()
  if (filters.username) params.username = filters.username
  if (filters.action) params.action = filters.action
  if (filters.result) params.result = filters.result
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_time = dateRange.value[0]
    params.end_time = dateRange.value[1]
  }
  return params
}

async function loadLogs(page = 1) {
  loading.value = true
  try {
    const params = buildParams(page)
    // 服务名称等服务端已支持下推，直接使用后端返回的分页与总数
    const response = await axios.get('/api/audit', { params })
    if (response.data.code === 0) {
      const data = response.data.data || {}
      logs.value = data.items || []
      total.value = data.total
      // 日志总数：数据范围内不受筛选影响的总量
      totalAll.value = data.total_all ?? data.total
      // 是否带筛选（page / limit 之外的参数即视为筛选条件）
      appliedFiltered.value = Object.keys(params).some(key => key !== 'page' && key !== 'limit')
      currentPage.value = page
    }
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  loadLogs(1)
}

function handleReset() {
  filters.project_id = ''
  filters.subsystem_id = ''
  filters.service_name = ''
  filters.username = ''
  filters.action = ''
  filters.result = ''
  dateRange.value = []
  subsystems.value = []
  loadLogs(1)
}

function handlePageChange(page) {
  loadLogs(page)
}

function handleSizeChange(size) {
  pageSize.value = size
  loadLogs(1)
}

function showDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

// 支持从服务管理页跳转带入筛选条件
const applyRouteQuery = async () => {
  const q = route.query
  // 清空无 query 时残留的筛选
  if (!q.project_id) filters.project_id = ''
  if (!q.subsystem_id) filters.subsystem_id = ''
  if (!q.service_id) filters.service_id = ''

  if (q.project_id) {
    filters.project_id = Number(q.project_id)
    await loadSubsystems(filters.project_id)
  }
  if (q.subsystem_id) filters.subsystem_id = Number(q.subsystem_id)
  if (q.service_id) filters.service_id = Number(q.service_id)
}

// keep-alive 缓存下 onMounted 只走一次，后续从服务详情跳转过来时 query 会变
// 监听 route.query 变化（immediate: true 保证首次进入也执行）
watch(() => JSON.stringify(route.query), () => {
  applyRouteQuery().then(() => loadLogs(1))
}, { immediate: true })

onMounted(async () => {
  await loadProjects()
})
</script>

<style scoped>
.audit-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: var(--app-text);
}

/* 筛选区样式与告警中心保持一致 */
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

/* 日期范围保持固定宽度，不被弹性拉伸 */
.filter-bar :deep(.el-date-editor) {
  flex: none;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

.detail-output {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
}
</style>
