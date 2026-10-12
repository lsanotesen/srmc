from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from models.role import Role
from models.permission import Permission
from models.role_permission import RolePermission
from models.user_role import UserRole
from models.user import User
from schemas.common import ResponseModel
from core.database import get_db
from api.dependencies import get_current_user, require_permission
from services.role_permission_service import RolePermissionService
from services.data_scope_service import DataScopeService
from services.audit_service import log_audit

router = APIRouter()


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class RolePermAssign(BaseModel):
    permission_ids: List[int]


class UserRoleAssign(BaseModel):
    user_ids: List[int]


@router.get("/roles", response_model=ResponseModel)
async def list_roles(
    include_system: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("role:view")),
):
    roles = RolePermissionService.list_roles(db, include_system=include_system)
    result = [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "is_system": r.is_system,
        }
        for r in roles
    ]
    return ResponseModel(data=result)


@router.post("/roles", response_model=ResponseModel)
async def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not DataScopeService._is_super_admin(user):
        raise HTTPException(status_code=403, detail="仅超级管理员可创建角色")

    try:
        role = RolePermissionService.create_role(db, data.name, data.description)
        log_audit(db, user.id, user.username, "ROLE_CREATE", result="success", output=f"创建角色: {data.name}")
        return ResponseModel(data={"id": role.id, "name": role.name})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/roles/{role_id}", response_model=ResponseModel)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not DataScopeService._is_super_admin(user):
        raise HTTPException(status_code=403, detail="仅超级管理员可修改角色")

    try:
        role = RolePermissionService.update_role(db, role_id, data.name, data.description)
        log_audit(db, user.id, user.username, "ROLE_UPDATE", result="success", output=f"更新角色: {role.name}")
        return ResponseModel(data={"id": role.id, "name": role.name})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/roles/{role_id}", response_model=ResponseModel)
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not DataScopeService._is_super_admin(user):
        raise HTTPException(status_code=403, detail="仅超级管理员可删除角色")

    try:
        role = RolePermissionService.delete_role(db, role_id)
        log_audit(db, user.id, user.username, "ROLE_DELETE", result="success", output=f"删除角色 ID: {role_id}")
        return ResponseModel(message="删除成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/roles/{role_id}/permissions", response_model=ResponseModel)
async def get_role_permissions(
    role_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("role:view")),
):
    perms = RolePermissionService.get_role_permissions(db, role_id)
    return ResponseModel(data=perms)


@router.post("/roles/{role_id}/permissions", response_model=ResponseModel)
async def assign_permissions_to_role(
    role_id: int,
    data: RolePermAssign,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not DataScopeService._is_super_admin(user):
        raise HTTPException(status_code=403, detail="仅超级管理员可分配权限")

    try:
        diff = RolePermissionService.assign_permissions_to_role(db, role_id, data.permission_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_audit(
        db, user.id, user.username, "PERMISSION_GRANT", result="success",
        output=(
            f"为角色 '{diff['role_name']}'(ID:{role_id}) 保存功能权限："
            f"新增 {diff['added']}，移除 {diff['removed']}"
        ),
    )
    return ResponseModel(message="权限保存成功")


@router.delete("/roles/{role_id}/permissions", response_model=ResponseModel)
async def remove_permissions_from_role(
    role_id: int,
    data: RolePermAssign,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not DataScopeService._is_super_admin(user):
        raise HTTPException(status_code=403, detail="仅超级管理员可移除权限")

    RolePermissionService.remove_permissions_from_role(db, role_id, data.permission_ids)
    log_audit(db, user.id, user.username, "PERMISSION_REVOKE", result="success", output=f"为角色 ID:{role_id} 移除 {len(data.permission_ids)} 个权限")
    return ResponseModel(message="权限移除成功")


@router.get("/permissions", response_model=ResponseModel)
async def list_permissions(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("role:view")),
):
    perms = RolePermissionService.list_permissions(db)
    result = [
        {
            "id": p.id,
            "resource": p.resource,
            "action": p.action,
            "name": p.name,
            "description": p.description,
        }
        for p in perms
    ]
    return ResponseModel(data=result)


@router.get("/users/{user_id}/roles", response_model=ResponseModel)
async def get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("user:view")),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    # 数据范围：不得查看数据范围外用户的角色
    if not DataScopeService.can_access_user(user, target):
        raise HTTPException(status_code=403, detail="无权查看该用户")
    roles = RolePermissionService.get_user_roles(db, user_id)
    return ResponseModel(data=roles)


@router.post("/users/{user_id}/roles/{role_id}", response_model=ResponseModel)
async def assign_role_to_user(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not DataScopeService._is_super_admin(user):
        raise HTTPException(status_code=403, detail="仅超级管理员可分配角色")

    RolePermissionService.assign_role(db, user_id, role_id)
    log_audit(db, user.id, user.username, "PERMISSION_GRANT", result="success", output=f"为用户 ID:{user_id} 分配角色 ID:{role_id}")
    return ResponseModel(message="角色分配成功")


@router.delete("/users/{user_id}/roles/{role_id}", response_model=ResponseModel)
async def revoke_role_from_user(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not DataScopeService._is_super_admin(user):
        raise HTTPException(status_code=403, detail="仅超级管理员可撤销角色")

    RolePermissionService.revoke_role(db, user_id, role_id)
    log_audit(db, user.id, user.username, "PERMISSION_REVOKE", result="success", output=f"为用户 ID:{user_id} 撤销角色 ID:{role_id}")
    return ResponseModel(message="角色撤销成功")


@router.get("/users/{user_id}/permissions", response_model=ResponseModel)
async def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("user:view")),
):
    from services.permission_service import PermissionService
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    # 数据范围：不得查看数据范围外用户的权限
    if not DataScopeService.can_access_user(user, target):
        raise HTTPException(status_code=403, detail="无权查看该用户")
    perms = PermissionService.get_user_permissions(db, user_id)
    return ResponseModel(data=perms)


@router.post("/permissions/check", response_model=ResponseModel)
async def check_permission(
    resource_type: str = Query(...),
    action: str = Query(...),
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from services.unified_permission_service import UnifiedPermissionService, ResourceContext
    context = ResourceContext(resource_type, 0, project_id)
    has = UnifiedPermissionService.has_permission(db, user.id, context, action)
    return ResponseModel(data={"has_permission": has})


# 注：项目权限管理已迁移至项目上下文
# - 项目成员角色（Owner/Manager/Developer/Operator/Viewer）：/api/projects/{id}/members
# - 项目共享权限（READ/EDIT/MANAGE）：/api/projects/{id}/permissions
# 系统角色不再配置项目级权限，避免概念混淆
