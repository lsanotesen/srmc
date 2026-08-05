from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from models.project_member import ProjectMember
from models.project_permission import ProjectPermission
from models.project import Project
from models.user import User
from schemas.common import ResponseModel
from core.database import get_db
from api.dependencies import get_current_user
from services.project_member_service import ProjectMemberService
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


class ShareUpdateRequest(BaseModel):
    permission: str


VALID_PROJECT_ROLES = ["Owner", "Manager", "Developer", "Operator", "Viewer"]
VALID_TARGET_TYPES = ["Organization", "Department", "User"]
VALID_PERMISSIONS = ["READ", "EDIT", "MANAGE"]


@router.get("/projects/{project_id}/members", response_model=ResponseModel)
async def get_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

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

    permissions = db.query(ProjectPermission).filter(ProjectPermission.project_id == project_id).all()
    result = []
    for perm in permissions:
        target_name = f"{perm.target_type}_{perm.target_id}"
        result.append({
            "id": perm.id,
            "target_type": perm.target_type,
            "target_id": perm.target_id,
            "target_name": target_name,
            "permission": perm.permission,
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

    if data.target_type not in VALID_TARGET_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的授权目标类型: {data.target_type}")

    if data.permission not in VALID_PERMISSIONS:
        raise HTTPException(status_code=400, detail=f"无效的权限等级: {data.permission}")

    existing = db.query(ProjectPermission).filter(
        ProjectPermission.project_id == project_id,
        ProjectPermission.target_type == data.target_type,
        ProjectPermission.target_id == data.target_id,
    ).first()
    if existing:
        existing.permission = data.permission
        db.commit()
        log_audit(
            db, user.id, user.username, "PROJECT_SHARE",
            result="success",
            output=f"更新项目 {project.name} 共享权限: {data.target_type}:{data.target_id} -> {data.permission}",
            project_id=project_id,
        )
        return ResponseModel(data={"id": existing.id, "permission": existing.permission})

    perm = ProjectPermission(
        project_id=project_id,
        target_type=data.target_type,
        target_id=data.target_id,
        permission=data.permission,
        created_by=user.id,
    )
    db.add(perm)
    db.commit()

    log_audit(
        db, user.id, user.username, "PROJECT_SHARE",
        result="success",
        output=f"共享项目 {project.name} 给 {data.target_type}:{data.target_id} ({data.permission})",
        project_id=project_id,
    )
    return ResponseModel(data={"id": perm.id, "permission": perm.permission})


@router.put("/projects/{project_id}/permissions/{perm_id}", response_model=ResponseModel)
async def update_project_permission(
    project_id: int,
    perm_id: int,
    data: ShareUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    perm = db.query(ProjectPermission).filter(
        ProjectPermission.id == perm_id,
        ProjectPermission.project_id == project_id,
    ).first()
    if not perm:
        raise HTTPException(status_code=404, detail="授权记录不存在")

    if data.permission not in VALID_PERMISSIONS:
        raise HTTPException(status_code=400, detail=f"无效的权限等级: {data.permission}")

    perm.permission = data.permission
    db.commit()

    project = db.query(Project).filter(Project.id == project_id).first()
    log_audit(
        db, user.id, user.username, "PROJECT_SHARE",
        result="success",
        output=f"更新项目 {project.name} 共享权限 ID:{perm_id} -> {data.permission}",
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
    perm = db.query(ProjectPermission).filter(
        ProjectPermission.id == perm_id,
        ProjectPermission.project_id == project_id,
    ).first()
    if not perm:
        raise HTTPException(status_code=404, detail="授权记录不存在")

    db.delete(perm)
    db.commit()

    project = db.query(Project).filter(Project.id == project_id).first()
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
