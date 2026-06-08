<template>
  <div class="subsystem-page">
    <div class="page-header">
      <h1>子系统管理</h1>
      <div class="actions">
        <el-button type="primary" @click="showAddDialog = true">新增子系统</el-button>
      </div>
    </div>

    <div class="search-bar">
      <el-select v-model="filters.project_id" placeholder="选择项目" clearable class="project-select">
        <el-option label="全部项目" value="" />
        <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索子系统名称或编码" class="search-input" @keyup.enter="loadSubsystems" />
      <el-button type="primary" @click="loadSubsystems">搜索</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <div class="table-wrapper">
      <el-table :data="subsystems" border>
        <el-table-column type="index" label="序号" width="80" />
        <el-table-column prop="subsystem_name" label="子系统名称" min-width="150" />
        <el-table-column prop="subsystem_code" label="子系统编码" min-width="120" />
        <el-table-column prop="project_name" label="所属项目" min-width="120" />
        <el-table-column prop="display_order" label="显示顺序" width="100" />
        <el-table-column prop="description" label="描述" min-width="180" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" align="center">
          <template #default="scope">
            <div class="action-buttons">
              <div class="action-btn edit-btn" @click="editSubsystem(scope.row)">
                <span>编辑</span>
              </div>
              <div class="action-btn delete-btn" @click="deleteSubsystem(scope.row)">
                <span>删除</span>
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

    <el-dialog title="新增/编辑子系统" v-model="showAddDialog" width="600px" @close="resetForm">
      <el-form :model="subsystemForm" label-width="120px">
        <el-form-item label="所属项目" required>
          <el-select v-model="subsystemForm.project_id" placeholder="请选择项目">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="子系统名称" required>
          <el-input v-model="subsystemForm.subsystem_name" placeholder="请输入子系统名称" />
        </el-form-item>
        <el-form-item label="子系统编码" required>
          <el-input v-model="subsystemForm.subsystem_code" placeholder="请输入子系统编码" />
        </el-form-item>
        <el-form-item label="显示顺序">
          <el-input v-model.number="subsystemForm.display_order" placeholder="默认0" />
        </el-form-item>
        <el-form-item label="关联分类">
          <el-select v-model="subsystemForm.group_ids" multiple placeholder="请选择关联的程序分类" style="width: 100%">
            <el-option v-for="group in serviceGroups" :key="group.id" :label="group.group_name" :value="group.id" />
          </el-select>
          <div class="form-tip">不选择则该子系统不显示任何程序分类</div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="subsystemForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveSubsystem">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import axios from '@/utils/axios';

const subsystems = ref([]);
const projects = ref([]);
const serviceGroups = ref([]);
const pagination = reactive({
  page: 1,
  size: 10,
  total: 0
});
const filters = reactive({
  project_id: '',
  keyword: ''
});
const showAddDialog = ref(false);
const subsystemForm = reactive({
  id: null,
  project_id: '',
  subsystem_name: '',
  subsystem_code: '',
  display_order: 0,
  description: '',
  group_ids: []
});

const loadSubsystems = async () => {
  try {
    const params = new URLSearchParams();
    params.append('page', pagination.page);
    params.append('size', pagination.size);
    if (filters.project_id) {
      params.append('project_id', filters.project_id);
    }
    if (filters.keyword) {
      params.append('keyword', filters.keyword);
    }
    const response = await axios.get(`/api/subsystems?${params}`);
    if (response.data.code === 0) {
      subsystems.value = response.data.data.items;
      pagination.total = response.data.data.total;
    }
  } catch (error) {
    ElMessage.error('加载子系统列表失败');
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

const loadServiceGroups = async () => {
  try {
    const response = await axios.get('/api/service-groups/all');
    if (response.data.code === 0) {
      serviceGroups.value = response.data.data;
    }
  } catch (error) {
    console.error('加载程序分类列表失败', error);
  }
};

const loadSubsystemGroups = async (subsystemId) => {
  try {
    const response = await axios.get(`/api/subsystems/${subsystemId}/groups`);
    if (response.data.code === 0) {
      subsystemForm.group_ids = response.data.data.map(g => g.id);
    }
  } catch (error) {
    console.error('加载子系统关联分类失败', error);
  }
};

const resetForm = () => {
  subsystemForm.id = null;
  subsystemForm.project_id = '';
  subsystemForm.subsystem_name = '';
  subsystemForm.subsystem_code = '';
  subsystemForm.display_order = 0;
  subsystemForm.description = '';
  subsystemForm.group_ids = [];
};

const resetFilters = () => {
  filters.project_id = '';
  filters.keyword = '';
  loadSubsystems();
};

const editSubsystem = async (subsystem) => {
  subsystemForm.id = subsystem.id;
  subsystemForm.project_id = subsystem.project_id;
  subsystemForm.subsystem_name = subsystem.subsystem_name;
  subsystemForm.subsystem_code = subsystem.subsystem_code;
  subsystemForm.display_order = subsystem.display_order;
  subsystemForm.description = subsystem.description || '';
  await loadSubsystemGroups(subsystem.id);
  showAddDialog.value = true;
};

const saveSubsystem = async () => {
  if (!subsystemForm.project_id) {
    ElMessage.error('请选择所属项目');
    return;
  }
  if (!subsystemForm.subsystem_name.trim()) {
    ElMessage.error('请输入子系统名称');
    return;
  }
  if (!subsystemForm.subsystem_code.trim()) {
    ElMessage.error('请输入子系统编码');
    return;
  }
  try {
    const data = {
      project_id: subsystemForm.project_id,
      subsystem_name: subsystemForm.subsystem_name,
      subsystem_code: subsystemForm.subsystem_code,
      display_order: subsystemForm.display_order,
      description: subsystemForm.description || null
    };
    let response;
    if (subsystemForm.id) {
      response = await axios.put(`/api/subsystems/${subsystemForm.id}`, data);
    } else {
      response = await axios.post('/api/subsystems', data);
    }
    if (response.data.code === 0) {
      // 保存成功后，更新子系统与分类的关联关系
      const subsystemId = subsystemForm.id || response.data.data?.id;
      if (subsystemId) {
        await axios.post(`/api/subsystems/${subsystemId}/groups`, subsystemForm.group_ids);
      }
      ElMessage.success(subsystemForm.id ? '更新成功' : '新增成功');
      showAddDialog.value = false;
      resetForm();
      loadSubsystems();
    } else {
      ElMessage.error(response.data.message || '操作失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '操作失败');
  }
};

const deleteSubsystem = async (subsystem) => {
  if (!confirm(`确定要删除子系统 "${subsystem.subsystem_name}" 吗？`))
    return;
  try {
    const response = await axios.delete(`/api/subsystems/${subsystem.id}`);
    if (response.data.code === 0) {
      ElMessage.success('删除成功');
      loadSubsystems();
    } else {
      ElMessage.error(response.data.message || '删除失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '删除失败');
  }
};

const handlePageChange = (page) => {
  pagination.page = page;
  loadSubsystems();
};

const handleSizeChange = (size) => {
  pagination.size = size;
  pagination.page = 1;
  loadSubsystems();
};

onMounted(() => {
  loadSubsystems();
  loadProjects();
  loadServiceGroups();
});
</script>

<style scoped>
.subsystem-page {
  padding: 20px;
}

.table-wrapper {
  overflow-x: auto;
  max-width: 100%;
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

.project-select {
  width: 200px;
}

.search-input {
  width: 300px;
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
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

.edit-btn {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
}

.delete-btn {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}
</style>