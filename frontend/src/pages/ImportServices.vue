<template>
  <div class="import-services-page">
    <!-- 顶部操作区 -->
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon"><Upload /></el-icon>
        <h2>服务导入</h2>
        <span class="header-sep">|</span>
        <span class="header-desc">上传 Excel 文件批量导入服务数据</span>
      </div>
      <div class="header-right">
        <el-button @click="resetForm" :disabled="!importFile && !importResult">
          <el-icon><RefreshLeft /></el-icon>
          重置
        </el-button>
        <router-link to="/services" class="back-link">
          <el-icon><ArrowLeft /></el-icon>
          返回服务列表
        </router-link>
      </div>
    </div>

    <!-- 主体 -->
    <div class="page-body">
      <!-- 第一步：配置目标 -->
      <div class="section-card">
        <div class="section-title">
          <span class="step-num">1</span>
          <span>配置目标项目</span>
        </div>
        <el-form :model="importForm" label-width="70px" inline class="config-form">
          <el-form-item label="项目">
            <el-select v-model="importForm.project_id" placeholder="请选择项目" clearable style="width: 200px" @change="handleProjectChange">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="子系统">
            <el-select v-model="importForm.subsystem_id" placeholder="请选择子系统" clearable style="width: 180px" @change="handleSubsystemChange">
              <el-option v-for="s in subsystems" :key="s.id" :label="s.subsystem_name" :value="s.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="分组">
            <el-select v-model="importForm.group_id" placeholder="可选" clearable style="width: 180px" :disabled="!importForm.subsystem_id">
              <el-option label="按Sheet自动匹配" :value="null" />
              <el-option v-for="g in groups" :key="g.id" :label="g.group_name" :value="g.id" />
            </el-select>
          </el-form-item>
          <el-form-item label-width="0">
            <div class="form-hint">
              <el-icon><InfoFilled /></el-icon>
              <span>不选分组时，按 Excel Sheet 名自动匹配或创建</span>
            </div>
          </el-form-item>
        </el-form>
      </div>

      <!-- 第二步：上传文件 -->
      <div class="section-card">
        <div class="section-title">
          <span class="step-num">2</span>
          <span>上传文件</span>
        </div>
        <div class="upload-row">
          <div
            class="upload-area"
            :class="{ 'has-file': importFile }"
          >
            <el-upload
              :auto-upload="false"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
              accept=".xlsx"
              drag
              :limit="1"
              :disabled="importing"
              class="upload-inner"
            >
              <template v-if="!importFile">
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <div class="upload-text">
                  <span>拖拽文件到此处，或 <span class="link-blue">点击选择</span></span>
                  <span class="upload-sub">支持 .xlsx 格式，不超过 10MB</span>
                </div>
              </template>
              <template v-else>
                <div class="file-selected">
                  <el-icon class="file-ico"><FileText /></el-icon>
                  <div class="file-info">
                    <span class="file-name">{{ importFile.name }}</span>
                    <span class="file-size">{{ formatFileSize(importFile.size) }}</span>
                  </div>
                </div>
              </template>
            </el-upload>
          </div>
          <div class="upload-actions">
            <el-button type="primary" size="large" style="width:160px" @click="doImport" :loading="importing" :disabled="!importFile || !importForm.project_id">
              <el-icon><Upload /></el-icon>
              {{ importing ? '导入中...' : '开始导入' }}
            </el-button>
            <el-button size="large" style="width:160px" @click="downloadTemplate">
              <el-icon><Download /></el-icon>
              下载模板
            </el-button>
          </div>
        </div>
      </div>

      <!-- 第三步：导入结果 -->
      <div v-if="importResult" class="section-card result-card">
        <div class="section-title">
          <span class="step-num">3</span>
          <span>导入结果</span>
          <el-tag v-if="importResult.reverted" type="info" size="small" style="margin-left:8px">已撤销</el-tag>
        </div>
        <div v-if="importResult.batch_no && !importResult.reverted" class="revert-bar">
          <el-icon><Warning /></el-icon>
          <span>目标项目选错了？可以撤销本次导入。</span>
          <el-button type="danger" size="small" plain :loading="revertingNo === importResult.batch_no" @click="revertBatch({ batch_no: importResult.batch_no })">撤销本次导入</el-button>
        </div>
        <div class="stat-row">
          <div class="stat-item stat-success">
            <span class="stat-num">{{ importResult.success_count }}</span>
            <span class="stat-label">成功导入</span>
          </div>
          <div class="stat-item stat-warning">
            <span class="stat-num">{{ importResult.skipped_count }}</span>
            <span class="stat-label">跳过重复</span>
          </div>
          <div v-if="importResult.repaired_count > 0" class="stat-item stat-warning">
            <span class="stat-num">{{ importResult.repaired_count }}</span>
            <span class="stat-label">补全归属</span>
          </div>
          <div class="stat-item stat-error">
            <span class="stat-num">{{ importResult.failed_count }}</span>
            <span class="stat-label">导入失败</span>
          </div>
        </div>
        <div v-if="importResult.failed_rows && importResult.failed_rows.length > 0" class="error-detail">
          <div class="error-title">失败详情</div>
          <el-table :data="importResult.failed_rows" border size="small" :max-height="180">
            <el-table-column prop="row_num" label="行号" width="60" />
            <el-table-column prop="sheet" label="Sheet" width="120" />
            <el-table-column prop="error" label="失败原因" min-width="200">
              <template #default="scope">
                <div>{{ scope.row.error }}</div>
                <div v-if="scope.row.missing_fields" style="color:#e6a23c;font-size:12px">缺少: {{ scope.row.missing_fields.join('、') }}</div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- 导入历史 -->
      <div class="section-card">
        <div class="section-title">
          <span class="section-title-text">导入历史</span>
          <span class="section-title-sub">支持撤销误导入</span>
        </div>
        <el-table v-if="serverBatches.length > 0" :data="serverBatches" border size="small" :max-height="240">
          <el-table-column prop="filename" label="文件名" min-width="180" show-overflow-tooltip />
          <el-table-column prop="project_name" label="目标项目" width="140" show-overflow-tooltip />
          <el-table-column label="新增/补全" width="100" align="center">
            <template #default="{ row }">{{ row.added_count }} / {{ row.repaired_count }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="导入时间" width="160" />
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'reverted'" type="info" size="small">已撤销</el-tag>
              <el-tag v-else type="success" size="small">有效</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ row }">
              <el-button v-if="row.status === 'active'" link type="danger" size="small" :loading="revertingNo === row.batch_no" @click="revertBatch(row)">撤销</el-button>
              <span v-else style="color:var(--app-text-3)">-</span>
            </template>
          </el-table-column>
        </el-table>
        <div v-else class="empty-history">
          <el-icon class="empty-icon"><Document /></el-icon>
          <span>暂无导入记录</span>
        </div>
      </div>

      <!-- 导入提示 -->
      <el-collapse class="tips-collapse" :active-name="['tips']">
        <el-collapse-item name="tips">
          <template #title>
            <el-icon style="margin-right:4px"><InfoFilled /></el-icon>
            导入提示
          </template>
          <div class="tips-content">
            <p><el-icon color="#67c23a"><Select /></el-icon> 建议先下载模板，按模板格式填写数据</p>
            <p><el-icon color="#67c23a"><Select /></el-icon> 功能描述为必填项，其他字段根据需要填写</p>
            <p><el-icon color="#67c23a"><Select /></el-icon> IP地址和端口号请确保格式正确</p>
            <p><el-icon color="#e6a23c"><Warning /></el-icon> 选错项目可在导入结果页或历史中撤销</p>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
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
const importResult = ref(null);
const serverBatches = ref([]);
const revertingNo = ref('');

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
                skipped_count: data.skipped || 0,
                repaired_count: data.repaired || 0,
                failed_count: data.failed || 0,
                batch_no: data.batch_no || '',
                pre_backup_record_id: data.pre_backup_record_id || null,
                reverted: false,
                failed_rows: data.failed_items?.map((item) => ({
                    row_num: item.row || 0,
                    sheet: item.sheet || '',
                    error: item.reason,
                    missing_fields: item.missing_fields || []
                })) || []
            };
            
            let message = `导入完成！成功：${importResult.value.success_count}条，跳过：${importResult.value.skipped_count}条`;
            if (importResult.value.repaired_count > 0) {
                message += `，补全归属：${importResult.value.repaired_count}条`;
            }
            if (importResult.value.failed_count > 0) {
                message += `，失败：${importResult.value.failed_count}条`;
            }
            ElMessage.success(message);

            loadServerBatches();
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

