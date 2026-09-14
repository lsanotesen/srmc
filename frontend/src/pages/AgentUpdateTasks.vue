<template>
  <div class="update-tasks-page">
    <div class="page-header">
      <h1>批量更新任务</h1>
      <div class="actions">
        <el-button @click="$router.push('/agents')">返回 Agent 管理</el-button>
        <el-button type="primary" @click="loadTasks">刷新</el-button>
      </div>
    </div>

    <div class="table-wrapper">
      <el-table :data="tasks" border fit @selection-change="() => {}">
        <el-table-column prop="task_id" label="任务ID" width="150" show-overflow-tooltip>
          <template #default="scope">
            <span style="font-family: monospace; font-size: 12px;">{{ scope.row.task_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="更新类型" width="110">
          <template #default="scope">
            <el-tag :type="scope.row.update_type === 'docker' ? 'warning' : 'primary'" size="small">
              {{ typeLabel(scope.row.update_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="120" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ scope.row.version || scope.row.image_tag || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="文件" min-width="180" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ scope.row.file_name }}（{{ formatBytes(scope.row.file_size) }}）</span>
          </template>
        </el-table-column>
        <el-table-column label="目标/成功/失败/执行中" width="200" align="center">
          <template #default="scope">
            <span>
              {{ scope.row.total_count }} / {{ scope.row.success_count }} / {{ scope.row.failed_count }} / {{ scope.row.running_count }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_by" label="创建人" width="110" show-overflow-tooltip />
        <el-table-column label="创建时间" width="170">
          <template #default="scope">
            <span>{{ formatDateTime(scope.row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="scope">
            <el-tag :type="taskStatusType(scope.row.status)">{{ taskStatusLabel(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center">
          <template #default="scope">
            <el-button size="small" type="primary" plain @click="openDetail(scope.row)">详情</el-button>
            <el-button
              v-if="['waiting', 'running'].includes(scope.row.status)"
              size="small"
              type="danger"
              plain
              @click="cancelTask(scope.row)"
            >取消</el-button>
            <el-button
              v-if="['failed', 'partial', 'cancelled'].includes(scope.row.status)"
              size="small"
              type="warning"
              plain
              @click="retryTask(scope.row)"
            >重试失败</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog title="任务详情" v-model="showDetail" width="920px">
      <div v-if="currentTask" class="task-meta">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="任务ID">{{ currentTask.task_id }}</el-descriptions-item>
          <el-descriptions-item label="更新类型">{{ typeLabel(currentTask.update_type) }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ currentTask.version || currentTask.image_tag || '-' }}</el-descriptions-item>
          <el-descriptions-item label="镜像/文件名">{{ currentTask.file_name }}</el-descriptions-item>
          <el-descriptions-item label="SHA256" :span="2">
            <span style="font-size: 12px; font-family: monospace; word-break: break-all;">{{ currentTask.file_sha256 }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <el-table :data="detailItems" border style="margin-top: 16px;" v-loading="detailLoading">
        <el-table-column prop="hostname" label="主机名" min-width="130" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP" width="130" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="scope">
            <el-tag :type="itemStatusType(scope.row.status)">{{ itemStatusLabel(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_step" label="当前步骤" min-width="140" show-overflow-tooltip />
        <el-table-column label="进度" width="110">
          <template #default="scope">
            <el-progress :percentage="scope.row.progress" :status="scope.row.status === 'failed' ? 'exception' : undefined" />
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="170">
          <template #default="scope">
            <span>{{ formatDateTime(scope.row.started_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="结束时间" width="170">
          <template #default="scope">
            <span>{{ formatDateTime(scope.row.finished_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" min-width="180" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from '@/utils/axios'

const tasks = ref([])
const showDetail = ref(false)
const currentTask = ref(null)
const detailItems = ref([])
const detailLoading = ref(false)
let timer = null

const typeLabel = (t) => (t === 'docker' ? 'Docker 镜像' : '二进制文件')

const taskStatusMap = {
  waiting: { label: '等待中', type: 'info' },
  running: { label: '执行中', type: 'warning' },
  success: { label: '成功', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  partial: { label: '部分成功', type: 'warning' },
  cancelled: { label: '已取消', type: 'info' }
}

const itemStatusMap = {
  waiting: { label: '等待中', type: 'info' },
  running: { label: '执行中', type: 'warning' },
  success: { label: '成功', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' },
  skipped: { label: '已跳过', type: 'info' }
}

const taskStatusLabel = (s) => (taskStatusMap[s] || { label: s }).label
const taskStatusType = (s) => (taskStatusMap[s] || { type: 'info' }).type
const itemStatusLabel = (s) => (itemStatusMap[s] || { label: s }).label
const itemStatusType = (s) => (itemStatusMap[s] || { type: 'info' }).type

const formatBytes = (bytes) => {
  if (!bytes) return '0 B'
  if (bytes >= 1024 * 1024 * 1024) return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
  if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(2) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return bytes + ' B'
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })
}

const loadTasks = async () => {
  try {
    const res = await axios.get('/api/agent-update/tasks')
    if (res.data.code === 0) {
      tasks.value = res.data.data || []
    } else {
      ElMessage.error(res.data.message || '加载任务列表失败')
    }
  } catch (err) {
    ElMessage.error('加载任务列表失败')
  }
}

const loadDetail = async (taskId) => {
  detailLoading.value = true
  try {
    const res = await axios.get(`/api/agent-update/tasks/${taskId}`)
    if (res.data.code === 0) {
      currentTask.value = res.data.data
      detailItems.value = res.data.data.items || []
    } else {
      ElMessage.error(res.data.message || '加载任务详情失败')
    }
  } catch (err) {
    ElMessage.error('加载任务详情失败')
  } finally {
    detailLoading.value = false
  }
}

const openDetail = (row) => {
  showDetail.value = true
  loadDetail(row.task_id)
}

const cancelTask = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定取消任务 ${row.task_id} 吗？未执行的 Agent 将被标记为已取消。`,
      '取消确认',
      { confirmButtonText: '确定取消', cancelButtonText: '返回', type: 'warning' }
    )
  } catch (e) {
    return
  }
  try {
    const res = await axios.post(`/api/agent-update/tasks/${row.task_id}/cancel`)
    if (res.data.code === 0) {
      ElMessage.success('任务已取消')
      loadTasks()
    } else {
      ElMessage.error(res.data.message || '取消失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '取消失败')
  }
}

const retryTask = async (row) => {
  const failedCount = row.failed_count + row.cancelled_count
  try {
    await ElMessageBox.confirm(
      `将重试任务 ${row.task_id} 中 ${failedCount} 台失败/取消的 Agent，已成功的保持不变。确认重试？`,
      '重试确认',
      { confirmButtonText: '确认重试', cancelButtonText: '返回', type: 'warning' }
    )
  } catch (e) {
    return
  }
  try {
    const res = await axios.post(`/api/agent-update/tasks/${row.task_id}/retry`)
    if (res.data.code === 0) {
      ElMessage.success(res.data.message || '重试任务已提交')
      loadTasks()
    } else {
      ElMessage.error(res.data.message || '重试失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '重试失败')
  }
}

onMounted(() => {
  loadTasks()
  timer = setInterval(() => {
    loadTasks()
    if (showDetail.value && currentTask.value) {
      loadDetail(currentTask.value.task_id)
    }
  }, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.update-tasks-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  margin: 0;
}

.actions {
  display: flex;
  gap: 10px;
}

.table-wrapper {
  overflow-x: auto;
}

.task-meta {
  margin-bottom: 8px;
}
</style>