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
    user = Depends(require_permission("user_manage"))
):
    query = db.query(User)
    if organization_id is not None:
        query = query.filter(User.organization_id == organization_id)
    users = query.all()
    result = [_user_to_dict(db, u) for u in users]
    return ResponseModel(data=result)

@router.get("/users/{user_id}", response_model=ResponseModel)
async def get_user(user_id: int, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return ResponseModel(data=_user_to_dict(db, u))

@router.post("/users", response_model=ResponseModel)
async def create_user(user_create: UserCreate, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    existing = db.query(User).filter(User.username == user_create.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=user_create.username,
        password=get_password_hash(user_create.password),
        role=user_create.role or "READONLY",
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
async def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    user_to_update = db.query(User).filter(User.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found")

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
async def delete_user(user_id: int, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    user_to_delete = db.query(User).filter(User.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")

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
    
    # Dashboard - 所有登录用户可见
    menu.append({"id": "dashboard", "name": "Dashboard", "icon": "dashboard", "path": "/dashboard", "children": []})
    
    # 项目服务管理
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
            "name": "项目服务管理",
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
    
    # 权限管理（组织+角色+用户）
    if has_perm("organization", "view") or has_perm("role", "view") or has_perm("user", "view"):
        perm_children = []
        if has_perm("organization", "view"):
            perm_children.append({"id": "organization", "name": "组织管理", "icon": "office-building", "path": "/organization"})
        if has_perm("role", "view"):
            perm_children.append({"id": "roles", "name": "角色管理", "icon": "user", "path": "/roles"})
        if has_perm("user", "view"):
            perm_children.append({"id": "users", "name": "用户管理", "icon": "users", "path": "/users"})
        menu.append({
            "id": "permission",
            "name": "权限管理",
            "icon": "lock",
            "path": "",
            "children": perm_children
        })
    
    # 审计日志
    if has_perm("audit", "view"):
        menu.append({"id": "audit", "name": "审计日志", "icon": "file-search", "path": "/audit", "children": []})
    
    # 系统设置
    if has_perm("user", "view"):
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
