from typing import List, Dict, Any
from sqlalchemy.orm import Session
from models.role import Role
from models.permission import Permission
from models.role_permission import RolePermission
from models.user_role import UserRole
from models.user import User


SYSTEM_PERMISSIONS = {
    # 项目管理
    "project:view", "project:add", "project:edit", "project:delete", "project:share",
    # 服务管理
    "service:view", "service:start", "service:stop", "service:restart", "service:deploy", "service:edit-config",
    # 容器管理（不包含 create/delete）
    "container:view", "container:exec", "container:start", "container:stop", "container:restart",
    # WebShell
    "webshell:login", "webshell:root-login",
    # 主机管理（基础查看/重启；host:manage 为服务器（主机）增删改的独立权限码）
    "host:view", "host:reboot", "host:manage",
    # 数据备份（查看配置/记录；管理=配置/执行/下载/恢复/删除）
    "backup:view", "backup:manage",
    # 系统设置（查看）
    "settings:view",
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


# 系统角色（User.role 枚举）→ 数据库系统角色名称的映射（方案 C 运行时权限来源）
ROLE_NAME_BY_USER_ROLE = {
    "SUPER_ADMIN": "超级管理员",
    "ORG_ADMIN": "组织管理员",
    "DEPT_ADMIN": "部门管理员",
    "DEPT_MEMBER": "部门成员",
    "READONLY": "只读用户",
}


class PermissionService:
    """
    第二层：RBAC功能权限服务
    负责：菜单权限、API权限、按钮权限、功能操作权限

    授权规则（方案 C，统一来源）：
    - SUPER_ADMIN 始终拥有全部系统权限，不依赖数据库角色关联；
    - 其余系统角色按 User.role 映射到数据库系统角色（ROLE_NAME_BY_USER_ROLE）；
    - 自定义角色（is_system=False）只能与系统角色权限取交集，不得扩大系统角色权限。
    """

    @staticmethod
    def _role_permission_codes(db: Session, role_id: int) -> set:
        """取某数据库角色拥有的新版权限码集合"""
        rows = (
            db.query(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(RolePermission.role_id == role_id)
            .all()
        )
        return {f"{p.resource}:{p.action}" for p in rows}

    @staticmethod
    def get_user_permissions(db: Session, user_id: int) -> List[str]:
        """获取用户的所有功能权限（方案 C 统一来源）"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        # 超级管理员：直接返回全部系统权限，不依赖数据库角色关联
        if user.role == "SUPER_ADMIN":
            return list(SYSTEM_PERMISSIONS)

        role_name = ROLE_NAME_BY_USER_ROLE.get(user.role)
        if not role_name:
            return []
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            return []

        system_perms = PermissionService._role_permission_codes(db, role.id)

        # 自定义角色：仅与系统角色权限取交集（只能收窄，不能扩权）
        custom_role_ids = [
            row[0]
            for row in db.query(Role.id)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user_id, Role.is_system.is_(False))
            .all()
        ]
        if not custom_role_ids:
            return sorted(system_perms)

        custom_perms = set()
        for rid in custom_role_ids:
            custom_perms |= PermissionService._role_permission_codes(db, rid)
        return sorted(system_perms & custom_perms)

    @staticmethod
    def user_has_permission(db: Session, user_id: int, permission_code: str) -> bool:
        """判断用户是否拥有指定功能权限（与 get_user_permissions 同源）"""
        if not permission_code:
            return False
        if ":" in permission_code:
            required = [permission_code]
        else:
            # 兼容旧版权限码调用：转换为新码后判断
            from api.dependencies import LEGACY_TO_NEW_PERMISSIONS
            required = LEGACY_TO_NEW_PERMISSIONS.get(permission_code, [])
        if not required:
            return False
        perms = set(PermissionService.get_user_permissions(db, user_id))
        return any(code in perms for code in required)

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