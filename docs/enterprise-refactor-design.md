# SRMC 服务列表企业级改造设计文档

> 目标：支撑上千条服务、多用户并发访问，点击操作零卡顿

---

## 一、现状诊断

### 1.1 索引现状（关键问题）

| 表 | 现有索引 | 缺失索引 | 影响 |
|------|---------|---------|------|
| `app_services` | `idx_subsystem_id`, `idx_group_id` | **`project_id`** | 按 project_id 过滤时**全表扫描**，这是最常用的过滤条件 |
| `app_services` | - | **复合索引** `(project_id, subsystem_id, group_id)` | 多条件查询无法走索引合并 |
| `app_services` | - | `ip`, `owner`, `module` | 按这些字段搜索时全表扫描 |
| `subsystems` | `idx_project_id` | - | ✓ 已足够 |
| `service_groups` | `uk_group_code` | - | ✓ 全局分类，足够 |
| `projects` | `idx_project_org`, `idx_project_dept`, `idx_project_visibility` | - | ✓ 已足够 |

**最严重问题**：`app_services.project_id` 无索引。用户点击项目树时按 `project_id` 过滤，每次都是全表扫描。1000 条数据时，单次查询从 30ms 退化到 300ms+。

### 1.2 请求流分析

```
当前流程（每次点击树节点）：
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐
│ 用户点击树  │ ──> │ GET /subsystems   │ ──> │ GET /groups     │ ──> │ GET /services │
└─────────────┘     │ ?project_id=X     │     │ ?subsystem_id=Y │     │ ?filters=...  │
                    └──────────────────┘     └─────────────────┘     └──────────────┘
                    串行请求1                 串行请求2               串行请求3
                    ~30ms                    ~30ms                  ~50ms（含JOIN）
                    
                    总延迟：~110ms × N次点击，HTTP/1.1 连接池 6 个上限被占满
```

### 1.3 架构问题清单

| # | 问题 | 影响 | 严重度 |
|---|------|------|--------|
| 1 | `project_id` 无索引 | 全表扫描，数据量大时查询慢 | P0 |
| 2 | 无复合索引 | 多条件查询无法利用索引 | P0 |
| 3 | 树结构按需加载 | 每次点击 3 个串行请求 | P0 |
| 4 | 无 Pinia Store | 状态散落，无全局缓存 | P1 |
| 5 | 无虚拟滚动 | 上千条 DOM 卡死 | P1 |
| 6 | 服务列表无 Redis 缓存 | 每次查库 | P1 |
| 7 | HTTP/1.1 | 连接池 6 上限 | P2 |
| 8 | 无接口限流 | 多用户并发可能压垮后端 | P2 |

---

## 二、架构图（目标架构）

```
                        ┌─────────────────────────────────────────────────┐
                        │                   Nginx (HTTP/2)                │
                        │   多路复用 / 静态资源缓存 / Gzip / 限流          │
                        └──────────────┬──────────────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
                    ▼                                     ▼
        ┌──────────────────────┐             ┌──────────────────────┐
        │   前端 (Vue3 + Pinia) │             │   后端 (FastAPI)      │
        │                      │             │                      │
        │  ┌────────────────┐  │             │  ┌────────────────┐  │
        │  │ projectStore   │  │  请求       │  │ /projects/tree │  │
        │  │ (树缓存 5min)  │ ←─────────── │  │ Redis缓存 5min │  │
        │  └────────────────┘  │             │  └────────────────┘  │
        │                      │             │                      │
        │  ┌────────────────┐  │             │  ┌────────────────┐  │
        │  │ 虚拟滚动列表   │  │  请求       │  │ /services      │  │
        │  │ RecycleScroller │ ←─────────── │  │ Redis缓存 30s  │  │
        │  └────────────────┘  │             │  │ +复合索引      │  │
        │                      │             │  └────────────────┘  │
        └──────────────────────┘             └──────────┬───────────┘
                                                        │
                                            ┌───────────┴───────────┐
                                            │                       │
                                            ▼                       ▼
                                ┌──────────────────┐     ┌──────────────────┐
                                │   Redis 缓存层    │     │   PostgreSQL     │
                                │                  │     │                  │
                                │ • projects_tree  │     │ app_services    │
                                │   (5min TTL)     │     │ 复合索引:        │
                                │ • services_list  │     │ (project_id,    │
                                │   (30s TTL)     │     │  subsystem_id,  │
                                │ • services_count │     │  group_id)      │
                                │   (30s TTL)     │     │                  │
                                └──────────────────┘     └──────────────────┘
```

