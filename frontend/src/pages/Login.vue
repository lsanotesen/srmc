<template>
  <div class="login-container">
    <div class="login-box">
      <div class="logo">
        <h1>SRMC</h1>
        <p>服务资源管理中心</p>
      </div>
      <el-form ref="formRef" :model="form" class="login-form">
        <el-form-item prop="username" label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item prop="password" label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="login-btn" @click="handleLogin">登录</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

const form = reactive({
  username: '',
  password: ''
})

const formRef = ref(null)

async function handleLogin() {
  if (!form.username || !form.password) {
    ElMessage.error('请输入用户名和密码')
    return
  }
  
  const result = await userStore.login(form.username, form.password)
  if (result.code === 0) {
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } else {
    ElMessage.error(result.message || '登录失败')
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-box {
  background: #fff;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
  width: 400px;
}

.logo {
  text-align: center;
  margin-bottom: 30px;
}

.logo h1 {
  margin: 0;
  font-size: 36px;
  color: #667eea;
}

.logo p {
  margin: 10px 0 0;
  color: #9ca3af;
}

.login-form {
  width: 100%;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
}
</style>