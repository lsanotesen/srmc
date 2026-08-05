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
        <p>系统支持三种部署方式，根据服务类型选择合适的部署方式：</p>
        
        <div class="deploy-cards">
          <div class="deploy-card">
            <div class="deploy-icon host">🖥️</div>
            <h3>主机部署</h3>
            <p>直接在物理主机上运行的服务，需要手动编写启动和停止脚本。</p>
            <ul>
              <li><strong>适用场景：</strong>传统服务、自定义脚本部署</li>
              <li><strong>必填字段：</strong>程序路径、启动脚本、停止脚本</li>
              <li><strong>启停方式：</strong>执行用户自定义脚本</li>
            </ul>
          </div>

          <div class="deploy-card">
            <div class="deploy-icon docker">🐳</div>
            <h3>Docker容器部署</h3>
            <p>单个Docker容器运行的服务，系统自动使用docker命令管理容器。</p>
            <ul>
              <li><strong>适用场景：</strong>单容器应用（如Nginx、MySQL）</li>
              <li><strong>必填字段：</strong>程序路径、容器名称</li>
              <li><strong>启停命令：</strong>docker start/stop {容器名称}</li>
            </ul>
          </div>

          <div class="deploy-card">
            <div class="deploy-icon compose">📦</div>
            <h3>Docker Compose部署</h3>
            <p>使用docker-compose编排的多容器应用，系统自动管理整个应用栈。</p>
            <ul>
              <li><strong>适用场景：</strong>多容器应用（含数据库、中间件）</li>
              <li><strong>必填字段：</strong>程序路径（docker-compose.yml所在目录）</li>
              <li><strong>启停命令：</strong>docker-compose up -d / docker-compose down</li>
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
          <h3>3.2 启动/停止服务</h3>
          <p>在服务列表中，点击对应服务的"启动"或"停止"按钮，系统会通过SSH连接到目标服务器执行相应命令。</p>
        </div>

        <div class="guide-subsection">
          <h3>3.3 查看服务详情</h3>
          <p>点击服务列表中的服务名称，可查看服务的详细信息，包括配置参数、运行状态等。</p>
        </div>
      </div>

      <div class="guide-section">
        <h2>四、导入/导出功能</h2>
        
        <div class="guide-subsection">
          <h3>4.1 导入服务</h3>
          <ol>
            <li>点击"导入服务"菜单进入导入页面</li>
            <li>下载导入模板，按照模板格式填写数据</li>
            <li>选择项目和程序分类</li>
            <li>上传Excel文件，系统会自动识别部署方式</li>
            <li>查看导入结果，处理失败的数据</li>
          </ol>
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
        <p>模板包含完整的字段列表，用于标准化导入数据。模板中的示例数据展示了三种部署方式的填写格式。</p>
        
        <h3>字段说明</h3>
        <table class="field-table">
          <thead>
            <tr>
              <th>字段名</th>
              <th>说明</th>
              <th>主机部署</th>
              <th>Docker容器</th>
              <th>Docker Compose</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>功能描述</td>
              <td>服务的功能说明</td>
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
            </tr>
            <tr>
              <td>IP地址</td>
              <td>服务器IP</td>
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
            </tr>
            <tr>
              <td>用户名</td>
              <td>SSH登录用户名</td>
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
            </tr>
            <tr>
              <td>程序路径</td>
              <td>代码或docker-compose.yml所在目录</td>
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
            </tr>
            <tr>
              <td>停止脚本</td>
              <td>停止命令或脚本路径</td>
              <td>必填</td>
              <td>不填</td>
              <td>不填</td>
            </tr>
            <tr>
              <td>日志路径</td>
              <td>日志文件或目录路径</td>
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
            </tr>
            <tr>
              <td>部署方式</td>
              <td>主机部署 / Docker容器 / Docker Compose</td>
              <td>-</td>
              <td>-</td>
              <td>-</td>
            </tr>
            <tr>
              <td>容器名称</td>
              <td>Docker容器名称</td>
              <td>不填</td>
              <td>必填</td>
              <td>不填</td>
            </tr>
            <tr>
              <td>镜像名称</td>
              <td>Docker镜像名称</td>
              <td>不填</td>
              <td>选填</td>
              <td>不填</td>
            </tr>
            <tr>
              <td>端口映射</td>
              <td>端口映射配置，如8080:80</td>
              <td>不填</td>
              <td>选填</td>
              <td>不填</td>
            </tr>
            <tr>
              <td>日志类型</td>
              <td>HOST_DIR（主机目录）/ DOCKER_LOGS（容器日志）</td>
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
            </tr>
            <tr>
              <td>备注</td>
              <td>备注信息</td>
              <td>选填</td>
              <td>选填</td>
              <td>选填</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="guide-section">
        <h2>六、注意事项</h2>
        <ul>
          <li><strong>密码安全：</strong>系统会加密存储密码，请确保密码强度足够</li>
          <li><strong>网络连通性：</strong>确保SRMC服务器能够访问目标服务器的SSH端口</li>
          <li><strong>Docker环境：</strong>Docker部署的服务需要目标服务器已安装Docker</li>
          <li><strong>程序路径：</strong>所有部署方式都需要填写程序路径，用于定位代码或配置文件</li>
          <li><strong>容器名称：</strong>Docker容器部署时必须填写容器名称，系统用它来管理容器</li>
        </ul>
      </div>

      <div class="guide-section">
        <h2>七、常见问题</h2>
        
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
  background: #fff;
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
  color: #1e293b;
  margin: 0 0 16px;
  padding-bottom: 12px;
  border-bottom: 3px solid #667eea;
}

.guide-section p {
  font-size: 15px;
  line-height: 1.8;
  color: #475569;
  margin: 0 0 16px;
}

.guide-subsection {
  margin-left: 20px;
  margin-bottom: 24px;
}

.guide-subsection h3 {
  font-size: 18px;
  font-weight: 600;
  color: #334155;
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
  color: #475569;
  margin-bottom: 8px;
}

.deploy-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
  margin-top: 20px;
}

.deploy-card {
  background: #f8fafc;
  border-radius: 12px;
  padding: 24px;
  border-left: 4px solid #667eea;
}

.deploy-card h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin: 12px 0 8px;
}

.deploy-card p {
  font-size: 14px;
  color: #64748b;
  margin: 0 0 12px;
}

.deploy-card ul {
  margin: 0;
  padding-left: 20px;
}

.deploy-card li {
  font-size: 14px;
  line-height: 1.8;
  color: #475569;
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
  border-bottom: 1px solid #e2e8f0;
}

.field-table th {
  background: #f8fafc;
  font-weight: 600;
  color: #334155;
}

.field-table td {
  color: #475569;
}

.field-table tbody tr:hover {
  background: #f8fafc;
}

.faq-item {
  margin-bottom: 20px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
}

.faq-item h3 {
  font-size: 16px;
  font-weight: 600;
  color: #334155;
  margin: 0 0 8px;
}

.faq-item p {
  font-size: 14px;
  line-height: 1.8;
  color: #475569;
  margin: 0;
}
</style>