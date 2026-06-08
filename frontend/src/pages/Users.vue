<template>
  <div class="users-page">
    <div class="page-header">
      <h2>用户管理</h2>
      <el-button type="success" @click="showAddDialog = true">
        <el-icon component="Plus" />
        新增用户
      </el-button>
    </div>
    
    <el-table :data="users" border>
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="role" label="角色">
        <template #default="scope">
          <el-tag :type="getRoleType(scope.row.role)">{{ getRoleLabel(scope.row.role) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="email" label="邮箱" />
      <el-table-column prop="phone" label="电话" />
      <el-table-column prop="is_active" label="状态">
        <template #default="scope">
          <el-switch :value="scope.row.is_active" @change="toggleUserStatus(scope.row)" />
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" />
      <el-table-column label="操作">
        <template #default="scope">
          <el-button size="small" @click="editUser(scope.row)">编辑</el-button>
          <el-button size="small" @click="resetPassword(scope.row)">重置密码</el-button>
          <el-button size="small" @click="deleteUser(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    
    <el-dialog title="新增/编辑用户" :visible="showAddDialog" @close="resetForm">
      <el-form :model="userForm" label-width="120px">
        <el-form-item label="用户名">
          <el-input v-model="userForm.username" :disabled="!!userForm.id" />
        </el-form-item>
        <el-form-item label="密码" v-if="!userForm.id">
          <el-input v-model="userForm.password" type="password" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role">
            <el-option v-for="role in roles" :key="role.value" :label="role.label" :value="role.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="userForm.phone" />
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
import { ElMessage } from 'element-plus'
import axios from '@/utils/axios'

const users = ref([])
const showAddDialog = ref(false)

const userForm = reactive({
  id: null,
  username: '',
  password: '',
  role: 'READONLY',
  email: '',
  phone: ''
})

const roles = [
  { value: 'ADMIN', label: '管理员' },
  { value: 'OPS', label: '运维' },
  { value: 'DEV', label: '开发' },
  { value: 'READONLY', label: '只读' }
]

function getRoleType(role) {
  switch (role) {
    case 'ADMIN': return 'danger'
    case 'OPS': return 'primary'
    case 'DEV': return 'warning'
    default: return 'info'
  }
}

function getRoleLabel(role) {
  const roleMap = { ADMIN: '管理员', OPS: '运维', DEV: '开发', READONLY: '只读' }
  return roleMap[role] || role
}

function resetForm() {
  Object.assign(userForm, {
    id: null,
    username: '',
    password: '',
    role: 'READONLY',
    email: '',
    phone: ''
  })
}

async function loadUsers() {
  const response = await axios.get('/api/users')
  if (response.data.code === 0) {
    users.value = response.data.data
  }
}

async function saveUser() {
  try {
    let result
    if (userForm.id) {
      result = await axios.put(`/api/users/${userForm.id}`, userForm)
    } else {
      if (!userForm.password) {
        ElMessage.error('请设置密码')
        return
      }
      result = await axios.post('/api/users', userForm)
    }
    
    if (result.data.code === 0) {
      ElMessage.success(userForm.id ? '更新成功' : '创建成功')
      showAddDialog.value = false
      resetForm()
      await loadUsers()
    } else {
      ElMessage.error(result.data.message)
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

function editUser(row) {
  Object.assign(userForm, {
    id: row.id,
    username: row.username,
    password: '',
    role: row.role,
    email: row.email || '',
    phone: row.phone || ''
  })
  showAddDialog.value = true
}

async function resetPassword(row) {
  const newPassword = prompt('请输入新密码：')
  if (!newPassword) return
  
  const result = await axios.put(`/api/users/${row.id}`, { password: newPassword })
  if (result.data.code === 0) {
    ElMessage.success('密码重置成功')
  } else {
    ElMessage.error(result.data.message)
  }
}

async function deleteUser(row) {
  if (await ElMessage.confirm(`确定删除用户 ${row.username} 吗？`)) {
    const result = await axios.delete(`/api/users/${row.id}`)
    if (result.data.code === 0) {
      ElMessage.success('删除成功')
      await loadUsers()
    } else {
      ElMessage.error(result.data.message)
    }
  }
}

async function toggleUserStatus(row) {
  const result = await axios.put(`/api/users/${row.id}`, { is_active: !row.is_active })
  if (result.data.code === 0) {
    row.is_active = !row.is_active
    ElMessage.success(row.is_active ? '已启用' : '已禁用')
  } else {
    ElMessage.error(result.data.message)
  }
}

onMounted(() => {
  loadUsers()
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
  margin-bottom: 20px;
}
</style>