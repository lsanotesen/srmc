<template>
  <div class="import-services-page">
    <div class="page-header">
      <h1>导入服务</h1>
      <div class="actions">
        <el-button @click="goBack">返回</el-button>
      </div>
    </div>

    <div class="import-container">
      <!-- 导入选项 -->
      <div class="import-options">
        <el-form :model="importForm" label-width="120px">
          <el-form-item label="目标项目">
            <el-select v-model="importForm.project_id" placeholder="请选择项目" @change="onProjectChange">
              <el-option v-for="project in projects" :key="project.id" :label="project.project_name" :value="project.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="目标子系统">
            <el-select v-model="importForm.subsystem_id" placeholder="请选择子系统" @change="onSubsystemChange">
              <el-option v-for="subsystem in subsystems" :key="subsystem.id" :label="subsystem.subsystem_name" :value="subsystem.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="目标程序分类">
            <el-select v-model="importForm.group_id" placeholder="请选择程序分类（可选）">
              <el-option :key="0" label="不指定（按Sheet名称匹配）" :value="0" />
              <el-option v-for="group in groups" :key="group.id" :label="group.group_name" :value="group.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-upload
              class="upload-demo"
              :auto-upload="false"
              :on-change="handleFileChange"
              accept=".xlsx"
              :show-file-list="false"
            >
              <el-button type="primary" :disabled="importing">选择Excel文件</el-button>
            </el-upload>
            <span v-if="importFile" class="file-name">{{ importFile.name }}</span>
          </el-form-item>
        </el-form>
      </div>

      <!-- 预览区域 -->
      <div v-if="previewData.length > 0" class="preview-section">
        <h3>数据预览（前5行）</h3>
        <div class="preview-table">
          <table>
            <thead>
              <tr>
                <th>行号</th>
                <th v-for="(header, index) in previewHeaders" :key="index">{{ header }}</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in previewData.slice(0, 5)" :key="index">
                <td>{{ index + 2 }}</td>
                <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell || '' }}</td>
                <td>
                  <span class="status-pending">待导入</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 导入按钮 -->
      <div class="import-actions">
        <el-button type="success" @click="startImport" :disabled="!canImport || importing">
          <span v-if="importing">导入中...</span>
          <span v-else>开始导入</span>
        </el-button>
        <el-button @click="downloadTemplate">下载模板</el-button>
      </div>

      <!-- 导入进度 -->
      <div v-if="importing" class="progress-section">
        <el-progress :percentage="progress" :status="progressStatus" />
        <div class="progress-info">
          <span>已处理: {{ processedCount }} / {{ totalCount }}</span>
          <span v-if="currentSheet">当前Sheet: {{ currentSheet }}</span>
        </div>
      </div>

      <!-- 导入结果 -->
      <div v-if="importResult" class="result-section">
        <div class="result-summary">
          <div class="result-item success">
            <span class="count">{{ importResult.added }}</span>
            <span class="label">新增</span>
          </div>
          <div class="result-item updated">
            <span class="count">{{ importResult.updated }}</span>
            <span class="label">更新</span>
          </div>
          <div class="result-item failed">
            <span class="count">{{ importResult.failed }}</span>
            <span class="label">失败</span>
          </div>
        </div>

        <!-- 失败详情 -->
        <div v-if="importResult.failed_items && importResult.failed_items.length > 0" class="failed-details">
          <h3>失败详情</h3>
          <div class="failed-list">
            <div v-for="(item, index) in importResult.failed_items" :key="index" class="failed-item">
              <div class="failed-header">
                <span class="sheet-name">{{ item.sheet }} - 第{{ item.row }}行</span>
                <span class="reason-badge">{{ item.reason }}</span>
              </div>
              <div v-if="item.missing_fields && item.missing_fields.length > 0" class="failed-detail">
                <span class="detail-label">缺失字段:</span>
                <span class="missing-fields">
                  <span v-for="(field, idx) in item.missing_fields" :key="idx" class="field-tag">{{ field }}</span>
                </span>
              </div>
              <div v-if="item.row_data && Object.keys(item.row_data).length > 0" class="failed-detail">
                <span class="detail-label">原始数据:</span>
                <div class="row-data-container">
                  <pre class="row-data">{{ formatRowData(item.row_data) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage, ElProgress } from 'element-plus';
import axios from '@/utils/axios';

// 字段名中文映射
const fieldNameMapping = {
  'func_desc': '功能描述',
  'module': '对应模块',
  'ip': 'IP地址',
  'username': '用户名',
  'password': '密码',
  'program_path': '程序路径',
  'start_script': '启动脚本',
  'stop_script': '停止脚本',
  'log_path': '日志路径',
  'port': '端口',
  'owner': '责任人',
  'remark': '备注'
};

// 格式化行数据为可读格式
const formatRowData = (rowData) => {
  if (!rowData) return '';
  const lines = [];
  for (const [key, value] of Object.entries(rowData)) {
    const fieldName = fieldNameMapping[key] || key;
    lines.push(`${fieldName}: ${value || ''}`);
  }
  return lines.join('\n');
};

const projects = ref([]);
const subsystems = ref([]);
const groups = ref([]);
const importForm = reactive({
  project_id: null,
  subsystem_id: null,
  group_id: 0
});

const importFile = ref(null);
const previewData = ref([]);
const previewHeaders = ref([]);
const importing = ref(false);
const progress = ref(0);
const progressStatus = ref('active');
const processedCount = ref(0);
const totalCount = ref(0);
const currentSheet = ref('');
const importResult = ref(null);

const canImport = () => {
  return importFile.value && importForm.project_id && importForm.subsystem_id;
};

const goBack = () => {
  window.history.back();
};

const onProjectChange = async () => {
  if (importForm.project_id) {
    subsystems.value = [];
    importForm.subsystem_id = null;
    groups.value = [];
    importForm.group_id = 0;
    
    try {
      const response = await axios.get(`/api/subsystems?project_id=${importForm.project_id}`);
      if (response.data.code === 0) {
        // 后端返回的是分页格式，需要提取items
        subsystems.value = response.data.data.items || response.data.data;
      }
    } catch (error) {
      ElMessage.error('加载子系统列表失败');
    }
  }
};

const onSubsystemChange = async () => {
  if (importForm.subsystem_id) {
    groups.value = [];
    importForm.group_id = 0;
    
    try {
      const response = await axios.get(`/api/subsystems/${importForm.subsystem_id}/groups`);
      if (response.data.code === 0) {
        // 后端返回的可能是数组或分页格式
        const data = response.data.data;
        groups.value = Array.isArray(data) ? data : (data.items || []);
      }
    } catch (error) {
      ElMessage.error('加载程序分类列表失败');
    }
  }
};

const handleFileChange = (file) => {
  importFile.value = file.raw;
  previewData.value = [];
  previewHeaders.value = [];
  importResult.value = null;
  
  // 预览文件内容
  previewFile(file.raw);
};

const previewFile = async (file) => {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await axios.post('/api/services/import/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    
    if (response.data.code === 0) {
      previewHeaders.value = response.data.data.headers;
      previewData.value = response.data.data.rows;
    }
  } catch (error) {
    ElMessage.error('预览文件失败');
  }
};

const startImport = async () => {
  if (!canImport()) {
    ElMessage.warning('请选择文件并填写目标项目和子系统');
    return;
  }

  importing.value = true;
  progress.value = 0;
  progressStatus.value = 'active';
  processedCount.value = 0;
  totalCount.value = 0;
  importResult.value = null;

  const formData = new FormData();
  formData.append('file', importFile.value);
  formData.append('project_id', importForm.project_id);
  formData.append('subsystem_id', importForm.subsystem_id);
  if (importForm.group_id && importForm.group_id !== 0) {
    formData.append('group_id', importForm.group_id);
  }

  try {
    const response = await axios.post('/api/services/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          progress.value = Math.round((progressEvent.loaded / progressEvent.total) * 100);
        }
      }
    });

    if (response.data.code === 0) {
      importResult.value = response.data.data;
      progress.value = 100;
      progressStatus.value = 'success';
      
      if (importResult.value.failed > 0) {
        ElMessage.warning(`导入完成，但有 ${importResult.value.failed} 条记录失败`);
      } else {
        ElMessage.success('导入成功');
      }
    } else {
      ElMessage.error(response.data.message || '导入失败');
      progressStatus.value = 'exception';
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '导入失败');
    progressStatus.value = 'exception';
  } finally {
    importing.value = false;
  }
};

