from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from models.subsystem import Subsystem
from models.project import Project
from schemas.subsystem import SubsystemCreate, SubsystemUpdate, SubsystemResponse
from schemas.common import ResponseModel
from services.audit_service import log_audit
from core.database import get_db
from api.dependencies import require_permission
from api.permission_dependencies import assert_project_access, get_visible_project_ids

router = APIRouter()

@router.get("/subsystems", response_model=ResponseModel)
async def list_subsystems(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    project_id: int = Query(None, description="项目ID"),
    keyword: str = Query(None, description="搜索关键字"),
    db: Session = Depends(get_db),
    user = Depends(require_permission("project_view"))
):
    """获取子系统列表"""
    # 指定项目时校验该项目的数据范围；未指定时仅返回当前用户可见项目下的子系统
    if project_id:
        assert_project_access(db, user, project_id)

    # 先确定数据范围内的基础集合（始终收敛到可见项目，不受项目/关键字筛选影响）
    scope_query = db.query(Subsystem, Project).outerjoin(Project, Subsystem.project_id == Project.id)
    visible_project_ids = get_visible_project_ids(db, user)
    if visible_project_ids is not None:
        scope_query = scope_query.filter(Subsystem.project_id.in_(visible_project_ids))
    # total_all：数据范围内（可见项目下）的子系统总数
    total_all = scope_query.count()

    query = scope_query
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
        "total_all": total_all,
        "page": page,
        "size": size
    })

@router.get("/subsystems/{subsystem_id}", response_model=ResponseModel)
async def get_subsystem(
    subsystem_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_permission("project_view"))
):
    """获取子系统详情"""
    subsystem = db.query(Subsystem).filter(Subsystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系统不存在")
    assert_project_access(db, user, subsystem.project_id, detail="无权访问该子系统")
    return ResponseModel(data=SubsystemResponse.model_validate(subsystem))

@router.post("/subsystems", response_model=ResponseModel)
async def create_subsystem(
    subsystem_data: SubsystemCreate,
    db: Session = Depends(get_db),
    user = Depends(require_permission("project_manage"))
):
    """创建子系统"""
    # 检查项目是否存在
    project = db.query(Project).filter(Project.id == subsystem_data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 数据范围校验：无该项目权限不能创建
    assert_project_access(db, user, subsystem_data.project_id, detail="无权在该项目下创建子系统")
    
    # 检查编码在项目内是否重复（subsystem_code 从全局唯一改为项目内唯一）
    existing = db.query(Subsystem).filter(
        Subsystem.project_id == subsystem_data.project_id,
        Subsystem.subsystem_code == subsystem_data.subsystem_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该项目下子系统编码已存在")
    
    subsystem = Subsystem(**subsystem_data.model_dump())
    db.add(subsystem)
    db.commit()
    db.refresh(subsystem)

    # 清除项目树缓存
    from utils.cache import invalidate_projects_tree
    invalidate_projects_tree()

    log_audit(db, user.id, user.username, "SUBSYSTEM_CREATE", result="success", output=f"创建子系统: {subsystem.subsystem_name}")
    return ResponseModel(data=SubsystemResponse.model_validate(subsystem))

@router.put("/subsystems/{subsystem_id}", response_model=ResponseModel)
async def update_subsystem(
    subsystem_id: int,
    subsystem_data: SubsystemUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_permission("project_manage"))
):
    """更新子系统"""
    subsystem = db.query(Subsystem).filter(Subsystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系统不存在")

    # 数据范围校验：按子系统实际归属项目判断（SubsystemUpdate 不含 project_id，无法转移项目）
    assert_project_access(db, user, subsystem.project_id, detail="无权修改该子系统")
    
    # 检查编码在项目内是否重复
    if subsystem_data.subsystem_code and subsystem_data.subsystem_code != subsystem.subsystem_code:
        existing = db.query(Subsystem).filter(
            Subsystem.project_id == subsystem.project_id,
            Subsystem.subsystem_code == subsystem_data.subsystem_code,
            Subsystem.id != subsystem_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="该项目下子系统编码已存在")
    
    for key, value in subsystem_data.model_dump(exclude_unset=True).items():
        setattr(subsystem, key, value)

    db.commit()
    db.refresh(subsystem)

    # 清除项目树缓存
    from utils.cache import invalidate_projects_tree
    invalidate_projects_tree()

    log_audit(db, user.id, user.username, "SUBSYSTEM_UPDATE", result="success", output=f"更新子系统: {subsystem.subsystem_name}")
    return ResponseModel(data=SubsystemResponse.model_validate(subsystem))

@router.delete("/subsystems/{subsystem_id}", response_model=ResponseModel)
async def delete_subsystem(
    subsystem_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_permission("project_manage"))
):
    """删除子系统"""
    subsystem = db.query(Subsystem).filter(Subsystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系统不存在")

    # 数据范围校验：只能删除自己有权限项目下的子系统
    assert_project_access(db, user, subsystem.project_id, detail="无权删除该子系统")
    
    db.delete(subsystem)
    db.commit()

    # 清除项目树缓存
    from utils.cache import invalidate_projects_tree
    invalidate_projects_tree()

    log_audit(db, user.id, user.username, "SUBSYSTEM_DELETE", result="success", output=f"删除子系统: {subsystem.subsystem_name}")
    return ResponseModel(message="删除成功")