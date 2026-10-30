<template>
  <div class="usage-guide-page">
    <div class="guide-header">
        <h1>使用说明</h1>
        <p>服务资源管理中心 (SRMC) - 一站式服务管理平台</p>
      </div>

    <div class="guide-content">
      <div class="guide-section">
        <h2>一、系统概述</h2>
        <p>SRMC (Service Resource Management Center) 是一个服务资源管理平台，提供项目管理、服务管理、服务器管理、监控中心等功能模块，帮助团队高效管理和运维各类服务。</p>
      </div>

      <div class="guide-section">
        <h2>二、部署方式说明</h2>
        <p>系统支持四种部署方式，根据服务类型选择合适的部署方式：</p>
        
        <div class="deploy-cards">
          <div class="deploy-card">
            <div class="deploy-icon host">🖥️</div>
            <h3>主机进程部署 (PROCESS)</h3>
            <p>直接在物理主机上运行的服务进程，通过进程名/端口/PID 文件检测状态。</p>
            <ul>
              <li><strong>适用场景：</strong>传统 Java/Go/Python 服务、自定义脚本部署</li>
              <li><strong>必填字段：</strong>程序路径、启动脚本、停止脚本</li>
              <li><strong>状态检测：</strong>PID 文件 → 端口 → StartCmd 脚本解析 → 进程名</li>
              <li><strong>启停方式：</strong>执行用户自定义脚本</li>
            </ul>
          </div>

          <div class="deploy-card">
            <div class="deploy-icon host">🏠</div>
            <h3>主机命令部署 (HOST)</h3>
            <p>主机上通过 systemd 管理或命令启动的服务。</p>
            <ul>
              <li><strong>适用场景：</strong>systemd 管理的服务、标准系统服务</li>
              <li><strong>必填字段：</strong>程序路径</li>
              <li><strong>状态检测：</strong>同 PROCESS 检测链</li>
            </ul>
          </div>

          <div class="deploy-card">
            <div class="deploy-icon docker">🐳</div>
            <h3>Docker容器部署 (DOCKER)</h3>
            <p>单个 Docker 容器运行的服务，系统通过 docker inspect 自动管理。</p>
            <ul>
              <li><strong>适用场景：</strong>单容器应用（Nginx、MySQL、Redis 等）</li>
              <li><strong>必填字段：</strong>程序路径、容器名称</li>
              <li><strong>启停命令：</strong>docker start/stop/restart {容器名称}</li>
              <li><strong>日志查看：</strong>docker logs -f</li>
            </ul>
          </div>

          <div class="deploy-card">
            <div class="deploy-icon compose">📦</div>
            <h3>Docker Compose部署 (DOCKER_COMPOSE)</h3>
            <p>使用 docker-compose 编排的多容器应用，系统自动管理整个 Compose 项目。</p>
            <ul>
              <li><strong>适用场景：</strong>多容器应用（含数据库、中间件、前端等）</li>
              <li><strong>必填字段：</strong>程序路径（docker-compose.yml 所在目录）</li>
              <li><strong>启停命令：</strong>docker compose up -d / down / restart</li>
              <li><strong>状态检测：</strong>两种方式互为兜底（docker inspect 单容器 / docker ps --filter compose.project.config_files）</li>
              <li><strong>注意：</strong>compose 文件建议配唯一顶层 `name` 字段</li>
            </ul>
          </div>
        </div>
      </div>

      <div class="guide-section">
        <h2>三、服务管理操作</h2>
        
        <div class="guide-subsection">
          <h3>3.1 新增服务</h3>
          <ol>
            <li>点击"服务管理"页面的"新增服务"按钮</li>
            <li>填写基本信息：项目、子系统、程序分类、功能描述</li>
            <li>选择部署方式（主机部署 / Docker容器 / Docker Compose）</li>
            <li>根据部署方式填写对应字段</li>
            <li>点击"保存"完成创建</li>
          </ol>
        </div>

        <div class="guide-subsection">
          <h3>3.2 启动/停止/重启服务</h3>
          <p>在服务列表中，点击对应服务行的「启动」「停止」「重启」按钮即可操作。系统优先通过 Agent（WebSocket）在目标服务器上执行，Agent 离线时回退到 SSH 直连执行。服务运行状态完全由 Agent 上报及心跳判断，Agent 离线时状态显示为「未知」，<strong>不会</strong>通过 SSH 探测状态。</p>
          <ul>
            <li>操作会自动记录到审计日志（见 §五）</li>
            <li>如果 Agent 在线，操作几乎实时执行；离线时走 SSH，略有延迟</li>
            <li>Docker Compose 部署的服务操作作用于<strong>整个 compose 项目</strong>的全部容器</li>
          </ul>
        </div>

        <div class="guide-subsection">
          <h3>3.3 查看服务详情</h3>
          <p>点击服务列表中的「详情」按钮（或服务名称），弹出详情弹窗，包含：</p>
          <ul>
            <li><strong>基本信息：</strong>项目、子系统、程序分类、功能描述、对应模块</li>
            <li><strong>部署信息：</strong>部署方式、容器名称、程序路径、启停脚本</li>
            <li><strong>主机信息：</strong>IP 地址、SSH 端口、用户名、Agent 状态（在线/离线/未关联）</li>
            <li><strong>运行状态：</strong>当前状态（运行中/已停止/部分运行）、状态最后更新时间</li>
            <li><strong>停止时间：</strong>仅当服务处于「已停止」状态时显示</li>
            <li><strong>远程终端：</strong>内嵌 Web 终端（xterm.js），自动 cd 到程序路径</li>
            <li><strong>实时日志：</strong>通过 WebSocket 流式查看服务日志（tail -f）</li>
            <li><strong>查看操作记录：</strong>一键跳转到审计日志，自动带入当前服务的筛选条件，只显示该服务的所有历史操作</li>
          </ul>
        </div>
      </div>

      <div class="guide-section">
        <h2>四、导入/导出功能</h2>
        
        <div class="guide-subsection">
          <h3>4.1 导入服务</h3>
          <ol>
            <li>点击"导入服务"菜单进入导入页面</li>
            <li>下载导入模板，按照模板格式填写数据（每行一个服务）</li>
            <li>选择项目和程序分类</li>
            <li>上传 Excel 文件，系统自动识别部署方式并校验字段</li>
            <li>查看导入结果（成功/失败/跳过），处理失败数据</li>
            <li>导入后系统自动尝试将新增服务关联到同 IP 的在线 Agent</li>
          </ol>
          <p><strong>导入回滚：</strong>每次导入生成一个批次记录，可在导入页面将该批次的全部新增服务删除（回滚）。</p>
        </div>

        <div class="guide-subsection">
          <h3>4.2 导出服务</h3>
          <ol>
            <li>点击"导出服务"菜单进入导出页面</li>
            <li>选择项目和子系统（可选）</li>
            <li>点击"导出"按钮，系统按程序分类生成Excel文件</li>
            <li>文件名格式：{项目名}-{子系统名}_服务列表.xlsx</li>
          </ol>
        </div>
      </div>

      <div class="guide-section">
        <h2>五、模板使用说明</h2>
        <p>模板包含完整的字段列表，用于标准化导入数据。模板中的示例数据展示了四种部署方式的填写格式。</p>
        
        <h3>字段说明</h3>
        <table class="field-table">
          <thead>
            <tr>
              <th>字段名</th>
              <th>说明</th>
              <th>主机进程 (PROCESS)</th>
              <th>主机命令 (HOST)</th>
              <th>Docker容器 (DOCKER)</th>
              <th>Docker Compose (DOCKER_COMPOSE)</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>功能描述</td>
              <td>服务的功能说明</td>
              <td>必填</td>
              <td>必填</td>
              <td>必填</td>
              <td>必填</td>
            </tr>
            <tr>
              <td>对应模块</td>
              <td>服务所属模块</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
            </tr>
            <tr>
              <td>IP地址</td>
              <td>服务器IP</td>
              <td>必填</td>
              <td>必填</td>
              <td>必填</td>
              <td>必填</td>
            </tr>
            <tr>
              <td>SSH端口</td>
              <td>SSH连接端口，默认22</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
            </tr>
            <tr>
              <td>用户名</td>
              <td>SSH登录用户名</td>
              <td>必填</td>
              <td>必填</td>
              <td>必填</td>
              <td>必填</td>
            </tr>
            <tr>
              <td>密码</td>
              <td>SSH登录密码</td>
              <td>必填</td>
              <td>必填</td>
              <td>必填</td>
              <td>必填</td>
            </tr>
            <tr>
              <td>程序路径</td>
              <td>代码或 docker-compose.yml 所在目录</td>
              <td>必填</td>
              <td>必填</td>
              <td>必填</td>
              <td>必填</td>
            </tr>
            <tr>
              <td>启动脚本</td>
              <td>启动命令或脚本路径</td>
              <td>必填</td>
              <td>不填</td>
              <td>不填</td>
              <td>不填</td>
            </tr>
            <tr>
              <td>停止脚本</td>
              <td>停止命令或脚本路径</td>
              <td>必填</td>
              <td>不填</td>
              <td>不填</td>
              <td>不填</td>
            </tr>
            <tr>
              <td>日志路径</td>
              <td>日志文件或目录路径</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
            </tr>
            <tr>
              <td>端口</td>
              <td>服务端口号</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
            </tr>
            <tr>
              <td>部署方式</td>
              <td>PROCESS / HOST / DOCKER / DOCKER_COMPOSE</td>
              <td>-</td>
              <td>-</td>
              <td>-</td>
              <td>-</td>
            </tr>
            <tr>
              <td>容器名称</td>
              <td>Docker 容器名称（用于 docker start/stop/restart）</td>
              <td>不填</td>
              <td>不填</td>
              <td>必填</td>
              <td>不填</td>
            </tr>
            <tr>
              <td>镜像名称</td>
              <td>Docker 镜像名称</td>
              <td>不填</td>
              <td>不填</td>
              <td>选填</td>
              <td>不填</td>
            </tr>
            <tr>
              <td>端口映射</td>
              <td>端口映射配置，如 8080:80</td>
              <td>不填</td>
              <td>不填</td>
              <td>选填</td>
              <td>不填</td>
            </tr>
            <tr>
              <td>日志类型</td>
              <td>HOST_DIR（主机目录）/ DOCKER_LOGS（容器日志）</td>
              <td>不填</td>
              <td>不填</td>
              <td>选填</td>
              <td>选填</td>
            </tr>
            <tr>
              <td>责任人</td>
              <td>服务负责人</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
            </tr>
            <tr>
              <td>备注</td>
              <td>备注信息</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="guide-section">
        <h2>六、审计日志</h2>
        <p>系统自动记录所有重要操作到审计日志，支持追溯和安全审计。</p>
        
        <div class="guide-subsection">
          <h3>6.1 入口</h3>
          <ul>
            <li><strong>侧边栏：</strong>系统设置 → 审计日志</li>
            <li><strong>服务详情：</strong>详情弹窗中点击「查看操作记录」按钮，自动带入当前服务的筛选条件</li>
          </ul>
        </div>

        <div class="guide-subsection">
          <h3>6.2 记录的操作类型</h3>
          <table class="field-table">
            <thead>
              <tr><th>操作类型</th><th>触发场景</th></tr>
            </thead>
            <tbody>
              <tr><td>SERVICE_START</td><td>启动服务</td></tr>
              <tr><td>SERVICE_STOP</td><td>停止服务</td></tr>
              <tr><td>SERVICE_RESTART</td><td>重启服务</td></tr>
              <tr><td>SERVICE_CREATE</td><td>新增服务</td></tr>
              <tr><td>SERVICE_UPDATE</td><td>编辑服务信息</td></tr>
              <tr><td>SERVICE_DELETE</td><td>删除服务</td></tr>
              <tr><td>SERVICE_IMPORT</td><td>Excel 导入服务</td></tr>
              <tr><td>IMPORT_REVERT</td><td>导入回滚（删除某个批次的全部新增服务）</td></tr>
              <tr><td>BACKUP_*</td><td>备份策略变更、手动备份、恢复等</td></tr>
              <tr><td>AUTH_*</td><td>登录、登出、密码重置等</td></tr>
            </tbody>
          </table>
        </div>

        <div class="guide-subsection">
          <h3>6.3 筛选</h3>
          <p>支持以下多条件组合筛选：</p>
          <ul>
            <li>操作类型（多选，如同时查看启动+停止）</li>
            <li>项目 → 子系统（级联）</li>
            <li>服务 ID（从服务详情跳转自动带入）</li>
            <li>操作人、操作结果（成功/失败）、时间范围</li>
          </ul>
        </div>
      </div>

      <div class="guide-section">
        <h2>七、注意事项</h2>
        <ul>
          <li><strong>密码安全：</strong>系统会加密存储密码，请确保密码强度足够</li>
          <li><strong>网络连通性：</strong>确保SRMC服务器能够访问目标服务器的SSH端口</li>
          <li><strong>Docker环境：</strong>Docker部署的服务需要目标服务器已安装Docker</li>
          <li><strong>程序路径：</strong>所有部署方式都需要填写程序路径，用于定位代码或配置文件</li>
          <li><strong>容器名称：</strong>Docker容器部署时必须填写容器名称，系统用它来管理容器</li>
        </ul>
      </div>

      <div class="guide-section">
        <h2>八、常见问题</h2>
        
        <div class="faq-item">
          <h3>Q: 为什么Docker部署的服务启动失败？</h3>
          <p>A: 请检查：1) 服务器是否安装了Docker；2) 容器名称是否正确；3) 程序路径是否存在；4) SSH连接是否正常。</p>
        </div>

        <div class="faq-item">
          <h3>Q: 导入服务时提示缺少必填字段？</h3>
          <p>A: 根据部署方式检查必填字段：主机部署需要启动/停止脚本，Docker容器需要容器名称，所有方式都需要程序路径。</p>
        </div>

        <div class="faq-item">
          <h3>Q: 如何更新Docker Compose部署的服务代码？</h3>
          <p>A: 直接更新程序路径下的代码文件，然后使用docker-compose down再up -d重启服务即可。</p>
        </div>

        <div class="faq-item">
          <h3>Q: 导出的Excel为什么有多个Sheet？</h3>
          <p>A: 系统按程序分类分组导出，每个分类一个Sheet，便于管理和查看。</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
