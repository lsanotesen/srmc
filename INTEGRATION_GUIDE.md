# 项目服务管理模块集成说明

## 一、模块概述

本模块将原有的"项目管理"与"后台程序管理"合并，统一为**项目服务管理**，包含两个二级页面：
- **项目名称管理**：维护项目基础信息
- **服务管理**：管理项目下的具体程序服务

## 二、新增文件清单

### 2.1 数据库迁移脚本
```
backend/init_sql/003_create_projects_services_tables.sql
```

### 2.2 后端模型
```
backend/models/project.py      # 项目表模型
backend/models/service.py      # 服务表模型
```

### 2.3 后端Schema
```
backend/schemas/project.py     # 项目相关Schema
backend/schemas/service.py     # 服务相关Schema
```

### 2.4 后端API路由
```
backend/api/projects.py        # 项目管理API
backend/api/services.py        # 服务管理API
```

### 2.5 前端页面
```
frontend/src/pages/Projects.vue    # 项目名称管理页面
frontend/src/pages/Services.vue    # 服务管理页面
```

## 三、修改的文件

### 3.1 后端主路由配置
**文件**: `backend/main.py`
- 添加了 projects_router 和 services_router 的导入
- 注册了 `/api/projects` 和 `/api/services` 路由

### 3.2 后端菜单配置
**文件**: `backend/api/user.py`
- 移除了原有的"项目管理"和"后台程序管理"菜单
- 添加了"项目服务管理"一级菜单，包含两个子菜单：
  - 项目名称管理 (/projects)
  - 服务管理 (/services)

### 3.3 前端路由配置
**文件**: `frontend/src/router/index.js`
- 更新了路由配置，映射正确的页面组件

## 四、数据库表结构

### 4.1 项目表 (projects)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INT | 主键，自增 |
| name | VARCHAR(100) | 项目名称，必填，唯一 |
| code | VARCHAR(50) | 项目编码 |
| owner | VARCHAR(100) | 负责人 |
| department | VARCHAR(100) | 所属部门 |
| description | TEXT | 项目描述 |
| status | TINYINT | 状态：1启用，0停用 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 4.2 服务表 (services)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INT | 主键，自增 |
| project_id | INT | 所属项目ID，外键 |
| func_desc | VARCHAR(255) | 功能描述，必填 |
| module | VARCHAR(100) | 对应模块 |
| ip | VARCHAR(45) | 服务器IP，必填 |
| username | VARCHAR(100) | SSH用户名，必填 |
| password | VARCHAR(500) | AES加密密码，必填 |
| program_path | VARCHAR(500) | 程序路径，必填 |
| start_script | VARCHAR(500) | 启动脚本 |
| stop_script | VARCHAR(500) | 停止脚本 |
| log_path | VARCHAR(500) | 日志路径 |
| port | INT | 程序端口 |
| owner | VARCHAR(100) | 负责人 |
| remark | TEXT | 备注 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

## 五、API接口列表

### 5.1 项目管理API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/projects | 分页查询项目列表 |
| GET | /api/projects/{id} | 获取单个项目 |
| POST | /api/projects | 新增项目 |
| PUT | /api/projects/{id} | 更新项目 |
| DELETE | /api/projects/{id} | 删除项目 |
| POST | /api/projects/import | 导入项目Excel |
| GET | /api/projects/export | 导出项目列表 |
| GET | /api/projects/list | 获取项目下拉列表 |

### 5.2 服务管理API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/services | 分页查询服务列表 |
| GET | /api/services/{id} | 获取单个服务 |
| POST | /api/services | 新增服务 |
| PUT | /api/services/{id} | 更新服务 |
| DELETE | /api/services/{id} | 删除服务 |
| POST | /api/services/status/batch | 批量获取状态 |
| POST | /api/services/{id}/start | 启动服务 |
| POST | /api/services/{id}/stop | 停止服务 |
| POST | /api/services/{id}/restart | 重启服务 |
| GET | /api/services/{id}/log | 获取服务日志 |
| GET | /api/services/{id}/log/download | 下载日志文件 |
| POST | /api/services/import | 导入服务Excel |
| GET | /api/services/export | 导出服务列表 |

## 六、部署步骤

### 6.1 数据库初始化

执行数据库迁移脚本：
```sql
source backend/init_sql/003_create_projects_services_tables.sql
```

### 6.2 启动后端服务

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 6.3 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

## 七、功能特性

### 7.1 项目名称管理
- ✅ 项目增删改查
- ✅ 启用/停用开关
- ✅ Excel导入导出
- ✅ 项目编码唯一性校验

### 7.2 服务管理
- ✅ 服务CRUD管理
- ✅ 按项目筛选服务
- ✅ 状态监控（每10秒刷新）
- ✅ 远程启停（SSH执行脚本）
- ✅ 日志查看与下载
- ✅ 密码AES加密存储
- ✅ Excel导入导出

## 八、权限说明

模块使用现有系统的JWT认证机制，新增权限项：
- `project:manage` - 项目管理权限
- `service:manage` - 服务管理权限
- `service:operate` - 服务操作权限（启停等）

## 九、注意事项

1. 服务密码采用AES-256-GCM加密存储，前端不显示密码
2. 编辑服务时密码留空表示不修改
3. 服务必须关联一个项目（外键约束）
4. 删除项目会级联删除关联的服务
5. 状态监控采用TCP端口检测+SSH进程检测双重方式