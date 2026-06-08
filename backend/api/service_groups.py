from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from models.service_group import ServiceGroup
from schemas.service_group import ServiceGroupCreate, ServiceGroupUpdate, ServiceGroupResponse
from schemas.common import ResponseModel
from services.audit_service import log_audit
from core.database import get_db
from api.dependencies import get_current_user

router = APIRouter()

@router.get("/service-groups", response_model=ResponseModel)
async def list_service_groups(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None, description="搜索关键字"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """获取程序分类列表（全局统一分类）"""
    query = db.query(ServiceGroup)
    
    if keyword:
        query = query.filter(
            (ServiceGroup.group_name.like(f"%{keyword}%")) |
            (ServiceGroup.group_code.like(f"%{keyword}%"))
        )
    
    total = query.count()
    groups = query.order_by(ServiceGroup.display_order, ServiceGroup.id)\
        .offset((page - 1) * size).limit(size).all()
    
    return ResponseModel(data={
        "items": [ServiceGroupResponse.model_validate(g) for g in groups],
        "total": total,
        "page": page,
        "size": size
    })

@router.get("/service-groups/all", response_model=ResponseModel)
async def get_all_service_groups(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """获取所有程序分类（用于下拉选择）"""
    groups = db.query(ServiceGroup).order_by(ServiceGroup.display_order, ServiceGroup.id).all()
    return ResponseModel(data=[{
        "id": g.id,
        "group_name": g.group_name,
        "group_code": g.group_code
    } for g in groups])

@router.get("/service-groups/{group_id}", response_model=ResponseModel)
async def get_service_group(
    group_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """获取程序分类详情"""
    group = db.query(ServiceGroup).filter(ServiceGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="程序分类不存在")
    return ResponseModel(data=ServiceGroupResponse.model_validate(group))

@router.post("/service-groups", response_model=ResponseModel)
async def create_service_group(
    group_data: ServiceGroupCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """创建程序分类（全局统一分类）"""
    # 检查编码是否重复（全局唯一）
    existing = db.query(ServiceGroup).filter(
        ServiceGroup.group_code == group_data.group_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="分类编码已存在")
    
    group = ServiceGroup(
        group_name=group_data.group_name,
        group_code=group_data.group_code,
        display_order=group_data.display_order or 0,
        description=group_data.description
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    
    log_audit(db, user.id, user.username, "SERVICE_GROUP_CREATE", result="success", output=f"创建程序分类: {group.group_name}")
    return ResponseModel(data=ServiceGroupResponse.model_validate(group))

@router.put("/service-groups/{group_id}", response_model=ResponseModel)
async def update_service_group(
    group_id: int,
    group_data: ServiceGroupUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """更新程序分类"""
    group = db.query(ServiceGroup).filter(ServiceGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="程序分类不存在")
    
    # 检查编码是否重复（全局唯一）
    if group_data.group_code and group_data.group_code != group.group_code:
        existing = db.query(ServiceGroup).filter(
            ServiceGroup.group_code == group_data.group_code,
            ServiceGroup.id != group_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="分类编码已存在")
    
    if group_data.group_name:
        group.group_name = group_data.group_name
    if group_data.group_code:
        group.group_code = group_data.group_code
    if group_data.display_order is not None:
        group.display_order = group_data.display_order
    if group_data.description is not None:
        group.description = group_data.description
    
    db.commit()
    db.refresh(group)
    
    log_audit(db, user.id, user.username, "SERVICE_GROUP_UPDATE", result="success", output=f"更新程序分类: {group.group_name}")
    return ResponseModel(data=ServiceGroupResponse.model_validate(group))

@router.delete("/service-groups/{group_id}", response_model=ResponseModel)
async def delete_service_group(
    group_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """删除程序分类"""
    from models.service import AppService
    
    # 检查是否有服务引用该分类
    service_count = db.query(AppService).filter(AppService.group_id == group_id).count()
    if service_count > 0:
        raise HTTPException(status_code=400, detail=f"该分类下有 {service_count} 个服务，无法删除")
    
    group = db.query(ServiceGroup).filter(ServiceGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="程序分类不存在")
    
    db.delete(group)
    db.commit()
    
    log_audit(db, user.id, user.username, "SERVICE_GROUP_DELETE", result="success", output=f"删除程序分类: {group.group_name}")
    return ResponseModel(message="删除成功")
