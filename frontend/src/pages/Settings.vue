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
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'

const settings = reactive({
  auditRetentionDays: 90,
  sshTimeout: 10,
  batchWorkers: 5
})

async function saveSettings() {
  ElMessage.success('设置已保存')
}
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
</style>