const loadServerBatches = async () => {
  try {
    const res = await axios.get('/api/services/import/batches', {
      params: { page: 1, size: 20 }
    });
    serverBatches.value = res.data?.data?.items || [];
  } catch (error) {
    console.error('加载导入历史失败', error);
    serverBatches.value = [];
  }
};

const revertBatch = async (row) => {
  try {
    await ElMessageBox.confirm(
      '撤销本次导入将删除该批新增的服务，并把归属补全的服务还原为导入前的状态。确定继续？',
      '确认撤销导入',
      { confirmButtonText: '确认撤销', cancelButtonText: '取消', type: 'warning' }
    );
  } catch (e) {
    return;
  }

  revertingNo.value = row.batch_no;
  try {
    const res = await axios.post(`/api/services/import/batches/${row.batch_no}/revert`);
    const d = res.data?.data || {};
    if (importResult.value && importResult.value.batch_no === row.batch_no) {
      importResult.value.reverted = true;
    }
    ElMessage.success(
      `已撤销：删除${d.deleted_count ?? 0}条新增，还原${d.restored_count ?? 0}条归属`
      + (d.removed_groups ? `，清理${d.removed_groups}个自动创建的分类` : '')
    );
    loadServerBatches();
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '撤销失败');
  } finally {
    revertingNo.value = '';
  }
};

