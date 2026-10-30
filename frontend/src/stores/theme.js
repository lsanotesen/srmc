import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'srmc-theme'
const VALID_THEMES = ['light', 'dark']

function readInitialTheme() {
  const saved = localStorage.getItem(STORAGE_KEY)
  return VALID_THEMES.includes(saved) ? saved : 'light'
}

/**
 * 将主题应用到根元素：
 * - html.dark 供本项目 CSS 变量与 Element Plus 暗色模式使用
 * - data-theme 便于第三方/调试识别当前主题
 */
function applyTheme(theme) {
  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
  root.setAttribute('data-theme', theme)
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref(readInitialTheme())
  // 初始化即应用，保证刷新 / 路由跳转后主题保持一致
  applyTheme(theme.value)

  function setTheme(next) {
    if (!VALID_THEMES.includes(next)) return
    theme.value = next
    localStorage.setItem(STORAGE_KEY, next)
    applyTheme(next)
  }

  function toggleTheme() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  return { theme, setTheme, toggleTheme }
})
