<template>
  <el-dialog title="日志查看" :visible="visible" width="800px" :before-close="handleClose">
    <div class="log-header">
      <el-select v-model="lines" style="width: 120px">
        <el-option :label="'100行'" :value="100" />
        <el-option :label="'500行'" :value="500" />
        <el-option :label="'1000行'" :value="1000" />
      </el-select>
      <el-button type="primary" @click="loadLog">刷新日志</el-button>
      <el-button @click="downloadLog">下载完整日志</el-button>
    </div>
    <div class="log-content">
      <el-input
        type="textarea"
        :rows="20"
        :value="logContent"
        readonly
        class="log-textarea"
      />
    </div>
    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getProgramLog, downloadProgramLog } from '../api/program'

const props = defineProps({
  visible: Boolean,
  programId: Number
})

const emit = defineEmits(['close'])

const lines = ref(200)
const logContent = ref('')

watch(() => props.visible, async (val) => {
  if (val && props.programId) {
    await loadLog()
  }
})

async function loadLog() {
  if (!props.programId) return
  
  try {
    const result = await getProgramLog(props.programId, lines.value)
    if (result.code === 0) {
      logContent.value = result.data.content || '暂无日志内容'
    } else {
      logContent.value = '获取日志失败: ' + result.message
    }
  } catch (error) {
    logContent.value = '获取日志失败: ' + (error.response?.data?.message || error.message)
    ElMessage.error('获取日志失败')
  }
}

function downloadLog() {
  if (!props.programId) return
  downloadProgramLog(props.programId)
}

function handleClose() {
  emit('close')
}
</script>

<style scoped>
.log-header {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}

.log-content {
  max-height: 500px;
  overflow: auto;
}

.log-textarea {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
}
</style>