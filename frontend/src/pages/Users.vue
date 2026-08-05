<template>
  <div class="users-page">
    <div class="page-header">
      <h2>用户管理</h2>
      <el-button v-if="hasPermission('user:add')" type="success" @click="openAddDialog">
        <el-icon><Plus /></el-icon>
        新增用户
      </el-button>
    </div>
    
    <el-table :data="users" border>
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="job_title" label="姓名" width="120">
        <template #default="scope">
          {{ scope.row.job_title || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="role" label="系统角色" width="120">
        <template #default="scope">
          <el-tag :type="getRoleType(scope.row.role)">{{ getRoleLabel(scope.row.role) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="所属组织" width="150">
        <template #default="scope">
          {{ scope.row.organization_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="所属部门" width="150">
        <template #default="scope">
          {{ scope.row.department_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="email" label="邮箱" width="160" />
      <el-table-column prop="phone" label="电话" width="130" />
      <el-table-column prop="is_active" label="状态" width="80">
        <template #default="scope">
          <el-switch
            :model-value="scope.row.is_active"
            :active-value="1"
            :inactive-value="0"
            @change="toggleUserStatus(scope.row)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="scope">
          <el-button v-if="hasPermission('user:edit')" size="small" @click="editUser(scope.row)">编辑</el-button>
          <el-button v-if="hasPermission('user:edit')" size="small" @click="resetPassword(scope.row)">重置密码</el-button>
          <el-button v-if="hasPermission('user:delete')" size="small" type="danger" @click="deleteUser(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    
    <el-dialog title="新增/编辑用户" v-model="showAddDialog" @close="resetForm" width="550px">
      <el-form :model="userForm" label-width="120px">
        <el-form-item label="用户名" required>
          <el-input v-model="userForm.username" :disabled="!!userForm.id" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="姓名" required>
          <el-input v-model="userForm.job_title" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="密码" v-if="!userForm.id" required>
          <el-input v-model="userForm.password" type="password" show-password placeholder="请设置初始密码" />
        </el-form-item>
        <el-form-item label="系统角色" required>
          <el-select v-model="userForm.role" style="width: 100%;" placeholder="请选择系统角色">
            <el-option v-for="role in systemRoles" :key="role.value" :label="role.label" :value="role.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属部门" required>
          <el-select v-model="userForm.department_id" clearable filterable style="width: 100%;" placeholder="请选择所属部门" @change="onDeptChange">
            <el-option v-for="dept in allDepartments" :key="dept.id" :label="dept.name" :value="dept.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属组织">
          <el-input v-model="userForm.organization_name" disabled placeholder="选择部门后自动带出" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="userForm.phone" placeholder="请输入电话" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import axios from '@/utils/axios'
import { usePermission } from '@/composables/usePermission'

const { hasPermission } = usePermission()

const users = ref([])
const organizations = ref([])
const allDepartments = ref([])
const showAddDialog = ref(false)

const userForm = reactive({
  id: null,
  username: '',
  password: '',
  job_title: '',
  role: 'READONLY',
  organization_id: null,
  organization_name: '',
  department_id: null,
  email: '',
  phone: ''
})

const systemRoles = [
  { value: 'SUPER_ADMIN', label: '超级管理员' },
  { value: 'ORG_ADMIN', label: '组织管理员' },
  { value: 'DEPT_ADMIN', label: '部门管理员' },
  { value: 'DEPT_MEMBER', label: '部门成员' },
  { value: 'READONLY', label: '只读用户' }
]

function getRoleType(role) {
  switch (role) {
    case 'SUPER_ADMIN': return 'danger'
    case 'ORG_ADMIN': return 'primary'
    case 'DEPT_ADMIN': return 'warning'
    case 'DEPT_MEMBER': return 'success'
    default: return 'info'
  }
}

function getRoleLabel(role) {
  const roleMap = { 
    SUPER_ADMIN: '超级管理员', 
    ORG_ADMIN: '组织管理员', 
    DEPT_ADMIN: '部门管理员',
    DEPT_MEMBER: '部门成员',
    READONLY: '只读用户' 
  }
  return roleMap[role] || role
}

function onDeptChange(deptId) {
  if (!deptId) {
    userForm.organization_id = null
    userForm.organization_name = ''
    return
  }
  const dept = allDepartments.value.find(d => d.id === deptId)
  if (dept) {
    userForm.organization_id = dept.organization_id
    const orgList = Array.isArray(organizations.value) ? organizations.value : []
    const org = orgList.find(o => o.id === dept.organization_id)
    userForm.organization_name = org ? org.name : ''
  }
}

function resetForm() {
  Object.assign(userForm, {
    id: null,
    username: '',
    password: '',
    job_title: '',
    role: 'READONLY',
    organization_id: null,
    organization_name: '',
    department_id: null,
    email: '',
    phone: ''
  })
}

function openAddDialog() {
  resetForm()
  showAddDialog.value = true
}

async function loadUsers() {
  try {
    const response = await axios.get('/api/users')
    if (response.data.code === 0) {
      users.value = response.data.data
    }
  } catch (error) {
    ElMessage.error('加载用户列表失败')
  }
}

async function loadOrganizations() {
  try {
    const response = await axios.get('/api/organizations?page=1&size=100')
    if (response.data.code === 0) {
      const data = response.data.data
      organizations.value = Array.isArray(data) ? data : (data.items || [])
    }
  } catch (error) {
    console.error('加载组织列表失败:', error)
  }
}

async function loadDepartments() {
  try {
    const response = await axios.get('/api/departments/tree-flat')
    if (response.data.code === 0) {
      allDepartments.value = response.data.data
    }
  } catch (error) {
    console.error('加载部门列表失败:', error)
  }
}

async function saveUser() {
  try {
    if (!userForm.username) {
      ElMessage.error('请输入用户名')
      return
    }
    if (!userForm.job_title) {
      ElMessage.error('请输入姓名')
      return
    }

    let result
    const payload = {
      username: userForm.username,
      role: userForm.role,
      job_title: userForm.job_title,
      organization_id: userForm.organization_id || null,
      department_id: userForm.department_id || null,
      email: userForm.email,
      phone: userForm.phone
    }

    if (userForm.id) {
      result = await axios.put(`/api/users/${userForm.id}`, payload)
    } else {
      if (!userForm.password) {
        ElMessage.error('请设置密码')
        return
      }
      payload.password = userForm.password
      result = await axios.post('/api/users', payload)
    }
    
    if (result.data.code === 0) {
      ElMessage.success(userForm.id ? '更新成功' : '创建成功')
      showAddDialog.value = false
      resetForm()
      await loadUsers()
    } else {
      ElMessage.error(result.data.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

function editUser(row) {
  const orgList = Array.isArray(organizations.value) ? organizations.value : []
  const org = orgList.find(o => o.id === row.organization_id)
  Object.assign(userForm, {
    id: row.id,
    username: row.username,
    password: '',
    job_title: row.job_title || '',
    role: row.role,
    organization_id: row.organization_id || null,
    organization_name: org ? org.name : (row.organization_name || ''),
    department_id: row.department_id || null,
    email: row.email || '',
    phone: row.phone || ''
  })
  showAddDialog.value = true
}

async function resetPassword(row) {
  const newPassword = prompt('请输入新密码：')
  if (!newPassword) return

  try {
    const result = await axios.put(`/api/users/${row.id}`, { password: newPassword })
    if (result.data.code === 0) {
      ElMessage.success('密码重置成功')
    } else {
      ElMessage.error(result.data.message || '重置失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '重置失败')
  }
}

async function deleteUser(row) {
  try {
    await ElMessageBox.confirm(`确定删除用户 ${row.username} 吗？`, '确认', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    const result = await axios.delete(`/api/users/${row.id}`)
    if (result.data.code === 0) {
      ElMessage.success('删除成功')
      await loadUsers()
    } else {
      ElMessage.error(result.data.message || '删除失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

async function toggleUserStatus(row) {
  try {
    const newStatus = row.is_active ? 0 : 1
    const result = await axios.put(`/api/users/${row.id}`, { is_active: newStatus })
    if (result.data.code === 0) {
      row.is_active = newStatus
      ElMessage.success(newStatus ? '已启用' : '已禁用')
    } else {
      ElMessage.error(result.data.message || '操作失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadOrganizations(), loadDepartments()])
})
</script>

<style scoped>
.users-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
</style>