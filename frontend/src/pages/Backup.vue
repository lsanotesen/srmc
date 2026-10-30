<template>
  <div class="backup-page">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <el-icon class="title-icon"><Box /></el-icon>
          <h1>数据备份</h1>
        </div>
        <p class="subtitle">备份系统数据库，支持定时自动备份与手动备份、一键恢复</p>
      </div>
    </div>

    <div class="page-content">
      <!-- 顶部两栏：定时备份配置 + 手动备份 -->
      <div class="top-row">
        <!-- 备份配置 -->
        <div class="config-card">
          <div class="card-header config-header">
            <div class="manual-title">
              <el-icon class="card-icon"><Setting /></el-icon>
              <span>定时备份配置</span>
            </div>
            <div v-if="config.last_run_at" class="config-hint">上次执行：{{ config.last_run_at }}</div>
          </div>
        <el-form :model="config" label-width="72px" v-loading="loadingConfig" class="config-form">
          <div class="config-row">
            <el-form-item label="定时备份">
              <el-switch
                v-model="config.enabled"
                active-text="开启"
                inactive-text="关闭"
              />
            </el-form-item>
            <el-form-item label="执行频率">
              <el-select v-model="config.schedule_type" class="cfg-select">
                <el-option label="每天" value="daily" />
                <el-option label="每周" value="weekly" />
              </el-select>
            </el-form-item>
            <el-form-item label="执行时间">
              <el-time-picker
                v-model="config.timeObj"
                format="HH:mm"
                placeholder="选择时间"
                class="cfg-select"
              />
            </el-form-item>
            <el-form-item v-if="config.schedule_type === 'weekly'" label="星期">
              <el-select v-model="config.week_day" class="cfg-select">
                <el-option
                  v-for="(name, idx) in weekNames"
                  :key="idx"
                  :label="name"
                  :value="idx"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="保留份数">
              <el-input-number
                v-model="config.retention_count"
                :min="1"
                :max="100"
                class="cfg-number"
              />
            </el-form-item>
          </div>
          <div class="config-actions">
            <el-button type="primary" @click="saveConfig">保存配置</el-button>
          </div>
        </el-form>
        </div>

        <!-- 手动备份 -->
        <div class="manual-card">
          <div class="card-header">
            <el-icon class="card-icon"><CirclePlus /></el-icon>
            <span>手动备份</span>
          </div>
          <div class="manual-body">
            <div class="manual-info">
              <el-icon class="manual-icon"><InfoFilled /></el-icon>
              <p class="manual-desc">
                立即对数据库业务表做一次全量逻辑备份（mysqldump + gzip 压缩），审计日志大表不参与备份。恢复前系统会自动再做一次当前状态快照兜底。
              </p>
            </div>
          </div>
          <div class="manual-actions">
            <el-button class="manual-btn" type="success" :loading="running" @click="runBackup">
              <el-icon><Upload /></el-icon><span class="manual-btn-text">立即备份</span>
            </el-button>
          </div>
        </div>
      </div>

      <!-- 备份记录 -->
      <div class="records-card">
        <div class="card-header">
          <el-icon class="card-icon"><Files /></el-icon>
          <span>备份记录</span>
          <el-button link type="primary" @click="loadRecords" style="margin-left: auto;">
            <el-icon><Refresh /></el-icon>&nbsp;刷新
          </el-button>
        </div>
        <ListStats :items="statsItems" />
        <el-table :data="records" v-loading="loadingRecords" border stripe>
          <el-table-column prop="filename" label="文件名" min-width="260" show-overflow-tooltip />
          <el-table-column label="大小" min-width="78" align="right">
            <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
          </el-table-column>
          <el-table-column label="类型" min-width="70">
            <template #default="{ row }">
              <el-tag :type="typeTagMap[row.backup_type]?.tag || 'info'" size="small">
                {{ typeTagMap[row.backup_type]?.label || row.backup_type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="70">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
                {{ statusMap[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="table_count" label="表数" min-width="55" align="right" />
          <el-table-column label="耗时" min-width="66" align="right">
            <template #default="{ row }">{{ row.duration_ms ? (row.duration_ms / 1000).toFixed(1) + 's' : '-' }}</template>
          </el-table-column>
          <el-table-column prop="created_by" label="触发人" min-width="72" show-overflow-tooltip />
          <el-table-column prop="created_at" label="时间" min-width="150" />
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :disabled="row.status !== 'success'" @click="download(row)">
                <el-icon><Download /></el-icon>下载
              </el-button>
              <el-button link type="warning" :disabled="row.status !== 'success' || row.backup_type === 'pre_restore'" @click="restore(row)">
                <el-icon><RefreshLeft /></el-icon>恢复
              </el-button>
              <el-button link type="danger" @click="remove(row)">
                <el-icon><Delete /></el-icon>删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="pagination.page"
            :page-size="pagination.size"
            :total="pagination.total"
            layout="total, prev, pager, next"
            @current-change="loadRecords"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import axios from '@/utils/axios';
import ListStats from '@/components/ListStats.vue';

const loadingConfig = ref(false);
const loadingRecords = ref(false);
const running = ref(false);

const config = reactive({
  enabled: false,
  schedule_type: 'daily',
  timeObj: null,      // Date 对象给 el-time-picker 用
  schedule_time: '02:00',
  week_day: 1,
  retention_count: 10,
  last_run_at: ''
});

const records = ref([]);
const pagination = reactive({ page: 1, size: 20, total: 0 });
// 统计：备份记录总数（接口分页 total，无筛选）与本页条数
const statsItems = computed(() => [
  { label: '备份记录总数', value: `${pagination.total} 条` },
  { label: '本页', value: `${records.value.length} 条` }
]);

const weekNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
const typeTagMap = {
  manual: { tag: 'primary', label: '手动' },
  scheduled: { tag: '', label: '定时' },
  pre_import: { tag: 'warning', label: '导入前快照' },
  pre_restore: { tag: 'danger', label: '恢复前快照' },
};
const statusMap = { success: '成功', failed: '失败', running: '进行中' };

const parseTime = (s) => {
  if (!s) return null;
  const [h, m] = s.split(':').map(Number);
  const d = new Date();
  d.setHours(h || 0); d.setMinutes(m || 0); d.setSeconds(0);
  return d;
};

const loadConfig = async () => {
  loadingConfig.value = true;
  try {
    const res = await axios.get('/api/backup/config');
    const c = res.data?.data || {};
    config.enabled = !!c.enabled;
    config.schedule_type = c.schedule_type || 'daily';
    config.schedule_time = c.schedule_time || '02:00';
    config.timeObj = parseTime(c.schedule_time);
    config.week_day = c.week_day ?? 1;
    config.retention_count = c.retention_count ?? 10;
    config.last_run_at = c.last_run_at || '';
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '加载配置失败');
  } finally {
    loadingConfig.value = false;
  }
};

const saveConfig = async () => {
  try {
    let t = config.schedule_time;
    if (config.timeObj) {
      const hh = String(config.timeObj.getHours()).padStart(2, '0');
      const mm = String(config.timeObj.getMinutes()).padStart(2, '0');
      t = `${hh}:${mm}`;
    }
    await axios.put('/api/backup/config', {
      enabled: config.enabled ? 1 : 0,
      schedule_type: config.schedule_type,
      schedule_time: t,
      week_day: config.week_day,
      retention_count: config.retention_count
    });
    ElMessage.success('配置已保存，定时任务已更新');
    loadConfig();
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '保存失败');
  }
};

const runBackup = async () => {
  running.value = true;
  try {
    const res = await axios.post('/api/backup/run');
    ElMessage.success(res.data?.message || '备份完成');
    loadRecords();
    loadConfig();
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '备份失败');
  } finally {
    running.value = false;
  }
};

const loadRecords = async () => {
  loadingRecords.value = true;
  try {
    const res = await axios.get('/api/backup/records', {
      params: { page: pagination.page, size: pagination.size }
    });
    const data = res.data?.data || {};
    records.value = data.items || [];
    pagination.total = data.total || 0;
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '加载备份记录失败');
  } finally {
    loadingRecords.value = false;
  }
};

const download = async (row) => {
  try {
    const response = await axios.get(`/api/backup/${row.id}/download`, {
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const a = document.createElement('a');
    a.href = url;
    a.download = row.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (e) {
    ElMessage.error('下载失败');
  }
};

const restore = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt(
      `即将把数据库恢复到 ${row.created_at} 的状态（来源文件：${row.filename}）。\n` +
      `此操作会覆盖当前全部业务数据！恢复前会自动生成一份当前状态的快照。\n` +
      `请输入完整文件名以确认操作。`,
      '高危操作确认',
      {
        confirmButtonText: '确认恢复',
        cancelButtonText: '取消',
        inputPlaceholder: row.filename,
        inputValidator: (v) => (v && v.trim() === row.filename) || '输入的文件名不匹配'
      }
    );
    const res = await axios.post(`/api/backup/${row.id}/restore`, {
      confirm_filename: value.trim()
    });
    ElMessage.success(res.data?.message || '恢复成功');
    // 恢复后强制刷新页面，清空旧页面缓存状态
    setTimeout(() => window.location.reload(), 800);
  } catch (e) {
    if (e === 'cancel') return;
    ElMessage.error(e.response?.data?.message || e.message || '恢复失败');
  }
};

const remove = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除备份「${row.filename}」？该文件不可恢复`, '提示', { type: 'warning' });
    await axios.delete(`/api/backup/records/${row.id}`);
    ElMessage.success('已删除');
    loadRecords();
  } catch (e) {
    if (e === 'cancel') return;
    ElMessage.error(e.response?.data?.message || '删除失败');
  }
};

const formatSize = (bytes) => {
  if (!bytes) return '-';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1024 / 1024).toFixed(2) + ' MB';
};

onMounted(() => {
  loadConfig();
  loadRecords();
});
</script>

<style scoped>
.backup-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  font-size: 28px;
  color: #409eff;
}

.subtitle {
  color: var(--app-text-3);
  font-size: 13px;
  margin-top: 4px;
}

.config-card, .manual-card, .records-card {
  background: var(--app-panel);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

/* 两栏等宽后，手动备份卡片内边距与其他卡片保持一致 */
.manual-card {
  padding: 20px;
}

.manual-card .card-header {
  margin-bottom: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 16px;
  color: var(--app-text);
}

.card-icon {
  color: #409eff;
}

.hint-text {
  color: var(--app-text-2);
  font-size: 13px;
}

/* 定时备份配置：开关/频率/时间/星期/保留份数/保存 排在同一行 */
.config-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0 14px;
}

.config-row :deep(.el-form-item) {
  margin-bottom: 0;
}


.config-row :deep(.el-form-item__content) {
  gap: 12px;
}

.cfg-select {
  width: 90px;
}

.cfg-number {
  width: 100px;
}

/* 时间选择器根节点带 EP 双类名，需用 :deep 覆盖默认宽度 */
.config-row :deep(.el-date-editor) {
  width: 90px;
}

/* 备份记录表格：加大单元格上下留白，操作列左右留白并与数据列分隔 */
.records-card :deep(.el-table th.el-table__cell),
.records-card :deep(.el-table td.el-table__cell) {
  padding: 12px 0;
}

.records-card :deep(.el-table .el-table-fixed-column--right .cell) {
  padding-left: 16px;
  padding-right: 16px;
}

.records-card :deep(.el-table th.el-table-fixed-column--right) {
  border-left: 1px solid var(--app-border);
}

.config-header {
  justify-content: space-between;
}

.config-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--app-text-2);
}

.form-hint-inline {
  font-size: 12px;
  color: var(--app-text-3);
  padding-left: 110px;
}

/* 顶部两栏：定时备份配置 + 手动备份 */
.top-row {
  display: flex;
  gap: 20px;
  align-items: stretch;
  margin-bottom: 20px;
}

.top-row > .config-card,
.top-row > .manual-card {
  flex: 1 1 0;
  min-width: 0;
  margin-bottom: 0;
}

.config-card {
  display: flex;
  flex-direction: column;
}

/* 表单在卡片内纵向撑开，让配置行与操作按钮分离 */
.top-row > .config-card :deep(.el-form) {
  display: flex;
  flex-direction: column;
  flex: 1;
}

/* 保存配置固定在卡片右下角，与右侧「立即备份」同一水平线 */
.config-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: auto;
  padding-top: 12px;
}

.manual-card {
  display: flex;
  flex-direction: column;
}

.manual-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.manual-body {
  display: flex;
  align-items: flex-start;
}

/* 按钮固定在卡片右下角 */
.manual-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: auto;
  padding-top: 12px;
}

/* 窄屏回落为单栏 */
@media (max-width: 1100px) {
  .top-row {
    flex-direction: column;
  }

  .top-row > .config-card,
  .top-row > .manual-card {
    margin-bottom: 0;
  }
}

.manual-info {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.manual-icon {
  flex: none;
  margin-top: 4px;
  font-size: 14px;
  color: var(--app-text-2);
}

.manual-desc {
  flex: 1;
  max-width: 860px;
  color: var(--app-text-2);
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
  text-wrap: pretty;
}

.manual-btn {
  flex: none;
  min-width: 132px;
}

.manual-btn-text {
  margin-left: 2px;
}

.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
