<template>
  <div class="deploy-tasks-page">
    <div class="page-header">
      <h1>批量部署任务</h1>
      <div class="actions">
        <el-button
          type="danger"
          plain
          :disabled="selectedTasks.length === 0"
          @click="batchDeleteTasks"
        >批量删除{{ selectedTasks.length ? `（${selectedTasks.length}）` : '' }}</el-button>
        <el-button @click="$router.push('/agents')">返回 Agent 管理</el-button>
        <el-button type="primary" @click="loadTasks">刷新</el-button>
      </div>
    </div>

    <div class="table-wrapper">
      <el-table :data="tasks" border fit @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" :selectable="canSelect" />
        <el-table-column prop="task_id" label="任务ID" width="150" show-overflow-tooltip>
          <template #default="scope">
            <span style="font-family: monospace; font-size: 12px;">{{ scope.row.task_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="部署方式" width="110">
          <template #default="scope">
            <el-tag :type="scope.row.package_type === 'docker' ? 'warning' : 'primary'" size="small">
              {{ typeLabel(scope.row.package_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="120" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ scope.row.version || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="deploy_dir" label="部署目录" min-width="160" show-overflow-tooltip />
        <el-table-column label="总数/成功/失败/执行中" width="180" align="center">
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
        <el-table-column label="操作" width="210" align="center">
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
            <el-button
              v-if="!['waiting', 'running'].includes(scope.row.status)"
              size="small"
              type="danger"
              text
              @click="deleteTask(scope.row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog title="部署任务详情" v-model="showDetail" width="1000px">
      <div v-if="currentTask" class="task-meta">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="任务ID">{{ currentTask.task_id }}</el-descriptions-item>
          <el-descriptions-item label="部署方式">{{ typeLabel(currentTask.package_type) }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ currentTask.version || '-' }}</el-descriptions-item>
          <el-descriptions-item label="部署目录">{{ currentTask.deploy_dir }}</el-descriptions-item>
          <el-descriptions-item label="后端地址" :span="2">{{ currentTask.server_url }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <el-table :data="detailItems" border style="margin-top: 16px;" v-loading="detailLoading">
        <el-table-column prop="host" label="主机IP" width="130" show-overflow-tooltip />
        <el-table-column prop="port" label="端口" width="70" />
        <el-table-column prop="ssh_username" label="SSH用户" width="90" />
        <el-table-column prop="hostname" label="主机名" min-width="120" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="scope">
            <el-tag :type="itemStatusType(scope.row.status)">{{ itemStatusLabel(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_step" label="当前步骤" min-width="150" show-overflow-tooltip />
        <el-table-column label="进度" width="110">
          <template #default="scope">
            <el-progress :percentage="scope.row.progress" :status="scope.row.status === 'failed' ? 'exception' : undefined" />
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-dialog>

    <el-dialog title="重试失败主机" v-model="showRetryDialog" width="880px">
      <div style="margin-bottom: 10px; color: #909399; font-size: 12px; line-height: 1.6;">
        仅重试失败/已取消/已跳过的主机，已成功的不受影响。可逐台修改 SSH 用户与密码（各主机可不同，本任务只需填这一次）；
        密码留空则使用任务创建时保存的密码。非 root 用户会自动尝试 sudo 提权（复用该登录密码）。
      </div>
      <el-table :data="retryItems" border size="small">
        <el-table-column prop="host" label="主机IP" width="130" show-overflow-tooltip />
        <el-table-column prop="port" label="端口" width="70" />
        <el-table-column label="SSH 用户" width="160">
          <template #default="scope">
            <el-input v-model="scope.row.ssh_username" size="small" placeholder="root" />
          </template>
        </el-table-column>
        <el-table-column label="SSH 密码" min-width="220">
          <template #default="scope">
            <el-input
              v-model="scope.row.new_password"
              type="password"
              show-password
              size="small"
              placeholder="留空则使用已保存的密码"
            />
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="上次错误" min-width="180" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <el-button @click="showRetryDialog = false">取消</el-button>
        <el-button type="warning" :loading="retrying" @click="submitRetry">确认重试</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from '@/utils/axios'

const tasks = ref([])
const selectedTasks = ref([])
const showDetail = ref(false)
const currentTask = ref(null)
const detailItems = ref([])
const detailLoading = ref(false)
const showRetryDialog = ref(false)
const retryRow = ref(null)
const retryItems = ref([])
const retrying = ref(false)
let timer = null

const typeLabel = (t) => (t === 'docker' ? 'Docker' : '二进制')

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
    const res = await axios.get('/api/agent-deploy/tasks')
    if (res.data.code === 0) {
      tasks.value = res.data.data || []
    } else {
      ElMessage.error(res.data.message || '加载部署任务列表失败')
    }
  } catch (err) {
    ElMessage.error('加载部署任务列表失败')
  }
}

// 执行中的任务不允许勾选删除
const canSelect = (row) => !['waiting', 'running'].includes(row.status)
const handleSelectionChange = (rows) => { selectedTasks.value = rows }

const deleteTask = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定删除部署任务 ${row.task_id} 吗？将同时删除其全部主机明细，此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '返回', type: 'warning' }
    )
  } catch (e) {
    return
  }
  try {
    const res = await axios.delete(`/api/agent-deploy/tasks/${row.task_id}`)
    if (res.data.code === 0) {
      ElMessage.success('任务已删除')
      if (showDetail.value && currentTask.value?.task_id === row.task_id) {
        showDetail.value = false
      }
      loadTasks()
    } else {
      ElMessage.error(res.data.message || '删除失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '删除失败')
  }
}

const batchDeleteTasks = async () => {
  const ids = selectedTasks.value.map(t => t.task_id)
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${ids.length} 个部署任务吗？将同时删除全部主机明细，此操作不可恢复。`,
      '批量删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '返回', type: 'warning' }
    )
  } catch (e) {
    return
  }
  try {
    const res = await axios.post('/api/agent-deploy/tasks/batch-delete', { task_ids: ids })
    if (res.data.code === 0) {
      ElMessage.success(res.data.message || '删除成功')
      if (showDetail.value && ids.includes(currentTask.value?.task_id)) {
        showDetail.value = false
      }
      selectedTasks.value = []
      loadTasks()
    } else {
      ElMessage.error(res.data.message || '删除失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '删除失败')
  }
}

const loadDetail = async (taskId) => {
  detailLoading.value = true
  try {
    const res = await axios.get(`/api/agent-deploy/tasks/${taskId}`)
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
      `确定取消部署任务 ${row.task_id} 吗？未开始的主机将被标记为已取消，进行中的主机无法中断。`,
      '取消确认',
      { confirmButtonText: '确定取消', cancelButtonText: '返回', type: 'warning' }
    )
  } catch (e) {
    return
  }
  try {
    const res = await axios.post(`/api/agent-deploy/tasks/${row.task_id}/cancel`)
    if (res.data.code === 0) {
      ElMessage.success('任务已取消')
      loadTasks()
    } else {
      ElMessage.error(res.data.message || '取消失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '取消失败')
  }
}

const retryTask = async (row) => {
  retryRow.value = row
  try {
    const res = await axios.get(`/api/agent-deploy/tasks/${row.task_id}`)
    if (res.data.code !== 0) {
      ElMessage.error(res.data.message || '加载任务详情失败')
      return
    }
    const items = (res.data.data?.items || []).filter(i => ['failed', 'skipped', 'cancelled'].includes(i.status))
    if (!items.length) {
      ElMessage.warning('没有可重试的主机（全部成功）')
      return
    }
    retryItems.value = items.map(i => ({ ...i, new_password: '' }))
    showRetryDialog.value = true
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '加载任务详情失败')
  }
}

// 逐台提交：各主机可填不同用户名/密码；密码留空则沿用已保存的密码
const submitRetry = async () => {
  retrying.value = true
  try {
    const credentials = retryItems.value.map(i => ({
      id: i.id,
      ssh_username: (i.ssh_username || '').trim(),
      ssh_password: i.new_password || '',
    }))
    const res = await axios.post(
      `/api/agent-deploy/tasks/${retryRow.value.task_id}/retry`,
      { credentials }
    )
    if (res.data.code === 0) {
      ElMessage.success(res.data.message || '重试任务已提交')
      showRetryDialog.value = false
      loadTasks()
      if (showDetail.value && currentTask.value?.task_id === retryRow.value.task_id) {
        loadDetail(retryRow.value.task_id)
      }
    } else {
      ElMessage.error(res.data.message || '重试失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '重试失败')
  } finally {
    retrying.value = false
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
.deploy-tasks-page {
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