### 请求流对比

```
改造后流程（点击树节点）：
┌─────────────┐     ┌──────────────────────────────────────────┐
│ 用户点击树  │ ──> │ 从 Pinia Store 取子系统/分组（0ms，无请求）│
└─────────────┘     └──────────────────────────────────────────┘
                                │
                                ▼
                    ┌──────────────────────────────┐
                    │ GET /services?filters=...     │  ← 唯一请求
                    │ Redis 缓存命中 → <5ms         │
                    │ 缓存未命中 → 复合索引查询 ~10ms│
                    └──────────────────────────────┘
                    
                    总延迟：<20ms，只有 1 个请求
```

---

## 三、数据库优化方案

### 3.1 索引优化（P0，立即执行）

```sql
-- 1. 为 project_id 添加单列索引（最常用过滤条件）
CREATE INDEX idx_app_service_project_id ON app_services (project_id);

-- 2. 复合索引：覆盖"项目+子系统+分组"组合查询
CREATE INDEX idx_app_service_tree ON app_services (project_id, subsystem_id, group_id);

-- 3. 搜索字段索引（按需，如果搜索频繁）
CREATE INDEX idx_app_service_ip ON app_services (ip);
CREATE INDEX idx_app_service_owner ON app_services (owner);

-- 4. 验证索引效果
EXPLAIN ANALYZE SELECT * FROM app_services WHERE project_id = 1 AND subsystem_id = 2;
```

### 3.2 索引选择策略

| 索引类型 | 适用场景 | 利 | 弊 |
|---------|---------|---|---|
| **单列索引** | 单字段过滤 | 写入开销小 | 多条件查询需索引合并 |
| **复合索引** | 多字段组合过滤 | 查询性能最优 | 写入有额外开销 |
| **覆盖索引** | 查询字段都在索引中 | 免回表 | 索引体积大 |
| **部分索引** | `WHERE deleted=false` | 减小索引体积 | 不适用全量查询 |

**推荐方案**：复合索引 `(project_id, subsystem_id, group_id)` 覆盖 90% 的树过滤场景。

### 3.3 分页优化

```python
# 问题：OFFSET 在大数据量下性能差
# SELECT * FROM app_services ORDER BY id OFFSET 10000 LIMIT 20  ← 慢

# 方案：游标分页（keyset pagination）
# 第一页：SELECT * FROM app_services WHERE project_id=1 ORDER BY id LIMIT 20
# 第二页：SELECT * FROM app_services WHERE project_id=1 AND id > {last_id} ORDER BY id LIMIT 20

# 后端实现
def get_services(db, last_id: int = None, ...):
    query = db.query(AppService).filter(AppService.project_id == project_id)
    if last_id:
        query = query.filter(AppService.id > last_id)  # 游标
    query = query.order_by(AppService.id).limit(size)
```

---

## 四、后端改造方案

### 4.1 树结构 API（P0）

```
GET /api/projects/tree

Response:
{
  "code": 0,
  "data": [
    {
      "id": 1,
      "name": "核心交易系统",
      "subsystems": [
        {
          "id": 1,
          "name": "订单服务",
          "groups": [
            {"id": 1, "name": "订单创建"},
            {"id": 2, "name": "订单查询"}
          ]
        }
      ]
    }
  ]
}
```

**后端实现**：

