<template>
  <div class="shell-page">
    <div class="shell-header">
      <el-tag type="primary">{{ serviceName }}</el-tag>
      <el-tag v-if="connected" class="connected-tag">已连接</el-tag>
      <el-tag v-else class="disconnected-tag">未连接</el-tag>
      <el-button @click="connect" v-if="!connected" type="primary">连接</el-button>
      <el-button @click="disconnect" v-else type="danger">断开</el-button>
      <el-button @click="goBack" type="default">返回</el-button>
    </div>
    <div class="shell-container">
      <div class="shell-output" ref="shellOutput" v-html="output"></div>
      <div class="shell-input-wrapper">
        <span class="shell-prompt">{{ prompt }}</span>
        <input 
          ref="shellInput"
          v-model="input" 
          class="shell-input" 
          @keydown.enter="sendCommand"
          placeholder="输入命令..."
          :disabled="!connected"
          autofocus
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

const route = useRoute();
const router = useRouter();
const serviceId = ref(route.query.serviceId);
const serviceName = ref(route.query.serviceName || '远程终端');
const connected = ref(false);
const output = ref('');
const input = ref('');
const prompt = ref('$ ');
let websocket = null;

const goBack = () => {
  router.push('/dashboard');
};

const connect = () => {
  const token = localStorage.getItem('token');
  if (!token) {
    ElMessage.error('请先登录');
    router.push('/login');
    return;
  }

  output.value = '[正在连接服务器...]\n';
  
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${window.location.host}/api/shell/ws/${serviceId.value}?token=${token}`;
  
  websocket = new WebSocket(wsUrl);
  
  websocket.onopen = () => {
    connected.value = true;
    output.value += '[已连接到服务器]\n';
    prompt.value = '$ ';
  };
  
  websocket.onmessage = (event) => {
    let data = event.data;
    data = data.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    data = data.replace(/\n/g, '<br>').replace(/\r/g, '');
    data = data.replace(/ /g, '&nbsp;');
    output.value += data;
    
    setTimeout(() => {
      const shellOutput = document.querySelector('.shell-output');
      if (shellOutput) {
        shellOutput.scrollTop = shellOutput.scrollHeight;
      }
    }, 10);
  };
  
  websocket.onerror = (error) => {
    console.error('WebSocket error:', error);
    output.value += `[错误] 连接失败\n`;
    connected.value = false;
  };
  
  websocket.onclose = (event) => {
    output.value += `[断开] 连接已关闭 (Code: ${event.code})\n`;
    connected.value = false;
    websocket = null;
  };
};

const disconnect = () => {
  if (websocket) {
    websocket.close();
  }
};

const sendCommand = () => {
  if (!websocket || !connected.value || !input.value.trim()) return;
  
  const command = input.value;
  output.value += `<span class="command">${input.value}</span><br>`;
  websocket.send(command + '\n');
  input.value = '';
};

onMounted(() => {
  connect();
});

onUnmounted(() => {
  disconnect();
});
</script>

<style scoped>
.shell-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #1e1e1e;
}

.shell-header {
  padding: 16px 20px;
  background: #2d2d2d;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #3d3d3d;
}

.shell-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.shell-output {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 14px;
  color: #d4d4d4;
  line-height: 1.5;
}

.shell-output .command {
  color: #4ec9b0;
}

.shell-input-wrapper {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  background: #2d2d2d;
  border-top: 1px solid #3d3d3d;
}

.shell-prompt {
  color: #4ec9b0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 14px;
  margin-right: 8px;
}

.shell-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #d4d4d4;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 14px;
}

.shell-input::placeholder {
  color: #6b6b6b;
}

.shell-input:disabled {
  opacity: 0.5;
}

.connected-tag {
  background: #52c41a;
  color: #fff;
}

.disconnected-tag {
  background: #ff4d4f;
  color: #fff;
}
</style>
