from typing import Optional, List, Dict, Any
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import or_
from models.role import Role
from models.permission import Permission
from models.role_permission import RolePermission
from models.user_role import UserRole
from models.user import User
from core.capabilities import ROLE_PERMISSIONS


SYSTEM_PERMISSIONS = {
    # 项目管理
    "project:view", "project:add", "project:edit", "project:delete", "project:share",
    # 服务管理
    "service:view", "service:start", "service:stop", "service:restart", "service:deploy", "service:edit-config",
    # 容器管理（不包含 create/delete）
    "container:view", "container:exec", "container:start", "container:stop", "container:restart",
    # WebShell
    "webshell:login", "webshell:root-login",
    # 主机管理（不包含 create/delete）
    "host:view", "host:reboot",
    # 日志管理
    "log:view", "log:download",
    # 脚本管理
    "script:view", "script:run",
    # Agent 管理
    "agent:view", "agent:manage",
    # 组织管理
    "organization:view", "organization:edit",
    # 部门管理
    "department:view", "department:edit",
    # 用户管理
    "user:view", "user:add", "user:edit", "user:delete",
    # 角色管理
    "role:view", "role:edit",
    # 审计日志
    "audit:view",
}


class PermissionService:
    """
    第二层：RBAC功能权限服务
    负责：菜单权限、API权限、按钮权限、功能操作权限
    """

    @staticmethod
    def user_has_permission(db: Session, user_id: int, permission_code: str) -> bool:
        """判断用户是否拥有指定功能权限"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        if user.role == "SUPER_ADMIN":
            return True

        legacy_permissions = ROLE_PERMISSIONS.get(user.role, [])
        if PermissionService._match_legacy_permission(permission_code, legacy_permissions):
            return True

        user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
        if not user_roles:
            return False

        role_ids = [ur.role_id for ur in user_roles]

        rp_count = db.query(RolePermission).join(Permission).filter(
            RolePermission.role_id.in_(role_ids),
            Permission.resource == permission_code.split(":")[0],
            Permission.action == permission_code.split(":")[1],
        ).count()

        return rp_count > 0

    @staticmethod
    def _match_legacy_permission(permission_code: str, legacy_permissions: List[str]) -> bool:
        """匹配旧版权限码（用于兼容旧用户角色）"""
        legacy_map = {
            # 项目管理
            "project:view": ["project_view"],
            "project:add": ["project_manage"],
            "project:edit": ["project_manage"],
            "project:delete": ["project_manage"],
            "project:share": ["project_manage"],
            # 服务管理
            "service:view": ["service_view"],
            "service:start": ["service_operate", "service_manage"],
            "service:stop": ["service_operate", "service_manage"],
            "service:restart": ["service_operate", "service_manage"],
            "service:deploy": ["service_manage"],
            "service:edit-config": ["service_manage"],
            # 容器管理（docker 权限映射到 container）
            "container:view": ["service_view"],
            "container:exec": ["webshell"],
            "container:start": ["service_operate", "service_manage"],
            "container:stop": ["service_operate", "service_manage"],
            "container:restart": ["service_operate", "service_manage"],
            # WebShell
            "webshell:login": ["webshell"],
            "webshell:root-login": ["service_manage"],
            # 主机管理
            "host:view": ["service_view"],
            "host:reboot": ["service_manage"],
            # 日志管理
            "log:view": ["log_view"],
            "log:download": ["log_download"],
            # 脚本管理
            "script:view": ["service_view"],
            "script:run": ["webshell", "service_operate"],
            # Agent 管理
            "agent:view": ["agent_view"],
            "agent:manage": ["agent_manage"],
            # 组织管理
            "organization:view": ["project_view"],
            "organization:edit": ["user_manage"],
            # 部门管理
            "department:view": ["project_view"],
            "department:edit": ["user_manage"],
            # 用户管理
            "user:view": ["user_manage"],
            "user:add": ["user_manage"],
            "user:edit": ["user_manage"],
            "user:delete": ["user_manage"],
            # 角色管理
            "role:view": ["user_manage"],
            "role:edit": ["user_manage"],
            # 审计日志
            "audit:view": ["audit_view"],
        }

        allowed_legacy = legacy_map.get(permission_code, [])
        return any(lp in legacy_permissions for lp in allowed_legacy)

    @staticmethod
    def get_user_permissions(db: Session, user_id: int) -> List[str]:
        """获取用户的所有功能权限"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        permissions = set()

        if user.role == "SUPER_ADMIN":
            return list(SYSTEM_PERMISSIONS)

        legacy_perms = ROLE_PERMISSIONS.get(user.role, [])
        for lp in legacy_perms:
            matched = PermissionService._reverse_match_legacy_permission(lp)
            permissions.update(matched)

        user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
        role_ids = [ur.role_id for ur in user_roles]

        if role_ids:
            rps = db.query(RolePermission).join(Permission).filter(
                RolePermission.role_id.in_(role_ids)
            ).all()
            for rp in rps:
                perm = db.query(Permission).filter(Permission.id == rp.permission_id).first()
                if perm:
                    permissions.add(f"{perm.resource}:{perm.action}")

        return list(permissions)

    @staticmethod
    def _reverse_match_legacy_permission(legacy_perm: str) -> List[str]:
        """旧版权限码转换为新版权限码（用于兼容旧用户角色）"""
        reverse_map = {
            "project_view": ["project:view"],
            "project_manage": ["project:add", "project:edit", "project:delete", "project:share"],
            "service_view": ["service:view", "container:view", "host:view", "script:view"],
            "service_operate": ["service:start", "service:stop", "service:restart", "script:run", "container:start", "container:stop", "container:restart"],
            "service_manage": ["service:deploy", "service:edit-config", "host:reboot", "webshell:root-login"],
            "webshell": ["webshell:login", "container:exec", "script:run"],
            "log_view": ["log:view"],
            "log_download": ["log:download"],
            "agent_view": ["agent:view"],
            "agent_manage": ["agent:manage"],
            "audit_view": ["audit:view"],
            "user_manage": ["user:view", "user:add", "user:edit", "user:delete", "role:view", "role:edit", "organization:edit", "department:edit"],
        }
        return reverse_map.get(legacy_perm, [])

    @staticmethod
    def assign_role(db: Session, user_id: int, role_id: int) -> bool:
        """为用户分配角色"""
        existing = db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        ).first()
        if existing:
            return True

        ur = UserRole(user_id=user_id, role_id=role_id)
        db.add(ur)
        db.commit()
        return True

    @staticmethod
    def revoke_role(db: Session, user_id: int, role_id: int) -> bool:
        """撤销用户角色"""
        ur = db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        ).first()
        if ur:
            db.delete(ur)
            db.commit()
            return True
        return False

    @staticmethod
    def get_user_roles(db: Session, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的所有角色"""
        user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
        result = []
        for ur in user_roles:
            role = db.query(Role).filter(Role.id == ur.role_id).first()
            if role:
                result.append({
                    "id": role.id,
                    "name": role.name,
                    "description": role.description,
                    "is_system": role.is_system,
                })
        return result
