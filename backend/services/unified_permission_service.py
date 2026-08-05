from sqlalchemy.orm import Session
from models.user import User
from models.project import Project
from services.data_scope_service import DataScopeService
from services.permission_service import PermissionService
from services.project_member_service import ProjectMemberService


class ResourceContext:
    """资源上下文 - 用于权限校验"""

    def __init__(self, resource_type: str, resource_id: int, project_id: int = None):
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.project_id = project_id


class UnifiedPermissionService:
    """
    统一权限校验服务
    三层权限职责划分（系统角色与项目角色完全独立）：
    第一层：DataScope（数据权限） - 判断用户是否可以访问该项目
    第二层：RBAC（功能权限） - 判断用户是否拥有该功能操作权限（由系统角色决定）
    第三层：ProjectMember Role（项目角色） - 判断用户在项目中的职责边界
           （Owner / Manager / Developer / Operator / Viewer）

    设计原则：
    - 系统角色（User.role / UserRole）→ 决定菜单、功能权限、数据可见范围
    - 项目角色（ProjectMember.role）→ 决定在单个项目内的操作权限
    - 两者独立，不互相替代
    - 项目共享（ProjectPermission）→ READ/EDIT/MANAGE，控制外部访问级别
    """

    @staticmethod
    def has_permission(
        db: Session,
        user_id: int,
        resource_context: ResourceContext,
        action: str,
    ) -> bool:
        """
        统一权限校验入口
        三层权限全部通过才允许执行操作，任何一层失败立即返回无权限
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return False

        # 超级管理员直接放行
        if user.role == "ADMIN":
            return True

        # 第一层：DataScope - 项目访问权限
        if resource_context.project_id:
            if not DataScopeService.can_access_project(db, user, resource_context.project_id):
                return False

        # 第二层：RBAC - 功能权限（由系统角色决定）
        permission_code = f"{resource_context.resource_type}:{action}"
        if not PermissionService.user_has_permission(db, user_id, permission_code):
            return False

        # 第三层：ProjectMember - 项目角色（决定在项目内的职责边界）
        if resource_context.project_id:
            if not ProjectMemberService.has_permission(
                db, user_id, resource_context.project_id, action
            ):
                return False

        return True

    @staticmethod
    def has_read_permission(
        db: Session,
        user_id: int,
        resource_context: ResourceContext,
    ) -> bool:
        """查看权限：由 DataScope + RBAC 决定（项目角色对查看不限制）"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return False

        if user.role == "ADMIN":
            return True

        if resource_context.project_id:
            if not DataScopeService.can_access_project(db, user, resource_context.project_id):
                return False

        permission_code = f"{resource_context.resource_type}:view"
        return PermissionService.user_has_permission(db, user_id, permission_code)

    @staticmethod
    def has_operation_permission(
        db: Session,
        user_id: int,
        resource_context: ResourceContext,
        action: str,
    ) -> bool:
        """操作权限：必须同时满足 DataScope + RBAC + ProjectMember"""
        return UnifiedPermissionService.has_permission(
            db, user_id, resource_context, action
        )

    @staticmethod
    def apply_data_scope(db: Session, user_id: int, query, resource_type: str = None):
        """
        数据范围过滤 - 在查询构造器上动态添加WHERE条件
        禁止先查全部再内存过滤
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.role == "ADMIN":
            return query

        if hasattr(query, "model_class") and query.model_class == Project:
            return DataScopeService.filter_projects_query(db, user)

        return query
