from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from models.organization import Organization
from models.department import Department
from models.user import User
from schemas.common import ResponseModel
from core.database import get_db
from api.dependencies import get_current_user
from services.audit_service import log_audit

router = APIRouter()


class OrgCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    logo: Optional[str] = None
    status: Optional[int] = 1


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None
    status: Optional[int] = None


class DeptCreate(BaseModel):
    organization_id: int
    parent_id: Optional[int] = None
    name: str
    code: str
    leader_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[int] = 1


class DeptUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    organization_id: Optional[int] = None
    leader_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[int] = None
    sort_order: Optional[int] = None


@router.get("/organizations", response_model=ResponseModel)
async def list_organizations(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Organization)
    if keyword:
        query = query.filter(Organization.name.like(f"%{keyword}%"))
    total = query.count()
    orgs = query.offset((page - 1) * size).limit(size).all()
    result = [
        {
            "id": o.id,
            "name": o.name,
            "code": o.code,
            "logo": o.logo,
            "description": o.description,
            "status": o.status,
            "created_at": str(o.created_at) if o.created_at else None,
        }
        for o in orgs
    ]
    return ResponseModel(data={"items": result, "total": total, "page": page, "size": size})


@router.post("/organizations", response_model=ResponseModel)
async def create_organization(
    data: OrgCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="仅超级管理员可创建组织")

    existing = db.query(Organization).filter(Organization.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="组织编码已存在")

    org = Organization(
        name=data.name,
        code=data.code,
        description=data.description,
        logo=data.logo,
        status=data.status or 1,
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    # 自动创建默认根部门，确保每个组织至少有一个部门
    from models.department import Department
    default_dept = Department(
        name="根部门",
        code="ROOT",
        organization_id=org.id,
        parent_id=None,
        description="默认根部门",
        status=1,
        sort_order=0,
    )
    db.add(default_dept)
    db.commit()

    log_audit(db, user.id, user.username, "ORG_CREATE", result="success", output=f"创建组织: {data.name}")
    return ResponseModel(data={"id": org.id, "name": org.name, "code": org.code})


@router.put("/organizations/{org_id}", response_model=ResponseModel)
async def update_organization(
    org_id: int,
    data: OrgUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="仅超级管理员可修改组织")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    if data.name is not None:
        org.name = data.name
    if data.description is not None:
        org.description = data.description
    if data.logo is not None:
        org.logo = data.logo
    if data.status is not None:
        org.status = data.status

    db.commit()
    log_audit(db, user.id, user.username, "ORG_UPDATE", result="success", output=f"更新组织: {org.name}")
    return ResponseModel(data={"id": org.id, "name": org.name})


@router.delete("/organizations/{org_id}", response_model=ResponseModel)
async def delete_organization(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="仅超级管理员可删除组织")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    # 清理组织下的部门（级联删除子部门和关联数据）
    from models.department import Department
    depts = db.query(Department).filter(Department.organization_id == org_id).all()
    for dept in depts:
        # 清理部门关联的用户
        from models.user import User
        db.query(User).filter(User.department_id == dept.id).update({"department_id": None})

    # 删除所有部门（CASCADE 处理子部门和 leader 关系）
    db.query(Department).filter(Department.organization_id == org_id).delete(synchronize_session=False)

    # 清理组织下用户的 organization_id
    from models.user import User
    db.query(User).filter(User.organization_id == org_id).update({"organization_id": None})

    db.delete(org)
    db.commit()
    log_audit(db, user.id, user.username, "ORG_DELETE", result="success", output=f"删除组织: {org.name}")
    return ResponseModel(message="删除成功")


@router.get("/organizations/{org_id}/departments/tree", response_model=ResponseModel)
async def get_department_tree(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    depts = db.query(Department).filter(Department.organization_id == org_id).all()

    # Build user lookup
    user_ids = set(d.leader_id for d in depts if d.leader_id)
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: u for u in users}

    def build_tree(parent_id=None):
        result = []
        children = [d for d in depts if d.parent_id == parent_id]
        for dept in children:
            leader = user_map.get(dept.leader_id) if dept.leader_id else None
            node = {
                "id": dept.id,
                "organization_id": dept.organization_id,
                "parent_id": dept.parent_id,
                "name": dept.name,
                "code": dept.code,
                "leader_id": dept.leader_id,
                "leader_name": leader.job_title or leader.username if leader else None,
                "description": dept.description,
                "status": dept.status,
                "sort_order": dept.sort_order,
                "children": build_tree(dept.id),
            }
            result.append(node)
        return result

    tree = build_tree()
    return ResponseModel(data=tree)


@router.post("/departments", response_model=ResponseModel)
async def create_department(
    data: DeptCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org = db.query(Organization).filter(Organization.id == data.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    if data.parent_id:
        parent = db.query(Department).filter(Department.id == data.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父部门不存在")

    existing = db.query(Department).filter(
        Department.organization_id == data.organization_id,
        Department.code == data.code,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="部门编码已存在")

    dept = Department(
        organization_id=data.organization_id,
        parent_id=data.parent_id,
        name=data.name,
        code=data.code,
        leader_id=data.leader_id,
        description=data.description,
        status=data.status or 1,
    )
    db.add(dept)
    db.commit()

    log_audit(db, user.id, user.username, "DEPT_CREATE", result="success", output=f"创建部门: {data.name}")
    return ResponseModel(data={"id": dept.id, "name": dept.name, "code": dept.code})


@router.put("/departments/{dept_id}", response_model=ResponseModel)
async def update_department(
    dept_id: int,
    data: DeptUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")

    old_org_id = dept.organization_id
    new_org_id = data.organization_id if data.organization_id is not None else old_org_id

    # 处理组织变更
    if new_org_id != old_org_id:
        new_org = db.query(Organization).filter(Organization.id == new_org_id).first()
        if not new_org:
            raise HTTPException(status_code=400, detail="目标组织不存在")

        # 检查新组织下是否有相同编码的部门
        existing_code = db.query(Department).filter(
            Department.organization_id == new_org_id,
            Department.code == dept.code,
            Department.id != dept_id,
        ).first()
        if existing_code:
            raise HTTPException(status_code=400, detail="目标组织下已存在相同编码的部门")

        # 级联更新所有子部门的 organization_id
        def get_child_depts(parent_id):
            children = db.query(Department).filter(Department.parent_id == parent_id).all()
            result = []
            for child in children:
                result.append(child)
                result.extend(get_child_depts(child.id))
            return result

        child_depts = get_child_depts(dept_id)
        for child in child_depts:
            child.organization_id = new_org_id

        # 如果 parent_id 在新组织下不存在，清空 parent_id
        if dept.parent_id:
            parent = db.query(Department).filter(Department.id == dept.parent_id).first()
            if not parent or parent.organization_id != new_org_id:
                dept.parent_id = None

        dept.organization_id = new_org_id

    if data.name is not None:
        dept.name = data.name
    if data.code is not None:
        dept.code = data.code
    if data.leader_id is not None:
        dept.leader_id = data.leader_id
    if data.description is not None:
        dept.description = data.description
    if data.status is not None:
        dept.status = data.status
    if data.sort_order is not None:
        dept.sort_order = data.sort_order

    db.commit()
    log_audit(db, user.id, user.username, "DEPT_UPDATE", result="success", output=f"更新部门: {dept.name}")
    return ResponseModel(data={"id": dept.id, "name": dept.name})


@router.delete("/departments/{dept_id}", response_model=ResponseModel)
async def delete_department(
    dept_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")

    has_children = db.query(Department).filter(Department.parent_id == dept_id).count()
    if has_children > 0:
        raise HTTPException(status_code=400, detail="部门下还有子部门，无法删除")

    user_count = db.query(User).filter(User.department_id == dept_id).count()
    if user_count > 0:
        raise HTTPException(status_code=400, detail="部门下还有用户，无法删除")

    db.delete(dept)
    db.commit()
    log_audit(db, user.id, user.username, "DEPT_DELETE", result="success", output=f"删除部门: {dept.name}")
    return ResponseModel(message="删除成功")
