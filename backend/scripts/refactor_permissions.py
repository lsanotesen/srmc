"""
RBAC 权限体系重构脚本

重构原则：
1. 权限名称必须与系统实际功能完全一致
2. 不暴露底层技术实现细节
3. 不使用系统中不会出现的操作
4. 每个权限点必须对应一个真实存在的业务操作

删除的无效权限：
- docker:create, docker:remove (SRMC 不创建/销毁容器)
- image:delete (SRMC 不管理镜像删除)

新增的权限：
- container:start, container:stop, container:restart
- webshell:root-login
- organization:view, organization:edit
- department:view, department:edit
- user:view, user:add, user:edit, user:delete
- role:view, role:edit
- service:deploy, service:edit-config
- script:view
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from core.config import settings

# 新的权限定义（按用户要求的完整权限树）
NEW_PERMISSIONS = [
    # 3.1 项目管理
    {"resource": "project", "action": "view", "name": "查看项目", "description": "查看项目列表和详情"},
    {"resource": "project", "action": "add", "name": "创建项目", "description": "新建项目"},
    {"resource": "project", "action": "edit", "name": "编辑项目", "description": "修改项目基本信息"},
    {"resource": "project", "action": "delete", "name": "删除项目", "description": "删除项目"},
    {"resource": "project", "action": "share", "name": "共享项目", "description": "将项目共享给组织/部门/用户"},

    # 3.2 服务管理
    {"resource": "service", "action": "view", "name": "查看服务", "description": "查看服务列表和详情"},
    {"resource": "service", "action": "start", "name": "启动服务", "description": "启动已停止的服务"},
    {"resource": "service", "action": "stop", "name": "停止服务", "description": "停止运行中的服务"},
    {"resource": "service", "action": "restart", "name": "重启服务", "description": "重启服务"},
    {"resource": "service", "action": "deploy", "name": "部署服务", "description": "部署新版本服务"},
    {"resource": "service", "action": "edit-config", "name": "修改服务配置", "description": "修改服务的配置文件"},

    # 3.3 容器管理
    {"resource": "container", "action": "view", "name": "查看容器", "description": "查看容器列表和状态"},
    {"resource": "container", "action": "exec", "name": "进入容器", "description": "通过 Exec 进入容器内部"},
    {"resource": "container", "action": "start", "name": "启动容器", "description": "启动已停止的容器"},
    {"resource": "container", "action": "stop", "name": "停止容器", "description": "停止运行中的容器"},
    {"resource": "container", "action": "restart", "name": "重启容器", "description": "重启容器"},

    # 3.4 WebShell
    {"resource": "webshell", "action": "login", "name": "WebShell 登录", "description": "通过 WebShell 登录主机"},
    {"resource": "webshell", "action": "root-login", "name": "Root WebShell 登录", "description": "通过 WebShell 以 Root 身份登录主机"},

    # 3.5 日志管理
    {"resource": "log", "action": "view", "name": "查看日志", "description": "查看服务/系统日志"},
    {"resource": "log", "action": "download", "name": "下载日志", "description": "下载日志文件"},

    # 3.6 脚本管理
    {"resource": "script", "action": "view", "name": "查看脚本", "description": "查看脚本列表和内容"},
    {"resource": "script", "action": "run", "name": "执行脚本", "description": "执行脚本"},

    # 3.7 Agent 管理
    {"resource": "agent", "action": "view", "name": "查看 Agent", "description": "查看 Agent 列表和状态"},
    {"resource": "agent", "action": "manage", "name": "管理 Agent", "description": "管理 Agent 配置"},

    # 3.8 主机管理
    {"resource": "host", "action": "view", "name": "查看主机", "description": "查看主机列表和详情"},
    {"resource": "host", "action": "reboot", "name": "重启主机", "description": "重启主机"},

    # 3.9 组织管理
    {"resource": "organization", "action": "view", "name": "查看组织", "description": "查看组织信息"},
    {"resource": "organization", "action": "edit", "name": "编辑组织", "description": "修改组织基本信息"},

    # 3.10 部门管理
    {"resource": "department", "action": "view", "name": "查看部门", "description": "查看部门列表和详情"},
    {"resource": "department", "action": "edit", "name": "编辑部门", "description": "修改部门基本信息"},

    # 3.11 用户管理
    {"resource": "user", "action": "view", "name": "查看用户", "description": "查看用户列表和详情"},
    {"resource": "user", "action": "add", "name": "创建用户", "description": "新建用户"},
    {"resource": "user", "action": "edit", "name": "编辑用户", "description": "修改用户信息"},
    {"resource": "user", "action": "delete", "name": "删除用户", "description": "删除用户"},

    # 3.12 角色管理
    {"resource": "role", "action": "view", "name": "查看角色", "description": "查看角色列表和详情"},
    {"resource": "role", "action": "edit", "name": "编辑角色", "description": "创建/修改/删除角色及权限分配"},

    # 3.13 审计日志
    {"resource": "audit", "action": "view", "name": "查看审计日志", "description": "查看审计日志列表和详情"},
]

# 角色权限分配表（按用户要求的预设权限）
ROLE_PERMISSION_MAP = {
    "超级管理员": [
        # 所有权限
        "project:view", "project:add", "project:edit", "project:delete", "project:share",
        "service:view", "service:start", "service:stop", "service:restart", "service:deploy", "service:edit-config",
        "container:view", "container:exec", "container:start", "container:stop", "container:restart",
        "webshell:login", "webshell:root-login",
        "log:view", "log:download",
        "script:view", "script:run",
        "agent:view", "agent:manage",
        "host:view", "host:reboot",
        "organization:view", "organization:edit",
        "department:view", "department:edit",
        "user:view", "user:add", "user:edit", "user:delete",
        "role:view", "role:edit",
        "audit:view",
    ],
    "组织管理员": [
        "project:view", "project:add", "project:edit", "project:delete", "project:share",
        "service:view", "service:start", "service:stop", "service:restart", "service:deploy", "service:edit-config",
        "container:view", "container:exec", "container:start", "container:stop", "container:restart",
        "webshell:login",
        "log:view", "log:download",
        "script:view", "script:run",
        "agent:view", "agent:manage",
        "host:view", "host:reboot",
        "organization:view", "organization:edit",
        "department:view", "department:edit",
        "user:view", "user:add", "user:edit",
        "role:view",
        "audit:view",
    ],
    "部门管理员": [
        "project:view", "project:add", "project:edit", "project:delete", "project:share",
        "service:view", "service:start", "service:stop", "service:restart",
        "container:view", "container:exec", "container:start", "container:stop", "container:restart",
        "webshell:login",
        "log:view", "log:download",
        "script:view", "script:run",
        "agent:view", "agent:manage",
        "host:view",
        "organization:view",
        "department:view",
        "audit:view",
    ],
    "部门成员": [
        "project:view", "project:add", "project:edit", "project:delete", "project:share",
        "service:view", "service:start", "service:stop", "service:restart",
        "container:view", "container:exec", "container:start", "container:stop", "container:restart",
        "webshell:login",
        "log:view",
        "script:view",
        "agent:view",
        "host:view",
        "organization:view",
        "department:view",
    ],
    "只读用户": [
        "project:view",
        "service:view",
        "container:view",
        "log:view",
        "script:view",
        "agent:view",
        "host:view",
        "organization:view",
        "department:view",
    ],
}


def run_refactor():
    """执行权限重构"""
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        print("=" * 60)
        print("RBAC 权限体系重构开始")
        print("=" * 60)

        # 1. 清理旧的无效权限
        print("\n[步骤1] 清理无效权限...")
        invalid_perms = [
            ("docker", "create"),
            ("docker", "remove"),
            ("image", "view"),
            ("image", "delete"),
            ("config", "view"),
            ("config", "edit"),
            ("file", "upload"),
            ("file", "delete"),
            ("user", "manage"),
            ("role", "manage"),
        ]

        for resource, action in invalid_perms:
            result = db.execute(text(
                "DELETE FROM role_permissions WHERE permission_id IN "
                "(SELECT id FROM permissions WHERE resource = :resource AND action = :action)"
            ), {"resource": resource, "action": action})
            result = db.execute(text(
                "DELETE FROM permissions WHERE resource = :resource AND action = :action"
            ), {"resource": resource, "action": action})
            if result.rowcount > 0:
                print(f"  删除无效权限: {resource}:{action}")

        # 2. 迁移 docker -> container
        print("\n[步骤2] 迁移 docker 权限到 container...")
        docker_to_container = {
            "view": "view",
            "exec": "exec",
        }
        for old_action, new_action in docker_to_container.items():
            # 检查是否已存在 container 权限
            existing = db.execute(text(
                "SELECT id FROM permissions WHERE resource = 'container' AND action = :action"
            ), {"action": new_action}).fetchone()

            if not existing:
                # 更新 docker -> container
                db.execute(text(
                    "UPDATE permissions SET resource = 'container' "
                    "WHERE resource = 'docker' AND action = :action"
                ), {"action": old_action})
                print(f"  迁移: docker:{old_action} -> container:{new_action}")

        db.commit()

        # 3. 插入新权限
        print("\n[步骤3] 插入新权限...")
        for perm in NEW_PERMISSIONS:
            existing = db.execute(text(
                "SELECT id FROM permissions WHERE resource = :resource AND action = :action"
            ), {"resource": perm["resource"], "action": perm["action"]}).fetchone()

            if not existing:
                db.execute(text(
                    "INSERT INTO permissions (resource, action, name, description, created_at) "
                    "VALUES (:resource, :action, :name, :description, NOW())"
                ), perm)
                print(f"  新增: {perm['resource']}:{perm['action']} - {perm['name']}")

        db.commit()

        # 4. 获取所有权限映射
        print("\n[步骤4] 构建权限映射...")
        perm_map = {}
        for row in db.execute(text("SELECT id, resource, action FROM permissions")):
            perm_map[f"{row.resource}:{row.action}"] = row.id

        # 5. 获取角色映射
        role_map = {}
        for row in db.execute(text("SELECT id, name FROM roles")):
            role_map[row.name] = row.id

        # 6. 清空旧的权限关联，重新分配
        print("\n[步骤5] 重新分配角色权限...")
        for role_name, perm_keys in ROLE_PERMISSION_MAP.items():
            role_id = role_map.get(role_name)
            if not role_id:
                print(f"  警告: 角色 '{role_name}' 不存在，跳过")
                continue

            # 清空该角色的旧权限
            db.execute(text("DELETE FROM role_permissions WHERE role_id = :role_id"), {"role_id": role_id})

            # 分配新权限
            added_count = 0
            for perm_key in perm_keys:
                perm_id = perm_map.get(perm_key)
                if perm_id:
                    db.execute(text(
                        "INSERT INTO role_permissions (role_id, permission_id, created_at) "
                        "VALUES (:role_id, :perm_id, NOW())"
                    ), {"role_id": role_id, "perm_id": perm_id})
                    added_count += 1
                else:
                    print(f"  警告: 权限 '{perm_key}' 不存在")

            print(f"  {role_name}: 分配 {added_count} 个权限")

        db.commit()

        # 7. 显示最终权限列表
        print("\n[步骤6] 验证权限列表...")
        perms = db.execute(text(
            "SELECT resource, action, name FROM permissions ORDER BY resource, action"
        )).fetchall()

        print(f"\n共 {len(perms)} 个权限点:")
        current_resource = None
        for p in perms:
            if p.resource != current_resource:
                current_resource = p.resource
                print(f"\n{current_resource}:")
            print(f"  {p.action}: {p.name}")

        print("\n" + "=" * 60)
        print("RBAC 权限体系重构完成！")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n错误: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_refactor()