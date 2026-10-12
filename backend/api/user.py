from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from models.user import User
from models.user_role import UserRole
from models.role import Role
from models.service import Service
from schemas.user import UserCreate, UserUpdate, UserResponse
from schemas.common import ResponseModel
from services.auth_service import get_password_hash, verify_password
from services.audit_service import log_audit
from core.database import get_db
from core.capabilities import ROLE_PERMISSIONS, SERVICE_TYPE_CAPABILITIES, ServiceType
from api.dependencies import get_current_user, require_permission
from services.data_scope_service import DataScopeService

router = APIRouter()

def _get_user_roles(db: Session, user_id: int) -> list:
    user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
    result = []
    for ur in user_roles:
        role = db.query(Role).filter(Role.id == ur.role_id).first()
        if role:
            result.append({
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_system": role.is_system
            })
    return result

def _user_to_dict(db: Session, u: User) -> dict:
    # Get organization name
    org_name = None
    if u.organization_id:
        from models.organization import Organization
        org = db.query(Organization).filter(Organization.id == u.organization_id).first()
        if org:
            org_name = org.name
    
    # Get department name
    dept_name = None
    if u.department_id:
        from models.department import Department
        dept = db.query(Department).filter(Department.id == u.department_id).first()
        if dept:
            dept_name = dept.name
    
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "roles": _get_user_roles(db, u.id),
        "email": u.email,
        "phone": u.phone,
        "is_active": u.is_active,
        "organization_id": u.organization_id,
        "organization_name": org_name,
        "department_id": u.department_id,
        "department_name": dept_name,
        "job_title": u.job_title,
        "status": u.status,
        "created_at": str(u.created_at) if u.created_at else None,
        "updated_at": str(u.updated_at) if u.updated_at else None,
    }

@router.get("/users", response_model=ResponseModel)
async def get_users(
    organization_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("user:view"))
):
    # 查看权限：user:view 通过后，数据范围收敛（超管=全部；组织管理员=本组织；其余=本部门）
    query = DataScopeService.filter_users_query(db, user)
    if organization_id is not None:
        # 显式指定组织时也不得越出数据范围，防止篡改 organization_id 越权查询
        if not DataScopeService._is_super_admin(user) and organization_id != user.organization_id:
            raise HTTPException(status_code=403, detail="无权查看其他组织的用户")
        query = query.filter(User.organization_id == organization_id)
    users = query.all()
    result = [_user_to_dict(db, u) for u in users]
    return ResponseModel(data=result)

@router.get("/users/{user_id}", response_model=ResponseModel)
async def get_user(user_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("user:view"))):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    # 查看权限：非超管仅可查看数据范围内的用户，防止篡改 user_id 越权访问
    if not DataScopeService.can_access_user(user, u):
        raise HTTPException(status_code=403, detail="无权查看该用户")
    return ResponseModel(data=_user_to_dict(db, u))

