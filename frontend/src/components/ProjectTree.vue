<template>
  <div class="project-tree">
    <div class="tree-header">
      <span class="tree-title">项目树</span>
      <el-button size="mini" @click="refreshTree">刷新</el-button>
    </div>
    <div class="tree-container">
      <el-tree
        :data="treeData"
        :props="treeProps"
        :default-expand-all="true"
        @node-click="handleNodeClick"
        :highlight-current="true"
        class="project-el-tree"
      >
        <template #default="{ node, data }">
          <span class="tree-node">
            <span v-if="data.type === 'project'" class="icon-wrapper">
              <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
            </span>
            <span v-else-if="data.type === 'subsystem'" class="icon-wrapper">
              <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
              </svg>
            </span>
            <span v-else class="icon-wrapper">
              <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
            </span>
            <span class="node-label">{{ data.label }}</span>
          </span>
        </template>
      </el-tree>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import axios from '@/utils/axios';

const emit = defineEmits(['node-click']);

const treeData = ref([]);
const treeProps = reactive({
  label: 'label',
  children: 'children'
});

const loadTree = async () => {
  try {
    const response = await axios.get('/api/projects/tree');
    console.log('项目树接口响应:', response.data);
    if (response.data.code === 0) {
      if (!response.data.data || response.data.data.length === 0) {
        console.warn('项目树数据为空');
      }
      treeData.value = response.data.data.map(project => ({
        id: project.id,
        label: project.name,
        type: 'project',
        children: project.subsystems?.map(subsystem => ({
          id: subsystem.id,
          label: subsystem.subsystem_name,
          type: 'subsystem',
          project_id: project.id,
          children: subsystem.service_groups?.map(group => ({
            id: group.id,
            label: group.group_name,
            type: 'service_group',
            project_id: project.id,
            subsystem_id: subsystem.id
          })) || []
        })) || []
      }));
    } else {
      console.error('项目树接口返回错误:', response.data.message);
    }
  } catch (error) {
    console.error('加载项目树失败', error.response?.data || error.message);
  }
};

const handleNodeClick = (data) => {
  emit('node-click', data);
};

const refreshTree = () => {
  loadTree();
};

onMounted(() => {
  loadTree();
});
</script>

<style scoped>
.project-tree {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e8e8e8;
}

.tree-title {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.project-el-tree {
  background: transparent;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
}

.icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
}

.icon {
  width: 16px;
  height: 16px;
}

.node-label {
  font-size: 13px;
  color: #666;
}

:deep(.el-tree-node.is-current > .el-tree-node__content) {
  background: #e6f7ff;
  color: #1890ff;
}

:deep(.el-tree-node__content:hover) {
  background: #f5f5f5;
}
</style>