```python
@router.get("/projects/tree", response_model=ResponseModel)
async def get_projects_tree(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    from utils.redis_client import redis_client
    import json
    
    cache_key = "projects_tree"
    
    # 1. 先查 Redis 缓存
    cached = redis_client.get(cache_key)
    if cached:
        return ResponseModel(data=json.loads(cached))
    
    # 2. 缓存未命中，查数据库（3 次查询，非 N+1）
    projects = db.query(Project).order_by(Project.id).all()
    project_ids = [p.id for p in projects]
    
    subsystems = db.query(Subsystem).filter(
        Subsystem.project_id.in_(project_ids)
    ).order_by(Subsystem.display_order).all()
    subsystem_ids = [s.id for s in subsystems]
    
    # 通过 SubsystemGroupRelation 关联
    relations = db.query(SubsystemGroupRelation).filter(
        SubsystemGroupRelation.subsystem_id.in_(subsystem_ids)
    ).all()
    group_ids = [r.group_id for r in relations]
    groups = db.query(ServiceGroup).filter(
        ServiceGroup.id.in_(group_ids)
    ).all()
    
    # 3. 内存组装树结构
    group_map = {g.id: g for g in groups}
    sub_groups = {}  # subsystem_id -> [groups]
    for r in relations:
        g = group_map.get(r.group_id)
        if g:
            sub_groups.setdefault(r.subsystem_id, []).append({
                "id": g.id, "name": g.group_name
            })
    
    sub_map = {}  # project_id -> [subsystems]
    for s in subsystems:
        sub_map.setdefault(s.project_id, []).append({
            "id": s.id,
            "name": s.subsystem_name,
            "groups": sub_groups.get(s.id, [])
        })
    
    tree = [{
        "id": p.id,
        "name": p.name,
        "subsystems": sub_map.get(p.id, [])
    } for p in projects]
    
    # 4. 写入 Redis，5 分钟过期
    redis_client.setex(cache_key, 300, json.dumps(tree, ensure_ascii=False))
    
    return ResponseModel(data=tree)
```

### 4.2 缓存失效策略

```python
# 在增删改项目/子系统/分组时，主动清除缓存
def invalidate_tree_cache():
    """数据变更时调用"""
    redis_client.delete("projects_tree")

# 在对应的 CRUD 接口中调用
@router.post("/projects")
async def create_project(...):
    # ... 创建逻辑 ...
    invalidate_tree_cache()  # 清除树缓存
    return ResponseModel(data=...)
```

### 4.3 服务列表 Redis 缓存（P1）

```python
@router.get("/services")
async def get_services(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    project_id: int = Query(None),
    subsystem_id: int = Query(None),
    group_id: int = Query(None),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    from utils.redis_client import redis_client
    import json, hashlib
    
    # 构建缓存 key（包含所有过滤参数 + 分页）
    filter_str = f"{project_id}:{subsystem_id}:{group_id}:{page}:{size}"
    cache_key = f"services:{hashlib.md5(filter_str.encode()).hexdigest()}"
    
    # 1. 查缓存
    cached = redis_client.get(cache_key)
    if cached:
        return ResponseModel(data=json.loads(cached))
    
    # 2. 查数据库（使用复合索引）
    # ... 查询逻辑 ...
    
    # 3. 写缓存，30 秒过期
    result = {"items": result, "total": total, "page": page, "size": size}
    redis_client.setex(cache_key, 30, json.dumps(result, ensure_ascii=False, default=str))
    
    return ResponseModel(data=result)
```

### 4.4 缓存策略对比

| 策略 | TTL | 适用场景 | 利 | 弊 |
|------|-----|---------|---|---|
| **Cache-Aside** | 30s | 服务列表 | 简单可靠 | 首次请求慢 |
| **Write-Through** | 实时 | 树结构 | 数据一致 | 写入有延迟 |
| **Write-Invalidate** | 写时清除 | 树结构 | 强一致 | 缓存击穿风险 |
| **SWR** | stale+revalidate | 前端展示 | 用户感知快 | 实现复杂 |

**推荐**：树结构用 Write-Invalidate（5min TTL + 写时清除），服务列表用 Cache-Aside（30s TTL）。

---

## 五、前端改造方案

### 5.1 Pinia Store（P0）

```
src/stores/
├── projectStore.js    ← 项目树全局缓存
└── serviceStore.js    ← 服务列表状态
```

