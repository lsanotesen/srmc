<template>
  <div class="shell-page">
    <div class="shell-header">
      <el-tag type="primary">{{ serviceName }}</el-tag>
      <el-tag v-if="connected" class="connected-tag">已连接</el-tag>
      <el-tag v-else class="disconnected-tag">未连接</el-tag>
      <el-button @click="connect" v-if="!connected" type="primary">连接</el-button>
      <el-button @click="disconnect" v-else type="danger">断开</el-button>
      <el-button @click="goBack" type="default">返回</el-button>
      <TerminalSettingsMenu class="shell-header-settings" />
    </div>
    <div class="shell-container">
      <div class="terminal-wrapper" ref="terminalRef"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { WebLinksAddon } from 'xterm-addon-web-links';
import TerminalSettingsMenu from '@/components/TerminalSettingsMenu.vue';
import { attachTerminalClipboard } from '@/composables/useTerminalSettings';
import 'xterm/css/xterm.css';

const route = useRoute();
const router = useRouter();
// 服务器管理入口通过 ?server_id= 传入，服务管理入口通过 ?serviceId= 传入
const serverId = ref(route.query.server_id);
const serviceId = ref(route.query.serviceId);
// 服务器多 SSH 账号：账号管理弹窗点「登录」时通过 account_id/accountName 传入
const accountId = ref(route.query.account_id || '');
const isServerMode = !!serverId.value;
const serviceName = ref(
  (route.query.serverName || route.query.serviceName ||
    (isServerMode ? '服务器终端' : '远程终端')) +
  (route.query.accountName ? `（${route.query.accountName}）` : '')
);

const connected = ref(false);
const terminalRef = ref(null);

let terminal = null;
let fitAddon = null;
let websocket = null;
let terminalReady = false;
let messageQueue = [];
let terminalClickHandler = null;
let windowResizeHandler = null;
let sizeSyncTimers = [];
let detachClipboard = null;
// 首次连接延后到终端 fit 完成后执行，确保首帧携带真实尺寸
let autoConnectPending = false;

// 返回路径：优先使用入口透传的 from（仅接受站内路径），
// 未提供时按模式回退——服务器终端回服务器管理，服务终端保持原有行为（运行总览）。
const resolveBackPath = () => {
  const from = route.query.from;
  if (typeof from === 'string' && from.startsWith('/') && !from.startsWith('//')) {
    return from;
  }
  return isServerMode ? '/servers' : '/';
};

const goBack = () => {
  router.push(resolveBackPath());
};

const focusTerminal = () => {
  // xterm 通过隐藏的 textarea 接收键盘输入，必须聚焦到它才能真正输入
  const textarea = terminalRef.value?.querySelector('.xterm-helper-textarea');
  if (textarea) textarea.focus();
  terminal?.focus();
};

// 用二进制消息通知后端同步 PTY 尺寸：[0x01][cols_uint16_le][rows_uint16_le]
// 每次都读取终端最新的 cols/rows（xterm 只提供 cols/rows，没有 size 属性），
// 保证不会用旧尺寸覆盖新尺寸
const syncTerminalSize = () => {
  if (!terminal || !websocket || websocket.readyState !== WebSocket.OPEN) return;
  const cols = terminal.cols;
  const rows = terminal.rows;
  if (!cols || !rows) return;
  try {
    const buf = new ArrayBuffer(5);
    const view = new DataView(buf);
    view.setUint8(0, 0x01);
    view.setUint16(1, cols, true);
    view.setUint16(3, rows, true);
    websocket.send(buf);
  } catch (e) {
    console.warn('Failed to send resize:', e);
  }
};

const clearSizeSyncTimers = () => {
  sizeSyncTimers.forEach((timer) => clearTimeout(timer));
  sizeSyncTimers = [];
};

// 建链后补发几次尺寸：PTY 在 SSH 会话建立前就可能收到首帧，
// 单次发送无法确认是否生效，多轮补发可覆盖建链/认证耗时较长的场景
const scheduleSizeSyncRetry = () => {
  clearSizeSyncTimers();
  sizeSyncTimers = [300, 900, 1800].map((ms) =>
    setTimeout(() => {
      if (connected.value) syncTerminalSize();
    }, ms)
  );
};

const cleanupTerminal = () => {
  clearSizeSyncTimers();
  detachClipboard?.();
  detachClipboard = null;
  if (terminal) {
    terminal.dispose();
    terminal = null;
  }
  fitAddon = null;
  terminalReady = false;
  messageQueue = [];

  if (terminalClickHandler && terminalRef.value) {
    terminalRef.value.removeEventListener('click', terminalClickHandler, true);
    terminalClickHandler = null;
  }
  if (windowResizeHandler) {
    window.removeEventListener('resize', windowResizeHandler);
    windowResizeHandler = null;
  }
};

