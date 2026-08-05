<template>
  <div class="export-services-page">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <el-icon class="title-icon"><Download /></el-icon>
          <h1>服务导出</h1>
        </div>
        <p class="subtitle">选择项目和子系统，导出服务列表数据</p>
      </div>
    </div>

    <div class="page-content">
      <div class="filter-card">
        <div class="card-header">
          <el-icon class="card-icon"><Filter /></el-icon>
          <span>筛选条件</span>
        </div>
        <el-form :model="exportForm" label-width="120px" class="filter-form">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="项目名称">
                <el-select
                  v-model="exportForm.project_id"
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
                  v-model="exportForm.subsystem_id"
                  placeholder="请选择子系统"
                  clearable
                  class="full-width"
                  :disabled="!exportForm.project_id"
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
                  v-model="exportForm.group_id"
                  placeholder="请选择服务分组"
                  clearable
                  class="full-width"
                  :disabled="!exportForm.subsystem_id"
                >
                  <el-option label="全部分组" :value="null" />
                  <el-option v-for="group in groups" :key="group.id" :label="group.group_name" :value="group.id" />
                </el-select>
                <div class="form-hint">
                  <el-icon><InfoFilled /></el-icon>
                  <span>若不选择，将导出所有分组，每个分组单独一个Sheet</span>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="部署方式">
                <el-select
                  v-model="exportForm.deploy_type"
                  placeholder="请选择部署方式"
                  clearable
                  class="full-width"
                >
                  <el-option label="全部方式" :value="null" />
                  <el-option label="主机" value="主机" />
                  <el-option label="容器" value="容器" />
                </el-select>
                <div class="form-hint">
                  <el-icon><InfoFilled /></el-icon>
                  <span>若不选择，将导出所有部署方式的服务</span>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </div>

      <div class="preview-card">
        <div class="card-header">
          <el-icon class="card-icon"><Eye /></el-icon>
          <span>导出预览</span>
        </div>
        <div class="preview-content">
          <div class="preview-info">
            <div class="info-item">
              <span class="info-label">预计导出数量</span>
              <span class="info-value">{{ estimatedCount }} 条</span>
            </div>
            <div class="info-item">
              <span class="info-label">导出文件名</span>
              <span class="info-value">{{ generateFileName() }}</span>
            </div>
          </div>
          <div class="preview-hint">
            <el-icon class="hint-icon"><InfoFilled /></el-icon>
            <span>导出格式为 Excel (.xlsx)，包含服务的完整信息</span>
          </div>
        </div>
      </div>

      <div class="action-card">
        <div class="action-left">
          <el-button type="primary" size="large" @click="startExport" :loading="exporting">
            <el-icon><Download /></el-icon>
            {{ exporting ? '导出中...' : '开始导出' }}
          </el-button>
          <el-button size="large" @click="resetForm">
            <el-icon><Refresh /></el-icon>
            重置筛选
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
          <span>最近导出记录</span>
        </div>
        <div v-if="exportHistory.length > 0" class="history-list">
          <div v-for="(record, index) in exportHistory" :key="index" class="history-item">
            <div class="history-info">
              <span class="history-name">{{ record.filename }}</span>
              <span class="history-time">{{ record.time }}</span>
            </div>
            <el-button size="small" type="text" @click="reExport(record)">
              <el-icon><Refresh /></el-icon>
              重新导出
            </el-button>
          </div>
        </div>
        <div v-else class="empty-history">
          <el-icon class="empty-icon"><FileText /></el-icon>
          <p>暂无导出记录</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue';
import { ElMessage } from 'element-plus';
import axios from '@/utils/axios';

const exportForm = reactive({
  project_id: null,
  subsystem_id: null,
  group_id: null,
  deploy_type: null
});

const projects = ref([]);
const subsystems = ref([]);
const groups = ref([]);
const exporting = ref(false);
const estimatedCount = ref(0);

