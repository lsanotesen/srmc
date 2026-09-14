# SRMC 工程说明文档

> **使用约定：后续任何任务请优先阅读本文档获取项目全貌与关键约定，不要批量遍历全部源码。**
> 文档基于 2026-09 源码整理；如代码发生结构性变更，请同步更新本文档对应章节。

---

## 1. 项目概述

**SRMC（服务资源管理中心）** 是一个面向内网多服务器环境的**服务资源监控与管控平台**，核心能力：

- 按「项目 → 子系统 → 程序分类 → 服务」四级结构管理大量服务（50~100+）
- 实时监控每台服务器上各服务的运行状态（主机进程 / Docker / Docker Compose）
- 通过 **Agent（Go，容器部署在目标服务器）** 优先采集状态与执行启停；Agent 离线时自动回退 **SSH** 检测
- 内置 Web 远程终端（xterm.js + SSH PTY）、Excel 批量导入导出、数据库备份恢复、RBAC 权限、审计日志

## 2. 总体架构

```
┌─────────────┐   HTTP/WS(/api 代理)   ┌──────────────────┐   pymysql     ┌─────────────┐
│  前端 Vue3   │ ─────────────────────▶ │  后端 FastAPI     │ ────────────▶ │ MySQL(srmc) │
│ (5173 dev)  │ ◀───── WebSocket ────── │  (8000)          │               └─────────────┘
└─────────────┘                        │                  │   redis-py    ┌─────────────┐
                                       │                  │ ────────────▶ │ Redis       │
                                       └──────┬───────────┘               └─────────────┘
                                              │ WebSocket /ws/agent/{uuid}
                                              ▼
                                       ┌──────────────────┐  docker CLI/socket  ┌──────────────┐
                                       │ SRMC Agent (Go)  │ ──────────────────▶ │ 目标服务器容器 │
                                       │ (每台目标机一个)   │  nsenter/su         │ 目标服务器进程 │
                                       └──────────────────┘                     └──────────────┘
                                       后端在 Agent 离线时走 SSH 直连目标机检测（asyncssh/paramiko 池）
```

**状态检测优先原则**：服务 IP 必须与 Agent IP 一致才会被该 Agent 监控（不支持跨 IP）；Agent 在线 → 独占使用 Redis 缓存状态；Agent 离线 → SSH 检测（每次最多 10 个服务）。

## 3. 目录结构与技术栈

| 目录 | 说明 | 技术栈 |
|---|---|---|
| `frontend/` | Web 前端（dev 模式运行） | Vue 3 + Vite 5 + Element Plus + Pinia + Vue Router + xterm.js |
| `backend/` | 后端 API 服务 | Python FastAPI + SQLAlchemy + PyMySQL + Redis + JWT + asyncssh/paramiko + openpyxl |
| `srmc-agent/` | 目标机 Agent | Go（gopsutil、gorilla/websocket），静态编译 CGO_ENABLED=0 |
| `monitor/` | 独立监控脚本目录（辅助用途） | — |
| 根目录 `docker-compose.yml` | 平台自身五个容器的编排 | Docker Compose |

