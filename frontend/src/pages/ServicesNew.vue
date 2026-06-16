<template>
  <div class="services-page-new">
    <div class="page-layout">
      <div class="left-panel">
        <ProjectTree @node-click="handleTreeClick" />
      </div>
      <div class="right-panel">
        <div class="page-header">
          <h1>服务管理</h1>
          <div class="actions">
            <el-button type="danger" @click="confirmBatchDelete" :disabled="selectedServices.length === 0">
              批量删除 ({{ selectedServices.length }})
            </el-button>
            <el-button type="primary" @click="showAddDialog = true">新增服务</el-button>
            <el-button @click="downloadTemplate">下载模板</el-button>
            <el-button type="primary" @click="goToImport">导入服务</el-button>
            <el-button @click="exportServices">导出服务</el-button>
          </div>
        </div>

        <div class="search-bar">
          <el-select v-model="filters.project_id" placeholder="选择项目" clearable class="project-select" @change="handleProjectChange">
            <el-option label="全部项目" value="" />
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
          <el-select v-model="filters.subsystem_id" placeholder="选择子系统" clearable class="subsystem-select" @change="handleSubsystemChange">
            <el-option label="全部子系统" value="" />
            <el-option v-for="subsystem in subsystems" :key="subsystem.id" :label="subsystem.subsystem_name" :value="subsystem.id" />
          </el-select>
          <el-select v-model="filters.group_id" placeholder="选择程序分类" clearable class="group-select">
            <el-option label="全部分类" value="" />
            <el-option v-for="group in groups" :key="group.id" :label="group.group_name" :value="group.id" />
          </el-select>
          <el-input v-model="filters.keyword" placeholder="搜索功能描述或模块" class="search-input" @keyup.enter="loadServices" />
          <el-input v-model="filters.ip" placeholder="搜索IP地址" class="ip-input" @keyup.enter="loadServices" />
          <el-button type="primary" @click="loadServices">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>

        <div class="table-wrapper">
          <el-table 
            ref="serviceTable"
            :data="services" 
            border 
            @selection-change="handleSelectionChange"
            @select="handleSelect"
          >
            <el-table-column type="selection" width="60" />
            <el-table-column type="index" label="序号" width="80" />
            <el-table-column prop="func_desc" label="功能描述" min-width="150" />
            <el-table-column prop="module" label="对应模块" min-width="120" />
            <el-table-column prop="subsystem_name" label="子系统" min-width="120" />
            <el-table-column prop="group_name" label="程序分类" min-width="120" />
            <el-table-column prop="deploy_type" label="部署方式" min-width="100">
              <template #default="scope">
                <el-tag :type="getDeployType(scope.row.deploy_type).type">
                  {{ getDeployType(scope.row.deploy_type).label }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="service_type" label="服务类型" min-width="120">
              <template #default="scope">
                <el-tag :type="getServiceType(scope.row.service_type).type">
                  {{ getServiceType(scope.row.service_type).label }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="instance_name" label="运行实例" min-width="120" show-overflow-tooltip />
            <el-table-column prop="ip" label="IP地址" min-width="120" />
            <el-table-column prop="username" label="用户名" min-width="100" />
            <el-table-column prop="program_path" label="程序路径" min-width="180" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="scope">
                <el-tag :type="getStatusType(scope.row.status)">
                  {{ scope.row.status || '未知' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" align="center">
              <template #default="scope">
                <div class="action-buttons">
                  <div class="action-btn view-btn" @click="viewService(scope.row)">
                    <span>查看</span>
                  </div>
                  <div class="action-btn edit-btn" @click="editService(scope.row)">
                    <span>编辑</span>
                  </div>
                  <div class="action-btn delete-btn" @click="deleteService(scope.row)">
                    <span>删除</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="日志" width="80" align="center">
              <template #default="scope">
                <div class="action-buttons">
                  <div class="action-btn log-btn" @click="viewLog(scope.row)">
                    <span>日志</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="启停控制" width="160" align="center">
              <template #default="scope">
                <div class="action-buttons">
                  <template v-if="scope.row.status !== 'RUNNING'">
                    <div class="action-btn start-btn" :class="{ 'disabled': operatingServices.has(scope.row.id) }" @click="startService(scope.row)">
                      <span v-if="operatingServices.has(scope.row.id)">启动中...</span>
                      <span v-else>启动</span>
                    </div>
                  </template>
                  <template v-else>
                    <div class="action-btn stop-btn" :class="{ 'disabled': operatingServices.has(scope.row.id) }" @click="stopService(scope.row)">
                      <span v-if="operatingServices.has(scope.row.id)">停止中...</span>
                      <span v-else>停止</span>
                    </div>
                    <div class="action-btn restart-btn" :class="{ 'disabled': operatingServices.has(scope.row.id) }" @click="restartService(scope.row)">
                      <span v-if="operatingServices.has(scope.row.id)">重启中...</span>
                      <span v-else>重启</span>
                    </div>
                  </template>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="远程登录" width="100" align="center">
              <template #default="scope">
                <div class="action-buttons">
                  <div class="action-btn login-btn" @click="webShell(scope.row)">
                    <span>登录</span>
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
      </div>
    </div>

    <el-dialog title="新增/编辑服务" v-model="showAddDialog" width="700px" @close="resetForm">
      <el-form :model="serviceForm" label-width="120px">
        <el-form-item label="所属项目" required>
          <el-select v-model="serviceForm.project_id" placeholder="请选择项目" @change="handleFormProjectChange">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属子系统">
          <el-select v-model="serviceForm.subsystem_id" placeholder="请选择子系统（可选）" @change="handleFormSubsystemChange" :loading="formLoadingSubsystems">
            <el-option label="无" value="" />
            <el-option v-for="subsystem in formSubsystems" :key="subsystem.id" :label="subsystem.subsystem_name" :value="subsystem.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="程序分类">
          <el-select v-model="serviceForm.group_id" placeholder="请选择程序分类（可选）" :loading="formLoadingGroups">
            <el-option label="无" value="" />
            <el-option v-for="group in formGroups" :key="group.id" :label="group.group_name" :value="group.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="功能描述" required>
          <el-input v-model="serviceForm.func_desc" placeholder="请输入功能描述" />
        </el-form-item>
        <el-form-item label="对应模块">
          <el-input v-model="serviceForm.module" placeholder="请输入模块名称" />
        </el-form-item>
        <el-form-item label="IP地址" required>
          <el-input v-model="serviceForm.ip" placeholder="请输入服务器IP地址" />
        </el-form-item>
        <el-form-item label="SSH端口">
          <el-input v-model.number="serviceForm.ssh_port" placeholder="默认22" />
        </el-form-item>
        <el-form-item label="SSH用户名" required>
          <el-input v-model="serviceForm.username" placeholder="请输入SSH用户名" />
        </el-form-item>
        <el-form-item label="密码" :required="!serviceForm.id">
          <el-input v-model="serviceForm.password" type="password" placeholder="编辑时留空表示不修改密码" />
        </el-form-item>
        <!-- 主机部署相关字段 -->
        <template v-if="serviceForm.deploy_type === 'HOST' || !serviceForm.deploy_type">
          <el-form-item label="程序路径" required>
            <el-input v-model="serviceForm.program_path" placeholder="请输入程序路径" />
          </el-form-item>
          <el-form-item label="启动脚本" required>
            <el-input v-model="serviceForm.start_script" placeholder="如: ./start.sh" />
          </el-form-item>
          <el-form-item label="停止脚本" required>
            <el-input v-model="serviceForm.stop_script" placeholder="如: ./stop.sh" />
          </el-form-item>
          <el-form-item label="日志路径">
            <el-input v-model="serviceForm.log_path" placeholder="日志文件路径或目录" />
          </el-form-item>
          <el-form-item label="程序端口">
            <el-input v-model.number="serviceForm.port" placeholder="请输入端口号" />
          </el-form-item>
        </template>

        <!-- Docker部署相关字段 -->
        <template v-if="serviceForm.deploy_type === 'DOCKER'">
          <el-form-item label="程序路径" required>
            <el-input v-model="serviceForm.program_path" placeholder="docker-compose.yml所在目录路径" />
          </el-form-item>
          <el-form-item label="启动脚本" required>
            <el-input v-model="serviceForm.start_script" placeholder="如: docker-compose up -d" />
          </el-form-item>
          <el-form-item label="停止脚本" required>
            <el-input v-model="serviceForm.stop_script" placeholder="如: docker-compose down" />
          </el-form-item>
          <el-form-item label="容器名称">
            <el-input v-model="serviceForm.container_name" placeholder="请输入容器名称" />
          </el-form-item>
          <el-form-item label="镜像名称">
            <el-input v-model="serviceForm.image_name" placeholder="如: nginx:latest" />
          </el-form-item>
          <el-form-item label="端口映射">
            <el-input v-model="serviceForm.port_mapping" placeholder="如: 8080:80" />
          </el-form-item>
          <el-form-item label="日志类型">
            <el-select v-model="serviceForm.log_type" placeholder="请选择日志类型">
              <el-option label="主机目录" value="HOST_DIR" />
              <el-option label="Docker Logs" value="DOCKER_LOGS" />
            </el-select>
          </el-form-item>
          <el-form-item label="日志路径" v-if="serviceForm.log_type === 'HOST_DIR'">
            <el-input v-model="serviceForm.log_path" placeholder="挂载到主机的日志目录路径" />
          </el-form-item>
          <el-form-item label="程序端口">
            <el-input v-model.number="serviceForm.port" placeholder="容器内部端口" />
          </el-form-item>
        </template>
        <el-form-item label="服务类型">
          <el-select v-model="serviceForm.service_type" placeholder="请选择服务类型">
            <el-option label="主机应用" value="HOST_APP" />
            <el-option label="Docker容器" value="DOCKER" />
            <el-option label="Elasticsearch" value="ES" />
            <el-option label="Solr" value="SOLR" />
            <el-option label="Redis" value="REDIS" />
            <el-option label="MySQL" value="MYSQL" />
            <el-option label="PostgreSQL" value="POSTGRESQL" />
            <el-option label="Kafka" value="KAFKA" />
            <el-option label="RocketMQ" value="ROCKETMQ" />
            <el-option label="RabbitMQ" value="RABBITMQ" />
            <el-option label="Nginx" value="NGINX" />
            <el-option label="AI模型" value="AI_MODEL" />
          </el-select>
        </el-form-item>
        <el-form-item label="部署方式">
          <el-select v-model="serviceForm.deploy_type" placeholder="请选择部署方式">
            <el-option label="主机部署" value="HOST" />
            <el-option label="Docker部署" value="DOCKER" />
          </el-select>
        </el-form-item>
        <!-- 主机部署才显示运行实例 -->
        <el-form-item label="运行实例" v-if="serviceForm.deploy_type === 'HOST' || !serviceForm.deploy_type">
          <el-input v-model="serviceForm.instance_name" placeholder="实例名称或主机名（可选）" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="serviceForm.owner" placeholder="请输入负责人" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="serviceForm.remark" type="textarea" :rows="3" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveService">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog title="服务详情" v-model="showDetailDialog">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="功能描述">{{ selectedService.func_desc || '-' }}</el-descriptions-item>
        <el-descriptions-item label="对应模块">{{ selectedService.module || '-' }}</el-descriptions-item>
        <el-descriptions-item label="所属项目">{{ selectedService.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="所属子系统">{{ selectedService.subsystem_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="程序分类">{{ selectedService.group_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ selectedService.ip || '-' }}</el-descriptions-item>
        <el-descriptions-item label="SSH端口">{{ selectedService.ssh_port || '-' }}</el-descriptions-item>
        <el-descriptions-item label="SSH用户名">{{ selectedService.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="程序端口">{{ selectedService.port || '-' }}</el-descriptions-item>
        <el-descriptions-item label="负责人">{{ selectedService.owner || '-' }}</el-descriptions-item>
        <el-descriptions-item label="程序路径">{{ selectedService.program_path || '-' }}</el-descriptions-item>
        <el-descriptions-item label="启动脚本">{{ selectedService.start_script || '-' }}</el-descriptions-item>
        <el-descriptions-item label="停止脚本">{{ selectedService.stop_script || '-' }}</el-descriptions-item>
        <el-descriptions-item label="日志路径">{{ selectedService.log_path || '-' }}</el-descriptions-item>
        <el-descriptions-item label="服务类型">
          <el-tag :type="getServiceType(selectedService.service_type).type">
            {{ getServiceType(selectedService.service_type).label }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="部署方式">
          <el-tag :type="getDeployType(selectedService.deploy_type).type">
            {{ getDeployType(selectedService.deploy_type).label }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="运行实例">{{ selectedService.instance_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(selectedService.status)">
            {{ selectedService.status || '未知' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="备注">{{ selectedService.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog title="日志查看" v-model="showLogDialog" width="900px" :before-close="handleLogClose">
      <div class="log-header">
        <!-- Docker Logs方式显示容器信息 -->
        <template v-if="selectedLogService?.deploy_type === 'DOCKER' && selectedLogService?.log_type === 'DOCKER_LOGS'">
          <el-tag type="info">Docker Logs - {{ selectedLogService.container_name || '未配置容器名称' }}</el-tag>
        </template>
        <!-- 主机目录方式显示文件选择 -->
        <template v-else>
          <el-select v-model="selectedLogFile" style="width: 250px" placeholder="选择日志文件" @change="loadLog">
            <el-option label="最新日志" value="" />
            <el-option v-for="file in logFiles" :key="file.name" :label="`${file.name} (${file.size})`" :value="file.name" />
          </el-select>
        </template>
        <el-select v-model="logLines" style="width: 120px">
          <el-option label="100行" :value="100" />
          <el-option label="200行" :value="200" />
          <el-option label="500行" :value="500" />
          <el-option label="1000行" :value="1000" />
        </el-select>
        <el-button @click="loadLogFileList">刷新列表</el-button>
        <el-button @click="refreshLog">刷新内容</el-button>
        <el-button @click="downloadLog" v-if="!(selectedLogService?.deploy_type === 'DOCKER' && selectedLogService?.log_type === 'DOCKER_LOGS')">下载日志</el-button>
      </div>
      <div class="log-content" ref="logContent">
        <pre>{{ logContentText }}</pre>
      </div>
    </el-dialog>

    <el-dialog title="远程终端" v-model="showShellDialog" width="900px" height="600px" :before-close="handleShellClose">
      <div class="shell-header">
        <el-tag type="primary" v-if="currentShellService">{{ currentShellService.func_desc }}</el-tag>
        <el-tag v-if="shellConnected" class="connected-tag">已连接</el-tag>
        <el-tag v-else class="disconnected-tag">未连接</el-tag>
        <el-button @click="connectShell" v-if="!shellConnected" type="primary">连接</el-button>
        <el-button @click="disconnectShell" v-else type="danger">断开</el-button>
        <el-tabs v-model="shellActiveTab" class="shell-tabs">
          <el-tab-pane label="终端" name="terminal">
          </el-tab-pane>
          <el-tab-pane label="文件管理" name="files">
          </el-tab-pane>
        </el-tabs>
      </div>
      <div class="shell-container" ref="shellContainer">
        <div v-show="shellActiveTab === 'terminal'" ref="terminalRef" class="terminal-container"></div>
        <div v-show="shellActiveTab === 'files'" class="file-manager">
          <div class="file-manager-panels">
            <!-- 左侧：本地文件 -->
            <div class="file-panel local-panel">
              <div class="panel-header">
                <span class="panel-title">📁 本地文件</span>
                <input type="file" ref="uploadFileInput" class="upload-input" @change="handleFileUpload" multiple />
                <input type="file" ref="uploadDirInput" class="upload-input" @change="handleDirUpload" multiple webkitdirectory directory />
                <el-button @click="triggerFileUpload" size="small">选择文件</el-button>
                <el-button @click="triggerDirUpload" size="small">选择目录</el-button>
                <el-button 
                  v-if="localFiles.length > 0" 
                  @click="uploadAllFiles" 
                  size="small" 
                  type="primary"
                  :disabled="uploadingAll"
                >
                  {{ uploadingAll ? '上传中...' : '全部上传' }}
                </el-button>
              </div>
              <div class="panel-body">
                <div v-if="localFiles.length === 0" class="empty-state">
                  <p>点击上方按钮选择本地文件</p>
                  <p style="font-size: 12px; color: #999;">或拖拽文件到此处</p>
                </div>
                <el-table :data="localFiles" class="file-table" v-else>
                  <el-table-column prop="relativePath" label="文件路径">
                    <template #default="scope">
                      <span class="file-icon">📄</span>
                      <span class="file-path">{{ scope.row.relativePath }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="size" label="大小">
                    <template #default="scope">{{ formatFileSize(scope.row.size) }}</template>
                  </el-table-column>
                  <el-table-column label="操作">
                    <template #default="scope">
                      <el-button @click="uploadSelectedFile(scope.row)" size="small" type="primary">上传</el-button>
                      <el-button @click="removeLocalFile(scope.$index)" size="small" type="danger">移除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <div class="drop-zone" @drop.prevent="handleDrop" @dragover.prevent>
                <span>📥 拖拽文件到此处上传</span>
              </div>
            </div>

            <!-- 中间分隔线 -->
            <div class="panel-divider">
              <div class="divider-line"></div>
            </div>

            <!-- 右侧：远程文件 -->
            <div class="file-panel remote-panel">
              <div class="panel-header">
                <span class="panel-title">🖥️ 远程文件</span>
                <div class="header-actions">
                  <el-button 
                    @click="goBack" 
                    size="small" 
                    :disabled="pathHistoryIndex <= 0"
                    title="后退"
                  >◀</el-button>
                  <el-button 
                    @click="goForward" 
                    size="small" 
                    :disabled="pathHistoryIndex >= pathHistory.length - 1"
                    title="前进"
                  >▶</el-button>
                  <el-input v-model="currentRemotePath" placeholder="远程路径" class="path-input" @keyup.enter="listRemoteFiles" />
                  <el-button @click="listRemoteFiles" size="small" type="primary">刷新</el-button>
                  <el-button @click="createRemoteDir" size="small">新建文件夹</el-button>
                </div>
              </div>
              <div class="panel-body" @contextmenu="handlePanelContextMenuNew">
                <el-table 
                  :data="remoteFiles" 
                  class="file-table" 
                  ref="remoteFileTable"
                >
                  <el-table-column prop="filename" label="文件名">
                    <template #default="scope">
                      <span v-if="scope.row.filename === '..'" class="dir-icon">⬆️</span>
                      <span v-else-if="scope.row.is_directory" class="dir-icon">📁</span>
                      <span v-else class="file-icon">📄</span>
                      <span 
                        @click="scope.row.is_directory && navigateToDir(scope.row.filename)"
                        @dblclick="scope.row.is_directory && navigateToDir(scope.row.filename)"
                        :class="{ 'dir-clickable': scope.row.is_directory }"
                      >{{ scope.row.filename }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="size" label="大小">
                    <template #default="scope">{{ scope.row.is_directory ? '-' : formatFileSize(scope.row.size) }}</template>
                  </el-table-column>
                  <el-table-column prop="modify_time" label="修改时间">
                    <template #default="scope">{{ formatTime(scope.row.modify_time) }}</template>
                  </el-table-column>
                  <el-table-column label="操作">
                    <template #default="scope">
                      <el-button v-if="!scope.row.is_directory" @click="downloadRemoteFile(scope.row.filename)" size="small">下载</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 文件覆盖确认对话框 -->
    <el-dialog 
      title="确认覆盖" 
      v-model="overwriteDialogVisible" 
      width="450px" 
      :close-on-click-modal="false" 
      :show-close="true"
      append-to-body
      style="z-index: 9999 !important;"
      :before-close="handleOverwriteDialogClose"
    >
      <div style="margin-bottom: 15px;">
        <p style="font-size: 14px; color: #666;">此文件夹已包含同名文件</p>
        <p style="margin-top: 10px; font-size: 16px; font-weight: bold;">{{ overwriteDialogFile }}</p>
      </div>
      
      <div style="margin-bottom: 20px; padding: 15px; background-color: #f5f5f5; border-radius: 4px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
          <span style="color: #999;">目标文件大小:</span>
          <span>2.05 MB</span>
        </div>
        <div style="display: flex; justify-content: space-between;">
          <span style="color: #999;">源文件大小:</span>
          <span>2.05 MB</span>
        </div>
      </div>
      
      <div style="margin-bottom: 20px; text-align: right;">
        <el-checkbox v-model="overwriteAllSelected" style="margin-right: 8px;">全部应用</el-checkbox>
        <span style="color: #999; font-size: 12px;">对所有后续同名文件执行相同操作</span>
      </div>
      
      <template #footer>
        <el-button @click="handleOverwriteCancel">取消</el-button>
        <el-button @click="handleOverwriteSkip">跳过</el-button>
        <el-button type="primary" @click="handleOverwriteConfirm">覆盖</el-button>
      </template>
    </el-dialog>

    <!-- 右键菜单 -->
    <el-menu
      v-if="contextMenuVisible"
      :style="{ left: contextMenuPosition.x + 'px', top: contextMenuPosition.y + 'px' }"
      class="context-menu"
      mode="vertical"
    >
      <el-menu-item v-if="contextMenuFile && !contextMenuFile.is_directory" @click="handleContextMenuDownload">
        <span>📥 下载</span>
      </el-menu-item>
      <el-menu-item v-if="contextMenuFile && contextMenuFile.filename !== '..'" @click="handleContextMenuRename">
        <span>✏️ 重命名</span>
      </el-menu-item>
      <el-menu-item v-if="contextMenuFile" @click="handleContextMenuCopy">
        <span>📋 复制路径</span>
      </el-menu-item>
      <el-menu-item v-if="contextMenuFile && contextMenuFile.filename !== '..'" @click="handleContextMenuDelete">
        <span>🗑️ 删除</span>
      </el-menu-item>
    </el-menu>

    <el-dialog title="导入服务" v-model="showImportDialog">
      <el-upload
        class="upload-demo"
        :auto-upload="false"
        :on-change="handleFileChange"
        accept=".xlsx"
      >
        <el-button type="primary">选择文件</el-button>
      </el-upload>
      <p class="import-tip">支持.xlsx格式文件，可先下载模板</p>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="doImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue';
import { ElMessage, ElMessageBox, ElMenu, ElMenuItem } from 'element-plus';
import axios from '@/utils/axios';
import ProjectTree from '@/components/ProjectTree.vue';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';

const services = ref([]);
const selectedServices = ref([]);
const serviceTable = ref(null);
const lastSelectedIndex = ref(-1);
const shiftPressed = ref(false);
const projects = ref([]);
const subsystems = ref([]);
const groups = ref([]);
const formSubsystems = ref([]);
const formGroups = ref([]);
const pagination = reactive({
  page: 1,
  size: 10,
  total: 0
});
const filters = reactive({
  project_id: '',
  subsystem_id: '',
  group_id: '',
  keyword: '',
  ip: ''
});
const showAddDialog = ref(false);
const showDetailDialog = ref(false);
const showLogDialog = ref(false);
const showImportDialog = ref(false);
const showShellDialog = ref(false);
const importFile = ref(null);
const selectedService = reactive({});
const currentShellService = ref(null);
const shellConnected = ref(false);
const terminalRef = ref(null);
let terminal = null;
let fitAddon = null;
const shellActiveTab = ref('terminal');
const remoteFiles = ref([]);
const currentRemotePath = ref('/');
const pathHistory = ref(['/']);
const pathHistoryIndex = ref(0);
const uploadFileInput = ref(null);
const uploadDirInput = ref(null);
const localFiles = ref([]);
const uploadingAll = ref(false);
const selectedLogService = ref(null);

// 覆盖确认相关
const overwriteOption = ref(''); // 'overwrite', 'skip', 'overwrite_all', 'skip_all'
const overwriteDialogVisible = ref(false);
const overwriteDialogFile = ref('');
const overwriteAllSelected = ref(false);
const overwriteResolve = ref(null);

// 右键菜单相关
const contextMenuVisible = ref(false);
const contextMenuPosition = ref({ x: 0, y: 0 });
const contextMenuFile = ref(null);
const logLines = ref(200);
const logContentText = ref('');
const logFiles = ref([]);
const selectedLogFile = ref('');
const isSubmitting = ref(false);
// 操作中的服务ID集合
const operatingServices = ref(new Set());
const serviceForm = reactive({
  id: null,
  project_id: '',
  subsystem_id: '',
  group_id: '',
  func_desc: '',
  module: '',
  ip: '',
  ssh_port: 22,
  username: '',
  password: '',
  program_path: '',
  start_script: '',
  stop_script: '',
  log_path: '',
  log_type: '',
  port: null,
  service_type: '',
  deploy_type: '',
  instance_name: '',
  // Docker相关字段
  container_name: '',
  image_name: '',
  port_mapping: '',
  owner: '',
  remark: ''
});
let statusInterval = null;

// 缓存已加载的数据，避免重复请求
const subsystemCache = ref({});
const groupCache = ref({});
// 加载状态
const loadingSubsystems = ref(false);
const loadingGroups = ref(false);
const formLoadingSubsystems = ref(false);
const formLoadingGroups = ref(false);

const getStatusType = (status) => {
  switch (status) {
    case 'RUNNING':
      return 'success';
    case 'STOPPED':
      return 'danger';
    default:
      return 'warning';
  }
};

const loadServices = async () => {
  try {
    const params = new URLSearchParams();
    params.append('page', pagination.page);
    params.append('size', pagination.size);
    if (filters.project_id) {
      params.append('project_id', filters.project_id);
    }
    if (filters.subsystem_id) {
      params.append('subsystem_id', filters.subsystem_id);
    }
    if (filters.group_id) {
      params.append('group_id', filters.group_id);
    }
    if (filters.keyword) {
      params.append('func_desc', filters.keyword);
    }
    if (filters.ip) {
      params.append('ip', filters.ip);
    }
    const response = await axios.get(`/api/services?${params}`);
    if (response.data.code === 0) {
      services.value = response.data.data.items;
      pagination.total = response.data.data.total;
      // 非阻塞更新状态，避免超时影响服务列表加载
      updateStatuses();
    }
  } catch (error) {
    ElMessage.error('加载服务列表失败');
  }
};

const loadProjects = async () => {
  try {
    const response = await axios.get('/api/projects', {
      params: { page: 1, size: 100 }
    });
    if (response.data.code === 0) {
      projects.value = response.data.data.items.map(p => ({
        id: p.id,
        name: p.name
      }));
    }
  } catch (error) {
    console.error('加载项目列表失败', error);
  }
};

const loadSubsystems = async (projectId = '', forForm = false) => {
  // 使用缓存键，空字符串表示全部子系统
  const cacheKey = projectId || 'all';
  
  // 检查缓存
  if (subsystemCache.value[cacheKey]) {
    return subsystemCache.value[cacheKey];
  }
  
  // 设置加载状态
  if (forForm) {
    formLoadingSubsystems.value = true;
  } else {
    loadingSubsystems.value = true;
  }
  
  try {
    const params = new URLSearchParams();
    if (projectId) {
      params.append('project_id', projectId);
    }
    const response = await axios.get(`/api/subsystems?${params}`);
    if (response.data.code === 0) {
      const data = response.data.data.items;
      // 缓存结果
      subsystemCache.value[cacheKey] = data;
      return data;
    }
    return [];
  } catch (error) {
    console.error('加载子系统列表失败', error);
    return [];
  } finally {
    // 清除加载状态
    if (forForm) {
      formLoadingSubsystems.value = false;
    } else {
      loadingSubsystems.value = false;
    }
  }
};

const loadGroups = async (subsystemId = '', forForm = false) => {
  if (!subsystemId) {
    return [];
  }
  
  // 检查缓存
  if (groupCache.value[subsystemId]) {
    return groupCache.value[subsystemId];
  }
  
  // 设置加载状态
  if (forForm) {
    formLoadingGroups.value = true;
  } else {
    loadingGroups.value = true;
  }
  
  try {
    const response = await axios.get(`/api/subsystems/${subsystemId}/groups`);
    if (response.data.code === 0) {
      const data = response.data.data;
      // 缓存结果
      groupCache.value[subsystemId] = data;
      return data;
    }
    return [];
  } catch (error) {
    console.error('加载程序分类列表失败', error);
    return [];
  } finally {
    // 清除加载状态
    if (forForm) {
      formLoadingGroups.value = false;
    } else {
      loadingGroups.value = false;
    }
  }
};

const handleTreeClick = async (data) => {
  filters.subsystem_id = '';
  filters.group_id = '';
  
  if (data.type === 'project') {
    // 点击项目，设置项目筛选并加载该项目下所有子系统和全局分类
    filters.project_id = data.id;
    subsystems.value = await loadSubsystems(data.id);
    groups.value = await loadGroups();
  } else if (data.type === 'subsystem') {
    // 点击子系统，设置项目和子系统筛选，加载该子系统的关联分类
    filters.project_id = data.project_id;
    subsystems.value = await loadSubsystems(data.project_id);
    filters.subsystem_id = data.id;
    groups.value = await loadGroups(data.id);
  } else if (data.type === 'service_group') {
    // 点击程序分类，设置项目、子系统和分类筛选
    filters.project_id = data.project_id;
    subsystems.value = await loadSubsystems(data.project_id);
    filters.subsystem_id = data.subsystem_id;
    filters.group_id = data.id;
    groups.value = await loadGroups(data.subsystem_id);
  }
  
  pagination.page = 1;
  loadServices();
};

const handleProjectChange = async () => {
  filters.subsystem_id = '';
  filters.group_id = '';
  if (filters.project_id) {
    subsystems.value = await loadSubsystems(filters.project_id);
    groups.value = [];
  } else {
    subsystems.value = [];
    groups.value = [];
  }
  pagination.page = 1;
  loadServices();
};

const handleSubsystemChange = async () => {
  filters.group_id = '';
  groups.value = await loadGroups(filters.subsystem_id);
  pagination.page = 1;
  loadServices();
};

const handleFormProjectChange = async () => {
  formSubsystems.value = await loadSubsystems(serviceForm.project_id, true);
  formGroups.value = [];
  serviceForm.subsystem_id = '';
  serviceForm.group_id = '';
};

const handleFormSubsystemChange = async () => {
  serviceForm.group_id = '';
  formGroups.value = await loadGroups(serviceForm.subsystem_id, true);
};

const updateStatuses = async () => {
  const serviceIds = services.value.map(s => s.id);
  if (serviceIds.length === 0)
    return;
  try {
    const response = await axios.post('/api/services/status/batch', serviceIds);
    if (response.data.code === 0) {
      const statusMap = response.data.data;
      services.value.forEach(service => {
        service.status = statusMap[service.id] || 'UNKNOWN';
      });
    }
  } catch (error) {
    console.error('更新状态失败', error);
  }
};

const resetForm = () => {
  serviceForm.id = null;
  serviceForm.project_id = '';
  serviceForm.subsystem_id = '';
  serviceForm.group_id = '';
  serviceForm.func_desc = '';
  serviceForm.module = '';
  serviceForm.ip = '';
  serviceForm.ssh_port = 22;
  serviceForm.username = '';
  serviceForm.password = '';
  serviceForm.program_path = '';
  serviceForm.start_script = '';
  serviceForm.stop_script = '';
  serviceForm.log_path = '';
  serviceForm.log_type = '';
  serviceForm.port = null;
  serviceForm.service_type = '';
  serviceForm.deploy_type = '';
  serviceForm.instance_name = '';
  serviceForm.container_name = '';
  serviceForm.image_name = '';
  serviceForm.port_mapping = '';
  serviceForm.owner = '';
  serviceForm.remark = '';
  formSubsystems.value = [];
  formGroups.value = [];
};

const resetFilters = () => {
  filters.project_id = '';
  filters.subsystem_id = '';
  filters.group_id = '';
  filters.keyword = '';
  filters.ip = '';
  subsystems.value = [];
  groups.value = [];
  pagination.page = 1;
  loadServices();
};

const viewService = async (service) => {
  try {
    const response = await axios.get(`/api/services/${service.id}`);
    if (response.data.code === 0) {
      Object.assign(selectedService, response.data.data);
      showDetailDialog.value = true;
      // 异步获取状态，不阻塞弹窗显示
      setTimeout(async () => {
        try {
          const statusResponse = await axios.post('/api/services/status/batch', [service.id]);
          if (statusResponse.data.code === 0) {
            selectedService.status = statusResponse.data.data[service.id] || 'UNKNOWN';
          }
        } catch (e) {
          console.error('获取状态失败:', e);
        }
      }, 100);
    } else {
      ElMessage.error('获取服务详情失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '获取服务详情失败');
  }
};

const editService = async (service) => {
  serviceForm.id = service.id;
  serviceForm.project_id = service.project_id;
  serviceForm.subsystem_id = service.subsystem_id;
  serviceForm.group_id = service.group_id;
  serviceForm.func_desc = service.func_desc;
  serviceForm.module = service.module || '';
  serviceForm.ip = service.ip;
  serviceForm.ssh_port = service.ssh_port || 22;
  serviceForm.username = service.username;
  serviceForm.password = '';
  serviceForm.program_path = service.program_path;
  serviceForm.start_script = service.start_script || '';
  serviceForm.stop_script = service.stop_script || '';
  serviceForm.log_path = service.log_path || '';
  serviceForm.port = service.port || null;
  serviceForm.service_type = service.service_type || '';
  serviceForm.deploy_type = service.deploy_type || '';
  serviceForm.instance_name = service.instance_name || '';
  serviceForm.owner = service.owner || '';
  serviceForm.remark = service.remark || '';
  
  formSubsystems.value = await loadSubsystems(service.project_id);
  if (service.subsystem_id) {
    formGroups.value = await loadGroups(service.subsystem_id);
  } else {
    formGroups.value = [];
  }
  showAddDialog.value = true;
};

const saveService = async () => {
  // 防止重复提交
  if (isSubmitting.value) {
    ElMessage.warning('正在提交中，请稍后');
    return;
  }
  
  if (!serviceForm.project_id) {
    ElMessage.error('请选择所属项目');
    return;
  }
  if (!serviceForm.func_desc.trim()) {
    ElMessage.error('请输入功能描述');
    return;
  }
  if (!serviceForm.ip.trim()) {
    ElMessage.error('请输入IP地址');
    return;
  }
  if (!serviceForm.username.trim()) {
    ElMessage.error('请输入SSH用户名');
    return;
  }
  
  // 根据部署方式进行字段验证
  if (serviceForm.deploy_type === 'HOST' || !serviceForm.deploy_type) {
    if (!serviceForm.program_path.trim()) {
      ElMessage.error('请输入程序路径');
      return;
    }
    if (!serviceForm.start_script.trim()) {
      ElMessage.error('请输入启动脚本');
      return;
    }
    if (!serviceForm.stop_script.trim()) {
      ElMessage.error('请输入停止脚本');
      return;
    }
  } else if (serviceForm.deploy_type === 'DOCKER') {
    if (!serviceForm.program_path.trim()) {
      ElMessage.error('请输入程序路径');
      return;
    }
    if (!serviceForm.start_script.trim()) {
      ElMessage.error('请输入启动脚本');
      return;
    }
    if (!serviceForm.stop_script.trim()) {
      ElMessage.error('请输入停止脚本');
      return;
    }
  }
  
  if (!serviceForm.id && !serviceForm.password.trim()) {
    ElMessage.error('请输入密码');
    return;
  }
  
  // 设置提交状态
  isSubmitting.value = true;
  
  try {
    const data = {
      project_id: serviceForm.project_id,
      subsystem_id: serviceForm.subsystem_id || null,
      group_id: serviceForm.group_id || null,
      func_desc: serviceForm.func_desc,
      module: serviceForm.module || null,
      ip: serviceForm.ip,
      ssh_port: serviceForm.ssh_port || 22,
      username: serviceForm.username,
      program_path: serviceForm.program_path || null,
      start_script: serviceForm.start_script || null,
      stop_script: serviceForm.stop_script || null,
      log_path: serviceForm.log_path || null,
      log_type: serviceForm.log_type || null,
      port: serviceForm.port || null,
      service_type: serviceForm.service_type || 'HOST_APP',
      deploy_type: serviceForm.deploy_type || 'HOST',
      instance_name: serviceForm.instance_name || null,
      // Docker相关字段
      container_name: serviceForm.container_name || null,
      image_name: serviceForm.image_name || null,
      port_mapping: serviceForm.port_mapping || null,
      owner: serviceForm.owner || null,
      remark: serviceForm.remark || null
    };
    if (serviceForm.password.trim()) {
      data.password = serviceForm.password;
    }
    let response;
    if (serviceForm.id) {
      response = await axios.put(`/api/services/${serviceForm.id}`, data);
    } else {
      response = await axios.post('/api/services', data);
    }
    if (response.data.code === 0) {
      ElMessage.success(serviceForm.id ? '更新成功' : '新增成功');
      showAddDialog.value = false;
      resetForm();
      loadServices();
    } else {
      ElMessage.error(response.data.message || '操作失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '操作失败');
  } finally {
    // 重置提交状态
    isSubmitting.value = false;
  }
};

const deleteService = async (service) => {
  if (!confirm(`确定要删除服务 "${service.func_desc}" 吗？`))
    return;
  try {
    const response = await axios.delete(`/api/services/${service.id}`);
    if (response.data.code === 0) {
      ElMessage.success('删除成功');
      loadServices();
    } else {
      ElMessage.error(response.data.message || '删除失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '删除失败');
  }
};

const handleSelectionChange = (val) => {
  selectedServices.value = val;
};

const handleSelect = (selection, row) => {
  const currentIndex = services.value.findIndex(s => s.id === row.id);
  if (currentIndex === -1) return;
  
  // 检查当前行是否被选中（selection是选择后的数据）
  const isSelected = selection.some(s => s.id === row.id);
  
  if (!shiftPressed.value) {
    // 非Shift选择，记录当前索引
    if (isSelected) {
      lastSelectedIndex.value = currentIndex;
    } else {
      // 如果取消选中且是唯一选中项，重置索引
      if (selection.length === 0) {
        lastSelectedIndex.value = -1;
      }
    }
    return;
  }
  
  // Shift键按下时进行批量选择
  if (lastSelectedIndex.value === -1) {
    // 如果之前没有选中项，先记录当前索引
    lastSelectedIndex.value = currentIndex;
    return;
  }
  
  const table = serviceTable.value;
  if (!table) return;
  
  // 等待DOM更新后再操作
  nextTick(() => {
    // 清除当前选择（除了当前点击的行）
    table.clearSelection();
    
    // 计算选择范围
    const startIndex = Math.min(lastSelectedIndex.value, currentIndex);
    const endIndex = Math.max(lastSelectedIndex.value, currentIndex);
    
    // 选择范围内的所有行
    for (let i = startIndex; i <= endIndex; i++) {
      table.toggleRowSelection(services.value[i], true);
    }
    
    // 更新最后选中的索引
    lastSelectedIndex.value = currentIndex;
  });
};

const handleKeyDown = (event) => {
  if (event.key === 'Shift') {
    shiftPressed.value = true;
    event.preventDefault();
  }
};

const handleKeyUp = (event) => {
  if (event.key === 'Shift') {
    shiftPressed.value = false;
  }
};

const confirmBatchDelete = async () => {
  if (selectedServices.value.length === 0) {
    ElMessage.warning('请先选择要删除的服务');
    return;
  }
  const count = selectedServices.value.length;
  const names = selectedServices.value.map(s => s.func_desc).join('、');
  if (!confirm(`确定要删除选中的 ${count} 个服务吗？\n\n服务名称：\n${names}`)) {
    return;
  }
  await batchDeleteServices();
};

const batchDeleteServices = async () => {
  const ids = selectedServices.value.map(s => s.id);
  try {
    const response = await axios.post('/api/services/batch/delete', ids);
    if (response.data.code === 0) {
      ElMessage.success(`成功删除 ${response.data.data.deleted} 个服务`);
      selectedServices.value = [];
      loadServices();
    } else {
      ElMessage.error(response.data.message || '批量删除失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '批量删除失败');
  }
};

const startService = async (service) => {
  // 防止重复操作
  if (operatingServices.value.has(service.id)) {
    return;
  }
  operatingServices.value.add(service.id);
  
  try {
    const response = await axios.post(`/api/services/${service.id}/start`);
    if (response.data.code === 0) {
      ElMessage.success(response.data.data.message);
      service.status = 'RUNNING';
    } else {
      ElMessage.error(response.data.data.message || '启动失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '启动失败');
  } finally {
    operatingServices.value.delete(service.id);
  }
};

const stopService = async (service) => {
  // 防止重复操作
  if (operatingServices.value.has(service.id)) {
    return;
  }
  operatingServices.value.add(service.id);
  
  try {
    const response = await axios.post(`/api/services/${service.id}/stop`);
    if (response.data.code === 0) {
      ElMessage.success(response.data.data.message);
      service.status = 'STOPPED';
    } else {
      ElMessage.error(response.data.data.message || '停止失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '停止失败');
  } finally {
    operatingServices.value.delete(service.id);
  }
};

const restartService = async (service) => {
  // 防止重复操作
  if (operatingServices.value.has(service.id)) {
    return;
  }
  operatingServices.value.add(service.id);
  
  try {
    const response = await axios.post(`/api/services/${service.id}/restart`);
    if (response.data.code === 0) {
      ElMessage.success(response.data.data.message);
      service.status = 'RUNNING';
    } else {
      ElMessage.error(response.data.data.message || '重启失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '重启失败');
  } finally {
    operatingServices.value.delete(service.id);
  }
};

const viewLog = async (service) => {
  selectedLogService.value = service;
  showLogDialog.value = true;
  selectedLogFile.value = '';
  await loadLogFileList();
  await loadLog();
};

const loadLogFileList = async () => {
  if (!selectedLogService.value)
    return;
  try {
    const response = await axios.get(`/api/services/${selectedLogService.value.id}/log/files`);
    if (response.data.code === 0) {
      logFiles.value = response.data.data.files || [];
    } else {
      logFiles.value = [];
    }
  } catch (error) {
    logFiles.value = [];
  }
};

const loadLog = async () => {
  if (!selectedLogService.value)
    return;
  try {
    const params = { lines: logLines.value };
    if (selectedLogFile.value) {
      params.filename = selectedLogFile.value;
    }
    const response = await axios.get(`/api/services/${selectedLogService.value.id}/log`, {
      params
    });
    if (response.data.code === 0) {
      logContentText.value = response.data.data.content;
    } else {
      logContentText.value = response.data.message || '获取日志失败';
    }
  } catch (error) {
    logContentText.value = error.response?.data?.message || '获取日志失败';
  }
};

const refreshLog = async () => {
  await loadLog();
};

const downloadLog = async () => {
  if (!selectedLogService.value)
    return;
  try {
    const params = {};
    if (selectedLogFile.value) {
      params.filename = selectedLogFile.value;
    }
    const response = await axios.get(`/api/services/${selectedLogService.value.id}/log/download`, {
      responseType: 'blob',
      params
    });
    const blob = new Blob([response.data], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const filename = selectedLogFile.value || `${selectedLogService.value.func_desc}.log`;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (error) {
    ElMessage.error('下载日志失败');
  }
};

const handleLogClose = () => {
  showLogDialog.value = false;
  logContentText.value = '';
};

const handlePageChange = (page) => {
  pagination.page = page;
  loadServices();
};

const handleSizeChange = (size) => {
  pagination.size = size;
  pagination.page = 1;
  loadServices();
};

const goToImport = () => {
  window.location.href = '/import-services';
};

const downloadTemplate = async () => {
  try {
    const response = await axios.get('/api/services/import/template', { responseType: 'blob' });
    const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '服务导入模板.xlsx';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (error) {
    ElMessage.error('下载模板失败');
  }
};

const exportServices = async () => {
  try {
    const params = new URLSearchParams();
    if (filters.subsystem_id)
      params.append('subsystem_id', filters.subsystem_id);
    if (filters.group_id)
      params.append('group_id', filters.group_id);
    const response = await axios.get(`/api/services/export?${params}`, { responseType: 'blob' });
    const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'services.xlsx';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (error) {
    ElMessage.error('导出失败');
  }
};

const handleFileChange = (file) => {
  importFile.value = file.raw;
};

const doImport = async () => {
  if (!importFile.value) {
    ElMessage.error('请选择要导入的文件');
    return;
  }
  const formData = new FormData();
  formData.append('file', importFile.value);
  // 如果当前有选中的子系统，传递子系统ID
  if (filters.subsystem_id) {
    formData.append('subsystem_id', filters.subsystem_id);
  }
  // 如果当前有选中的程序分类，传递分类ID
  if (filters.group_id) {
    formData.append('group_id', filters.group_id);
  }
  try {
    const response = await axios.post('/api/services/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    if (response.data.code === 0) {
      ElMessage.success(response.data.data.message);
      // 如果有失败的记录，显示详细信息
      if (response.data.data.failed > 0 && response.data.data.failed_items && response.data.data.failed_items.length > 0) {
        const failedDetails = response.data.data.failed_items.map(item => {
          return `${item.sheet || '未知sheet'} - 第${item.row}行: ${item.reason}`;
        }).join('\n');
        ElMessageBox.alert(`导入失败详情:\n\n${failedDetails}`, '导入失败详情', {
          confirmButtonText: '确定',
          type: 'warning'
        });
      }
      showImportDialog.value = false;
      loadServices();
    } else {
      ElMessage.error(response.data.message || '导入失败');
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '导入失败');
  }
};

let websocket = null;

const initTerminal = () => {
  if (terminal) {
    terminal.dispose();
  }
  
  terminal = new Terminal({
    fontSize: 14,
    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
    cursorBlink: true,
    scrollback: 1000,
    convertEol: true,
    disableStdin: false,
    theme: {
      background: '#1e1e1e',
      foreground: '#d4d4d4',
      cursor: '#d4d4d4',
      selection: '#264f78',
      black: '#000000',
      red: '#ff0000',
      green: '#00ff00',
      yellow: '#ffff00',
      blue: '#0000ff',
      magenta: '#ff00ff',
      cyan: '#00ffff',
      white: '#ffffff',
      brightBlack: '#808080',
      brightRed: '#ff0000',
      brightGreen: '#00ff00',
      brightYellow: '#ffff00',
      brightBlue: '#0000ff',
      brightMagenta: '#ff00ff',
      brightCyan: '#00ffff',
      brightWhite: '#ffffff'
    }
  });
  
  fitAddon = new FitAddon();
  terminal.loadAddon(fitAddon);
  
  terminal.open(terminalRef.value);
  
  // 确保终端容器有正确的尺寸和焦点
  setTimeout(() => {
    fitAddon.fit();
    // 直接聚焦到 xterm 的 textarea 输入元素
    const textarea = terminalRef.value?.querySelector('.xterm-helper-textarea');
    if (textarea) {
      textarea.focus();
    }
    terminal.focus();
  }, 200);
  
  terminal.onData((data) => {
    console.log('Terminal onData:', data, 'websocket:', !!websocket, 'connected:', shellConnected.value);
    // 不进行本地回显，让后端bash处理所有输出
    if (websocket && shellConnected.value) {
      websocket.send(data);
      console.log('Sent data to websocket');
    }
  });
  
  terminal.onResize((size) => {
    if (fitAddon) {
      fitAddon.fit();
    }
  });
  
  // 直接为终端容器添加点击事件，确保聚焦到 textarea
  terminalRef.value?.addEventListener('click', () => {
    const textarea = terminalRef.value?.querySelector('.xterm-helper-textarea');
    if (textarea) {
      textarea.focus();
    }
    terminal.focus();
  }, true);
  
  // 窗口resize时重新适配
  window.addEventListener('resize', () => {
    if (fitAddon && terminal) {
      fitAddon.fit();
    }
  });
};

const webShell = (service) => {
  console.log('Opening shell for service:', service);
  currentShellService.value = service;
  shellConnected.value = false;
  showShellDialog.value = true;
  
  // 设置默认远程目录为程序路径，如果没有则使用根目录
  currentRemotePath.value = service.program_path || '/';
  
  setTimeout(() => {
    initTerminal();
    connectShell();
  }, 100);
};

const connectShell = () => {
  if (!currentShellService.value) return;
  
  // 防止重复连接
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    console.log('WebSocket already connected');
    return;
  }
  
  const token = localStorage.getItem('token');
  console.log('Connecting to WebSocket, token:', !!token);
  if (!token) {
    terminal.write('[错误] 未找到认证token，请重新登录\r\n');
    return;
  }
  
  terminal.write('[正在连接服务器...]\r\n');
  
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${window.location.host}/api/shell/ws/${currentShellService.value.id}?token=${token}`;
  console.log('WebSocket URL:', wsUrl);
  websocket = new WebSocket(wsUrl);
  
  websocket.binaryType = 'arraybuffer';
  
  websocket.onopen = () => {
    console.log('WebSocket connected');
    shellConnected.value = true;
    // 连接成功后强制聚焦终端的 textarea 输入元素
    setTimeout(() => {
      if (terminalRef.value) {
        // xterm 使用 textarea 接收输入，直接聚焦到 textarea
        const textarea = terminalRef.value.querySelector('.xterm-helper-textarea');
        if (textarea) {
          textarea.focus();
          console.log('Focused on xterm textarea');
        }
      }
      if (terminal) {
        terminal.focus();
      }
    }, 500);
  };
  
  websocket.onmessage = (event) => {
    console.log('WebSocket received:', event.data);
    if (event.data instanceof ArrayBuffer) {
      terminal.write(new Uint8Array(event.data));
    } else {
      terminal.write(event.data);
    }
  };
  
  websocket.onerror = (error) => {
    console.error('WebSocket error:', error);
    terminal.write('[错误] 连接失败\r\n');
    shellConnected.value = false;
  };
  
  websocket.onclose = (event) => {
    console.log('WebSocket closed:', event.code, event.reason);
    terminal.write(`[断开] 连接已关闭 (Code: ${event.code})\r\n`);
    shellConnected.value = false;
    websocket = null;
  };
};

const disconnectShell = () => {
  if (websocket) {
    websocket.close();
  }
};

const handleShellClose = () => {
  disconnectShell();
  if (terminal) {
    terminal.dispose();
    terminal = null;
  }
  showShellDialog.value = false;
};

const listRemoteFiles = async () => {
  if (!currentShellService.value) return;
  try {
    const response = await axios.get(`/api/sftp/listdir`, {
      params: {
        service_id: currentShellService.value.id,
        path: currentRemotePath.value
      }
    });
    if (response.data.code === 0) {
      remoteFiles.value = response.data.data.files;
    } else {
      ElMessage.error(response.data.message || '获取文件列表失败');
    }
  } catch (error) {
    ElMessage.error('获取文件列表失败');
  }
};

const navigateToDir = (dirName) => {
  let newPath = currentRemotePath.value;
  if (dirName === '..') {
    const parts = currentRemotePath.value.split('/').filter(p => p);
    parts.pop();
    newPath = '/' + parts.join('/');
  } else {
    if (currentRemotePath.value === '/') {
      newPath = '/' + dirName;
    } else {
      newPath += '/' + dirName;
    }
  }
  
  // 更新路径历史
  if (newPath !== currentRemotePath.value) {
    // 清除当前位置之后的历史记录
    pathHistory.value = pathHistory.value.slice(0, pathHistoryIndex.value + 1);
    // 添加新路径
    pathHistory.value.push(newPath);
    pathHistoryIndex.value = pathHistory.value.length - 1;
    currentRemotePath.value = newPath;
    listRemoteFiles();
  }
};

const goBack = () => {
  if (pathHistoryIndex.value > 0) {
    pathHistoryIndex.value--;
    currentRemotePath.value = pathHistory.value[pathHistoryIndex.value];
    listRemoteFiles();
  }
};

const goForward = () => {
  if (pathHistoryIndex.value < pathHistory.value.length - 1) {
    pathHistoryIndex.value++;
    currentRemotePath.value = pathHistory.value[pathHistoryIndex.value];
    listRemoteFiles();
  }
};

const downloadRemoteFile = async (fileName) => {
  if (!currentShellService.value) return;
  const fullPath = currentRemotePath.value === '/' ? '/' + fileName : currentRemotePath.value + '/' + fileName;
  try {
    const response = await axios.get(`/api/sftp/download`, {
      params: {
        service_id: currentShellService.value.id,
        remote_path: fullPath
      },
      responseType: 'blob'
    });
    const blob = new Blob([response.data]);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (error) {
    ElMessage.error('下载文件失败');
  }
};

const deleteRemoteFile = async (fileName) => {
  if (!currentShellService.value) return;
  
  ElMessageBox.confirm(
    `确定要删除 "${fileName}" 吗？此操作无法撤销。`,
    '确认删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    const fullPath = currentRemotePath.value === '/' ? '/' + fileName : currentRemotePath.value + '/' + fileName;
    try {
      await axios.delete(`/api/sftp/delete`, {
        params: {
          service_id: currentShellService.value.id,
          remote_path: fullPath
        }
      });
      ElMessage.success('删除成功');
      listRemoteFiles();
    } catch (error) {
      ElMessage.error('删除失败');
    }
  }).catch(() => {
    ElMessage.info('已取消删除');
  });
};

const showContextMenu = (event, row, column, cell) => {
  // 阻止浏览器默认右键菜单
  event.preventDefault();
  event.stopPropagation();
  
  // 只有在行数据存在时才显示菜单
  if (!row || typeof row !== 'object') {
    return;
  }
  
  contextMenuFile.value = row;
  contextMenuPosition.value = { x: event.clientX, y: event.clientY };
  contextMenuVisible.value = true;
  
  // 点击其他地方关闭菜单
  document.addEventListener('click', closeContextMenu);
  document.addEventListener('contextmenu', closeContextMenu);
};

const showContextMenuDirect = (event, row) => {
  // 直接处理右键菜单 - 支持 el-table 的 @row-contextmenu 事件
  event.preventDefault();
  event.stopPropagation();
  
  // 检查 row 是否有效
  if (!row || typeof row !== 'object' || !row.filename) {
    return;
  }
  
  contextMenuFile.value = row;
  contextMenuPosition.value = { x: event.clientX, y: event.clientY };
  contextMenuVisible.value = true;
  
  document.addEventListener('click', closeContextMenu);
  document.addEventListener('contextmenu', closeContextMenu);
};

const handleTableRowContextMenu = (event, row) => {
  // 处理表格行右键菜单
  // event 是原生事件对象
  const nativeEvent = event;
  
  // 阻止浏览器默认右键菜单
  nativeEvent.preventDefault();
  nativeEvent.stopPropagation();
  
  // 检查 row 是否有效
  if (!row || typeof row !== 'object' || !row.filename) {
    return;
  }
  
  contextMenuFile.value = row;
  contextMenuPosition.value = { x: nativeEvent.clientX, y: nativeEvent.clientY };
  contextMenuVisible.value = true;
  
  document.addEventListener('click', closeContextMenu);
  document.addEventListener('contextmenu', closeContextMenu);
};

const handleTableRowContextMenuNative = (event) => {
  // 使用原生事件处理右键菜单
  event.preventDefault();
  event.stopPropagation();
  
  // 通过点击位置查找对应的表格行
  let target = event.target;
  let rowElement = null;
  
  // 向上查找表格行
  while (target && !rowElement) {
    if (target.tagName === 'TR') {
      rowElement = target;
    } else {
      target = target.parentElement;
    }
  }
  
  // 如果找到了行，获取行索引
  if (rowElement) {
    const table = rowElement.parentElement.parentElement;
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    const rowIndex = rows.indexOf(rowElement);
    
    // 获取对应的数据
    if (rowIndex >= 0 && rowIndex < remoteFiles.value.length) {
      const rowData = remoteFiles.value[rowIndex];
      
      contextMenuFile.value = rowData;
      contextMenuPosition.value = { x: event.clientX, y: event.clientY };
      contextMenuVisible.value = true;
      
      document.addEventListener('click', closeContextMenu);
      document.addEventListener('contextmenu', closeContextMenu);
    }
  }
};

const handleTableRowContextMenuElement = (row, event) => {
  // Element Plus @row-contextmenu 事件处理
  // 参数顺序: (row, event)
  // 阻止浏览器默认右键菜单
  event.preventDefault();
  event.stopPropagation();
  
  // 检查 row 是否有效
  if (!row || typeof row !== 'object' || !row.filename) {
    return;
  }
  
  contextMenuFile.value = row;
  contextMenuPosition.value = { x: event.clientX, y: event.clientY };
  contextMenuVisible.value = true;
  
  document.addEventListener('click', closeContextMenu);
  document.addEventListener('contextmenu', closeContextMenu);
};

const handleTableRowContextMenuFinal = (arg1, arg2) => {
  // 处理右键菜单 - 自动识别参数顺序
  let event, row;
  
  // 判断哪个是事件对象，哪个是行数据
  if (arg1 && arg1.preventDefault) {
    // arg1 是事件对象
    event = arg1;
    row = arg2;
  } else if (arg2 && arg2.preventDefault) {
    // arg2 是事件对象
    event = arg2;
    row = arg1;
  } else {
    // 无法识别，尝试使用第一个作为行数据
    row = arg1;
    event = arg2 || { clientX: 0, clientY: 0, preventDefault: () => {}, stopPropagation: () => {} };
  }
  
  // 阻止浏览器默认右键菜单
  event.preventDefault();
  event.stopPropagation();
  
  // 检查 row 是否有效
  if (!row || typeof row !== 'object' || !row.filename) {
    return;
  }
  
  contextMenuFile.value = row;
  contextMenuPosition.value = { x: event.clientX, y: event.clientY };
  contextMenuVisible.value = true;
  
  document.addEventListener('click', closeContextMenu);
  document.addEventListener('contextmenu', closeContextMenu);
};

const handlePanelContextMenu = (event) => {
  // 点击面板空白处关闭菜单
  if (contextMenuVisible.value) {
    closeContextMenu();
  }
};

const handlePanelContextMenuNew = (event) => {
  // 处理面板上的右键菜单 - 直接绑定到容器
  event.preventDefault();
  event.stopPropagation();
  
  // 通过点击位置查找对应的表格行
  let target = event.target;
  let rowElement = null;
  
  // 向上查找表格行
  while (target && !rowElement) {
    if (target.tagName === 'TR' || target.classList.contains('el-table__row')) {
      rowElement = target;
    } else {
      target = target.parentElement;
    }
  }
  
  // 如果找到了行，获取行索引
  if (rowElement) {
    // 查找 tbody 中的所有行
    const tbody = rowElement.closest('tbody');
    if (tbody) {
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const rowIndex = rows.indexOf(rowElement);
      
      // 获取对应的数据
      if (rowIndex >= 0 && rowIndex < remoteFiles.value.length) {
        const rowData = remoteFiles.value[rowIndex];
        
        contextMenuFile.value = rowData;
        contextMenuPosition.value = { x: event.clientX, y: event.clientY };
        contextMenuVisible.value = true;
        
        document.addEventListener('click', closeContextMenu);
        document.addEventListener('contextmenu', closeContextMenu);
        return;
      }
    }
  }
  
  // 如果没有找到行数据，关闭菜单
  closeContextMenu();
};

const closeContextMenu = () => {
  contextMenuVisible.value = false;
  document.removeEventListener('click', closeContextMenu);
  document.removeEventListener('contextmenu', closeContextMenu);
};

const handleContextMenuRename = () => {
  if (contextMenuFile.value && contextMenuFile.value.filename !== '..') {
    const newName = prompt('请输入新文件名:', contextMenuFile.value.filename);
    if (newName && newName.trim() && newName !== contextMenuFile.value.filename) {
      renameRemoteFile(contextMenuFile.value.filename, newName.trim());
    }
  }
  closeContextMenu();
};

const handleContextMenuCopy = () => {
  if (contextMenuFile.value) {
    const fullPath = currentRemotePath.value === '/' 
      ? '/' + contextMenuFile.value.filename 
      : currentRemotePath.value + '/' + contextMenuFile.value.filename;
    
    // 降级方案：直接使用 textarea 方法，兼容性更好
    const textarea = document.createElement('textarea');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.value = fullPath;
    document.body.appendChild(textarea);
    textarea.select();
    
    try {
      const successful = document.execCommand('copy');
      if (successful) {
        ElMessage.success('路径已复制到剪贴板');
      } else {
        ElMessage.error('复制失败，请手动复制');
      }
    } catch (err) {
      ElMessage.error('复制失败，请手动复制');
    }
    
    document.body.removeChild(textarea);
  }
  closeContextMenu();
};

const renameRemoteFile = async (oldName, newName) => {
  if (!currentShellService.value) return;
  const oldPath = currentRemotePath.value === '/' ? '/' + oldName : currentRemotePath.value + '/' + oldName;
  const newPath = currentRemotePath.value === '/' ? '/' + newName : currentRemotePath.value + '/' + newName;
  
  try {
    await axios.post(`/api/sftp/rename`, null, {
      params: {
        service_id: currentShellService.value.id,
        old_path: oldPath,
        new_path: newPath
      }
    });
    ElMessage.success('重命名成功');
    listRemoteFiles();
  } catch (error) {
    ElMessage.error('重命名失败');
  }
};

const handleContextMenuDownload = () => {
  if (contextMenuFile.value) {
    downloadRemoteFile(contextMenuFile.value.filename);
  }
  closeContextMenu();
};

const handleContextMenuDelete = () => {
  if (contextMenuFile.value) {
    deleteRemoteFile(contextMenuFile.value.filename);
  }
  closeContextMenu();
};

const createRemoteDir = async () => {
  if (!currentShellService.value) return;
  const dirName = prompt('请输入新文件夹名称:');
  if (!dirName) return;
  const fullPath = currentRemotePath.value === '/' ? '/' + dirName : currentRemotePath.value + '/' + dirName;
  try {
    await axios.post(`/api/sftp/mkdir`, null, {
      params: {
        service_id: currentShellService.value.id,
        remote_path: fullPath
      }
    });
    ElMessage.success('创建成功');
    listRemoteFiles();
  } catch (error) {
    ElMessage.error('创建失败');
  }
};

const triggerFileUpload = () => {
  uploadFileInput.value?.click();
};

const triggerDirUpload = () => {
  uploadDirInput.value?.click();
};

const handleFileUpload = (event) => {
  const files = event.target.files;
  if (!files || files.length === 0) return;
  
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    localFiles.value.push({
      name: file.name,
      size: file.size,
      file: file,
      relativePath: file.name
    });
  }
  
  event.target.value = '';
};

const handleDirUpload = (event) => {
  const files = event.target.files;
  if (!files || files.length === 0) return;
  
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    // 获取相对路径，用于保持目录结构
    const relativePath = file.webkitRelativePath || file.name;
    localFiles.value.push({
      name: file.name,
      size: file.size,
      file: file,
      relativePath: relativePath
    });
  }
  
  event.target.value = '';
};

const handleDrop = (event) => {
  const files = event.dataTransfer.files;
  if (!files || files.length === 0) return;
  
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    // 获取相对路径，用于保持目录结构
    const relativePath = file.webkitRelativePath || file.name;
    localFiles.value.push({
      name: file.name,
      size: file.size,
      file: file,
      relativePath: relativePath
    });
  }
  
  ElMessage.success(`已添加 ${files.length} 个文件`);
};

const removeLocalFile = (index) => {
  localFiles.value.splice(index, 1);
};

const uploadAllFiles = async () => {
  if (!currentShellService.value) return;
  if (localFiles.value.length === 0) return;
  
  uploadingAll.value = true;
  let successCount = 0;
  let failCount = 0;
  
  // 重置覆盖选项
  resetOverwriteOption();
  
  // 创建文件列表副本，避免循环过程中数组被修改导致索引错乱
  const filesToUpload = [...localFiles.value];
  
  for (let i = 0; i < filesToUpload.length; i++) {
    const fileInfo = filesToUpload[i];
    try {
      await uploadSelectedFile(fileInfo);
      successCount++;
    } catch (error) {
      // 如果是用户取消上传，立即停止整个流程
      if (error.code === 'UPLOAD_CANCELLED') {
        ElMessage.info('用户取消上传');
        uploadingAll.value = false;
        resetOverwriteOption();
        return;
      }
      failCount++;
    }
  }
  
  uploadingAll.value = false;
  
  // 重置覆盖选项
  resetOverwriteOption();
  
  if (failCount === 0) {
    ElMessage.success(`全部上传完成！共上传 ${successCount} 个文件`);
    localFiles.value = [];
  } else {
    ElMessage.warning(`上传完成！成功 ${successCount} 个，失败 ${failCount} 个`);
  }
};

const uploadSelectedFile = async (fileInfo) => {
  if (!currentShellService.value) return;
  if (!fileInfo.file) return;
  
  const formData = new FormData();
  formData.append('file', fileInfo.file);
  
  // 计算远程路径（保持目录结构）
  let remoteFilePath = currentRemotePath.value;
  
  if (fileInfo.relativePath && fileInfo.relativePath !== fileInfo.name) {
    // 获取目录部分（去掉文件名）
    const dirPath = fileInfo.relativePath.substring(0, fileInfo.relativePath.lastIndexOf('/'));
    remoteFilePath = remoteFilePath.replace(/\/$/, '') + '/' + dirPath;
  }
  
  // 构建完整的远程文件路径
  const fullRemotePath = remoteFilePath.replace(/\/$/, '') + '/' + fileInfo.name;
  
  // 检查文件是否存在
  try {
    const response = await axios.get(`/api/sftp/exists`, {
      params: {
        service_id: currentShellService.value.id,
        path: fullRemotePath
      }
    });
    
    if (response.data?.code === 0 && response.data?.data?.exists) {
      // 文件已存在，需要确认如何处理
      if (overwriteOption.value === 'overwrite_all') {
        // 自动覆盖所有，不提示
      } else if (overwriteOption.value === 'skip_all') {
        // 自动跳过所有
        ElMessage.info(`跳过文件 ${fileInfo.name}`);
        return;
      } else {
        // 弹出 Element Plus 确认对话框
        const action = await showOverwriteDialog(fileInfo.name);
        
        if (action === 'skip' || action === 'skip_all') {
          ElMessage.info(`跳过文件 ${fileInfo.name}`);
          return;
        } else if (action === 'cancel') {
          // 用户取消上传，抛出特殊错误以停止整个上传流程
          const error = new Error('用户取消上传');
          error.code = 'UPLOAD_CANCELLED';
          throw error;
        }
        // overwrite 或 overwrite_all 继续上传
      }
    }
  } catch (error) {
    // 如果是用户取消上传，重新抛出错误让外层处理
    if (error.code === 'UPLOAD_CANCELLED') {
      throw error;
    }
    // 其他错误（检查失败），继续上传
  }
  
  try {
    await axios.post(`/api/sftp/upload`, formData, {
      params: {
        service_id: currentShellService.value.id,
        remote_path: remoteFilePath,
        preserve_path: fileInfo.relativePath !== fileInfo.name ? 'true' : 'false'
      },
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    ElMessage.success(`文件 ${fileInfo.name} 上传成功`);
    listRemoteFiles();
    const index = localFiles.value.findIndex(f => f.name === fileInfo.name && f.size === fileInfo.size);
    if (index > -1) {
      localFiles.value.splice(index, 1);
    }
  } catch (error) {
    ElMessage.error(`文件 ${fileInfo.name} 上传失败`);
  }
};

const resetOverwriteOption = () => {
  overwriteOption.value = '';
};

const handleOverwriteConfirm = () => {
  // 覆盖当前文件
  if (overwriteAllSelected.value) {
    // 用户勾选了"全部应用"，设置全局覆盖选项
    overwriteOption.value = 'overwrite_all';
    if (overwriteResolve.value) {
      overwriteResolve.value('overwrite_all');
      overwriteResolve.value = null;
    }
  } else {
    // 用户没有勾选"全部应用"，只覆盖当前文件
    if (overwriteResolve.value) {
      overwriteResolve.value('overwrite');
      overwriteResolve.value = null;
    }
  }
  overwriteDialogVisible.value = false;
};

const handleOverwriteSkip = () => {
  // 跳过当前文件
  if (overwriteAllSelected.value) {
    // 用户勾选了"全部应用"，设置全局跳过选项
    overwriteOption.value = 'skip_all';
    if (overwriteResolve.value) {
      overwriteResolve.value('skip_all');
      overwriteResolve.value = null;
    }
  } else {
    // 用户没有勾选"全部应用"，只跳过当前文件
    if (overwriteResolve.value) {
      overwriteResolve.value('skip');
      overwriteResolve.value = null;
    }
  }
  overwriteDialogVisible.value = false;
};

const handleOverwriteCancel = () => {
  // 取消上传
  if (overwriteResolve.value) {
    overwriteResolve.value('cancel');
    overwriteResolve.value = null;
  }
  overwriteDialogVisible.value = false;
};

const handleOverwriteDialogClose = (done) => {
  // 对话框关闭前的处理（点击右上角关闭按钮时触发）
  if (overwriteResolve.value) {
    overwriteResolve.value('cancel');
    overwriteResolve.value = null;
  }
  done(); // 关闭对话框
};

const showOverwriteDialog = (filename) => {
  return new Promise((resolve) => {
    overwriteDialogFile.value = filename;
    overwriteAllSelected.value = false;
    overwriteResolve.value = resolve;
    overwriteDialogVisible.value = true;
  });
};

const showOverwriteDialogSimple = (filename) => {
  return new Promise((resolve) => {
    const action = window.confirm(`文件 "${filename}" 已存在，是否覆盖？`);
    if (action) {
      const applyAll = window.confirm('是否应用到所有后续同名文件？');
      if (applyAll) {
        overwriteOption.value = 'overwrite_all';
        resolve('overwrite_all');
      } else {
        resolve('overwrite');
      }
    } else {
      const applyAll = window.confirm('是否跳过所有后续同名文件？');
      if (applyAll) {
        overwriteOption.value = 'skip_all';
        resolve('skip_all');
      } else {
        resolve('skip');
      }
    }
  });
};

const formatFileSize = (size) => {
  if (size < 1024) return size + ' B';
  if (size < 1024 * 1024) return (size / 1024).toFixed(2) + ' KB';
  if (size < 1024 * 1024 * 1024) return (size / (1024 * 1024)).toFixed(2) + ' MB';
  return (size / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
};

const formatTime = (timestamp) => {
  const date = new Date(timestamp * 1000);
  return date.toLocaleString('zh-CN');
};

const getDeployType = (type) => {
  const types = {
    'HOST': { label: '主机部署', type: 'primary' },
    'DOCKER': { label: 'Docker部署', type: 'success' },
    'CLUSTER': { label: '集群部署', type: 'warning' },
  };
  return types[type] || { label: type || '未知', type: 'info' };
};

const getServiceType = (type) => {
  const types = {
    'HOST_APP': { label: '主机应用', type: 'primary' },
    'DOCKER': { label: 'Docker容器', type: 'success' },
    'ES': { label: 'Elasticsearch', type: 'warning' },
    'SOLR': { label: 'Solr', type: 'warning' },
    'REDIS': { label: 'Redis', type: 'danger' },
    'MYSQL': { label: 'MySQL', type: 'info' },
    'POSTGRESQL': { label: 'PostgreSQL', type: 'info' },
    'KAFKA': { label: 'Kafka', type: 'purple' },
    'ROCKETMQ': { label: 'RocketMQ', type: 'purple' },
    'RABBITMQ': { label: 'RabbitMQ', type: 'purple' },
    'NGINX': { label: 'Nginx', type: 'primary' },
    'AI_MODEL': { label: 'AI模型', type: 'danger' },
  };
  return types[type] || { label: type || '未知', type: 'info' };
};

onMounted(() => {
  loadServices();
  loadProjects();
  statusInterval = setInterval(updateStatuses, 10000);
  window.addEventListener('keydown', handleKeyDown);
  window.addEventListener('keyup', handleKeyUp);
});

onUnmounted(() => {
  if (statusInterval) {
    clearInterval(statusInterval);
  }
  window.removeEventListener('keydown', handleKeyDown);
  window.removeEventListener('keyup', handleKeyUp);
});
</script>

<style scoped>
.services-page-new {
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
}

.page-layout {
  display: flex;
  height: 100%;
  gap: 20px;
  padding: 20px;
}

.left-panel {
  width: 280px;
  flex-shrink: 0;
}

.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
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

.project-select, .subsystem-select, .group-select {
  width: 180px;
}

.search-input {
  width: 250px;
}

.ip-input {
  width: 150px;
}

.table-wrapper {
  flex: 1;
  overflow-y: auto;
}

.el-table {
  height: calc(100% - 20px);
}

.import-tip {
  color: #999;
  margin-top: 10px;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.log-content {
  max-height: 500px;
  overflow-y: auto;
  background: #1a1a1a;
  padding: 15px;
  border-radius: 4px;
}

.log-content pre {
  color: #e4e4e4;
  font-family: monospace;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
}

.el-descriptions__label {
  font-weight: bold;
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

  &.disabled {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
  }
}

.view-btn {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
}

.edit-btn {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
}

.delete-btn {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.log-btn {
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
}

.start-btn {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
}

.stop-btn {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.restart-btn {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}

.login-btn {
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
}

.shell-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
  flex-wrap: wrap;
}

.shell-container {
  background: #1e1e1e;
  border-radius: 8px;
  padding: 10px;
  height: 500px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.terminal-container {
  flex: 1;
  width: 100%;
  height: 100%;
  min-height: 400px;
}

.terminal-container:focus {
  outline: none;
}

.shell-output {
  flex: 1;
  overflow-y: auto;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 14px;
  color: #e5e7eb;
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.5;
}

.shell-output .command {
  color: #a78bfa;
}

.shell-input-wrapper {
  display: flex;
  align-items: center;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #374151;
}

.shell-prompt {
  color: #10b981;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 14px;
  margin-right: 5px;
}

.shell-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #e5e7eb;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 14px;
}

.shell-input::placeholder {
  color: #6b7280;
}

.shell-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.connected-tag {
  background: #d1fae5;
  color: #065f46;
  border: none;
}

.disconnected-tag {
  background: #fee2e2;
  color: #991b1b;
  border: none;
}

.file-manager {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.file-manager-panels {
  display: flex;
  height: 100%;
}

.file-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid #e5e5e5;
}

.local-panel {
  border-right: none;
}

.remote-panel {
  border-left: none;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f5f5f5;
  border-bottom: 1px solid #e5e5e5;
}

.panel-title {
  font-weight: 600;
  font-size: 14px;
}

.path-input {
  flex: 1;
  max-width: 200px;
}

.upload-input {
  display: none;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
}

.file-table {
  height: 100%;
}

.dir-icon, .file-icon {
  margin-right: 6px;
}

.file-table .el-table__row {
  cursor: pointer;
}

.file-table .el-table__row:hover {
  background-color: #f9fafb;
}

.panel-divider {
  width: 6px;
  background-color: #e5e5e5;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
}

.divider-line {
  width: 2px;
  height: 30px;
  background-color: #ccc;
  border-radius: 1px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
}

.drop-zone {
  padding: 15px;
  border-top: 1px dashed #ccc;
  text-align: center;
  color: #999;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s;
}

.drop-zone:hover {
  background-color: #f9fafb;
  color: #666;
}

.dir-clickable {
  cursor: pointer;
  color: #409eff;
  text-decoration: underline;
}

.dir-clickable:hover {
  color: #67c23a;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 1;
}

.header-actions .path-input {
  flex: 1;
  min-width: 200px;
}

.context-menu {
  position: fixed;
  z-index: 9999;
  min-width: 120px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  padding: 5px 0;
}

.context-menu .el-menu-item {
  padding: 8px 20px;
  font-size: 14px;
  color: #606266;
  cursor: pointer;
}

.context-menu .el-menu-item:hover {
  background-color: #f5f7fa;
  color: #409eff;
}
</style>