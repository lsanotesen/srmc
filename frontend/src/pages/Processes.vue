<template>
  <div class="processes-page">
    <div class="page-header">
      <div class="header-left">
        <h2>后台程序管理</h2>
        <div class="project-selector">
          <el-select v-model="selectedProject" placeholder="选择项目" class="project-select">
            <el-option label="全部项目" value="" />
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="showImportDialog = true">
          <el-icon name="upload" :size="18" />
          导入程序
        </el-button>
        <el-button type="success" @click="showAddDialog = true">
          <el-icon name="plus" :size="18" />
          新增程序
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-select v-model="filters.language" placeholder="语言类型" clearable>
        <el-option label="全部" value="" />
        <el-option label="Java" value="JAVA" />
        <el-option label="Python" value="PYTHON" />
        <el-option label="Go" value="GO" />
        <el-option label="Node.js" value="NODEJS" />
        <el-option label="Shell" value="SHELL" />
      </el-select>
      <el-select v-model="filters.status" placeholder="状态" clearable>
        <el-option label="全部" value="" />
        <el-option label="运行中" value="RUNNING" />
        <el-option label="已停止" value="STOPPED" />
        <el-option label="异常" value="ERROR" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索程序名称/编码" @keyup.enter="loadProcesses" />
      <el-button @click="loadProcesses">搜索</el-button>
    </div>

    <div class="project-tree">
      <el-tree
        :data="projectTree"
        :props="{ label: 'name', children: 'processes' }"
        :highlight-current="true"
        :expand-on-click-node="false"
        @node-click="handleNodeClick"
        class="tree"
      >
        <template #default="{ node, data }">
          <span class="tree-node">
            <el-icon v-if="data.type === 'project'" :name="node.expanded ? 'folder-opened' : 'folder'" class="node-icon" />
            <el-icon v-else name="file-text" class="node-icon file-icon" />
            <span class="node-label">{{ node.label }}</span>
            <el-tag v-if="data.type === 'project' && data.status_count" size="small" class="node-badge">
              {{ data.status_count.running || 0 }}/{{ data.status_count.total || 0 }}
            </el-tag>
          </span>
        </template>
      </el-tree>
    </div>

    <div class="content-area">
      <el-table :data="filteredProcesses" border @selection-change="handleSelectionChange">
        <el-table-column type="selection" />
        <el-table-column prop="process_name" label="程序名称" min-width="150">
          <template #default="scope">
            <div class="process-name-cell">
              <el-icon :name="getLanguageIcon(scope.row.language)" :size="18" class="lang-icon" />
              <span>{{ scope.row.process_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="process_code" label="程序编码" min-width="120" />
        <el-table-column prop="language" label="语言" min-width="80">
          <template #default="scope">
            <el-tag :type="getLanguageTagType(scope.row.language)" size="small">{{ scope.row.language }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="所属项目" min-width="120">
          <template #default="scope">
            <el-tag type="info" size="small">{{ scope.row.project_name || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" min-width="100" />
        <el-table-column prop="environment" label="环境" min-width="80">
          <template #default="scope">
            <el-tag :type="getEnvType(scope.row.environment)" size="small">{{ scope.row.environment }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" min-width="120" />
        <el-table-column prop="port" label="端口" min-width="80" />
        <el-table-column prop="status" label="状态" min-width="100">
          <template #default="scope">
            <div class="status-badge" :class="scope.row.status.toLowerCase()">
              <span class="status-dot"></span>
              <span>{{ scope.row.status }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="负责人" min-width="100" />
        <el-table-column label="操作" width="220">
          <template #default="scope">
            <el-button size="small" @click="viewProcess(scope.row)">查看</el-button>
            <el-button size="small" @click="editProcess(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteProcess(scope.row)">删除</el-button>
            <template v-if="scope.row.status !== 'RUNNING'">
              <el-button size="small" type="success" @click="startProcess(scope.row)">启动</el-button>
            </template>
            <template v-else>
              <el-button size="small" type="danger" @click="stopProcess(scope.row)">停止</el-button>
              <el-button size="small" @click="restartProcess(scope.row)">重启</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <div class="batch-actions">
        <el-button type="primary" @click="batchStart" :disabled="selectedProcesses.length === 0">批量启动</el-button>
        <el-button type="danger" @click="batchStop" :disabled="selectedProcesses.length === 0">批量停止</el-button>
        <el-button @click="batchRestart" :disabled="selectedProcesses.length === 0">批量重启</el-button>
      </div>
    </div>

    <el-dialog title="新增/编辑程序" v-model="showAddDialog" width="600px" @close="resetForm">
      <el-form :model="processForm" label-width="120px">
        <el-form-item label="程序名称" required>
          <el-input v-model="processForm.process_name" placeholder="请输入程序名称" />
        </el-form-item>
        <el-form-item label="程序编码" required>
          <el-input v-model="processForm.process_code" :disabled="!!processForm.id" />
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="processForm.project_id" placeholder="选择项目">
            <el-option label="无项目" value="" />
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="语言类型" required>
          <el-select v-model="processForm.language">
            <el-option v-for="lang in languages" :key="lang.value" :label="lang.label" :value="lang.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="模块">
          <el-input v-model="processForm.module" />
        </el-form-item>
        <el-form-item label="环境" required>
          <el-select v-model="processForm.environment">
            <el-option v-for="env in environments" :key="env" :label="env" :value="env" />
          </el-select>
        </el-form-item>
        <el-form-item label="IP地址" required>
          <el-input v-model="processForm.ip" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input v-model.number="processForm.port" />
        </el-form-item>
        <el-form-item label="工作目录">
          <el-input v-model="processForm.work_dir" />
        </el-form-item>
        <el-form-item label="启动命令">
          <el-input v-model="processForm.start_command" placeholder="如: java -jar app.jar" />
        </el-form-item>
        <el-form-item label="停止命令">
          <el-input v-model="processForm.stop_command" placeholder="如: kill -9 %PID%" />
        </el-form-item>
        <el-form-item label="检测类型">
          <el-select v-model="processForm.check_type">
            <el-option v-for="type in checkTypes" :key="type" :label="type" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item label="检测关键词">
          <el-input v-model="processForm.check_keyword" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="processForm.owner" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="processForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveProcess">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog title="程序详情" v-model="showDetailDialog">
      <el-descriptions :column="2" :data="selectedProcess">
        <el-descriptions-item label="程序名称" prop="process_name" />
        <el-descriptions-item label="程序编码" prop="process_code" />
        <el-descriptions-item label="语言类型" prop="language" />
        <el-descriptions-item label="所属项目" prop="project_name" />
        <el-descriptions-item label="模块" prop="module" />
        <el-descriptions-item label="环境" prop="environment" />
        <el-descriptions-item label="IP" prop="ip" />
        <el-descriptions-item label="端口" prop="port" />
        <el-descriptions-item label="工作目录" prop="work_dir" />
        <el-descriptions-item label="启动命令" prop="start_command" />
        <el-descriptions-item label="状态" prop="status">
          <template #content>
            <el-tag :type="getStatusType(selectedProcess?.status)">{{ selectedProcess?.status }}</el-tag>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="负责人" prop="owner" />
      </el-descriptions>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog title="导入程序" v-model="showImportDialog">
      <el-upload
        class="upload-demo"
        :auto-upload="false"
        :on-change="handleFileChange"
        accept=".xlsx"
      >
        <el-button type="primary">选择文件</el-button>
      </el-upload>
      <p class="import-tip">支持.xlsx格式文件，可先下载模板</p>
      <el-button @click="downloadTemplate">下载模板</el-button>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="doImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from '@/utils/axios'

const router = useRouter()

const processes = ref([])
const projects = ref([])
const selectedProcesses = ref([])
const selectedProject = ref('')
const selectedProcess = ref(null)

const showAddDialog = ref(false)
const showDetailDialog = ref(false)
const showImportDialog = ref(false)
const importFile = ref(null)

const filters = reactive({
  language: '',
  status: '',
  keyword: ''
})

const processForm = reactive({
  id: null,
  process_name: '',
  process_code: '',
  project_id: '',
  language: 'JAVA',
  module: '',
  environment: 'DEV',
  ip: '',
  port: null,
  work_dir: '',
  start_command: '',
  stop_command: '',
  check_type: 'PROCESS',
  check_keyword: '',
  owner: '',
  remark: ''
})

const languages = [
  { label: 'Java', value: 'JAVA' },
  { label: 'Python', value: 'PYTHON' },
  { label: 'Go', value: 'GO' },
  { label: 'Node.js', value: 'NODEJS' },
  { label: 'Shell', value: 'SHELL' },
  { label: 'Other', value: 'OTHER' }
]

const environments = ['DEV', 'TEST', 'STAGING', 'PROD']
const checkTypes = ['PROCESS', 'PORT', 'PID', 'SCRIPT', 'HTTP', 'TCP']

const filteredProcesses = computed(() => {
  let result = processes.value
  if (selectedProject.value) {
    result = result.filter(p => p.project_id === selectedProject.value)
  }
  if (filters.language) {
    result = result.filter(p => p.language === filters.language)
  }
  if (filters.status) {
    result = result.filter(p => p.status === filters.status)
  }
  if (filters.keyword) {
    const keyword = filters.keyword.toLowerCase()
    result = result.filter(p =>
      p.process_name.toLowerCase().includes(keyword) ||
      p.process_code.toLowerCase().includes(keyword)
    )
  }
  return result
})

const projectTree = computed(() => {
  const tree = []
  const projectMap = {}

  processes.value.forEach(p => {
    const projectId = p.project_id || 'no-project'
    const projectName = p.project_name || '未分类'

    if (!projectMap[projectId]) {
      projectMap[projectId] = {
        id: projectId,
        name: projectName,
        type: 'project',
        processes: [],
        status_count: { running: 0, total: 0 }
      }
    }

    projectMap[projectId].processes.push({
      id: p.id,
      name: p.process_name,
      type: 'process',
      status: p.status
    })

    projectMap[projectId].status_count.total++
    if (p.status === 'RUNNING') {
      projectMap[projectId].status_count.running++
    }
  })

  Object.values(projectMap).forEach(project => {
    tree.push(project)
  })

  return tree
})

function getStatusType(status) {
  switch (status) {
    case 'RUNNING': return 'success'
    case 'STOPPED': return 'danger'
    case 'ERROR': return 'warning'
    default: return 'info'
  }
}

function getLanguageIcon(language) {
  const iconMap = {
    'JAVA': 'coffee',
    'PYTHON': 'file-code',
    'GO': 'rocket',
    'NODEJS': 'circle-dot',
    'SHELL': 'terminal',
    'OTHER': 'file-text'
  }
  return iconMap[language] || 'file-text'
}

function getLanguageTagType(language) {
  const typeMap = {
    'JAVA': 'success',
    'PYTHON': 'warning',
    'GO': 'primary',
    'NODEJS': 'info',
    'SHELL': 'danger',
    'OTHER': 'info'
  }
  return typeMap[language] || 'info'
}

function getEnvType(env) {
  switch (env) {
    case 'PROD': return 'danger'
    case 'STAGING': return 'warning'
    case 'TEST': return 'info'
    case 'DEV': return 'success'
    default: return 'info'
  }
}

function handleNodeClick(data) {
  if (data.type === 'project') {
    selectedProject.value = data.id === 'no-project' ? '' : data.id
  } else {
    const process = processes.value.find(p => p.id === data.id)
    if (process) {
      viewProcess(process)
    }
  }
}

function handleSelectionChange(val) {
  selectedProcesses.value = val
}

function goToCreateProject() {
  router.push('/project/create')
}

async function loadProjects() {
  const token = localStorage.getItem('token')
  const response = await axios.get('/api/projects', {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (response.data.code === 0) {
    projects.value = response.data.data
  }
}

async function loadProcesses() {
  const token = localStorage.getItem('token')
  const params = {}
  if (selectedProject.value) params.project_id = selectedProject.value
  if (filters.language) params.language = filters.language
  if (filters.status) params.status = filters.status
  if (filters.keyword) params.keyword = filters.keyword

  const response = await axios.get('/api/processes', {
    headers: { Authorization: `Bearer ${token}` },
    params
  })
  if (response.data.code === 0) {
    processes.value = response.data.data
  }
}

function resetForm() {
  Object.assign(processForm, {
    id: null,
    process_name: '',
    process_code: '',
    project_id: '',
    language: 'JAVA',
    module: '',
    environment: 'DEV',
    ip: '',
    port: null,
    work_dir: '',
    start_command: '',
    stop_command: '',
    check_type: 'PROCESS',
    check_keyword: '',
    owner: '',
    remark: ''
  })
}

async function saveProcess() {
  const token = localStorage.getItem('token')
  let result
  if (processForm.id) {
    result = await axios.put(`/api/processes/${processForm.id}`, processForm, {
      headers: { Authorization: `Bearer ${token}` }
    })
  } else {
    result = await axios.post('/api/processes', processForm, {
      headers: { Authorization: `Bearer ${token}` }
    })
  }

  if (result.data.code === 0) {
    ElMessage.success(processForm.id ? '更新成功' : '创建成功')
    showAddDialog.value = false
    resetForm()
    await loadProcesses()
  } else {
    ElMessage.error(result.data.message)
  }
}

function editProcess(row) {
  Object.assign(processForm, {
    id: row.id,
    process_name: row.process_name,
    process_code: row.process_code,
    project_id: row.project_id || '',
    language: row.language,
    module: row.module || '',
    environment: row.environment,
    ip: row.ip,
    port: row.port,
    work_dir: row.work_dir || '',
    start_command: row.start_command || '',
    stop_command: row.stop_command || '',
    check_type: row.check_type || 'PROCESS',
    check_keyword: row.check_keyword || '',
    owner: row.owner || '',
    remark: row.remark || ''
  })
  showAddDialog.value = true
}

async function deleteProcess(row) {
  const token = localStorage.getItem('token')
  if (await ElMessage.confirm(`确定删除程序 ${row.process_name} 吗？`)) {
    const result = await axios.delete(`/api/processes/${row.id}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (result.data.code === 0) {
      ElMessage.success('删除成功')
      await loadProcesses()
    } else {
      ElMessage.error(result.data.message)
    }
  }
}

function viewProcess(row) {
  selectedProcess.value = row
  showDetailDialog.value = true
}

async function startProcess(row) {
  const token = localStorage.getItem('token')
  const result = await axios.post(`/api/processes/${row.id}/start`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (result.data.code === 0) {
    ElMessage.success('启动成功')
    await loadProcesses()
  } else {
    ElMessage.error(result.data.message)
  }
}

async function stopProcess(row) {
  const token = localStorage.getItem('token')
  const result = await axios.post(`/api/processes/${row.id}/stop`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (result.data.code === 0) {
    ElMessage.success('停止成功')
    await loadProcesses()
  } else {
    ElMessage.error(result.data.message)
  }
}

async function restartProcess(row) {
  const token = localStorage.getItem('token')
  const result = await axios.post(`/api/processes/${row.id}/restart`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (result.data.code === 0) {
    ElMessage.success('重启成功')
    await loadProcesses()
  } else {
    ElMessage.error(result.data.message)
  }
}

async function batchStart() {
  const token = localStorage.getItem('token')
  const ids = selectedProcesses.value.map(p => p.id)
  const result = await axios.post('/api/processes/batch/start', ids, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (result.data.code === 0) {
    ElMessage.success('批量启动完成')
    await loadProcesses()
  }
}

async function batchStop() {
  const token = localStorage.getItem('token')
  const ids = selectedProcesses.value.map(p => p.id)
  const result = await axios.post('/api/processes/batch/stop', ids, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (result.data.code === 0) {
    ElMessage.success('批量停止完成')
    await loadProcesses()
  }
}

async function batchRestart() {
  const token = localStorage.getItem('token')
  const ids = selectedProcesses.value.map(p => p.id)
  const result = await axios.post('/api/processes/batch/restart', ids, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (result.data.code === 0) {
    ElMessage.success('批量重启完成')
    await loadProcesses()
  }
}

function handleFileChange(file) {
  importFile.value = file.raw
}

async function downloadTemplate() {
  try {
    const token = localStorage.getItem('token')
    const response = await axios.get('/api/import/processes/template', {
      headers: { Authorization: `Bearer ${token}` },
      responseType: 'blob'
    })
    
    const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'process_import_template.xlsx'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error('下载模板失败')
  }
}

async function doImport() {
  if (!importFile.value) {
    ElMessage.error('请选择文件')
    return
  }

  const token = localStorage.getItem('token')
  const formData = new FormData()
  formData.append('file', importFile.value)

  try {
    const result = await axios.post('/api/import/processes', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
        'Authorization': `Bearer ${token}`
      }
    })

    if (result.data.code === 0) {
      const data = result.data.data
      ElMessage.success(`导入完成：新增${data.added}条，更新${data.updated}条，失败${data.failed}条`)
      showImportDialog.value = false
      importFile.value = null
      await loadProcesses()
      await loadProjects()
    } else {
      ElMessage.error(result.data.message)
    }
  } catch (error) {
    ElMessage.error('导入失败：' + (error.response?.data?.message || error.message))
  }
}

onMounted(async () => {
  await loadProjects()
  await loadProcesses()
})
</script>

<style scoped>
.processes-page {
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 15px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
}

.project-selector {
  display: flex;
  align-items: center;
  gap: 10px;
}

.project-select {
  width: 200px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.filter-bar > * {
  width: 180px;
}

.project-tree {
  width: 280px;
  border-right: 1px solid #e2e8f0;
  padding-right: 20px;
  height: calc(100vh - 220px);
  overflow-y: auto;
}

.tree {
  border: none;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-icon {
  font-size: 14px;
  color: #94a3b8;
}

.node-icon.file-icon {
  color: #60a5fa;
}

.node-label {
  flex: 1;
  font-size: 13px;
}

.node-badge {
  font-size: 11px;
  padding: 2px 8px;
}

.content-area {
  flex: 1;
  overflow: auto;
}

.process-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.lang-icon {
  color: #64748b;
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

.status-badge.error {
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

.status-badge.error .status-dot {
  background: #f59e0b;
}

@keyframes pulse-green {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(1.2);
  }
}

.batch-actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

.upload-demo {
  margin-bottom: 20px;
}

.import-tip {
  color: #6b7280;
  font-size: 14px;
}
</style>
