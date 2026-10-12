from typing import Optional
from functools import wraps
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from models.user import User
from core.database import get_db
from services.unified_permission_service import UnifiedPermissionService, ResourceContext


security = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """获取当前登录用户"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    from jose import jwt
    from core.config import settings
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="无效的Token")
    except Exception:
        raise HTTPException(status_code=401, detail="Token已过期或无效")

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


def require_read_permission(resource_type: str, get_project_id=None):
    """
    读取权限依赖 - 仅检查 DataScope + RBAC
    get_project_id: 可调用函数，从请求中提取 project_id
    """
    async def checker(
        request: Request,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        project_id = None
        if get_project_id:
            project_id = get_project_id(request)

        if project_id:
            context = ResourceContext(resource_type, 0, project_id)
            if not UnifiedPermissionService.has_read_permission(db, user.id, context):
                raise HTTPException(status_code=403, detail="无访问权限")

        return user
    return checker


def require_operation_permission(resource_type: str, action: str, get_project_id=None):
    """
    操作权限依赖 - 检查 DataScope + RBAC + ProjectMember
    get_project_id: 可调用函数，从请求中提取 project_id
    """
    async def checker(
        request: Request,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        project_id = None
        resource_id = 0
        if get_project_id:
            result = get_project_id(request)
            if isinstance(result, tuple):
                resource_id, project_id = result
            else:
                project_id = result

        context = ResourceContext(resource_type, resource_id, project_id)
        if not UnifiedPermissionService.has_operation_permission(db, user.id, context, action):
            raise HTTPException(status_code=403, detail="无操作权限")

        return user
    return checker


def get_project_id_from_path(param_name: str = "project_id"):
    """从路径参数中提取 project_id 的辅助函数"""
    def extractor(request: Request):
        path_params = request.path_params
        if param_name in path_params:
            return int(path_params[param_name])
        return None
    return extractor


def get_project_id_from_body(param_name: str = "project_id"):
    """从请求体中提取 project_id 的辅助函数"""
    def extractor(request: Request):
        import json
        try:
            if hasattr(request, 'body'):
                body = json.loads(request.body) if isinstance(request.body, bytes) else {}
                return body.get(param_name)
        except Exception:
            pass
        return None
    return extractor


def apply_data_scope_filter(db: Session, user: User, query, resource_type: str = None):
    """对查询应用数据权限过滤"""
    return UnifiedPermissionService.apply_data_scope(db, user.id, query, resource_type)


def get_visible_project_ids(db: Session, user: User):
    """返回用户可见的项目ID集合（复用 DataScopeService）。

    超管返回 None，表示不限制；其余用户返回 set。与 /api/services 列表口径一致。
    """
    from services.data_scope_service import DataScopeService

    if DataScopeService._is_super_admin(user):
        return None
    return set(DataScopeService.get_user_project_ids(db, user))


def user_can_access_project(db: Session, user: User, project_id) -> bool:
    """判断用户是否可访问指定项目（复用 DataScopeService）。"""
    visible = get_visible_project_ids(db, user)
    return visible is None or project_id in visible


def assert_project_access(db: Session, user: User, project_id, detail: str = "无权访问该项目"):
    """项目数据范围校验，不通过则抛 403。"""
    if project_id is None or not user_can_access_project(db, user, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def assert_high_risk_capability(db: Session, user: User, project_id, capability: str, detail: str = None):
    """项目级高风险能力校验（WebShell/Root/SFTP/删除/发布/备份恢复）。

    仅"通过项目共享获得访问"的用户，需在共享记录中被明确勾选对应高风险能力；
    超管/组织级管理员/本部门用户/项目成员不受此额外限制（由系统权限码控制）。
    """
    from models.project import Project
    from services.data_scope_service import DataScopeService

    if project_id is None:
        return
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return
    if not DataScopeService.has_high_risk_grant(db, user, project, capability):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail or "该项目共享未授予对应高风险操作权限",
        )


def assert_project_write_capability(db: Session, user: User, project_id, detail: str = None):
    """项目写操作校验（启停/重启/配置修改等）。

    仅通过 PUBLIC 可见或项目共享获得访问、且不具备固有操作权的用户，其共享级别必须是
    "读写"（EDIT/MANAGE）；"只读"共享或无共享记录不得执行写操作，公开可见也不自动赋予写权限。
    本部门用户/项目成员/管理员拥有固有操作权，不受此额外限制（由系统权限码控制）。
    """
    from models.project import Project
    from models.project_permission import is_write_permission
    from services.data_scope_service import DataScopeService

    if project_id is None:
        return
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return
    if DataScopeService.has_intrinsic_project_authority(db, user, project):
        return
    shares = DataScopeService.get_applicable_shares(db, user, project.id)
    if not any(is_write_permission(s.permission) for s in shares):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail or "该项目共享为只读，不能执行写操作",
        )


def assert_project_manage_capability(db: Session, user: User, project_id, detail: str = None):
    """项目管理操作校验（修改项目基本信息/可见范围、删除项目等）。

    与共享管理鉴权口径一致：仅通过项目共享或公开可见获得访问的用户不具备项目管理权，
    即便拥有 project:* 系统权限码也不得管理该项目；须对项目拥有"固有操作权"
    （超管 / 本组织组织级管理员 / 本部门用户 / 项目成员）。
    """
    from models.project import Project
    from services.data_scope_service import DataScopeService

    if project_id is None:
        return
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return
    if DataScopeService.has_intrinsic_project_authority(db, user, project):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail or "仅通过共享或公开可见获得访问，不能管理该项目",
    )


def assert_service_access(db: Session, user: User, service_id: int, service=None):
    """服务数据范围校验：按服务所属项目判断，返回服务对象。

    服务不存在抛 404（保持原有语义），无权限抛 403。
    """
    from models.app_service import AppService

    if service is None:
        service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="服务不存在")
    if not user_can_access_project(db, user, service.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该服务")
    return service


def assert_services_access(db: Session, user: User, service_ids):
    """批量校验：逐个验证 service_id 的数据范围。

    只要存在一个越权服务即整体抛 403，避免批量接口绕过权限。
    不存在的 id 按原有语义忽略。返回命中的服务对象列表。
    """
    from models.app_service import AppService

    if not service_ids:
        return []
    services = db.query(AppService).filter(AppService.id.in_(list(service_ids))).all()
    visible = get_visible_project_ids(db, user)
    if visible is not None:
        for svc in services:
            if svc.project_id not in visible:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问部分服务")
    return services


def _organization_scoped_out(user: User, organization_id) -> bool:
    """组织维度收敛规则（与 DataScope 既有"同组织"规则一致）。

    - 超管始终放行；
    - 组织已知且与当前用户组织不一致 -> 越权；
    - 组织未知（NULL）时放行，避免误伤未归属组织的存量数据。
    """
    from services.data_scope_service import DataScopeService

    if DataScopeService._is_super_admin(user):
        return False
    if organization_id is None:
        return False
    return organization_id != getattr(user, "organization_id", None)


def assert_legacy_service_access(db: Session, user: User, service_id: int):
    """遗留监控服务（models.service.Service）的数据范围校验。

    遗留 services 表没有 project_id，只能按所属 Server 的组织维度收敛：
    - 超管放行；
    - Server 组织已知且与当前用户组织不一致 -> 403；
    - Server 组织未知（NULL）或无归属 Server 时按原行为放行，避免误伤存量数据。
    """
    from models.service import Service
    from models.server import Server

    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="服务不存在")
    server = db.query(Server).filter(Server.id == service.server_id).first() if service.server_id else None
    if _organization_scoped_out(user, server.organization_id if server else None):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该服务")
    return service


def assert_legacy_services_access(db: Session, user: User, service_ids):
    """批量校验遗留服务：逐个验证，任一越权即整体抛 403。"""
    for sid in service_ids or []:
        assert_legacy_service_access(db, user, sid)


def filter_legacy_services_query(db: Session, user: User, query):
    """对遗留 Service 查询按组织维度过滤，口径与 assert_legacy_service_access 一致。

    超管不过滤；非超管排除"所属 Server 组织已知且与用户组织不一致"的服务，
    Server 组织未知或服务无归属 Server 的记录保持可见。
    """
    from models.service import Service
    from models.server import Server
    from services.data_scope_service import DataScopeService
    from sqlalchemy import select, or_

    if DataScopeService._is_super_admin(user):
        return query

    excluded_conditions = [Server.organization_id.isnot(None)]
    user_org = getattr(user, "organization_id", None)
    if user_org is not None:
        excluded_conditions.append(Server.organization_id != user_org)
    excluded_server_ids = select(Server.id).where(*excluded_conditions)

    return query.filter(
        or_(Service.server_id.is_(None), ~Service.server_id.in_(excluded_server_ids))
    )


def assert_server_access(db: Session, user: User, server_id: int):
    """服务器数据范围校验，复用 api.server 现有 _scope_server_query 规则。

    超管可见全部；普通用户仅可见本组织服务器；无组织普通用户不可见任何服务器。
    越权与不存在统一返回 404，避免泄露服务器是否存在。
    """
    from api.server import _scope_server_query
    from models.server import Server

    server = _scope_server_query(db.query(Server), user).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="服务器不存在")
    return server
