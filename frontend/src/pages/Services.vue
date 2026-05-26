<template>
  <div class="services-page">
    <div class="page-header">
      <h2>服务管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showImportDialog = true">
          <el-icon component="Upload" />
          导入服务
        </el-button>
        <el-button type="success" @click="showAddDialog = true">
          <el-icon component="Plus" />
          新增服务
        </el-button>
      </div>
    </div>
    
    <div class="filter-bar">
      <el-select v-model="filters.service_type" placeholder="服务类型" clearable>
        <el-option label="全部" value="" />
        <el-option label="APP" value="APP" />
        <el-option label="NGINX" value="NGINX" />
        <el-option label="REDIS" value="REDIS" />
        <el-option label="MYSQL" value="MYSQL" />
        <el-option label="KINGBASE" value="KINGBASE" />
        <el-option label="DAMENG" value="DAMENG" />
        <el-option label="ELASTICSEARCH" value="ELASTICSEARCH" />
        <el-option label="RABBITMQ" value="RABBITMQ" />
      </el-select>
      <el-select v-model="filters.environment" placeholder="环境" clearable>
        <el-option label="全部" value="" />
        <el-option label="DEV" value="DEV" />
        <el-option label="TEST" value="TEST" />
        <el-option label="STAGING" value="STAGING" />
        <el-option label="PROD" value="PROD" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索服务名称/编码" @keyup.enter="loadServices" />
      <el-button @click="loadServices">搜索</el-button>
    </div>
    
    <el-table :data="services" border @selection-change="handleSelectionChange">
      <el-table-column type="selection" />
      <el-table-column prop="service_name" label="服务名称" />
      <el-table-column prop="service_code" label="服务编码" />
      <el-table-column prop="service_type" label="服务类型" />
      <el-table-column prop="module" label="模块" />
      <el-table-column prop="environment" label="环境" />
      <el-table-column prop="ip" label="IP" />
      <el-table-column prop="port" label="端口" />
      <el-table-column prop="status" label="状态">
        <template #default="scope">
          <el-tag :type="getStatusType(scope.row.status)">{{ scope.row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="owner" label="负责人" />
      <el-table-column label="操作">
        <template #default="scope">
          <el-button size="small" @click="viewService(scope.row)">查看</el-button>
          <el-button size="small" @click="editService(scope.row)">编辑</el-button>
          <el-button size="small" @click="deleteService(scope.row)">删除</el-button>
          <template v-if="scope.row.capabilities?.includes('start_stop')">
            <el-button size="small" type="success" @click="startService(scope.row)" v-if="scope.row.status !== 'RUNNING'">
              启动
            </el-button>
            <el-button size="small" type="danger" @click="stopService(scope.row)" v-if="scope.row.status === 'RUNNING'">
              停止
            </el-button>
            <el-button size="small" @click="restartService(scope.row)">重启</el-button>
          </template>
          <template v-if="scope.row.capabilities?.includes('log_view')">
            <el-button size="small" @click="viewLogs(scope.row)">日志</el-button>
          </template>
          <template v-if="scope.row.capabilities?.includes('web_shell')">
            <el-button size="small" @click="openShell(scope.row)">Shell</el-button>
          </template>
          <template v-if="scope.row.capabilities?.includes('sql_console')">
            <el-button size="small" @click="openSQL(scope.row)">SQL</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>
    
    <div class="batch-actions">
      <el-button type="primary" @click="batchStart" :disabled="selectedServices.length === 0">批量启动</el-button>
      <el-button type="danger" @click="batchStop" :disabled="selectedServices.length === 0">批量停止</el-button>
      <el-button @click="batchRestart" :disabled="selectedServices.length === 0">批量重启</el-button>
    </div>
    
    <el-dialog title="新增/编辑服务" :visible="showAddDialog" @close="resetForm">
      <el-form :model="serviceForm" label-width="120px">
        <el-form-item label="服务名称">
          <el-input v-model="serviceForm.service_name" />
        </el-form-item>
        <el-form-item label="服务编码">
          <el-input v-model="serviceForm.service_code" :disabled="!!serviceForm.id" />
        </el-form-item>
        <el-form-item label="服务类型">
          <el-select v-model="serviceForm.service_type">
            <el-option v-for="type in serviceTypes" :key="type" :label="type" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item label="模块">
          <el-input v-model="serviceForm.module" />
        </el-form-item>
        <el-form-item label="环境">
          <el-select v-model="serviceForm.environment">
            <el-option v-for="env in environments" :key="env" :label="env" :value="env" />
          </el-select>
        </el-form-item>
        <el-form-item label="IP地址">
          <el-input v-model="serviceForm.ip" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input v-model.number="serviceForm.port" />
        </el-form-item>
        <el-form-item label="工作目录">
          <el-input v-model="serviceForm.work_dir" />
        </el-form-item>
        <el-form-item label="启动脚本">
          <el-input v-model="serviceForm.start_script" />
        </el-form-item>
        <el-form-item label="停止脚本">
          <el-input v-model="serviceForm.stop_script" />
        </el-form-item>
        <el-form-item label="检测类型">
          <el-select v-model="serviceForm.check_type">
            <el-option v-for="type in checkTypes" :key="type" :label="type" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item label="检测关键词">
          <el-input v-model="serviceForm.check_keyword" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="serviceForm.owner" />
        </el-form-item>
        <el-form-item label="备注">
          <el-textarea v-model="serviceForm.remark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveService">保存</el-button>
      </template>
    </el-dialog>
    
    <el-dialog title="导入服务" :visible="showImportDialog">
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
    
    <el-dialog title="服务详情" :visible="showDetailDialog">
      <el-descriptions :column="2" :data="selectedService">
        <el-descriptions-item label="服务名称" prop="service_name" />
        <el-descriptions-item label="服务编码" prop="service_code" />
        <el-descriptions-item label="服务类型" prop="service_type" />
        <el-descriptions-item label="环境" prop="environment" />
        <el-descriptions-item label="IP" prop="ip" />
        <el-descriptions-item label="端口" prop="port" />
        <el-descriptions-item label="工作目录" prop="work_dir" />
        <el-descriptions-item label="负责人" prop="owner" />
        <el-descriptions-item label="能力" prop="capabilities">
          <template #content>
            <el-tag v-for="cap in selectedService?.capabilities" :key="cap" size="small">{{ cap }}</el-tag>
          </template>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useServiceStore } from '../stores/service'
import { Upload, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const serviceStore = useServiceStore()

const services = ref([])
const selectedServices = ref([])
const showAddDialog = ref(false)
const showImportDialog = ref(false)
const showDetailDialog = ref(false)
const selectedService = ref(null)
const importFile = ref(null)

const filters = reactive({
  service_type: '',
  environment: '',
  keyword: ''
})

const serviceForm = reactive({
  id: null,
  service_name: '',
  service_code: '',
  service_type: 'APP',
  module: '',
  environment: 'DEV',
  ip: '',
  port: null,
  work_dir: '',
  start_script: '',
  stop_script: '',
  check_type: 'PROCESS',
  check_keyword: '',
  owner: '',
  remark: ''
})

const serviceTypes = ['APP', 'NGINX', 'REDIS', 'MYSQL', 'KINGBASE', 'DAMENG', 'ELASTICSEARCH', 'RABBITMQ', 'OTHER']
const environments = ['DEV', 'TEST', 'STAGING', 'PROD']
const checkTypes = ['PROCESS', 'PORT', 'PID', 'SCRIPT', 'HTTP', 'TCP']

function getStatusType(status) {
  switch (status) {
    case 'RUNNING': return 'success'
    case 'STOPPED': return 'danger'
    default: return 'warning'
  }
}

function handleSelectionChange(val) {
  selectedServices.value = val
}

async function loadServices() {
  const params = {}
  if (filters.service_type) params.service_type = filters.service_type
  if (filters.environment) params.environment = filters.environment
  if (filters.keyword) params.keyword = filters.keyword
  
  await serviceStore.getServices(params)
  services.value = serviceStore.services
}

function resetForm() {
  Object.assign(serviceForm, {
    id: null,
    service_name: '',
    service_code: '',
    service_type: 'APP',
    module: '',
    environment: 'DEV',
    ip: '',
    port: null,
    work_dir: '',
    start_script: '',
    stop_script: '',
    check_type: 'PROCESS',
    check_keyword: '',
    owner: '',
    remark: ''
  })
}

async function saveService() {
  try {
    let result
    if (serviceForm.id) {
      result = await serviceStore.updateService(serviceForm.id, serviceForm)
    } else {
      result = await serviceStore.createService(serviceForm)
    }
    
    if (result.code === 0) {
      ElMessage.success(serviceForm.id ? '更新成功' : '创建成功')
      showAddDialog.value = false
      resetForm()
      await loadServices()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

function editService(row) {
  Object.assign(serviceForm, {
    id: row.id,
    service_name: row.service_name,
    service_code: row.service_code,
    service_type: row.service_type,
    module: row.module || '',
    environment: row.environment,
    ip: row.ip,
    port: row.port,
    work_dir: row.work_dir || '',
    start_script: row.start_script || '',
    stop_script: row.stop_script || '',
    check_type: row.check_type || 'PROCESS',
    check_keyword: row.check_keyword || '',
    owner: row.owner || '',
    remark: row.remark || ''
  })
  showAddDialog.value = true
}

async function deleteService(row) {
  if (await ElMessage.confirm(`确定删除服务 ${row.service_name} 吗？`)) {
    const result = await serviceStore.deleteService(row.id)
    if (result.code === 0) {
      ElMessage.success('删除成功')
      await loadServices()
    } else {
      ElMessage.error(result.message)
    }
  }
}

function viewService(row) {
  selectedService.value = row
  showDetailDialog.value = true
}

async function startService(row) {
  const result = await serviceStore.startService(row.id)
  if (result.code === 0) {
    ElMessage.success('启动成功')
    await loadServices()
  } else {
    ElMessage.error(result.message)
  }
}

async function stopService(row) {
  const result = await serviceStore.stopService(row.id)
  if (result.code === 0) {
    ElMessage.success('停止成功')
    await loadServices()
  } else {
    ElMessage.error(result.message)
  }
}

async function restartService(row) {
  const result = await serviceStore.restartService(row.id)
  if (result.code === 0) {
    ElMessage.success('重启成功')
    await loadServices()
  } else {
    ElMessage.error(result.message)
  }
}

function viewLogs(row) {
  router.push(`/logs?serviceId=${row.id}`)
}

function openShell(row) {
  router.push(`/shell?serviceId=${row.id}`)
}

function openSQL(row) {
  router.push(`/sql?serviceId=${row.id}`)
}

async function batchStart() {
  const ids = selectedServices.value.map(s => s.id)
  const result = await axios.post('/api/monitor/batch/START', ids)
  if (result.data.code === 0) {
    ElMessage.success('批量启动完成')
    await loadServices()
  }
}

async function batchStop() {
  const ids = selectedServices.value.map(s => s.id)
  const result = await axios.post('/api/monitor/batch/STOP', ids)
  if (result.data.code === 0) {
    ElMessage.success('批量停止完成')
    await loadServices()
  }
}

async function batchRestart() {
  const ids = selectedServices.value.map(s => s.id)
  const result = await axios.post('/api/monitor/batch/RESTART', ids)
  if (result.data.code === 0) {
    ElMessage.success('批量重启完成')
    await loadServices()
  }
}

function handleFileChange(file) {
  importFile.value = file.raw
}

function downloadTemplate() {
  window.location.href = '/api/import/template'
}

async function doImport() {
  if (!importFile.value) {
    ElMessage.error('请选择文件')
    return
  }
  
  const formData = new FormData()
  formData.append('file', importFile.value)
  
  const result = await axios.post('/api/import/services', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  
  if (result.data.code === 0) {
    const data = result.data.data
    ElMessage.success(`导入完成：新增${data.added}条，更新${data.updated}条，失败${data.failed}条`)
    showImportDialog.value = false
    importFile.value = null
    await loadServices()
  } else {
    ElMessage.error(result.data.message)
  }
}

onMounted(() => {
  loadServices()
})
</script>

<style scoped>
.services-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
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