from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from models.audit_log import AuditLog
from models.app_service import AppService
from models.project import Project
from models.subsystem import Subsystem
from schemas.common import ResponseModel
from core.database import get_db
from api.dependencies import require_permission
from services.data_scope_service import DataScopeService

router = APIRouter()

# 服务操作记录关注的操作类型（启动/停止/重启/发布/编辑）
SERVICE_OPERATION_ACTIONS = [
    "SERVICE_START", "SERVICE_STOP", "SERVICE_RESTART",
    "SERVICE_CREATE", "SERVICE_UPDATE", "SERVICE_DELETE",
    "SERVICE_IMPORT", "IMPORT_REVERT",
]

def log_to_dict(log: AuditLog):
    return {
        "id": log.id,
        "user_id": log.user_id,
        "username": log.username,
        "action": log.action,
        "service_id": log.service_id,
        "service_code": log.service_code,
        "server_id": log.server_id,
        "ip": log.ip,
        "project_id": log.project_id,
        "subsystem_id": log.subsystem_id,
        "result": log.result,
        "output": log.output,
        "duration": log.duration,
        "created_at": log.created_at.isoformat() if log.created_at else None
    }

def _apply_audit_data_scope(query, db: Session, user):
    """复用 DataScope 收敛非超管的操作记录可见范围。

    - 有权限项目的记录（AppService 操作）按 project_id 过滤；
    - 无项目归属的记录（legacy Service 等）改按 organization_id 收敛到当前用户组织，
      避免跨组织查看；
    - 超级管理员不限制，保持全量访问。
    """
    if DataScopeService._is_super_admin(user):
        return query

    allowed_project_ids = DataScopeService.get_user_project_ids(db, user)
    # 无项目归属的记录只能看到本组织的
    no_project_scope = and_(
        AuditLog.project_id.is_(None),
        AuditLog.organization_id == user.organization_id,
    )
    if allowed_project_ids:
        return query.filter(
            or_(AuditLog.project_id.in_(allowed_project_ids), no_project_scope)
        )
    return query.filter(no_project_scope)

@router.get("/audit/logs", response_model=ResponseModel)
async def get_audit_logs_short(
    limit: int = Query(5, ge=1, le=100),
    db: Session = Depends(get_db),
    user = Depends(require_permission("audit:view"))
):
    # 复用 DataScope：按项目权限 + 组织维度收敛可见范围
    query = _apply_audit_data_scope(db.query(AuditLog), db, user)

    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    logs_dict = [log_to_dict(log) for log in logs]
    return ResponseModel(data=logs_dict)

