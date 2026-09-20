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
        <el-button v-if="hasPermission('agent:manage')" plain :loading="probingArch" @click="probeArch">
          {{ selectedAgents.length ? `探测架构 (${selectedAgents.length})` : '探测架构' }}
        </el-button>
        <el-button v-if="hasPermission('agent:manage')" type="primary" plain @click="openDeployDialog">
          批量部署
        </el-button>
        <el-dropdown v-if="hasPermission('agent:manage')" @command="handleTaskMenu">
          <el-button>
            任务记录<el-icon class="el-icon--right"><arrow-down /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="deploy">批量部署任务</el-dropdown-item>
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
        ref="agentTableRef"
        :data="agents" 
        border 
        fit 
        row-key="uuid"
        :header-cell-style="{ 'white-space': 'nowrap' }"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" reserve-selection />
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
            <el-tag :type="deployModeTag(scope.row.deploy_type)" size="small">{{ deployModeLabel(scope.row.deploy_type) }}</el-tag>
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
        <el-table-column label="架构" width="95" show-overflow-tooltip>
          <template #default="scope">
            <el-tag v-if="scope.row.arch" type="info" size="small">{{ formatArch(scope.row.arch) }}</el-tag>
            <span v-else style="color: #e6a23c;">未知</span>
          </template>
        </el-table-column>
        <el-table-column label="Agent版本" width="100" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ formatVersion(scope.row.agent_version) }}</span>
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
          <el-descriptions-item label="架构">{{ formatArch(selectedAgent.arch) || '未知' }}</el-descriptions-item>
          <el-descriptions-item label="CPU型号">{{ selectedAgent.cpu_model }}</el-descriptions-item>
          <el-descriptions-item label="CPU核心">{{ selectedAgent.cpu_cores }}</el-descriptions-item>
          <el-descriptions-item label="内存总量">{{ formatMemory(selectedAgent.memory_total) }}</el-descriptions-item>
          <el-descriptions-item label="Agent版本">{{ formatVersion(selectedAgent.agent_version) }}</el-descriptions-item>
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

    <!-- ===== 批量部署弹窗（SSH 推送，适用于首次安装/覆盖升级） ===== -->
    <el-dialog title="Agent 批量部署（SSH 推送）" v-model="showDeployDialog" width="780px" @closed="resetDeployForm">
      <el-form label-width="130px">
        <el-form-item label="安装包">
          <el-select v-model="deployForm.package_id" placeholder="选择已上传的安装包" style="width: 420px;" @change="onPackageSelected">
            <el-option-group label="Docker 镜像包">
              <el-option
                v-for="p in dockerPackages"
                :key="p.package_id"
                :label="`${p.version} · ${p.name}（${formatBytes(p.file_size)}）`"
                :value="p.package_id"
              >
                <span class="pkg-option">
                  <span class="pkg-option-label">{{ p.version }} · {{ p.name }}（{{ formatBytes(p.file_size) }}）</span>
                  <el-icon class="pkg-option-del" title="删除该安装包" @click.stop="deletePackage(p)"><Delete /></el-icon>
                </span>
              </el-option>
            </el-option-group>
            <el-option-group label="二进制安装包">
              <el-option
                v-for="p in binaryPackages"
                :key="p.package_id"
                :label="`${p.version} · ${p.name}（${formatBytes(p.file_size)}）`"
                :value="p.package_id"
              >
                <span class="pkg-option">
                  <span class="pkg-option-label">{{ p.version }} · {{ p.name }}（{{ formatBytes(p.file_size) }}）</span>
                  <el-icon class="pkg-option-del" title="删除该安装包" @click.stop="deletePackage(p)"><Delete /></el-icon>
                </span>
              </el-option>
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

        <el-divider content-position="left">目标主机</el-divider>
        <el-form-item label="选择方式">
          <el-radio-group v-model="deployForm.target_mode">
            <el-radio label="managed">从已纳管 Agent 选择</el-radio>
            <el-radio label="manual">手工填写主机</el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="deployForm.target_mode === 'managed'">
          <el-form-item label="目标 Agent">
            <div style="width: 100%;">
              <div style="margin-bottom: 6px;">
                <span style="font-size: 12px; color: #606266; margin-right: 8px;">架构</span>
                <el-select v-model="deployArchFilter" size="small" style="width: 140px; margin-right: 12px;">
                  <el-option label="全部" value="__all__" />
                  <el-option
                    v-for="opt in deployArchOptions"
                    :key="opt.value"
                    :label="`${opt.label} (${opt.count})`"
                    :value="opt.value"
                  />
                </el-select>
                <el-button size="small" :disabled="!deployCandidateAgents.length" @click="selectAllCandidates">
                  全选筛选结果 ({{ deployCandidateAgents.length }})
                </el-button>
                <el-button size="small" :disabled="!deployTargetUuids.length" @click="deployTargetUuids = []">清空</el-button>
                <span style="font-size: 12px; color: #909399; margin-left: 8px;">
                  共 {{ allAgents.length }} 台，当前安装包类型匹配 {{ deployMatchedAgents.length }} 台
                </span>
              </div>
              <el-select
                v-model="deployTargetUuids"
                multiple
                filterable
                :placeholder="selectedPackage ? '选择目标 Agent' : '请先选择安装包'"
                :disabled="!selectedPackage"
                style="width: 560px;"
              >
                <el-option v-for="a in deployCandidateAgents" :key="a.uuid" :label="`${a.hostname} (${a.ip})`" :value="a.uuid">
                  <span>{{ a.hostname }} ({{ a.ip }})</span>
                  <span style="float: right; margin-left: 8px;">
                    <el-tag :type="a.arch ? 'info' : 'warning'" size="small" style="margin-right: 4px;">{{ formatArch(a.arch) || '架构未知' }}</el-tag>
                    <el-tag :type="deployModeTag(a.deploy_type)" size="small" style="margin-right: 4px;">{{ deployModeLabel(a.deploy_type) }}</el-tag>
                    <el-tag type="success" size="small">{{ formatVersion(a.agent_version) }}</el-tag>
                  </span>
                </el-option>
              </el-select>
              <el-alert
                v-if="selectedPackage && !deployMatchedAgents.length"
                type="warning"
                :closable="false"
                show-icon
                style="margin-top: 6px; width: 560px;"
              >
                没有与当前安装包类型（{{ selectedPackage.package_type === 'docker' ? 'Docker 镜像' : '二进制文件' }}）匹配的 Agent。
              </el-alert>
              <div v-if="deployTargetUuids.length" style="font-size: 12px; color: #909399; margin-top: 6px; width: 560px;">
                已选 {{ deployTargetUuids.length }} 台：{{ deployTargetSummary }}
              </div>
              <div style="font-size: 12px; color: #909399; line-height: 1.5; margin-top: 4px; width: 560px;">
                将复用「服务器管理」中该 IP 已保存的 SSH 凭据，无需重复输入密码。若提示无可用凭据，请先在服务器管理中维护，或改用手工填写。
              </div>
            </div>
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="主机 IP 列表">
            <el-input
              v-model="deployForm.hosts_text"
              type="textarea"
              :rows="5"
              placeholder="每行一个 IP，例如：&#10;192.168.12.81&#10;192.168.12.82"
              style="width: 420px;"
            />
            <div style="font-size: 12px; color: #909399; line-height: 1.5; margin-top: 4px; width: 420px;">
              Agent IP 默认使用 SSH 连接的 IP，无需逐台填写；部署时会自动校验该 IP 是否在目标机网卡上，NAT/多网卡异常会在任务详情中告警。
            </div>
          </el-form-item>
          <el-form-item label="SSH 端口">
            <el-input-number v-model="deployForm.port" :min="1" :max="65535" controls-position="right" style="width: 160px;" />
          </el-form-item>
          <el-form-item label="SSH 用户">
            <el-input v-model="deployForm.username" placeholder="root" style="width: 200px;" />
            <div style="font-size: 12px; color: #909399; margin-left: 8px;">
              非 root 用户需具备 sudo 权限（免密，或用同一密码提权）
            </div>
          </el-form-item>
          <el-form-item label="SSH 密码">
            <el-input v-model="deployForm.password" type="password" show-password style="width: 200px;" placeholder="root 密码" />
          </el-form-item>
        </template>

        <el-alert type="warning" :closable="false" show-icon style="margin: 4px 0 0 130px; max-width: 560px;">
          将对 {{ deployHostCount }} 台主机通过 SSH 推送部署。Docker 方式执行 docker load + compose 重建；二进制方式安装 systemd 服务。单台失败不影响其他主机。
        </el-alert>
      </el-form>

      <template #footer>
        <el-button @click="showDeployDialog = false">取消</el-button>
        <el-button type="primary" :loading="creatingDeployTask" @click="createDeployTask">
          创建部署任务（{{ deployHostCount }} 台）
        </el-button>
      </template>
    </el-dialog>

    <el-dialog title="探测架构结果" v-model="probeResultDialog" width="720px">
      <el-alert
        :type="probeResult.failed ? 'warning' : 'success'"
        :closable="false"
        show-icon
        style="margin-bottom: 12px;"
      >
        共 {{ probeResult.total }} 台，成功 {{ probeResult.success }} 台，失败 {{ probeResult.failed }} 台
      </el-alert>
      <el-table :data="probeResult.results" border size="small" max-height="380" style="width: 100%">
        <el-table-column prop="hostname" label="主机名" min-width="120" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP" width="140" show-overflow-tooltip />
        <el-table-column label="结果" width="80" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.success ? 'success' : 'danger'" size="small">
              {{ scope.row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="arch" label="架构" width="90" align="center">
          <template #default="scope">{{ formatArch(scope.row.arch) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="message" label="失败原因" min-width="240" show-overflow-tooltip>
          <template #default="scope">{{ scope.row.message || '-' }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="probeResultDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
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
const agentTableRef = ref(null)
const configForm = ref({
  agent_uuid: '',
  hostname: '',
  ip: '',
  ssh_port: 22,
  ssh_username: '',
  ssh_password: '',
  service_name: 'srmc-agent'
})

// Agent 自身的部署方式标签（agents.deploy_type：docker / binary）
// 注意：这里表示 Agent 自己怎么部署的，决定用 Docker 包还是二进制包更新它；
// 与「服务管理」里业务服务的部署方式（app_services.deploy_type）是两回事，不要混用。
const deployModeLabel = (agentDeployType) => {
  if (agentDeployType === 'docker') return 'Docker'
  if (agentDeployType === 'binary') return '二进制'
  return '未知'
}
const deployModeTag = (agentDeployType) => {
  const label = deployModeLabel(agentDeployType)
  return label === 'Docker' ? 'warning' : label === '二进制' ? 'primary' : 'info'
}

// 版本号统一展示：内部规范形态为 1.0.1，展示时统一补 v 前缀，避免出现 vV1.0.1
const formatVersion = (v) => {
  const s = (v || '').trim().replace(/^[vV](?=\d)/, '')
  return s ? `v${s}` : '--'
}

// 架构展示：内部存储为 Go 命名（amd64/arm64），展示时转换为 uname -m 命名
const ARCH_DISPLAY = { amd64: 'x86_64', arm64: 'aarch64' }
const formatArch = (v) => {
  const s = (v || '').trim()
  if (!s) return ''
  return ARCH_DISPLAY[s.toLowerCase()] || s
}

// 探测架构：有选中则探选中项，未选中则补录所有架构未知的 Agent
const probingArch = ref(false)
const probeResultDialog = ref(false)
const probeResult = ref({ total: 0, success: 0, failed: 0, results: [] })

const probeArch = async () => {
  probingArch.value = true
  try {
    const body = selectedAgents.value.length
      ? { agent_uuids: selectedAgents.value.map(a => a.uuid) }
      : {}
    const res = await axios.post('/api/agents/probe-arch', body)
    const d = res.data?.data || {}
    if (!d.total) {
      ElMessage.info('没有需要探测的 Agent（架构均已上报）')
    } else if (d.failed) {
      // 有失败时弹出明细，展示每台的失败原因
      probeResult.value = d
      probeResultDialog.value = true
    } else {
      ElMessage.success(`探测完成：成功 ${d.success} 台`)
    }
    await loadAgents()
    clearSelection()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || err.response?.data?.detail || '探测架构失败')
  } finally {
    probingArch.value = false
  }
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

// 清空表格勾选（reserve-selection 会跨刷新保留，操作完成后需主动清除）
const clearSelection = () => {
  agentTableRef.value?.clearSelection()
  selectedAgents.value = []
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
      clearSelection()
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

// ===== 批量部署（SSH 推送） =====
const showDeployDialog = ref(false)
const showPkgUpload = ref(false)
const creatingDeployTask = ref(false)
const packages = ref([])
const deployTargetUuids = ref([])
const deployArchFilter = ref('__all__')

const deployForm = ref({
  package_id: '',
  target_mode: 'managed',
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
const deployHostCount = computed(() => {
  if (deployForm.value.target_mode === 'managed') return deployTargetUuids.value.length
  return deployForm.value.hosts_text.split('\n').map(s => s.trim()).filter(Boolean).length
})

// 已选 Agent 的部署方式汇总，如「Docker 3 台、二进制 2 台」
const deployTargetSummary = computed(() => {
  const m = {}
  allAgents.value
    .filter(a => deployTargetUuids.value.includes(a.uuid))
    .forEach(a => {
      const label = deployModeLabel(a.deploy_type)
      m[label] = (m[label] || 0) + 1
    })
  return Object.entries(m).map(([k, v]) => `${k} ${v} 台`).join('、')
})

// 与当前安装包类型匹配的 Agent（Docker 包只列 Docker Agent，二进制包只列二进制 Agent）
// 一次部署只能用一种包，因此从源头过滤，避免选错导致部署失败
const deployMatchedAgents = computed(() => {
  const pkg = selectedPackage.value
  if (!pkg) return []
  const want = pkg.package_type === 'docker' ? 'Docker' : '二进制'
  return allAgents.value.filter(a => deployModeLabel(a.deploy_type) === want)
})

// 架构筛选选项（从匹配的 Agent 中动态统计）
// 架构未知用 __unknown__ 哨兵值：el-option 的 value 为空串时会被 Element Plus 当作"未选择"
const ARCH_UNKNOWN = '__unknown__'
const deployArchOptions = computed(() => {
  const m = {}
  deployMatchedAgents.value.forEach(a => {
    const k = a.arch || ARCH_UNKNOWN
    m[k] = (m[k] || 0) + 1
  })
  return Object.entries(m)
    .map(([value, count]) => ({ value, label: value === ARCH_UNKNOWN ? '架构未知' : formatArch(value), count }))
    .sort((x, y) => y.count - x.count)
})

// 最终候选列表：匹配包类型 + 架构筛选
// 用 __all__ 哨兵值表示"全部"，避免与"架构未知"冲突
const deployCandidateAgents = computed(() => {
  const arch = deployArchFilter.value
  if (arch === '__all__') return deployMatchedAgents.value
  if (arch === ARCH_UNKNOWN) return deployMatchedAgents.value.filter(a => !a.arch)
  return deployMatchedAgents.value.filter(a => a.arch === arch)
})

// 全选当前筛选结果（替换语义，避免误操作累积）
const selectAllCandidates = () => {
  deployTargetUuids.value = deployCandidateAgents.value.map(a => a.uuid)
}

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

const handleTaskMenu = () => {
  router.push('/agent-deploy-tasks')
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
    target_mode: 'managed',
    deploy_dir: '/etc/srmc-agent',
    server_url: defaultServerUrl(),
    hosts_text: '',
    port: 22,
    username: 'root',
    password: ''
  }
  deployTargetUuids.value = []
  deployArchFilter.value = '__all__'
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

// 切换安装包后，之前选中的 Agent 可能不再匹配新包类型，清空选择与架构筛选
const onPackageSelected = () => {
  deployTargetUuids.value = []
  deployArchFilter.value = '__all__'
}

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
      // 新包类型可能与之前选中的 Agent 不匹配，清空选择与架构筛选
      deployTargetUuids.value = []
      deployArchFilter.value = '__all__'
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

const deletePackage = async (pkg) => {
  try {
    await ElMessageBox.confirm(
      `确认删除安装包「${pkg.version} · ${pkg.name}」？服务端文件将一并删除，且不可恢复。`,
      '删除安装包',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (e) { return }
  try {
    const res = await axios.delete(`/api/agent-deploy/packages/${pkg.package_id}`)
    if (res.data.code === 0) {
      ElMessage.success('安装包已删除')
      if (deployForm.value.package_id === pkg.package_id) deployForm.value.package_id = ''
      await loadPackages()
    } else {
      ElMessage.error(res.data.message || '删除失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || err.response?.data?.message || '删除失败')
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
  if (!deployForm.value.server_url.startsWith('ws')) { ElMessage.warning('后端地址需以 ws:// 或 wss:// 开头'); return }

  const managed = deployForm.value.target_mode === 'managed'
  let ips = []
  if (managed) {
    if (!deployTargetUuids.value.length) { ElMessage.warning('请选择至少一个目标 Agent'); return }
  } else {
    ips = deployForm.value.hosts_text.split('\n').map(s => s.trim()).filter(Boolean)
    if (!ips.length) { ElMessage.warning('请填写至少一个目标主机 IP'); return }
    if (!deployForm.value.username || !deployForm.value.password) { ElMessage.warning('请填写 SSH 用户和密码'); return }
  }

  const pkg = selectedPackage.value
  const typeLabel = pkg?.package_type === 'docker' ? 'Docker 镜像' : '二进制'
  const targetDesc = managed
    ? `${deployTargetUuids.value.length} 台已纳管 Agent（复用服务器管理中的 SSH 凭据）`
    : `${ips.length} 台主机（手工填写凭据）`
  try {
    await ElMessageBox.confirm(
      `将向 ${targetDesc} 以 ${typeLabel}（${pkg?.version}）方式部署，部署目录 ${deployForm.value.deploy_dir}。确认执行？`,
      '部署确认',
      { confirmButtonText: '确认部署', cancelButtonText: '返回', type: 'warning' }
    )
  } catch (e) { return }

  creatingDeployTask.value = true
  try {
    const payload = {
      package_id: deployForm.value.package_id,
      deploy_dir: deployForm.value.deploy_dir,
      server_url: deployForm.value.server_url,
      compose_file: deployExtra.compose_content || '',
      config_file: deployExtra.config_content || ''
    }
    if (managed) {
      payload.agent_uuids = deployTargetUuids.value
    } else {
      payload.hosts = ips.map(ip => ({
        ip,
        port: deployForm.value.port,
        username: deployForm.value.username,
        password: deployForm.value.password
      }))
    }
    const res = await axios.post('/api/agent-deploy/tasks', payload)
    if (res.data.code === 0) {
      ElMessage.success('部署任务已创建，正在后台逐台执行')
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

/* 安装包下拉选项：右侧删除图标 */
.pkg-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.pkg-option-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pkg-option-del {
  color: #c0c4cc;
  cursor: pointer;
  flex-shrink: 0;
}

.pkg-option-del:hover {
  color: #f56c6c;
}
</style>