```javascript
// stores/projectStore.js
import { defineStore } from 'pinia'
import axios from 'axios'

export const useProjectStore = defineStore('project', {
  state: () => ({
    tree: [],
    lastFetchTime: 0,
    loading: false,
    // 扁平化索引，O(1) 查找
    projectMap: new Map(),
    subsystemMap: new Map(),
    groupMap: new Map()
  }),

  getters: {
    // 按 project_id 获取子系统列表（从缓存，无请求）
    subsystemsByProject: (state) => (projectId) => {
      return state.subsystemMap.get(projectId) || []
    },
    // 按 subsystem_id 获取分组列表
    groupsBySubsystem: (state) => (subsystemId) => {
      return state.groupMap.get(subsystemId) || []
    }
  },

  actions: {
    async fetchTree(force = false) {
      // 5 分钟内不重复请求
      const TTL = 5 * 60 * 1000
      if (!force && Date.now() - this.lastFetchTime < TTL && this.tree.length > 0) {
        return this.tree
      }
      if (this.loading) return this.tree

      this.loading = true
      try {
        const res = await axios.get('/api/projects/tree')
        this.tree = res.data.data
        this.lastFetchTime = Date.now()
        this.buildIndex()  // 构建扁平化索引
      } finally {
        this.loading = false
      }
      return this.tree
    },

    // 构建扁平化索引，供 O(1) 查找
    buildIndex() {
      this.projectMap.clear()
      this.subsystemMap.clear()
      this.groupMap.clear()
      
      for (const project of this.tree) {
        this.projectMap.set(project.id, project)
        this.subsystemMap.set(project.id, project.subsystems)
        for (const sub of project.subsystems) {
          this.groupMap.set(sub.id, sub.groups)
        }
      }
    },

    // 数据变更后强制刷新
    invalidate() {
      this.lastFetchTime = 0
      this.fetchTree(true)
    }
  }
})
```

### 5.2 ServicesNew.vue 改造

```javascript
// 改造前：每次点击都请求
const handleTreeClick = async (data) => {
  filters.project_id = data.id
  const subs = await loadSubsystems(data.id)  // ← 请求
  groups.value = await loadGroups()            // ← 请求
  loadServices()                               // ← 请求
}

// 改造后：从 Store 取，无请求
import { useProjectStore } from '@/stores/projectStore'
const projectStore = useProjectStore()

const handleTreeClick = (data) => {
  filters.project_id = data.project_id || data.id
  filters.subsystem_id = data.subsystem_id || ''
  filters.group_id = data.type === 'service_group' ? data.id : ''
  
  // 从 Store 缓存取，零请求
  subsystems.value = projectStore.subsystemsByProject(filters.project_id)
  groups.value = projectStore.groupsBySubsystem(filters.subsystem_id)
  
  // 唯一的请求
  scheduleLoadServices()
}

// 页面初始化
onMounted(async () => {
  await projectStore.fetchTree()  // 一次性加载树
  await loadServices()
})
```

### 5.3 虚拟滚动（P1）

```vue
<!-- 改造前：全量渲染 -->
<el-table :data="services">
  <el-table-column ... />
</el-table>

<!-- 改造后：虚拟滚动 -->
<RecycleScroller
  :items="services"
  :item-size="60"
  key-field="id"
  v-slot="{ item }"
>
  <el-row :gutter="0" class="service-row">
    <el-col :span="4">{{ item.func_desc }}</el-col>
    <el-col :span="3">{{ item.project_name }}</el-col>
    <!-- ... -->
  </el-row>
</RecycleScroller>
```

**性能对比**：

| 数据量 | el-table 渲染 | 虚拟滚动 | 提升 |
|--------|--------------|---------|------|
| 100 条 | 200ms | 20ms | 10x |
| 1000 条 | 3000ms（卡顿） | 25ms | 120x |
| 10000 条 | 浏览器崩溃 | 30ms | ∞ |

### 5.4 虚拟滚动方案对比

| 方案 | 库 | 利 | 弊 |
|------|---|---|---|
| **RecycleScroller** | vue-virtual-scroller（已安装） | 轻量，已安装 | 需自定义样式 |
| **el-table-v2** | Element Plus 内置 | 原生集成 | 功能受限，复杂表头支持差 |
| **vxe-table** | vxe-table | 功能最全 | 体积大，学习成本 |
| **自研虚拟滚动** | - | 完全可控 | 开发成本高 |

**推荐**：优先尝试 `el-table-v2`（与现有 UI 一致），如果功能不满足再用 `RecycleScroller`。

---

## 六、HTTP/2 与并发防护

