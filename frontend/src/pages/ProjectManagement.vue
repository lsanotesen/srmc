<template>
  <div class="project-management-page">
    <div class="page-header">
      <div class="header-left">
        <h2>项目管理</h2>
        <p class="subtitle">管理后台程序的项目分组</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreate">
          <el-icon name="plus" :size="18" />
          新建项目
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-input 
        v-model="filters.keyword" 
        placeholder="搜索项目名称/编码" 
        @keyup.enter="loadProjects"
        class="search-input"
      />
      <el-button @click="loadProjects">搜索</el-button>
    </div>

    <el-card class="project-card">
      <el-table :data="filteredProjects" border>
        <el-table-column prop="name" label="项目名称" min-width="150">
          <template #default="scope">
            <div class="project-name-cell">
              <el-icon name="folder-opened" :size="18" class="folder-icon" />
              <span>{{ scope.row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="项目编码" min-width="120" />
        <el-table-column prop="description" label="项目描述" min-width="200" />
        <el-table-column prop="created_at" label="创建时间" min-width="150">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="process_count" label="程序数量" min-width="100">
          <template #default="scope">
            <el-tag type="info" size="small">{{ scope.row.process_count || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button size="small" @click="editProject(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteProject(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="filteredProjects.length === 0" class="empty-state">
        <el-icon name="folder-opened" :size="48" class="empty-icon" />
        <p>暂无项目</p>
        <el-button type="primary" @click="showCreateDialog = true">新建项目</el-button>
      </div>
    </el-card>

    <el-dialog :title="isEditing ? '编辑项目' : '新建项目'" v-model="showCreateDialog" width="450px" @close="resetForm">
      <el-form ref="formRef" :model="projectForm" :rules="formRules" label-position="top">
        <el-form-item label="项目名称" prop="name">
          <el-input
            v-model="projectForm.name"
            placeholder="请输入项目名称"
            size="large"
          />
        </el-form-item>

        <el-form-item label="项目编码" prop="code" :disabled="isEditing">
          <el-input
            v-model="projectForm.code"
            placeholder="请输入项目编码，用于唯一标识"
            size="large"
            :disabled="isEditing"
          />
          <div class="form-tip">项目编码将用于系统内部识别，建议使用英文和下划线组合</div>
        </el-form-item>

        <el-form-item label="项目描述" prop="description">
          <el-input
            v-model="projectForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入项目描述（可选）"
            size="large"
            :maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="isSubmitting">
          {{ isSubmitting ? '保存中...' : (isEditing ? '保存修改' : '创建项目') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from '@/utils/axios'

const router = useRouter()
const formRef = ref(null)
const isSubmitting = ref(false)
const showCreateDialog = ref(false)
const isEditing = ref(false)

const projects = ref([])

const filters = reactive({
  keyword: ''
})

const projectForm = reactive({
  id: null,
  name: '',
  code: '',
  description: ''
})

const formRules = {
  name: [
    { required: true, message: '请输入项目名称', trigger: 'blur' },
    { min: 2, max: 100, message: '项目名称长度为 2-100 个字符', trigger: 'blur' }
  ],
  code: [
    { required: true, message: '请输入项目编码', trigger: 'blur' },
    { pattern: /^[a-zA-Z][a-zA-Z0-9_]*$/, message: '编码必须以字母开头，只能包含字母、数字和下划线', trigger: 'blur' },
    { min: 2, max: 50, message: '项目编码长度为 2-50 个字符', trigger: 'blur' }
  ]
}

const filteredProjects = computed(() => {
  let result = projects.value
  if (filters.keyword) {
    const keyword = filters.keyword.toLowerCase()
    result = result.filter(p =>
      p.name.toLowerCase().includes(keyword) ||
      p.code.toLowerCase().includes(keyword)
    )
  }
  return result
})

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function resetForm() {
  Object.assign(projectForm, {
    id: null,
    name: '',
    code: '',
    description: ''
  })
  isEditing.value = false
}

function handleCreate() {
  console.log('handleCreate clicked')
  resetForm()
  showCreateDialog.value = true
}

function editProject(row) {
  Object.assign(projectForm, {
    id: row.id,
    name: row.name,
    code: row.code,
    description: row.description
  })
  isEditing.value = true
  showCreateDialog.value = true
}

async function deleteProject(row) {
  if (row.process_count && row.process_count > 0) {
    ElMessage.warning('项目下存在程序，请先删除程序')
    return
  }

  const result = await ElMessageBox.confirm(`确定删除项目 "${row.name}" 吗？`)
  if (result !== 'confirm') return

  try {
    const token = localStorage.getItem('token')
    const response = await axios.delete(`/api/projects/${row.id}`, {
      headers: { Authorization: `Bearer ${token}` }
    })

    if (response.data.code === 0) {
      ElMessage.success('删除成功')
      await loadProjects()
    } else {
      ElMessage.error(response.data.message || '删除失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

async function submitForm() {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch (error) {
    return
  }

  isSubmitting.value = true

  try {
    const token = localStorage.getItem('token')
    let response

    if (isEditing.value) {
      response = await axios.put(`/api/projects/${projectForm.id}`, {
        name: projectForm.name,
        description: projectForm.description
      }, {
        headers: { Authorization: `Bearer ${token}` }
      })
    } else {
      response = await axios.post('/api/projects', projectForm, {
        headers: { Authorization: `Bearer ${token}` }
      })
    }

    if (response.data.code === 0) {
      ElMessage.success(isEditing.value ? '修改成功' : '创建成功')
      showCreateDialog.value = false
      resetForm()
      await loadProjects()
    } else {
      ElMessage.error(response.data.message || (isEditing.value ? '修改失败' : '创建失败'))
    }
  } catch (error) {
    if (error.response) {
      ElMessage.error(error.response.data.detail || (isEditing.value ? '修改失败' : '创建失败'))
    } else {
      ElMessage.error('网络错误，请稍后重试')
    }
  } finally {
    isSubmitting.value = false
  }
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

onMounted(async () => {
  await loadProjects()
})
</script>

<style scoped>
.project-management-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 15px;
}

.header-left h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
}

.subtitle {
  margin: 0;
  color: #718096;
  font-size: 14px;
}

.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.search-input {
  width: 300px;
}

.project-card {
  border-radius: 12px;
}

.project-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.folder-icon {
  color: #60a5fa;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #94a3b8;
}

.empty-icon {
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state p {
  margin: 0 0 16px 0;
}

.form-tip {
  font-size: 12px;
  color: #a0aec0;
  margin-top: 4px;
}
</style>
