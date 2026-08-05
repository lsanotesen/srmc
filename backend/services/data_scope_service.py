from typing import Optional, List, Dict, Any
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import or_
from models.project import Project
from models.project_member import ProjectMember
from models.project_permission import ProjectPermission
from models.department import Department
from models.organization import Organization
from models.user import User


class VisibilityType(str, Enum):
    DEPARTMENT = "DEPARTMENT"
    AUTHORIZED = "AUTHORIZED"
    PUBLIC = "PUBLIC"


class ProjectRole(str, Enum):
    OWNER = "Owner"
    MANAGER = "Manager"
    DEVELOPER = "Developer"
    OPERATOR = "Operator"
    VIEWER = "Viewer"


class PermissionLevel(str, Enum):
    READ = "READ"
    EDIT = "EDIT"
    MANAGE = "MANAGE"


class DataScopeService:
    """
    第一层：数据权限服务
    负责：项目可见性、部门范围、Organization范围、共享权限判断
    只判断：用户是否可以访问该资源
    """

    @staticmethod
    def can_access_project(db: Session, user: User, project_id: int) -> bool:
        """判断用户是否可以访问指定项目"""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return False

        if DataScopeService._is_super_admin(user):
            return True

        visibility = project.visibility or VisibilityType.DEPARTMENT

        if visibility == VisibilityType.PUBLIC:
            if user.organization_id == project.organization_id:
                return True
            return DataScopeService._check_project_member(db, user.id, project_id)

        if visibility == VisibilityType.DEPARTMENT:
            if user.department_id == project.department_id:
                return True
            if user.organization_id == project.organization_id:
                return True
            return DataScopeService._check_project_member(db, user.id, project_id)

        if visibility == VisibilityType.AUTHORIZED:
            if DataScopeService._check_project_member(db, user.id, project_id):
                return True
            return DataScopeService._check_project_shared_with_user(db, project_id, user)

        return False

    @staticmethod
    def filter_projects_query(db: Session, user: User):
        """根据数据权限过滤项目查询"""
        query = db.query(Project)

        if DataScopeService._is_super_admin(user):
            return query

        org_id = user.organization_id
        dept_id = user.department_id
        user_id = user.id

        conditions = []

        if org_id:
            conditions.append(Project.organization_id == org_id)

        if dept_id:
            conditions.append(Project.department_id == dept_id)

        conditions.append(Project.visibility == VisibilityType.PUBLIC)

        member_project_ids = db.query(ProjectMember.project_id).filter(
            ProjectMember.user_id == user_id
        ).subquery()
        conditions.append(Project.id.in_(member_project_ids))

        shared_subquery = db.query(ProjectPermission.project_id).filter(
            or_(
                ProjectPermission.target_type == "User",
                ProjectPermission.target_id == user_id,
            ),
            (
                ProjectPermission.target_type == "Department",
                ProjectPermission.target_id == dept_id,
            ),
            (
                ProjectPermission.target_type == "Organization",
                ProjectPermission.target_id == org_id,
            ),
        ).subquery()
        conditions.append(Project.id.in_(shared_subquery))

        if conditions:
            query = query.filter(or_(*conditions))

        return query

    @staticmethod
    def _check_project_member(db: Session, user_id: int, project_id: int) -> bool:
        count = db.query(ProjectMember).filter(
            ProjectMember.user_id == user_id,
            ProjectMember.project_id == project_id,
        ).count()
        return count > 0

    @staticmethod
    def _check_project_shared_with_user(db: Session, project_id: int, user: User) -> bool:
        shared = db.query(ProjectPermission).filter(
            ProjectPermission.project_id == project_id,
            or_(
                (ProjectPermission.target_type == "User", ProjectPermission.target_id == user.id),
                (ProjectPermission.target_type == "Department", ProjectPermission.target_id == user.department_id),
                (ProjectPermission.target_type == "Organization", ProjectPermission.target_id == user.organization_id),
            ),
        ).first()
        return shared is not None

    @staticmethod
    def _is_super_admin(user: User) -> bool:
        return user.role == "ADMIN"

    @staticmethod
    def get_user_project_ids(db: Session, user: User) -> List[int]:
        """获取用户可访问的所有项目ID列表"""
        query = DataScopeService.filter_projects_query(db, user)
        return [p.id for p in query.all()]
