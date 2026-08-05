from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from models.role import Role
from models.permission import Permission
from models.role_permission import RolePermission
from models.user_role import UserRole
from models.project import Project
from models.subsystem import Subsystem


DEFAULT_ROLES = [
    {
        "name": "超级管理员",
        "description": "拥有系统所有权限",
        "is_system": True,
    },
    {
        "name": "组织管理员",
        "description": "管理组织下的所有资源和用户",
        "is_system": True,
    },
    {
        "name": "部门管理员",
        "description": "管理部门下的资源和用户",
        "is_system": True,
    },
    {
        "name": "部门成员",
        "description": "部门内的普通成员，可查看和操作项目资源",
        "is_system": True,
    },
    {
        "name": "只读用户",
        "description": "仅可查看资源，无操作权限",
        "is_system": True,
    },
]

DEFAULT_PERMISSIONS = [
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

    # 3.3 容器管理（不包含 create/delete，SRMC 不管理容器生命周期创建销毁）
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

    # 3.8 主机管理（不包含 create/delete，主机由底层基础设施管理）
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

# 角色权限映射（按用户要求的预设权限表）
ROLE_PERMISSION_MAP = {
    "超级管理员": [p["resource"] + ":" + p["action"] for p in DEFAULT_PERMISSIONS],
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


class RolePermissionService:
    """RBAC角色权限管理服务"""

    @staticmethod
    def create_role(db: Session, name: str, description: str = None, is_system: bool = False) -> Role:
        """创建角色"""
        existing = db.query(Role).filter(Role.name == name).first()
        if existing:
            raise ValueError(f"角色 '{name}' 已存在")
        role = Role(name=name, description=description, is_system=is_system)
        db.add(role)
        db.commit()
        return role

    @staticmethod
    def update_role(db: Session, role_id: int, name: str = None, description: str = None) -> Role:
        """更新角色"""
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise ValueError("角色不存在")
        if role.is_system:
            raise ValueError("系统内置角色不可修改名称")
        if name:
            existing = db.query(Role).filter(Role.name == name, Role.id != role_id).first()
            if existing:
                raise ValueError(f"角色 '{name}' 已存在")
            role.name = name
        if description is not None:
            role.description = description
        db.commit()
        return role

    @staticmethod
    def delete_role(db: Session, role_id: int) -> bool:
        """删除角色"""
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise ValueError("角色不存在")
        if role.is_system:
            raise ValueError("系统内置角色不可删除")
        has_users = db.query(UserRole).filter(UserRole.role_id == role_id).count()
        if has_users > 0:
            raise ValueError("角色下还有用户，无法删除")
        db.delete(role)
        db.commit()
        return True

    @staticmethod
    def get_role(db: Session, role_id: int) -> Optional[Role]:
        """获取角色详情"""
        return db.query(Role).filter(Role.id == role_id).first()

    @staticmethod
    def list_roles(db: Session, include_system: bool = True) -> List[Role]:
        """获取角色列表"""
        query = db.query(Role)
        if not include_system:
            query = query.filter(Role.is_system == False)
        return query.all()

    @staticmethod
    def assign_permissions_to_role(db: Session, role_id: int, permission_ids: List[int]) -> bool:
        """为角色分配权限"""
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise ValueError("角色不存在")

        existing = db.query(RolePermission).filter(RolePermission.role_id == role_id).all()
        existing_ids = {rp.permission_id for rp in existing}

        for pid in permission_ids:
            if pid not in existing_ids:
                rp = RolePermission(role_id=role_id, permission_id=pid)
                db.add(rp)

        db.commit()
        return True

    @staticmethod
    def remove_permissions_from_role(db: Session, role_id: int, permission_ids: List[int]) -> bool:
        """移除角色的权限"""
        for pid in permission_ids:
            rp = db.query(RolePermission).filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == pid,
            ).first()
            if rp:
                db.delete(rp)
        db.commit()
        return True

    @staticmethod
    def get_role_permissions(db: Session, role_id: int) -> List[Dict[str, Any]]:
        """获取角色的所有权限"""
        rps = db.query(RolePermission).filter(RolePermission.role_id == role_id).all()
        result = []
        for rp in rps:
            perm = db.query(Permission).filter(Permission.id == rp.permission_id).first()
            if perm:
                result.append({
                    "id": perm.id,
                    "resource": perm.resource,
                    "action": perm.action,
                    "name": perm.name,
                    "description": perm.description,
                })
        return result

    @staticmethod
    def create_permission(db: Session, resource: str, action: str, name: str, description: str = None) -> Permission:
        """创建权限"""
        existing = db.query(Permission).filter(
            Permission.resource == resource,
            Permission.action == action,
        ).first()
        if existing:
            raise ValueError(f"权限 '{resource}:{action}' 已存在")
        perm = Permission(resource=resource, action=action, name=name, description=description)
        db.add(perm)
        db.commit()
        return perm

    @staticmethod
    def list_permissions(db: Session) -> List[Permission]:
        """获取所有权限"""
        return db.query(Permission).order_by(Permission.resource, Permission.action).all()

    @staticmethod
    def initialize_default_data(db: Session):
        """初始化默认角色和权限数据"""
        # 1. 创建权限
        for perm_data in DEFAULT_PERMISSIONS:
            existing = db.query(Permission).filter(
                Permission.resource == perm_data["resource"],
                Permission.action == perm_data["action"],
            ).first()
            if not existing:
                perm = Permission(
                    resource=perm_data["resource"],
                    action=perm_data["action"],
                    name=perm_data["name"],
                    description=perm_data.get("description"),
                )
                db.add(perm)

        # 2. 创建角色
        for role_data in DEFAULT_ROLES:
            existing = db.query(Role).filter(Role.name == role_data["name"]).first()
            if not existing:
                role = Role(
                    name=role_data["name"],
                    description=role_data["description"],
                    is_system=role_data["is_system"],
                )
                db.add(role)

        db.commit()

        # 3. 构建权限映射
        perm_map = {}
        for perm in db.query(Permission).all():
            perm_map[f"{perm.resource}:{perm.action}"] = perm

        # 4. 按预设分配角色权限
        for role_name, perm_keys in ROLE_PERMISSION_MAP.items():
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                continue

            existing_rp_ids = set()
            for rp in db.query(RolePermission).filter(RolePermission.role_id == role.id).all():
                existing_rp_ids.add(rp.permission_id)

            for perm_key in perm_keys:
                perm = perm_map.get(perm_key)
                if perm and perm.id not in existing_rp_ids:
                    rp = RolePermission(role_id=role.id, permission_id=perm.id)
                    db.add(rp)

        db.commit()

    @staticmethod
    def get_user_roles(db: Session, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的所有角色"""
        urs = db.query(UserRole).filter(UserRole.user_id == user_id).all()
        result = []
        for ur in urs:
            role = db.query(Role).filter(Role.id == ur.role_id).first()
            if role:
                result.append({
                    "id": role.id,
                    "name": role.name,
                    "description": role.description,
                    "is_system": role.is_system,
                })
        return result

    @staticmethod
    def assign_role(db: Session, user_id: int, role_id: int) -> UserRole:
        """为用户分配角色"""
        existing = db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        ).first()
        if existing:
            raise ValueError("用户已拥有该角色")
        ur = UserRole(user_id=user_id, role_id=role_id)
        db.add(ur)
        db.commit()
        return ur

    @staticmethod
    def revoke_role(db: Session, user_id: int, role_id: int) -> bool:
        """撤销用户角色"""
        ur = db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        ).first()
        if not ur:
            raise ValueError("用户不具有该角色")
        db.delete(ur)
        db.commit()
        return True

    @staticmethod
    def get_project_tree(db: Session) -> List[Dict[str, Any]]:
        """获取项目树（包含子系统）"""
        projects = db.query(Project).order_by(Project.id).all()
        result = []
        for proj in projects:
            subsystems = db.query(Subsystem).filter(
                Subsystem.project_id == proj.id
            ).order_by(Subsystem.display_order, Subsystem.id).all()
            sub_list = [
                {
                    "id": s.id,
                    "name": s.subsystem_name,
                    "code": s.subsystem_code,
                    "description": s.description,
                }
                for s in subsystems
            ]
            result.append({
                "id": proj.id,
                "name": proj.name,
                "code": proj.code,
                "description": proj.description,
                "visibility": proj.visibility,
                "subsystems": sub_list,
            })
        return result

    # 注：项目权限管理已迁移至 ProjectMemberService（项目角色）
    # 和 ProjectPermission（项目共享），不再通过系统角色配置项目权限
    # 系统角色与项目角色完全独立，避免概念混淆