@router.get("/audit", response_model=ResponseModel)
async def get_audit_logs(
    user_id: int = Query(None),
    username: str = Query(None),
    action: str = Query(None),
    service_code: str = Query(None),
    service_id: int = Query(None),
    project_id: int = Query(None),
    subsystem_id: int = Query(None),
    result: str = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user = Depends(require_permission("audit:view"))
):
    # 复用 DataScope：按项目权限 + 组织维度收敛可见范围
    query = _apply_audit_data_scope(db.query(AuditLog), db, user)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if username:
        query = query.filter(AuditLog.username.like(f"%{username}%"))
    if action:
        # 支持单个 action 或逗号分隔的多个 action
        actions = [item.strip() for item in action.split(',') if item.strip()]
        if len(actions) > 1:
            query = query.filter(AuditLog.action.in_(actions))
        elif len(actions) == 1:
            query = query.filter(AuditLog.action == actions[0])
    if service_code:
        query = query.filter(AuditLog.service_code == service_code)
    if service_id:
        # 对于 service_id 参数，必须校验用户是否对服务所属项目有访问权限
        # AppService 属于某个 Project，因此需通过 project_id 进行过滤
        service = db.query(AppService).filter(AppService.id == service_id).first()
        if service:
            # 服务存在，检查用户是否对该服务所属项目有权限
            if not DataScopeService._is_super_admin(user):
                allowed_project_ids = DataScopeService.get_user_project_ids(db, user)
                if allowed_project_ids and service.project_id not in allowed_project_ids:
                    # 用户无该项目权限，只能查到 project_id 为空的历史记录
                    # 为避免逻辑复杂，直接限制 project_id 条件
                    query = query.filter(
                        or_(
                            AuditLog.project_id.is_(None),
                            AuditLog.project_id.in_(allowed_project_ids),
                        )
                    )
                else:
                    # 用户有项目权限，允许查询该服务记录（包括 project_id 为空的历史记录）
                    query = query.filter(
                        or_(
                            AuditLog.service_id == service_id,
                            AuditLog.project_id.is_(None),
                        )
                    )
            else:
                # 超级管理员，允许查询所有记录
                query = query.filter(AuditLog.service_id == service_id)
        else:
            # 服务不存在，返回空结果
            query = query.filter(AuditLog.service_id == service_id)
    if project_id:
        query = query.filter(AuditLog.project_id == project_id)
    if subsystem_id:
        # 对于 subsystem_id 参数，必须校验用户是否对子系统所属项目有访问权限
        # 子系统属于某个项目，因此需通过 project_id 进行过滤
        subsystem = db.query(Subsystem).filter(Subsystem.id == subsystem_id).first()
        if subsystem:
            # 子系统存在，检查用户是否对该子系统所属项目有权限
            if not DataScopeService._is_super_admin(user):
                allowed_project_ids = DataScopeService.get_user_project_ids(db, user)
                if allowed_project_ids and subsystem.project_id not in allowed_project_ids:
                    # 用户无该项目权限，只能查到 project_id 为空的历史记录
                    query = query.filter(
                        or_(
                            and_(
                                AuditLog.subsystem_id == subsystem_id,
                                AuditLog.project_id.is_(None),
                            ),
                            and_(
                                AuditLog.project_id.in_(allowed_project_ids),
                                AuditLog.project_id.is_(None),
                            ),
                        )
                    )
                    # 为避免逻辑冲突，直接限制 project_id 条件
                    query = query.filter(
                        or_(
                            AuditLog.project_id.is_(None),
                            AuditLog.project_id.in_(allowed_project_ids),
                        )
                    )
                else:
                    # 用户有项目权限，允许查询该子系统记录（包括 project_id 为空的历史记录）
                    query = query.filter(
                        or_(
                            AuditLog.subsystem_id == subsystem_id,
                            AuditLog.project_id.is_(None),
                        )
                    )
            else:
                # 超级管理员，允许查询所有记录
                query = query.filter(AuditLog.subsystem_id == subsystem_id)
        else:
            # 子系统不存在，返回空结果
            query = query.filter(AuditLog.subsystem_id == subsystem_id)
    if result:
        query = query.filter(AuditLog.result == result)
    if start_time:
        query = query.filter(AuditLog.created_at >= start_time)
    if end_time:
        query = query.filter(AuditLog.created_at <= end_time)

    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    logs_dict = [log_to_dict(log) for log in logs]

    # 批量关联项目/子系统/服务名称，避免 N+1 查询
    _attach_names(db, logs_dict)

    return ResponseModel(data={
        "items": logs_dict,
        "total": total,
        "page": page,
        "limit": limit
    })


def _attach_names(db: Session, logs: list):
    """批量填充 project_name / subsystem_name / service_name，避免逐条查询。"""
    if not logs:
        return

    project_ids = {l["project_id"] for l in logs if l.get("project_id")}
    subsystem_ids = {l["subsystem_id"] for l in logs if l.get("subsystem_id")}
    service_ids = {l["service_id"] for l in logs if l.get("service_id")}

    project_map = {}
    if project_ids:
        rows = db.query(Project.id, Project.name).filter(Project.id.in_(project_ids)).all()
        project_map = {pid: name for pid, name in rows}

    subsystem_map = {}
    if subsystem_ids:
        rows = db.query(Subsystem.id, Subsystem.subsystem_name).filter(
            Subsystem.id.in_(subsystem_ids)
        ).all()
        subsystem_map = {sid: name for sid, name in rows}

    service_map = {}
    if service_ids:
        rows = db.query(AppService.id, AppService.func_desc).filter(
            AppService.id.in_(service_ids)
        ).all()
        service_map = {sid: name for sid, name in rows}

    for log in logs:
        log["project_name"] = project_map.get(log.get("project_id"))
        log["subsystem_name"] = subsystem_map.get(log.get("subsystem_id"))
        log["service_name"] = service_map.get(log.get("service_id"))
