<template>
  <el-dropdown trigger="click" :hide-on-click="false" class="terminal-settings">
    <el-button text size="small" class="terminal-settings-trigger">
      <el-icon><Setting /></el-icon>
      <span>终端设置</span>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item :hide-on-click="false">
          <div class="terminal-settings-item" @click.stop>
            <span class="terminal-settings-label">选中的文本自动复制到剪贴板</span>
            <el-switch v-model="terminalSettings.autoCopy" size="small" />
          </div>
        </el-dropdown-item>
        <el-dropdown-item :hide-on-click="false">
          <div class="terminal-settings-item" @click.stop>
            <span class="terminal-settings-label">鼠标右键粘贴剪贴板内容</span>
            <el-switch v-model="terminalSettings.rightClickPaste" size="small" />
          </div>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { Setting } from '@element-plus/icons-vue';
import { terminalSettings } from '@/composables/useTerminalSettings';
</script>

<style scoped>
.terminal-settings-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.terminal-settings-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  white-space: nowrap;
  padding: 4px 0;
}

.terminal-settings-label {
  font-size: 13px;
  line-height: 20px;
}
</style>
