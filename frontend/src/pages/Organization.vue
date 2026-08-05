<template>
  <div class="org-page">
    <div class="page-header">
      <h2>组织管理</h2>
      <el-button v-if="hasPermission('organization:edit')" type="primary" @click="openAddOrgDialog">
        <el-icon><Plus /></el-icon>
        新增组织
      </el-button>
    </div>

    <div class="org-container">
      <!-- 左侧组织列表 -->
      <div class="org-sidebar">
        <div class="sidebar-header">
          <span>组织列表</span>
          <el-badge :value="organizations.length" class="org-count" />
        </div>
        <div class="org-list">
          <div
            v-for="org in organizations"
            :key="org.id"
            :class="['org-item', { active: currentOrgId === org.id }]"
            @click="selectOrg(org)"
          >
            <div class="org-indicator" v-if="currentOrgId === org.id"></div>
            <div class="org-info">
              <div class="org-name">{{ org.name }}</div>
              <div class="org-code">{{ org.code }}</div>
            </div>
            <div class="org-actions" @click.stop>
              <el-tag :type="org.status ? 'success' : 'danger'" size="small" effect="plain" class="org-status-tag">
                {{ org.status ? '启用' : '禁用' }}
              </el-tag>
              <el-button
                v-if="hasPermission('organization:edit')"
                type="primary"
                size="small"
                link
                @click="editOrg(org)"
              >
                编辑
              </el-button>
              <el-button
                v-if="hasPermission('organization:edit')"
                type="danger"
                size="small"
                link
                @click="deleteOrg(org)"
              >
                删除
              </el-button>
            </div>
          </div>
          <el-empty v-if="organizations.length === 0" description="暂无组织" :image-size="60" />
        </div>
      </div>

      <!-- 右侧部门结构 -->
      <div class="org-content">
        <div class="content-header" v-if="currentOrg">
          <div class="content-title">
            <span class="title-icon">📁</span>
            <span>部门结构 - {{ currentOrg.name }}</span>
          </div>
          <el-button v-if="hasPermission('department:edit')" type="primary" size="default" @click="openAddDeptDialog(null)">
            <el-icon><Plus /></el-icon>
            新增根部门
          </el-button>
        </div>

        <div class="content-header empty" v-else>
          <span>请从左侧选择一个组织</span>
        </div>

        <div class="dept-content" v-if="currentOrgId">
          <el-table :data="deptFlatList" border size="default" row-key="id" :tree-props="{ children: 'children' }" default-expand-all>
            <el-table-column prop="name" label="部门名称" min-width="200">
              <template #default="scope">
                <span>{{ scope.row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="code" label="编码" width="140" />
            <el-table-column prop="leader_name" label="负责人" width="120">
              <template #default="scope">
                {{ scope.row.leader_name || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.status ? 'success' : 'danger'" size="small">
                  {{ scope.row.status ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="260" fixed="right">
              <template #default="scope">
                <el-button v-if="hasPermission('department:edit')" type="primary" size="small" link @click.stop="openAddDeptDialog(scope.row.id)">添加子部门</el-button>
                <el-button v-if="hasPermission('department:edit')" type="primary" size="small" link @click.stop="editDept(scope.row)">编辑</el-button>
                <el-button v-if="hasPermission('department:edit')" type="danger" size="small" link @click.stop="deleteDept(scope.row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="deptFlatList.length === 0" description="暂无部门，点击上方按钮新增" />
        </div>
      </div>
    </div>

    <!-- 新增/编辑组织弹窗 -->
    <el-dialog :title="orgForm.id ? '编辑组织' : '新增组织'" v-model="showAddOrgDialog" width="500px">
      <el-form :model="orgForm" label-width="100px">
        <el-form-item label="组织名称" required>
          <el-input v-model="orgForm.name" placeholder="请输入组织名称" />
        </el-form-item>
        <el-form-item label="组织编码" required>
          <el-input v-model="orgForm.code" :disabled="!!orgForm.id" placeholder="请输入唯一编码" />
        </el-form-item>
        <el-form-item label="Logo">
          <el-input v-model="orgForm.logo" placeholder="Logo URL (选填)" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="orgForm.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="orgForm.description" type="textarea" :rows="3" placeholder="请输入描述（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddOrgDialog = false">取消</el-button>
        <el-button type="primary" @click="saveOrg">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑部门弹窗 -->
    <el-dialog :title="deptForm.id ? '编辑部门' : '新增部门'" v-model="showAddDeptDialog" width="550px">
      <el-form :model="deptForm" label-width="100px">
        <el-form-item label="所属组织" required>
          <el-select v-model="deptForm.organization_id" style="width: 100%;" @change="onOrgChange">
            <el-option v-for="org in organizations" :key="org.id" :label="org.name" :value="org.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="上级部门">
          <el-select v-model="deptForm.parent_id" clearable style="width: 100%;" placeholder="为空则作为一级部门">
            <el-option v-for="dept in currentOrgDepts" :key="dept.id" :label="dept.name" :value="dept.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门名称" required>
          <el-input v-model="deptForm.name" placeholder="请输入部门名称" />
        </el-form-item>
        <el-form-item label="部门编码" required>
          <el-input v-model="deptForm.code" placeholder="请输入唯一编码" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="deptForm.leader_id" clearable filterable style="width: 100%;" placeholder="请选择负责人（选填）">
            <el-option v-for="user in orgUsers" :key="user.id" :label="user.job_title || user.username" :value="user.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="deptForm.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="deptForm.description" type="textarea" :rows="3" placeholder="请输入描述（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDeptDialog = false">取消</el-button>
        <el-button type="primary" @click="saveDept">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import axios from '@/utils/axios'
import { usePermission } from '@/composables/usePermission'

const { hasPermission } = usePermission()

const organizations = ref([])
const currentOrgId = ref(null)
const currentOrg = ref(null)
const deptTree = ref([])
const orgUsers = ref([])
const dialogDeptList = ref([])

const showAddOrgDialog = ref(false)
const showAddDeptDialog = ref(false)

const orgForm = reactive({ id: null, name: '', code: '', logo: '', description: '', status: 1 })
const deptForm = reactive({ id: null, organization_id: null, parent_id: null, name: '', code: '', leader_id: null, description: '', status: 1 })

const deptFlatList = computed(() => {
  return flattenTree(deptTree.value)
})

const currentOrgDepts = computed(() => {
  return dialogDeptList.value.filter(d => !d.children || d.children.length === 0)
})

function flattenTree(nodes, result = []) {
  for (const node of nodes) {
    const { children, ...item } = node
    result.push(item)
    if (children && children.length > 0) {
      flattenTree(children, result)
    }
  }
  return result
}

const loadOrganizations = async () => {
  try {
    const response = await axios.get('/api/organizations?page=1&size=100')
    if (response.data.code === 0) {
      organizations.value = response.data.data.items
      if (organizations.value.length > 0 && !currentOrgId.value) {
        selectOrg(organizations.value[0])
      }
    }
  } catch (error) {
    ElMessage.error('加载组织列表失败')
  }
}

const selectOrg = async (org) => {
  if (!org || !org.id) return
  currentOrgId.value = org.id
  currentOrg.value = org
  deptForm.organization_id = org.id
  await loadDeptTree()
  await loadOrgUsers()
}

const loadDeptTree = async () => {
  if (!currentOrgId.value) return
  try {
    const response = await axios.get(`/api/organizations/${currentOrgId.value}/departments/tree`)
    if (response.data.code === 0) {
      deptTree.value = response.data.data || []
    }
  } catch (error) {
    ElMessage.error('加载部门树失败')
  }
}

const loadOrgUsers = async () => {
  if (!currentOrgId.value) return
  try {
    const response = await axios.get('/api/users', { params: { organization_id: currentOrgId.value } })
    if (response.data.code === 0) {
      orgUsers.value = response.data.data || []
    }
  } catch (error) {
    console.error('加载组织用户失败:', error)
  }
}

const openAddOrgDialog = () => {
  Object.assign(orgForm, { id: null, name: '', code: '', logo: '', description: '', status: 1 })
  showAddOrgDialog.value = true
}

const editOrg = (org) => {
  Object.assign(orgForm, {
    id: org.id,
    name: org.name,
    code: org.code,
    logo: org.logo || '',
    description: org.description || '',
    status: org.status ?? 1
  })
  showAddOrgDialog.value = true
}

const saveOrg = async () => {
  if (!orgForm.name || !orgForm.code) {
    ElMessage.error('请填写必填项')
    return
  }
  try {
    let response
    if (orgForm.id) {
      response = await axios.put(`/api/organizations/${orgForm.id}`, {
        name: orgForm.name,
        code: orgForm.code,
        logo: orgForm.logo,
        description: orgForm.description,
        status: orgForm.status
      })
    } else {
      response = await axios.post('/api/organizations', {
        name: orgForm.name,
        code: orgForm.code,
        logo: orgForm.logo,
        description: orgForm.description,
        status: orgForm.status
      })
    }
    if (response.data.code === 0) {
      ElMessage.success('保存成功')
      showAddOrgDialog.value = false
      await loadOrganizations()
      if (!currentOrgId.value && organizations.value.length > 0) {
        selectOrg(organizations.value[0])
      }
    } else {
      ElMessage.error(response.data.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

const deleteOrg = async (org) => {
  try {
    await ElMessageBox.confirm(`确定要删除组织 "${org.name}" 吗？此操作将同时删除其下所有部门。`, '确认', { type: 'warning' })
    const response = await axios.delete(`/api/organizations/${org.id}`)
    if (response.data.code === 0) {
      ElMessage.success('删除成功')
      if (currentOrgId.value === org.id) {
        currentOrgId.value = null
        currentOrg.value = null
        deptTree.value = []
      }
      await loadOrganizations()
    } else {
      ElMessage.error(response.data.detail || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const loadDeptListForDialog = async (orgId, excludeDeptId = null) => {
  if (!orgId) {
    dialogDeptList.value = []
    return
  }
  try {
    const response = await axios.get(`/api/organizations/${orgId}/departments/tree`)
    if (response.data.code === 0) {
      let flatList = flattenTree(response.data.data || [])
      if (excludeDeptId) {
        flatList = flatList.filter(d => d.id !== excludeDeptId && !isDescendant(d.id, excludeDeptId, response.data.data || []))
      }
      dialogDeptList.value = flatList
    }
  } catch (error) {
    console.error('加载部门列表失败:', error)
    dialogDeptList.value = []
  }
}

function isDescendant(deptId, ancestorId, tree) {
  function search(nodes) {
    for (const node of nodes) {
      if (node.id === ancestorId) {
        return node.children ? containsTarget(node.children, deptId) : false
      }
      if (node.children && search(node.children)) {
        return true
      }
    }
    return false
  }
  function containsTarget(nodes, targetId) {
    for (const node of nodes) {
      if (node.id === targetId) return true
      if (node.children && containsTarget(node.children, targetId)) return true
    }
    return false
  }
  return search(tree)
}

const onOrgChange = async (newOrgId) => {
  deptForm.parent_id = null
  await loadDeptListForDialog(newOrgId, deptForm.id || null)
}

const openAddDeptDialog = async (parentId) => {
  Object.assign(deptForm, {
    id: null,
    organization_id: currentOrgId.value,
    parent_id: parentId,
    name: '',
    code: '',
    leader_id: null,
    description: '',
    status: 1
  })
  await loadDeptListForDialog(currentOrgId.value)
  showAddDeptDialog.value = true
}

const editDept = async (data) => {
  Object.assign(deptForm, {
    id: data.id,
    organization_id: data.organization_id || currentOrgId.value,
    parent_id: data.parent_id || null,
    name: data.name,
    code: data.code,
    leader_id: data.leader_id || null,
    description: data.description || '',
    status: data.status ?? 1
  })
  await loadDeptListForDialog(deptForm.organization_id, data.id)
  showAddDeptDialog.value = true
}

const saveDept = async () => {
  if (!deptForm.name || !deptForm.code) {
    ElMessage.error('请填写必填项')
    return
  }
  try {
    let response
    if (deptForm.id) {
      response = await axios.put(`/api/departments/${deptForm.id}`, {
        organization_id: deptForm.organization_id,
        name: deptForm.name,
        code: deptForm.code,
        leader_id: deptForm.leader_id,
        description: deptForm.description,
        status: deptForm.status
      })
    } else {
      response = await axios.post('/api/departments', {
        organization_id: deptForm.organization_id,
        parent_id: deptForm.parent_id,
        name: deptForm.name,
        code: deptForm.code,
        leader_id: deptForm.leader_id,
        description: deptForm.description,
        status: deptForm.status
      })
    }
    if (response.data.code === 0) {
      ElMessage.success('保存成功')
      showAddDeptDialog.value = false
      if (deptForm.organization_id !== currentOrgId.value) {
        const newOrg = organizations.value.find(o => o.id === deptForm.organization_id)
        if (newOrg) {
          selectOrg(newOrg)
        }
      } else {
        await loadDeptTree()
      }
    } else {
      ElMessage.error(response.data.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

const deleteDept = async (data) => {
  try {
    await ElMessageBox.confirm(`确定要删除部门 "${data.name}" 吗？`, '确认', { type: 'warning' })
    const response = await axios.delete(`/api/departments/${data.id}`)
    if (response.data.code === 0) {
      ElMessage.success('删除成功')
      await loadDeptTree()
    } else {
      ElMessage.error(response.data.detail || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

watch(currentOrgId, async (newId) => {
  if (newId) {
    deptForm.organization_id = newId
  }
})

onMounted(() => {
  loadOrganizations()
})
</script>

<style scoped>
.org-page {
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

.org-container {
  display: flex;
  gap: 16px;
  min-height: 500px;
}

.org-sidebar {
  width: 280px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
}

.org-count {
  background: #e6f4ff;
  color: #1890ff;
}

.org-list {
  flex: 1;
  overflow-y: auto;
}

.org-item {
  padding: 12px 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #f5f5f5;
  transition: all 0.2s ease;
  position: relative;
}

.org-item:hover {
  background: #f5f7fa;
}

.org-item.active {
  background: #e6f4ff;
}

.org-item.active .org-name {
  color: #1890ff;
  font-weight: 600;
}

.org-indicator {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: #1890ff;
}

.org-info {
  flex: 1;
  min-width: 0;
}

.org-name {
  font-size: 14px;
  color: #333;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.org-code {
  font-size: 12px;
  color: #999;
}

.org-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}

.org-actions .el-button {
  padding: 2px 4px;
  font-size: 12px;
}

.org-status-tag {
  margin-bottom: 2px;
}

.org-content {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.content-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.content-header.empty {
  justify-content: center;
  color: #999;
  font-size: 14px;
}

.content-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 16px;
}

.title-icon {
  font-size: 20px;
}

.dept-content {
  flex: 1;
  padding: 16px 20px;
  overflow: auto;
}

.dept-content .el-table {
  width: 100%;
}
</style>