const initTerminal = () => {
  cleanupTerminal();

  terminal = new Terminal({
    fontSize: 14,
    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
    cursorBlink: true,
    scrollback: 10000,
    convertEol: true,
    disableStdin: false,
    rendererType: 'canvas',
    screenKeys: true,
    theme: {
      background: '#1e1e1e',
      foreground: '#d4d4d4',
      cursor: '#d4d4d4',
      selection: '#264f78',
      black: '#000000',
      red: '#cd3131',
      green: '#0dbc79',
      yellow: '#e5e510',
      blue: '#2472c8',
      magenta: '#bc3fbc',
      cyan: '#11a8cd',
      white: '#e5e5e5',
      brightBlack: '#666666',
      brightRed: '#f14c4c',
      brightGreen: '#23d18b',
      brightYellow: '#f5f543',
      brightBlue: '#3b8eea',
      brightMagenta: '#d670d6',
      brightCyan: '#29b8db',
      brightWhite: '#e5e5e5'
    }
  });

  fitAddon = new FitAddon();
  terminal.loadAddon(fitAddon);
  terminal.loadAddon(new WebLinksAddon());

  terminal.open(terminalRef.value);

  // 挂载选中自动复制与右键粘贴
  detachClipboard = attachTerminalClipboard(terminal, terminalRef.value);

  setTimeout(() => {
    fitAddon?.fit();
    focusTerminal();
    terminalReady = true;
    // 初始化完成后再同步一次尺寸（fit 后尺寸可能已变化）
    syncTerminalSize();
    // 补齐终端初始化期间积压的输出
    while (messageQueue.length > 0) {
      const msg = messageQueue.shift();
      if (msg) terminal?.write(msg);
    }
    // fit 完成后才建链：此时终端的 cols/rows 已是真实列数/行数，
    // 首帧即可把正确尺寸带给后端创建 PTY，不会先落到默认 80x24
    if (autoConnectPending) {
      autoConnectPending = false;
      connect();
    }
  }, 200);

  // 键盘输入直连 WebSocket，由 xterm 负责回显与光标移动
  terminal.onData((data) => {
    if (websocket && connected.value) {
      websocket.send(data);
    }
  });

  terminal.onResize(() => {
    // 注意：这里不能调用 fitAddon.fit()，否则会与 onResize 形成死循环
    syncTerminalSize();
  });

  terminalClickHandler = () => focusTerminal();
  terminalRef.value?.addEventListener('click', terminalClickHandler, true);

  windowResizeHandler = () => {
    fitAddon?.fit();
  };
  window.addEventListener('resize', windowResizeHandler);
};

const connect = () => {
  autoConnectPending = false;
  const token = localStorage.getItem('token');
  if (!token) {
    ElMessage.error('请先登录');
    router.push('/login');
    return;
  }

  if (isServerMode ? !serverId.value : !serviceId.value) {
    ElMessage.error('缺少目标服务器信息');
    return;
  }

  // 防止重复连接
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    return;
  }

  if (!terminal) {
    initTerminal();
  }
  // 建链前先 fit 一次，尽量让首帧携带真实列数/行数；
  // 若字体尚未测量完成 fit 会跳过，后续 resize 帧会纠正
  try {
    fitAddon?.fit();
  } catch (e) {
    console.warn('Fit before connect failed:', e);
  }
  terminal?.write('[正在连接服务器...]\r\n');

  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsPath = isServerMode
    ? `/api/shell/server/ws/${serverId.value}`
    : `/api/shell/ws/${serviceId.value}`;
  // 把终端实际尺寸随建链请求带给后端，后端据此创建 PTY，
  // 避免 PTY 固定 80x24 时首次提示符与终端列数不一致
  const initialSize = terminal ? { cols: terminal.cols, rows: terminal.rows } : { cols: 80, rows: 24 };
  const accountQuery = isServerMode && accountId.value
    ? `&account_id=${encodeURIComponent(accountId.value)}`
    : '';
  const wsUrl = `${wsProtocol}//${window.location.host}${wsPath}?token=${token}&cols=${initialSize.cols}&rows=${initialSize.rows}${accountQuery}`;

  websocket = new WebSocket(wsUrl);
  websocket.binaryType = 'arraybuffer';

  websocket.onopen = () => {
    connected.value = true;
    // 建链后立即同步当前尺寸，并在稍后补发，避免单帧丢失导致 PTY 停留在旧尺寸
    syncTerminalSize();
    scheduleSizeSyncRetry();
    setTimeout(() => {
      focusTerminal();
      syncTerminalSize();
    }, 500);
  };

  websocket.onmessage = (event) => {
    const msg = event.data instanceof ArrayBuffer ? new Uint8Array(event.data) : event.data;
    if (!terminal) return;
    if (terminalReady) {
      terminal.write(msg);
    } else {
      messageQueue.push(msg);
    }
  };

  websocket.onerror = (error) => {
    console.error('WebSocket error:', error);
    terminal?.write('\r\n[错误] 连接失败\r\n');
    connected.value = false;
  };

  websocket.onclose = (event) => {
    terminal?.write(`\r\n[断开] 连接已关闭 (Code: ${event.code})\r\n`);
    connected.value = false;
    clearSizeSyncTimers();
    websocket = null;
  };
};

const disconnect = () => {
  clearSizeSyncTimers();
  if (websocket) {
    websocket.close();
  }
};

onMounted(() => {
  nextTick(() => {
    if (!terminalRef.value) {
      console.error('Terminal ref not found!');
      return;
    }
    initTerminal();
    // 由 initTerminal 在 fit 完成后发起连接
    autoConnectPending = true;
  });
});

onUnmounted(() => {
  disconnect();
  cleanupTerminal();
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

.shell-header-settings {
  margin-left: auto;
}

.shell-container {
  flex: 1;
  /* flex 子项默认 min-height:auto，内容变长时会顶开容器把终端挤出可视区 */
  min-height: 0;
  overflow: hidden;
  background: #1e1e1e;
}

.terminal-wrapper {
  width: 100%;
  height: 100%;
  padding: 8px;
  box-sizing: border-box;
}

.connected-tag {
  background-color: #0dbc79 !important;
  border-color: #0dbc79 !important;
  color: #ffffff !important;
}

.disconnected-tag {
  background-color: #666666 !important;
  border-color: #666666 !important;
  color: #ffffff !important;
}
</style>
