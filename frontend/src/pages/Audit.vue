<template>
  <div class="audit-page">
    <div class="page-header">
      <h2>审计日志</h2>
    </div>
    
    <div class="filter-bar">
      <el-select v-model="filters.action" placeholder="操作类型" clearable>
        <el-option label="全部" value="" />
        <el-option label="启动" value="START" />
        <el-option label="停止" value="STOP" />
        <el-option label="重启" value="RESTART" />
        <el-option label="登录" value="LOGIN" />
        <el-option label="SQL执行" value="SQL" />
        <el-option label="导入" value="IMPORT" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索用户名/服务编码" />
      <el-date-picker v-model="filters.startTime" type="date" placeholder="开始日期" />
      <el-date-picker v-model="filters.endTime" type="date" placeholder="结束日期" />
      <el-button @click="loadLogs">搜索</el-button>
    </div>
    
    <el-table :data="logs" border>
      <el-table-column prop="created_at" label="时间" />
      <el-table-column prop="username" label="用户" />
      <el-table-column prop="action" label="操作类型" />
      <el-table-column prop="service_code" label="服务编码" />
      <el-table-column prop="ip" label="IP地址" />
      <el-table-column prop="result" label="结果">
        <template #default="scope">
          <el-tag :type="scope.row.result === 'success' ? 'success' : 'danger'">
            {{ scope.row.result === 'success' ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="duration" label="耗时(ms)" />
      <el-table-column prop="output" label="输出" width="300">
        <template #default="scope">
          <el-popover trigger="hover" placement="top">
            <template #content>
              <pre>{{ scope.row.output }}</pre>
            </template>
            <span class="output-preview">{{ scope.row.output?.slice(0, 50) }}{{ scope.row.output?.length > 50 ? '...' : '' }}</span>
          </el-popover>
        </template>
      </el-table-column>
    </el-table>
    
    <el-pagination
      :total="total"
      :page-size="pageSize"
      :current-page="currentPage"
      @current-change="handlePageChange"
      layout="prev, pager, next, jumper"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from '@/utils/axios'

const logs = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const filters = reactive({
  action: '',
  keyword: '',
  startTime: '',
  endTime: ''
})

async function loadLogs(page = 1) {
  const params = {
    page,
    limit: pageSize.value
  }
  
  if (filters.action) params.action = filters.action
  if (filters.keyword) {
    params.username = filters.keyword
    params.service_code = filters.keyword
  }
  if (filters.startTime) params.start_time = filters.startTime
  if (filters.endTime) params.end_time = filters.endTime
  
  const response = await axios.get('/api/audit', { params })
  if (response.data.code === 0) {
    logs.value = response.data.data.items
    total.value = response.data.data.total
    currentPage.value = page
  }
}

function handlePageChange(page) {
  loadLogs(page)
}

onMounted(() => {
  loadLogs()
})
</script>

<style scoped>
.audit-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.output-preview {
  color: #6366f1;
  cursor: pointer;
}
</style>