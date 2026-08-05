<template>
  <div class="projects-page">
    <div class="page-header">
      <div class="header-left">
        <h1>项目列表</h1>
        <p class="subtitle">管理系统中的项目信息</p>
      </div>
      <div class="actions">
        <el-button v-if="hasPermission('project:add')" type="primary" icon="plus" @click="openAddProjectDialog">新增项目</el-button>
        <el-button icon="download" @click="downloadTemplate">下载模板</el-button>
        <el-button v-if="hasPermission('project:add')" icon="upload" @click="showImportDialog = true">导入项目</el-button>
        <el-button v-if="hasPermission('project:view')" icon="export" @click="exportProjects">导出项目</el-button>
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
        <el-table-column prop="code" label="项目编码" min-width="120" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.code" type="info" size="small">{{ scope.row.code }}</el-tag>
            <span v-else class="empty-text">-</span>
          </template>
        </el-table-column>
        <el-table-column label="所属组织" min-width="130" align="center">
          <template #default="scope">
            {{ scope.row.organization_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="所属部门" min-width="140" align="center">
          <template #default="scope">
            {{ scope.row.department_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="可见性" min-width="110" align="center">
          <template #default="scope">
            <el-tag :type="getVisibilityTagType(scope.row.visibility)" size="small">
              {{ getVisibilityLabel(scope.row.visibility) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="负责人" min-width="110" align="center">
          <template #default="scope">
            {{ scope.row.owner_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="description" label="项目描述" min-width="240">
          <template #default="scope">
            <span :class="['description-text', { 'empty-text': !scope.row.description }]">
              {{ scope.row.description || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="480" align="center" fixed="right">
          <template #default="scope">
            <div class="action-buttons">
              <el-button type="primary" size="small" @click="viewProject(scope.row)">查看</el-button>
              <el-button v-if="hasPermission('project:edit')" type="success" size="small" @click="editProject(scope.row)">编辑</el-button>
              <el-button v-if="hasPermission('project:share')" type="warning" size="small" @click="openMemberDialog(scope.row)">成员管理</el-button>
              <el-button v-if="hasPermission('project:share')" type="info" size="small" @click="openShareDialog(scope.row)">共享管理</el-button>
              <el-button v-if="hasPermission('project:delete')" type="danger" size="small" @click="deleteProject(scope.row)">删除</el-button>
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
        <el-form-item label="所属组织" required>
          <el-select
            v-model="projectForm.organization_id"
            style="width: 100%;"
            placeholder="请选择所属组织"
            :disabled="!!projectForm.id && !!projectForm._orgLocked"
            @change="onProjectOrgChange"
          >
            <el-option v-for="org in projectOrgList" :key="org.id" :label="org.name" :value="org.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属部门" required>
          <el-select
            v-model="projectForm.department_id"
            style="width: 100%;"
            filterable
            clearable
            placeholder="请选择所属部门"
            :disabled="!projectForm.organization_id"
          >
            <el-option v-for="dept in projectDeptList" :key="dept.id" :label="dept.name" :value="dept.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="可见性" required>
          <el-select v-model="projectForm.visibility" style="width: 100%;" placeholder="请选择可见性">
            <el-option v-for="opt in visibilityOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目负责人" required>
          <el-select
            v-model="projectForm.owner_id"
            style="width: 100%;"
            filterable
            clearable
            placeholder="请选择项目负责人"
            :disabled="!projectForm.organization_id"
          >
            <el-option
              v-for="u in projectUserList"
              :key="u.id"
              :label="u.job_title ? `${u.job_title} (${u.username})` : u.username"
              :value="u.id"
            />
          </el-select>
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

    <el-dialog title="项目详情" v-model="showDetailDialog" width="560px">
      <el-descriptions :column="1" border v-if="selectedProject">
        <el-descriptions-item label="项目名称">
          <span class="detail-name">{{ selectedProject.name }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="项目编码">
          {{ selectedProject.code || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="所属组织">
          {{ selectedProject.organization_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="所属部门">
          {{ selectedProject.department_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="可见性">
          <el-tag :type="getVisibilityTagType(selectedProject.visibility)" size="small">
            {{ getVisibilityLabel(selectedProject.visibility) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="项目负责人">
          {{ selectedProject.owner_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="创建人">
          {{ selectedProject.creator_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="项目描述">
          {{ selectedProject.description || '-' }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 项目成员管理 Dialog -->
    <el-dialog
      :title="`成员管理 - ${memberProject?.name || ''}`"
      v-model="showMemberDialog"
      width="800px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 12px;"
      >
        <template #title>
          <span>项目角色（Owner / Manager / Developer / Operator / Viewer）决定成员在本项目内的职责边界，与系统角色独立。</span>
        </template>
      </el-alert>

      <el-tabs v-model="memberTab" type="border-card" class="member-tabs">
        <!-- 单个添加 Tab -->
        <el-tab-pane label="单个添加" name="single">
          <div class="member-toolbar">
            <el-select
              v-model="addMemberForm.user_id"
              placeholder="选择用户"
              filterable
              style="width: 280px;"
            >
              <el-option
                v-for="u in allUsers"
                :key="u.id"
                :label="`${u.username}（${u.email || '无邮箱'}）`"
                :value="u.id"
              />
            </el-select>
            <el-select v-model="addMemberForm.role" style="width: 160px;">
              <el-option v-for="r in projectRoles" :key="r.value" :label="r.label" :value="r.value" />
            </el-select>
            <el-button type="primary" @click="addMember" :disabled="!addMemberForm.user_id">添加成员</el-button>
          </div>
        </el-tab-pane>

        <!-- 批量添加 Tab -->
        <el-tab-pane label="批量添加" name="batch">
          <el-tabs v-model="batchTab" tab-position="left" class="batch-subtabs">
            <!-- 按部门批量添加 -->
            <el-tab-pane label="按部门" name="department">
              <div class="batch-form">
                <el-form label-width="120px" inline>
                  <el-form-item label="选择部门">
                    <el-select
                      v-model="batchByDeptForm.department_id"
                      placeholder="请选择部门"
                      filterable
                      style="width: 320px;"
                    >
                      <el-option
                        v-for="d in allDepartmentsFlat"
                        :key="d.id"
                        :label="d.name"
                        :value="d.id"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="项目角色">
                    <el-select v-model="batchByDeptForm.role" style="width: 200px;">
                      <el-option v-for="r in projectRoles" :key="r.value" :label="r.label" :value="r.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item>
                    <el-button
                      type="primary"
                      @click="batchAddByDepartment"
                      :disabled="!batchByDeptForm.department_id"
                    >
                      批量添加
                    </el-button>
                  </el-form-item>
                </el-form>
                <el-alert
                  v-if="batchByDeptResult"
                  :title="`批量添加完成：新增 ${batchByDeptResult.added} 人，跳过 ${batchByDeptResult.skipped} 人（共 ${batchByDeptResult.total} 人）`"
                  type="success"
                  :closable="false"
                  show-icon
                  style="margin-top: 12px;"
                />
              </div>
            </el-tab-pane>

            <!-- 按系统角色批量添加 -->
            <el-tab-pane label="按系统角色" name="role">
              <div class="batch-form">
                <el-form label-width="120px" inline>
                  <el-form-item label="系统角色">
                    <el-select
                      v-model="batchByRoleForm.role_id"
                      placeholder="请选择系统角色"
                      style="width: 240px;"
                    >
                      <el-option
                        v-for="r in allRoles"
                        :key="r.id"
                        :label="r.name"
                        :value="r.id"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="项目角色">
                    <el-select v-model="batchByRoleForm.project_role" style="width: 200px;">
                      <el-option v-for="r in projectRoles" :key="r.value" :label="r.label" :value="r.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item>
                    <el-button
                      type="primary"
                      @click="batchAddByRole"
                      :disabled="!batchByRoleForm.role_id"
                    >
                      批量添加
                    </el-button>
                  </el-form-item>
                </el-form>
                <el-alert
                  v-if="batchByRoleResult"
                  :title="`批量添加完成：新增 ${batchByRoleResult.added} 人，跳过 ${batchByRoleResult.skipped} 人（共 ${batchByRoleResult.total} 人）`"
                  type="success"
                  :closable="false"
                  show-icon
                  style="margin-top: 12px;"
                />
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>
      </el-tabs>

      <el-divider content-position="left">当前项目成员</el-divider>
      <el-table :data="members" border size="small" max-height="280">
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column label="项目角色" width="180">
          <template #default="scope">
            <el-select
              v-model="scope.row.role"
              size="small"
              @change="changeMemberRole(scope.row)"
              :disabled="scope.row.role === 'Owner'"
              style="width: 100%;"
            >
              <el-option v-for="r in projectRoles" :key="r.value" :label="r.label" :value="r.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column prop="join_time" label="加入时间" width="160" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="scope">
            <el-button
              type="danger"
              size="small"
              link
              :disabled="scope.row.role === 'Owner'"
              @click="removeMember(scope.row)"
            >
              移除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showMemberDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 项目共享管理 Dialog -->
    <el-dialog
      :title="`共享管理 - ${shareProject?.name || ''}`"
      v-model="showShareDialog"
      width="720px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 12px;"
      >
        <template #title>
          <span>将项目共享给组织/部门/用户，并设置访问权限（READ / EDIT / MANAGE）。仅 Project Owner、部门管理员、组织管理员、超级管理员可操作。</span>
        </template>
      </el-alert>

      <div class="member-toolbar">
        <el-select v-model="addShareForm.target_type" placeholder="共享目标类型" style="width: 140px;">
          <el-option label="组织" value="Organization" />
          <el-option label="部门" value="Department" />
          <el-option label="用户" value="User" />
        </el-select>
        <el-select
          v-model="addShareForm.target_id"
          :placeholder="shareTargetPlaceholder"
          filterable
          style="width: 260px;"
        >
          <el-option
            v-for="t in shareTargetOptions"
            :key="t.id"
            :label="t.name"
            :value="t.id"
          />
        </el-select>
        <el-select v-model="addShareForm.permission" style="width: 140px;">
          <el-option label="READ 只读" value="READ" />
          <el-option label="EDIT 编辑" value="EDIT" />
          <el-option label="MANAGE 管理" value="MANAGE" />
        </el-select>
        <el-button type="primary" @click="addShare" :disabled="!addShareForm.target_id">添加共享</el-button>
      </div>

      <el-table :data="shares" border size="small">
        <el-table-column label="目标类型" width="120">
          <template #default="scope">
            <el-tag size="small">{{ targetTypeLabel(scope.row.target_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_name" label="目标名称" min-width="180" />
        <el-table-column label="权限级别" width="180">
          <template #default="scope">
            <el-select
              v-model="scope.row.permission"
              size="small"
              @change="updateSharePermission(scope.row)"
              style="width: 100%;"
            >
              <el-option label="READ 只读" value="READ" />
              <el-option label="EDIT 编辑" value="EDIT" />
              <el-option label="MANAGE 管理" value="MANAGE" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="scope">
            <el-button type="danger" size="small" link @click="removeShare(scope.row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showShareDialog = false">关闭</el-button>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from '@/utils/axios'
import { usePermission } from '@/composables/usePermission'
import { useUserStore } from '@/stores/user'

const { hasPermission } = usePermission()

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
  description: '',
  organization_id: null,
  department_id: null,
  visibility: 'DEPARTMENT',
  owner_id: null,
  _orgLocked: false  // 内部标志：编辑已有组织的项目时锁定组织
})

// 项目表单所需的下拉数据
const projectOrgList = ref([])
const projectDeptList = ref([])
const projectUserList = ref([])

const visibilityOptions = [
  { value: 'DEPARTMENT', label: '同部门可见' },
  { value: 'AUTHORIZED', label: '授权可见' },
  { value: 'PUBLIC', label: '公开可见' }
]

function getVisibilityLabel(val) {
  const item = visibilityOptions.find(o => o.value === val)
  return item ? item.label : (val || '-')
}

function getVisibilityTagType(val) {
  switch (val) {
    case 'DEPARTMENT': return 'info'
    case 'AUTHORIZED': return 'warning'
    case 'PUBLIC': return 'success'
    default: return 'info'
  }
}

// ===== 项目成员管理 =====
const showMemberDialog = ref(false)
const memberProject = ref(null)
const members = ref([])
const allUsers = ref([])
const projectRoles = [
  { value: 'Owner', label: 'Owner（所有者）' },
  { value: 'Manager', label: 'Manager（管理者）' },
  { value: 'Developer', label: 'Developer（开发）' },
  { value: 'Operator', label: 'Operator（运维）' },
  { value: 'Viewer', label: 'Viewer（只读）' },
]
const addMemberForm = reactive({ user_id: null, role: 'Viewer' })

// ===== 批量添加相关 =====
const memberTab = ref('single')
const batchTab = ref('department')
const allDepartmentsFlat = ref([])
const allRoles = ref([])
const batchByDeptForm = reactive({ department_id: null, role: 'Viewer' })
const batchByRoleForm = reactive({ role_id: null, project_role: 'Viewer' })
const batchByDeptResult = ref(null)
const batchByRoleResult = ref(null)

// ===== 项目共享管理 =====
const showShareDialog = ref(false)
const shareProject = ref(null)
const shares = ref([])
const allOrganizations = ref([])
const allDepartments = ref([])
const addShareForm = reactive({
  target_type: 'Organization',
  target_id: null,
  permission: 'READ',
})

const shareTargetOptions = computed(() => {
  if (addShareForm.target_type === 'Organization') return allOrganizations.value
  if (addShareForm.target_type === 'Department') return allDepartments.value
  return allUsers.value.map(u => ({ id: u.id, name: u.username }))
})

const shareTargetPlaceholder = computed(() => {
  if (addShareForm.target_type === 'Organization') return '选择组织'
  if (addShareForm.target_type === 'Department') return '选择部门'
  return '选择用户'
})

function targetTypeLabel(t) {
  return { Organization: '组织', Department: '部门', User: '用户' }[t] || t
}

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
  projectForm.organization_id = null
  projectForm.department_id = null
  projectForm.visibility = 'DEPARTMENT'
  projectForm.owner_id = null
  projectForm._orgLocked = false
  projectDeptList.value = []
  projectUserList.value = []
}

const resetFilters = () => {
  filters.keyword = ''
  loadProjects()
}

const viewProject = (project) => {
  selectedProject.value = project
  showDetailDialog.value = true
}

const editProject = async (project) => {
  resetForm()
  // 先加载组织列表
  await loadProjectOrganizations()
  // 回填表单数据
  projectForm.id = project.id
  projectForm.name = project.name
  projectForm.code = project.code || ''
  projectForm.description = project.description || ''
  projectForm.organization_id = project.organization_id || null
  projectForm.department_id = project.department_id || null
  projectForm.visibility = project.visibility || 'DEPARTMENT'
  projectForm.owner_id = project.owner_id || null
  // 加载该组织下的部门与用户
  if (project.organization_id) {
    await loadProjectDepartments(project.organization_id)
    await loadProjectUsers(project.organization_id)
  }
  // 锁定规则：已有组织 && 该组织下有部门时锁定；否则允许切换组织
  const hasDepartments = projectDeptList.value.length > 0
  projectForm._orgLocked = !!project.organization_id && hasDepartments
  showAddDialog.value = true
}

// 加载项目表单所需的组织列表
async function loadProjectOrganizations() {
  try {
    const response = await axios.get('/api/organizations?page=1&size=100')
    if (response.data.code === 0) {
      const data = response.data.data
      projectOrgList.value = Array.isArray(data) ? data : (data.items || [])
    }
  } catch (error) {
    console.error('加载组织列表失败:', error)
  }
}

// 根据组织加载部门（带组织前缀）
async function loadProjectDepartments(orgId) {
  if (!orgId) {
    projectDeptList.value = []
    return
  }
  try {
    const response = await axios.get(`/api/organizations/${orgId}/departments/tree`)
    if (response.data.code === 0) {
      const org = projectOrgList.value.find(o => o.id === orgId)
      const orgName = org ? org.name : ''
      const flat = []
      const walk = (nodes, parentPath = '') => {
        for (const n of nodes) {
          const path = parentPath ? `${parentPath} / ${n.name}` : `${orgName} / ${n.name}`
          flat.push({ id: n.id, name: path, organization_id: n.organization_id })
          if (n.children && n.children.length) walk(n.children, path)
        }
      }
      walk(response.data.data || [])
      projectDeptList.value = flat
    }
  } catch (error) {
    console.error('加载部门列表失败:', error)
    projectDeptList.value = []
  }
}

// 根据组织加载用户
async function loadProjectUsers(orgId) {
  if (!orgId) {
    projectUserList.value = []
    return
  }
  try {
    const response = await axios.get('/api/users', { params: { organization_id: orgId } })
    if (response.data.code === 0) {
      projectUserList.value = response.data.data || []
    }
  } catch (error) {
    console.error('加载用户列表失败:', error)
    projectUserList.value = []
  }
}

// 表单内切换组织
async function onProjectOrgChange(orgId) {
  projectForm.department_id = null
  projectForm.owner_id = null
  await Promise.all([loadProjectDepartments(orgId), loadProjectUsers(orgId)])
}

// 打开新增项目对话框
async function openAddProjectDialog() {
  resetForm()
  await loadProjectOrganizations()
  // 默认填充当前用户所在组织
  const userStore = useUserStore()
  const currentOrgId = userStore.user?.organization_id
  if (currentOrgId) {
    projectForm.organization_id = currentOrgId
    await onProjectOrgChange(currentOrgId)
  }
  showAddDialog.value = true
}

const saveProject = async () => {
  if (!projectForm.name.trim()) {
    ElMessage.error('请输入项目名称')
    return
  }
  if (!projectForm.organization_id) {
    ElMessage.error('请选择所属组织')
    return
  }
  if (!projectForm.department_id) {
    ElMessage.error('请选择所属部门')
    return
  }
  if (!projectForm.owner_id) {
    ElMessage.error('请选择项目负责人')
    return
  }

  try {
    const commonPayload = {
      name: projectForm.name,
      code: projectForm.code || null,
      description: projectForm.description || null,
      department_id: projectForm.department_id || null,
      visibility: projectForm.visibility || 'DEPARTMENT',
      owner_id: projectForm.owner_id || null
    }
    let response
    if (projectForm.id) {
      // 编辑：仅在项目尚无组织时提交 organization_id（首次设置）
      const payload = { ...commonPayload }
      if (!projectForm._orgLocked && projectForm.organization_id) {
        payload.organization_id = projectForm.organization_id
      }
      response = await axios.put(`/api/projects/${projectForm.id}`, payload)
    } else {
      // 新建：提交 organization_id
      response = await axios.post('/api/projects', {
        ...commonPayload,
        organization_id: projectForm.organization_id
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
    ElMessage.error(error.response?.data?.message || error.response?.data?.detail || '操作失败')
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

// ===== 项目成员管理方法 =====
async function loadAllUsers() {
  try {
    const response = await axios.get('/api/users')
    if (response.data.code === 0) {
      allUsers.value = response.data.data
    }
  } catch (error) {
    console.error('加载用户列表失败:', error)
  }
}

async function loadMembers(projectId) {
  try {
    const response = await axios.get(`/api/projects/${projectId}/members`)
    if (response.data.code === 0) {
      members.value = response.data.data
    }
  } catch (error) {
    ElMessage.error('加载成员列表失败')
  }
}

async function openMemberDialog(project) {
  memberProject.value = project
  showMemberDialog.value = true
  memberTab.value = 'single'
  batchTab.value = 'department'
  addMemberForm.user_id = null
  addMemberForm.role = 'Viewer'
  batchByDeptForm.department_id = null
  batchByDeptForm.role = 'Viewer'
  batchByRoleForm.role_id = null
  batchByRoleForm.project_role = 'Viewer'
  batchByDeptResult.value = null
  batchByRoleResult.value = null
  await Promise.all([loadAllUsers(), loadMembers(project.id), loadDepartmentsFlat(), loadRoles()])
}

async function addMember() {
  if (!memberProject.value || !addMemberForm.user_id) return
  try {
    const response = await axios.post(`/api/projects/${memberProject.value.id}/members`, {
      user_id: addMemberForm.user_id,
      role: addMemberForm.role,
    })
    if (response.data.code === 0) {
      ElMessage.success('添加成员成功')
      addMemberForm.user_id = null
      addMemberForm.role = 'Viewer'
      await loadMembers(memberProject.value.id)
    } else {
      ElMessage.error(response.data.message || '添加失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加失败')
  }
}

async function changeMemberRole(row) {
  if (!memberProject.value) return
  try {
    const response = await axios.put(
      `/api/projects/${memberProject.value.id}/members/${row.id}`,
      { role: row.role }
    )
    if (response.data.code === 0) {
      ElMessage.success('角色已更新')
    } else {
      ElMessage.error(response.data.message || '更新失败')
      await loadMembers(memberProject.value.id)
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '更新失败')
    await loadMembers(memberProject.value.id)
  }
}

async function removeMember(row) {
  if (!memberProject.value) return
  try {
    await ElMessageBox.confirm(`确定移除成员 "${row.username}" 吗？`, '确认', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    const response = await axios.delete(
      `/api/projects/${memberProject.value.id}/members/${row.id}`
    )
    if (response.data.code === 0) {
      ElMessage.success('移除成功')
      await loadMembers(memberProject.value.id)
    } else {
      ElMessage.error(response.data.message || '移除失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '移除失败')
  }
}

// ===== 批量添加方法 =====
async function loadDepartmentsFlat() {
  try {
    const response = await axios.get('/api/departments/tree-flat')
    if (response.data.code === 0) {
      allDepartmentsFlat.value = response.data.data || []
    }
  } catch (error) {
    console.error('加载部门列表失败:', error)
  }
}

async function loadRoles() {
  try {
    const response = await axios.get('/api/rbac/roles')
    if (response.data.code === 0) {
      allRoles.value = response.data.data || []
    }
  } catch (error) {
    console.error('加载角色列表失败:', error)
  }
}

async function batchAddByDepartment() {
  if (!memberProject.value || !batchByDeptForm.department_id) return
  try {
    const response = await axios.post(
      `/api/projects/${memberProject.value.id}/members/batch-by-department`,
      {
        department_id: batchByDeptForm.department_id,
        role: batchByDeptForm.role,
      }
    )
    if (response.data.code === 0) {
      batchByDeptResult.value = response.data.data
      ElMessage.success(response.data.message || '批量添加成功')
      await loadMembers(memberProject.value.id)
    } else {
      ElMessage.error(response.data.message || '批量添加失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '批量添加失败')
  }
}

async function batchAddByRole() {
  if (!memberProject.value || !batchByRoleForm.role_id) return
  try {
    const response = await axios.post(
      `/api/projects/${memberProject.value.id}/members/batch-by-role`,
      {
        role_id: batchByRoleForm.role_id,
        project_role: batchByRoleForm.project_role,
      }
    )
    if (response.data.code === 0) {
      batchByRoleResult.value = response.data.data
      ElMessage.success(response.data.message || '批量添加成功')
      await loadMembers(memberProject.value.id)
    } else {
      ElMessage.error(response.data.message || '批量添加失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '批量添加失败')
  }
}

// ===== 项目共享管理方法 =====
async function loadOrganizations() {
  try {
    const response = await axios.get('/api/organizations')
    if (response.data.code === 0) {
      allOrganizations.value = response.data.data || []
    }
  } catch (error) {
    console.error('加载组织列表失败:', error)
  }
}

async function loadDepartments() {
  try {
    const response = await axios.get('/api/organizations')
    if (response.data.code === 0) {
      const orgs = response.data.data || []
      const depts = []
      for (const org of orgs) {
        try {
          const deptRes = await axios.get(`/api/organizations/${org.id}/departments/tree`)
          if (deptRes.data.code === 0) {
            const flatten = (nodes) => {
              for (const n of nodes) {
                depts.push({ id: n.id, name: `${org.name} / ${n.name}` })
                if (n.children) flatten(n.children)
              }
            }
            flatten(deptRes.data.data || [])
          }
        } catch (e) {
          // 忽略单个组织部门加载失败
        }
      }
      allDepartments.value = depts
    }
  } catch (error) {
    console.error('加载部门列表失败:', error)
  }
}

async function loadShares(projectId) {
  try {
    const response = await axios.get(`/api/projects/${projectId}/permissions`)
    if (response.data.code === 0) {
      const list = response.data.data || []
      for (const item of list) {
        item.target_name = await resolveShareTargetName(item.target_type, item.target_id)
      }
      shares.value = list
    }
  } catch (error) {
    ElMessage.error('加载共享列表失败')
  }
}

async function resolveShareTargetName(targetType, targetId) {
  try {
    if (targetType === 'User') {
      const u = allUsers.value.find(x => x.id === targetId)
      return u ? u.username : `用户#${targetId}`
    }
    if (targetType === 'Organization') {
      const o = allOrganizations.value.find(x => x.id === targetId)
      return o ? o.name : `组织#${targetId}`
    }
    if (targetType === 'Department') {
      const d = allDepartments.value.find(x => x.id === targetId)
      return d ? d.name : `部门#${targetId}`
    }
  } catch (e) {
    // ignore
  }
  return `${targetType}#${targetId}`
}

async function openShareDialog(project) {
  shareProject.value = project
  showShareDialog.value = true
  addShareForm.target_type = 'Organization'
  addShareForm.target_id = null
  addShareForm.permission = 'READ'
  await Promise.all([loadAllUsers(), loadOrganizations(), loadDepartments()])
  await loadShares(project.id)
}

async function addShare() {
  if (!shareProject.value || !addShareForm.target_id) return
  try {
    const response = await axios.post(`/api/projects/${shareProject.value.id}/permissions`, {
      target_type: addShareForm.target_type,
      target_id: addShareForm.target_id,
      permission: addShareForm.permission,
    })
    if (response.data.code === 0) {
      ElMessage.success('共享添加成功')
      addShareForm.target_id = null
      await loadShares(shareProject.value.id)
    } else {
      ElMessage.error(response.data.message || '添加失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加失败')
  }
}

async function updateSharePermission(row) {
  if (!shareProject.value) return
  try {
    const response = await axios.put(
      `/api/projects/${shareProject.value.id}/permissions/${row.id}`,
      { permission: row.permission }
    )
    if (response.data.code === 0) {
      ElMessage.success('权限已更新')
    } else {
      ElMessage.error(response.data.message || '更新失败')
      await loadShares(shareProject.value.id)
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '更新失败')
    await loadShares(shareProject.value.id)
  }
}

async function removeShare(row) {
  if (!shareProject.value) return
  try {
    await ElMessageBox.confirm('确定取消此共享吗？', '确认', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    const response = await axios.delete(
      `/api/projects/${shareProject.value.id}/permissions/${row.id}`
    )
    if (response.data.code === 0) {
      ElMessage.success('已取消共享')
      await loadShares(shareProject.value.id)
    } else {
      ElMessage.error(response.data.message || '取消失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '取消失败')
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
  flex-wrap: wrap;
}

.member-toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  flex-wrap: wrap;
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

.member-tabs {
  margin-bottom: 0;
  
  :deep(.el-tabs__content) {
    padding: 0;
  }
}

.batch-subtabs {
  background: transparent;
  
  :deep(.el-tabs__content) {
    padding: 16px;
  }
}

.batch-form {
  padding: 8px 0;
  
  .el-form-item {
    margin-right: 16px;
  }
}
</style>