onMounted(() => {
  loadProjects();
  loadServerBatches();
});
</script>

<style scoped>
/* ============ 整体 ============ */
.import-services-page {
  padding: 24px;
  background: var(--app-panel-soft);
  min-height: calc(100vh - 60px);
}

/* ============ 顶部操作区 ============ */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 24px;
  background: linear-gradient(135deg, #667eea 0%, #5a67d8 100%);
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.25);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  font-size: 26px;
  color: #fff;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.15));
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #fff;
}

.header-sep {
  color: rgba(255,255,255,0.4);
  margin: 0 4px;
}

.header-desc {
  font-size: 13px;
  color: rgba(255,255,255,0.85);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-right .el-button {
  background: rgba(255,255,255,0.2);
  border: 1px solid rgba(255,255,255,0.3);
  color: #fff;
  backdrop-filter: blur(4px);
}

.header-right .el-button:hover {
  background: rgba(255,255,255,0.3);
  border-color: rgba(255,255,255,0.5);
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: rgba(255,255,255,0.9);
  text-decoration: none;
  font-size: 14px;
  padding: 6px 12px;
  border-radius: 6px;
  background: rgba(255,255,255,0.15);
  transition: background 0.2s;
}

.back-link:hover {
  background: rgba(255,255,255,0.25);
  color: #fff;
}

/* ============ 主体 ============ */
.page-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ============ 步骤卡片 ============ */
.section-card {
  background: var(--app-panel);
  border-radius: 10px;
  padding: 18px 22px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s;
}

.section-card:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 14px;
  margin-bottom: 16px;
  border-bottom: 1px solid #f0f2f5;
  font-size: 15px;
  font-weight: 600;
  color: var(--app-text);
}

.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #5a67d8 100%);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(102,126,234,0.35);
}

.section-title-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--app-text);
}

.section-title-sub {
  font-size: 12px;
  font-weight: normal;
  color: var(--app-text-3);
  margin-left: 6px;
}

/* ============ 配置表单 ============ */
.config-form {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  align-items: flex-start;
}

.config-form .el-form-item {
  margin-bottom: 0;
}

.form-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--app-text-3);
}

.form-hint .el-icon {
  font-size: 14px;
  color: #409eff;
}

/* ============ 上传区域 ============ */
.upload-row {
  display: flex;
  gap: 20px;
  align-items: stretch;
}

.upload-area {
  flex: 1;
  border: 2px dashed var(--app-border);
  border-radius: 8px;
  padding: 24px;
  background: linear-gradient(135deg, var(--app-panel-soft) 0%, var(--app-panel-soft) 100%);
  transition: all 0.25s ease;
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-area:hover {
  border-color: #667eea;
  background: linear-gradient(135deg, #f5f7ff 0%, #eef1ff 100%);
}

.upload-area.has-file {
  border-style: solid;
  border-color: #67c23a;
  background: linear-gradient(135deg, #f0f9eb 0%, #e6f7ea 100%);
}

.upload-inner {
  width: 100%;
}

.upload-icon {
  font-size: 48px;
  color: var(--app-text-3);
  margin-bottom: 10px;
  transition: color 0.2s;
}

.upload-area:hover .upload-icon {
  color: #667eea;
}

.upload-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: var(--app-text-2);
  font-size: 14px;
}

.upload-sub {
  font-size: 12px;
  color: var(--app-text-3);
}

.link-blue {
  color: #667eea;
  cursor: pointer;
  font-weight: 500;
}

.file-selected {
  display: flex;
  align-items: center;
  gap: 14px;
}

.file-ico {
  font-size: 42px;
  color: #667eea;
  filter: drop-shadow(0 2px 6px rgba(102,126,234,0.3));
}

.file-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--app-text);
}

