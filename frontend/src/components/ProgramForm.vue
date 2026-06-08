<template>
  <el-dialog :title="isEdit ? '编辑程序' : '新增程序'" v-model="visible" width="600px">
    <el-form :model="form" label-width="120px" ref="formRef">
      <el-form-item label="功能描述" required>
        <el-input v-model="form.func_desc" placeholder="请输入功能描述" />
      </el-form-item>
      <el-form-item label="对应模块">
        <el-input v-model="form.module" placeholder="请输入模块名称" />
      </el-form-item>
      <el-form-item label="IP地址" required>
        <el-input v-model="form.ip" placeholder="请输入服务器IP" />
      </el-form-item>
      <el-form-item label="SSH用户名" required>
        <el-input v-model="form.username" placeholder="请输入SSH用户名" />
      </el-form-item>
      <el-form-item label="SSH密码" :required="!isEdit">
        <el-input 
          v-model="form.password" 
          type="password" 
          placeholder="编辑时留空表示不修改密码" 
        />
      </el-form-item>
      <el-form-item label="程序路径" required>
        <el-input v-model="form.program_path" placeholder="请输入程序路径" />
      </el-form-item>
      <el-form-item label="启动脚本">
        <el-input v-model="form.start_script" placeholder="如: ./start.sh" />
      </el-form-item>
      <el-form-item label="停止脚本">
        <el-input v-model="form.stop_script" placeholder="如: ./stop.sh" />
      </el-form-item>
      <el-form-item label="重启脚本">
        <el-input v-model="form.restart_script" placeholder="如: ./restart.sh" />
      </el-form-item>
      <el-form-item label="日志路径">
        <el-input v-model="form.log_path" placeholder="日志文件路径或目录" />
      </el-form-item>
      <el-form-item label="程序端口">
        <el-input v-model.number="form.port" placeholder="请输入端口号" />
      </el-form-item>
      <el-form-item label="负责人">
        <el-input v-model="form.owner" placeholder="请输入负责人" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="loading">
        {{ loading ? '保存中...' : (isEdit ? '保存修改' : '创建程序') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createProgram, updateProgram } from '../api/program'

const props = defineProps({
  visible: Boolean,
  editData: Object,
  isEdit: Boolean
})

const emit = defineEmits(['close', 'success'])

const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  id: null,
  func_desc: '',
  module: '',
  ip: '',
  username: '',
  password: '',
  program_path: '',
  start_script: '',
  stop_script: '',
  restart_script: '',
  log_path: '',
  port: null,
  owner: '',
  remark: ''
})

watch(() => props.visible, (val) => {
  if (val && props.editData) {
    Object.assign(form, {
      id: props.editData.id,
      func_desc: props.editData.func_desc,
      module: props.editData.module || '',
      ip: props.editData.ip,
      username: props.editData.username,
      password: '',
      program_path: props.editData.program_path,
      start_script: props.editData.start_script || '',
      stop_script: props.editData.stop_script || '',
      restart_script: props.editData.restart_script || '',
      log_path: props.editData.log_path || '',
      port: props.editData.port,
      owner: props.editData.owner || '',
      remark: props.editData.remark || ''
    })
  } else if (val) {
    resetForm()
  }
})

function resetForm() {
  Object.assign(form, {
    id: null,
    func_desc: '',
    module: '',
    ip: '',
    username: '',
    password: '',
    program_path: '',
    start_script: '',
    stop_script: '',
    restart_script: '',
    log_path: '',
    port: null,
    owner: '',
    remark: ''
  })
}

function handleCancel() {
  emit('close')
}

async function handleSubmit() {
  if (!form.func_desc.trim()) {
    ElMessage.error('请输入功能描述')
    return
  }
  if (!form.ip.trim()) {
    ElMessage.error('请输入IP地址')
    return
  }
  if (!form.username.trim()) {
    ElMessage.error('请输入SSH用户名')
    return
  }
  if (!form.program_path.trim()) {
    ElMessage.error('请输入程序路径')
    return
  }
  if (!props.isEdit && !form.password.trim()) {
    ElMessage.error('请输入SSH密码')
    return
  }

  loading.value = true
  try {
    const data = {
      func_desc: form.func_desc,
      module: form.module || undefined,
      ip: form.ip,
      username: form.username,
      password: form.password || undefined,
      program_path: form.program_path,
      start_script: form.start_script || undefined,
      stop_script: form.stop_script || undefined,
      restart_script: form.restart_script || undefined,
      log_path: form.log_path || undefined,
      port: form.port || undefined,
      owner: form.owner || undefined,
      remark: form.remark || undefined
    }

    let result
    if (props.isEdit && form.id) {
      result = await updateProgram(form.id, data)
    } else {
      result = await createProgram(data)
    }

    if (result.code === 0) {
      ElMessage.success(props.isEdit ? '更新成功' : '创建成功')
      emit('success')
      emit('close')
    } else {
      ElMessage.error(result.message || (props.isEdit ? '更新失败' : '创建失败'))
    }
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.message || error.message))
  } finally {
    loading.value = false
  }
}
</script>