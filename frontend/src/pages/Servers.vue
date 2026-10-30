<template>
  <div class="servers-page">
    <div class="page-header">
      <div>
        <h2>服务器管理</h2>
        <p class="page-subtitle">纳管服务器 SSH 凭据、带外管理入口，并与 Agent、监控、服务联动。</p>
      </div>
      <div class="header-actions">
        <el-button
          v-if="canManage && canDeployAgent"
          type="warning"
          plain
          :disabled="selection.length === 0"
          @click="openDeployDialog"
        >
          <el-icon><Download /></el-icon>
          批量安装 Agent{{ selection.length ? `（${selection.length}）` : '' }}
        </el-button>
        <el-button v-if="canManage" plain @click="openImportDialog">
          <el-icon><Upload /></el-icon>
          批量导入
        </el-button>
        <el-button v-if="canManage" plain @click="openAccountImportDialog">
          <el-icon><Upload /></el-icon>
          导入 SSH 账号
        </el-button>
        <el-button
          v-if="canManage"
          plain
          :loading="refreshing"
          :disabled="selection.length === 0 || refreshing"
          @click="refreshSystemInfo"
        >
          <el-icon><Refresh /></el-icon>
          刷新系统信息{{ selection.length ? `（${selection.length}）` : '' }}
        </el-button>
        <el-button
          v-if="canManage"
          type="danger"
          plain
          :disabled="selection.length === 0"
          @click="batchDelete"
        >
          批量删除{{ selection.length ? `（${selection.length}）` : '' }}
        </el-button>
        <el-button v-if="canManage" type="success" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          新增服务器
        </el-button>
      </div>
    </div>

    <div class="toolbar">
      <el-input
        v-model="filters.keyword"
        placeholder="按主机名 / IP / 用户名 / 备注搜索"
        clearable
        style="width: 260px"
        @clear="handleSearch"
        @keyup.enter="handleSearch"
      />
      <el-select v-model="filters.osType" placeholder="全部系统" clearable style="width: 120px" @change="handleSearch">
        <el-option label="Linux" value="LINUX" />
        <el-option label="Unix" value="UNIX" />
      </el-select>
      <el-select v-model="filters.hasBmc" placeholder="带外管理" clearable style="width: 130px" @change="handleSearch">
        <el-option label="已配置带外" :value="true" />
        <el-option label="未配置带外" :value="false" />
      </el-select>
      <el-select v-model="filters.agentStatus" placeholder="Agent状态" clearable style="width: 140px" @change="handleSearch">
        <el-option label="在线" value="online" />
        <el-option label="离线" value="offline" />
        <el-option label="未发现 Agent" value="no-agent" />
      </el-select>
      <el-button type="primary" @click="handleSearch">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <ListStats :items="statsItems" />

    <el-table
      :data="servers"
      border
      v-loading="loading"
      row-key="id"
      class="servers-table"
      :header-cell-style="{ backgroundColor: '#f8fafc', color: '#334155', fontWeight: '600' }"
      @selection-change="onSelectionChange"
      @row-click="handleRowClick"
    >
      <el-table-column type="selection" width="48" fixed="left" reserve-selection />
      <el-table-column label="主机名" min-width="150">
        <template #default="{ row }">
          <a class="host-link" @click.prevent="openDetail(row)">{{ row.hostname }}</a>
        </template>
      </el-table-column>
      <el-table-column prop="ip" label="IP地址" min-width="130" show-overflow-tooltip />
      <el-table-column label="操作系统" min-width="130">
        <template #default="{ row }">
          <span class="cell-wrap">{{ row.agent_os_distro || systemLabel(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="架构" width="96" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.agent_arch" type="info" size="small">{{ formatArch(row.agent_arch) }}</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="Agent状态" width="140" align="center">
        <template #default="{ row }">
          <template v-if="row.agent_installed">
            <el-tag v-if="row.agent_online" type="success" size="small">● 在线</el-tag>
            <el-tag v-else type="warning" size="small">● 离线</el-tag>
          </template>
          <el-tag v-else type="info" size="small">未发现 Agent</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="SSH账号" min-width="130">
        <template #default="{ row }">
          <a
            v-if="row.ssh_account_count > 0"
            class="host-link"
            title="查看 / 管理 SSH 账号"
            @click.prevent="openAccountDialog(row)"
          >{{ row.ssh_account_count }} 个账号</a>
          <a
            v-else-if="canManage"
            class="account-empty-link"
            @click.prevent="openAccountDialog(row)"
          >未配置</a>
          <span v-else class="text-muted">未配置</span>
        </template>
      </el-table-column>
      <el-table-column label="带外管理" width="100" align="center">
        <template #default="{ row }">
          <a
            v-if="row.bmc_url"
            class="bmc-link"
            :href="row.bmc_url"
            target="_blank"
            rel="noopener noreferrer"
            :title="row.bmc_url"
          >打开</a>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="290" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="canLogin"
            type="primary"
            size="small"
            :loading="loginCheckingId === row.id"
            @click="handleListLogin(row)"
          >登录</el-button>
          <el-button type="warning" size="small" :loading="testingIds.has(row.id)" @click="testConnection(row)">测试连接</el-button>
          <el-button v-if="canManage" type="success" size="small" @click="editServer(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <!-- ===== 新增 / 编辑 ===== -->
    <el-dialog
      :title="serverForm.id ? '编辑服务器' : '新增服务器'"
      v-model="showAddDialog"
      width="660px"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="serverForm" :rules="formRules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="主机名" prop="hostname">
              <el-input v-model="serverForm.hostname" placeholder="如 web-node-01" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="IP地址" prop="ip">
              <el-input v-model="serverForm.ip" placeholder="如 192.168.1.10" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="SSH端口" prop="ssh_port">
              <el-input v-model.number="serverForm.ssh_port" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="SSH用户名" prop="username">
              <el-input v-model="serverForm.username" />
              <div class="field-hint">此处维护默认账号；多账号请在列表「SSH账号」列管理</div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="认证方式">
          <el-radio-group v-model="authType">
            <el-radio label="password">密码认证</el-radio>
            <el-radio label="key">密钥认证</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="密码" v-if="authType === 'password'">
          <el-input
            v-model="serverForm.password"
            type="password"
            show-password
            :placeholder="serverForm.id && hasPassword ? '留空表示不修改现有密码' : '请输入登录密码'"
          />
        </el-form-item>
        <el-form-item label="私钥" v-if="authType === 'key'">
          <el-input
            v-model="serverForm.private_key"
            type="textarea"
            :rows="4"
            :placeholder="serverForm.id && hasPrivateKey ? '留空表示不修改现有私钥' : '粘贴私钥内容'"
          />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="操作系统" prop="os_type">
              <el-select v-model="serverForm.os_type" style="width: 100%">
                <el-option label="Linux" value="LINUX" />
                <el-option label="Unix" value="UNIX" />
              </el-select>
              <div v-if="serverForm.id && serverForm.agent_os_distro" class="field-hint">
                Agent 采集：{{ serverForm.agent_os_distro }}
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="带外类型">
              <el-select v-model="serverForm.bmc_type" clearable placeholder="未配置" style="width: 100%">
                <el-option label="IPMI" value="IPMI" />
                <el-option label="iDRAC" value="IDRAC" />
                <el-option label="iLO" value="ILO" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="带外地址" prop="bmc_url">
          <el-input v-model="serverForm.bmc_url" placeholder="https://192.168.1.110（留空表示未配置）" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="serverForm.remark" type="textarea" :rows="2" maxlength="255" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveServer">保存</el-button>
      </template>
    </el-dialog>

    <!-- ===== 批量导入 ===== -->
    <el-dialog v-model="importVisible" title="批量导入服务器" width="760px" @closed="resetImport">
      <div class="import-hint">
        <el-icon><InfoFilled /></el-icon>
        <span>支持 .xlsx；按 IP 匹配：已存在的服务器更新有值且发生变化的字段（含密码/私钥），不存在则新增；单元格留空保留原值。单次最多 500 行。</span>
      </div>
      <div class="import-actions">
        <el-button link type="primary" @click="downloadTemplate">
          <el-icon><Download /></el-icon>
          下载导入模板
        </el-button>
        <el-upload
          :auto-upload="false"
          :limit="1"
          accept=".xlsx"
          :show-file-list="false"
          :on-change="onImportFileChange"
          :disabled="importing"
        >
          <el-button :disabled="importing">选择 Excel 文件</el-button>
        </el-upload>
        <span v-if="importFile" class="import-file">{{ importFile.name }}</span>
      </div>

      <div v-if="importResult" class="import-result">
        <div class="import-summary">
          <el-tag type="success">新增 {{ importResult.added }}</el-tag>
          <el-tag type="primary">更新 {{ importResult.updated }}</el-tag>
          <el-tag type="info">未变化 {{ importResult.unchanged }}</el-tag>
          <el-tag type="danger">失败 {{ importResult.failed }}</el-tag>
        </div>
        <el-table :data="importResult.items" border max-height="260" size="small">
          <el-table-column prop="row" label="行号" width="70" align="center" />
          <el-table-column prop="hostname" label="主机名" min-width="130" show-overflow-tooltip />
          <el-table-column prop="ip" label="IP地址" width="130" />
          <el-table-column label="结果" width="90" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="importTagType(row.status)">{{ importStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="说明" min-width="180" show-overflow-tooltip />
        </el-table>
      </div>

      <template #footer>
        <el-button @click="importVisible = false">关闭</el-button>
        <el-button type="primary" :loading="importing" :disabled="!importFile" @click="submitImport">
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <!-- ===== SSH 账号管理 ===== -->
    <el-dialog
      v-model="accountDialogVisible"
      :title="`SSH 账号 - ${accountServer?.hostname || ''}`"
      width="860px"
      @closed="resetAccountDialog"
    >
      <div class="import-hint">
        <el-icon><InfoFilled /></el-icon>
        <span>一台服务器可配置多个 SSH 账号；默认账号用于登录、测试连接与 Agent 部署。点「登录」可用指定账号打开独立终端，密码与私钥不会明文展示。</span>
      </div>
      <div class="import-actions">
        <span v-if="accountServer" class="account-server-info">
          {{ accountServer.ip }} · 端口 {{ accountServer.ssh_port }} · 共 {{ accounts.length }} 个账号
        </span>
        <el-button v-if="canManage" type="primary" size="small" @click="openAccountForm()">
          <el-icon><Plus /></el-icon>
          新增账号
        </el-button>
      </div>

      <el-table :data="accounts" border v-loading="accountsLoading" size="small" max-height="380">
        <el-table-column prop="username" label="SSH用户名" min-width="130" show-overflow-tooltip />
        <el-table-column label="认证方式" width="90" align="center">
          <template #default="{ row }">
            <span v-if="row.has_password">密码</span>
            <span v-else-if="row.has_private_key">密钥</span>
            <span v-else class="text-muted">未配置</span>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" size="small">默认</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || '-' }}</template>
        </el-table-column>
        <el-table-column label="更新时间" width="150">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" align="center">
          <template #default="{ row }">
            <el-button
              v-if="canLogin && (row.has_password || row.has_private_key)"
              type="primary"
              size="small"
              @click="remoteLogin(accountServer, row)"
            >登录</el-button>
            <el-button v-if="canManage && !row.is_default" size="small" @click="setDefaultAccount(row)">
              设为默认
            </el-button>
            <el-button v-if="canManage" type="success" size="small" @click="openAccountForm(row)">编辑</el-button>
            <el-button v-if="canManage" type="danger" size="small" @click="deleteAccount(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!accountsLoading && accounts.length === 0" class="detail-empty account-empty">
        该服务器尚未配置 SSH 账号
      </div>

      <template #footer>
        <el-button @click="accountDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- ===== 新增 / 编辑 SSH 账号 ===== -->
    <el-dialog
      v-model="accountFormVisible"
      :title="accountForm.id ? '编辑 SSH 账号' : '新增 SSH 账号'"
      width="540px"
      append-to-body
      @closed="resetAccountForm"
    >
      <el-form ref="accountFormRef" :model="accountForm" :rules="accountRules" label-width="100px">
        <el-form-item label="SSH用户名" prop="username">
          <el-input v-model="accountForm.username" maxlength="64" placeholder="如 ops、dba" />
        </el-form-item>
        <el-form-item label="认证方式">
          <el-radio-group v-model="accountAuthType">
            <el-radio label="password">密码认证</el-radio>
            <el-radio label="key">密钥认证</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="accountAuthType === 'password'" label="密码">
          <el-input
            v-model="accountForm.password"
            type="password"
            show-password
            :placeholder="accountForm.id && accountForm.has_password ? '留空表示不修改现有密码' : '请输入登录密码'"
          />
          <div v-if="accountForm.id && accountForm.has_private_key" class="field-hint">
            当前为密钥认证，填写密码后将切换为密码认证
          </div>
        </el-form-item>
        <el-form-item v-else label="私钥">
          <el-input
            v-model="accountForm.private_key"
            type="textarea"
            :rows="4"
            :placeholder="accountForm.id && accountForm.has_private_key ? '留空表示不修改现有私钥' : '粘贴私钥内容'"
          />
          <div v-if="accountForm.id && accountForm.has_password" class="field-hint">
            当前为密码认证，填写私钥后将切换为密钥认证
          </div>
        </el-form-item>
        <el-form-item label="默认账号">
          <el-checkbox
            v-model="accountForm.is_default"
            :disabled="!!(accountForm.id && accountForm.is_default)"
          >设为默认账号</el-checkbox>
          <div class="field-hint">默认账号用于服务器登录、测试连接与 Agent 部署</div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="accountForm.remark" maxlength="255" show-word-limit placeholder="如 运维账号 / 数据库账号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="accountFormVisible = false">取消</el-button>
        <el-button type="primary" :loading="accountSaving" @click="saveAccount">保存</el-button>
      </template>
    </el-dialog>

    <!-- ===== SSH 账号批量导入 ===== -->
    <el-dialog v-model="accountImportVisible" title="批量导入 SSH 账号" width="760px" @closed="resetAccountImport">
      <div class="import-hint">
        <el-icon><InfoFilled /></el-icon>
        <span>支持 .xlsx；每行一个账号，同一 IP 可重复出现；SSH 端口需与服务器登记端口一致；新增账号必须填写密码或私钥，更新时留空保留原密码/私钥；同一服务器只能标记一个默认账号。导入前会全量校验，任一行有误则整批不写入，单次最多 500 行。</span>
      </div>
      <div class="import-actions">
        <el-button link type="primary" @click="downloadAccountTemplate">
          <el-icon><Download /></el-icon>
          下载导入模板
        </el-button>
        <el-upload
          :auto-upload="false"
          :limit="1"
          accept=".xlsx"
          :show-file-list="false"
          :on-change="onAccountImportFileChange"
          :disabled="accountImporting"
        >
          <el-button :disabled="accountImporting">选择 Excel 文件</el-button>
        </el-upload>
        <span v-if="accountImportFile" class="import-file">{{ accountImportFile.name }}</span>
      </div>

      <div v-if="accountImportResult" class="import-result">
        <div class="import-summary">
          <el-tag type="success">新增 {{ accountImportResult.added }}</el-tag>
          <el-tag type="primary">更新 {{ accountImportResult.updated }}</el-tag>
          <el-tag type="info">未变化 {{ accountImportResult.unchanged }}</el-tag>
        </div>
        <el-table :data="accountImportResult.items" border max-height="260" size="small">
          <el-table-column prop="row" label="行号" width="70" align="center" />
          <el-table-column prop="ip" label="IP地址" width="130" />
          <el-table-column prop="username" label="SSH用户名" min-width="120" />
          <el-table-column label="结果" width="90" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="importTagType(row.status)">{{ importStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="说明" min-width="180" show-overflow-tooltip />
        </el-table>
      </div>

      <template #footer>
        <el-button @click="accountImportVisible = false">关闭</el-button>
        <el-button
          type="primary"
          :loading="accountImporting"
          :disabled="!accountImportFile"
          @click="submitAccountImport"
        >
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <!-- ===== 登录账号选择 ===== -->
    <el-dialog
      v-model="loginDialogVisible"
      title="选择登录账号"
      width="480px"
      @closed="resetLoginDialog"
    >
      <div class="login-account-hint">
        {{ loginServerRow?.hostname }}（{{ loginServerRow?.ip }}）有 {{ loginCandidates.length }} 个可用 SSH 账号，请选择：
      </div>
      <el-radio-group v-model="loginSelectedId" class="login-account-list">
        <el-radio
          v-for="account in loginCandidates"
          :key="account.id"
          :label="account.id"
          class="login-account-item"
        >
          <span class="login-account-name">{{ account.username }}</span>
          <el-tag v-if="account.is_default" type="success" size="small">默认</el-tag>
          <span class="login-account-auth">{{ account.has_private_key ? '密钥认证' : '密码认证' }}</span>
        </el-radio>
      </el-radio-group>
      <template #footer>
        <el-button @click="loginDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!loginSelectedId" @click="confirmLogin">登录</el-button>
      </template>
    </el-dialog>

    <!-- ===== 系统信息刷新结果 ===== -->
    <el-dialog v-model="refreshResultVisible" title="系统信息刷新结果" width="720px">
      <div class="import-summary">
        <el-tag type="success">成功 {{ refreshSuccessCount }}</el-tag>
        <el-tag type="warning">Agent 离线 {{ refreshOfflineCount }}</el-tag>
        <el-tag type="danger">失败 {{ refreshFailedCount }}</el-tag>
      </div>
      <el-table :data="refreshResults" border size="small" max-height="320">
        <el-table-column prop="hostname" label="主机名" min-width="140" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP地址" width="140" />
        <el-table-column label="结果" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="refreshTagType(row.status)">{{ refreshStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作系统" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.os_distro || '-' }}</template>
        </el-table-column>
        <el-table-column prop="message" label="说明" min-width="200" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <el-button @click="refreshResultVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- ===== 批量安装 Agent ===== -->
    <el-dialog v-model="deployVisible" title="批量安装 Agent（SSH 推送）" width="760px" @closed="resetDeployForm">
      <div class="import-hint" v-if="deployInstalledCount > 0">
        <el-icon><Warning /></el-icon>
        <span>
          所选服务器中有 <b>{{ deployInstalledCount }}</b> 台已发现 Agent
          （在线 {{ deployOnlineCount }} 台，离线 {{ deployOfflineCount }} 台），
          继续部署将覆盖已有安装执行升级。
        </span>
      </div>

      <el-form label-width="120px">
        <el-form-item label="目标服务器">
          <div class="deploy-targets">
            <span class="deploy-count">已选 {{ deployTargets.length }} 台</span>
            <el-table :data="deployTargets" border size="small" max-height="180" style="width: 100%">
              <el-table-column prop="hostname" label="主机名" min-width="130" show-overflow-tooltip />
              <el-table-column prop="ip" label="IP地址" width="130" />
              <el-table-column label="Agent状态" width="110" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.agent_installed && row.agent_online" type="success" size="small">在线</el-tag>
                  <el-tag v-else-if="row.agent_installed" type="warning" size="small">离线</el-tag>
                  <el-tag v-else type="info" size="small">未发现</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-form-item>
        <el-form-item label="安装包">
          <el-select v-model="deployForm.package_id" placeholder="选择已上传的安装包" style="width: 420px">
            <el-option-group label="Docker 镜像包">
              <el-option
                v-for="p in deployDockerPackages"
                :key="p.package_id"
                :label="`${p.version} · ${p.name}`"
                :value="p.package_id"
              />
            </el-option-group>
            <el-option-group label="二进制安装包">
              <el-option
                v-for="p in deployBinaryPackages"
                :key="p.package_id"
                :label="`${p.version} · ${p.name}`"
                :value="p.package_id"
              />
            </el-option-group>
          </el-select>
          <el-button link type="primary" style="margin-left: 8px" @click="router.push('/agents')">
            去上传安装包 →
          </el-button>
        </el-form-item>
        <el-form-item label="部署目录">
          <el-input v-model="deployForm.deploy_dir" placeholder="/etc/srmc-agent" style="width: 420px" />
        </el-form-item>
        <el-form-item label="后端地址">
          <el-input
            v-model="deployForm.server_url"
            placeholder="ws://192.168.12.79:8000/api/ws/agent/"
            style="width: 420px"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="deployVisible = false">取消</el-button>
        <el-button type="primary" :loading="deploySubmitting" @click="submitDeploy">
          创建部署任务
        </el-button>
      </template>
    </el-dialog>

    <!-- ===== 详情抽屉 ===== -->
    <el-drawer v-model="detailVisible" title="服务器详情" size="520px">
      <template v-if="detailRow">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="主机名">{{ detailRow.hostname }}</el-descriptions-item>
          <el-descriptions-item label="IP地址">{{ detailRow.ip }}</el-descriptions-item>
          <el-descriptions-item label="SSH账号">
            <template v-if="detailRow.ssh_account_count">
              {{ detailRow.ssh_account_count }} 个账号（默认 {{ detailRow.username }}，端口 {{ detailRow.ssh_port }}）
            </template>
            <span v-else>未配置（端口 {{ detailRow.ssh_port }}）</span>
          </el-descriptions-item>
          <el-descriptions-item label="认证方式">
            <span v-if="detailRow.has_password">密码</span>
            <span v-else-if="detailRow.has_private_key">密钥</span>
            <span v-else>未配置</span>
          </el-descriptions-item>
          <el-descriptions-item label="操作系统">{{ detailRow.agent_os_distro || (agentOf(detailRow) && agentOf(detailRow).os_distro) || systemLabel(detailRow) }}</el-descriptions-item>
          <el-descriptions-item label="带外管理">
            <template v-if="detailRow.bmc_url">
              <span class="detail-bmc-type">{{ bmcTypeLabel(detailRow.bmc_type) }}</span>
              <a class="bmc-link" :href="detailRow.bmc_url" target="_blank" rel="noopener noreferrer">{{ detailRow.bmc_url }}</a>
            </template>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="备注">{{ detailRow.remark || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detailRow.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatTime(detailRow.updated_at) }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-section" v-if="canViewAgent">
          <div class="detail-title">关联 Agent</div>
          <div v-if="agentsLoading" class="detail-empty">加载中...</div>
          <template v-else-if="agentOf(detailRow)">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="状态">
                <el-tag size="small" :type="agentOf(detailRow).is_online ? 'success' : 'info'">
                  {{ agentOf(detailRow).is_online ? '在线' : '离线' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="发行版">{{ agentOf(detailRow).os_distro || agentOf(detailRow).os || '-' }}</el-descriptions-item>
              <el-descriptions-item label="Agent版本">{{ agentOf(detailRow).agent_version || '-' }}</el-descriptions-item>
              <el-descriptions-item label="最后心跳">{{ formatTime(agentOf(detailRow).last_heartbeat) }}</el-descriptions-item>
            </el-descriptions>
          </template>
          <div v-else class="detail-empty">
            <span>该 IP 尚未安装 Agent</span>
            <el-button v-if="canManage" link type="primary" @click="goDeployAgent(detailRow)">去部署</el-button>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-title">监控摘要</div>
          <template v-if="monitorOf(detailRow)">
            <div class="metric-row" v-if="monitorOf(detailRow).has_data">
              <span>CPU <b>{{ (monitorOf(detailRow).cpu_percent || 0).toFixed(1) }}%</b></span>
              <span>内存 <b>{{ (monitorOf(detailRow).memory_percent || 0).toFixed(1) }}%</b></span>
              <span>磁盘 <b>{{ (monitorOf(detailRow).disk_usage_percent || 0).toFixed(1) }}%</b></span>
            </div>
            <div v-else class="detail-empty">暂无监控指标数据</div>
            <el-button link type="primary" @click="goMonitor(detailRow)">查看监控详情 →</el-button>
          </template>
          <div v-else class="detail-empty">监控数据加载中</div>
        </div>

        <div class="detail-section">
          <div class="detail-title">关联服务</div>
          <div v-if="relatedServices.loading" class="detail-empty">加载中...</div>
          <div v-else-if="relatedServices.total > 0" class="service-related">
            <span>该 IP 上共有 <b>{{ relatedServices.total }}</b> 个服务</span>
            <el-button link type="primary" @click="goServices(detailRow)">查看服务 →</el-button>
          </div>
          <div v-else class="detail-empty">该 IP 暂无关联服务</div>
        </div>
      </template>

      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button
          v-if="canLogin"
          type="primary"
          :loading="loginCheckingId === detailRow?.id"
          @click="handleListLogin(detailRow)"
        >远程登录</el-button>
        <el-button v-if="canManage" type="success" @click="editServer(detailRow)">编辑</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, Download, InfoFilled, Refresh, Warning } from '@element-plus/icons-vue'
import axios from '@/utils/axios'
import { usePermission } from '@/composables/usePermission'
import ListStats from '@/components/ListStats.vue'

const router = useRouter()
const { hasPermission } = usePermission()

const canManage = computed(() => hasPermission('host:manage'))
const canLogin = computed(() => hasPermission('webshell:login'))
const canViewAgent = computed(() => hasPermission('agent:view'))
const canDeployAgent = computed(() => hasPermission('agent:manage'))

const servers = ref([])
const agents = ref([])
const agentsLoaded = ref(false)
const agentsLoading = ref(false)
const monitorServers = ref([])
const selection = ref([])
const statsItems = ref([])
const showAddDialog = ref(false)
const saving = ref(false)
const authType = ref('password')
const hasPassword = ref(false)
const hasPrivateKey = ref(false)
const loading = ref(false)
const refreshing = ref(false)
const refreshResultVisible = ref(false)
const refreshResults = ref([])
const refreshSuccessCount = computed(() => refreshResults.value.filter(i => i.status === 'success').length)
const refreshOfflineCount = computed(() => refreshResults.value.filter(i => i.status === 'offline').length)
const refreshFailedCount = computed(() => refreshResults.value.filter(i => i.status !== 'success' && i.status !== 'offline').length)
const testingIds = ref(new Set())
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const filters = reactive({
  keyword: '',
  osType: '',
  hasBmc: null,
  agentStatus: ''
})

const formRef = ref(null)
const serverForm = reactive({
  id: null,
  hostname: '',
  ip: '',
  ssh_port: 22,
  username: '',
  password: '',
  private_key: '',
  os_type: 'LINUX',
  agent_os_distro: '',
  bmc_type: '',
  bmc_url: '',
  remark: ''
})

const ipValidator = (_rule, value, callback) => {
  if (!value) return callback()
  const ipv4 = /^(\d{1,3}\.){3}\d{1,3}$/
  if (!ipv4.test(value) && !value.includes(':')) {
    return callback(new Error('请输入合法的 IP 地址'))
  }
  callback()
}

const bmcUrlValidator = (_rule, value, callback) => {
  if (!value) return callback()
  if (!/^https?:\/\//i.test(value)) {
    return callback(new Error('带外地址必须以 http:// 或 https:// 开头'))
  }
  callback()
}

const formRules = {
  hostname: [{ required: true, message: '请输入主机名', trigger: 'blur' }],
  ip: [
    { required: true, message: '请输入 IP 地址', trigger: 'blur' },
    { validator: ipValidator, trigger: 'blur' }
  ],
  ssh_port: [{ required: true, message: '请输入 SSH 端口', trigger: 'blur' }],
  username: [{ required: true, message: '请输入 SSH 用户名', trigger: 'blur' }],
  bmc_url: [{ validator: bmcUrlValidator, trigger: 'blur' }]
}

const agentByIp = computed(() => {
  const map = {}
  agents.value.forEach(agent => {
    if (!map[agent.ip]) map[agent.ip] = agent
  })
  return map
})

const monitorById = computed(() => {
  const map = {}
  monitorServers.value.forEach(item => { map[item.id] = item })
  return map
})

function agentOf(row) {
  return agentByIp.value[row?.ip]
}

function monitorOf(row) {
  return monitorById.value[row?.id]
}

function systemLabel(row) {
  return row?.os_type === 'UNIX' ? 'Unix' : 'Linux'
}

// 架构展示与 Agent 管理保持一致
const ARCH_DISPLAY = { amd64: 'x86_64', arm64: 'aarch64' }
function formatArch(value) {
  const s = (value || '').trim()
  if (!s) return ''
  return ARCH_DISPLAY[s.toLowerCase()] || s
}

function bmcTypeLabel(type) {
  return { IPMI: 'IPMI', IDRAC: 'iDRAC', ILO: 'iLO', OTHER: '其他' }[type] || '带外'
}

function formatTime(value) {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '-'
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function apiError(error, fallback) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(i => i.msg).join('；')
  return error?.response?.data?.message || fallback
}

function resetForm() {
  Object.assign(serverForm, {
    id: null,
    hostname: '',
    ip: '',
    ssh_port: 22,
    username: '',
    password: '',
    private_key: '',
    os_type: 'LINUX',
    agent_os_distro: '',
    bmc_type: '',
    bmc_url: '',
    remark: ''
  })
  authType.value = 'password'
  hasPassword.value = false
  hasPrivateKey.value = false
  formRef.value?.clearValidate()
}

function openCreateDialog() {
  resetForm()
  showAddDialog.value = true
}

function editServer(row) {
  if (!row) return
  Object.assign(serverForm, {
    id: row.id,
    hostname: row.hostname,
    ip: row.ip,
    ssh_port: row.ssh_port,
    username: row.username,
    password: '',
    private_key: '',
    os_type: row.os_type || 'LINUX',
    agent_os_distro: row.agent_os_distro || '',
    bmc_type: row.bmc_type || '',
    bmc_url: row.bmc_url || '',
    remark: row.remark || ''
  })
  hasPassword.value = !!row.has_password
  hasPrivateKey.value = !!row.has_private_key
  authType.value = row.has_password ? 'password' : (row.has_private_key ? 'key' : 'password')
  showAddDialog.value = true
}

function buildPayload() {
  const payload = {
    hostname: serverForm.hostname.trim(),
    ip: serverForm.ip.trim(),
    ssh_port: Number(serverForm.ssh_port) || 22,
    username: serverForm.username.trim(),
    os_type: serverForm.os_type,
    bmc_type: serverForm.bmc_type || null,
    bmc_url: serverForm.bmc_url.trim() || null,
    remark: serverForm.remark.trim() || null
  }
  // 只在用户实际填写时提交凭据，避免编辑时把原密码/私钥清空
  if (authType.value === 'password' && serverForm.password) {
    payload.password = serverForm.password
  }
  if (authType.value === 'key' && serverForm.private_key) {
    payload.private_key = serverForm.private_key
  }
  return payload
}

async function saveServer() {
  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }

  if (!serverForm.id && authType.value === 'password' && !serverForm.password) {
    ElMessage.warning('新增服务器请填写登录密码')
    return
  }
  if (!serverForm.id && authType.value === 'key' && !serverForm.private_key) {
    ElMessage.warning('新增服务器请填写私钥')
    return
  }
  if (serverForm.id && authType.value === 'password' && !serverForm.password && !hasPassword.value && !hasPrivateKey.value) {
    ElMessage.warning('当前服务器尚未配置凭据，请填写密码')
    return
  }

  saving.value = true
  try {
    const payload = buildPayload()
    const result = serverForm.id
      ? await axios.put(`/api/servers/${serverForm.id}`, payload)
      : await axios.post('/api/servers', payload)
    if (result.data.code === 0) {
      ElMessage.success(serverForm.id ? '更新成功' : '创建成功')
      showAddDialog.value = false
      await loadServers()
    } else {
      ElMessage.error(result.data.message || '操作失败')
    }
  } catch (error) {
    ElMessage.error(apiError(error, '操作失败'))
  } finally {
    saving.value = false
  }
}

async function loadServers() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      keyword: filters.keyword.trim() || undefined
    }
    if (filters.osType) params.os_type = filters.osType
    if (filters.hasBmc === true || filters.hasBmc === false) params.has_bmc = filters.hasBmc
    if (filters.agentStatus) params.agent_status = filters.agentStatus

    const response = await axios.get('/api/servers', { params })
    if (response.data.code === 0) {
      const data = response.data.data
      servers.value = data.items
      total.value = data.total
      page.value = data.page
      pageSize.value = data.page_size

      const totalAll = data.total_all ?? data.total
      const hasFilter = !!(
        filters.keyword.trim() || filters.osType ||
        filters.hasBmc === true || filters.hasBmc === false || filters.agentStatus
      )
      const items = [{ label: '服务器总数', value: `${totalAll} 台` }]
      if (hasFilter) items.push({ label: '筛选结果', value: `${total.value} 台` })
      items.push({ label: '本页', value: `${servers.value.length} 条` })
      statsItems.value = items
    }
  } catch (error) {
    ElMessage.error(apiError(error, '加载服务器列表失败'))
  } finally {
    loading.value = false
  }
}

// Agent 数据仅在打开详情时按需加载，列表页不再请求 Agent 状态
async function loadAgents() {
  if (!canViewAgent.value || agentsLoaded.value || agentsLoading.value) return
  agentsLoading.value = true
  try {
    const res = await axios.get('/api/agents/')
    if (res.data.code === 0) {
      agents.value = res.data.data || []
      agentsLoaded.value = true
    }
  } catch (e) {
    agents.value = []
  } finally {
    agentsLoading.value = false
  }
}

async function loadMonitorServers() {
  try {
    const res = await axios.get('/api/monitor/servers')
    monitorServers.value = res.data?.data || []
  } catch (e) {
    monitorServers.value = []
  }
}

function handleSearch() {
  page.value = 1
  loadServers()
}

function resetFilters() {
  filters.keyword = ''
  filters.osType = ''
  filters.hasBmc = null
  filters.agentStatus = ''
  page.value = 1
  loadServers()
}

function handlePageChange(nextPage) {
  page.value = nextPage
  loadServers()
}

function handleSizeChange(nextSize) {
  pageSize.value = nextSize
  page.value = 1
  loadServers()
}

function onSelectionChange(rows) {
  selection.value = rows
}

function handleRowClick(row, _column, event) {
  // 点击行内按钮/链接/多选框时不打开详情，避免与操作冲突
  if (event?.target?.closest('button, a, .el-checkbox, .el-table-column--selection')) return
  openDetail(row)
}

async function batchDelete() {
  if (!selection.value.length) return
  const names = selection.value.slice(0, 5).map(s => s.hostname).join('、')
  const more = selection.value.length > 5 ? ` 等 ${selection.value.length} 台` : ''
  try {
    await ElMessageBox.confirm(
      `确定删除 ${names}${more}？删除后不可恢复。`,
      '批量删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch (e) {
    return
  }
  try {
    const ids = selection.value.map(s => s.id)
    const result = await axios.post('/api/servers/batch-delete', { ids })
    if (result.data.code === 0) {
      const data = result.data.data
      if (data.failed_count) {
        ElMessage.warning(`成功删除 ${data.success_count} 台，失败 ${data.failed_count} 台`)
      } else {
        ElMessage.success(`成功删除 ${data.success_count} 台`)
      }
      selection.value = []
      await loadServers()
    } else {
      ElMessage.error(result.data.message || '批量删除失败')
    }
  } catch (error) {
    ElMessage.error(apiError(error, '批量删除失败'))
  }
}

async function refreshSystemInfo() {
  if (!selection.value.length || refreshing.value) return
  refreshing.value = true
  try {
    const ids = selection.value.map(s => s.id)
    const result = await axios.post('/api/servers/refresh-system-info', { ids })
    if (result.data.code === 0) {
      const data = result.data.data
      refreshResults.value = data.items || []
      refreshResultVisible.value = true
      const offline = data.offline_count || 0
      if (data.success_count === data.total) {
        ElMessage.success(`已刷新 ${data.success_count} 台服务器的系统信息`)
      } else if (data.success_count > 0) {
        ElMessage.warning(`刷新完成：成功 ${data.success_count} 台，离线 ${offline} 台，失败 ${data.failed_count} 台`)
      } else {
        ElMessage.warning(`未能刷新系统信息：离线 ${offline} 台，失败 ${data.failed_count} 台`)
      }
      if (data.success_count > 0) await loadServers()
    } else {
      ElMessage.error(result.data.message || '刷新系统信息失败')
    }
  } catch (error) {
    ElMessage.error(apiError(error, '刷新系统信息失败'))
  } finally {
    refreshing.value = false
  }
}

function refreshStatusLabel(status) {
  return { success: '成功', offline: 'Agent 离线', no_agent: '未安装 Agent', failed: '失败' }[status] || status
}

function refreshTagType(status) {
  return { success: 'success', offline: 'warning', no_agent: 'info', failed: 'danger' }[status] || 'info'
}

async function testConnection(row) {
  if (testingIds.value.has(row.id)) return
  testingIds.value = new Set(testingIds.value).add(row.id)
  try {
    const result = await axios.post(`/api/servers/${row.id}/test-connection`)
    if (result.data.code === 0) {
      ElMessage.success(`连接成功：${row.hostname}`)
    } else {
      ElMessage.error(result.data.message || '连接失败')
    }
  } catch (error) {
    ElMessage.error(apiError(error, '连接失败'))
  } finally {
    const next = new Set(testingIds.value)
    next.delete(row.id)
    testingIds.value = next
  }
}

// 列表/详情「登录」：先获取当前用户有权使用的账号，再决定直连或让用户选择
const loginCheckingId = ref(null)
const loginDialogVisible = ref(false)
const loginServerRow = ref(null)
const loginCandidates = ref([])
const loginSelectedId = ref(null)

async function handleListLogin(row) {
  if (!row) return
  loginCheckingId.value = row.id
  try {
    const res = await axios.get(`/api/servers/${row.id}/usable-ssh-accounts`)
    if (res.data.code !== 0) {
      ElMessage.error(res.data.message || '获取可用 SSH 账号失败')
      return
    }
    const data = res.data.data || {}
    const items = data.items || []
    if (items.length === 0) {
      ElMessage.warning(data.message || '没有可用的 SSH 账号，请先在 SSH 账号管理中配置')
      return
    }
    // 仅一个可用账号：直接登录，不再假设默认账号一定可用
    if (items.length === 1) {
      remoteLogin(row, items[0])
      return
    }
    loginServerRow.value = row
    loginCandidates.value = items
    // 默认账号在可用列表中时优先选中
    loginSelectedId.value = (items.find(a => a.is_default) || items[0]).id
    loginDialogVisible.value = true
  } catch (error) {
    ElMessage.error(apiError(error, '获取可用 SSH 账号失败'))
  } finally {
    loginCheckingId.value = null
  }
}

function resetLoginDialog() {
  loginServerRow.value = null
  loginCandidates.value = []
  loginSelectedId.value = null
}

function confirmLogin() {
  const account = loginCandidates.value.find(a => a.id === loginSelectedId.value)
  if (!account) {
    ElMessage.warning('请选择登录账号')
    return
  }
  loginDialogVisible.value = false
  remoteLogin(loginServerRow.value, account)
}

function remoteLogin(row, account = null) {
  if (!row) return
  const name = encodeURIComponent(row.hostname || row.ip)
  const from = encodeURIComponent('/servers')
  let url = `/shell?server_id=${row.id}&serverName=${name}&from=${from}`
  // 指定账号登录：Shell 通过 account_id 选择该服务器的对应 SSH 账号
  if (account) {
    url += `&account_id=${account.id}&accountName=${encodeURIComponent(account.username || '')}`
  }
  window.open(url, '_blank')
}

function goDeployAgent(row) {
  if (!row) return
  router.push({ path: '/agents', query: { deploy_ip: row.ip } })
}

function goMonitor(row) {
  if (!row) return
  router.push({ path: '/monitoring', query: { server_id: row.id } })
}

function goServices(row) {
  if (!row) return
  router.push({ path: '/services', query: { ip: row.ip } })
}

// ===== 批量安装 Agent（只传 server_ids，凭据由后端从服务器记录读取）=====
const deployVisible = ref(false)
const deploySubmitting = ref(false)
const deployTargets = ref([])
const deployForm = reactive({
  package_id: '',
  deploy_dir: '/etc/srmc-agent',
  server_url: ''
})
const deployDockerPackages = ref([])
const deployBinaryPackages = ref([])

const deployInstalledCount = computed(() => deployTargets.value.filter(r => r.agent_installed).length)
const deployOnlineCount = computed(() => deployTargets.value.filter(r => r.agent_installed && r.agent_online).length)
const deployOfflineCount = computed(() => deployTargets.value.filter(r => r.agent_installed && !r.agent_online).length)

function defaultServerUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  // Agent 是独立进程，不能走前端 dev/nginx 端口，需直连后端 8000；
  // 与 Agent 管理页的默认值保持一致。
  const port = window.location.port
  if (port === '8000' || port === '') {
    return `${proto}://${window.location.host}/api/ws/agent/`
  }
  return `${proto}://${window.location.hostname}:8000/api/ws/agent/`
}

function openDeployDialog() {
  if (!selection.value.length) {
    ElMessage.warning('请先勾选要安装 Agent 的服务器')
    return
  }
  deployTargets.value = selection.value.slice()
  deployForm.package_id = ''
  deployForm.deploy_dir = '/etc/srmc-agent'
  deployForm.server_url = defaultServerUrl()
  deployVisible.value = true
  loadDeployPackages()
}

function resetDeployForm() {
  deployTargets.value = []
  deployForm.package_id = ''
  deploySubmitting.value = false
  deployDockerPackages.value = []
  deployBinaryPackages.value = []
}

async function loadDeployPackages() {
  try {
    const res = await axios.get('/api/agent-deploy/packages')
    if (res.data.code === 0) {
      const list = res.data.data || []
      deployDockerPackages.value = list.filter(p => p.package_type === 'docker')
      deployBinaryPackages.value = list.filter(p => p.package_type === 'binary')
    }
  } catch (e) {
    deployDockerPackages.value = []
    deployBinaryPackages.value = []
  }
}

async function submitDeploy() {
  if (!deployForm.package_id) {
    ElMessage.warning('请选择安装包（如未上传，请先到批量部署任务页上传）')
    return
  }
  if (!deployForm.server_url.startsWith('ws')) {
    ElMessage.warning('后端地址需以 ws:// 或 wss:// 开头')
    return
  }
  const installedTip = deployInstalledCount.value > 0
    ? `其中 ${deployInstalledCount.value} 台已发现 Agent，将按覆盖升级处理。`
    : ''
  try {
    await ElMessageBox.confirm(
      `将向 ${deployTargets.value.length} 台服务器推送 Agent 安装包（目录 ${deployForm.deploy_dir}）。${installedTip}` +
      '任务创建后由后台异步执行。',
      '部署确认',
      { type: 'warning', confirmButtonText: '确认创建', cancelButtonText: '取消' }
    )
  } catch (e) {
    return
  }

  deploySubmitting.value = true
  try {
    const res = await axios.post('/api/agent-deploy/tasks', {
      package_id: deployForm.package_id,
      deploy_dir: deployForm.deploy_dir,
      server_url: deployForm.server_url,
      server_ids: deployTargets.value.map(r => r.id)
    })
    if (res.data.code === 0) {
      ElMessage.success('部署任务已创建，Agent 上线需等待首次心跳上报')
      deployVisible.value = false
      router.push('/agent-deploy-tasks')
    } else {
      ElMessage.error(res.data.message || '创建部署任务失败')
    }
  } catch (error) {
    ElMessage.error(apiError(error, '创建部署任务失败'))
  } finally {
    deploySubmitting.value = false
  }
}

// ===== 详情抽屉 =====
const detailVisible = ref(false)
const detailRow = ref(null)
const relatedServices = reactive({ loading: false, total: 0 })

async function openDetail(row) {
  detailRow.value = row
  detailVisible.value = true
  relatedServices.total = 0
  relatedServices.loading = true
  loadAgents()
  try {
    const res = await axios.get('/api/services', { params: { ip: row.ip, page: 1, size: 5 } })
    relatedServices.total = res.data?.data?.total || 0
  } catch (e) {
    relatedServices.total = 0
  } finally {
    relatedServices.loading = false
  }
}

// ===== 批量导入 =====
const importVisible = ref(false)
const importing = ref(false)
const importFile = ref(null)
const importResult = ref(null)

function openImportDialog() {
  resetImport()
  importVisible.value = true
}

function resetImport() {
  importFile.value = null
  importResult.value = null
  importing.value = false
}

function onImportFileChange(uploadFile) {
  importFile.value = uploadFile?.raw || null
  importResult.value = null
}

async function downloadTemplate() {
  try {
    const res = await axios.get('/api/servers/import/template', { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = 'server-import-template.xlsx'
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(apiError(error, '模板下载失败'))
  }
}

async function submitImport() {
  if (!importFile.value) return
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    const res = await axios.post('/api/servers/batch-import', formData)
    if (res.data.code === 0) {
      importResult.value = res.data.data
      const data = res.data.data
      if (data.added > 0 || data.updated > 0) {
        ElMessage.success(`导入完成：新增 ${data.added} 条，更新 ${data.updated} 条`)
        await loadServers()
      } else {
        ElMessage.warning(`导入完成：无新增或更新（未变化 ${data.unchanged}，失败 ${data.failed}）`)
      }
    } else {
      ElMessage.error(res.data.message || '导入失败')
    }
  } catch (error) {
    ElMessage.error(apiError(error, '导入失败'))
  } finally {
    importing.value = false
  }
}

function importStatusLabel(status) {
  return { added: '新增', updated: '更新', unchanged: '未变化', failed: '失败' }[status] || status
}

function importTagType(status) {
  return { added: 'success', updated: 'primary', unchanged: 'info', failed: 'danger' }[status] || 'info'
}

// ===== SSH 账号管理 =====
const accountDialogVisible = ref(false)
const accountServer = ref(null)
const accounts = ref([])
const accountsLoading = ref(false)
const accountFormVisible = ref(false)
const accountSaving = ref(false)
const accountFormRef = ref(null)
const accountAuthType = ref('password')
const accountForm = reactive({
  id: null,
  username: '',
  password: '',
  private_key: '',
  is_default: false,
  has_password: false,
  has_private_key: false,
  remark: ''
})
const accountRules = {
  username: [{ required: true, message: '请输入 SSH 用户名', trigger: 'blur' }]
}

function openAccountDialog(row) {
  if (!row) return
  accountServer.value = row
  accounts.value = []
  accountDialogVisible.value = true
  loadAccounts(row.id)
}

function resetAccountDialog() {
  accountServer.value = null
  accounts.value = []
  accountsLoading.value = false
  accountFormVisible.value = false
}

async function loadAccounts(serverId) {
  accountsLoading.value = true
  try {
    const res = await axios.get(`/api/servers/${serverId}/ssh-accounts`)
    if (res.data.code === 0) {
      accounts.value = res.data.data.items || []
      if (res.data.data.server) accountServer.value = { ...accountServer.value, ...res.data.data.server }
    } else {
      ElMessage.error(res.data.message || '加载 SSH 账号失败')
    }
  } catch (error) {
    ElMessage.error(apiError(error, '加载 SSH 账号失败'))
  } finally {
    accountsLoading.value = false
  }
}

function openAccountForm(row = null) {
  resetAccountForm()
  if (row) {
    Object.assign(accountForm, {
      id: row.id,
      username: row.username,
      is_default: !!row.is_default,
      has_password: !!row.has_password,
      has_private_key: !!row.has_private_key,
      remark: row.remark || ''
    })
    accountAuthType.value = row.has_private_key ? 'key' : 'password'
  } else {
    // 该服务器还没有账号时，新账号自动成为默认账号
    accountForm.is_default = accounts.value.length === 0
  }
  accountFormVisible.value = true
}

function resetAccountForm() {
  Object.assign(accountForm, {
    id: null,
    username: '',
    password: '',
    private_key: '',
    is_default: false,
    has_password: false,
    has_private_key: false,
    remark: ''
  })
  accountAuthType.value = 'password'
  accountSaving.value = false
  accountFormRef.value?.clearValidate()
}

async function saveAccount() {
  try {
    await accountFormRef.value.validate()
  } catch (e) {
    return
  }
  const hasCredential = accountForm.password.trim() || accountForm.private_key.trim()
  if (!accountForm.id && !hasCredential) {
    ElMessage.warning('新增账号请填写密码或私钥')
    return
  }

  const payload = {
    username: accountForm.username.trim(),
    is_default: !!accountForm.is_default,
    remark: accountForm.remark.trim() || null
  }
  if (accountAuthType.value === 'password' && accountForm.password) {
    payload.password = accountForm.password
  }
  if (accountAuthType.value === 'key' && accountForm.private_key) {
    payload.private_key = accountForm.private_key
  }

  accountSaving.value = true
  try {
    const base = `/api/servers/${accountServer.value.id}/ssh-accounts`
    const res = accountForm.id
      ? await axios.put(`${base}/${accountForm.id}`, payload)
      : await axios.post(base, payload)
    if (res.data.code === 0) {
      ElMessage.success(accountForm.id ? '账号已更新' : '账号已添加')
      accountFormVisible.value = false
      await loadAccounts(accountServer.value.id)
      await loadServers()
    } else {
      ElMessage.error(res.data.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error(apiError(error, '保存失败'))
  } finally {
    accountSaving.value = false
  }
}

async function setDefaultAccount(row) {
  try {
    const res = await axios.put(`/api/servers/${accountServer.value.id}/ssh-accounts/${row.id}`, {
      is_default: true
    })
    if (res.data.code === 0) {
      ElMessage.success(`已将 ${row.username} 设为默认账号`)
      await loadAccounts(accountServer.value.id)
      await loadServers()
    } else {
      ElMessage.error(res.data.message || '设置失败')
    }
  } catch (error) {
    ElMessage.error(apiError(error, '设置失败'))
  }
}

async function deleteAccount(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除账号 ${row.username}？该操作不可恢复。`,
      '删除 SSH 账号',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch (e) {
    return
  }
  try {
    const res = await axios.delete(`/api/servers/${accountServer.value.id}/ssh-accounts/${row.id}`)
    if (res.data.code === 0) {
      ElMessage.success('账号已删除')
      await loadAccounts(accountServer.value.id)
      await loadServers()
    } else {
      ElMessage.error(res.data.message || '删除失败')
    }
  } catch (error) {
    ElMessage.error(apiError(error, '删除失败'))
  }
}

// ===== SSH 账号批量导入 =====
const accountImportVisible = ref(false)
const accountImporting = ref(false)
const accountImportFile = ref(null)
const accountImportResult = ref(null)

function openAccountImportDialog() {
  resetAccountImport()
  accountImportVisible.value = true
}

function resetAccountImport() {
  accountImportFile.value = null
  accountImportResult.value = null
  accountImporting.value = false
}

function onAccountImportFileChange(uploadFile) {
  accountImportFile.value = uploadFile?.raw || null
  accountImportResult.value = null
}

async function downloadAccountTemplate() {
  try {
    const res = await axios.get('/api/servers/ssh-accounts/import/template', { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = 'ssh-account-import-template.xlsx'
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(apiError(error, '模板下载失败'))
  }
}

async function submitAccountImport() {
  if (!accountImportFile.value) return
  accountImporting.value = true
  try {
    const formData = new FormData()
    formData.append('file', accountImportFile.value)
    const res = await axios.post('/api/servers/ssh-accounts/batch-import', formData)
    if (res.data.code === 0) {
      accountImportResult.value = res.data.data
      const data = res.data.data
      ElMessage.success(`导入完成：新增 ${data.added} 条，更新 ${data.updated} 条，未变化 ${data.unchanged} 条`)
      await loadServers()
      if (accountDialogVisible.value && accountServer.value) {
        await loadAccounts(accountServer.value.id)
      }
    } else {
      ElMessage.error(res.data.message || '导入失败')
    }
  } catch (error) {
    // 后端统一错误体为 {code, message}，兼容标准 FastAPI 的 detail
    const detail = error?.response?.data?.detail || error?.response?.data?.message
    // 整批校验失败：展示全部错误行，提示修正后重新导入
    if (error?.response?.status === 400 && typeof detail === 'string') {
      ElMessageBox.alert(detail, '导入校验未通过', { type: 'warning', confirmButtonText: '知道了' })
    } else {
      ElMessage.error(apiError(error, '导入失败'))
    }
  } finally {
    accountImporting.value = false
  }
}

onMounted(() => {
  loadServers()
  loadMonitorServers()
})
</script>

<style scoped>
.servers-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

.page-subtitle {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--app-text-3);
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.host-link {
  color: var(--el-color-primary);
  cursor: pointer;
  word-break: break-all;
  line-height: 1.4;
}

.host-link:hover {
  text-decoration: underline;
}

.servers-table :deep(tbody tr) {
  cursor: pointer;
}

.cell-wrap {
  white-space: normal;
  word-break: break-all;
  line-height: 1.4;
}

.field-hint {
  width: 100%;
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--app-text-3);
}

.account-empty-link {
  color: var(--el-color-primary);
  cursor: pointer;
}

.account-empty-link:hover {
  text-decoration: underline;
}

.text-muted {
  color: var(--app-text-3);
}

.account-server-info {
  font-size: 13px;
  color: var(--app-text-2);
}

.account-empty {
  padding: 16px 0 4px;
}

.login-account-hint {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--app-text-2);
}

.login-account-list {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.login-account-item {
  width: 100%;
  margin-right: 0;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}

.login-account-item + .login-account-item {
  margin-top: 10px;
}

.login-account-name {
  margin-right: 8px;
  font-weight: 600;
}

.login-account-auth {
  margin-left: 8px;
  font-size: 12px;
  color: var(--app-text-3);
}

.bmc-link {
  color: var(--el-color-primary);
  text-decoration: none;
  font-size: 12px;
}

.bmc-link:hover {
  text-decoration: underline;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.import-hint {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 10px 12px;
  margin-bottom: 12px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--app-text-2);
  background: var(--app-panel-soft);
  border: 1px solid var(--app-border);
  border-radius: 6px;
}

.import-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.import-file {
  font-size: 12px;
  color: var(--app-text-2);
}

.import-result {
  margin-top: 10px;
}

.import-summary {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.deploy-targets {
  width: 100%;
}

.deploy-count {
  display: inline-block;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--app-text-3);
}

.detail-section {
  margin-top: 18px;
}

.detail-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--app-text-1);
}

.detail-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--app-text-3);
}

.metric-row {
  display: flex;
  gap: 18px;
  font-size: 12px;
  color: var(--app-text-2);
  margin-bottom: 8px;
}

.metric-row b {
  color: var(--app-text-1);
}

.service-related {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--app-text-2);
}

.detail-bmc-type {
  margin-right: 8px;
  font-size: 12px;
  color: var(--app-text-3);
}
</style>
