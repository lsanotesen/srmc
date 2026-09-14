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
      <!-- 备份配置 -->
      <div class="config-card">
        <div class="card-header">
          <el-icon class="card-icon"><Setting /></el-icon>
          <span>定时备份配置</span>
        </div>
        <el-form :model="config" label-width="110px" v-loading="loadingConfig" class="config-form">
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="定时备份">
                <el-switch
                  v-model="config.enabled"
                  active-text="开启"
                  inactive-text="关闭"
                />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="执行频率">
                <el-select v-model="config.schedule_type" style="width: 100%">
                  <el-option label="每天" value="daily" />
                  <el-option label="每周" value="weekly" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="执行时间">
                <el-time-picker
                  v-model="config.timeObj"
                  format="HH:mm"
                  placeholder="选择时间"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item v-if="config.schedule_type === 'weekly'" label="星期">
                <el-select v-model="config.week_day" style="width: 100%">
                  <el-option
                    v-for="(name, idx) in weekNames"
                    :key="idx"
                    :label="name"
                    :value="idx"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="保留份数">
                <el-input-number
                  v-model="config.retention_count"
                  :min="1"
                  :max="100"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="">
                <el-button type="primary" @click="saveConfig">保存配置</el-button>
                <span v-if="config.last_run_at" class="hint-text" style="margin-left: 12px;">
                  上次执行：{{ config.last_run_at }}
                </span>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </div>

      <!-- 手动备份 -->
      <div class="manual-card">
        <div class="card-header">
          <el-icon class="card-icon"><CirclePlus /></el-icon>
          <span>手动备份</span>
        </div>
        <div class="manual-body">
          <p class="manual-desc">
            立即对数据库业务表做一次全量逻辑备份（mysqldump + gzip 压缩），审计日志大表不参与备份。恢复前系统会自动再做一次当前状态快照兜底。
          </p>
          <el-button type="success" size="large" :loading="running" @click="runBackup">
            <el-icon><Upload /></el-icon>&nbsp;立即备份
          </el-button>
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
        <el-table :data="records" v-loading="loadingRecords" border stripe>
          <el-table-column prop="filename" label="文件名" min-width="240" show-overflow-tooltip />
          <el-table-column label="大小" width="100">
            <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
          </el-table-column>
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              <el-tag :type="typeTagMap[row.backup_type]?.tag || 'info'" size="small">
                {{ typeTagMap[row.backup_type]?.label || row.backup_type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
                {{ statusMap[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="table_count" label="表数" width="70" />
          <el-table-column label="耗时" width="90">
            <template #default="{ row }">{{ row.duration_ms ? (row.duration_ms / 1000).toFixed(1) + 's' : '-' }}</template>
          </el-table-column>
          <el-table-column prop="created_by" label="触发人" width="90" />
          <el-table-column prop="created_at" label="时间" width="165" />
          <el-table-column label="操作" width="190" fixed="right">
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
import { ref, reactive, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import axios from '@/utils/axios';

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
  color: #909399;
  font-size: 13px;
  margin-top: 4px;
}

.config-card, .manual-card, .records-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 16px;
  color: #303133;
}

.card-icon {
  color: #409eff;
}

.hint-text {
  color: #606266;
  font-size: 13px;
}

.form-hint-inline {
  font-size: 12px;
  color: #909399;
  padding-left: 110px;
}

.manual-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.manual-desc {
  flex: 1;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
}

.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