@router.post("/users", response_model=ResponseModel)
async def create_user(user_create: UserCreate, db: Session = Depends(get_db), user = Depends(require_permission("user:add"))):
    existing = db.query(User).filter(User.username == user_create.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    # 数据范围：新增用户时指定的组织/部门必须在操作者范围内
    if not DataScopeService.validate_user_scope_assignment(
        db, user, user_create.organization_id, user_create.department_id
    ):
        raise HTTPException(status_code=403, detail="无权在该组织/部门下创建用户")

    new_user = User(
        username=user_create.username,
        password=get_password_hash(user_create.password),
        role=user_create.role or "DEPT_MEMBER",
        email=user_create.email,
        phone=user_create.phone,
        organization_id=user_create.organization_id,
        department_id=user_create.department_id,
        job_title=user_create.job_title,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if user_create.role_ids:
        for role_id in user_create.role_ids:
            db_user_role = UserRole(user_id=new_user.id, role_id=role_id)
            db.add(db_user_role)
        db.commit()

    log_audit(db, user.id, user.username, "CREATE", result="success", output=f"Created user: {user_create.username}")

    return ResponseModel(data=_user_to_dict(db, new_user))

@router.put("/users/{user_id}", response_model=ResponseModel)
async def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db), user = Depends(require_permission("user:edit"))):
    user_to_update = db.query(User).filter(User.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found")

    # 数据范围：目标用户必须在操作者范围内，防止篡改 user_id 越权操作
    if not DataScopeService.can_access_user(user, user_to_update):
        raise HTTPException(status_code=403, detail="无权操作该用户")

    # 数据范围：调整组织/部门时不得越界或转移归属
    if user_update.organization_id is not None or user_update.department_id is not None:
        target_org_id = user_update.organization_id if user_update.organization_id is not None else user_to_update.organization_id
        target_dept_id = user_update.department_id if user_update.department_id is not None else user_to_update.department_id
        if not DataScopeService.validate_user_scope_assignment(db, user, target_org_id, target_dept_id):
            raise HTTPException(status_code=403, detail="无权将用户调整到该组织/部门")

    if user_update.password:
        user_to_update.password = get_password_hash(user_update.password)
    if user_update.role:
        user_to_update.role = user_update.role
    if user_update.email:
        user_to_update.email = user_update.email
    if user_update.phone:
        user_to_update.phone = user_update.phone
    if user_update.is_active is not None:
        user_to_update.is_active = user_update.is_active
    if user_update.organization_id is not None:
        user_to_update.organization_id = user_update.organization_id
    if user_update.department_id is not None:
        user_to_update.department_id = user_update.department_id
    if user_update.job_title is not None:
        user_to_update.job_title = user_update.job_title

    if user_update.role_ids is not None:
        existing_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
        existing_role_ids = {er.role_id for er in existing_roles}
        new_role_ids = set(user_update.role_ids)

        for er in existing_roles:
            if er.role_id not in new_role_ids:
                db.delete(er)

        for rid in new_role_ids:
            if rid not in existing_role_ids:
                db.add(UserRole(user_id=user_id, role_id=rid))

    db.commit()
    db.refresh(user_to_update)

    log_audit(db, user.id, user.username, "UPDATE", result="success", output=f"Updated user: {user_to_update.username}")

    return ResponseModel(data=_user_to_dict(db, user_to_update))

@router.delete("/users/{user_id}", response_model=ResponseModel)
async def delete_user(user_id: int, db: Session = Depends(get_db), user = Depends(require_permission("user:delete"))):
    user_to_delete = db.query(User).filter(User.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")

    # 数据范围：目标用户必须在操作者范围内，防止篡改 user_id 越权删除
    if not DataScopeService.can_access_user(user, user_to_delete):
        raise HTTPException(status_code=403, detail="无权删除该用户")

    if user_to_delete.role == "SUPER_ADMIN" and db.query(User).filter(User.role == "SUPER_ADMIN").count() <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only ADMIN user")

    db.delete(user_to_delete)
    db.commit()

    log_audit(db, user.id, user.username, "DELETE", result="success", output=f"Deleted user: {user_to_delete.username}")

    return ResponseModel(message="User deleted successfully")

@router.get("/user/menu", response_model=ResponseModel)
async def get_user_menu(db: Session = Depends(get_db), user = Depends(get_current_user)):
    from services.permission_service import PermissionService
    
    user_perms = PermissionService.get_user_permissions(db, user.id)
    perm_set = set(user_perms)
    
    def has_perm(resource: str, action: str = "view") -> bool:
        return f"{resource}:{action}" in perm_set
    
    menu = []
    
    # 运行总览 - 所有登录用户可见
    menu.append({"id": "overview", "name": "运行总览", "icon": "data-analysis", "path": "/overview", "children": []})
    
    # 项目资源管理
    project_children = []
    if has_perm("project") or has_perm("service", "view"):
        if has_perm("project", "view"):
            project_children.append({"id": "projects", "name": "项目列表", "icon": "folder", "path": "/projects"})
        if has_perm("service", "view"):
            project_children.append({"id": "services", "name": "服务管理", "icon": "server", "path": "/services"})
        project_children.append({"id": "subsystems", "name": "子系统管理", "icon": "folder", "path": "/subsystems"})
        project_children.append({"id": "service-groups", "name": "程序分类管理", "icon": "folder", "path": "/service-groups"})
        menu.append({
            "id": "project-services",
            "name": "项目资源管理",
            "icon": "folder-opened",
            "path": "",
            "children": project_children
        })
    
    # 服务器管理
    if has_perm("host", "view"):
        menu.append({"id": "servers", "name": "服务器管理", "icon": "computer", "path": "/servers", "children": []})
    
    # Agent管理
    if has_perm("agent", "view"):
        menu.append({"id": "agents", "name": "Agent管理", "icon": "cpu", "path": "/agents", "children": []})
    
    # 数据库管理（基于服务类型动态显示）
    service_types = db.query(Service.service_type).distinct().all()
    service_types = [st[0] for st in service_types]
    has_database_service = any(st in ['MYSQL', 'KINGBASE', 'DAMENG'] for st in service_types)
    has_es_service = any(st == 'ELASTICSEARCH' for st in service_types)
    
    if has_perm("service", "view") and has_database_service:
        menu.append({"id": "sql", "name": "数据库管理", "icon": "database", "path": "/sql", "children": []})
    
    if has_perm("service", "view") and has_es_service:
        menu.append({"id": "es", "name": "Elasticsearch管理", "icon": "search", "path": "/es", "children": []})
    
    # 权限管理（组织+角色+用户）：按查看权限码显示，仅显示有权限的项
    perm_children = []
    if has_perm("organization", "view"):
        perm_children.append({"id": "organization", "name": "组织管理", "icon": "office-building", "path": "/organization"})
    if has_perm("role", "view"):
        perm_children.append({"id": "roles", "name": "角色管理", "icon": "user", "path": "/roles"})
    if has_perm("user", "view"):
        perm_children.append({"id": "users", "name": "用户管理", "icon": "users", "path": "/users"})
    if perm_children:
        menu.append({
            "id": "permission",
            "name": "权限管理",
            "icon": "lock",
            "path": "",
            "children": perm_children
        })
    
    # 审计日志：需 audit:view
    if has_perm("audit", "view"):
        menu.append({"id": "audit", "name": "审计日志", "icon": "file-search", "path": "/audit", "children": []})

    # 数据备份：需 backup:view（写操作另受 backup:manage 保护）
    if has_perm("backup", "view"):
        menu.append({"id": "backup", "name": "数据备份", "icon": "box", "path": "/backup", "children": []})
    
    # 系统设置：需 settings:view
    if has_perm("settings", "view"):
        menu.append({"id": "settings", "name": "系统设置", "icon": "settings", "path": "/settings", "children": []})
    
    return ResponseModel(data=menu)


@router.get("/user/info", response_model=ResponseModel)
async def get_current_user_info(user = Depends(get_current_user), db: Session = Depends(get_db)):
    org_name = None
    dept_name = None
    if user.organization_id:
        from models.organization import Organization
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()
        if org:
            org_name = org.name
    if user.department_id:
        from models.department import Department
        dept = db.query(Department).filter(Department.id == user.department_id).first()
        if dept:
            dept_name = dept.name
    return ResponseModel(data={
        "username": user.username,
        "role": user.role,
        "roles": _get_user_roles(db, user.id),
        "email": user.email,
        "phone": user.phone,
        "organization_id": user.organization_id,
        "organization_name": org_name,
        "department_id": user.department_id,
        "department_name": dept_name,
        "job_title": user.job_title,
    })


@router.get("/user/permissions", response_model=ResponseModel)
async def get_user_permissions(user = Depends(get_current_user), db: Session = Depends(get_db)):
    from services.permission_service import PermissionService
    permissions = PermissionService.get_user_permissions(db, user.id)
    return ResponseModel(data=permissions)
