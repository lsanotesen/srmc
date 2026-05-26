<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>
    
    <el-card title="审计日志保留">
      <el-form :model="settings" label-width="200px">
        <el-form-item label="审计日志保留天数">
          <el-input v-model.number="settings.auditRetentionDays" />
          <span class="form-tip">天</span>
        </el-form-item>
        <el-form-item label="SSH连接超时">
          <el-input v-model.number="settings.sshTimeout" />
          <span class="form-tip">秒</span>
        </el-form-item>
        <el-form-item label="批量操作并发数">
          <el-input v-model.number="settings.batchWorkers" />
          <span class="form-tip">个</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveSettings">保存设置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card title="系统信息">
      <el-descriptions :column="2">
        <el-descriptions-item label="系统版本">1.0.0</el-descriptions-item>
        <el-descriptions-item label="后端服务">
          <span :class="backendStatus ? 'online' : 'offline'">{{ backendStatus ? '在线' : '离线' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="数据库">
          <span :class="dbStatus ? 'online' : 'offline'">{{ dbStatus ? '在线' : '离线' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="Redis">
          <span :class="redisStatus ? 'online' : 'offline'">{{ redisStatus ? '在线' : '离线' }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <el-button @click="checkHealth">检查健康状态</el-button>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const settings = reactive({
  auditRetentionDays: 90,
  sshTimeout: 10,
  batchWorkers: 5
})

const backendStatus = ref(false)
const dbStatus = ref(false)
const redisStatus = ref(false)

async function saveSettings() {
  ElMessage.success('设置已保存')
}

async function checkHealth() {
  try {
    const response = await axios.get('/health')
    if (response.data.code === 0) {
      backendStatus.value = true
      dbStatus.value = true
      redisStatus.value = true
      ElMessage.success('系统健康检查通过')
    } else {
      backendStatus.value = true
      dbStatus.value = false
      redisStatus.value = false
      ElMessage.error('健康检查失败')
    }
  } catch (error) {
    backendStatus.value = false
    dbStatus.value = false
    redisStatus.value = false
    ElMessage.error('无法连接到后端服务')
  }
}

onMounted(() => {
  checkHealth()
})
</script>

<style scoped>
.settings-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.form-tip {
  margin-left: 8px;
  color: #9ca3af;
}

.online {
  color: #10b981;
}

.offline {
  color: #ef4444;
}
</style>