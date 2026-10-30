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

    # 项目所有者（Owner）/ 管理员（Manager）：具备项目级管理权限（manage_project=True），
    # 不允许通过「批量添加」再次加入，避免权限越级或重复授权。
    PROTECTED_PROJECT_ROLES = {"Owner", "Manager"}

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
    def ensure_owner_member(db: Session, project_id: int, owner_id: Optional[int]) -> bool:
        """确保项目负责人（projects.owner_id）在 project_members 中存在 Owner 记录（幂等）。

        负责人应与项目成员中的 Owner 保持一致；若记录缺失或角色不是 Owner，
        项目级 manage_project 校验会失败（成员管理接口返回 403）。
        返回是否发生了变更。
        """
        if not owner_id:
            return False
        member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == owner_id,
        ).first()
        if member:
            if member.role != "Owner":
                member.role = "Owner"
                db.commit()
                return True
            return False
        db.add(ProjectMember(project_id=project_id, user_id=owner_id, role="Owner"))
        db.commit()
        return True

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
    def get_department_users(db: Session, project_id: int, department_id: int) -> List[dict]:
        """获取某部门下的在职用户列表（供批量勾选）。

        - 排除项目所有者（Owner）/ 管理员（Manager）：不允许被再次加入；
        - 其余已加入成员保留并标注 is_member（前端标记「已加入」且不可勾选，避免重复添加）。
        """
        users = db.query(User).filter(
            User.department_id == department_id,
            User.status == 1,
        ).all()
        role_by_user = {
            row[0]: row[1] for row in db.query(ProjectMember.user_id, ProjectMember.role).filter(
                ProjectMember.project_id == project_id
            ).all()
        }
        result = []
        for u in users:
            role = role_by_user.get(u.id)
            if role in ProjectMemberService.PROTECTED_PROJECT_ROLES:
                continue
            result.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "department_id": u.department_id,
                "project_role": role,
                "is_member": role is not None,
            })
        return result

    @staticmethod
    def batch_add_by_users(db: Session, project_id: int, user_ids: List[int], role: str) -> dict:
        """按指定用户ID批量添加项目成员。

        - 所有者（Owner）/ 管理员（Manager）不得被添加，否则拒绝（防止绕过前端直接提交）；
        - 已存在的成员跳过（不改其角色），不允许重复添加。
        """
        user_ids = list(dict.fromkeys(user_ids))
        users = db.query(User).filter(
            User.id.in_(user_ids),
            User.status == 1,
        ).all()
        found_ids = {u.id for u in users}
        missing = [uid for uid in user_ids if uid not in found_ids]
        if missing:
            raise ValueError(f"用户不存在或已停用: {missing}")

        role_by_user = {
            row[0]: row[1] for row in db.query(ProjectMember.user_id, ProjectMember.role).filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id.in_(user_ids),
            ).all()
        }
        protected = [
            uid for uid in user_ids
            if role_by_user.get(uid) in ProjectMemberService.PROTECTED_PROJECT_ROLES
        ]
        if protected:
            raise ValueError(f"以下用户是项目所有者/管理员，不允许添加为成员: {protected}")

        existing_ids = set(role_by_user.keys())
        added = 0
        for u in users:
            if u.id in existing_ids:
                continue
            db.add(ProjectMember(project_id=project_id, user_id=u.id, role=role))
            added += 1
        db.commit()
        return {"added": added, "skipped": len(user_ids) - added, "total": len(user_ids)}

    @staticmethod
    def _get_all_dept_ids(db: Session, root_dept_id: int) -> List[int]:
        """递归获取所有子部门ID"""
        ids = [root_dept_id]
        children = db.query(Department.id).filter(Department.parent_id == root_dept_id).all()
        for child in children:
            ids.extend(ProjectMemberService._get_all_dept_ids(db, child.id))
        return ids
