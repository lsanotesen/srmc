from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload, joinedload
from models.project import Project
from models.subsystem_group_relation import SubsystemGroupRelation
from schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from schemas.common import ResponseModel
from services.audit_service import log_audit
from core.database import get_db
from api.dependencies import get_current_user, require_permission
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font
from io import BytesIO
import io

router = APIRouter()


def _project_to_dict(db: Session, project: Project) -> dict:
    """将 Project 对象转换为字典，带组织/部门/负责人名称"""
    from models.organization import Organization
    from models.department import Department
    from models.user import User

    org_name = None
    if project.organization_id:
        org = db.query(Organization).filter(Organization.id == project.organization_id).first()
        if org:
            org_name = org.name

    dept_name = None
    if project.department_id:
        dept = db.query(Department).filter(Department.id == project.department_id).first()
        if dept:
            dept_name = dept.name

    owner_name = None
    if project.owner_id:
        owner = db.query(User).filter(User.id == project.owner_id).first()
        if owner:
            owner_name = owner.job_title or owner.username

    creator_name = None
    if project.creator_id:
        creator = db.query(User).filter(User.id == project.creator_id).first()
        if creator:
            creator_name = creator.job_title or creator.username

    return {
        'id': project.id,
        'name': project.name,
        'project_name': project.name,
        'code': project.code,
        'description': project.description,
        'organization_id': project.organization_id,
        'organization_name': org_name,
        'department_id': project.department_id,
        'department_name': dept_name,
        'creator_id': project.creator_id,
        'creator_name': creator_name,
        'owner_id': project.owner_id,
        'owner_name': owner_name,
        'visibility': project.visibility or 'DEPARTMENT',
    }