const exportHistory = ref([]);

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
  exportForm.subsystem_id = null;
  exportForm.group_id = null;
  if (projectId) {
    await loadSubsystems(projectId);
  } else {
    subsystems.value = [];
    groups.value = [];
  }
  await updateEstimatedCount();
};

const handleSubsystemChange = async (subsystemId) => {
  exportForm.group_id = null;
  if (subsystemId) {
    await loadGroups(subsystemId);
  } else {
    groups.value = [];
  }
  await updateEstimatedCount();
};

const updateEstimatedCount = async () => {
  try {
    const params = new URLSearchParams();
    if (exportForm.project_id) params.append('project_id', exportForm.project_id);
    if (exportForm.subsystem_id) params.append('subsystem_id', exportForm.subsystem_id);
    if (exportForm.group_id) params.append('group_id', exportForm.group_id);
    if (exportForm.deploy_type) params.append('deploy_type', exportForm.deploy_type);
    
    const response = await axios.get(`/api/services/count?${params}`);
    if (response.data.code === 0) {
      estimatedCount.value = response.data.data;
    }
  } catch (error) {
    console.error('获取统计数量失败', error);
  }
};

const getSelectedProjectName = () => {
  if (!exportForm.project_id) return '';
  const project = projects.value.find(p => p.id === exportForm.project_id);
  return project ? project.name : '';
};

const getSelectedSubsystemName = () => {
  if (!exportForm.subsystem_id) return '';
  const subsystem = subsystems.value.find(s => s.id === exportForm.subsystem_id);
  return subsystem ? subsystem.subsystem_name : '';
};

const generateFileName = () => {
  let filename = '服务列表';
  if (getSelectedProjectName()) {
    filename = getSelectedProjectName();
    if (getSelectedSubsystemName()) {
      filename += '-' + getSelectedSubsystemName();
    }
    filename += '_服务列表';
  }
  return `${filename}.xlsx`;
};

const startExport = async () => {
  exporting.value = true;
  try {
    const params = new URLSearchParams();
    if (exportForm.project_id) params.append('project_id', exportForm.project_id);
    if (exportForm.subsystem_id) params.append('subsystem_id', exportForm.subsystem_id);
    if (exportForm.group_id) params.append('group_id', exportForm.group_id);
    if (exportForm.deploy_type) params.append('deploy_type', exportForm.deploy_type);
    
    const response = await axios.get(`/api/services/export?${params}`, {
      responseType: 'blob'
    });
    
    const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = generateFileName();
    
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    ElMessage.success('导出成功');
    
    exportHistory.value.unshift({
      filename: generateFileName(),
      time: new Date().toLocaleString('zh-CN')
    });
    if (exportHistory.value.length > 5) {
      exportHistory.value.pop();
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '导出失败');
  } finally {
    exporting.value = false;
  }
};

const resetForm = () => {
  exportForm.project_id = null;
  exportForm.subsystem_id = null;
  exportForm.group_id = null;
  exportForm.deploy_type = null;
  subsystems.value = [];
  groups.value = [];
  estimatedCount.value = 0;
};

const reExport = (record) => {
  ElMessage.info('正在重新导出: ' + record.filename);
  startExport();
};

onMounted(() => {
  loadProjects();
  loadGroups();
  // 从本地存储加载历史记录
  const savedHistory = localStorage.getItem('exportHistory');
  if (savedHistory) {
    exportHistory.value = JSON.parse(savedHistory);
  }
});

// 监听历史记录变化，保存到本地
watch(exportHistory, (newVal) => {
  localStorage.setItem('exportHistory', JSON.stringify(newVal));
}, { deep: true });
</script>

<style scoped>
.export-services-page {
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
.preview-card,
.action-card,
.history-card {
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

.preview-content {
  padding: 24px;
}

.preview-info {
  display: flex;
  gap: 40px;
  margin-bottom: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.info-label {
  font-size: 14px;
  color: #999;
}

.info-value {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.preview-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 8px;
}

.hint-icon {
  color: #52c41a;
}

.preview-hint span {
  font-size: 14px;
  color: #52c41a;
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

@media (max-width: 768px) {
  .preview-info {
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
