<template>
  <div class="login-container">
    <div class="login-bg">
      <div class="bg-circle bg-circle-1"></div>
      <div class="bg-circle bg-circle-2"></div>
      <div class="bg-circle bg-circle-3"></div>
    </div>
    
    <div class="login-box">
      <div class="logo-section">
        <div class="logo-icon">
          <el-icon name="server" :size="40" />
        </div>
        <div class="logo-text">
          <h1>SRMC</h1>
          <p>服务资源管理中心</p>
        </div>
      </div>
      
      <el-form ref="formRef" :model="form" class="login-form" @keyup.enter="handleLogin">
        <div class="form-title">欢迎登录</div>
        
        <el-form-item prop="username">
          <div class="input-wrapper">
            <el-icon name="user" class="input-icon" />
            <el-input 
              v-model="form.username" 
              placeholder="请输入用户名" 
              class="custom-input"
              :disabled="isLoading"
            />
          </div>
        </el-form-item>
        
        <el-form-item prop="password">
          <div class="input-wrapper">
            <el-icon name="lock" class="input-icon" />
            <el-input 
              v-model="form.password" 
              type="password" 
              placeholder="请输入密码" 
              class="custom-input"
              :disabled="isLoading"
            />
          </div>
        </el-form-item>
        
        <el-form-item class="remember-item">
          <el-checkbox v-model="rememberMe">记住我</el-checkbox>
          <a href="#" class="forgot-link">忘记密码？</a>
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            class="login-btn" 
            @click="handleLogin"
            :loading="isLoading"
            :disabled="isLoading"
          >
            {{ isLoading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="version-info">
        <span>Version 1.0.0</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const userStore = useUserStore()

const form = reactive({
  username: '',
  password: ''
})

const formRef = ref(null)
const isLoading = ref(false)
const rememberMe = ref(false)

onMounted(() => {
  const savedUser = localStorage.getItem('rememberedUser')
  if (savedUser) {
    form.username = savedUser
    rememberMe.value = true
  }
})

async function handleLogin() {
  if (!form.username.trim()) {
    ElMessage.error('请输入用户名')
    return
  }
  
  if (!form.password.trim()) {
    ElMessage.error('请输入密码')
    return
  }
  
  isLoading.value = true
  
  try {
    const response = await axios.post('/api/auth/login', { 
      username: form.username.trim(), 
      password: form.password.trim() 
    })
    
    if (response.data.code === 0) {
      const { user, access_token } = response.data.data
      
      userStore.user = user
      userStore.token = access_token
      localStorage.setItem('token', access_token)
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
      
      if (rememberMe.value) {
        localStorage.setItem('rememberedUser', form.username)
      } else {
        localStorage.removeItem('rememberedUser')
      }
      
      userStore.fetchMenu().then(() => {
        router.push('/dashboard').catch(() => {
          router.push('/')
        })
      }).catch(() => {
        router.push('/dashboard').catch(() => {
          router.push('/')
        })
      })
      
    } else {
      ElMessage.error(response.data.message || '登录失败')
    }
  } catch (error) {
    console.error('登录请求失败:', error)
    if (error.response) {
      ElMessage.error(error.response.data.message || '登录失败')
    } else {
      ElMessage.error('网络连接失败，请稍后重试')
    }
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
  position: relative;
  overflow: hidden;
}

.login-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
}

.bg-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.15;
}

.bg-circle-1 {
  width: 600px;
  height: 600px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  top: -200px;
  right: -100px;
  animation: float1 20s ease-in-out infinite;
}

.bg-circle-2 {
  width: 400px;
  height: 400px;
  background: linear-gradient(135deg, #ec4899, #f43f5e);
  bottom: -100px;
  left: -50px;
  animation: float2 15s ease-in-out infinite;
}

.bg-circle-3 {
  width: 300px;
  height: 300px;
  background: linear-gradient(135deg, #10b981, #06b6d4);
  top: 50%;
  left: 10%;
  animation: float3 18s ease-in-out infinite;
}

@keyframes float1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-50px, 50px) scale(1.1); }
}

@keyframes float2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(50px, -30px) scale(0.9); }
}

@keyframes float3 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-30px, -50px) scale(1.05); }
}

.login-box {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 48px;
  border-radius: 20px;
  width: 420px;
  box-shadow: 
    0 8px 32px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  position: relative;
  z-index: 10;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
}

.logo-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 8px 25px rgba(59, 130, 246, 0.4);
}

.logo-text h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, #fff 0%, #cbd5e1 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.logo-text p {
  margin: 4px 0 0;
  font-size: 13px;
  color: #94a3b8;
}

.form-title {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 24px;
  text-align: center;
}

.login-form {
  width: 100%;
}

.input-wrapper {
  position: relative;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
}

.input-wrapper:focus-within {
  border-color: rgba(59, 130, 246, 0.5);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.input-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3b8;
  font-size: 18px;
}

.custom-input {
  width: 100%;
  background: transparent;
  border: none;
  padding: 14px 14px 14px 48px;
  color: #fff;
  font-size: 14px;
}

.custom-input::placeholder {
  color: #64748b;
}

.custom-input :deep(.el-input__wrapper) {
  background: transparent;
  border: none;
  box-shadow: none;
}

.custom-input :deep(.el-input__inner) {
  background: transparent;
  border: none;
  color: #fff;
}

.custom-input :deep(.el-input__inner):focus {
  box-shadow: none;
}

.custom-input:disabled :deep(.el-input__inner) {
  color: #64748b;
  cursor: not-allowed;
}

.remember-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.remember-item :deep(.el-checkbox__label) {
  color: #94a3b8;
  font-size: 13px;
}

.remember-item :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: #3b82f6;
  border-color: #3b82f6;
}

.forgot-link {
  color: #60a5fa;
  font-size: 13px;
  text-decoration: none;
  transition: color 0.3s ease;
}

.forgot-link:hover {
  color: #93c5fd;
}

.login-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border: none;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
  transition: all 0.3s ease;
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5);
}

.login-btn:active:not(:disabled) {
  transform: translateY(0);
}

.login-btn :deep(.el-button__loading-text) {
  color: #fff;
}

.version-info {
  text-align: center;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.version-info span {
  color: #64748b;
  font-size: 12px;
}
</style>
