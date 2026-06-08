<template>
  <div class="program-list-page">
    <div class="page-header">
      <div class="header-left">
        <h2>后台程序管理</h2>
        <p class="subtitle">管理多台服务器上的业务程序，支持远程启停和日志查看</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="handleExport">
          <el-icon name="download" :size="18" />
          导出
        </el-button>
        <el-button type="success" @click="handleImport">
          <el-icon name="upload" :size="18" />
          导入
        </el-button>
        <el-button type="primary" @click="openAddForm">
          <el-icon name="plus" :size="18" />
          新增程序
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-input 
        v-model="filters.func_desc" 
        placeholder="功能描述" 
        class="filter-input"
      />
      <el-input 
        v-model="filters.module" 
        placeholder="模块" 
        class="filter-input"
      />
      <el-input 
        v-model="filters.ip" 
        placeholder="IP地址" 
        class="filter-input"
      />
      <el-input 
        v-model="filters.owner" 
        placeholder="负责人" 
        class="filter-input"
      />
      <el-button @click="loadPrograms">搜索</el-button>
    </div>

    <el-table :data="programList" border class="program-table">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="func_desc" label="功能描述" min-width="150" />
      <el-table-column prop="module" label="对应模块" min-width="100" />
      <el-table-column prop="ip" label="IP地址" min-width="120" />
      <el-table-column prop="username" label="SSH用户名" min-width="100" />
      <el-table-column prop="program_path" label="程序路径" min-width="200" />
      <el-table-column prop="start_script" label="启动脚本" min-width="120" />
      <el-table-column prop="stop_script" label="停止脚本" min-width="120" />
      <el-table-column prop="log_path" label="日志路径" min-width="150" />
      <el-table-column prop="port" label="程序端口" width="100" />
      <el-table-column prop="owner" label="负责人" width="100" />
      <el-table-column prop="remark" label="备注" min-width="100" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="scope">
          <el-tag :type="getStatusType(scope.row.status)">
            {{ scope.row.status || '未知' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="scope">
          <el-button size="small" @click="startProgram(scope.row)">启动</el-button>
          <el-button size="small" @click="stopProgram(scope.row)">停止</el-button>
          <el-button size="small" @click="restartProgram(scope.row)">重启</el-button>
          <el-button size="small" @click="viewLog(scope.row)">日志</el-button>
          <el-button size="small" @click="editProgram(scope.row)">编辑</el-button>
          <el-button size="small" type="danger" @click="deleteProgram(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="programList.length === 0" class="empty-state">
      <el-icon name="server" :size="48" class="empty-icon" />
      <p>暂无程序</p>
      <el-button type="primary" @click="openAddForm">新增程序</el-button>
    </div>

    <!-- 分页 -->
    <div class="pagination" v-if="total > 0">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 表单弹窗 -->
    <ProgramForm 
      :visible="showForm" 
      :edit-data="editData"
      :is-edit="isEdit"
      @close="showForm = false"
      @success="handleFormSuccess"
    />

    <!-- 日志弹窗 -->
    <LogDialog 
      :visible="showLog" 
      :program-id="currentLogId"
      @close="showLog = false"
    />

    <!-- 导入弹窗 -->
    <el-dialog title="导入程序" v-model="showImport">
      <el-upload
        class="upload-demo"
        :auto-upload="false"
        :on-change="handleFileChange"
        accept=".xlsx"
      >
        <el-button type="primary">选择文件</el-button>
      </el-upload>
      <p class="import-tip">支持.xlsx格式文件，可先下载模板</p>
      <el-button @click="downloadImportTemplate">下载模板</el-button>
      <template #footer>
        <el-button @click="showImport = false">取消</el-button>
        <el-button type="primary" @click="doImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>import { ref, reactive, onMounted, onUnmounted } from 'vue';
import { ElMessage } from 'element-plus';
import ProgramForm from '../components/ProgramForm.vue';
import LogDialog from '../components/LogDialog.vue';
import * as programApi from '../api/program';
const programList = ref([]);
const total = ref(0);
const page = ref(1);
const size = ref(10);
const showForm = ref(false);
const showLog = ref(false);
const showImport = ref(false);
const isEdit = ref(false);
const editData = ref(null);
const currentLogId = ref(null);
const importFile = ref(null);
let statusTimer = null;
const filters = reactive({
 func_desc: '',
 module: '',
 ip: '',
 owner: ''
});
function getStatusType(status) {
 switch (status) {
 case 'RUNNING': return 'success';
 case 'STOPPED': return 'danger';
 default: return 'info';
 }
}
async function loadPrograms() {
 try {
 const params = {
 page: page.value,
 size: size.value,
 func_desc: filters.func_desc || undefined,
 module: filters.module || undefined,
 ip: filters.ip || undefined,
 owner: filters.owner || undefined
 };
 const result = await programApi.getPrograms(params);
 if (result.code === 0) {
 programList.value = result.data.items.map(item => ({
 ...item,
 status: 'UNKNOWN'
 }));
 total.value = result.data.total;
 // 加载后立即获取状态
 await updateStatuses();
 }
 }
 catch (error) {
 ElMessage.error('加载程序列表失败: ' + (error.response?.data?.message || error.message));
 }
}
async function updateStatuses() {
 if (programList.value.length === 0)
 return;
 const ids = programList.value.map(p => p.id);
 try {
 const result = await programApi.batchGetStatus(ids);
 if (result.code === 0) {
 programList.value.forEach(p => {
 p.status = result.data[p.id] || 'UNKNOWN';
 });
 }
 }
 catch (error) {
 console.error('更新状态失败:', error);
 }
}
function handleSizeChange(val) {
 size.value = val;
 loadPrograms();
}
function handleCurrentChange(val) {
 page.value = val;
 loadPrograms();
}
function openAddForm() {
 isEdit.value = false;
 editData.value = null;
 showForm.value = true;
}
function editProgram(row) {
 isEdit.value = true;
 editData.value = row;
 showForm.value = true;
}
function viewLog(row) {
 currentLogId.value = row.id;
 showLog.value = true;
}
async function startProgram(row) {
 try {
 const result = await programApi.startProgram(row.id);
 if (result.code === 0 && result.data.success) {
 ElMessage.success(result.data.message);
 }
 else {
 ElMessage.error(result.data?.message || '启动失败');
 }
 }
 catch (error) {
 ElMessage.error('启动失败: ' + (error.response?.data?.message || error.message));
 }
 // 延迟更新状态
 setTimeout(updateStatuses, 3000);
}
async function stopProgram(row) {
 try {
 const result = await programApi.stopProgram(row.id);
 if (result.code === 0 && result.data.success) {
 ElMessage.success(result.data.message);
 }
 else {
 ElMessage.error(result.data?.message || '停止失败');
 }
 }
 catch (error) {
 ElMessage.error('停止失败: ' + (error.response?.data?.message || error.message));
 }
 setTimeout(updateStatuses, 3000);
}
async function restartProgram(row) {
 try {
 const result = await programApi.restartProgram(row.id);
 if (result.code === 0 && result.data.success) {
 ElMessage.success(result.data.message);
 }
 else {
 ElMessage.error(result.data?.message || '重启失败');
 }
 }
 catch (error) {
 ElMessage.error('重启失败: ' + (error.response?.data?.message || error.message));
 }
 setTimeout(updateStatuses, 3000);
}
async function deleteProgram(row) {
 if (!confirm(`确定删除程序 "${row.func_desc}" 吗？`))
 return;
 try {
 const result = await programApi.deleteProgram(row.id);
 if (result.code === 0) {
 ElMessage.success('删除成功');
 loadPrograms();
 }
 else {
 ElMessage.error(result.message || '删除失败');
 }
 }
 catch (error) {
 ElMessage.error('删除失败: ' + (error.response?.data?.message || error.message));
 }
}
function handleFormSuccess() {
 loadPrograms();
}
function handleExport() {
 programApi.exportPrograms();
}
function handleImport() {
 showImport.value = true;
}
function handleFileChange(file) {
 importFile.value = file.raw;
}
function downloadImportTemplate() {
 // 导出空模板
 programApi.exportPrograms();
}
async function doImport() {
 if (!importFile.value) {
 ElMessage.error('请选择文件');
 return;
 }
 try {
 const result = await programApi.importPrograms(importFile.value);
 if (result.code === 0) {
 const data = result.data;
 ElMessage.success(data.message);
 showImport.value = false;
 importFile.value = null;
 loadPrograms();
 }
 else {
 ElMessage.error(result.message);
 }
 }
 catch (error) {
 ElMessage.error('导入失败: ' + (error.response?.data?.message || error.message));
 }
}
onMounted(() => {
 loadPrograms();
 // 每10秒刷新状态
 statusTimer = setInterval(updateStatuses, 10000);
});
onUnmounted(() => {
 if (statusTimer) {
 clearInterval(statusTimer);
 }
});
</script>

<style scoped>
.program-list-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 15px;
}

.header-left h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
}

.subtitle {
  margin: 0;
  color: #718096;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.filter-input {
  width: 150px;
}

.program-table {
  border-radius: 12px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #94a3b8;
}

.empty-icon {
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state p {
  margin: 0 0 16px 0;
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.import-tip {
  margin: 10px 0;
  color: #94a3b8;
  font-size: 12px;
}
</style>