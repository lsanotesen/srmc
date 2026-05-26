# 服务资源管理中心 (SRMC)

企业级运维管理平台，用于统一管理多台 Linux 服务器上的运行服务资源。

## 功能特性

### 核心功能
- **服务统一管理**：支持 APP、NGINX、REDIS、MYSQL、KINGBASE、DAMENG、ELASTICSEARCH、RABBITMQ 等多种服务类型
- **远程启停与监控**：通过 SSH 连接实现服务的远程启停和状态监控
- **日志管理**：在线查看日志、实时 tail、关键字过滤
- **WebShell**：基于 xterm.js 的远程终端访问
- **SQL 控制台**：支持 MySQL、Kingbase、达梦数据库的 SQL 执行
- **Elasticsearch 管理**：集群状态、节点管理、索引管理、DSL 查询
- **插件化能力系统**：不同服务类型绑定不同能力，前端菜单动态生成
- **Excel 批量导入**：支持服务资源的批量初始化导入

### 安全特性
- RBAC 权限管理（ADMIN/OPS/DEV/READONLY）
- 操作审计日志（保留90天）
- SSH 连接池复用
- AES-256-GCM 密码加密存储

## 技术栈

### 后端
- **框架**: FastAPI
- **数据库**: MySQL 8.0 / MariaDB 10.5+
- **缓存**: Redis
- **ORM**: SQLAlchemy
- **SSH**: paramiko
- **定时任务**: APScheduler

### 前端
- **框架**: Vue 3 + Vite
- **UI**: Element Plus
- **状态管理**: Pinia
- **路由**: Vue Router
- **终端**: xterm.js

## 快速开始

### 环境要求
- Docker 20.10+
- Docker Compose 2.0+

### 启动服务

```bash
# 克隆项目
git clone <repository-url>
cd srmc

# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

### 访问地址

- **前端**: http://localhost:5173
- **后端 API**: http://localhost:8000
- **后端文档**: http://localhost:8000/docs

### 默认账号

- 用户名: `admin`
- 密码: `admin123`

## 项目结构

```
srmc/
├── backend/                    # 后端代码
│   ├── api/                    # API 路由
│   ├── core/                   # 核心配置
│   ├── models/                 # SQLAlchemy ORM 模型
│   ├── schemas/                # Pydantic 数据结构
│   ├── services/               # 业务逻辑层
│   ├── utils/                  # 工具函数
│   ├── init_sql/               # 初始化 SQL
│   ├── main.py                 # FastAPI 入口
│   ├── requirements.txt        # 依赖列表
│   └── Dockerfile              # 后端镜像配置
├── frontend/                   # 前端代码
│   ├── src/
│   │   ├── components/         # 通用组件
│   │   ├── pages/              # 页面组件
│   │   ├── router/             # 路由配置
│   │   ├── stores/             # Pinia 状态管理
│   │   ├── utils/              # 工具函数
│   │   ├── App.vue             # 根组件
│   │   └── main.js             # 入口文件
│   ├── package.json            # 依赖列表
│   ├── vite.config.js          # Vite 配置
│   └── Dockerfile              # 前端镜像配置
├── docker-compose.yml          # Docker Compose 配置
├── .env.example                # 环境变量示例
└── README.md                   # 项目文档
```

## API 模块

| 模块 | 路径 | 说明 |
|------|------|------|
| Auth | `/api/auth` | 用户认证 |
| Server | `/api/servers` | 服务器管理 |
| Service | `/api/services` | 服务管理 |
| Monitor | `/api/monitor` | 状态监控与启停 |
| Log | `/api/logs` | 日志管理 |
| Shell | `/api/shell/ws` | WebShell |
| SQL | `/api/sql` | SQL 控制台 |
| ES | `/api/es` | Elasticsearch 管理 |
| User | `/api/users` | 用户管理 |
| Audit | `/api/audit` | 审计日志 |
| Import/Export | `/api/import` | 导入导出 |

## 服务类型与能力映射

| 服务类型 | 能力 |
|---------|------|
| APP | 状态监控、启停管理、日志查看、WebShell |
| MYSQL | 状态监控、SQL控制台、数据库列表、用户管理 |
| KINGBASE | SQL执行、实例监控、用户管理、表空间管理 |
| DAMENG | SQL执行、实例监控、用户管理 |
| ELASTICSEARCH | 集群状态、节点管理、索引管理、DSL查询、快照管理 |

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| SECRET_KEY | 加密密钥（32字节base64） | - |
| JWT_SECRET_KEY | JWT密钥 | - |
| DATABASE_URL | 数据库连接地址 | - |
| REDIS_URL | Redis连接地址 | - |
| AUDIT_LOG_RETENTION_DAYS | 审计日志保留天数 | 90 |
| SSH_CONNECT_TIMEOUT | SSH连接超时（秒） | 10 |
| BATCH_MAX_WORKERS | 批量操作并发数 | 5 |

## 开发指南

### 后端开发

```bash
cd backend
pip install -r requirements.txt
python main.py
```

### 前端开发

```bash
cd frontend
npm install
npm run dev
```

## 生产部署

```bash
# 构建镜像
docker-compose build

# 启动服务（后台模式）
docker-compose up -d

# 停止服务
docker-compose down
```

## License

MIT License
