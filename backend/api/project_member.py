from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from models.project_member import ProjectMember
from models.project_permission import ProjectPermission, HIGH_RISK_FLAG_BY_CAPABILITY
from models.project import Project
from models.user import User
from schemas.common import ResponseModel
from core.database import get_db
from api.dependencies import get_current_user
from services.project_member_service import ProjectMemberService
from services.permission_service import PermissionService
from services.data_scope_service import DataScopeService
from services.audit_service import log_audit

router = APIRouter()


class AddMemberRequest(BaseModel):
    user_id: int
    role: str = "Viewer"


class ChangeRoleRequest(BaseModel):
    role: str


class ShareRequest(BaseModel):
    target_type: str
    target_id: int
    permission: str = "READ"
    # 高风险能力独立授权（不随"读写"自动开放，默认关闭）
    allow_webshell: Optional[bool] = False
    allow_root: Optional[bool] = False
    allow_sftp: Optional[bool] = False
    allow_service_delete: Optional[bool] = False
    allow_service_deploy: Optional[bool] = False
    allow_backup: Optional[bool] = False


class ShareUpdateRequest(BaseModel):
    permission: str
    allow_webshell: Optional[bool] = None
    allow_root: Optional[bool] = None
    allow_sftp: Optional[bool] = None
    allow_service_delete: Optional[bool] = None
    allow_service_deploy: Optional[bool] = None
    allow_backup: Optional[bool] = None


VALID_PROJECT_ROLES = ["Owner", "Manager", "Developer", "Operator", "Viewer"]
VALID_TARGET_TYPES = ["Organization", "Department", "User"]
# 对外只保留两级：READ（只读）/ EDIT（读写）。WRITE、MANAGE 为兼容别名，统一归为读写。
VALID_PERMISSIONS = ["READ", "EDIT", "WRITE", "MANAGE"]

# 高风险授权字段 → 授权人自身需具备的系统权限码（None 表示无对应系统权限码，不做系统级前置约束）
SHARE_CAPABILITY_PERMISSION = {
    "allow_webshell": "webshell:login",
    "allow_root": "webshell:root-login",
    "allow_sftp": None,
    "allow_service_delete": "service:deploy",
    "allow_service_deploy": "service:deploy",
    "allow_backup": "backup:manage",
}


def _normalize_permission(permission: str) -> Optional[str]:
    """将共享级别归一为两级：READ / EDIT（读写）。非法值返回 None。"""
    p = (permission or "").upper()
    if p == "READ":
        return "READ"
    if p in ("EDIT", "MANAGE", "WRITE"):
        return "EDIT"
    return None


def _assert_can_manage_sharing(db: Session, user: User, project: Project):
    """共享管理鉴权：超管 / 组织级管理员（本组织）/ 项目共享管理者 / 具备 project:share 的固有权限用户。

    仅通过 PUBLIC 可见或项目共享获得访问、不具备固有操作权的用户不得管理共享，
    防止其擅自提升自身共享级别或越权管理他人的授权。
    """
    if DataScopeService._is_super_admin(user):
        return
    if not DataScopeService.can_access_project(db, user, project.id):
        raise HTTPException(status_code=403, detail="无权访问该项目")
    if not DataScopeService.has_intrinsic_project_authority(db, user, project):
        raise HTTPException(status_code=403, detail="仅通过共享或公开可见获得访问，不能管理项目共享")
    if DataScopeService._is_org_wide(user) and user.organization_id and user.organization_id == project.organization_id:
        return
    if ProjectMemberService.has_permission(db, user.id, project.id, "manage_sharing") or \
       ProjectMemberService.has_permission(db, user.id, project.id, "manage_project"):
        return
    if PermissionService.user_has_permission(db, user.id, "project:share"):
        return
    raise HTTPException(status_code=403, detail="无权限管理项目共享")


def _assert_valid_share_target(db: Session, target_type: str, target_id: int):
    """校验共享目标对象存在，避免向不存在的用户/部门/组织写入授权记录。"""
    from models.department import Department
    from models.organization import Organization
    if target_type == "User":
        exists = db.query(User.id).filter(User.id == target_id).first() is not None
    elif target_type == "Department":
        exists = db.query(Department.id).filter(Department.id == target_id).first() is not None
    elif target_type == "Organization":
        exists = db.query(Organization.id).filter(Organization.id == target_id).first() is not None
    else:
        exists = False
    if not exists:
        raise HTTPException(status_code=400, detail=f"授权目标不存在: {target_type}:{target_id}")


