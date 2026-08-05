<template>
  <div class="import-services-page">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <el-icon class="title-icon"><Upload /></el-icon>
          <h1>服务导入</h1>
        </div>
        <p class="subtitle">选择目标项目和子系统，上传Excel文件批量导入服务数据</p>
      </div>
    </div>

    <div class="page-content">
      <div class="filter-card">
        <div class="card-header">
          <el-icon class="card-icon"><Filter /></el-icon>
          <span>目标项目</span>
        </div>
        <el-form :model="importForm" label-width="120px" class="filter-form">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="项目名称">
                <el-select
                  v-model="importForm.project_id"
                  placeholder="请选择项目"
                  clearable
                  class="full-width"
                  @change="handleProjectChange"
                >
                  <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="子系统">
                <el-select
                  v-model="importForm.subsystem_id"
                  placeholder="请选择子系统"
                  clearable
                  class="full-width"
                  @change="handleSubsystemChange"
                >
                  <el-option v-for="subsystem in subsystems" :key="subsystem.id" :label="subsystem.subsystem_name" :value="subsystem.id" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="服务分组">
                <el-select
                  v-model="importForm.group_id"
                  placeholder="请选择服务分组"
                  clearable
                  class="full-width"
                  :disabled="!importForm.subsystem_id"
                >
                  <el-option label="全部方式" :value="null" />
                  <el-option v-for="group in groups" :key="group.id" :label="group.group_name" :value="group.id" />
                </el-select>
                <div class="form-hint">
                  <el-icon><InfoFilled /></el-icon>
                  <span>若不选择，将根据Excel文件的Sheet名称自动匹配或创建服务分组</span>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </div>

      <div class="upload-card">
        <div class="card-header">
          <el-icon class="card-icon"><UploadFilled /></el-icon>
          <span>上传文件</span>
        </div>
        
        <div 
          class="upload-area"
          :class="{ 'upload-area-dragover': isDragover }"
          @dragover.prevent="isDragover = true"
          @dragleave="isDragover = false"
          @drop.prevent="handleDrop"
        >
          <el-upload
            class="upload-demo"
            :auto-upload="false"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            accept=".xlsx"
            drag
            :limit="1"
            :disabled="importing"
          >
            <div class="upload-icon-wrapper">
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
            </div>
            <div class="upload-text">
              <span class="upload-title">拖拽文件到此处</span>
              <span class="upload-subtitle">或点击选择文件</span>
            </div>
            <template #tip>
              <div class="upload-tip">
                <el-icon class="tip-icon"><InfoFilled /></el-icon>
                <span>支持 .xlsx 格式的Excel文件，文件大小不超过 10MB</span>
              </div>
            </template>
          </el-upload>
        </div>

        <div class="template-section">
          <el-button type="primary" link @click="downloadTemplate">
            <el-icon><Download /></el-icon>
            下载导入模板
          </el-button>
        </div>
      </div>

      <div v-if="importFile" class="preview-card">
        <div class="card-header">
          <el-icon class="card-icon"><Eye /></el-icon>
          <span>文件预览</span>
        </div>
        <div class="preview-content">
          <div class="file-info">
            <el-icon class="file-icon"><FileText /></el-icon>
            <div class="file-details">
              <span class="file-name">{{ importFile.name }}</span>
              <span class="file-size">{{ formatFileSize(importFile.size) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="importResult" class="result-card">
        <div class="card-header">
          <el-icon class="card-icon"><CheckCircle /></el-icon>
          <span>导入结果</span>
        </div>
        <div class="result-content">
          <div class="result-summary">
            <div class="summary-item success">
              <el-icon class="summary-icon"><CheckCircle /></el-icon>
              <div class="summary-info">
                <span class="summary-value">{{ importResult.success_count }}</span>
                <span class="summary-label">成功导入</span>
              </div>
            </div>
            <div class="summary-item warning">
              <el-icon class="summary-icon"><WarningCircle /></el-icon>
              <div class="summary-info">
                <span class="summary-value">{{ importResult.updated_count }}</span>
                <span class="summary-label">更新覆盖</span>
              </div>
            </div>
            <div class="summary-item error">
              <el-icon class="summary-icon"><CloseCircle /></el-icon>
              <div class="summary-info">
                <span class="summary-value">{{ importResult.failed_count }}</span>
                <span class="summary-label">导入失败</span>
              </div>
            </div>
          </div>

          <div v-if="importResult.failed_rows && importResult.failed_rows.length > 0" class="error-list">
            <div class="error-list-header">
              <el-icon class="error-icon"><AlertCircle /></el-icon>
              <span>失败记录详情</span>
            </div>
            <el-table :data="importResult.failed_rows" border :max-height="300">
              <el-table-column prop="row_num" label="行号" width="80" />
              <el-table-column prop="error" label="失败原因" />
            </el-table>
          </div>
        </div>
      </div>

      <div class="action-card">
        <div class="action-left">
          <el-button 
            type="primary" 
            size="large" 
            @click="doImport" 
            :loading="importing"
            :disabled="!importFile || !importForm.project_id"
          >
            <el-icon><Upload /></el-icon>
            {{ importing ? '导入中...' : '开始导入' }}
          </el-button>
          <el-button size="large" @click="resetForm">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </div>
        <div class="action-right">
          <router-link to="/services" class="back-link">
            <el-icon><ArrowLeft /></el-icon>
            返回服务列表
          </router-link>
        </div>
      </div>

      <div class="history-card">
        <div class="card-header">
          <el-icon class="card-icon"><Clock /></el-icon>
          <span>最近导入记录</span>
        </div>
        <div v-if="importHistory.length > 0" class="history-list">
          <div v-for="(record, index) in importHistory" :key="index" class="history-item">
            <div class="history-info">
              <span class="history-name">{{ record.filename }}</span>
              <span class="history-time">{{ record.time }}</span>
            </div>
            <el-tag v-if="record.success" type="success">成功</el-tag>
            <el-tag v-else type="danger">失败</el-tag>
          </div>
        </div>
        <div v-else class="empty-history">
          <el-icon class="empty-icon"><FileText /></el-icon>
          <p>暂无导入记录</p>
        </div>
      </div>

      <div class="tips-card">
        <div class="card-header">
          <el-icon class="card-icon"><Lightbulb /></el-icon>
          <span>导入提示</span>
        </div>
        <ul class="tips-list">
          <li>
            <el-icon class="tip-item-icon"><CheckCircle /></el-icon>
            <span>建议先下载模板，按照模板格式填写数据</span>
          </li>
          <li>
            <el-icon class="tip-item-icon"><CheckCircle /></el-icon>
            <span>导入时会自动更新已存在的服务，新增不存在的服务</span>
          </li>
          <li>
            <el-icon class="tip-item-icon"><CheckCircle /></el-icon>
            <span>功能描述为必填项，其他字段根据需要填写</span>
          </li>
          <li>
            <el-icon class="tip-item-icon"><CheckCircle /></el-icon>
            <span>IP地址和端口号请确保格式正确</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue';
import { ElMessage } from 'element-plus';
import axios from '@/utils/axios';

const importForm = reactive({
  project_id: null,
  subsystem_id: null,
  group_id: null
});

const projects = ref([]);
const subsystems = ref([]);
const groups = ref([]);
const importFile = ref(null);
const importing = ref(false);
const isDragover = ref(false);
const importResult = ref(null);
const importHistory = ref([]);

const loadProjects = async () => {
  try {
    const response = await axios.get('/api/projects', {
      params: { page: 1, size: 100 }
    });
    if (response.data.code === 0) {
      projects.value = response.data.data.items.map(p => ({
        id: p.id,
        name: p.name
      }));
    }
  } catch (error) {
    console.error('加载项目列表失败', error);
  }
};

const loadSubsystems = async (projectId) => {
  try {
    const params = new URLSearchParams();
    if (projectId) {
      params.append('project_id', projectId);
    }
    const response = await axios.get(`/api/subsystems?${params}`);
    if (response.data.code === 0) {
      subsystems.value = response.data.data.items;
    }
  } catch (error) {
    console.error('加载子系统列表失败', error);
    subsystems.value = [];
  }
};

const loadGroups = async (subsystemId) => {
  if (!subsystemId) {
    groups.value = [];
    return;
  }
  try {
    const response = await axios.get(`/api/subsystems/${subsystemId}/groups`);
    if (response.data.code === 0) {
      groups.value = response.data.data;
    }
  } catch (error) {
    console.error('加载服务分组列表失败', error);
    groups.value = [];
  }
};

const handleProjectChange = async (projectId) => {
  importForm.subsystem_id = null;
  importForm.group_id = null;
  if (projectId) {
    await loadSubsystems(projectId);
  } else {
    subsystems.value = [];
    groups.value = [];
  }
};

const handleSubsystemChange = async (subsystemId) => {
  importForm.group_id = null;
  if (subsystemId) {
    await loadGroups(subsystemId);
  } else {
    groups.value = [];
  }
};

const handleFileChange = (file) => {
  importFile.value = file.raw;
  importResult.value = null;
};

const handleFileRemove = () => {
  importFile.value = null;
  importResult.value = null;
};

const handleDrop = () => {
  isDragover.value = false;
};

const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
};

const downloadTemplate = async () => {
    try {
        const response = await axios.get('/api/services/template', {
            responseType: 'blob'
        });
        const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = '服务导入模板.xlsx';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        ElMessage.error('下载模板失败');
    }
};

const doImport = async () => {
    if (!importFile.value) {
        ElMessage.error('请选择要导入的文件');
        return;
    }
    if (!importForm.project_id) {
        ElMessage.error('请选择目标项目');
        return;
    }
    
    importing.value = true;
    importResult.value = null;
    
    try {
        const formData = new FormData();
        formData.append('file', importFile.value);
        formData.append('project_id', importForm.project_id);
        if (importForm.subsystem_id) {
            formData.append('subsystem_id', importForm.subsystem_id);
        }
        if (importForm.group_id) {
            formData.append('group_id', importForm.group_id);
        }
        
        const response = await axios.post('/api/services/import', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
        
        if (response.data.code === 0) {
            const data = response.data.data;
            importResult.value = {
                success_count: data.added || 0,
                updated_count: data.updated || 0,
                failed_count: data.failed || 0,
                failed_rows: data.failed_items?.map((item, idx) => ({
                    row_num: idx + 2,
                    error: item.reason
                })) || []
            };
            
            let message = `导入完成！成功：${importResult.value.success_count}条，更新：${importResult.value.updated_count}条`;
            if (importResult.value.failed_count > 0) {
                message += `，失败：${importResult.value.failed_count}条`;
            }
            ElMessage.success(message);
            
            // 更新历史记录
            importHistory.value.unshift({
                filename: importFile.value.name,
                time: new Date().toLocaleString('zh-CN'),
                success: importResult.value.failed_count === 0
            });
            if (importHistory.value.length > 5) {
                importHistory.value.pop();
            }
        } else {
            ElMessage.error(response.data.message || '导入失败');
        }
    } catch (error) {
        ElMessage.error(error.response?.data?.message || '导入失败');
    } finally {
        importing.value = false;
    }
};

const resetForm = () => {
  importForm.project_id = null;
  importForm.subsystem_id = null;
  importForm.group_id = null;
  importFile.value = null;
  importResult.value = null;
  subsystems.value = [];
  groups.value = [];
};

onMounted(() => {
  loadProjects();
  // 先从本地存储加载历史记录
  const savedHistory = localStorage.getItem('importHistory');
  if (savedHistory) {
    importHistory.value = JSON.parse(savedHistory);
  }
});

// 监听历史记录变化，保存到本地
watch(importHistory, (newVal) => {
  localStorage.setItem('importHistory', JSON.stringify(newVal));
}, { deep: true });
</script>

<style scoped>
.import-services-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px 20px;
}

.page-header {
  text-align: center;
  margin-bottom: 30px;
}

.header-content {
  color: #fff;
}

.title-section {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
  margin-bottom: 10px;
}

.title-icon {
  font-size: 36px;
}

.page-header h1 {
  font-size: 32px;
  font-weight: 600;
  margin: 0;
}

.subtitle {
  font-size: 16px;
  opacity: 0.9;
  margin: 0;
}

.page-content {
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.filter-card,
.upload-card,
.preview-card,
.result-card,
.action-card,
.history-card,
.tips-card {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  border-bottom: 1px solid #e8e8e8;
}

.card-icon {
  color: #667eea;
  font-size: 18px;
}

.card-header span {
  font-weight: 600;
  color: #333;
}

.filter-form {
  padding: 24px;
}

.full-width {
  width: 100%;
}

.form-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

.form-hint el-icon {
  font-size: 12px;
  color: #667eea;
}

.upload-area {
  margin: 24px;
  border: 2px dashed #d9d9d9;
  border-radius: 12px;
  padding: 40px 20px;
  text-align: center;
  transition: all 0.3s ease;
  background: #fafafa;
}

.upload-area:hover {
  border-color: #667eea;
  background: #f5f7ff;
}

.upload-area-dragover {
  border-color: #667eea;
  background: #f0f4ff;
  transform: scale(1.02);
}

.upload-icon-wrapper {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-icon {
  font-size: 40px;
  color: #fff;
}

.upload-text {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.upload-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.upload-subtitle {
  font-size: 14px;
  color: #999;
}

.upload-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
  color: #999;
  font-size: 13px;
}

.tip-icon {
  font-size: 14px;
}

.template-section {
  padding: 0 24px 24px;
  text-align: center;
}

.preview-content {
  padding: 24px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.file-icon {
  width: 50px;
  height: 50px;
  border-radius: 8px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 24px;
}

.file-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.file-size {
  font-size: 13px;
  color: #999;
}

.result-content {
  padding: 24px;
}

.result-summary {
  display: flex;
  justify-content: center;
  gap: 40px;
  margin-bottom: 24px;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  border-radius: 12px;
}

.summary-item.success {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.summary-item.success .summary-icon {
  color: #52c41a;
}

.summary-item.warning {
  background: #fff7e6;
  border: 1px solid #ffd591;
}

.summary-item.warning .summary-icon {
  color: #faad14;
}

.summary-item.error {
  background: #fff2f0;
  border: 1px solid #ffccc7;
}

.summary-item.error .summary-icon {
  color: #ff4d4f;
}

.summary-icon {
  font-size: 24px;
}

.summary-info {
  display: flex;
  flex-direction: column;
}

.summary-value {
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.summary-label {
  font-size: 13px;
  color: #999;
}

.error-list {
  border: 1px solid #ffccc7;
  border-radius: 8px;
  overflow: hidden;
}

.error-list-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fff2f0;
  border-bottom: 1px solid #ffccc7;
}

.error-icon {
  color: #ff4d4f;
}

.error-list-header span {
  font-weight: 600;
  color: #ff4d4f;
}

.action-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
}

.action-left {
  display: flex;
  gap: 12px;
}

.action-right {
  display: flex;
  align-items: center;
}

.back-link {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #11998e;
  text-decoration: none;
  font-size: 14px;
}

.back-link:hover {
  text-decoration: underline;
}

.history-list {
  padding: 24px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px dashed #eee;
}

.history-item:last-child {
  border-bottom: none;
}

.history-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.history-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.history-time {
  font-size: 12px;
  color: #999;
}

.empty-history {
  padding: 40px;
  text-align: center;
  color: #999;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  display: block;
  opacity: 0.5;
}

.tips-list {
  padding: 20px 24px;
  margin: 0;
  list-style: none;
}

.tips-list li {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px dashed #eee;
}

.tips-list li:last-child {
  border-bottom: none;
}

.tip-item-icon {
  color: #52c41a;
  font-size: 16px;
}

.tips-list li span {
  font-size: 14px;
  color: #666;
}

@media (max-width: 768px) {
  .result-summary {
    flex-direction: column;
    gap: 15px;
  }
  
  .action-card {
    flex-direction: column;
    gap: 15px;
    align-items: stretch;
  }
  
  .action-left {
    flex-direction: column;
  }
  
  .action-right {
    justify-content: center;
  }
}
</style>
