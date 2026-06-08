<template>
  <div class="sql-page">
    <div class="page-header">
      <h2>SQL控制台</h2>
      <el-select v-model="selectedServiceId" placeholder="选择数据库服务" @change="loadDatabases">
        <el-option v-for="service in dbServices" :key="service.id" :label="service.service_name" :value="service.id" />
      </el-select>
    </div>
    
    <div class="sql-content">
      <div class="left-panel">
        <div class="panel-header">数据库</div>
        <el-tree :data="databaseTree" :props="treeProps" @node-click="selectDatabase" />
      </div>
      
      <div class="right-panel">
        <div class="toolbar">
          <el-button @click="executeSQL" type="primary">执行</el-button>
          <el-button @click="clearEditor">清空</el-button>
          <el-select v-model="limit" placeholder="限制行数">
            <el-option label="10" :value="10" />
            <el-option label="50" :value="50" />
            <el-option label="100" :value="100" />
            <el-option label="全部" :value="0" />
          </el-select>
        </div>
        
        <div class="editor-container">
          <textarea v-model="sqlContent" class="sql-editor" placeholder="输入SQL语句..."></textarea>
        </div>
        
        <div class="result-container">
          <div class="result-header">执行结果</div>
          <el-table v-if="resultData.length > 0" :data="resultData" border>
            <el-table-column v-for="col in resultColumns" :key="col" :label="col" :prop="col" />
          </el-table>
          <div v-else-if="executionError" class="error-message">{{ executionError }}</div>
          <div v-else class="empty-result">执行结果将显示在这里</div>
        </div>
        
        <div class="history-panel">
          <div class="history-header">执行历史</div>
          <el-timeline>
            <el-timeline-item v-for="item in history" :key="item.id" :timestamp="item.created_at">
              <div class="history-item" @click="loadHistoryItem(item)">
                <pre>{{ item.sql_statement }}</pre>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import axios from '@/utils/axios'

const dbServices = ref([])
const selectedServiceId = ref('')
const selectedDatabase = ref('')
const sqlContent = ref('')
const limit = ref(100)
const resultData = ref([])
const resultColumns = ref([])
const executionError = ref('')
const history = ref([])

const treeProps = {
  label: 'name',
  children: 'children'
}

const databaseTree = computed(() => {
  return history.value.map(h => ({
    id: h.id,
    name: h.service_code,
    children: []
  }))
})

async function loadServices() {
  const response = await axios.get('/api/services')
  if (response.data.code === 0) {
    dbServices.value = response.data.data.filter(s => 
      ['MYSQL', 'KINGBASE', 'DAMENG'].includes(s.service_type)
    )
  }
}

async function loadDatabases() {
  if (!selectedServiceId.value) return
  
  const response = await axios.get(`/api/sql/databases/${selectedServiceId.value}`)
  if (response.data.code === 0) {
    const databases = response.data.data.map(db => ({
      id: db,
      name: db,
      children: []
    }))
    databaseTree.value = [{ id: 'root', name: 'Databases', children: databases }]
  }
}

function selectDatabase(data) {
  if (data.id !== 'root') {
    selectedDatabase.value = data.name
    sqlContent.value = `USE ${data.name};`
  }
}

async function executeSQL() {
  if (!selectedServiceId.value || !sqlContent.value.trim()) {
    ElMessage.error('请选择服务并输入SQL语句')
    return
  }
  
  executionError.value = ''
  
  try {
    const response = await axios.post('/api/sql/execute', {
      service_id: selectedServiceId.value,
      sql: sqlContent.value
    })
    
    if (response.data.code === 0) {
      const result = response.data.data
      resultColumns.value = result.columns || []
      resultData.value = result.data || []
    } else {
      executionError.value = response.data.message
    }
  } catch (error) {
    executionError.value = error.response?.data?.message || '执行失败'
  }
  
  await loadHistory()
}

function clearEditor() {
  sqlContent.value = ''
  resultData.value = []
  resultColumns.value = []
  executionError.value = ''
}

async function loadHistory() {
  const response = await axios.get('/api/sql/history')
  if (response.data.code === 0) {
    history.value = response.data.data.slice(0, 10)
  }
}

function loadHistoryItem(item) {
  sqlContent.value = item.sql_statement
}

onMounted(() => {
  loadServices()
  loadHistory()
})
</script>

<style scoped>
.sql-page {
  padding: 20px;
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 20px;
}

.sql-content {
  flex: 1;
  display: flex;
  gap: 20px;
  overflow: hidden;
}

.left-panel {
  width: 250px;
  background: #f9fafb;
  border-radius: 8px;
  overflow: hidden;
}

.panel-header {
  padding: 12px 15px;
  background: #e5e7eb;
  font-weight: bold;
}

.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

.editor-container {
  flex: 1;
  min-height: 150px;
}

.sql-editor {
  width: 100%;
  height: 100%;
  min-height: 150px;
  padding: 15px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 14px;
  background: #1f2937;
  color: #e5e7eb;
  border: none;
  border-radius: 8px;
  resize: none;
}

.sql-editor:focus {
  outline: none;
}

.result-container {
  flex: 2;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: auto;
}

.result-header {
  padding: 12px 15px;
  background: #f3f4f6;
  font-weight: bold;
  border-bottom: 1px solid #e5e7eb;
}

.error-message {
  padding: 20px;
  color: #dc2626;
}

.empty-result {
  padding: 20px;
  color: #9ca3af;
  text-align: center;
}

.history-panel {
  flex: 1;
  max-height: 200px;
  overflow-y: auto;
  margin-top: 10px;
}

.history-header {
  padding: 12px 15px;
  background: #f3f4f6;
  font-weight: bold;
  border-bottom: 1px solid #e5e7eb;
}

.history-item {
  padding: 10px;
  background: #fff;
  cursor: pointer;
}

.history-item:hover {
  background: #f3f4f6;
}

.history-item pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  color: #374151;
}
</style>