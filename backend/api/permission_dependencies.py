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