def _assert_sharer_can_grant(db: Session, user: User, flags: dict):
    """授权上限校验：非管理员不得授予自身不具备的高风险能力。"""
    if DataScopeService._is_super_admin(user):
        return
    for flag, value in flags.items():
        if not value:
            continue
        code = SHARE_CAPABILITY_PERMISSION.get(flag)
        if code and not PermissionService.user_has_permission(db, user.id, code):
            raise HTTPException(status_code=403, detail=f"自身不具备该高风险能力，无法授予：{flag}")


def _resolve_target_name(db: Session, target_type: str, target_id: int) -> str:
    from models.department import Department
    from models.organization import Organization
    if target_type == "User":
        u = db.query(User).filter(User.id == target_id).first()
        return u.username if u else f"User_{target_id}"
    if target_type == "Department":
        d = db.query(Department).filter(Department.id == target_id).first()
        return d.name if d else f"Department_{target_id}"
    if target_type == "Organization":
        o = db.query(Organization).filter(Organization.id == target_id).first()
        return o.name if o else f"Organization_{target_id}"
    return f"{target_type}_{target_id}"


@router.get("/projects/{project_id}/members", response_model=ResponseModel)
async def get_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if not DataScopeService.can_access_project(db, user, project_id):
        raise HTTPException(status_code=403, detail="无权访问该项目")

    members = ProjectMemberService.get_project_members(db, project_id)
    result = []
    for member in members:
        u = db.query(User).filter(User.id == member.user_id).first()
        result.append({
            "id": member.id,
            "user_id": member.user_id,
            "username": u.username if u else "未知用户",
            "email": u.email if u else None,
            "role": member.role,
            "join_time": str(member.join_time) if member.join_time else None,
        })
    return ResponseModel(data=result)