</script>

<style scoped>
.usage-guide-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.guide-header {
  text-align: center;
  margin-bottom: 40px;
  padding: 40px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  color: #fff;
}

.guide-header h1 {
  margin: 0 0 12px;
  font-size: 32px;
  font-weight: 700;
}

.guide-header p {
  margin: 0;
  font-size: 16px;
  opacity: 0.9;
}

.guide-content {
  background: var(--app-panel);
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.guide-section {
  margin-bottom: 40px;
}

.guide-section h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--app-text);
  margin: 0 0 16px;
  padding-bottom: 12px;
  border-bottom: 3px solid #667eea;
}

.guide-section p {
  font-size: 15px;
  line-height: 1.8;
  color: var(--app-text-2);
  margin: 0 0 16px;
}

.guide-subsection {
  margin-left: 20px;
  margin-bottom: 24px;
}

.guide-subsection h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--app-text);
  margin: 0 0 12px;
}

.guide-subsection ol,
.guide-subsection ul {
  margin: 0;
  padding-left: 24px;
}

.guide-subsection li {
  font-size: 15px;
  line-height: 1.8;
  color: var(--app-text-2);
  margin-bottom: 8px;
}

.deploy-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
  margin-top: 20px;
}

.deploy-card {
  background: var(--app-panel-soft);
  border-radius: 12px;
  padding: 24px;
  border-left: 4px solid #667eea;
}

.deploy-card h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--app-text);
  margin: 12px 0 8px;
}

.deploy-card p {
  font-size: 14px;
  color: var(--app-text-2);
  margin: 0 0 12px;
}

.deploy-card ul {
  margin: 0;
  padding-left: 20px;
}

.deploy-card li {
  font-size: 14px;
  line-height: 1.8;
  color: var(--app-text-2);
  margin-bottom: 6px;
}

.deploy-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
}

.deploy-icon.host {
  background: linear-gradient(135deg, #3b82f6 0%, #60a5fa 100%);
}

.deploy-icon.docker {
  background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
}

.deploy-icon.compose {
  background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
}

.field-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  margin-top: 16px;
}

.field-table th,
.field-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid var(--app-border);
}

.field-table th {
  background: var(--app-panel-soft);
  font-weight: 600;
  color: var(--app-text);
}

.field-table td {
  color: var(--app-text-2);
}

.field-table tbody tr:hover {
  background: var(--app-panel-soft);
}

.faq-item {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--app-panel-soft);
  border-radius: 8px;
}

.faq-item h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--app-text);
  margin: 0 0 8px;
}

.faq-item p {
  font-size: 14px;
  line-height: 1.8;
  color: var(--app-text-2);
  margin: 0;
}
</style>