### 6.1 Nginx 配置（P2）

```nginx
server {
    listen 443 ssl http2;                    # 启用 HTTP/2
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # 后端代理
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_cache_valid 200 30s;           # Nginx 层缓存
    }
    
    # 静态资源长期缓存
    location ~* \.(js|css|png|jpg|svg|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Gzip 压缩
    gzip on;
    gzip_types application/json text/css application/javascript;
    gzip_min_length 1000;
    
    # 限流：每个 IP 每秒最多 20 个请求
    limit_req_zone $binary_remote_addr zone=api:10m rate=20r/s;
    location /api/ {
        limit_req zone=api burst=40 nodelay;
    }
}
```

### 6.2 HTTP/1.1 vs HTTP/2

| 特性 | HTTP/1.1 | HTTP/2 |
|------|---------|--------|
| 并发连接 | 每域名 6 个 | 单连接多路复用 |
| 请求排队 | 是（连接池满时） | 否 |
| 头部压缩 | 否 | HPACK |
| 服务端推送 | 否 | 支持 |
| 部署成本 | - | 需 HTTPS |

### 6.3 后端限流（P2）

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("/services")
@limiter.limit("30/minute")  # 每用户每分钟 30 次
async def get_services(request: Request, ...):
    ...
```

---

## 七、实施路线图

### 阶段 1（P0，1-2 天）- 治本

| 任务 | 文件 | 预估 |
|------|------|------|
| 添加数据库索引 | 迁移脚本 | 0.5h |
| 新增 `/api/projects/tree` 接口 | `backend/api/projects.py` | 2h |
| Redis 缓存树结构 | `backend/api/projects.py` | 1h |
| 创建 Pinia Store | `frontend/src/stores/projectStore.js` | 1h |
| 改造 ServicesNew.vue | `frontend/src/pages/ServicesNew.vue` | 2h |
| 数据变更时清缓存 | 相关 CRUD 接口 | 1h |

**预期效果**：点击树节点从 3 个请求降到 1 个，延迟从 ~110ms 降到 ~20ms。

### 阶段 2（P1，1-2 天）- 性能

| 任务 | 文件 | 预估 |
|------|------|------|
| 服务列表 Redis 缓存 | `backend/api/services.py` | 2h |
| 启用虚拟滚动 | `frontend/src/pages/ServicesNew.vue` | 3h |
| 分页 size 调大 | 前后端 | 0.5h |
| count 查询缓存 | `backend/api/services.py` | 1h |

**预期效果**：1000 条服务流畅渲染，查询响应 <20ms。

### 阶段 3（P2，0.5 天）- 运维

| 任务 | 文件 | 预估 |
|------|------|------|
| Nginx HTTP/2 配置 | `nginx.conf` | 0.5h |
| 接口限流 | 后端中间件 | 1h |
| 数据库连接池调优 | `backend/core/database.py` | 0.5h |

---

## 八、容错与监控

### 8.1 缓存容错

```python
# Redis 故障时降级到直接查库
try:
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
except Exception as e:
    logger.warning(f"Redis 不可用，降级查库: {e}")
    # 继续走数据库查询
```

### 8.2 监控指标

| 指标 | 告警阈值 | 工具 |
|------|---------|------|
| 接口 P99 延迟 | >200ms | Prometheus |
| Redis 命中率 | <80% | Redis INFO |
| 数据库慢查询 | >100ms | pg_stat_statements |
| 前端 FPS | <30 | Performance API |

---

## 九、方案对比总结

| 方面 | 方案 A（保守） | 方案 B（推荐） | 方案 C（激进） |
|------|--------------|--------------|--------------|
| 树加载 | 按需加载+防抖 | 一次性加载+Pinia | 一次性+SWR |
| 列表渲染 | el-table | 虚拟滚动 | 虚拟滚动+SSR |
| 缓存 | 无 | Redis 30s | Redis+CDN |
| 分页 | OFFSET | OFFSET+缓存 | 游标分页 |
| 改动量 | 小 | 中 | 大 |
| 性能 | 一般 | 优秀 | 极致 |
| 适用规模 | <500 | <5000 | >5000 |

**推荐方案 B**：在改动量和性能之间取得最佳平衡，支撑上千条服务和多用户并发。