```
srmc/
├── docker-compose.yml          # mysql/redis/backend/frontend/agent 五服务编排
├── PROJECT.md                  # 本文档
├── backend/
│   ├── main.py                 # FastAPI 入口：CORS、router 注册、启动初始化、定时任务
│   ├── .env                    # 运行配置（DATABASE_URL/REDIS_URL/JWT/SSH 超时等）
│   ├── Dockerfile              # python 基础镜像 + mysql/shell 客户端，startup.sh 启动
│   ├── core/                   # config.py(配置)、database.py(会话)、security
│   ├── models/                 # SQLAlchemy 模型（app_service.py 的 AppService 为主表等）
│   ├── schemas/                # Pydantic 入参/出参
│   ├── api/                    # 路由层：auth/services/projects/agent/shell/backup/rbac...
│   ├── services/               # 业务服务（审计、监控、备份调度等）
│   ├── utils/                  # ssh_pool、crypto(加解密)、redis_client、cache
│   └── migrations/             # 编号迁移脚本（python 直接执行，如 0010_add_relation_display_order.py）
├── frontend/
│   ├── vite.config.js          # strictAssetsPlugin(防MIME) + /api 代理 → srmc-backend:8000
│   ├── Dockerfile              # node18-alpine，npm run dev
│   └── src/
│       ├── main.js             # 入口 + 全局遮罩清理 cleanupDeadOverlays
│       ├── router/index.js     # 路由 + 登录守卫 + afterEach 遮罩兜底清理
│       ├── stores/             # pinia: user(token/menu/permissions)、service 等
│       ├── utils/axios.js      # token 注入、401 跳登录
│       ├── components/         # Layout.vue(侧边菜单/面包屑) 等
│       └── pages/              # 业务页面（见 §6.3）
└── srmc-agent/
    ├── main.go                 # 入口：连接→注册→心跳循环
    ├── config/                 # config.yaml 解析与默认值
    ├── transport/ws_client.go  # WebSocket 协议、注册/心跳/命令分发
    ├── collector/collector.go  # 系统指标 + 服务状态采集（含全部防误报逻辑）
    ├── manager/manager.go      # start/stop/restart/logs 三种部署类型实现
    ├── Dockerfile              # 多阶段：go 静态编译 → alpine 运行
    ├── deploy.sh               # 构建镜像导出 tar，可 --upload user@host /path
    └── agent_deploy/           # 目标机部署包（docker-compose.yml + config.yaml）
```

## 4. 部署拓扑与端口

平台自身（根 `docker-compose.yml`，全部 `restart: unless-stopped`，agent 为 `always`）：

| 容器 | 镜像 | 端口 | 说明 |
|---|---|---|---|
| srmc-mysql | mysql | 3306 | 业务库 `srmc`（账号 srmc/srmc123），healthy |
| srmc-redis | redis | 6379 | 状态缓存/队列，healthy |
| srmc-backend | srmc-backend:latest | 8000 | FastAPI，startup.sh 启动（含迁移/初始化） |
| srmc-frontend | srmc-frontend:latest | 5173 | **dev server**，源码挂载 `./frontend:/app` + 匿名卷 `/app/node_modules`（保留镜像内 musl 依赖，防止宿主机 glibc 依赖在 alpine 内崩溃） |
| srmc-agent | srmc-agent:latest | 8080(内部) | 平台所在机的 Agent，`HOST_IP=192.168.12.79` |

**关键约定**：
- compose 中 `build+image` 必须同时写，image 固定镜像名，避免 compose V1/V2 项目名差异导致意外 rebuild
- 目标服务器 docker-compose V1.29.2 重建容器有 `KeyError: ContainerConfig` bug → 用 `down + up` 代替 `up -d`
- Agent 部署：`deploy.sh` 构建导出 tar → 目标机 `/root/agent_deploy/` `docker load` + `docker-compose up -d`
- Agent compose 关键配置：`network_mode: host`、`pid: host`、`privileged: true`、`security_opt: [label=disable]`；挂载 docker.sock、config.yaml、日志目录、/etc/passwd|shadow|group、/home、/u01、/u02、/opt、/data、/srv。**禁止挂载 `/proc:/proc:ro`**（会阻断 runc 创建进程报 `can't set process label ... read-only file system`）

## 5. 后端（backend/）

### 5.1 启动与配置

- 入口 `main.py`：CORS 全放开；`L115-L138` 注册全部 router；启动事件初始化服务分组、权限数据、定时任务（状态轮询、备份调度）
- `backend/.env`：`DATABASE_URL=mysql+pymysql://srmc:srmc123@mysql:3306/srmc`、`REDIS_URL=redis://redis:6379/0`、JWT 密钥/2h 过期、`SSH_CONNECT_TIMEOUT=10`/`SSH_COMMAND_TIMEOUT=30`/`SSH_IDLE_TIMEOUT=600`/`SSH_RETRY_COUNT=2`、`BATCH_MAX_WORKERS=5`
- 迁移：`backend/migrations/` 编号脚本，启动时或手动执行

