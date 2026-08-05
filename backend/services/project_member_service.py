from typing import Optional, List
from sqlalchemy.orm import Session
from models.project_member import ProjectMember
from models.project import Project
from models.user import User
from models.department import Department
from models.user_role import UserRole
from models.role import Role


class ProjectMemberService:
    """
    第三层：项目成员角色服务
    负责：Owner、Manager、Developer、Operator、Viewer 角色权限判断
    判断用户在当前项目中的操作范围
    """

    ROLE_PERMISSIONS = {
        "Owner": {
            "manage_project": True,
            "manage_members": True,
            "manage_resource_groups": True,
            "manage_sharing": True,
            "edit_project": True,
            "delete_project": True,
            "edit_service": True,
            "deploy_service": True,
            "view_log": True,
            "start_stop_service": True,
            "restart_service": True,
            "docker_manage": True,
            "webshell": True,
            "config_edit": True,
            "script_run": True,
            "file_upload": True,
            "file_delete": True,
            "log_download": True,
        },
        "Manager": {
            "manage_project": True,
            "manage_members": False,
            "manage_resource_groups": True,
            "manage_sharing": False,
            "edit_project": True,
            "delete_project": False,
            "edit_service": True,
            "deploy_service": True,
            "view_log": True,
            "start_stop_service": True,
            "restart_service": True,
            "docker_manage": True,
            "webshell": True,
            "config_edit": True,
            "script_run": True,
            "file_upload": True,
            "file_delete": True,
            "log_download": True,
        },
        "Developer": {
            "manage_project": False,
            "manage_members": False,
            "manage_resource_groups": False,
            "manage_sharing": False,
            "edit_project": False,
            "delete_project": False,
            "edit_service": True,
            "deploy_service": True,
            "view_log": True,
            "start_stop_service": False,
            "restart_service": False,
            "docker_manage": False,
            "webshell": True,
            "config_edit": True,
            "script_run": True,
            "file_upload": True,
            "file_delete": False,
            "log_download": True,
        },
        "Operator": {
            "manage_project": False,
            "manage_members": False,
            "manage_resource_groups": False,
            "manage_sharing": False,
            "edit_project": False,
            "delete_project": False,
            "edit_service": False,
            "deploy_service": False,
            "view_log": True,
            "start_stop_service": True,
            "restart_service": True,
            "docker_manage": True,
            "webshell": True,
            "config_edit": False,
            "script_run": False,
            "file_upload": False,
            "file_delete": False,
            "log_download": False,
        },
        "Viewer": {
            "manage_project": False,
            "manage_members": False,
            "manage_resource_groups": False,
            "manage_sharing": False,
            "edit_project": False,
            "delete_project": False,
            "edit_service": False,
            "deploy_service": False,
            "view_log": True,
            "start_stop_service": False,
            "restart_service": False,
            "docker_manage": False,
            "webshell": False,
            "config_edit": False,
            "script_run": False,
            "file_upload": False,
            "file_delete": False,
            "log_download": False,
        },
    }

    HIGHBIT_OPERATIONS = [
        "delete_project", "share_project",
        "start_stop_service", "restart_service",
        "docker_exec", "docker_remove",
        "image_delete", "config_edit",
        "file_upload", "file_delete",
        "log_download", "webshell_login",
        "script_run", "host_reboot",
    ]

    @staticmethod
    def get_user_role_in_project(db: Session, user_id: int, project_id: int) -> Optional[str]:
        """获取用户在指定项目中的角色"""
        member = db.query(ProjectMember).filter(
            ProjectMember.user_id == user_id,
            ProjectMember.project_id == project_id,
        ).first()
        if member:
            return member.role
        return None

    @staticmethod
    def has_permission(db: Session, user_id: int, project_id: int, action: str) -> bool:
        """判断用户在项目中是否有指定操作权限"""
        role = ProjectMemberService.get_user_role_in_project(db, user_id, project_id)
        if not role:
            return False
        permissions = ProjectMemberService.ROLE_PERMISSIONS.get(role, {})
        return permissions.get(action, False)

    @staticmethod
    def is_high_risk_operation(action: str) -> bool:
        """判断是否为高危操作"""
        return action in ProjectMemberService.HIGHBIT_OPERATIONS

    @staticmethod
    def add_member(db: Session, project_id: int, user_id: int, role: str) -> ProjectMember:
        """添加项目成员"""
        existing = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        ).first()
        if existing:
            existing.role = role
            db.commit()
            return existing

        member = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role=role,
        )
        db.add(member)
        db.commit()
        return member

    @staticmethod
    def remove_member(db: Session, project_id: int, user_id: int) -> bool:
        """移除项目成员"""
        member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        ).first()
        if member:
            if member.role == "Owner":
                return False
            db.delete(member)
            db.commit()
            return True
        return False

    @staticmethod
    def change_role(db: Session, project_id: int, user_id: int, new_role: str) -> bool:
        """修改成员角色"""
        member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        ).first()
        if not member:
            return False
        if member.role == "Owner" and new_role != "Owner":
            return False
        member.role = new_role
        db.commit()
        return True

    @staticmethod
    def get_project_members(db: Session, project_id: int) -> List[ProjectMember]:
        """获取项目所有成员"""
        return db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id
        ).all()

    @staticmethod
    def get_user_projects(db: Session, user_id: int) -> List[ProjectMember]:
        """获取用户参与的所有项目"""
        return db.query(ProjectMember).filter(
            ProjectMember.user_id == user_id
        ).all()

    @staticmethod
    def batch_add_by_department(db: Session, project_id: int, department_id: int, role: str) -> dict:
        """按部门批量添加项目成员（包含子部门）"""
        dept = db.query(Department).filter(Department.id == department_id).first()
        if not dept:
            raise ValueError(f"部门不存在: {department_id}")

        all_dept_ids = ProjectMemberService._get_all_dept_ids(db, department_id)
        users = db.query(User).filter(
            User.department_id.in_(all_dept_ids),
            User.status == 1,
        ).all()

        added = 0
        skipped = 0
        for user in users:
            existing = db.query(ProjectMember).filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            ).first()
            if existing:
                skipped += 1
                continue
            member = ProjectMember(
                project_id=project_id,
                user_id=user.id,
                role=role,
            )
            db.add(member)
            added += 1

        db.commit()
        return {"added": added, "skipped": skipped, "total": len(users)}

    @staticmethod
    def batch_add_by_system_role(db: Session, project_id: int, role_id: int, project_role: str) -> dict:
        """按系统角色批量添加项目成员"""
        sys_role = db.query(Role).filter(Role.id == role_id).first()
        if not sys_role:
            raise ValueError(f"系统角色不存在: {role_id}")

        user_ids = db.query(UserRole.user_id).filter(UserRole.role_id == role_id).subquery()
        users = db.query(User).filter(
            User.id.in_(user_ids),
            User.status == 1,
        ).all()

        added = 0
        skipped = 0
        for user in users:
            existing = db.query(ProjectMember).filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            ).first()
            if existing:
                skipped += 1
                continue
            member = ProjectMember(
                project_id=project_id,
                user_id=user.id,
                role=project_role,
            )
            db.add(member)
            added += 1

        db.commit()
        return {"added": added, "skipped": skipped, "total": len(users)}

    @staticmethod
    def _get_all_dept_ids(db: Session, root_dept_id: int) -> List[int]:
        """递归获取所有子部门ID"""
        ids = [root_dept_id]
        children = db.query(Department.id).filter(Department.parent_id == root_dept_id).all()
        for child in children:
            ids.extend(ProjectMemberService._get_all_dept_ids(db, child.id))
        return ids
