import { reactive, watch } from 'vue';
import { ElMessage } from 'element-plus';

// 终端设置：两个 SSH 终端入口（服务器管理 / 服务管理）共用同一份本地偏好
const STORAGE_KEY = 'srmc.terminal.settings';

const readSettings = () => {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    return {
      // 默认均开启，只有显式保存为 false 时才关闭
      autoCopy: saved.autoCopy !== false,
      rightClickPaste: saved.rightClickPaste !== false
    };
  } catch (e) {
    return { autoCopy: true, rightClickPaste: true };
  }
};

export const terminalSettings = reactive(readSettings());

watch(
  terminalSettings,
  (value) => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ autoCopy: value.autoCopy, rightClickPaste: value.rightClickPaste })
      );
    } catch (e) {
      // 本地存储不可用（隐私模式等）时只影响持久化，不影响本次使用
      console.warn('终端设置保存失败:', e);
    }
  },
  { deep: true }
);

// 非安全上下文（http + IP）下浏览器不提供 Clipboard API，
// 这里保留一份本次会话内复制过的文本作为右键粘贴兜底
let sessionClipboard = '';

const copyByTextarea = (text) => {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  let ok = false;
  try {
    textarea.select();
    ok = document.execCommand('copy');
  } catch (e) {
    console.warn('复制到剪贴板失败:', e);
  } finally {
    document.body.removeChild(textarea);
  }
  return ok;
};

const writeClipboard = async (text) => {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      // 权限被拒或非安全上下文，降级到 execCommand
      console.warn('Clipboard API 写入失败，尝试降级复制:', e);
    }
  }
  return copyByTextarea(text);
};

const readClipboard = async () => {
  if (navigator.clipboard && navigator.clipboard.readText) {
    try {
      const text = await navigator.clipboard.readText();
      if (text) return text;
    } catch (e) {
      console.warn('读取剪贴板失败，尝试使用会话内复制内容:', e);
    }
  }
  return sessionClipboard;
};

/**
 * 给终端挂载「选中自动复制」与「右键粘贴」。
 * 返回清理函数，需在终端销毁前调用。
 */
export function attachTerminalClipboard(terminal, containerEl) {
  let copyTimer = null;
  let lastCopied = '';

  const selectionDisposable = terminal.onSelectionChange(() => {
    if (!terminalSettings.autoCopy) return;
    // 拖拽选择会连续触发，稍作延后避免频繁写剪贴板
    clearTimeout(copyTimer);
    copyTimer = setTimeout(async () => {
      try {
        const text = terminal.getSelection();
        if (!text || text === lastCopied) return;
        lastCopied = text;
        const ok = await writeClipboard(text);
        if (ok) sessionClipboard = text;
      } catch (e) {
        console.warn('选中文本自动复制失败:', e);
      }
    }, 120);
  });

  // 用户通过 Ctrl+C / 剪切复制时同步到会话剪贴板
  const rememberSelection = () => {
    const text = terminal.getSelection();
    if (text) sessionClipboard = text;
  };
  containerEl?.addEventListener('copy', rememberSelection, true);
  containerEl?.addEventListener('cut', rememberSelection, true);

  const handleContextMenu = async (event) => {
    if (!terminalSettings.rightClickPaste) return;
    // 开启右键粘贴时屏蔽浏览器默认菜单
    event.preventDefault();
    let text = '';
    try {
      text = await readClipboard();
    } catch (e) {
      console.warn('右键粘贴读取剪贴板失败:', e);
    }
    if (!text) {
      ElMessage.warning('无法读取剪贴板，请检查浏览器剪贴板权限，或使用 Ctrl+Shift+V 粘贴');
      return;
    }
    // 统一换行符后走 xterm 输入链路，支持多行粘贴
    terminal.paste(text.replace(/\r\n/g, '\r').replace(/\n/g, '\r'));
    terminal.focus();
  };

  containerEl?.addEventListener('contextmenu', handleContextMenu);

  return () => {
    clearTimeout(copyTimer);
    selectionDisposable.dispose();
    containerEl?.removeEventListener('contextmenu', handleContextMenu);
    containerEl?.removeEventListener('copy', rememberSelection, true);
    containerEl?.removeEventListener('cut', rememberSelection, true);
  };
}