@router.get("/projects", response_model=ResponseModel)
async def get_projects(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    name: str = Query(None),
    code: str = Query(None),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    query = db.query(Project)

    if name:
        query = query.filter(Project.name.like(f"%{name}%"))
    if code:
        query = query.filter(Project.code.like(f"%{code}%"))

    total = query.count()
    projects = query.offset((page - 1) * size).limit(size).all()

    result = [_project_to_dict(db, p) for p in projects]

    return ResponseModel(data={"items": result, "total": total, "page": page, "size": size})

@router.get("/projects/tree", response_model=ResponseModel)
async def get_project_tree(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    from models.subsystem import Subsystem
    from models.service_group import ServiceGroup
    from sqlalchemy import select, func
    
    # 使用预加载优化查询性能，避免N+1问题
    projects = db.query(Project).options(
        selectinload(Project.subsystems).joinedload(Subsystem.group_relations).joinedload(SubsystemGroupRelation.group)
    ).all()
    
    result = []
    for project in projects:
        project_data = {
            "id": project.id,
            "name": project.name,
            "subsystems": []
        }
        
        for subsystem in project.subsystems:
            subsystem_data = {
                "id": subsystem.id,
                "subsystem_name": subsystem.subsystem_name,
                "subsystem_code": subsystem.subsystem_code,
                "service_groups": []
            }
            
            # 通过预加载的关联关系获取服务组
            for relation in subsystem.group_relations:
                if relation.group:
                    subsystem_data["service_groups"].append({
                        "id": relation.group.id,
                        "group_name": relation.group.group_name,
                        "group_code": relation.group.group_code
                    })
            
            project_data["subsystems"].append(subsystem_data)
        
        result.append(project_data)
    
    return ResponseModel(data=result)

@router.get("/projects/{project_id}", response_model=ResponseModel)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    return ResponseModel(data={
        'id': project.id,
        'name': project.name,
        'project_name': project.name,
        'code': project.code,
        'description': project.description
    })

@router.get("/projects/{project_id}/subsystems", response_model=ResponseModel)
async def get_project_subsystems(
    project_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    from models.subsystem import Subsystem
    
    subsystems = db.query(Subsystem).filter(Subsystem.project_id == project_id).all()
    result = []
    for subsystem in subsystems:
        result.append({
            'id': subsystem.id,
            'subsystem_name': subsystem.subsystem_name,
            'subsystem_code': subsystem.subsystem_code,
            'description': subsystem.description
        })
    
    return ResponseModel(data=result)

@router.post("/projects", response_model=ResponseModel)
async def create_project(
    project_create: ProjectCreate,
    db: Session = Depends(get_db),
    user = Depends(require_permission("project_manage"))
):
    existing = db.query(Project).filter(Project.name == project_create.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="项目名称已存在")

    # 校验所属组织存在性
    organization_id = project_create.organization_id
    if not organization_id:
        # 未指定组织时，默认使用当前用户所在组织
        organization_id = getattr(user, "organization_id", None)
    if organization_id:
        from models.organization import Organization
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        if not org:
            raise HTTPException(status_code=400, detail="所属组织不存在")

    # 校验部门归属与组织一致
    if project_create.department_id and organization_id:
        from models.department import Department
        dept = db.query(Department).filter(Department.id == project_create.department_id).first()
        if not dept:
            raise HTTPException(status_code=400, detail="所属部门不存在")
        if dept.organization_id != organization_id:
            raise HTTPException(status_code=400, detail="所属部门不属于该组织")

    new_project = Project(
        name=project_create.name,
        code=project_create.code,
        description=project_create.description,
        organization_id=organization_id,
        department_id=project_create.department_id,
        visibility=project_create.visibility or "DEPARTMENT",
        owner_id=project_create.owner_id,
        creator_id=user.id,
    )

    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    log_audit(db, user.id, user.username, "PROJECT_CREATE",
              result="success", output=f"创建项目: {project_create.name}")

    return ResponseModel(data=_project_to_dict(db, new_project))

@router.put("/projects/{project_id}", response_model=ResponseModel)
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_permission("project_manage"))
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if project_update.name and project_update.name != project.name:
        existing = db.query(Project).filter(Project.name == project_update.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="项目名称已存在")
        project.name = project_update.name

    if project_update.code is not None:
        project.code = project_update.code
    if project_update.description is not None:
        project.description = project_update.description

    # 组织可用于首次设置；已设置组织时不允许修改（由前端锁定控制）
    if project_update.organization_id is not None:
        if project.organization_id and project.organization_id != project_update.organization_id:
            raise HTTPException(status_code=400, detail="项目已关联组织，不可修改")
        if project_update.organization_id:
            from models.organization import Organization
            org = db.query(Organization).filter(Organization.id == project_update.organization_id).first()
            if not org:
                raise HTTPException(status_code=400, detail="所属组织不存在")
        project.organization_id = project_update.organization_id

    # 部门可修改，但必须属于项目所在组织
    if project_update.department_id is not None:
        if project_update.department_id:
            from models.department import Department
            dept = db.query(Department).filter(Department.id == project_update.department_id).first()
            if not dept:
                raise HTTPException(status_code=400, detail="所属部门不存在")
            effective_org_id = project.organization_id
            if effective_org_id and dept.organization_id != effective_org_id:
                raise HTTPException(status_code=400, detail="所属部门不属于该项目所在组织")
        project.department_id = project_update.department_id

    if project_update.visibility is not None:
        project.visibility = project_update.visibility
    if project_update.owner_id is not None:
        project.owner_id = project_update.owner_id

    db.commit()
    db.refresh(project)

    log_audit(db, user.id, user.username, "PROJECT_UPDATE",
              result="success", output=f"更新项目: {project.name}")

    return ResponseModel(data=_project_to_dict(db, project))

@router.delete("/projects/{project_id}", response_model=ResponseModel)
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_permission("project_manage"))
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_name = project.name

    # 1. 先清理没有数据库外键级联的关联数据
    # AppService 没有数据库级外键约束，需要手动清理
    from models.app_service import AppService
    db.query(AppService).filter(AppService.project_id == project_id).delete(synchronize_session=False)

    # 2. ProjectMember 有 CASCADE 外键，但显式删除更安全
    from models.project_member import ProjectMember
    db.query(ProjectMember).filter(ProjectMember.project_id == project_id).delete(synchronize_session=False)

    # 3. ProjectPermission 有 CASCADE 外键
    from models.project_permission import ProjectPermission
    db.query(ProjectPermission).filter(ProjectPermission.project_id == project_id).delete(synchronize_session=False)

    # 4. RoleProjectPermission 无数据库级外键
    from models.role_project_permission import RoleProjectPermission
    db.query(RoleProjectPermission).filter(RoleProjectPermission.project_id == project_id).delete(synchronize_session=False)

    # 5. ResourceGroup 有 CASCADE 外键
    from models.resource_group import ResourceGroup
    db.query(ResourceGroup).filter(ResourceGroup.project_id == project_id).delete(synchronize_session=False)

    # 6. 清理 SubsystemGroupRelation（Subsystem 的级联）
    from models.subsystem import Subsystem
    from models.subsystem_group_relation import SubsystemGroupRelation
    subsystem_ids = [s[0] for s in db.query(Subsystem.id).filter(Subsystem.project_id == project_id).all()]
    if subsystem_ids:
        db.query(SubsystemGroupRelation).filter(SubsystemGroupRelation.subsystem_id.in_(subsystem_ids)).delete(synchronize_session=False)

    # 7. 最后删除项目（CASCADE 外键会自动处理 Subsystem）
    db.delete(project)
    db.commit()

    log_audit(db, user.id, user.username, "PROJECT_DELETE",
              result="success", output=f"删除项目: {project_name}")

    return ResponseModel(data={"id": project_id})

@router.get("/projects/template")
async def download_project_template(
    user = Depends(require_permission("project_manage"))
):
    """下载项目导入模板"""
    headers = ['项目名称', '项目编码', '项目描述']

    wb = Workbook()
    ws = wb.active
    ws.title = "项目导入模板"

    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=projects_template.xlsx"}
    )


