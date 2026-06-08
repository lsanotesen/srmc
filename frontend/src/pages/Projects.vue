<template>
  <div class="projects-page">
    <div class="page-header">
      <div class="header-left">
        <h1>项目列表</h1>
        <p class="subtitle">管理系统中的项目信息</p>
      </div>
      <div class="actions">
        <el-button type="primary" icon="plus" @click="showAddDialog = true">新增项目</el-button>
        <el-button icon="download" @click="downloadTemplate">下载模板</el-button>
        <el-button icon="upload" @click="showImportDialog = true">导入项目</el-button>
        <el-button icon="export" @click="exportProjects">导出项目</el-button>
      </div>
    </div>

    <div class="table-card">
      <div class="table-header">
        <div class="header-left">
          <span class="table-title">项目列表</span>
          <span class="table-count">共 {{ pagination.total }} 条记录</span>
        </div>
        <div class="header-right">
          <el-input 
            v-model="filters.keyword" 
            placeholder="搜索项目名称或编码" 
            class="search-input" 
            @keyup.enter="loadProjects"
            clearable
          />
          <el-button type="primary" icon="search" @click="loadProjects">搜索</el-button>
          <el-button icon="refresh" @click="resetFilters">重置</el-button>
        </div>
      </div>
      
      <el-table 
        :data="projects" 
        border 
        class="project-table"
        :header-cell-style="{ backgroundColor: '#f8fafc', color: '#334155', fontWeight: '600' }"
        :row-style="{ transition: 'all 0.2s' }"
      >
        <el-table-column type="index" label="序号" width="80" align="center" />
        <el-table-column prop="name" label="项目名称" min-width="200">
          <template #default="scope">
            <div class="name-cell">
              <span class="name-text">{{ scope.row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="项目编码" min-width="150" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.code" type="info" size="small">{{ scope.row.code }}</el-tag>
            <span v-else class="empty-text">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="项目描述" min-width="300">
          <template #default="scope">
            <span :class="['description-text', { 'empty-text': !scope.row.description }]">
              {{ scope.row.description || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" align="center" fixed="right">
          <template #default="scope">
            <div class="action-buttons">
              <el-button type="primary" size="small" @click="viewProject(scope.row)">查看</el-button>
              <el-button type="success" size="small" @click="editProject(scope.row)">编辑</el-button>
              <el-button type="danger" size="small" @click="deleteProject(scope.row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          :current-page="pagination.page"
          :page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
          class="project-pagination"
        />
      </div>
    </div>

    <el-dialog 
      :title="projectForm.id ? '编辑项目' : '新增项目'" 
      v-model="showAddDialog" 
      width="600px" 
      @close="resetForm"
      :close-on-click-modal="false"
    >
      <el-form :model="projectForm" label-width="100px" class="project-form">
        <el-form-item label="项目名称" required>
          <el-input 
            v-model="projectForm.name" 
            placeholder="请输入项目名称" 
          />
        </el-form-item>
        <el-form-item label="项目编码">
          <el-input 
            v-model="projectForm.code" 
            placeholder="请输入项目编码（可选）" 
          />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input 
            v-model="projectForm.description" 
            type="textarea" 
            :rows="4" 
            placeholder="请输入项目描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveProject">
          {{ projectForm.id ? '更新' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog title="项目详情" v-model="showDetailDialog" width="500px">
      <el-descriptions :column="1" border v-if="selectedProject">
        <el-descriptions-item label="项目名称">
          <span class="detail-name">{{ selectedProject.name }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="项目编码">
          {{ selectedProject.code || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="项目描述">
          {{ selectedProject.description || '-' }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog title="导入项目" v-model="showImportDialog" width="500px">
      <div class="import-content">
        <el-upload
          class="upload-demo"
          :auto-upload="false"
          :on-change="handleFileChange"
          accept=".xlsx"
          :show-file-list="false"
        >
          <div class="upload-area">
            <el-icon name="upload" :size="48" color="#94a3b8" class="upload-icon" />
            <p class="upload-text">点击或拖拽文件到此处上传</p>
            <p class="upload-hint">支持 .xlsx 格式文件，可先下载模板</p>
          </div>
        </el-upload>
        <div v-if="importFile" class="file-info">
          <el-icon name="file-text" :size="20" color="#22c55e" class="file-icon" />
          <span class="file-name">{{ importFile.name }}</span>
          <el-button size="small" type="text" @click="importFile = null">移除</el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="doImport" :disabled="!importFile">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from '@/utils/axios'

const projects = ref([])
const pagination = reactive({
  page: 1,
  size: 10,
  total: 0
})

const filters = reactive({
  keyword: ''
})

const showAddDialog = ref(false)
const showDetailDialog = ref(false)
const showImportDialog = ref(false)
const importFile = ref(null)
const selectedProject = ref(null)

const projectForm = reactive({
  id: null,
  name: '',
  code: '',
  description: ''
})

const loadProjects = async () => {
  try {
    const params = new URLSearchParams()
    params.append('page', pagination.page)
    params.append('size', pagination.size)
    if (filters.keyword) {
      params.append('name', filters.keyword)
    }

    const response = await axios.get(`/api/projects?${params}`)
    if (response.data.code === 0) {
      projects.value = response.data.data.items
      pagination.total = response.data.data.total
    }
  } catch (error) {
    ElMessage.error('加载项目列表失败')
  }
}

const resetForm = () => {
  projectForm.id = null
  projectForm.name = ''
  projectForm.code = ''
  projectForm.description = ''
}

const resetFilters = () => {
  filters.keyword = ''
  loadProjects()
}

const viewProject = (project) => {
  selectedProject.value = project
  showDetailDialog.value = true
}

const editProject = (project) => {
  projectForm.id = project.id
  projectForm.name = project.name
  projectForm.code = project.code || ''
  projectForm.description = project.description || ''
  showAddDialog.value = true
}

const saveProject = async () => {
  if (!projectForm.name.trim()) {
    ElMessage.error('请输入项目名称')
    return
  }

  try {
    let response
    if (projectForm.id) {
      response = await axios.put(`/api/projects/${projectForm.id}`, {
        name: projectForm.name,
        code: projectForm.code || null,
        description: projectForm.description || null
      })
    } else {
      response = await axios.post('/api/projects', {
        name: projectForm.name,
        code: projectForm.code || null,
        description: projectForm.description || null
      })
    }

    if (response.data.code === 0) {
      ElMessage.success(projectForm.id ? '更新成功' : '新增成功')
      showAddDialog.value = false
      resetForm()
      loadProjects()
    } else {
      ElMessage.error(response.data.message || '操作失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '操作失败')
  }
}

const deleteProject = async (project) => {
  if (!confirm(`确定要删除项目 "${project.name}" 吗？`)) return

  try {
    const response = await axios.delete(`/api/projects/${project.id}`)
    if (response.data.code === 0) {
      ElMessage.success('删除成功')
      loadProjects()
    } else {
      ElMessage.error(response.data.message || '删除失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '删除失败')
  }
}

const handlePageChange = (page) => {
  pagination.page = page
  loadProjects()
}

const handleSizeChange = (size) => {
  pagination.size = size
  pagination.page = 1
  loadProjects()
}

const downloadTemplate = async () => {
  try {
    const response = await axios.get('/api/projects/template', { responseType: 'blob' })
    const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'projects_template.xlsx'
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  } catch (error) {
    ElMessage.error('下载模板失败')
  }
}

const exportProjects = async () => {
  try {
    const params = new URLSearchParams()
    if (filters.keyword) params.append('name', filters.keyword)

    const response = await axios.get(`/api/projects/export?${params}`, { responseType: 'blob' })
    const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'projects.xlsx'
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

const handleFileChange = (file) => {
  importFile.value = file.raw
}

const doImport = async () => {
  if (!importFile.value) {
    ElMessage.error('请选择要导入的文件')
    return
  }

  const formData = new FormData()
  formData.append('file', importFile.value)

  try {
    const response = await axios.post('/api/projects/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    if (response.data.code === 0) {
      ElMessage.success(response.data.data.message)
      showImportDialog.value = false
      loadProjects()
    } else {
      ElMessage.error(response.data.message || '导入失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '导入失败')
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.projects-page {
  padding: 24px;
  background-color: #f1f5f9;
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 20px 24px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.header-left {
  h1 {
    font-size: 24px;
    font-weight: 600;
    color: #1e293b;
    margin: 0 0 8px 0;
  }
  
  .subtitle {
    font-size: 14px;
    color: #64748b;
    margin: 0;
  }
}

.actions {
  display: flex;
  gap: 10px;
}

.table-card {
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e2e8f0;
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
    
    .table-title {
      font-size: 16px;
      font-weight: 600;
      color: #1e293b;
    }
    
    .table-count {
      font-size: 14px;
      color: #64748b;
    }
  }
  
  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
    
    .search-input {
      width: 300px;
      border-radius: 8px;
    }
  }
}

.project-table {
  --el-table-border-color: #e2e8f0;
  --el-table-row-hover-bg-color: #f8fafc;
  
  tr {
    height: 60px;
  }
  
  .el-table__cell {
    padding: 12px 16px;
  }
}

.name-cell {
  .name-text {
    font-weight: 500;
    color: #1e293b;
  }
}

.empty-text {
  color: #94a3b8;
}

.description-text {
  color: #475569;
  line-height: 1.5;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.pagination-wrapper {
  padding: 20px 24px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
}

.project-pagination {
  --el-pagination-item-bg-color: #f8fafc;
  --el-pagination-item-active-bg-color: #3b82f6;
}

.project-form {
  padding: 10px 0;
}

.detail-name {
  font-weight: 600;
  font-size: 16px;
  color: #1e293b;
}

.import-content {
  padding: 10px 0;
}

.upload-area {
  border: 2px dashed #cbd5e1;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  transition: all 0.3s;
  cursor: pointer;
  
  &:hover {
    border-color: #3b82f6;
    background-color: #eff6ff;
  }
  
  .upload-icon {
    margin-bottom: 12px;
  }
  
  .upload-text {
    font-size: 16px;
    font-weight: 500;
    color: #334155;
    margin: 0 0 8px 0;
  }
  
  .upload-hint {
    font-size: 14px;
    color: #94a3b8;
    margin: 0;
  }
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background-color: #f0fdf4;
  border-radius: 8px;
  margin-top: 16px;
  
  .file-icon {
    flex-shrink: 0;
  }
  
  .file-name {
    flex: 1;
    font-size: 14px;
    color: #1e293b;
  }
}
</style>
