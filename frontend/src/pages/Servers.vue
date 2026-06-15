<template>
  <div class="servers-page">
    <div class="page-header">
      <div>
        <h2>服务器管理</h2>
        <p class="page-subtitle">当前支持几十台平稳使用，并为后续扩展到 100 台预留分页与检索能力。</p>
      </div>
      <el-button type="success" @click="openCreateDialog">
        <el-icon component="Plus" />
        新增服务器
      </el-button>
    </div>

    <div class="toolbar">
      <el-input
        v-model="searchKeyword"
        placeholder="按主机名 / IP / 用户名搜索"
        clearable
        style="max-width: 320px"
        @clear="handleSearch"
        @keyup.enter="handleSearch"
      />
      <el-button @click="handleSearch">搜索</el-button>
    </div>

    <el-table :data="servers" border v-loading="loading">
      <el-table-column prop="hostname" label="主机名" min-width="140" />
      <el-table-column prop="ip" label="IP地址" min-width="140" />
      <el-table-column prop="ssh_port" label="SSH端口" width="100" />
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="os_type" label="操作系统" width="120" />
      <el-table-column prop="created_at" label="创建时间" min-width="160" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="scope">
          <el-button size="small" @click="testConnection(scope.row)">测试连接</el-button>
          <el-button size="small" @click="editServer(scope.row)">编辑</el-button>
          <el-button size="small" type="danger" @click="deleteServer(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>
    
    <el-dialog title="新增/编辑服务器" :visible="showAddDialog" @close="resetForm">
      <el-form :model="serverForm" label-width="120px">
        <el-form-item label="主机名">
          <el-input v-model="serverForm.hostname" />
        </el-form-item>
        <el-form-item label="IP地址">
          <el-input v-model="serverForm.ip" />
        </el-form-item>
        <el-form-item label="SSH端口">
          <el-input v-model.number="serverForm.ssh_port" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="serverForm.username" />
        </el-form-item>
        <el-form-item label="认证方式">
          <el-select v-model="authType" @change="toggleAuthType">
            <el-option label="密码认证" value="password" />
            <el-option label="密钥认证" value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="密码" v-if="authType === 'password'">
          <el-input v-model="serverForm.password" type="password" />
        </el-form-item>
        <el-form-item label="私钥" v-if="authType === 'key'">
          <el-input v-model="serverForm.private_key" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="操作系统">
          <el-select v-model="serverForm.os_type">
            <el-option label="Linux" value="LINUX" />
            <el-option label="Unix" value="UNIX" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveServer">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from '@/utils/axios'

const servers = ref([])
const showAddDialog = ref(false)
const authType = ref('password')
const loading = ref(false)
const searchKeyword = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const serverForm = reactive({
  id: null,
  hostname: '',
  ip: '',
  ssh_port: 22,
  username: '',
  password: '',
  private_key: '',
  os_type: 'LINUX'
})

function resetForm() {
  Object.assign(serverForm, {
    id: null,
    hostname: '',
    ip: '',
    ssh_port: 22,
    username: '',
    password: '',
    private_key: '',
    os_type: 'LINUX'
  })
  authType.value = 'password'
}

function openCreateDialog() {
  resetForm()
  showAddDialog.value = true
}

function toggleAuthType() {
  if (authType.value === 'password') {
    serverForm.private_key = ''
  } else {
    serverForm.password = ''
  }
}

async function loadServers() {
  loading.value = true
  try {
    const response = await axios.get('/api/servers', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        keyword: searchKeyword.value || undefined
      }
    })
    if (response.data.code === 0) {
      servers.value = response.data.data.items
      total.value = response.data.data.total
      page.value = response.data.data.page
      pageSize.value = response.data.data.page_size
    }
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadServers()
}

function handlePageChange(nextPage) {
  page.value = nextPage
  loadServers()
}

function handleSizeChange(nextSize) {
  pageSize.value = nextSize
  page.value = 1
  loadServers()
}

async function saveServer() {
  try {
    let result
    if (serverForm.id) {
      result = await axios.put(`/api/servers/${serverForm.id}`, serverForm)
    } else {
      result = await axios.post('/api/servers', serverForm)
    }
    
    if (result.data.code === 0) {
      ElMessage.success(serverForm.id ? '更新成功' : '创建成功')
      showAddDialog.value = false
      resetForm()
      await loadServers()
    } else {
      ElMessage.error(result.data.message)
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

function editServer(row) {
  Object.assign(serverForm, {
    id: row.id,
    hostname: row.hostname,
    ip: row.ip,
    ssh_port: row.ssh_port,
    username: row.username,
    password: '',
    private_key: '',
    os_type: row.os_type
  })
  authType.value = row.password ? 'password' : 'key'
  showAddDialog.value = true
}

async function deleteServer(row) {
  if (await ElMessage.confirm(`确定删除服务器 ${row.hostname} 吗？`)) {
    const result = await axios.delete(`/api/servers/${row.id}`)
    if (result.data.code === 0) {
      ElMessage.success('删除成功')
      await loadServers()
    } else {
      ElMessage.error(result.data.message)
    }
  }
}

async function testConnection(row) {
  const result = await axios.post(`/api/servers/${row.id}/test-connection`)
  if (result.data.code === 0) {
    ElMessage.success('连接成功')
  } else {
    ElMessage.error('连接失败')
  }
}

onMounted(() => {
  loadServers()
})
</script>

<style scoped>
.servers-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
</style>