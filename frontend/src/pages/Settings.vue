<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>
    
    <el-card title="审计日志保留">
      <el-form :model="settings" label-width="140px">
        <el-form-item label="审计日志保留天数">
          <el-input v-model.number="settings.auditRetentionDays" class="setting-input">
            <template #suffix>天</template>
          </el-input>
        </el-form-item>
        <el-form-item label="SSH连接超时">
          <el-input v-model.number="settings.sshTimeout" class="setting-input">
            <template #suffix>秒</template>
          </el-input>
        </el-form-item>
        <el-form-item label="批量操作并发数">
          <el-input v-model.number="settings.batchWorkers" class="setting-input">
            <template #suffix>个</template>
          </el-input>
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

/* 与全站筛选/表单控件统一宽度 */
.setting-input {
  width: 200px;
}
</style>