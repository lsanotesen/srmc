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

    result = []
    for project in projects:
        result.append({
            'id': project.id,
            'name': project.name,
            'project_name': project.name,
            'code': project.code,
            'description': project.description
        })

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

@router.post("/projects", response_model=ResponseModel)
async def create_project(
    project_create: ProjectCreate,
    db: Session = Depends(get_db),
    user = Depends(require_permission("project_manage"))
):
    existing = db.query(Project).filter(Project.name == project_create.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="项目名称已存在")

    new_project = Project(
        name=project_create.name,
        code=project_create.code,
        description=project_create.description
    )

    db.add(new_project)
    db.commit()

    log_audit(db, user.id, user.username, "PROJECT_CREATE",
              result="success", output=f"创建项目: {project_create.name}")

    return ResponseModel(data={
        'id': new_project.id,
        'name': new_project.name,
        'project_name': new_project.name,
        'code': new_project.code,
        'description': new_project.description
    })

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

    db.commit()

    log_audit(db, user.id, user.username, "PROJECT_UPDATE",
              result="success", output=f"更新项目: {project.name}")

    return ResponseModel(data={
        'id': project.id,
        'name': project.name,
        'project_name': project.name,
        'code': project.code,
        'description': project.description
    })

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
