<template>
  <div class="agents-page">
    <div class="page-header">
      <h1>Agent 管理</h1>
      <div class="actions">
        <el-button v-if="hasPermission('agent:manage')" type="success" @click="batchControl('start')" :disabled="!selectedAgents.length">
          批量启动 ({{ selectedAgents.length }})
        </el-button>
        <el-button v-if="hasPermission('agent:manage')" type="warning" @click="batchControl('restart')" :disabled="!selectedAgents.length">
          批量重启 ({{ selectedAgents.length }})
        </el-button>
        <el-button v-if="hasPermission('agent:manage')" type="danger" @click="batchControl('stop')" :disabled="!selectedAgents.length">
          批量停止 ({{ selectedAgents.length }})
        </el-button>
        <el-button v-if="hasPermission('agent:manage')" type="primary" plain @click="openUpdateDialog">
          批量更新
        </el-button>
        <el-button v-if="hasPermission('agent:manage')" type="primary" plain @click="openDeployDialog">
          批量装机
        </el-button>
        <el-dropdown v-if="hasPermission('agent:manage')" @command="handleTaskMenu">
          <el-button>
            任务记录<el-icon class="el-icon--right"><arrow-down /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="update">批量更新任务</el-dropdown-item>
              <el-dropdown-item command="deploy">批量装机任务</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="primary" @click="loadAgents">刷新</el-button>
      </div>
    </div>

    <div class="search-bar">
      <el-input v-model="searchKeyword" placeholder="搜索主机名或IP" class="search-input" @keyup.enter="loadAgents" />
      <el-select v-model="statusFilter" placeholder="状态筛选" clearable class="status-select">
        <el-option label="在线" value="online" />
        <el-option label="离线" value="offline" />
      </el-select>
      <el-button type="primary" @click="loadAgents">搜索</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <div class="table-wrapper">
      <el-table 
        :data="agents" 
        border 
        fit 
        :header-cell-style="{ 'white-space': 'nowrap' }"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="hostname" label="主机名" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP地址" width="130" show-overflow-tooltip />
        <el-table-column prop="uuid" label="UUID" width="260" show-overflow-tooltip>
          <template #default="scope">
            <span style="font-family: monospace; font-size: 12px;">{{ scope.row.uuid }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="scope">
            <el-tag :type="scope.row.is_online ? 'success' : 'danger'">
              {{ scope.row.is_online ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="部署方式" width="110">
          <template #default="scope">
            <el-tag :type="deployModeTag(scope.row.deploy_types, scope.row.deploy_type)" size="small">{{ deployModeLabel(scope.row.deploy_types, scope.row.deploy_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="CPU" width="75">
          <template #default="scope">
            <span>{{ formatPercent(scope.row.metrics?.cpu_percent) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="内存" width="75">
          <template #default="scope">
            <span>{{ formatPercent(scope.row.metrics?.memory_percent) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="磁盘" width="75">
          <template #default="scope">
            <span>{{ formatPercent(scope.row.metrics?.disk_percent) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Load" width="75">
          <template #default="scope">
            <span>{{ formatLoad(scope.row.metrics?.load1) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="系统" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ scope.row.os || '--' }} ({{ scope.row.cpu_cores || 0 }}核)</span>
          </template>
        </el-table-column>
        <el-table-column label="内存总量" width="95" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ formatMemory(scope.row.memory_total) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Agent版本" width="100" show-overflow-tooltip>
          <template #default="scope">
            <span>v{{ scope.row.agent_version || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最后心跳" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ formatDateTime(scope.row.last_heartbeat) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" align="center">
          <template #default="scope">
            <div class="action-buttons">
              <div class="action-btn view-btn" @click="viewAgent(scope.row)">
                <span>详情</span>
              </div>
              <div class="action-btn edit-btn" @click="viewAgentServices(scope.row)">
                <span>服务</span>
              </div>
              <div v-if="hasPermission('agent:manage')" class="action-btn start-btn" @click="controlAgent(scope.row, 'start')">
                <span>启动</span>
              </div>
              <div v-if="hasPermission('agent:manage')" class="action-btn restart-btn" @click="controlAgent(scope.row, 'restart')">
                <span>重启</span>
              </div>
              <div v-if="hasPermission('agent:manage')" class="action-btn stop-btn" @click="controlAgent(scope.row, 'stop')">
                <span>停止</span>
              </div>
              <div v-if="hasPermission('agent:manage')" class="action-btn config-btn" @click="openConfigDialog(scope.row)">
                <span>配置</span>
              </div>
              <div v-if="hasPermission('agent:manage')" class="action-btn delete-btn" @click="deleteAgent(scope.row)">
                <span>删除</span>
              </div>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog title="Agent 详情" v-model="showDetailDialog" width="600px">
      <div v-if="selectedAgent" class="agent-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="主机名">{{ selectedAgent.hostname }}</el-descriptions-item>
          <el-descriptions-item label="IP地址">{{ selectedAgent.ip }}</el-descriptions-item>
          <el-descriptions-item label="操作系统">{{ selectedAgent.os }}</el-descriptions-item>
          <el-descriptions-item label="内核版本">{{ selectedAgent.kernel }}</el-descriptions-item>
          <el-descriptions-item label="架构">{{ selectedAgent.arch }}</el-descriptions-item>
          <el-descriptions-item label="CPU型号">{{ selectedAgent.cpu_model }}</el-descriptions-item>
          <el-descriptions-item label="CPU核心">{{ selectedAgent.cpu_cores }}</el-descriptions-item>
          <el-descriptions-item label="内存总量">{{ formatMemory(selectedAgent.memory_total) }}</el-descriptions-item>
          <el-descriptions-item label="Agent版本">{{ selectedAgent.agent_version }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="selectedAgent.is_online ? 'success' : 'danger'">
              {{ selectedAgent.is_online ? '在线' : '离线' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="最后心跳" :span="2">
            {{ selectedAgent.last_heartbeat ? formatDateTime(selectedAgent.last_heartbeat) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="UUID" :span="2">{{ selectedAgent.uuid }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="selectedAgent.capabilities && selectedAgent.capabilities.length > 0" style="margin-top: 20px;">
          <h4>能力列表</h4>
          <div class="capabilities">
            <el-tag v-for="cap in selectedAgent.capabilities" :key="cap" size="small">{{ cap }}</el-tag>
          </div>
        </div>
        <div v-if="selectedAgent.tags && selectedAgent.tags.length > 0" style="margin-top: 10px;">
          <h4>标签</h4>
          <div class="tags">
            <el-tag v-for="tag in selectedAgent.tags" :key="tag" size="small" type="info">{{ tag }}</el-tag>
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog title="Agent 服务列表" v-model="showServicesDialog" width="800px">
      <div v-if="agentServices.length > 0">
        <el-table :data="agentServices" border>
          <el-table-column type="index" label="序号" width="80" />
          <el-table-column prop="name" label="服务名称" min-width="150" />
          <el-table-column prop="deploy_type" label="部署方式" min-width="120">
            <template #default="scope">
              <el-tag :type="getDeployType(scope.row.deploy_type).type">
                {{ getDeployType(scope.row.deploy_type).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="port" label="端口" width="100" />
          <el-table-column prop="docker_name" label="容器名称" min-width="150" />
        </el-table>
      </div>
      <div v-else style="text-align: center; padding: 40px;">
        <p>该 Agent 暂无关联服务</p>
      </div>
    </el-dialog>

    <el-dialog title="Agent 控制配置" v-model="showConfigDialog" width="500px">
      <el-form :model="configForm" label-width="120px" style="padding: 10px;">
        <el-form-item label="主机名">
          <span>{{ configForm.hostname }}</span>
        </el-form-item>
        <el-form-item label="IP地址">
          <span>{{ configForm.ip }}</span>
        </el-form-item>
        <el-form-item label="SSH端口">
          <el-input v-model="configForm.ssh_port" type="number" placeholder="默认 22" />
        </el-form-item>
        <el-form-item label="SSH用户名">
          <el-input v-model="configForm.ssh_username" placeholder="请输入 SSH 用户名" />
        </el-form-item>
        <el-form-item label="SSH密码">
          <el-input v-model="configForm.ssh_password" type="password" placeholder="请输入 SSH 密码" show-password />
        </el-form-item>
        <el-form-item label="服务名">
          <el-input v-model="configForm.service_name" placeholder="默认 srmc-agent" />
        </el-form-item>
        <div v-if="configForm.ssh_username" style="margin-top: 10px; padding: 10px; background: #f5f7fa; border-radius: 4px;">
          <el-tag type="success" size="small">✓ 已配置 SSH 凭据</el-tag>
          <span style="margin-left: 10px; font-size: 13px; color: #606266;">可通过 SSH 远程控制该 Agent</span>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="showConfigDialog = false">取消</el-button>
        <el-button type="primary" @click="saveConfig">保存配置</el-button>
      </template>
    </el-dialog>

    <!-- ===== 批量更新弹窗 ===== -->
    <el-dialog title="Agent 批量更新" v-model="showUpdateDialog" width="800px" @closed="resetUpdateForm">
      <el-form :model="updateForm" label-width="160px">
        <el-form-item label="更新类型">
          <el-radio-group v-model="updateForm.update_type">
            <el-radio label="docker">Docker 镜像</el-radio>
            <el-radio label="binary">二进制文件</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="目标 Agent">
          <div style="width: 100%;">
            <div style="margin-bottom: 6px;">
              <el-button size="small" @click="selectFilteredAgents">全选</el-button>
              <el-button size="small" @click="updateTargetUuids = []">清空</el-button>
              <span style="font-size: 12px; color: #909399; margin-left: 8px;">
                匹配 {{ filteredAgents.length }} / 全部 {{ allAgents.length }} 台
              </span>
            </div>
            <el-select v-model="updateTargetUuids" multiple filterable placeholder="选择目标 Agent" style="width: 100%;">
              <el-option v-for="a in filteredAgents" :key="a.uuid" :label="`${a.hostname} (${a.ip})`" :value="a.uuid">
                <span>{{ a.hostname }} ({{ a.ip }})</span>
                <span style="float: right;"><el-tag :type="deployModeTag(a.deploy_types)" size="small">{{ deployModeLabel(a.deploy_types) }}</el-tag></span>
              </el-option>
            </el-select>
            <el-alert v-if="!filteredAgents.length" type="warning" :closable="false" style="margin-top: 6px;">
              当前没有与「{{ updateForm.update_type === 'docker' ? 'Docker 镜像' : '二进制文件' }}」匹配的 Agent。
            </el-alert>
            <div v-if="updateTargetUuids.length" style="font-size: 12px; color: #909399; margin-top: 6px; word-break: break-all;">
              已选 {{ updateTargetUuids.length }} 台：{{ targetAgentNames }}
            </div>
          </div>
        </el-form-item>

        <el-form-item label="更新文件">
          <div style="width: 100%;">
            <input ref="fileInputRef" type="file" style="display: none;" @change="handleFileSelect" />
            <el-button @click="fileInputRef?.click()" :disabled="uploading">选择文件并上传</el-button>
            <div v-if="uploadMeta.file_name" style="margin-top: 8px; font-size: 13px;">
              {{ uploadMeta.file_name }}（{{ formatBytes(uploadMeta.file_size) }}）
            </div>
            <div v-if="uploadMeta.file_sha256" style="font-size: 12px; color: #909399; word-break: break-all; margin-top: 4px;">
              SHA256: {{ uploadMeta.file_sha256 }}
            </div>
            <el-progress v-if="uploading || uploadProgress === 100" :percentage="uploadProgress" style="margin-top: 8px;" />
          </div>
        </el-form-item>

        <template v-if="updateForm.update_type === 'docker'">
          <el-form-item label="版本号">
            <el-input v-model="updateForm.version" placeholder="例如 v1.0.1" />
          </el-form-item>
          <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px;">
            Docker 更新流程：docker load 载入镜像 → compose down + up -d 重启容器。镜像名由 compose 文件中的 image 字段决定，前端无需指定。
          </el-alert>
        </template>

        <template v-else>
          <el-form-item label="版本号">
            <el-input v-model="updateForm.version" placeholder="例如 v1.0.1" />
          </el-form-item>
          <el-form-item label="更新选项">
            <el-checkbox v-model="updateForm.backup_before_update">更新前备份旧文件</el-checkbox>
            <el-checkbox v-model="updateForm.auto_stop_old">自动停止旧程序</el-checkbox>
            <el-checkbox v-model="updateForm.auto_start_after">更新后自动启动</el-checkbox>
          </el-form-item>
          <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px;">
            二进制文件路径和服务名留空时，自动使用 Agent 自报的部署路径和 systemd 服务名（来自 config.yaml 的 deploy 段）。
          </el-alert>
        </template>

        <!-- ===== 高级选项：可选上传 compose/config 文件 ===== -->
        <el-form-item label="高级配置" style="margin-bottom: 4px;">
          <el-link type="primary" :underline="false" @click="showAdvancedConfig = !showAdvancedConfig">
            {{ showAdvancedConfig ? '收起 ▲' : '展开 ▼' }} 可选：同步 compose.yml / config.yaml / srmc-agent.service
          </el-link>
        </el-form-item>
        <template v-if="showAdvancedConfig">
          <div style="background: #f7f9fc; padding: 12px 14px; border-radius: 6px; margin: 0 0 12px 0;">
            <el-form-item label="docker-compose.yml" style="margin-bottom: 10px;">
              <div>
                <input ref="composeFileRef" type="file" accept=".yml,.yaml" style="display:none" @change="onComposeFileChange" />
                <el-button size="small" @click="composeFileRef?.click()">选择文件</el-button>
                <span v-if="extraFiles.compose_name" style="margin-left: 8px; font-size: 12px;">{{ extraFiles.compose_name }}</span>
                <el-icon v-if="extraFiles.compose_name" style="margin-left: 6px; cursor: pointer; color: #909399;" @click="extraFiles.compose_content = ''; extraFiles.compose_name = ''"><close /></el-icon>
              </div>
            </el-form-item>
            <el-form-item label="config.yaml" style="margin-bottom: 10px;">
              <div>
                <input ref="configFileRef" type="file" accept=".yml,.yaml" style="display:none" @change="onConfigFileChange" />
                <el-button size="small" @click="configFileRef?.click()">选择文件</el-button>
                <span v-if="extraFiles.config_name" style="margin-left: 8px; font-size: 12px;">{{ extraFiles.config_name }}</span>
                <el-icon v-if="extraFiles.config_name" style="margin-left: 6px; cursor: pointer; color: #909399;" @click="extraFiles.config_content = ''; extraFiles.config_name = ''"><close /></el-icon>
                <div v-if="extraFiles.config_name" style="font-size: 12px; color: #67c23a; margin-top: 2px;">Agent 会自动保留 server.url / token / agent.uuid / name / ip / deploy_dir 不被覆盖</div>
              </div>
            </el-form-item>
            <el-form-item v-if="updateForm.update_type === 'binary'" label="srmc-agent.service" style="margin-bottom: 0;">
              <div>
                <input ref="serviceFileRef" type="file" accept=".service" style="display:none" @change="onServiceFileChange" />
                <el-button size="small" @click="serviceFileRef?.click()">选择文件</el-button>
                <span v-if="extraFiles.service_name" style="margin-left: 8px; font-size: 12px;">{{ extraFiles.service_name }}</span>
                <el-icon v-if="extraFiles.service_name" style="margin-left: 6px; cursor: pointer; color: #909399;" @click="extraFiles.service_content = ''; extraFiles.service_name = ''"><close /></el-icon>
              </div>
            </el-form-item>
          </div>
        </template>
      </el-form>

      <template #footer>
        <el-button @click="showUpdateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creatingTask" @click="createUpdateTask">创建更新任务</el-button>
      </template>
    </el-dialog>

    <!-- ===== 批量装机弹窗（SSH 推送，适用于首次部署/覆盖安装旧版） ===== -->
    <el-dialog title="Agent 批量装机（SSH 推送）" v-model="showDeployDialog" width="780px" @closed="resetDeployForm">
      <el-form label-width="130px">
        <el-form-item label="安装包">
          <el-select v-model="deployForm.package_id" placeholder="选择已上传的安装包" style="width: 420px;" @change="onPackageSelected">
            <el-option-group label="Docker 镜像包">
              <el-option
                v-for="p in dockerPackages"
                :key="p.package_id"
                :label="`${p.version} · ${p.name}（${formatBytes(p.file_size)}）`"
                :value="p.package_id"
              />
            </el-option-group>
            <el-option-group label="二进制安装包">
              <el-option
                v-for="p in binaryPackages"
                :key="p.package_id"
                :label="`${p.version} · ${p.name}（${formatBytes(p.file_size)}）`"
                :value="p.package_id"
              />
            </el-option-group>
          </el-select>
          <el-button style="margin-left: 10px;" @click="showPkgUpload = !showPkgUpload">
            {{ showPkgUpload ? '收起上传' : '上传新包' }}
          </el-button>
        </el-form-item>

        <div v-if="showPkgUpload" style="background: #f7f9fc; padding: 14px; border-radius: 6px; margin: 0 0 14px 130px;">
          <el-form-item label="包类型">
            <el-radio-group v-model="pkgForm.package_type">
              <el-radio label="docker">Docker 镜像 tar</el-radio>
              <el-radio label="binary">二进制可执行文件</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="版本号">
            <el-input v-model="pkgForm.version" placeholder="例如 v1.1.0" style="width: 300px;" />
          </el-form-item>
          <el-form-item label="包名称（可选）">
            <el-input v-model="pkgForm.name" placeholder="留空使用文件名" style="width: 300px;" />
          </el-form-item>
          <el-form-item label="选择文件">
            <input ref="pkgFileInputRef" type="file" style="display:none" @change="onPkgFileSelected" />
            <el-button @click="pkgFileInputRef?.click()" :disabled="pkgUploading">选择文件</el-button>
            <span v-if="pkgForm.file_name" style="margin-left: 10px;">{{ pkgForm.file_name }}（{{ formatBytes(pkgForm.file_size) }}）</span>
            <el-progress v-if="pkgUploading || pkgUploadProgress === 100" :percentage="pkgUploadProgress" style="margin-top: 8px; width: 420px;" />
          </el-form-item>
          <el-form-item label="SHA256">
            <span style="font-family: monospace; font-size: 12px; word-break: break-all; width: 420px;">{{ pkgForm.file_sha256 || '上传后自动计算' }}</span>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="pkgUploading" :disabled="!pkgForm.file" @click="uploadPackage">上传安装包</el-button>
          </el-form-item>
        </div>

        <el-form-item label="部署目录">
          <el-input v-model="deployForm.deploy_dir" placeholder="/etc/srmc-agent" style="width: 420px;" />
          <span style="margin-left: 10px; color: #909399; font-size: 12px;">目录不存在会自动创建</span>
        </el-form-item>
        <el-form-item label="后端地址">
          <el-input v-model="deployForm.server_url" placeholder="ws://192.168.12.79:8000/api/ws/agent/" style="width: 420px;" />
        </el-form-item>

        <!-- 可选：自定义部署文件 -->
        <el-form-item label="高级配置" style="margin-bottom: 4px;">
          <el-link type="primary" :underline="false" @click="showDeployAdvanced = !showDeployAdvanced">
            {{ showDeployAdvanced ? '收起 ▲' : '展开 ▼' }} 可选：自定义 compose.yml / config.yaml
          </el-link>
        </el-form-item>
        <template v-if="showDeployAdvanced">
          <div style="background: #f7f9fc; padding: 12px 14px; border-radius: 6px; margin: 0 0 12px 130px;">
            <el-form-item label="docker-compose.yml" style="margin-bottom: 10px;">
              <div>
                <input ref="deployComposeRef" type="file" accept=".yml,.yaml" style="display:none" @change="onDeployComposeChange" />
                <el-button size="small" @click="deployComposeRef?.click()">选择文件</el-button>
                <span v-if="deployExtra.compose_name" style="margin-left: 8px; font-size: 12px;">{{ deployExtra.compose_name }}</span>
                <el-icon v-if="deployExtra.compose_name" style="margin-left: 6px; cursor: pointer; color: #909399;" @click="deployExtra.compose_content = ''; deployExtra.compose_name = ''"><close /></el-icon>
                <div style="font-size: 12px; color: #909399; margin-top: 2px;">留空则使用系统模板</div>
              </div>
            </el-form-item>
            <el-form-item label="config.yaml" style="margin-bottom: 0;">
              <div>
                <input ref="deployConfigRef" type="file" accept=".yml,.yaml" style="display:none" @change="onDeployConfigChange" />
                <el-button size="small" @click="deployConfigRef?.click()">选择文件</el-button>
                <span v-if="deployExtra.config_name" style="margin-left: 8px; font-size: 12px;">{{ deployExtra.config_name }}</span>
                <el-icon v-if="deployExtra.config_name" style="margin-left: 6px; cursor: pointer; color: #909399;" @click="deployExtra.config_content = ''; deployExtra.config_name = ''"><close /></el-icon>
                <div style="font-size: 12px; color: #909399; margin-top: 2px;">留空则使用系统模板，后端自动注入 server.url / token / agent.name / agent.ip / deploy_dir</div>
              </div>
            </el-form-item>
          </div>
        </template>

        <el-divider content-position="left">目标主机（需要 root SSH 凭据）</el-divider>
        <el-form-item label="主机 IP 列表">
          <el-input
            v-model="deployForm.hosts_text"
            type="textarea"
            :rows="5"
            placeholder="每行一个 IP，例如：&#10;192.168.12.81&#10;192.168.12.82"
            style="width: 420px;"
          />
          <div style="font-size: 12px; color: #909399; line-height: 1.5; margin-top: 4px; width: 420px;">
            Agent IP 默认使用 SSH 连接的 IP，无需逐台填写；装机时会自动校验该 IP 是否在目标机网卡上，NAT/多网卡异常会在任务详情中告警。
          </div>
        </el-form-item>
        <el-form-item label="SSH 端口">
          <el-input-number v-model="deployForm.port" :min="1" :max="65535" controls-position="right" style="width: 160px;" />
        </el-form-item>
        <el-form-item label="SSH 用户">
          <el-input v-model="deployForm.username" placeholder="root" style="width: 200px;" />
        </el-form-item>
        <el-form-item label="SSH 密码">
          <el-input v-model="deployForm.password" type="password" show-password style="width: 200px;" placeholder="root 密码" />
        </el-form-item>

        <el-alert type="warning" :closable="false" show-icon style="margin: 4px 0 0 130px; max-width: 560px;">
          将对 {{ deployHostCount }} 台主机通过 SSH 推送安装。Docker 方式执行 docker load + compose up；二进制方式安装 systemd 服务。单台失败不影响其他主机。
        </el-alert>
      </el-form>

      <template #footer>
        <el-button @click="showDeployDialog = false">取消</el-button>
        <el-button type="primary" :loading="creatingDeployTask" @click="createDeployTask">
          创建装机任务（{{ deployHostCount }} 台）
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import axios from '@/utils/axios'
import { usePermission } from '@/composables/usePermission'

const router = useRouter()
const { hasPermission } = usePermission()

const agents = ref([])
const allAgents = ref([])
const searchKeyword = ref('')
const statusFilter = ref('')
const showDetailDialog = ref(false)
const showServicesDialog = ref(false)
const showConfigDialog = ref(false)
const selectedAgent = ref(null)
const agentServices = ref([])
const selectedAgents = ref([])
const configForm = ref({
  agent_uuid: '',
  hostname: '',
  ip: '',
  ssh_port: 22,
  ssh_username: '',
  ssh_password: '',
  service_name: 'srmc-agent'
})

// ===== 批量更新 =====
const showUpdateDialog = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const creatingTask = ref(false)
const updateTargetUuids = ref([])
const uploadMeta = ref({})
const fileInputRef = ref(null)
const showAdvancedConfig = ref(false)
const composeFileRef = ref(null)
const configFileRef = ref(null)
const serviceFileRef = ref(null)
const extraFiles = reactive({
  compose_name: '',
  compose_content: '',
  config_name: '',
  config_content: '',
  service_name: '',
  service_content: ''
})
const updateForm = ref({
  update_type: 'docker',
  version: '',
  backup_before_update: true,
  auto_stop_old: true,
  auto_start_after: true
})

// 把 Agent 的 deploy_types 统计收敛成单一部署方式标签
// 优先用服务统计（多数决定；相同数量时 Docker 优先），无关联服务时 fallback 到 Agent 自报的 deploy_type
const deployModeLabel = (dt, agentDeployType) => {
  if (!dt || typeof dt !== 'object' || Object.keys(dt).length === 0) {
    // fallback 到 Agent 自报的 deploy_type
    if (agentDeployType === 'docker') return 'Docker'
    if (agentDeployType === 'binary') return '二进制'
    return '无关联'
  }
  const docker = (dt.DOCKER || 0) + (dt.DOCKER_COMPOSE || 0)
  const binary = (dt.HOST || 0) + (dt.HOST_APP || 0) + (dt.PROCESS || 0)
  if (docker === 0 && binary === 0) {
    if (agentDeployType === 'docker') return 'Docker'
    if (agentDeployType === 'binary') return '二进制'
    return '无关联'
  }
  return binary > docker ? '二进制' : 'Docker'
}
const deployModeTag = (dt, agentDeployType) => {
  const label = deployModeLabel(dt, agentDeployType)
  return label === 'Docker' ? 'warning' : label === '二进制' ? 'primary' : 'info'
}

// 批量更新弹窗按更新类型过滤 Agent 列表
const filteredAgents = computed(() => {
  const t = updateForm.value.update_type
  if (t === 'docker') return allAgents.value.filter(a => deployModeLabel(a.deploy_types, a.deploy_type) === 'Docker')
  if (t === 'binary') return allAgents.value.filter(a => deployModeLabel(a.deploy_types, a.deploy_type) === '二进制')
  return []
})

// 切换更新类型自动清空已选，防止遗留无效选择
watch(() => updateForm.value.update_type, () => { updateTargetUuids.value = [] })

const targetAgentNames = computed(() => {
  const m = {}
  allAgents.value.forEach(a => { m[a.uuid] = `${a.hostname} (${a.ip})` })
  return updateTargetUuids.value.map(u => m[u] || u).join('、')
})

const selectFilteredAgents = () => {
  updateTargetUuids.value = filteredAgents.value.map(a => a.uuid)
}

const loadAgents = async () => {
  try {
    const response = await fetch('/api/agents/', {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
    })
    const data = await response.json()
    if (data.code === 0) {
      allAgents.value = data.data
      let result = data.data
      if (searchKeyword.value) {
        const keyword = searchKeyword.value.toLowerCase()
        result = result.filter(a => 
          a.hostname.toLowerCase().includes(keyword) || 
          a.ip.toLowerCase().includes(keyword)
        )
      }
      if (statusFilter.value) {
        result = result.filter(a => 
          statusFilter.value === 'online' ? a.is_online : !a.is_online
        )
      }
      agents.value = result
      
      for (const agent of agents.value) {
        if (agent.is_online) {
          await loadAgentMetrics(agent.uuid)
        }
      }
    } else {
      ElMessage.error('加载失败')
    }
  } catch (error) {
    ElMessage.error('加载失败')
  }
}

const loadAgentMetrics = async (agent_uuid) => {
  try {
    const response = await fetch(`/api/agents/${agent_uuid}/metrics/`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
    })
    const data = await response.json()
    if (data.code === 0) {
      const agent = agents.value.find(a => a.uuid === agent_uuid)
      if (agent) {
        agent.metrics = data.data.system || {}
        agent.docker_containers = data.data.docker_containers || []
        agent.compose_projects = data.data.compose_projects || []
      }
    }
  } catch (error) {
    console.error('加载 Agent 指标失败:', error)
  }
}

const resetFilters = () => {
  searchKeyword.value = ''
  statusFilter.value = ''
  loadAgents()
}

const handleSelectionChange = (selection) => {
  selectedAgents.value = selection
}

const getToken = () => localStorage.getItem('token')

const controlAgent = async (agent, action) => {
  const actionLabels = { start: '启动', stop: '停止', restart: '重启', status: '状态' }
  try {
    await ElMessageBox.confirm(
      `确定要${actionLabels[action]} Agent "${agent.hostname} (${agent.ip})" 吗？`,
      '操作确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const response = await fetch(`/api/agents/${agent.uuid}/control`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}` 
      },
      body: JSON.stringify({ action })
    })
    const data = await response.json()
    if (data.code === 0 && data.data.success) {
      ElMessage.success(data.data.message)
      loadAgents()
    } else {
      ElMessage.error(data.data.message || '操作失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('控制 Agent 失败:', error)
    }
  }
}

const batchControl = async (action) => {
  if (!selectedAgents.value.length) return
  
  const actionLabels = { start: '启动', stop: '停止', restart: '重启' }
  try {
    await ElMessageBox.confirm(
      `确定要批量${actionLabels[action]} ${selectedAgents.value.length} 个 Agent 吗？`,
      '批量操作确认',
      {
        confirmButtonText: '确定执行',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const agent_uuids = selectedAgents.value.map(a => a.uuid)
    const response = await fetch('/api/agents/batch-control', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}` 
      },
      body: JSON.stringify({ action, agent_uuids })
    })
    const data = await response.json()
    if (data.code === 0) {
      const result = data.data
      const message = `总共 ${result.total} 个 Agent，成功 ${result.success} 个，失败 ${result.failed} 个`
      if (result.failed === 0) {
        ElMessage.success(message)
      } else {
        ElMessage.warning(message)
        // 显示失败详情
        const failedAgents = result.results.filter(r => !r.success)
        if (failedAgents.length > 0) {
          console.warn('失败详情:', failedAgents)
        }
      }
      loadAgents()
    } else {
      ElMessage.error(data.message || '批量操作失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量控制失败:', error)
    }
  }
}

const openConfigDialog = (agent) => {
  configForm.value = {
    agent_uuid: agent.uuid,
    hostname: agent.hostname,
    ip: agent.ip,
    ssh_port: agent.ssh_port || 22,
    ssh_username: agent.ssh_username || '',
    ssh_password: '',
    service_name: agent.service_name || 'srmc-agent'
  }
  showConfigDialog.value = true
}

const saveConfig = async () => {
  try {
    const response = await fetch(`/api/agents/${configForm.value.agent_uuid}/config`, {
      method: 'PUT',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}` 
      },
      body: JSON.stringify({
        ssh_port: configForm.value.ssh_port,
        ssh_username: configForm.value.ssh_username,
        ssh_password: configForm.value.ssh_password,
        service_name: configForm.value.service_name
      })
    })
    const data = await response.json()
    if (data.code === 0) {
      ElMessage.success('配置保存成功')
      showConfigDialog.value = false
      loadAgents()
    } else {
      ElMessage.error(data.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error('保存配置失败')
  }
}

const viewAgent = (agent) => {
  selectedAgent.value = agent
  showDetailDialog.value = true
}

const viewAgentServices = async (agent) => {
  try {
    const response = await fetch(`/api/agents/${agent.uuid}/services/`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
    })
    const data = await response.json()
    if (data.code === 0) {
      agentServices.value = data.data
      showServicesDialog.value = true
    } else {
      ElMessage.error('加载服务列表失败')
    }
  } catch (error) {
    ElMessage.error('加载服务列表失败')
  }
}

const deleteAgent = async (agent) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 Agent "${agent.hostname} (${agent.ip})" 吗？删除后，关联的服务将自动解除关联。如果误删，重启 Agent 后会自动重新注册。`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
    
    const response = await fetch(`/api/agents/${agent.uuid}/`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
    })
    const data = await response.json()
    if (data.code === 0) {
      ElMessage.success('Agent 删除成功')
      loadAgents()
    } else {
      ElMessage.error(data.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除 Agent 失败:', error)
    }
  }
}

const formatMemory = (bytes) => {
  if (!bytes) return '-'
  if (bytes >= 1024 * 1024 * 1024) {
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
  } else if (bytes >= 1024 * 1024) {
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
  } else if (bytes >= 1024) {
    return (bytes / 1024).toFixed(2) + ' KB'
  }
  return bytes + ' B'
}

const formatPercent = (value) => {
  if (value === undefined || value === null || isNaN(value)) return '--'
  return value.toFixed(1) + '%'
}

const formatLoad = (value) => {
  if (value === undefined || value === null || isNaN(value)) return '--'
  return value.toFixed(2)
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const getDeployType = (type) => {
  const types = {
    'HOST': { label: '主机部署', type: 'info' },
    'DOCKER': { label: 'Docker容器', type: 'success' },
    'DOCKER_COMPOSE': { label: 'Docker Compose', type: 'warning' }
  }
  return types[type] || { label: type, type: 'default' }
}

const formatBytes = (bytes) => {
  if (!bytes) return '0 B'
  if (bytes >= 1024 * 1024 * 1024) return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
  if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(2) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return bytes + ' B'
}

const openUpdateDialog = () => {
  updateTargetUuids.value = selectedAgents.value.map(a => a.uuid)
  showUpdateDialog.value = true
}

const resetUpdateForm = () => {
  updateForm.value = {
    update_type: 'docker',
    version: '',
    backup_before_update: true,
    auto_stop_old: true,
    auto_start_after: true
  }
  uploadMeta.value = {}
  uploading.value = false
  uploadProgress.value = 0
  updateTargetUuids.value = []
  showAdvancedConfig.value = false
  Object.assign(extraFiles, { compose_name: '', compose_content: '', config_name: '', config_content: '', service_name: '', service_content: '' })
}

// 可选文件读取（compose.yml / config.yaml / service）
const readFileAsText = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader()
  reader.onload = () => resolve(reader.result)
  reader.onerror = reject
  reader.readAsText(file)
})
const onComposeFileChange = async (e) => {
  const f = e.target.files[0]
  if (!f) return
  extraFiles.compose_name = f.name
  extraFiles.compose_content = await readFileAsText(f)
}
const onConfigFileChange = async (e) => {
  const f = e.target.files[0]
  if (!f) return
  extraFiles.config_name = f.name
  extraFiles.config_content = await readFileAsText(f)
}
const onServiceFileChange = async (e) => {
  const f = e.target.files[0]
  if (!f) return
  extraFiles.service_name = f.name
  extraFiles.service_content = await readFileAsText(f)
}

const handleFileSelect = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  uploading.value = true
  uploadProgress.value = 0
  try {
    const res = await axios.post('/api/agent-update/files', formData, {
      timeout: 0,
      onUploadProgress: (evt) => {
        if (evt.total) uploadProgress.value = Math.round((evt.loaded / evt.total) * 100)
      }
    })
    if (res.data.code === 0) {
      uploadMeta.value = res.data.data
      uploadProgress.value = 100
      ElMessage.success('上传成功')
    } else {
      ElMessage.error(res.data.message || '上传失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '上传失败')
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}

const createUpdateTask = async () => {
  if (!uploadMeta.value.file_ref) {
    ElMessage.error('请先选择并上传文件')
    return
  }
  if (!updateTargetUuids.value.length) {
    ElMessage.error('请选择目标 Agent')
    return
  }
  // Docker 模式：无需 image_name/image_tag，Agent 走 compose down + up 自动套用新镜像
  // 二进制模式：binary_target_path/binary_service_name 留空，由后端用 Agent 自报的 deploy 配置兜底

  const typeLabel = updateForm.value.update_type === 'docker' ? 'Docker 镜像' : '二进制文件'
  const versionLabel = updateForm.value.version || '-'
  const names = updateTargetUuids.value.map(u => {
    const a = allAgents.value.find(x => x.uuid === u)
    return a ? a.hostname : u
  }).join('、')
  try {
    await ElMessageBox.confirm(
      `更新类型：${typeLabel}；版本：${versionLabel}；文件：${uploadMeta.value.file_name || '-'}；` +
      `目标：${updateTargetUuids.value.length} 台（${names}）。确认开始执行？`,
      '发布确认',
      { confirmButtonText: '确认执行', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (e) {
    return
  }

  creatingTask.value = true
  try {
    const payload = {
      file_ref: uploadMeta.value.file_ref,
      file_name: uploadMeta.value.file_name,
      update_type: updateForm.value.update_type,
      version: updateForm.value.version,
      backup_before_update: updateForm.value.backup_before_update,
      auto_stop_old: updateForm.value.auto_stop_old,
      auto_start_after: updateForm.value.auto_start_after,
      agent_uuids: updateTargetUuids.value,
      compose_file: extraFiles.compose_content || '',
      config_file: extraFiles.config_content || '',
      service_file: extraFiles.service_content || ''
    }
    const res = await axios.post('/api/agent-update/tasks', payload)
    if (res.data.code === 0) {
      ElMessage.success('任务已创建，正在后台逐台执行')
      showUpdateDialog.value = false
      router.push('/agent-update-tasks')
    } else {
      ElMessage.error(res.data.message || '创建任务失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '创建任务失败')
  } finally {
    creatingTask.value = false
  }
}

// ===== 批量装机（SSH 推送） =====
const showDeployDialog = ref(false)
const showPkgUpload = ref(false)
const creatingDeployTask = ref(false)
const packages = ref([])

const deployForm = ref({
  package_id: '',
  deploy_dir: '/etc/srmc-agent',
  server_url: defaultServerUrl(),
  hosts_text: '',
  port: 22,
  username: 'root',
  password: ''
})
const showDeployAdvanced = ref(false)
const deployComposeRef = ref(null)
const deployConfigRef = ref(null)
const deployExtra = reactive({
  compose_name: '',
  compose_content: '',
  config_name: '',
  config_content: ''
})
const onDeployComposeChange = async (e) => {
  const f = e.target.files[0]
  if (!f) return
  deployExtra.compose_name = f.name
  deployExtra.compose_content = await readFileAsText(f)
}
const onDeployConfigChange = async (e) => {
  const f = e.target.files[0]
  if (!f) return
  deployExtra.config_name = f.name
  deployExtra.config_content = await readFileAsText(f)
}

const pkgForm = ref({
  package_type: 'docker',
  version: '',
  name: '',
  file: null,
  file_name: '',
  file_size: 0,
  file_sha256: ''
})
const pkgFileInputRef = ref(null)
const pkgUploading = ref(false)
const pkgUploadProgress = ref(0)

const dockerPackages = computed(() => packages.value.filter(p => p.package_type === 'docker'))
const binaryPackages = computed(() => packages.value.filter(p => p.package_type === 'binary'))
const selectedPackage = computed(() => packages.value.find(p => p.package_id === deployForm.value.package_id))
const deployHostCount = computed(() =>
  deployForm.value.hosts_text.split('\n').map(s => s.trim()).filter(Boolean).length
)

function defaultServerUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  // Agent 是独立进程，不能走前端 dev/nginx 端口（5173 等，其 /api 仅代理给浏览器），
  // 必须直连后端 8000。若浏览器本身就在访问后端端口，则原样保留 host。
  const port = window.location.port
  if (port === '8000' || port === '') {
    return `${proto}://${window.location.host}/api/ws/agent/`
  }
  return `${proto}://${window.location.hostname}:8000/api/ws/agent/`
}

const handleTaskMenu = (cmd) => {
  router.push(cmd === 'update' ? '/agent-update-tasks' : '/agent-deploy-tasks')
}

const loadPackages = async () => {
  try {
    const res = await axios.get('/api/agent-deploy/packages')
    if (res.data.code === 0) packages.value = res.data.data || []
  } catch (e) {
    // 静默：旧后端无此接口时不阻断页面
  }
}

const openDeployDialog = () => {
  resetDeployForm()
  showDeployDialog.value = true
  loadPackages()
}

const resetDeployForm = () => {
  deployForm.value = {
    package_id: '',
    deploy_dir: '/etc/srmc-agent',
    server_url: defaultServerUrl(),
    hosts_text: '',
    port: 22,
    username: 'root',
    password: ''
  }
  showPkgUpload.value = false
  resetPkgForm()
  showDeployAdvanced.value = false
  Object.assign(deployExtra, { compose_name: '', compose_content: '', config_name: '', config_content: '' })
}

const resetPkgForm = () => {
  pkgForm.value = { package_type: 'docker', version: '', name: '', file: null, file_name: '', file_size: 0, file_sha256: '' }
  pkgUploading.value = false
  pkgUploadProgress.value = 0
  if (pkgFileInputRef.value) pkgFileInputRef.value.value = ''
}

const onPackageSelected = () => {}

const onPkgFileSelected = (e) => {
  const f = e.target.files?.[0]
  if (!f) return
  pkgForm.value.file = f
  pkgForm.value.file_name = f.name
  pkgForm.value.file_size = f.size
  pkgForm.value.file_sha256 = ''
  pkgUploadProgress.value = 0
}

const uploadPackage = async () => {
  if (!pkgForm.value.file) { ElMessage.warning('请选择安装包文件'); return }
  if (!pkgForm.value.version.trim()) { ElMessage.warning('请填写版本号'); return }
  pkgUploading.value = true
  pkgUploadProgress.value = 0
  try {
    const fd = new FormData()
    fd.append('file', pkgForm.value.file)
    fd.append('package_type', pkgForm.value.package_type)
    fd.append('version', pkgForm.value.version.trim())
    fd.append('name', pkgForm.value.name || '')
    const res = await axios.post('/api/agent-deploy/packages', fd, {
      onUploadProgress: (e) => {
        if (e.total) pkgUploadProgress.value = Math.round((e.loaded / e.total) * 100)
      }
    })
    if (res.data.code === 0) {
      ElMessage.success('安装包上传成功')
      await loadPackages()
      deployForm.value.package_id = res.data.data.package_id
      resetPkgForm()
      showPkgUpload.value = false
    } else {
      ElMessage.error(res.data.message || '上传失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || err.response?.data?.message || '上传失败')
  } finally {
    pkgUploading.value = false
  }
}

const createDeployTask = async () => {
  // 更明确的校验提示
  if (showPkgUpload.value && pkgForm.value.file && !deployForm.value.package_id) {
    ElMessage.warning('请先点击"上传安装包"按钮完成文件上传')
    return
  }
  if (!deployForm.value.package_id) {
    ElMessage.warning('请先选择已上传的安装包，或展开上传区上传新包')
    return
  }
  if (showPkgUpload.value && pkgForm.value.file) {
    ElMessage.warning('新安装包尚未上传完成，请先点击上传')
    return
  }
  const ips = deployForm.value.hosts_text.split('\n').map(s => s.trim()).filter(Boolean)
  if (!ips.length) { ElMessage.warning('请填写至少一个目标主机 IP'); return }
  if (!deployForm.value.username || !deployForm.value.password) { ElMessage.warning('请填写 SSH 用户和密码'); return }
  if (!deployForm.value.server_url.startsWith('ws')) { ElMessage.warning('后端地址需以 ws:// 或 wss:// 开头'); return }

  const pkg = selectedPackage.value
  const typeLabel = pkg?.package_type === 'docker' ? 'Docker 镜像' : '二进制'
  try {
    await ElMessageBox.confirm(
      `将向 ${ips.length} 台主机以 ${typeLabel}（${pkg?.version}）方式装机，部署目录 ${deployForm.value.deploy_dir}。确认执行？`,
      '装机确认',
      { confirmButtonText: '确认装机', cancelButtonText: '返回', type: 'warning' }
    )
  } catch (e) { return }

  creatingDeployTask.value = true
  try {
    const hosts = ips.map(ip => ({
      ip,
      port: deployForm.value.port,
      username: deployForm.value.username,
      password: deployForm.value.password
    }))
    const res = await axios.post('/api/agent-deploy/tasks', {
      package_id: deployForm.value.package_id,
      deploy_dir: deployForm.value.deploy_dir,
      server_url: deployForm.value.server_url,
      hosts,
      compose_file: deployExtra.compose_content || '',
      config_file: deployExtra.config_content || ''
    })
    if (res.data.code === 0) {
      ElMessage.success('装机任务已创建，正在后台逐台执行')
      showDeployDialog.value = false
      router.push('/agent-deploy-tasks')
    } else {
      ElMessage.error(res.data.message || '创建任务失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || err.response?.data?.message || '创建任务失败')
  } finally {
    creatingDeployTask.value = false
  }
}

onMounted(() => {
  loadAgents()
  setInterval(loadAgents, 10000)
})
</script>

<style scoped>
.agents-page {
  padding: 20px;
}

.table-wrapper {
  overflow-x: auto;
  width: 100%;
  min-width: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  margin: 0;
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

.search-input {
  width: 200px;
}

.status-select {
  width: 120px;
}

.agent-detail {
  padding: 10px;
}

.capabilities, .tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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
}

.view-btn {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
}

.edit-btn {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
}

.start-btn {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.restart-btn {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}

.stop-btn {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.config-btn {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
}

.delete-btn {
  background: linear-gradient(135deg, #9ca3af 0%, #6b7280 100%);
}

/* 批量按钮禁用样式 */
.el-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>