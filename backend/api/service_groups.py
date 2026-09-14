from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from models.service_group import ServiceGroup
from schemas.service_group import ServiceGroupCreate, ServiceGroupUpdate, ServiceGroupResponse
from schemas.common import ResponseModel
from services.audit_service import log_audit
from core.database import get_db
from api.dependencies import get_current_user, require_permission

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

    # 清除项目树缓存（分组是树结构的一部分）
    from utils.cache import invalidate_projects_tree
    invalidate_projects_tree()

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

    # 清除项目树缓存
    from utils.cache import invalidate_projects_tree
    invalidate_projects_tree()

    log_audit(db, user.id, user.username, "SERVICE_GROUP_UPDATE", result="success", output=f"更新程序分类: {group.group_name}")
    return ResponseModel(data=ServiceGroupResponse.model_validate(group))

@router.delete("/service-groups/{group_id}", response_model=ResponseModel)
async def delete_service_group(
    group_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """删除程序分类"""
    from models.app_service import AppService
    
    group = db.query(ServiceGroup).filter(ServiceGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="程序分类不存在")
    
    # 检查是否有服务引用该分类
    service_count = db.query(AppService).filter(AppService.group_id == group_id).count()
    
    # 将关联服务的 group_id 设为 NULL（解除关联）
    if service_count > 0:
        db.query(AppService).filter(AppService.group_id == group_id).update({AppService.group_id: None})
        db.commit()
    
    # 删除分类
    db.delete(group)
    db.commit()

    # 清除项目树缓存
    from utils.cache import invalidate_projects_tree
    invalidate_projects_tree()

    log_audit(db, user.id, user.username, "SERVICE_GROUP_DELETE", result="success", output=f"删除程序分类: {group.group_name}")
    return ResponseModel(message=f"删除成功（已解除 {service_count} 个服务的关联）")

@router.post("/service-groups/cleanup-duplicates", response_model=ResponseModel)
async def cleanup_duplicate_groups(
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    """清理重复的程序分类（保留 ID 最小的，将关联服务移到保留的分类）"""
    import traceback
    from models.app_service import AppService
    from sqlalchemy import func, text
    
    try:
        
        # 查找重复的 group_name
        duplicate_names = db.query(ServiceGroup.group_name)\
            .group_by(ServiceGroup.group_name)\
            .having(func.count(ServiceGroup.id) > 1)\
            .all()
        
        deleted_count = 0
        merged_count = 0
        
        for item in duplicate_names:
            group_name = item[0]  # 获取 group_name 值
            # 按 ID 排序，保留 ID 最小的
            groups = db.query(ServiceGroup).filter(ServiceGroup.group_name == group_name)\
                .order_by(ServiceGroup.id).all()
            
            if len(groups) <= 1:
                continue
            
            keep_group = groups[0]  # 保留的分类
            duplicate_groups = groups[1:]  # 需要删除的分类
            
            for dup_group in duplicate_groups:
                # 将重复分类的关联服务移到保留的分类
                service_count = db.query(AppService).filter(AppService.group_id == dup_group.id).count()
                if service_count > 0:
                    # 使用 SQL 直接更新
                    db.execute(text(
                        "UPDATE app_services SET group_id = :keep_id WHERE group_id = :dup_id"
                    ), {"keep_id": keep_group.id, "dup_id": dup_group.id})
                    merged_count += service_count
                
                # 删除重复分类
                db.delete(dup_group)
                deleted_count += 1
            
            db.commit()
        
        # 清除缓存
        from utils.cache import invalidate_projects_tree
        invalidate_projects_tree()
        
        log_audit(db, user.id, user.username, "SERVICE_GROUP_CLEANUP", 
                  result="success", 
                  output=f"清理重复分类: 删除 {deleted_count} 个重复分类, 合并 {merged_count} 个服务")
        
        return ResponseModel(message=f"清理完成：删除 {deleted_count} 个重复分类，合并 {merged_count} 个服务")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")
