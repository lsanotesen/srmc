<template>
  <div class="role-page">
    <div class="page-header">
      <h2>角色管理</h2>
      <el-button type="primary" @click="openAddRoleDialog">
        <el-icon><Plus /></el-icon>
        新增角色
      </el-button>
    </div>

    <el-alert
      class="concept-tip"
      type="info"
      :closable="false"
      show-icon
    >
      <template #title>
        <span>系统角色仅用于分配功能权限（菜单/按钮/API）。项目内权限请在「项目详情 → 成员管理 / 共享管理」中配置。</span>
      </template>
    </el-alert>

    <el-card class="section-card">
      <template #header>
        <span class="section-title">角色列表</span>
      </template>
      <el-table
        :data="roles"
        border
        highlight-current-row
        @row-click="selectRole"
        size="default"
      >
        <el-table-column prop="name" label="角色名称" min-width="140" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip min-width="200" />
        <el-table-column label="系统内置" width="100">
          <template #default="scope">
            <el-tag v-if="scope.row.is_system" type="info" size="small">是</el-tag>
            <span v-else class="text-muted">否</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button type="primary" size="small" link :disabled="scope.row.is_system" @click.stop="editRole(scope.row)">编辑</el-button>
            <el-button type="danger" size="small" link :disabled="scope.row.is_system" @click.stop="deleteRole(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="section-card" v-if="currentRole">
      <template #header>
        <div class="card-header">
          <span class="section-title">功能权限分配 - {{ currentRole.name }}</span>
          <el-tag size="small" type="info">系统角色</el-tag>
        </div>
      </template>
      <div class="perm-section">
        <div class="perm-category" v-for="category in groupedPermissions" :key="category.key">
          <h4>{{ category.label }}</h4>
          <el-checkbox-group v-model="selectedPermissionIds" class="perm-checkbox-group">
            <el-checkbox
              v-for="perm in category.permissions"
              :key="perm.id"
              :value="perm.id"
              :label="perm.id"
            >
              {{ perm.name }}
            </el-checkbox>
          </el-checkbox-group>
        </div>
      </div>
      <div class="tab-footer">
        <el-button type="primary" @click="savePermissions">保存功能权限</el-button>
      </div>
    </el-card>

    <el-empty v-else description="请从上方选择一个角色进行功能权限分配" />

    <el-dialog :title="roleForm.id ? '编辑角色' : '新增角色'" v-model="showRoleDialog" width="500px">
      <el-form :model="roleForm" label-width="100px">
        <el-form-item label="角色名称" required>
          <el-input v-model="roleForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="roleForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRoleDialog = false">取消</el-button>
        <el-button type="primary" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import axios from '@/utils/axios'

const roles = ref([])
const permissions = ref([])
const currentRole = ref(null)
const selectedPermissionIds = ref([])

const showRoleDialog = ref(false)
const roleForm = reactive({ id: null, name: '', description: '' })

const groupedPermissions = computed(() => {
  const groups = {}
  const labels = {
    project: '项目管理',
    service: '服务管理',
    container: '容器管理',
    webshell: 'WebShell',
    log: '日志管理',
    script: '脚本管理',
    agent: 'Agent管理',
    host: '主机管理',
    organization: '组织管理',
    department: '部门管理',
    user: '用户管理',
    role: '角色管理',
    audit: '审计日志',
  }
  for (const perm of permissions.value) {
    const key = perm.resource
    if (!groups[key]) {
      groups[key] = { key, label: labels[key] || key, permissions: [] }
    }
    groups[key].permissions.push(perm)
  }
  return Object.values(groups)
})

const loadRoles = async () => {
  try {
    const response = await axios.get('/api/rbac/roles?include_system=true')
    if (response.data.code === 0) {
      roles.value = response.data.data
    }
  } catch (error) {
    ElMessage.error('加载角色列表失败')
  }
}

const loadPermissions = async () => {
  try {
    const response = await axios.get('/api/rbac/permissions')
    if (response.data.code === 0) {
      permissions.value = response.data.data
    }
  } catch (error) {
    ElMessage.error('加载权限列表失败')
  }
}

const selectRole = async (row) => {
  if (!row || !row.id) return
  currentRole.value = row
  try {
    const permRes = await axios.get(`/api/rbac/roles/${row.id}/permissions`)
    if (permRes.data.code === 0) {
      selectedPermissionIds.value = permRes.data.data.map(p => p.id)
    }
  } catch (error) {
    ElMessage.error('加载角色权限失败')
  }
}

const openAddRoleDialog = () => {
  Object.assign(roleForm, { id: null, name: '', description: '' })
  showRoleDialog.value = true
}

const editRole = (role) => {
  Object.assign(roleForm, { id: role.id, name: role.name, description: role.description })
  showRoleDialog.value = true
}

const saveRole = async () => {
  if (!roleForm.name) {
    ElMessage.error('请填写角色名称')
    return
  }
  try {
    let response
    if (roleForm.id) {
      response = await axios.put(`/api/rbac/roles/${roleForm.id}`, {
        name: roleForm.name, description: roleForm.description
      })
    } else {
      response = await axios.post('/api/rbac/roles', {
        name: roleForm.name, description: roleForm.description
      })
    }
    if (response.data.code === 0) {
      ElMessage.success('保存成功')
      showRoleDialog.value = false
      loadRoles()
    } else {
      ElMessage.error(response.data.message || response.data.detail || '保存失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

const deleteRole = async (role) => {
  try {
    await ElMessageBox.confirm(`确定要删除角色 "${role.name}" 吗？`, '确认', { type: 'warning' })
    const response = await axios.delete(`/api/rbac/roles/${role.id}`)
    if (response.data.code === 0) {
      ElMessage.success('删除成功')
      if (currentRole.value?.id === role.id) {
        currentRole.value = null
        selectedPermissionIds.value = []
      }
      loadRoles()
    } else {
      ElMessage.error(response.data.detail || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const savePermissions = async () => {
  if (!currentRole.value) return
  try {
    const response = await axios.post(`/api/rbac/roles/${currentRole.value.id}/permissions`, {
      permission_ids: selectedPermissionIds.value
    })
    if (response.data.code === 0) {
      ElMessage.success('功能权限保存成功')
    } else {
      ElMessage.error(response.data.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

onMounted(async () => {
  await Promise.all([loadRoles(), loadPermissions()])
})
</script>

<style scoped>
.role-page {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
.concept-tip {
  margin-bottom: 16px;
}
.section-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.section-title {
  font-weight: 600;
  font-size: 14px;
}
.text-muted {
  color: #909399;
}
.perm-section {
  max-height: 500px;
  overflow-y: auto;
  padding: 4px;
}
.perm-category {
  margin-bottom: 20px;
}
.perm-category h4 {
  margin: 0 0 10px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.perm-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}
.perm-checkbox-group .el-checkbox {
  margin-right: 0;
  margin-bottom: 4px;
}
.tab-footer {
  padding: 12px 4px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #f0f0f0;
  margin-top: 16px;
}
</style>
