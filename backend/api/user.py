from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.user import User
from schemas.user import UserCreate, UserUpdate, UserResponse
from schemas.common import ResponseModel
from services.auth_service import get_password_hash, verify_password
from services.audit_service import log_audit
from core.database import get_db
from core.capabilities import ROLE_PERMISSIONS, SERVICE_TYPE_CAPABILITIES, ServiceType
from api.dependencies import get_current_user, require_permission

router = APIRouter()

@router.get("/users", response_model=ResponseModel)
async def get_users(db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    users = db.query(User).all()
    return ResponseModel(data=users)

@router.get("/users/{user_id}", response_model=ResponseModel)
async def get_user(user_id: int, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return ResponseModel(data=user)

@router.post("/users", response_model=ResponseModel)
async def create_user(user_create: UserCreate, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    existing = db.query(User).filter(User.username == user_create.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    new_user = User(
        username=user_create.username,
        password=get_password_hash(user_create.password),
        role=user_create.role,
        email=user_create.email,
        phone=user_create.phone
    )
    db.add(new_user)
    db.commit()
    
    log_audit(db, user.id, user.username, "CREATE", result="success", output=f"Created user: {user_create.username}")
    
    return ResponseModel(data=new_user)

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
    
    db.commit()
    
    log_audit(db, user.id, user.username, "UPDATE", result="success", output=f"Updated user: {user_to_update.username}")
    
    return ResponseModel(data=user_to_update)

@router.delete("/users/{user_id}", response_model=ResponseModel)
async def delete_user(user_id: int, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    user_to_delete = db.query(User).filter(User.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_to_delete.role == "ADMIN" and db.query(User).filter(User.role == "ADMIN").count() <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only ADMIN user")
    
    db.delete(user_to_delete)
    db.commit()
    
    log_audit(db, user.id, user.username, "DELETE", result="success", output=f"Deleted user: {user_to_delete.username}")
    
    return ResponseModel(message="User deleted successfully")

@router.get("/user/menu", response_model=ResponseModel)
async def get_user_menu(db: Session = Depends(get_db), user = Depends(get_current_user)):
    permissions = ROLE_PERMISSIONS.get(user.role, [])
    
    menu = [
        {"id": "dashboard", "name": "Dashboard", "icon": "dashboard", "path": "/dashboard", "children": []},
        {"id": "services", "name": "服务管理", "icon": "server", "path": "/services", "children": []},
        {"id": "servers", "name": "服务器管理", "icon": "computer", "path": "/servers", "children": []},
        {"id": "logs", "name": "日志中心", "icon": "file-text", "path": "/logs", "children": []},
        {"id": "shell", "name": "WebShell", "icon": "terminal", "path": "/shell", "children": []}
    ]
    
    service_types = db.query(Service.service_type).distinct().all()
    service_types = [st[0] for st in service_types]
    
    has_database_service = any(st in ['MYSQL', 'KINGBASE', 'DAMENG'] for st in service_types)
    has_es_service = any(st == 'ELASTICSEARCH' for st in service_types)
    
    if "sql_execute" in permissions and has_database_service:
        menu.append({"id": "sql", "name": "数据库管理", "icon": "database", "path": "/sql", "children": []})
    
    if "service_view" in permissions and has_es_service:
        menu.append({"id": "es", "name": "Elasticsearch管理", "icon": "search", "path": "/es", "children": []})
    
    if "audit_view" in permissions:
        menu.append({"id": "audit", "name": "审计日志", "icon": "file-search", "path": "/audit", "children": []})
    
    if "user_manage" in permissions:
        menu.append({"id": "users", "name": "用户管理", "icon": "users", "path": "/users", "children": []})
        menu.append({"id": "settings", "name": "系统设置", "icon": "settings", "path": "/settings", "children": []})
    
    return ResponseModel(data=menu)