.file-size {
  font-size: 13px;
  color: #67c23a;
}

.upload-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 160px;
  flex: 0 0 160px;
}

.upload-actions :deep(.el-button) {
  width: 160px !important;
  min-width: 160px !important;
  box-sizing: border-box !important;
  justify-content: center !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
  margin: 0 !important;
  border-width: 1px !important;
  border-style: solid !important;
  border-radius: 4px !important;
  box-shadow: none !important;
}

.upload-actions :deep(.el-button .el-icon) {
  margin-right: 4px !important;
}

/* ============ 结果卡片 ============ */
.result-card {
  border-left: 4px solid #67c23a;
  background: linear-gradient(135deg, #fff 0%, #f6ffed 100%);
}

.revert-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, #fdf6ec 0%, #faecd8 100%);
  border: 1px solid #faecd8;
  border-radius: 8px;
  padding: 10px 16px;
  margin-bottom: 16px;
  font-size: 13px;
  color: #b88230;
}

.revert-bar .el-icon {
  font-size: 16px;
  color: #e6a23c;
}

.stat-row {
  display: flex;
  gap: 14px;
  margin-bottom: 14px;
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 10px;
  border-radius: 8px;
  gap: 4px;
  transition: transform 0.2s;
}

.stat-item:hover {
  transform: translateY(-2px);
}

.stat-success {
  background: linear-gradient(135deg, #f0f9eb 0%, #e1f7d5 100%);
  border: 1px solid #b7eb8f;
}

.stat-warning {
  background: linear-gradient(135deg, #fdf6ec 0%, #faecd8 100%);
  border: 1px solid #ffd591;
}

.stat-error {
  background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
  border: 1px solid #ffccc7;
}

.stat-num {
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, #67c23a, #52c41a);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-warning .stat-num {
  background: linear-gradient(135deg, #faad14, #d48806);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-error .stat-num {
  background: linear-gradient(135deg, #ff4d4f, #cf1322);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-label {
  font-size: 12px;
  color: var(--app-text-2);
  font-weight: 500;
}

.error-detail {
  border: 1px solid var(--app-border);
  border-radius: 8px;
  overflow: hidden;
}

.error-title {
  padding: 8px 14px;
  background: #fef0f0;
  color: #f56c6c;
  font-weight: 600;
  font-size: 13px;
}

/* ============ 历史 ============ */
.empty-history {
  padding: 50px;
  text-align: center;
  color: var(--app-text-3);
}

.empty-icon {
  font-size: 44px;
  display: block;
  margin-bottom: 10px;
  opacity: 0.4;
  color: var(--app-text-3);
}

/* ============ 提示折叠 ============ */
.tips-collapse {
  background: var(--app-panel);
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.tips-collapse :deep(.el-collapse-item__header) {
  padding: 0 18px;
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
  border-bottom: none;
  height: 42px;
  line-height: 42px;
  background: linear-gradient(135deg, #f5f7fa 0%, #eef1fa 100%);
}

.tips-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.tips-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.tips-content {
  padding: 14px 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  color: var(--app-text-2);
}

.tips-content p {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 6px 10px;
  background: var(--app-panel-soft);
  border-radius: 6px;
  transition: background 0.2s;
}

.tips-content p:hover {
  background: var(--app-panel-soft);
}

/* ============ 响应式 ============ */
@media (max-width: 768px) {
  .upload-row {
    flex-direction: column;
  }
  .upload-actions {
    flex-direction: row;
    width: 100%;
  }
  .upload-actions .el-button {
    flex: 1;
  }
  .stat-row {
    flex-wrap: wrap;
  }
  .stat-item {
    min-width: 40%;
  }
  .page-header {
    flex-direction: column;
    gap: 10px;
    align-items: flex-start;
  }
}
</style>