const downloadTemplate = async () => {
  try {
    const response = await axios.get('/api/services/import/template', {
      responseType: 'blob'
    });
    
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', '服务导入模板.xlsx');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error('下载模板失败');
  }
};

onMounted(async () => {
  try {
    const response = await axios.get('/api/projects');
    if (response.data.code === 0) {
      // 后端返回的是分页格式，需要提取items
      projects.value = response.data.data.items || response.data.data;
    }
  } catch (error) {
    ElMessage.error('加载项目列表失败');
  }
});
</script>

<style scoped>
.import-services-page {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.page-header h1 {
  font-size: 24px;
  margin: 0;
}

.import-container {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.import-options {
  margin-bottom: 24px;
}

.file-name {
  margin-left: 12px;
  color: #666;
}

.preview-section {
  margin-bottom: 24px;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
}

.preview-section h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: #333;
}

.preview-table {
  overflow-x: auto;
}

.preview-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.preview-table th,
.preview-table td {
  border: 1px solid #e8e8e8;
  padding: 8px 12px;
  text-align: left;
}

.preview-table th {
  background: #f5f5f5;
  font-weight: 500;
}

.status-pending {
  color: #1890ff;
  font-size: 12px;
}

.import-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.progress-section {
  margin-bottom: 24px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 14px;
  color: #666;
}

.result-section {
  padding: 20px;
  background: #fafafa;
  border-radius: 8px;
}

.result-summary {
  display: flex;
  justify-content: center;
  gap: 60px;
  margin-bottom: 24px;
}

.result-item {
  text-align: center;
}

.result-item .count {
  display: block;
  font-size: 36px;
  font-weight: bold;
}

.result-item.success .count {
  color: #52c41a;
}

.result-item.updated .count {
  color: #1890ff;
}

.result-item.failed .count {
  color: #f5222d;
}

.result-item .label {
  font-size: 14px;
  color: #666;
}

.failed-details h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: #333;
}

.failed-list {
  max-height: 300px;
  overflow-y: auto;
}

.failed-item {
  padding: 12px;
  background: #fff;
  border-radius: 4px;
  margin-bottom: 12px;
  border-left: 4px solid #f5222d;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.failed-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}

.sheet-name {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.reason-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  color: #f5222d;
  font-size: 12px;
  font-weight: 500;
  flex-shrink: 0;
}

.failed-detail {
  display: flex;
  align-items: flex-start;
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 4px;
  margin-bottom: 10px;
  font-size: 13px;
}

.failed-detail:last-child {
  margin-bottom: 0;
}

.missing-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-left: 8px;
}

.field-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 20px;
  color: #f5222d;
  font-size: 12px;
  font-weight: 500;
}

.row-data-container {
  margin-left: 8px;
  flex: 1;
}

.row-data {
  margin: 0;
  padding: 8px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  color: #666;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 150px;
  overflow-y: auto;
}

.detail-label {
  color: #999;
  font-weight: 500;
  flex-shrink: 0;
  margin-right: 8px;
}

.detail-value {
  color: #666;
  word-break: break-all;
}
</style>