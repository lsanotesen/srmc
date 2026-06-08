"""子系统与程序分类关联管理API"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from models.subsystem_group_relation import SubsystemGroupRelation
from models.subsystem import Subsystem
from models.service_group import ServiceGroup
from schemas.common import ResponseModel
from core.database import get_db
from api.dependencies import get_current_user

router = APIRouter()


@router.get("/subsystems/{subsystem_id}/groups", response_model=ResponseModel)
async def get_subsystem_groups(
    subsystem_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """获取子系统关联的所有分类"""
    # 检查子系统是否存在
    subsystem = db.query(Subsystem).filter(Subsystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系统不存在")
    
    # 获取关联的分类
    relations = db.query(SubsystemGroupRelation).filter(
        SubsystemGroupRelation.subsystem_id == subsystem_id
    ).all()
    
    return ResponseModel(data=[{
        "id": r.group.id,
        "group_name": r.group.group_name,
        "group_code": r.group.group_code
    } for r in relations])


@router.post("/subsystems/{subsystem_id}/groups", response_model=ResponseModel)
async def set_subsystem_groups(
    subsystem_id: int,
    group_ids: list[int] = Body(..., description="分类ID列表"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """设置子系统的关联分类（覆盖式更新）"""
    # 检查子系统是否存在
    subsystem = db.query(Subsystem).filter(Subsystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系统不存在")
    
    # 删除旧的关联
    db.query(SubsystemGroupRelation).filter(
        SubsystemGroupRelation.subsystem_id == subsystem_id
    ).delete()
    
    # 如果有新的分类ID，创建新的关联
    if group_ids:
        # 检查所有分类是否存在
        existing_groups = db.query(ServiceGroup).filter(
            ServiceGroup.id.in_(group_ids)
        ).all()
        if len(existing_groups) != len(group_ids):
            raise HTTPException(status_code=400, detail="部分分类ID不存在")
        
        # 创建新的关联
        for group_id in group_ids:
            relation = SubsystemGroupRelation(
                subsystem_id=subsystem_id,
                group_id=group_id
            )
            db.add(relation)
    
    db.commit()
    
    return ResponseModel(message="设置成功")


@router.post("/subsystems/{subsystem_id}/groups/add", response_model=ResponseModel)
async def add_subsystem_group(
    subsystem_id: int,
    group_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """添加子系统与分类的关联"""
    # 检查子系统是否存在
    subsystem = db.query(Subsystem).filter(Subsystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系统不存在")
    
    # 检查分类是否存在
    group = db.query(ServiceGroup).filter(ServiceGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    # 检查是否已存在关联
    existing = db.query(SubsystemGroupRelation).filter(
        SubsystemGroupRelation.subsystem_id == subsystem_id,
        SubsystemGroupRelation.group_id == group_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该关联已存在")
    
    # 创建关联
    relation = SubsystemGroupRelation(
        subsystem_id=subsystem_id,
        group_id=group_id
    )
    db.add(relation)
    db.commit()
    
    return ResponseModel(message="添加成功")


@router.delete("/subsystems/{subsystem_id}/groups/{group_id}", response_model=ResponseModel)
async def remove_subsystem_group(
    subsystem_id: int,
    group_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """移除子系统与分类的关联"""
    relation = db.query(SubsystemGroupRelation).filter(
        SubsystemGroupRelation.subsystem_id == subsystem_id,
        SubsystemGroupRelation.group_id == group_id
    ).first()
    
    if not relation:
        raise HTTPException(status_code=404, detail="关联不存在")
    
    db.delete(relation)
    db.commit()
    
    return ResponseModel(message="移除成功")
