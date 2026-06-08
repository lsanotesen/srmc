<template>
  <div class="service-group-page">
    <div class="page-header">
      <h1>程序分类管理</h1>
      <div class="actions">
        <el-button type="primary" @click="showAddDialog = true">新增分类</el-button>
      </div>
    </div>

    <div class="search-bar">
      <el-input v-model="filters.keyword" placeholder="搜索分类名称或编码" class="search-input" @keyup.enter="loadServiceGroups" />
      <el-button type="primary" @click="loadServiceGroups">搜索</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <div class="table-wrapper">
      <el-table :data="serviceGroups" border>
        <el-table-column type="index" label="序号" width="80" />
        <el-table-column prop="group_name" label="分类名称" min-width="150" />
        <el-table-column prop="group_code" label="分类编码" min-width="120" />
        <el-table-column prop="display_order" label="显示顺序" width="100" />
        <el-table-column prop="description" label="描述" min-width="180" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" align="center">
          <template #default="scope">
            <div class="action-buttons">
              <div class="action-btn edit-btn" @click="editServiceGroup(scope.row)">
                <span>编辑</span>
              </div>
              <div class="action-btn delete-btn" @click="deleteServiceGroup(scope.row)">
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

    <el-dialog title="新增/编辑程序分类" v-model="showAddDialog" width="500px" @close="resetForm">
      <el-form :model="groupForm" label-width="120px">
        <el-form-item label="分类名称" required>
          <el-input v-model="groupForm.group_name" placeholder="请输入分类名称" />
        </el-form-item>
        <el-form-item label="分类编码" required>
          <el-input v-model="groupForm.group_code" placeholder="请输入分类编码" />
        </el-form-item>
        <el-form-item label="显示顺序">
          <el-input v-model.number="groupForm.display_order" placeholder="默认0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="groupForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveServiceGroup">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import axios from '@/utils/axios';

const serviceGroups = ref([]);
const pagination = reactive({
  page: 1,
  size: 10,
  total: 0
});
const filters = reactive({
  keyword: ''
});
const showAddDialog = ref(false);
const groupForm = reactive({
  id: null,
  group_name: '',
  group_code: '',
  display_order: 0,
  description: ''
});

const loadServiceGroups = async () => {
  try {
    const params = new URLSearchParams();
    params.append('page', pagination.page);
    params.append('size', pagination.size);
    if (filters.keyword) {
      params.append('keyword', filters.keyword);
    }
    const response = await axios.get(`/api/service-groups?${params}`);
    if (response.data.code === 0) {
      serviceGroups.value = response.data.data.items;
      pagination.total = response.data.data.total;
    }
  } catch (error) {
    ElMessage.error('加载程序分类列表失败');
  }
};

const resetForm = () => {
  groupForm.id = null;
  groupForm.group_name = '';
  groupForm.group_code = '';
  groupForm.display_order = 0;
  groupForm.description = '';
};

const resetFilters = () => {
  filters.keyword = '';
  loadServiceGroups();
};

const editServiceGroup = async (group) => {
  groupForm.id = group.id;
  groupForm.group_name = group.group_name;
  groupForm.group_code = group.group_code;
  groupForm.display_order = group.display_order;
  groupForm.description = group.description || '';
  showAddDialog.value = true;
};

const saveServiceGroup = async () => {
  if (!groupForm.group_name.trim()) {
    ElMessage.error('请输入分类名称');
    return;
  }
  if (!groupForm.group_code.trim()) {
    ElMessage.error('请输入分类编码');
    return;
  }
  try {
    const data = {
      group_name: groupForm.group_name,
      group_code: groupForm.group_code,
      display_order: groupForm.display_order,
      description: groupForm.description || null
    };
    let response;
    if (groupForm.id) {
      response = await axios.put(`/api/service-groups/${groupForm.id}`, data);
    } else {
      response = await axios.post('/api/service-groups', data);
    }
    if (response.data.code === 0) {
      ElMessage.success(groupForm.id ? '更新成功' : '新增成功');
      showAddDialog.value = false;
      resetForm();
      loadServiceGroups();
    } else {
      ElMessage.error(response.data.message || '操作失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '操作失败');
  }
};

const deleteServiceGroup = async (group) => {
  if (!confirm(`确定要删除分类 "${group.group_name}" 吗？`))
    return;
  try {
    const response = await axios.delete(`/api/service-groups/${group.id}`);
    if (response.data.code === 0) {
      ElMessage.success('删除成功');
      loadServiceGroups();
    } else {
      ElMessage.error(response.data.message || '删除失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '删除失败');
  }
};

const handlePageChange = (page) => {
  pagination.page = page;
  loadServiceGroups();
};

const handleSizeChange = (size) => {
  pagination.size = size;
  pagination.page = 1;
  loadServiceGroups();
};

onMounted(() => {
  loadServiceGroups();
});
</script>

<style scoped>
.service-group-page {
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

.search-input {
  width: 300px;
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