@router.get("/projects/export")
async def export_projects(
    db: Session = Depends(get_db),
    user = Depends(require_permission("project_manage"))
):
    projects = db.query(Project).all()

    headers = ['name', 'code', 'description']

    wb = Workbook()
    ws = wb.active
    ws.title = "项目列表"

    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font

    for row_idx, project in enumerate(projects, 2):
        ws.cell(row=row_idx, column=1, value=project.name)
        ws.cell(row=row_idx, column=2, value=project.code or '')
        ws.cell(row=row_idx, column=3, value=project.description or '')

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=projects.xlsx"}
    )

@router.post("/projects/import", response_model=ResponseModel)
async def import_projects(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user = Depends(require_permission("project_manage"))
):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="仅支持xlsx格式文件")

    try:
        file_content = await file.read()
        wb = load_workbook(filename=io.BytesIO(file_content), read_only=True)
        ws = wb.active

        headers = []
        for col in range(1, ws.max_column + 1):
            header = ws.cell(row=1, column=col).value
            headers.append(header.strip() if header else '')

        rows = []
        for row in range(2, ws.max_row + 1):
            row_data = {}
            for col in range(1, ws.max_column + 1):
                header = headers[col - 1]
                value = ws.cell(row=row, column=col).value
                if value is not None:
                    row_data[header] = str(value) if isinstance(value, (int, float)) else value
            if row_data:
                rows.append(row_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")

    added = 0
    updated = 0
    failed = 0
    failed_items = []

    for idx, row in enumerate(rows):
        try:
            name = str(row.get('name', '')).strip()
            if not name:
                failed += 1
                failed_items.append({"row": idx + 2, "reason": "缺少项目名称"})
                continue

            existing = db.query(Project).filter(Project.name == name).first()

            if existing:
                if 'code' in row:
                    existing.code = str(row.get('code', '')).strip() or None
                if 'description' in row:
                    existing.description = str(row.get('description', '')).strip() or None
                db.commit()
                updated += 1
            else:
                new_project = Project(
                    name=name,
                    code=str(row.get('code', '')).strip() or None,
                    description=str(row.get('description', '')).strip() or None
                )
                db.add(new_project)
                db.commit()
                added += 1
        except Exception as e:
            failed += 1
            failed_items.append({"row": idx + 2, "reason": str(e)})

    log_audit(db, user.id, user.username, "PROJECT_IMPORT",
              result="success",
              output=f"导入完成: 新增{added}条, 更新{updated}条, 失败{failed}条")

    return ResponseModel(data={
        "success": True,
        "message": f"导入完成: 新增{added}条, 更新{updated}条, 失败{failed}条",
        "added": added,
        "updated": updated,
        "failed": failed,
        "failed_items": failed_items
    })

@router.get("/projects/list", response_model=ResponseModel)
async def list_projects(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    projects = db.query(Project).all()
    result = [{"id": p.id, "name": p.name, "project_name": p.name} for p in projects]
    return ResponseModel(data=result)
