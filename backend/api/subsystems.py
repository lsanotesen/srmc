from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from models.subsystem import Subsystem
from models.project import Project
from schemas.subsystem import SubsystemCreate, SubsystemUpdate, SubsystemResponse
from schemas.common import ResponseModel
from services.audit_service import log_audit
from core.database import get_db
from api.dependencies import get_current_user

router = APIRouter()

@router.get("/subsystems", response_model=ResponseModel)
async def list_subsystems(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    project_id: int = Query(None, description="项目ID"),
    keyword: str = Query(None, description="搜索关键字"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """获取子系统列表"""
    query = db.query(Subsystem, Project).outerjoin(Project, Subsystem.project_id == Project.id)
    if project_id:
        query = query.filter(Subsystem.project_id == project_id)
    if keyword:
        query = query.filter(
            (Subsystem.subsystem_name.like(f"%{keyword}%")) |
            (Subsystem.subsystem_code.like(f"%{keyword}%"))
        )
    
    total = query.count()
    results = query.order_by(Subsystem.display_order, Subsystem.id)\
        .offset((page - 1) * size).limit(size).all()
    
    items = []
    for subsystem, project in results:
        data = SubsystemResponse.model_validate(subsystem).dict()
        data['project_name'] = project.name if project else None
        items.append(data)
    
    return ResponseModel(data={
        "items": items,
        "total": total,
        "page": page,
        "size": size
    })

@router.get("/subsystems/{subsystem_id}", response_model=ResponseModel)
async def get_subsystem(
    subsystem_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """获取子系统详情"""
    subsystem = db.query(Subsystem).filter(Subsystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系统不存在")
    return ResponseModel(data=SubsystemResponse.model_validate(subsystem))

@router.post("/subsystems", response_model=ResponseModel)
async def create_subsystem(
    subsystem_data: SubsystemCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """创建子系统"""
    # 检查项目是否存在
    project = db.query(Project).filter(Project.id == subsystem_data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 检查编码是否重复
    existing = db.query(Subsystem).filter(Subsystem.subsystem_code == subsystem_data.subsystem_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="子系统编码已存在")
    
    subsystem = Subsystem(**subsystem_data.model_dump())
    db.add(subsystem)
    db.commit()
    db.refresh(subsystem)
    
    log_audit(db, user.id, user.username, "SUBSYSTEM_CREATE", result="success", output=f"创建子系统: {subsystem.subsystem_name}")
    return ResponseModel(data=SubsystemResponse.model_validate(subsystem))

@router.put("/subsystems/{subsystem_id}", response_model=ResponseModel)
async def update_subsystem(
    subsystem_id: int,
    subsystem_data: SubsystemUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """更新子系统"""
    subsystem = db.query(Subsystem).filter(Subsystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系统不存在")
    
    # 检查编码是否重复
    if subsystem_data.subsystem_code and subsystem_data.subsystem_code != subsystem.subsystem_code:
        existing = db.query(Subsystem).filter(
            Subsystem.subsystem_code == subsystem_data.subsystem_code,
            Subsystem.id != subsystem_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="子系统编码已存在")
    
    for key, value in subsystem_data.model_dump(exclude_unset=True).items():
        setattr(subsystem, key, value)
    
    db.commit()
    db.refresh(subsystem)
    
    log_audit(db, user.id, user.username, "SUBSYSTEM_UPDATE", result="success", output=f"更新子系统: {subsystem.subsystem_name}")
    return ResponseModel(data=SubsystemResponse.model_validate(subsystem))

@router.delete("/subsystems/{subsystem_id}", response_model=ResponseModel)
async def delete_subsystem(
    subsystem_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """删除子系统"""
    subsystem = db.query(Subsystem).filter(Subsystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系统不存在")
    
    db.delete(subsystem)
    db.commit()
    
    log_audit(db, user.id, user.username, "SUBSYSTEM_DELETE", result="success", output=f"删除子系统: {subsystem.subsystem_name}")
    return ResponseModel(message="删除成功")