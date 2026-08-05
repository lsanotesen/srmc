"""
初始化脚本 - 创建默认组织、部门、角色、权限
"""
import sys
sys.path.insert(0, "/app")

from core.database import SessionLocal
from models.organization import Organization
from models.department import Department
from models.user import User
from models.role import Role
from models.permission import Permission
from models.role_permission import RolePermission
from models.user_role import UserRole
from services.role_permission_service import RolePermissionService


def seed_default_organization():
    """创建默认组织"""
    db = SessionLocal()
    try:
        existing = db.query(Organization).filter(Organization.code == "DEFAULT").first()
        if existing:
            print(f"默认组织已存在: {existing.name}")
            return existing.id

        org = Organization(
            name="默认组织",
            code="DEFAULT",
            description="系统默认组织",
            status=1,
        )
        db.add(org)
        db.commit()
        print(f"创建默认组织: {org.name} (ID: {org.id})")
        return org.id
    except Exception as e:
        print(f"创建组织失败: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def seed_default_department(org_id: int):
    """创建默认部门"""
    db = SessionLocal()
    try:
        existing = db.query(Department).filter(
            Department.organization_id == org_id,
            Department.code == "ROOT",
        ).first()
        if existing:
            print(f"根部门已存在: {existing.name}")
            return existing.id

        dept = Department(
            organization_id=org_id,
            parent_id=None,
            name="根部门",
            code="ROOT",
            description="组织根部门",
            status=1,
            sort_order=0,
        )
        db.add(dept)
        db.commit()
        print(f"创建根部门: {dept.name} (ID: {dept.id})")
        return dept.id
    except Exception as e:
        print(f"创建部门失败: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def seed_user_org_dept(org_id: int, dept_id: int):
    """为现有用户分配组织和部门"""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.organization_id.is_(None)).all()
        for user in users:
            user.organization_id = org_id
            user.department_id = dept_id
            db.commit()
            print(f"为用户 {user.username} 分配组织和部门")
        print(f"共更新 {len(users)} 个用户的组织部门信息")
    except Exception as e:
        print(f"用户分配失败: {e}")
        db.rollback()
    finally:
        db.close()


def seed_admin_role():
    """为ADMIN用户分配超级管理员角色"""
    db = SessionLocal()
    try:
        admin_users = db.query(User).filter(User.role == "ADMIN").all()
        super_admin = db.query(Role).filter(Role.name == "超级管理员").first()
        if not super_admin:
            print("超级管理员角色不存在，跳过用户角色分配")
            return

        for user in admin_users:
            existing = db.query(UserRole).filter(
                UserRole.user_id == user.id,
                UserRole.role_id == super_admin.id,
            ).first()
            if not existing:
                ur = UserRole(user_id=user.id, role_id=super_admin.id)
                db.add(ur)
                db.commit()
                print(f"为ADMIN用户 {user.username} 分配超级管理员角色")
    except Exception as e:
        print(f"角色分配失败: {e}")
        db.rollback()
    finally:
        db.close()


def seed_project_owner():
    """为现有项目设置默认Owner"""
    db = SessionLocal()
    try:
        from models.project import Project
        projects = db.query(Project).filter(Project.owner_id.is_(None)).all()
        admin_user = db.query(User).filter(User.role == "ADMIN").first()
        if not admin_user:
            print("无ADMIN用户，跳过项目Owner设置")
            return

        from models.project_member import ProjectMember
        for project in projects:
            project.owner_id = admin_user.id
            project.creator_id = admin_user.id

            member = db.query(ProjectMember).filter(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == admin_user.id,
            ).first()
            if not member:
                member = ProjectMember(
                    project_id=project.id,
                    user_id=admin_user.id,
                    role="Owner",
                )
                db.add(member)

            if not project.organization_id and admin_user.organization_id:
                project.organization_id = admin_user.organization_id
            if not project.department_id and admin_user.department_id:
                project.department_id = admin_user.department_id

            db.commit()
            print(f"为项目 {project.name} 设置默认Owner")
        print(f"共更新 {len(projects)} 个项目的Owner信息")
    except Exception as e:
        print(f"项目Owner设置失败: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    print("=" * 60)
    print("SRMC 企业级权限体系 - 初始化脚本")
    print("=" * 60)

    print("\n[1/5] 创建默认组织...")
    org_id = seed_default_organization()
    if not org_id:
        print("组织创建失败，退出")
        return

    print("\n[2/5] 创建默认部门...")
    dept_id = seed_default_department(org_id)
    if not dept_id:
        print("部门创建失败，退出")
        return

    print("\n[3/5] 为现有用户分配组织和部门...")
    seed_user_org_dept(org_id, dept_id)

    print("\n[4/5] 初始化角色和权限数据...")
    db = SessionLocal()
    try:
        RolePermissionService.initialize_default_data(db)
        print("角色和权限初始化完成")
    except Exception as e:
        print(f"角色权限初始化失败: {e}")
        db.rollback()
    finally:
        db.close()

    print("\n[5/5] 分配用户角色和项目Owner...")
    seed_admin_role()
    seed_project_owner()

    print("\n" + "=" * 60)
    print("初始化完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
