from typing import Optional, List, Dict, Any
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
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

        # 组织级管理员（含超管）在本组织范围内拥有全量项目可见性；
        # 普通部门用户不再因「组织相同」获得其他部门项目的访问权。
        if DataScopeService._is_org_wide(user):
            if user.organization_id and user.organization_id == project.organization_id:
                return True

        visibility = project.visibility or VisibilityType.DEPARTMENT

        if visibility == VisibilityType.PUBLIC:
            if user.organization_id and user.organization_id == project.organization_id:
                return True
            return DataScopeService._check_project_member(db, user.id, project_id)

        if visibility == VisibilityType.DEPARTMENT:
            if user.department_id is not None and user.department_id == project.department_id:
                return True
            if DataScopeService._check_project_member(db, user.id, project_id):
                return True
            return DataScopeService._check_project_shared_with_user(db, project_id, user)

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

        # 仅组织级管理员（超管/组织管理员）按组织范围放行；
        # 部门管理员/部门成员/只读角色不再因组织相同而看到其他部门项目。
        if org_id and DataScopeService._is_org_wide(user):
            conditions.append(Project.organization_id == org_id)

        if dept_id:
            conditions.append(Project.department_id == dept_id)

        conditions.append(Project.visibility == VisibilityType.PUBLIC)

        member_project_ids = db.query(ProjectMember.project_id).filter(
            ProjectMember.user_id == user_id
        ).subquery()
        conditions.append(Project.id.in_(member_project_ids))

        share_conditions = [
            and_(
                ProjectPermission.target_type == "User",
                ProjectPermission.target_id == user_id,
            ),
        ]
        if dept_id:
            share_conditions.append(
                and_(
                    ProjectPermission.target_type == "Department",
                    ProjectPermission.target_id == dept_id,
                )
            )
        if org_id:
            share_conditions.append(
                and_(
                    ProjectPermission.target_type == "Organization",
                    ProjectPermission.target_id == org_id,
                )
            )
        shared_subquery = db.query(ProjectPermission.project_id).filter(
            or_(*share_conditions)
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
        share_conditions = [
            and_(
                ProjectPermission.target_type == "User",
                ProjectPermission.target_id == user.id,
            ),
        ]
        if user.department_id:
            share_conditions.append(
                and_(
                    ProjectPermission.target_type == "Department",
                    ProjectPermission.target_id == user.department_id,
                )
            )
        if user.organization_id:
            share_conditions.append(
                and_(
                    ProjectPermission.target_type == "Organization",
                    ProjectPermission.target_id == user.organization_id,
                )
            )
        shared = db.query(ProjectPermission).filter(
            ProjectPermission.project_id == project_id,
            or_(*share_conditions),
        ).first()
        return shared is not None

    @staticmethod
    def _is_super_admin(user: User) -> bool:
        return user.role in ("ADMIN", "SUPER_ADMIN")

    @staticmethod
    def _is_org_wide(user: User) -> bool:
        """组织级范围用户：可在本组织范围内访问全部项目（超管另由 _is_super_admin 全局放行）"""
        return user.role in ("ADMIN", "SUPER_ADMIN", "ORG_ADMIN")

    @staticmethod
    def get_applicable_shares(db: Session, user: User, project_id: int) -> List[ProjectPermission]:
        """返回当前用户在指定项目上所有生效的共享授权记录（User / 本部门 / 本组织）"""
        share_conditions = [
            and_(
                ProjectPermission.target_type == "User",
                ProjectPermission.target_id == user.id,
            ),
        ]
        if user.department_id:
            share_conditions.append(
                and_(
                    ProjectPermission.target_type == "Department",
                    ProjectPermission.target_id == user.department_id,
                )
            )
        if user.organization_id:
            share_conditions.append(
                and_(
                    ProjectPermission.target_type == "Organization",
                    ProjectPermission.target_id == user.organization_id,
                )
            )
        return db.query(ProjectPermission).filter(
            ProjectPermission.project_id == project_id,
            or_(*share_conditions),
        ).all()

    @staticmethod
    def has_intrinsic_project_authority(db: Session, user: User, project: Project) -> bool:
        """判断用户对项目是否拥有"固有操作权"（区别于仅通过 PUBLIC 可见性或项目共享获得的访问）。

        固有操作权来源：超管 / 组织级管理员（本组织）/ 本部门用户 / 项目成员。
        仅通过信息公开可见（PUBLIC）或仅通过项目共享获得访问的用户，不构成固有操作权——
        公开可见只提供"查看"，不能自动获得写操作或高风险能力；共享访问者的写/高风险能力
        需由共享记录中的独立授权决定。
        """
        if DataScopeService._is_super_admin(user):
            return True
        if DataScopeService._is_org_wide(user) and user.organization_id and user.organization_id == project.organization_id:
            return True
        if user.department_id is not None and user.department_id == project.department_id:
            return True
        if DataScopeService._check_project_member(db, user.id, project.id):
            return True
        return False

    @staticmethod
    def has_high_risk_grant(db: Session, user: User, project: Project, capability: str) -> bool:
        """判断用户在项目上是否拥有某项高风险能力的独立授权。

        - 拥有固有操作权的用户：不额外限制（由现有系统权限码控制），返回 True；
        - 仅通过 PUBLIC 可见或共享获得访问的用户：必须在其生效的共享记录中被明确勾选对应能力，
          否则视为无授权（无共享记录时返回 False，即拒绝）。
        """
        if DataScopeService.has_intrinsic_project_authority(db, user, project):
            return True
        from models.project_permission import HIGH_RISK_FLAG_BY_CAPABILITY

        flag = HIGH_RISK_FLAG_BY_CAPABILITY.get(capability)
        if not flag:
            return False
        shares = DataScopeService.get_applicable_shares(db, user, project.id)
        return any(bool(getattr(s, flag, False)) for s in shares)

    @staticmethod
    def get_user_project_ids(db: Session, user: User) -> List[int]:
        """获取用户可访问的所有项目ID列表"""
        query = DataScopeService.filter_projects_query(db, user)
        return [p.id for p in query.all()]

    # ---------------- 用户管理数据范围（查看/操作） ----------------
    # 规则：超级管理员=全系统；组织级管理员=本组织；其余角色=本部门；
    #       无组织/部门归属时收敛为仅本人，避免越权。

    @staticmethod
    def filter_users_query(db: Session, user: User, query=None):
        """按用户数据范围过滤用户查询（列表/搜索/统计统一入口）。"""
        query = db.query(User) if query is None else query
        if DataScopeService._is_super_admin(user):
            return query
        if DataScopeService._is_org_wide(user):
            if user.organization_id is None:
                return query.filter(User.id == user.id)
            return query.filter(User.organization_id == user.organization_id)
        if user.department_id is None:
            return query.filter(User.id == user.id)
        return query.filter(User.department_id == user.department_id)

    @staticmethod
    def can_access_user(user: User, target: User) -> bool:
        """判断目标用户是否落在操作者的用户数据范围内。"""
        if DataScopeService._is_super_admin(user):
            return True
        if DataScopeService._is_org_wide(user):
            return user.organization_id is not None and target.organization_id == user.organization_id
        return user.department_id is not None and target.department_id == user.department_id

    @staticmethod
    def validate_user_scope_assignment(db: Session, user: User, organization_id, department_id) -> bool:
        """校验新增/编辑用户时指定的组织、部门是否在操作者数据范围内。

        - 超级管理员：任意组织/部门；
        - 组织级管理员：仅限本组织，且部门必须属于该组织；
        - 其余角色（部门管理员等）：仅限本人所在组织与部门，禁止转移归属。
        """
        if DataScopeService._is_super_admin(user):
            return True
        if DataScopeService._is_org_wide(user):
            if organization_id != user.organization_id:
                return False
        else:
            if organization_id != user.organization_id or department_id != user.department_id:
                return False
        if department_id is not None:
            dept = db.query(Department).filter(Department.id == department_id).first()
            if not dept or dept.organization_id != organization_id:
                return False
        return True
