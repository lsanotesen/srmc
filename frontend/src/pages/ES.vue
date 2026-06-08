<template>
  <div class="es-page">
    <div class="page-header">
      <h2>Elasticsearch管理</h2>
      <el-select v-model="selectedServiceId" placeholder="选择ES服务" @change="loadClusterInfo">
        <el-option v-for="service in esServices" :key="service.id" :label="service.service_name" :value="service.id" />
      </el-select>
    </div>
    
    <el-tabs v-model="activeTab">
      <el-tab-pane label="集群状态" name="cluster">
        <el-card v-if="clusterInfo">
          <el-descriptions :column="2" :data="clusterInfo">
            <el-descriptions-item label="集群名称" prop="cluster_name" />
            <el-descriptions-item label="状态" prop="status">
              <template #content>
                <el-tag :type="getStatusType(clusterInfo.status)">{{ clusterInfo.status }}</el-tag>
              </template>
            </el-descriptions-item>
            <el-descriptions-item label="节点数" prop="number_of_nodes" />
            <el-descriptions-item label="数据节点数" prop="number_of_data_nodes" />
            <el-descriptions-item label="分片数" prop="active_primary_shards" />
            <el-descriptions-item label="副本分片数" prop="active_shards" />
          </el-descriptions>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="节点列表" name="nodes">
        <pre>{{ nodesInfo }}</pre>
      </el-tab-pane>
      
      <el-tab-pane label="索引管理" name="indices">
        <div class="indices-actions">
          <el-button @click="loadIndices">刷新</el-button>
          <el-button type="danger" @click="deleteSelectedIndex" :disabled="!selectedIndex">删除索引</el-button>
        </div>
        <el-table :data="indices" border @row-click="selectIndex">
          <el-table-column prop="name" label="索引名称" />
          <el-table-column prop="status" label="状态" />
          <el-table-column prop="docs" label="文档数" />
          <el-table-column prop="size" label="大小" />
        </el-table>
      </el-tab-pane>
      
      <el-tab-pane label="DSL查询" name="dsl">
        <div class="dsl-editor">
          <textarea v-model="dslQuery" placeholder="输入DSL查询..."></textarea>
        </div>
        <el-button @click="executeDSL" type="primary">执行查询</el-button>
        <pre class="dsl-result">{{ dslResult }}</pre>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from '@/utils/axios'

const esServices = ref([])
const selectedServiceId = ref('')
const activeTab = ref('cluster')
const clusterInfo = ref(null)
const nodesInfo = ref('')
const indices = ref([])
const selectedIndex = ref(null)
const dslQuery = ref('')
const dslResult = ref('')

function getStatusType(status) {
  switch (status) {
    case 'green': return 'success'
    case 'yellow': return 'warning'
    case 'red': return 'danger'
    default: return 'info'
  }
}

async function loadServices() {
  const response = await axios.get('/api/services')
  if (response.data.code === 0) {
    esServices.value = response.data.data.filter(s => s.service_type === 'ELASTICSEARCH')
  }
}

async function loadClusterInfo() {
  if (!selectedServiceId.value) return
  
  const response = await axios.get(`/api/es/cluster/${selectedServiceId.value}`)
  if (response.data.code === 0) {
    clusterInfo.value = response.data.data
  }
  
  await loadNodes()
}

async function loadNodes() {
  const response = await axios.get(`/api/es/nodes/${selectedServiceId.value}`)
  if (response.data.code === 0) {
    nodesInfo.value = response.data.data.raw
  }
}

async function loadIndices() {
  const response = await axios.get(`/api/es/indices/${selectedServiceId.value}`)
  if (response.data.code === 0) {
    const lines = response.data.data.raw.split('\n').slice(1)
    indices.value = lines.filter(line => line.trim()).map(line => {
      const parts = line.trim().split(/\s+/)
      return {
        name: parts[2],
        status: parts[0],
        docs: parts[5],
        size: parts[6]
      }
    })
  }
}

function selectIndex(row) {
  selectedIndex.value = row.name
}

async function deleteSelectedIndex() {
  if (!selectedIndex.value) return
  
  if (await ElMessage.confirm(`确定删除索引 ${selectedIndex.value} 吗？`)) {
    const response = await axios.delete(`/api/es/index/${selectedServiceId.value}/${selectedIndex.value}`)
    if (response.data.code === 0) {
      ElMessage.success('删除成功')
      await loadIndices()
      selectedIndex.value = null
    }
  }
}

async function executeDSL() {
  if (!selectedServiceId.value || !dslQuery.value.trim()) {
    ElMessage.error('请选择服务并输入DSL查询')
    return
  }
  
  try {
    const query = JSON.parse(dslQuery.value)
    const response = await axios.post(`/api/es/search/${selectedServiceId.value}`, query)
    if (response.data.code === 0) {
      dslResult.value = JSON.stringify(response.data.data, null, 2)
    } else {
      dslResult.value = response.data.message
    }
  } catch (error) {
    dslResult.value = error.message
  }
}

onMounted(() => {
  loadServices()
})
</script>

<style scoped>
.es-page {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 20px;
}

.indices-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
}

.dsl-editor {
  margin-bottom: 15px;
}

.dsl-editor textarea {
  width: 100%;
  height: 200px;
  padding: 15px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 14px;
  background: #1f2937;
  color: #e5e7eb;
  border: none;
  border-radius: 8px;
  resize: none;
}

.dsl-editor textarea:focus {
  outline: none;
}

.dsl-result {
  background: #1f2937;
  color: #e5e7eb;
  padding: 20px;
  border-radius: 8px;
  overflow: auto;
  max-height: 400px;
}
</style>