### 5.2 API 路由总览（前缀均挂 `/api`）

| 模块 | 文件 | 核心端点 |
|---|---|---|
| 认证 | api/auth.py | `POST /auth/login`（JWT，失败记审计）、`/auth/logout` |
| 用户/RBAC | api/rbac.py、users、organization | 角色 CRUD、权限分配、用户管理、组织管理 |
| 项目 | api/projects.py | 项目 CRUD、`/projects/tree`（树，按 SubsystemGroupRelation.display_order 排序，Redis key `projects_tree`） |
| 服务 | api/services.py | 服务 CRUD/列表（L272-309 合并 Redis 实时状态）、`/services/import`、`/services/export`、启停命令 `POST /services/{id}/{action}`、`/services/status/batch`、`/services/status/cache` |
| 子系统/分类 | api/subsystems.py、service-groups | 子系统、程序分类及关联（SubsystemGroupRelation 含 display_order） |
| 服务器 | api/server*.py | 服务器 CRUD（SSH 凭据加密存储） |
| Agent | api/agent.py | `WS /ws/agent/{uuid}`（L279-319 连接与消息循环、断连清理缓存标记 OFFLINE）、注册自动关联同 IP 服务（L353-427）、debug 接口 |
| 远程终端 | api/shell.py | `WS /shell/ws/{service_id}`：认证→查服务→SSH→PTY→转发（详见 §5.4） |
| 备份 | api/backup.py | 备份策略配置（动态重排定时任务）、手动备份/下载/删除/**恢复**（受权限控制） |
| 审计 | api/audit*.py | 审计日志查询（保留 `AUDIT_LOG_RETENTION_DAYS=90` 天） |
| **运行总览** | api/dashboard.py | 4 个接口（全部经 DataScope 权限过滤）：`GET /api/dashboard/overview`（6 统计卡）、`GET /api/dashboard/projects`（项目聚合）、`GET /api/dashboard/stopped-services`（分页）、`GET /api/dashboard/agent-offline` |
| **服务列表扩展** | api/services.py `get_services` | 新增 `status` / `agent_status` 查询参数（Redis 状态内存过滤，跳过列表缓存）；所有查询**接入 DataScopeService 权限过滤**（非 ADMIN 仅可见有权限的项目服务） |

### 5.3 数据模型要点

- 主表 `app_services`（AppService）：服务台账。关键字段：`ip`、`ssh_port`、`username`、`password`(加密)、`port`(程序端口)、`deploy_type`(HOST/PROCESS/DOCKER/DOCKER_COMPOSE)、`container_name`、`program_path`、`start_script/stop_script`、`pid_file`、`log_path`、`func_desc`、项目/子系统/分类外键
- `Agent`：uuid、ip、status、last_heartbeat（在线判断 = WebSocket 在 active_connections **或** 心跳 30s 内，见 agent.py L44-53）
- `SubsystemGroupRelation`：子系统×分类关联，含 `display_order`（每个子系统内独立排序，Excel 导入按 sheet 顺序写入）
- `AgentUpdateTask`/`AgentUpdateTaskItem`（`agent_update_tasks`/`agent_update_task_items`）：批量更新任务与逐台执行明细。任务含 `update_type`(docker/binary)、file_name/file_path/file_size/file_sha256、镜像参数(image_name/image_tag/container_name)或二进制参数(binary_target_path/binary_service_name/backup_before_update/auto_stop_old/auto_start_after)、六状态计数、`status`、created_by；明细含 agent_uuid、hostname/ip、`status`/`current_step`/`progress`/`error_message`/起止时间
- 导入查重仅在同一项目内；`(project_id, subsystem_code)` 唯一

### 5.4 核心流程

**① 服务状态采集（双通道）**
```
前端轮询(5s) → GET /api/services... → 列表接口内 MGET Redis:
  service_status:{id}          状态字符串(Running/Stopped/Partial/...)
  service_status_source:{id}   来源 AGENT/SSH/OFFLINE
  service_containers:{id}      Docker Compose 容器明细 JSON
Agent 在线 → 这些 key 由心跳持续刷新（TTL 60s），SSH 查询被禁用
Agent 离线 → SSH 兜底：utils/ssh_pool 连接执行检测（≤10 服务/次），状态检测优先
  StartCmd 脚本解析（提取具体可执行文件名）而非 ProgramPath 泛匹配；端口检测优先于进程匹配
```
（旧 monitor_service.py 为 Server 维度的 SSH 检测实现，部分场景仍引用。）

**② Agent 生命周期**
- 注册（agent.py L353-427）：复用/创建 Agent 记录 → **自动关联该 IP 上所有未关联服务** → 清旧缓存 → 下发服务清单（`handle_pull_services` L496-545 组装 ServiceConfig：`docker_name=container_name`、`compose_path=program_path`，start_cmd 相对路径自动拼 program_path 前缀）
- 心跳 `handle_heartbeat`（L429-482）：更新 last_heartbeat；遍历 `data.heartbeat.services[]` 写 Redis（TTL 60s）；系统指标写 `agent_metrics:{uuid}`；docker 容器/Compose 项目写 `agent_containers:{uuid}`、`agent_compose:{uuid}`

**③ Web 终端（api/shell.py，近期重构过）**
- 流程：token 认证 → 查 AppService → ssh_pool 连接（15s 超时）→ `invoke_shell(xterm, 80x24)` → 自动 `cd {program_path}`（~ 按 SSH 用户 home 展开）
- **消息协议**：客户端文本消息=键盘输入，直接 `shell.send()`；二进制 `[0x01][cols u16le][rows le]`=PTY resize
- 主循环用**单个 `websocket.receive()` 按 text/bytes 分发**（曾因并发 receive_text/receive_bytes 抢同一队列导致丢字符，已修复，勿回退）
- `read_output` 任务 20ms 轮询 `shell.recv(8192)` → utf-8/gbk 解码 → send_text；心跳 30s，闲置 300s 断开

**④ Excel 导入/导出**
- 导入（services.py L1594+）：多 sheet，每 sheet 必关联子系统分类（无条件，即使全重复）→ 查重（同项目内）→ 生成批次记录支持精确回滚 → 失效 `projects_tree` 缓存 → 按 sheet 序号写 display_order → **导入后调 associate_services_to_online_agents：把新增/补全归属的服务按 IP 关联到在线 Agent（填 agent_uuid，否则前端显示"未关联"）并向相关 Agent 发 pull_services 刷新采集清单**
- 导出：openpyxl，含 deploy_type 映射

**⑤ 备份恢复**
- MariaDB 需 `--skip-ssl`；dump 排除运行时表（如 db_backup_records）防恢复覆盖状态
- 恢复前自动快照；处理元数据锁（提交/清理空闲事务、`lock_wait_timeout=60`）

### 5.5 认证与权限

JWT（HS256，2h）；前端 axios 拦截器注入 `Authorization: Bearer`，401 跳登录。RBAC：用户→角色→权限，菜单按权限过滤（user store `fetchMenu/fetchPermissions`）；敏感操作（备份恢复、服务控制等）经 `require_permission` 依赖并记审计。

## 6. Agent（srmc-agent/）

### 6.1 消息协议（transport/ws_client.go）

统一 JSON：`{type, request_id, timestamp, data}`。连接 `ws(s)://{server.url}/ws/agent/{uuid}`。
- 上行：`register`（系统信息）、`heartbeat`（system 指标 + services 状态数组 + docker_containers + compose_projects）、`command_result`、`update_progress`（批量更新进度回传）
- 下行处理：`services`（更新采集清单）、`pull_services`（触发拉取）、`command`（start/stop/restart/logs → manager，结果回传）、`config_update`、`update`（批量更新指令 → manager.ExecuteUpdate）
- 心跳间隔 `config.yaml collector.heartbeat_interval`；断线自动重连

### 6.2 状态采集（collector/collector.go）— 检测优先级链

```
collectSingleService 按 deploy_type 分发:
  HOST/PROCESS      → collectProcessStatus:
      1) PID 文件（读 pid + isProcessRunningPure 校验）
      2) 单端口 isPortListening（TCP dial）
      3) 多端口 Ports 逗号分隔逐一试
      4) StartCmd：解析启动脚本（parseBashVariables/expandBashVariables 展开 $VAR；
         提取 .jar/二进制名）→ findProcessByCmdline 精确匹配 cmdline 并验证内容
      5) 服务名兜底：仅名称>6字符且纯 ASCII（防中文误匹配）
  DOCKER            → inspectContainer(docker_name)
  DOCKER_COMPOSE    → collectComposeStatus（两方式互为兜底）:
      方式一：docker_name 非空 → docker inspect 单容器（不依赖 compose 文件可达）；
              inspect 失败不判停，回退方式二
      方式二：resolveComposePathForCollector 解析 yml 路径 →
        listContainersByComposeFile: docker ps -a --filter
        label=com.docker.compose.project.config_files=<yml绝对路径> --format "ID|Name|State|Image|Ports|RunningFor"
        （docker ps 一次拿全字段，不调用 inspect）
      统计 running：全 running=Running，部分=Partial，0=Stopped
```

**防误报体系（务必保持）**：
- `isUselessKeyword`：过滤 start/java/nohup/server 等通用词
- Docker API 版本自适应：`DetectDockerAPIVersion` 启动探测；`execWithVersionFallback` 遇 "client version ... too new" 自动降级重试
- `stripDockerCLILogLines`/`isDockerCLILogLine`：剥离混入 stdout 的 `time="..." level=warning ...`（如 compose 变量未定义 warning）
- `isHexContainerID`：容器 ID 必须 12~64 位十六进制，防 warning 文本被当容器（曾致出现假"已停止"容器行）
- 容器只有 `state=="running"` 才算运行（restarting 不算）
- `execWithVersionFallback` 成功只返回纯 stdout（防 stderr warning 污染输出解析）

### 6.3 服务控制（manager/manager.go）

- 三种部署类型 `start/stop/restart`：PROCESS（脚本）、DOCKER（docker start/stop/restart 容器名）、DOCKER_COMPOSE（`runComposeCmd`：V2 `docker compose` 失败自动尝试 V1 `docker-compose`；up -d / down / restart —— **作用于整个 compose 项目全部容器**）
- `runHostCommand`：容器内（有 /.dockerenv）用 `nsenter -t 1 -m -u -i -n -p -- bash -c '<cmd>'` 落到宿主机执行；PROCESS 启动=先 `cd 脚本目录 && ./脚本`，root 下再 `su - <服务用户> -c '...'`（保证权限/环境/属主正确）
- 日志流 StreamLogs：PROCESS=`tail -F` 展开后的 log_path（~ 按服务用户 home 展开）；DOCKER=`docker logs -f`；COMPOSE=`docker compose -f <yml> logs -f`

### 6.4 构建/部署

- **必须 `CGO_ENABLED=0` 静态编译**（目标机 GLIBC 不可控）；进程操作走 /proc 纯 Go 实现
- Dockerfile 多阶段：golang 构建 → alpine 运行，EXPOSE 8080，CMD 指定 `/etc/srmc-agent/config.yaml`
- config.yaml：`server.url`（ws 后端地址）、`agent.name/ip`（**agent.ip 显式配置优先于自动探测**，多网卡机器必配）、心跳间隔、命令超时
- 环境变量 `SERVER_URL`/`AGENT_TOKEN`/`TZ`/`DOCKER_API_VERSION`(1.44，运行时自动校正)

### 6.5 批量更新执行（manager/updater.go）

`ExecuteUpdate`：下载更新文件（HTTP）→ SHA256 二次校验 → 按类型分发，逐步上报进度（step/status/progress/error）。

- **Docker 镜像**（走 docker socket，**不删旧镜像**）：`docker load -i` → 可选（配 `container_name` 且 AutoStartAfter）`docker stop` + `docker start` 套用新镜像
- **二进制文件**：备份旧文件 → `systemctl stop` → 替换 → 保留原权限 → `systemctl start` → `is-active` 检查；失败且开启备份时自动回滚旧文件并重启旧程序
- **宿主机文件操作**（容器内自动 `nsenter -t 1 -m -u -i -n -p`，裸机直接 os 操作）：`copyFileHost`/`statPermHost`/`mkdirAllHost`/`writeLocalToHost`（stdin 管道写宿主机，解决容器内文件↔宿主机路径跨命名空间）/`chmodHost`

## 7. 前端（frontend/）

### 7.1 运行方式与代理

- **dev server 直接服务**（非静态构建）：容器挂载源码，`npm run dev`，修改即时生效
- vite.config.js：
  - `strictAssetsPlugin`：.js/.wasm/.map 等静态资源未命中返回 404，**禁止 SPA fallback 到 index.html**（防 "Expected a JavaScript module... MIME type text/html" 连环报错；/@vite/、/node_modules/、/src/ 虚拟路径放行）
  - 代理 `/api` → `http://srmc-backend:8000`（keepAlive agent）；`/api/shell/ws`、`/api/services/:service_id/log/ws` → ws 代理

### 7.2 路由与全局守卫

`router/index.js`：`/login` + Layout 下 Overview（`/` 与 `/overview` 同页，即登录后首页「运行总览」）、Projects、Services(ServicesNew)、Subsystems、ServiceGroups、Servers、Agents、AgentUpdateTasks、Organization、Roles、Users、Audit、Backup、Settings、Shell、Monitoring、SQL、ImportServices、ExportServices、UsageGuide。**旧 Dashboard.vue 已删除、`/dashboard` 路由已移除**（登录/返回统一跳 `/`）。`beforeEach` 校验 token；`afterEach` 做遮罩兜底清理（1s/3s 后再清）。

### 7.3 状态管理与请求

- stores/user.js：token/user/menu/permissions；登录后设 axios 默认头并拉菜单+权限+用户信息；菜单为空时 Layout.vue 有内置兜底菜单
- utils/axios.js：超时、JSON 头、Bearer 注入、401 清 token 跳 /login
- stores/service.js：服务列表/详情/启停等 API 封装

### 7.4 关键页面/组件

| 页面 | 用途 |
|---|---|
| **Overview.vue**（运行总览） | 新增首页：6 统计卡（项目数/服务数/运行中/已停止/Agent异常/未知）+ 项目运行状态列表（点击下钻 `/services?project_id=xx`）+ 当前停止服务列表 + Agent 异常列表；支持自动刷新（60s 默认）、手动刷新、点击跳转服务管理带筛选条件 |
| ServicesNew.vue | 服务管理主页面（已升级）：列表+详情弹窗+内嵌 xterm+日志流；**新增**：状态/Agent状态/部署方式三个筛选下拉、状态统计快捷筛选栏（点击运行中/已停止/Agent异常切换筛选）、**支持 URL query 初始化筛选**（运行总览下钻带条件进来自动生效） |
| Agents.vue | Agent 列表：UUID 列（等宽字体）、在线状态（硬在线=ws 连接 ∨ 软在线=30s 内心跳）、最后心跳；**批量更新入口**：勾选或弹窗内多选目标 Agent → 选择更新类型（Docker 镜像/二进制）→ 流式上传（进度+SHA256）→ 配置参数 → 二次确认 → 创建任务 |
| AgentUpdateTasks.vue | 批量更新任务列表/详情：任务级（ID/类型/版本/目标/成功/失败/执行中/创建人/状态）5s 轮询；详情逐台主机名/IP/状态/当前步骤/进度/起止时间/错误信息，支持取消执行中任务 |
| Shell.vue | 独立简化终端页（textarea 逐条发送，非 xterm） |
| ImportServices.vue / ExportServices.vue | Excel 导入导出向导 |
| Backup.vue | 备份策略与记录、恢复 |
| Layout.vue | 侧边菜单（后端菜单+兜底）、面包屑、侧栏折叠持久化 localStorage；菜单首项已改为"运行总览"（icon=data-analysis → DataAnalysis） |

### 7.5 xterm 终端协议（ServicesNew.vue）

- `Terminal{convertEol:true, scrollback:10000, rendererType:'canvas'}` + FitAddon + WebLinksAddon
- `terminal.onData` → `websocket.send(data)`（文本=键盘输入）
- resize：二进制 `[0x01][cols u16le][rows u16le]`，onResize 与 onopen 各发一次
- 下行：ArrayBuffer → `terminal.write(Uint8Array)`；终端未 ready 时进 `messageQueue` 缓冲
- 注意：onResize 内**不得调用 fitAddon.fit()**（死循环）；聚焦用 `.xterm-helper-textarea`

### 7.6 全局遮罩清理（main.js / 已知坑）

`OVERLAY_SELECTORS`（v-modal、el-overlay、el-message-box__wrapper、el-loading-mask、el-dialog__wrapper、el-drawer__wrapper）+ `cleanupDeadOverlays()`：启动清一次，router.afterEach 兜底。**组件规范**：`el-dialog append-to-body` 的组件必须在 `onBeforeUnmount` 显式 `dialogVisible=false`，否则遮罩残留拦截点击（踩过多次）。

## 8. 环境速查

- 平台入口：`http://192.168.12.79:5173`（dev）；后端直连 `:8000`（/docs）
- 常用命令：平台机用 **V1 `docker-compose`（带连字符）**；recreate 容器遇 `KeyError: 'ContainerConfig'` 时改用 `docker-compose down && docker-compose up -d`（或先 `docker rm -f <旧名带hash前缀容器>` 再 up）、`docker restart srmc-backend`、Agent 部署见 §6.4
- **时区（统一北京时间 UTC+8）**：mysql 服务 `command: --default-time-zone=+08:00`；backend 镜像装 `tzdata` 并 `TZ=Asia/Shanghai`，`main.py` 顶部 `tzset()`（APScheduler/tzlocal 要求 Continent/City 格式，**不能用 POSIX 固定偏移 `CST-8`**，否则启动报 `ZoneInfoNotFoundError`）；各服务 `TZ=Asia/Shanghai`。历史 UTC 数据由 `migrations/0012_fix_datetime_to_cst.py` 把全部 **datetime 列 +8 小时**（本项目无 timestamp 列；每表一条 UPDATE 同时 SET 所有时间列以避开 ON UPDATE 干扰；脚本默认 dry-run，传 `apply` 才写库，**只能执行一次**）
- Redis 关键 key：`service_status:{id}`(TTL60) / `service_status_source:{id}` / `service_containers:{id}` / `agent_metrics:{uuid}` / `agent_containers:{uuid}` / `agent_compose:{uuid}` / `projects_tree`
- 目标服务器典型布局：服务目录 `/u01/isi/...`、`/home/...`；compose 项目每 yml 顶层配唯一 `name` 字段；compose 引用变量（如 docker_user_uid）需在同目录 `.env` 定义或 `${VAR:-默认值}` 兜底（.bashrc 的 export 对 Agent/nsenter 非交互 shell 无效）