@router.post("/projects/{project_id}/members", response_model=ResponseModel)
async def add_project_member(
    project_id: int,
    data: AddMemberRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if data.role not in VALID_PROJECT_ROLES:
        raise HTTPException(status_code=400, detail=f"无效的角色: {data.role}")

    if not ProjectMemberService.has_permission(db, user.id, project_id, "manage_project"):
        raise HTTPException(status_code=403, detail="无权限管理项目成员")

    member = ProjectMemberService.add_member(db, project_id, data.user_id, data.role)
    target_user = db.query(User).filter(User.id == data.user_id).first()
    log_audit(
        db, user.id, user.username, "PROJECT_SHARE",
        result="success",
        output=f"添加用户 {target_user.username if target_user else data.user_id} 为项目 {project.name} 的 {data.role}",
        project_id=project_id,
    )
    return ResponseModel(data={"id": member.id, "user_id": member.user_id, "role": member.role})


@router.put("/projects/{project_id}/members/{member_id}", response_model=ResponseModel)
async def change_member_role(
    project_id: int,
    member_id: int,
    data: ChangeRoleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if data.role not in VALID_PROJECT_ROLES:
        raise HTTPException(status_code=400, detail=f"无效的角色: {data.role}")

    if not ProjectMemberService.has_permission(db, user.id, project_id, "manage_project"):
        raise HTTPException(status_code=403, detail="无权限修改成员角色")

    member = db.query(ProjectMember).filter(ProjectMember.id == member_id).first()
    if not member or member.project_id != project_id:
        raise HTTPException(status_code=404, detail="成员不存在")

    success = ProjectMemberService.change_role(db, project_id, member.user_id, data.role)
    if not success:
        raise HTTPException(status_code=400, detail="无法修改角色")

    target_user = db.query(User).filter(User.id == member.user_id).first()
    log_audit(
        db, user.id, user.username, "PROJECT_SHARE",
        result="success",
        output=f"修改用户 {target_user.username if target_user else member.user_id} 在项目 {project.name} 的角色为 {data.role}",
        project_id=project_id,
    )
    return ResponseModel(message="角色修改成功")


@router.delete("/projects/{project_id}/members/{member_id}", response_model=ResponseModel)
async def remove_project_member(
    project_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if not ProjectMemberService.has_permission(db, user.id, project_id, "manage_project"):
        raise HTTPException(status_code=403, detail="无权限移除成员")

    member = db.query(ProjectMember).filter(ProjectMember.id == member_id).first()
    if not member or member.project_id != project_id:
        raise HTTPException(status_code=404, detail="成员不存在")

    if member.role == "Owner":
        raise HTTPException(status_code=400, detail="不可移除项目Owner")

    success = ProjectMemberService.remove_member(db, project_id, member.user_id)
    if not success:
        raise HTTPException(status_code=400, detail="移除失败")

    target_user = db.query(User).filter(User.id == member.user_id).first()
    log_audit(
        db, user.id, user.username, "PROJECT_SHARE_REMOVE",
        result="success",
        output=f"移除用户 {target_user.username if target_user else member.user_id} 的项目成员身份",
        project_id=project_id,
    )
    return ResponseModel(message="移除成功")


@router.get("/projects/{project_id}/permissions", response_model=ResponseModel)
async def get_project_permissions(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 共享列表属敏感授权信息，仅具备共享管理权限者可见
    _assert_can_manage_sharing(db, user, project)

    permissions = db.query(ProjectPermission).filter(ProjectPermission.project_id == project_id).all()
    result = []
    for perm in permissions:
        result.append({
            "id": perm.id,
            "target_type": perm.target_type,
            "target_id": perm.target_id,
            "target_name": _resolve_target_name(db, perm.target_type, perm.target_id),
            "permission": perm.permission,
            "level": "READ" if perm.permission == "READ" else "EDIT",
            "allow_webshell": bool(perm.allow_webshell),
            "allow_root": bool(perm.allow_root),
            "allow_sftp": bool(perm.allow_sftp),
            "allow_service_delete": bool(perm.allow_service_delete),
            "allow_service_deploy": bool(perm.allow_service_deploy),
            "allow_backup": bool(perm.allow_backup),
            "created_by": perm.created_by,
            "created_time": str(perm.created_time) if perm.created_time else None,
        })
    return ResponseModel(data=result)


@router.post("/projects/{project_id}/permissions", response_model=ResponseModel)
async def share_project(
    project_id: int,
    data: ShareRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    _assert_can_manage_sharing(db, user, project)

    if data.target_type not in VALID_TARGET_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的授权目标类型: {data.target_type}")

    _assert_valid_share_target(db, data.target_type, data.target_id)

    normalized = _normalize_permission(data.permission)
    if not normalized:
        raise HTTPException(status_code=400, detail=f"无效的权限等级: {data.permission}")

    flags = {flag: bool(getattr(data, flag)) for flag in HIGH_RISK_FLAG_BY_CAPABILITY.values()}
    _assert_sharer_can_grant(db, user, flags)

    existing = db.query(ProjectPermission).filter(
        ProjectPermission.project_id == project_id,
        ProjectPermission.target_type == data.target_type,
        ProjectPermission.target_id == data.target_id,
    ).first()
    if existing:
        existing.permission = normalized
        for flag, value in flags.items():
            setattr(existing, flag, value)
        db.commit()
        log_audit(
            db, user.id, user.username, "PROJECT_SHARE",
            result="success",
            output=f"更新项目 {project.name} 共享权限: {data.target_type}:{data.target_id} -> {normalized}",
            project_id=project_id,
        )
        return ResponseModel(data={"id": existing.id, "permission": existing.permission, "level": normalized})

    perm = ProjectPermission(
        project_id=project_id,
        target_type=data.target_type,
        target_id=data.target_id,
        permission=normalized,
        created_by=user.id,
        **flags,
    )
    db.add(perm)
    db.commit()

    log_audit(
        db, user.id, user.username, "PROJECT_SHARE",
        result="success",
        output=f"共享项目 {project.name} 给 {data.target_type}:{data.target_id} ({normalized})",
        project_id=project_id,
    )
    return ResponseModel(data={"id": perm.id, "permission": perm.permission, "level": normalized})


@router.put("/projects/{project_id}/permissions/{perm_id}", response_model=ResponseModel)
async def update_project_permission(
    project_id: int,
    perm_id: int,
    data: ShareUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    _assert_can_manage_sharing(db, user, project)

    perm = db.query(ProjectPermission).filter(
        ProjectPermission.id == perm_id,
        ProjectPermission.project_id == project_id,
    ).first()
    if not perm:
        raise HTTPException(status_code=404, detail="授权记录不存在")

    normalized = _normalize_permission(data.permission)
    if not normalized:
        raise HTTPException(status_code=400, detail=f"无效的权限等级: {data.permission}")

    # 仅更新显式传入的高风险字段，未传入的保持原值（兼容增量授权）
    flags = {}
    for flag in HIGH_RISK_FLAG_BY_CAPABILITY.values():
        value = getattr(data, flag)
        if value is not None:
            flags[flag] = bool(value)
    _assert_sharer_can_grant(db, user, flags)

    perm.permission = normalized
    for flag, value in flags.items():
        setattr(perm, flag, value)
    db.commit()

    log_audit(
        db, user.id, user.username, "PROJECT_SHARE",
        result="success",
        output=f"更新项目 {project.name} 共享权限 ID:{perm_id} -> {normalized}",
        project_id=project_id,
    )
    return ResponseModel(message="权限更新成功")


@router.delete("/projects/{project_id}/permissions/{perm_id}", response_model=ResponseModel)
async def remove_project_permission(
    project_id: int,
    perm_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    _assert_can_manage_sharing(db, user, project)

    perm = db.query(ProjectPermission).filter(
        ProjectPermission.id == perm_id,
        ProjectPermission.project_id == project_id,
    ).first()
    if not perm:
        raise HTTPException(status_code=404, detail="授权记录不存在")

    db.delete(perm)
    db.commit()

    log_audit(
        db, user.id, user.username, "PROJECT_SHARE_REMOVE",
        result="success",
        output=f"取消项目 {project.name} 的共享权限 ID:{perm_id}",
        project_id=project_id,
    )
    return ResponseModel(message="取消成功")


@router.put("/projects/{project_id}/visibility", response_model=ResponseModel)
async def update_project_visibility(
    project_id: int,
    visibility: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    _assert_can_manage_sharing(db, user, project)

    if visibility not in ["DEPARTMENT", "AUTHORIZED", "PUBLIC"]:
        raise HTTPException(status_code=400, detail=f"无效的可见性: {visibility}")

    project.visibility = visibility
    db.commit()

    log_audit(
        db, user.id, user.username, "PROJECT_UPDATE",
        result="success",
        output=f"修改项目 {project.name} 可见性为 {visibility}",
        project_id=project_id,
    )
    return ResponseModel(data={"id": project.id, "visibility": project.visibility})


class BatchByDeptRequest(BaseModel):
    department_id: int
    role: str = "Viewer"


class BatchByRoleRequest(BaseModel):
    role_id: int
    project_role: str = "Viewer"


class DeptInfo(BaseModel):
    id: int
    name: str
    organization_id: Optional[int] = None


@router.get("/departments/list", response_model=ResponseModel)
async def list_departments_for_batch(
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取部门扁平列表（用于批量添加下拉选择）"""
    from models.department import Department
    query = db.query(Department)
    if org_id:
        query = query.filter(Department.organization_id == org_id)
    depts = query.filter(Department.status == 1).all()
    result = [{"id": d.id, "name": d.name, "organization_id": d.organization_id} for d in depts]
    return ResponseModel(data=result)


@router.get("/departments/tree-flat", response_model=ResponseModel)
async def get_departments_flat(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取所有部门的扁平列表，带组织名前缀"""
    from models.department import Department
    from models.organization import Organization
    orgs = db.query(Organization).all()
    depts = db.query(Department).filter(Department.status == 1).all()
    result = []
    for d in depts:
        org = next((o for o in orgs if o.id == d.organization_id), None)
        result.append({
            "id": d.id,
            "name": f"{org.name if org else ''} / {d.name}",
            "organization_id": d.organization_id,
        })
    return ResponseModel(data=result)


@router.post("/projects/{project_id}/members/batch-by-department", response_model=ResponseModel)
async def batch_add_by_department(
    project_id: int,
    data: BatchByDeptRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if data.role not in VALID_PROJECT_ROLES:
        raise HTTPException(status_code=400, detail=f"无效的角色: {data.role}")

    if not ProjectMemberService.has_permission(db, user.id, project_id, "manage_project"):
        raise HTTPException(status_code=403, detail="无权限批量添加成员")

    try:
        result = ProjectMemberService.batch_add_by_department(
            db, project_id, data.department_id, data.role
        )
        log_audit(
            db, user.id, user.username, "PROJECT_MEMBER_BATCH_ADD",
            result="success",
            output=f"按部门ID:{data.department_id}批量添加项目{project.name}成员, 新增{result['added']}人, 跳过{result['skipped']}人",
            project_id=project_id,
        )
        return ResponseModel(
            data=result,
            message=f"批量添加完成：新增 {result['added']} 人，跳过 {result['skipped']} 人"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/members/batch-by-role", response_model=ResponseModel)
async def batch_add_by_system_role(
    project_id: int,
    data: BatchByRoleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if data.project_role not in VALID_PROJECT_ROLES:
        raise HTTPException(status_code=400, detail=f"无效的项目角色: {data.project_role}")

    if not ProjectMemberService.has_permission(db, user.id, project_id, "manage_project"):
        raise HTTPException(status_code=403, detail="无权限批量添加成员")

    try:
        result = ProjectMemberService.batch_add_by_system_role(
            db, project_id, data.role_id, data.project_role
        )
        log_audit(
            db, user.id, user.username, "PROJECT_MEMBER_BATCH_ADD",
            result="success",
            output=f"按系统角色ID:{data.role_id}批量添加项目{project.name}成员, 新增{result['added']}人, 跳过{result['skipped']}人",
            project_id=project_id,
        )
        return ResponseModel(
            data=result,
            message=f"批量添加完成：新增 {result['added']} 人，跳过 {result['skipped']} 人"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
