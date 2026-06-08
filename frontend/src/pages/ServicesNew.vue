<template>
  <div class="services-page-new">
    <div class="page-layout">
      <div class="left-panel">
        <ProjectTree @node-click="handleTreeClick" />
      </div>
      <div class="right-panel">
        <div class="page-header">
          <h1>服务管理</h1>
          <div class="actions">
            <el-button type="danger" @click="confirmBatchDelete" :disabled="selectedServices.length === 0">
              批量删除 ({{ selectedServices.length }})
            </el-button>
            <el-button type="primary" @click="showAddDialog = true">新增服务</el-button>
            <el-button @click="downloadTemplate">下载模板</el-button>
            <el-button type="primary" @click="goToImport">导入服务</el-button>
            <el-button @click="exportServices">导出服务</el-button>
          </div>
        </div>

        <div class="search-bar">
          <el-select v-model="filters.project_id" placeholder="选择项目" clearable class="project-select" @change="handleProjectChange">
            <el-option label="全部项目" value="" />
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
          <el-select v-model="filters.subsystem_id" placeholder="选择子系统" clearable class="subsystem-select" @change="handleSubsystemChange">
            <el-option label="全部子系统" value="" />
            <el-option v-for="subsystem in subsystems" :key="subsystem.id" :label="subsystem.subsystem_name" :value="subsystem.id" />
          </el-select>
          <el-select v-model="filters.group_id" placeholder="选择程序分类" clearable class="group-select">
            <el-option label="全部分类" value="" />
            <el-option v-for="group in groups" :key="group.id" :label="group.group_name" :value="group.id" />
          </el-select>
          <el-input v-model="filters.keyword" placeholder="搜索功能描述或模块" class="search-input" @keyup.enter="loadServices" />
          <el-input v-model="filters.ip" placeholder="搜索IP地址" class="ip-input" @keyup.enter="loadServices" />
          <el-button type="primary" @click="loadServices">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>

        <div class="table-wrapper">
          <el-table 
            ref="serviceTable"
            :data="services" 
            border 
            @selection-change="handleSelectionChange"
            @select="handleSelect"
          >
            <el-table-column type="selection" width="60" />
            <el-table-column type="index" label="序号" width="80" />
            <el-table-column prop="func_desc" label="功能描述" min-width="150" />
            <el-table-column prop="module" label="对应模块" min-width="120" />
            <el-table-column prop="subsystem_name" label="子系统" min-width="120" />
            <el-table-column prop="group_name" label="程序分类" min-width="120" />
            <el-table-column prop="ip" label="IP地址" min-width="120" />
            <el-table-column prop="username" label="用户名" min-width="100" />
            <el-table-column prop="program_path" label="程序路径" min-width="180" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="scope">
                <el-tag :type="getStatusType(scope.row.status)">
                  {{ scope.row.status || '未知' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" align="center">
              <template #default="scope">
                <div class="action-buttons">
                  <div class="action-btn view-btn" @click="viewService(scope.row)">
                    <span>查看</span>
                  </div>
                  <div class="action-btn edit-btn" @click="editService(scope.row)">
                    <span>编辑</span>
                  </div>
                  <div class="action-btn delete-btn" @click="deleteService(scope.row)">
                    <span>删除</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="日志" width="80" align="center">
              <template #default="scope">
                <div class="action-buttons">
                  <div class="action-btn log-btn" @click="viewLog(scope.row)">
                    <span>日志</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="启停控制" width="160" align="center">
              <template #default="scope">
                <div class="action-buttons">
                  <template v-if="scope.row.status !== 'RUNNING'">
                    <div class="action-btn start-btn" @click="startService(scope.row)">
                      <span>启动</span>
                    </div>
                  </template>
                  <template v-else>
                    <div class="action-btn stop-btn" @click="stopService(scope.row)">
                      <span>停止</span>
                    </div>
                    <div class="action-btn restart-btn" @click="restartService(scope.row)">
                      <span>重启</span>
                    </div>
                  </template>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="远程登录" width="100" align="center">
              <template #default="scope">
                <div class="action-buttons">
                  <div class="action-btn login-btn" @click="webShell(scope.row)">
                    <span>登录</span>
                  </div>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <el-pagination
          :current-page="pagination.page"
          :page-size="pagination.size"
          :total="pagination.total"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <el-dialog title="新增/编辑服务" v-model="showAddDialog" width="700px" @close="resetForm">
      <el-form :model="serviceForm" label-width="120px">
        <el-form-item label="所属项目" required>
          <el-select v-model="serviceForm.project_id" placeholder="请选择项目" @change="handleFormProjectChange">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属子系统" required>
          <el-select v-model="serviceForm.subsystem_id" placeholder="请选择子系统" @change="handleFormSubsystemChange">
            <el-option v-for="subsystem in formSubsystems" :key="subsystem.id" :label="subsystem.subsystem_name" :value="subsystem.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="程序分类" required>
          <el-select v-model="serviceForm.group_id" placeholder="请选择程序分类">
            <el-option v-for="group in formGroups" :key="group.id" :label="group.group_name" :value="group.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="功能描述" required>
          <el-input v-model="serviceForm.func_desc" placeholder="请输入功能描述" />
        </el-form-item>
        <el-form-item label="对应模块">
          <el-input v-model="serviceForm.module" placeholder="请输入模块名称" />
        </el-form-item>
        <el-form-item label="IP地址" required>
          <el-input v-model="serviceForm.ip" placeholder="请输入服务器IP地址" />
        </el-form-item>
        <el-form-item label="SSH端口">
          <el-input v-model.number="serviceForm.ssh_port" placeholder="默认22" />
        </el-form-item>
        <el-form-item label="SSH用户名" required>
          <el-input v-model="serviceForm.username" placeholder="请输入SSH用户名" />
        </el-form-item>
        <el-form-item label="密码" :required="!serviceForm.id">
          <el-input v-model="serviceForm.password" type="password" placeholder="编辑时留空表示不修改密码" />
        </el-form-item>
        <el-form-item label="程序路径" required>
          <el-input v-model="serviceForm.program_path" placeholder="请输入程序路径" />
        </el-form-item>
        <el-form-item label="启动脚本">
          <el-input v-model="serviceForm.start_script" placeholder="如: ./start.sh" />
        </el-form-item>
        <el-form-item label="停止脚本">
          <el-input v-model="serviceForm.stop_script" placeholder="如: ./stop.sh" />
        </el-form-item>
        <el-form-item label="日志路径">
          <el-input v-model="serviceForm.log_path" placeholder="日志文件路径或目录" />
        </el-form-item>
        <el-form-item label="程序端口">
          <el-input v-model.number="serviceForm.port" placeholder="请输入端口号" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="serviceForm.owner" placeholder="请输入负责人" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="serviceForm.remark" type="textarea" :rows="3" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveService">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog title="服务详情" v-model="showDetailDialog">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="功能描述">{{ selectedService.func_desc || '-' }}</el-descriptions-item>
        <el-descriptions-item label="对应模块">{{ selectedService.module || '-' }}</el-descriptions-item>
        <el-descriptions-item label="所属项目">{{ selectedService.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="所属子系统">{{ selectedService.subsystem_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="程序分类">{{ selectedService.group_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ selectedService.ip || '-' }}</el-descriptions-item>
        <el-descriptions-item label="SSH端口">{{ selectedService.ssh_port || '-' }}</el-descriptions-item>
        <el-descriptions-item label="SSH用户名">{{ selectedService.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="程序端口">{{ selectedService.port || '-' }}</el-descriptions-item>
        <el-descriptions-item label="负责人">{{ selectedService.owner || '-' }}</el-descriptions-item>
        <el-descriptions-item label="程序路径">{{ selectedService.program_path || '-' }}</el-descriptions-item>
        <el-descriptions-item label="启动脚本">{{ selectedService.start_script || '-' }}</el-descriptions-item>
        <el-descriptions-item label="停止脚本">{{ selectedService.stop_script || '-' }}</el-descriptions-item>
        <el-descriptions-item label="日志路径">{{ selectedService.log_path || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(selectedService.status)">
            {{ selectedService.status || '未知' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="备注">{{ selectedService.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog title="日志查看" v-model="showLogDialog" width="900px" :before-close="handleLogClose">
      <div class="log-header">
        <el-select v-model="selectedLogFile" style="width: 250px" placeholder="选择日志文件" @change="loadLog">
          <el-option label="最新日志" value="" />
          <el-option v-for="file in logFiles" :key="file.name" :label="`${file.name} (${file.size})`" :value="file.name" />
        </el-select>
        <el-select v-model="logLines" style="width: 120px">
          <el-option label="100行" :value="100" />
          <el-option label="200行" :value="200" />
          <el-option label="500行" :value="500" />
          <el-option label="1000行" :value="1000" />
        </el-select>
        <el-button @click="loadLogFileList">刷新列表</el-button>
        <el-button @click="refreshLog">刷新内容</el-button>
        <el-button @click="downloadLog">下载日志</el-button>
      </div>
      <div class="log-content" ref="logContent">
        <pre>{{ logContentText }}</pre>
      </div>
    </el-dialog>

    <el-dialog title="远程终端" v-model="showShellDialog" width="900px" height="600px" :before-close="handleShellClose">
      <div class="shell-header">
        <el-tag type="primary" v-if="currentShellService">{{ currentShellService.func_desc }}</el-tag>
        <el-tag v-if="shellConnected" class="connected-tag">已连接</el-tag>
        <el-tag v-else class="disconnected-tag">未连接</el-tag>
        <el-button @click="connectShell" v-if="!shellConnected" type="primary">连接</el-button>
        <el-button @click="disconnectShell" v-else type="danger">断开</el-button>
      </div>
      <div class="shell-container" ref="shellContainer">
        <div class="shell-output" ref="shellOutput" v-html="shellOutputText"></div>
        <div class="shell-input-wrapper">
          <span class="shell-prompt">{{ shellPrompt }}</span>
          <input 
            ref="shellInput"
            v-model="shellInputText" 
            class="shell-input" 
            @keydown.enter="sendShellCommand"
            placeholder="输入命令..."
            :disabled="!shellConnected"
          />
        </div>
      </div>
    </el-dialog>

    <el-dialog title="导入服务" v-model="showImportDialog">
      <el-upload
        class="upload-demo"
        :auto-upload="false"
        :on-change="handleFileChange"
        accept=".xlsx"
      >
        <el-button type="primary">选择文件</el-button>
      </el-upload>
      <p class="import-tip">支持.xlsx格式文件，可先下载模板</p>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="doImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue';
import { ElMessage } from 'element-plus';
import axios from '@/utils/axios';
import ProjectTree from '@/components/ProjectTree.vue';

const services = ref([]);
const selectedServices = ref([]);
const serviceTable = ref(null);
const lastSelectedIndex = ref(-1);
const shiftPressed = ref(false);
const projects = ref([]);
const subsystems = ref([]);
const groups = ref([]);
const formSubsystems = ref([]);
const formGroups = ref([]);
const pagination = reactive({
  page: 1,
  size: 10,
  total: 0
});
const filters = reactive({
  project_id: '',
  subsystem_id: '',
  group_id: '',
  keyword: '',
  ip: ''
});
const showAddDialog = ref(false);
const showDetailDialog = ref(false);
const showLogDialog = ref(false);
const showImportDialog = ref(false);
const showShellDialog = ref(false);
const importFile = ref(null);
const selectedService = reactive({});
const selectedLogService = ref(null);
const currentShellService = ref(null);
const shellConnected = ref(false);
const shellOutputText = ref('');
const shellInputText = ref('');
const shellPrompt = ref('$');
const logLines = ref(200);
const logContentText = ref('');
const logFiles = ref([]);
const selectedLogFile = ref('');
const serviceForm = reactive({
  id: null,
  project_id: '',
  subsystem_id: '',
  group_id: '',
  func_desc: '',
  module: '',
  ip: '',
  ssh_port: 22,
  username: '',
  password: '',
  program_path: '',
  start_script: '',
  stop_script: '',
  log_path: '',
  port: null,
  owner: '',
  remark: ''
});
let statusInterval = null;

const getStatusType = (status) => {
  switch (status) {
    case 'RUNNING':
      return 'success';
    case 'STOPPED':
      return 'danger';
    default:
      return 'warning';
  }
};

const loadServices = async () => {
  try {
    const params = new URLSearchParams();
    params.append('page', pagination.page);
    params.append('size', pagination.size);
    if (filters.project_id) {
      params.append('project_id', filters.project_id);
    }
    if (filters.subsystem_id) {
      params.append('subsystem_id', filters.subsystem_id);
    }
    if (filters.group_id) {
      params.append('group_id', filters.group_id);
    }
    if (filters.keyword) {
      params.append('func_desc', filters.keyword);
    }
    if (filters.ip) {
      params.append('ip', filters.ip);
    }
    const response = await axios.get(`/api/services?${params}`);
    if (response.data.code === 0) {
      services.value = response.data.data.items;
      pagination.total = response.data.data.total;
      // 非阻塞更新状态，避免超时影响服务列表加载
      updateStatuses();
    }
  } catch (error) {
    ElMessage.error('加载服务列表失败');
  }
};

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

const loadSubsystems = async (projectId = '') => {
  try {
    const params = new URLSearchParams();
    if (projectId) {
      params.append('project_id', projectId);
    }
    const response = await axios.get(`/api/subsystems?${params}`);
    if (response.data.code === 0) {
      return response.data.data.items;
    }
    return [];
  } catch (error) {
    console.error('加载子系统列表失败', error);
    return [];
  }
};

const loadGroups = async (subsystemId = '') => {
  try {
    // 如果指定了子系统，从子系统的关联中获取分类
    if (subsystemId) {
      const response = await axios.get(`/api/subsystems/${subsystemId}/groups`);
      if (response.data.code === 0) {
        return response.data.data;
      }
    }
    return [];
  } catch (error) {
    console.error('加载程序分类列表失败', error);
    return [];
  }
};

const handleTreeClick = async (data) => {
  filters.subsystem_id = '';
  filters.group_id = '';
  
  if (data.type === 'project') {
    // 点击项目，设置项目筛选并加载该项目下所有子系统和全局分类
    filters.project_id = data.id;
    subsystems.value = await loadSubsystems(data.id);
    groups.value = await loadGroups();
  } else if (data.type === 'subsystem') {
    // 点击子系统，设置项目和子系统筛选，加载该子系统的关联分类
    filters.project_id = data.project_id;
    subsystems.value = await loadSubsystems(data.project_id);
    filters.subsystem_id = data.id;
    groups.value = await loadGroups(data.id);
  } else if (data.type === 'service_group') {
    // 点击程序分类，设置项目、子系统和分类筛选
    filters.project_id = data.project_id;
    subsystems.value = await loadSubsystems(data.project_id);
    filters.subsystem_id = data.subsystem_id;
    filters.group_id = data.id;
    groups.value = await loadGroups(data.subsystem_id);
  }
  
  pagination.page = 1;
  loadServices();
};

const handleProjectChange = async () => {
  filters.subsystem_id = '';
  filters.group_id = '';
  if (filters.project_id) {
    subsystems.value = await loadSubsystems(filters.project_id);
    groups.value = [];
  } else {
    subsystems.value = [];
    groups.value = [];
  }
  pagination.page = 1;
  loadServices();
};

const handleSubsystemChange = async () => {
  filters.group_id = '';
  groups.value = await loadGroups(filters.subsystem_id);
  pagination.page = 1;
  loadServices();
};

const handleFormProjectChange = async () => {
  formSubsystems.value = await loadSubsystems(serviceForm.project_id);
  formGroups.value = [];
  serviceForm.subsystem_id = '';
  serviceForm.group_id = '';
};

const handleFormSubsystemChange = async () => {
  serviceForm.group_id = '';
  formGroups.value = await loadGroups(serviceForm.subsystem_id);
};

const updateStatuses = async () => {
  const serviceIds = services.value.map(s => s.id);
  if (serviceIds.length === 0)
    return;
  try {
    const response = await axios.post('/api/services/status/batch', serviceIds);
    if (response.data.code === 0) {
      const statusMap = response.data.data;
      services.value.forEach(service => {
        service.status = statusMap[service.id] || 'UNKNOWN';
      });
    }
  } catch (error) {
    console.error('更新状态失败', error);
  }
};

const resetForm = () => {
  serviceForm.id = null;
  serviceForm.project_id = '';
  serviceForm.subsystem_id = '';
  serviceForm.group_id = '';
  serviceForm.func_desc = '';
  serviceForm.module = '';
  serviceForm.ip = '';
  serviceForm.ssh_port = 22;
  serviceForm.username = '';
  serviceForm.password = '';
  serviceForm.program_path = '';
  serviceForm.start_script = '';
  serviceForm.stop_script = '';
  serviceForm.log_path = '';
  serviceForm.port = null;
  serviceForm.owner = '';
  serviceForm.remark = '';
  formSubsystems.value = [];
  formGroups.value = [];
};

const resetFilters = () => {
  filters.project_id = '';
  filters.subsystem_id = '';
  filters.group_id = '';
  filters.keyword = '';
  filters.ip = '';
  subsystems.value = [];
  groups.value = [];
  pagination.page = 1;
  loadServices();
};

const viewService = async (service) => {
  try {
    const response = await axios.get(`/api/services/${service.id}`);
    if (response.data.code === 0) {
      Object.assign(selectedService, response.data.data);
      showDetailDialog.value = true;
      const statusResponse = await axios.post('/api/services/status/batch', [service.id]);
      if (statusResponse.data.code === 0) {
        selectedService.status = statusResponse.data.data[service.id] || 'UNKNOWN';
      }
    } else {
      ElMessage.error('获取服务详情失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '获取服务详情失败');
  }
};

const editService = async (service) => {
  serviceForm.id = service.id;
  serviceForm.project_id = service.project_id;
  serviceForm.subsystem_id = service.subsystem_id;
  serviceForm.group_id = service.group_id;
  serviceForm.func_desc = service.func_desc;
  serviceForm.module = service.module || '';
  serviceForm.ip = service.ip;
  serviceForm.ssh_port = service.ssh_port || 22;
  serviceForm.username = service.username;
  serviceForm.password = '';
  serviceForm.program_path = service.program_path;
  serviceForm.start_script = service.start_script || '';
  serviceForm.stop_script = service.stop_script || '';
  serviceForm.log_path = service.log_path || '';
  serviceForm.port = service.port || null;
  serviceForm.owner = service.owner || '';
  serviceForm.remark = service.remark || '';
  
  formSubsystems.value = await loadSubsystems(service.project_id);
  if (service.subsystem_id) {
    formGroups.value = await loadGroups(service.subsystem_id);
  } else {
    formGroups.value = [];
  }
  showAddDialog.value = true;
};

const saveService = async () => {
  if (!serviceForm.project_id) {
    ElMessage.error('请选择所属项目');
    return;
  }
  if (!serviceForm.subsystem_id) {
    ElMessage.error('请选择所属子系统');
    return;
  }
  if (!serviceForm.group_id) {
    ElMessage.error('请选择程序分类');
    return;
  }
  if (!serviceForm.func_desc.trim()) {
    ElMessage.error('请输入功能描述');
    return;
  }
  if (!serviceForm.ip.trim()) {
    ElMessage.error('请输入IP地址');
    return;
  }
  if (!serviceForm.username.trim()) {
    ElMessage.error('请输入SSH用户名');
    return;
  }
  if (!serviceForm.program_path.trim()) {
    ElMessage.error('请输入程序路径');
    return;
  }
  if (!serviceForm.id && !serviceForm.password.trim()) {
    ElMessage.error('请输入密码');
    return;
  }
  try {
    const data = {
      project_id: serviceForm.project_id,
      subsystem_id: serviceForm.subsystem_id,
      group_id: serviceForm.group_id,
      func_desc: serviceForm.func_desc,
      module: serviceForm.module || null,
      ip: serviceForm.ip,
      ssh_port: serviceForm.ssh_port || 22,
      username: serviceForm.username,
      program_path: serviceForm.program_path,
      start_script: serviceForm.start_script || null,
      stop_script: serviceForm.stop_script || null,
      log_path: serviceForm.log_path || null,
      port: serviceForm.port || null,
      owner: serviceForm.owner || null,
      remark: serviceForm.remark || null
    };
    if (serviceForm.password.trim()) {
      data.password = serviceForm.password;
    }
    let response;
    if (serviceForm.id) {
      response = await axios.put(`/api/services/${serviceForm.id}`, data);
    } else {
      response = await axios.post('/api/services', data);
    }
    if (response.data.code === 0) {
      ElMessage.success(serviceForm.id ? '更新成功' : '新增成功');
      showAddDialog.value = false;
      resetForm();
      loadServices();
    } else {
      ElMessage.error(response.data.message || '操作失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '操作失败');
  }
};

const deleteService = async (service) => {
  if (!confirm(`确定要删除服务 "${service.func_desc}" 吗？`))
    return;
  try {
    const response = await axios.delete(`/api/services/${service.id}`);
    if (response.data.code === 0) {
      ElMessage.success('删除成功');
      loadServices();
    } else {
      ElMessage.error(response.data.message || '删除失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '删除失败');
  }
};

const handleSelectionChange = (val) => {
  selectedServices.value = val;
};

const handleSelect = (selection, row) => {
  const currentIndex = services.value.findIndex(s => s.id === row.id);
  if (currentIndex === -1) return;
  
  // 检查当前行是否被选中（selection是选择后的数据）
  const isSelected = selection.some(s => s.id === row.id);
  
  if (!shiftPressed.value) {
    // 非Shift选择，记录当前索引
    if (isSelected) {
      lastSelectedIndex.value = currentIndex;
    } else {
      // 如果取消选中且是唯一选中项，重置索引
      if (selection.length === 0) {
        lastSelectedIndex.value = -1;
      }
    }
    return;
  }
  
  // Shift键按下时进行批量选择
  if (lastSelectedIndex.value === -1) {
    // 如果之前没有选中项，先记录当前索引
    lastSelectedIndex.value = currentIndex;
    return;
  }
  
  const table = serviceTable.value;
  if (!table) return;
  
  // 等待DOM更新后再操作
  nextTick(() => {
    // 清除当前选择（除了当前点击的行）
    table.clearSelection();
    
    // 计算选择范围
    const startIndex = Math.min(lastSelectedIndex.value, currentIndex);
    const endIndex = Math.max(lastSelectedIndex.value, currentIndex);
    
    // 选择范围内的所有行
    for (let i = startIndex; i <= endIndex; i++) {
      table.toggleRowSelection(services.value[i], true);
    }
    
    // 更新最后选中的索引
    lastSelectedIndex.value = currentIndex;
  });
};

const handleKeyDown = (event) => {
  if (event.key === 'Shift') {
    shiftPressed.value = true;
    event.preventDefault();
  }
};

const handleKeyUp = (event) => {
  if (event.key === 'Shift') {
    shiftPressed.value = false;
  }
};

const confirmBatchDelete = async () => {
  if (selectedServices.value.length === 0) {
    ElMessage.warning('请先选择要删除的服务');
    return;
  }
  const count = selectedServices.value.length;
  const names = selectedServices.value.map(s => s.func_desc).join('、');
  if (!confirm(`确定要删除选中的 ${count} 个服务吗？\n\n服务名称：\n${names}`)) {
    return;
  }
  await batchDeleteServices();
};

const batchDeleteServices = async () => {
  const ids = selectedServices.value.map(s => s.id);
  try {
    const response = await axios.post('/api/services/batch/delete', ids);
    if (response.data.code === 0) {
      ElMessage.success(`成功删除 ${response.data.data.deleted} 个服务`);
      selectedServices.value = [];
      loadServices();
    } else {
      ElMessage.error(response.data.message || '批量删除失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '批量删除失败');
  }
};

const startService = async (service) => {
  try {
    const response = await axios.post(`/api/services/${service.id}/start`);
    if (response.data.code === 0) {
      ElMessage.success(response.data.data.message);
      service.status = 'RUNNING';
    } else {
      ElMessage.error(response.data.data.message || '启动失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '启动失败');
  }
};

const stopService = async (service) => {
  try {
    const response = await axios.post(`/api/services/${service.id}/stop`);
    if (response.data.code === 0) {
      ElMessage.success(response.data.data.message);
      service.status = 'STOPPED';
    } else {
      ElMessage.error(response.data.data.message || '停止失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '停止失败');
  }
};

const restartService = async (service) => {
  try {
    const response = await axios.post(`/api/services/${service.id}/restart`);
    if (response.data.code === 0) {
      ElMessage.success(response.data.data.message);
      service.status = 'RUNNING';
    } else {
      ElMessage.error(response.data.data.message || '重启失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '重启失败');
  }
};

const viewLog = async (service) => {
  selectedLogService.value = service;
  showLogDialog.value = true;
  selectedLogFile.value = '';
  await loadLogFileList();
  await loadLog();
};

const loadLogFileList = async () => {
  if (!selectedLogService.value)
    return;
  try {
    const response = await axios.get(`/api/services/${selectedLogService.value.id}/log/files`);
    if (response.data.code === 0) {
      logFiles.value = response.data.data.files || [];
    } else {
      logFiles.value = [];
    }
  } catch (error) {
    logFiles.value = [];
  }
};

const loadLog = async () => {
  if (!selectedLogService.value)
    return;
  try {
    const params = { lines: logLines.value };
    if (selectedLogFile.value) {
      params.filename = selectedLogFile.value;
    }
    const response = await axios.get(`/api/services/${selectedLogService.value.id}/log`, {
      params
    });
    if (response.data.code === 0) {
      logContentText.value = response.data.data.content;
    } else {
      logContentText.value = response.data.message || '获取日志失败';
    }
  } catch (error) {
    logContentText.value = error.response?.data?.message || '获取日志失败';
  }
};

const refreshLog = async () => {
  await loadLog();
};

const downloadLog = async () => {
  if (!selectedLogService.value)
    return;
  try {
    const params = {};
    if (selectedLogFile.value) {
      params.filename = selectedLogFile.value;
    }
    const response = await axios.get(`/api/services/${selectedLogService.value.id}/log/download`, {
      responseType: 'blob',
      params
    });
    const blob = new Blob([response.data], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const filename = selectedLogFile.value || `${selectedLogService.value.func_desc}.log`;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (error) {
    ElMessage.error('下载日志失败');
  }
};

const handleLogClose = () => {
  showLogDialog.value = false;
  logContentText.value = '';
};

const handlePageChange = (page) => {
  pagination.page = page;
  loadServices();
};

const handleSizeChange = (size) => {
  pagination.size = size;
  pagination.page = 1;
  loadServices();
};

const goToImport = () => {
  window.location.href = '/import-services';
};

const downloadTemplate = async () => {
  try {
    const response = await axios.get('/api/services/import/template', { responseType: 'blob' });
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

const exportServices = async () => {
  try {
    const params = new URLSearchParams();
    if (filters.subsystem_id)
      params.append('subsystem_id', filters.subsystem_id);
    if (filters.group_id)
      params.append('group_id', filters.group_id);
    const response = await axios.get(`/api/services/export?${params}`, { responseType: 'blob' });
    const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'services.xlsx';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (error) {
    ElMessage.error('导出失败');
  }
};

const handleFileChange = (file) => {
  importFile.value = file.raw;
};

const doImport = async () => {
  if (!importFile.value) {
    ElMessage.error('请选择要导入的文件');
    return;
  }
  const formData = new FormData();
  formData.append('file', importFile.value);
  // 如果当前有选中的子系统，传递子系统ID
  if (filters.subsystem_id) {
    formData.append('subsystem_id', filters.subsystem_id);
  }
  // 如果当前有选中的程序分类，传递分类ID
  if (filters.group_id) {
    formData.append('group_id', filters.group_id);
  }
  try {
    const response = await axios.post('/api/services/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    if (response.data.code === 0) {
      ElMessage.success(response.data.data.message);
      // 如果有失败的记录，显示详细信息
      if (response.data.data.failed > 0 && response.data.data.failed_items && response.data.data.failed_items.length > 0) {
        const failedDetails = response.data.data.failed_items.map(item => {
          return `${item.sheet || '未知sheet'} - 第${item.row}行: ${item.reason}`;
        }).join('\n');
        ElMessageBox.alert(`导入失败详情:\n\n${failedDetails}`, '导入失败详情', {
          confirmButtonText: '确定',
          type: 'warning'
        });
      }
      showImportDialog.value = false;
      loadServices();
    } else {
      ElMessage.error(response.data.message || '导入失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '导入失败');
  }
};

let websocket = null;
const webShell = (service) => {
  console.log('Opening shell for service:', service);
  currentShellService.value = service;
  shellOutputText.value = '';
  shellInputText.value = '';
  shellConnected.value = false;
  showShellDialog.value = true;
  
  // 自动连接
  setTimeout(() => {
    connectShell();
  }, 100);
};

const connectShell = () => {
  if (!currentShellService.value) return;
  
  const token = localStorage.getItem('token');
  console.log('Connecting to WebSocket, token:', !!token);
  if (!token) {
    shellOutputText.value += '[错误] 未找到认证token，请重新登录\n';
    return;
  }
  
  shellOutputText.value += '[正在连接服务器...]\n';
  
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${window.location.host}/api/shell/ws/${currentShellService.value.id}?token=${token}`;
  console.log('WebSocket URL:', wsUrl);
  websocket = new WebSocket(wsUrl);
  
  websocket.onopen = () => {
    console.log('WebSocket connected');
    shellConnected.value = true;
    shellOutputText.value += '[已连接到服务器]\n';
    shellPrompt.value = '$ ';
  };
  
  websocket.onmessage = (event) => {
    console.log('WebSocket received:', event.data);
    let output = event.data;
    output = output.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    output = output.replace(/\n/g, '<br>').replace(/\r/g, '');
    output = output.replace(/ /g, '&nbsp;');
    shellOutputText.value += output;
    setTimeout(() => {
      const shellOutput = document.querySelector('.shell-output');
      if (shellOutput) {
        shellOutput.scrollTop = shellOutput.scrollHeight;
      }
    }, 10);
  };
  
  websocket.onerror = (error) => {
    console.error('WebSocket error:', error);
    shellOutputText.value += `[错误] 连接失败\n`;
    shellConnected.value = false;
  };
  
  websocket.onclose = (event) => {
    console.log('WebSocket closed:', event.code, event.reason);
    shellOutputText.value += `[断开] 连接已关闭 (Code: ${event.code})\n`;
    shellConnected.value = false;
    websocket = null;
  };
};

const disconnectShell = () => {
  if (websocket) {
    websocket.close();
  }
};

const sendShellCommand = () => {
  if (!websocket || !shellConnected.value || !shellInputText.value.trim()) return;
  
  const command = shellInputText.value;
  shellOutputText.value += `<span class="command">${shellInputText.value}</span><br>`;
  websocket.send(command + '\n');
  shellInputText.value = '';
};

const handleShellClose = () => {
  disconnectShell();
  showShellDialog.value = false;
};

onMounted(() => {
  loadServices();
  loadProjects();
  statusInterval = setInterval(updateStatuses, 10000);
  window.addEventListener('keydown', handleKeyDown);
  window.addEventListener('keyup', handleKeyUp);
});

onUnmounted(() => {
  if (statusInterval) {
    clearInterval(statusInterval);
  }
  window.removeEventListener('keydown', handleKeyDown);
  window.removeEventListener('keyup', handleKeyUp);
});
</script>

<style scoped>
.services-page-new {
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
}

.page-layout {
  display: flex;
  height: 100%;
  gap: 20px;
  padding: 20px;
}

.left-panel {
  width: 280px;
  flex-shrink: 0;
}

.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.actions {
  display: flex;
  gap: 10px;
}

.search-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  align-items: center;
}

.project-select, .subsystem-select, .group-select {
  width: 180px;
}

.search-input {
  width: 250px;
}

.ip-input {
  width: 150px;
}

.table-wrapper {
  flex: 1;
  overflow-y: auto;
}

.el-table {
  height: calc(100% - 20px);
}

.import-tip {
  color: #999;
  margin-top: 10px;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.log-content {
  max-height: 500px;
  overflow-y: auto;
  background: #1a1a1a;
  padding: 15px;
  border-radius: 4px;
}

.log-content pre {
  color: #e4e4e4;
  font-family: monospace;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
}

.el-descriptions__label {
  font-weight: bold;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 4px;
}

.action-btn {
  width: 56px;
  height: 28px;
  border-radius: 4px;
  font-weight: 500;
  font-size: 13px;
  transition: all 0.25s ease;
  border: none;
  color: #fff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
  padding: 0;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  outline: none;
  text-align: center;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    filter: brightness(1.1);
  }

  &:active {
    transform: translateY(0);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
  }
}

.view-btn {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
}

.edit-btn {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
}

.delete-btn {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.log-btn {
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
}

.start-btn {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
}

.stop-btn {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.restart-btn {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}

.login-btn {
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
}

.shell-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
  flex-wrap: wrap;
}

.shell-container {
  background: #1f2937;
  border-radius: 8px;
  padding: 15px;
  height: calc(100vh - 320px);
  display: flex;
  flex-direction: column;
}

.shell-output {
  flex: 1;
  overflow-y: auto;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 14px;
  color: #e5e7eb;
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.5;
}

.shell-output .command {
  color: #a78bfa;
}

.shell-input-wrapper {
  display: flex;
  align-items: center;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #374151;
}

.shell-prompt {
  color: #10b981;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 14px;
  margin-right: 5px;
}

.shell-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #e5e7eb;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 14px;
}

.shell-input::placeholder {
  color: #6b7280;
}

.shell-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.connected-tag {
  background: #d1fae5;
  color: #065f46;
  border: none;
}

.disconnected-tag {
  background: #fee2e2;
  color: #991b1b;
  border: none;
}
</style>