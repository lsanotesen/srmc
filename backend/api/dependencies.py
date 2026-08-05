from fastapi import Depends, HTTPException, status, Header, Request
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from models.user import User
from core.database import get_db
from core.config import settings
from services.permission_service import PermissionService


def get_current_user(db: Session = Depends(get_db), authorization: str = Header(None)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not authorization:
        raise credentials_exception
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer" or not token:
            raise credentials_exception
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except (ValueError, JWTError):
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


# 旧权限码到新权限码的映射
LEGACY_TO_NEW_PERMISSIONS = {
    # 服务相关
    "service_view": ["service:view", "container:view", "host:view"],
    "service_operate": ["service:start", "service:stop", "service:restart", "container:start", "container:stop", "container:restart"],
    "service_manage": ["service:deploy", "service:edit-config"],
    "service_control": ["service:start", "service:stop", "service:restart", "container:start", "container:stop", "container:restart"],
    # 项目相关
    "project_view": ["project:view"],
    "project_manage": ["project:add", "project:edit", "project:delete", "project:share"],
    # 其他
    "webshell": ["webshell:login", "container:exec"],
    "sql_execute": ["service:view"],
    "sql_read": ["service:view"],
    "log_view": ["log:view"],
    "log_download": ["log:download"],
    "import": ["service:deploy"],
    "export": ["log:download"],
    "audit_view": ["audit:view"],
    "user_manage": ["user:view", "user:add", "user:edit", "user:delete", "role:view", "role:edit", "organization:view", "organization:edit", "department:view", "department:edit"],
    "agent_view": ["agent:view"],
    "agent_manage": ["agent:manage"],
    "program:manage": ["service:deploy", "service:edit-config"],
    "program:operate": ["service:start", "service:stop", "service:restart", "container:start", "container:stop", "container:restart"],
}


def require_permission(permission: str):
    """
    权限检查依赖（兼容旧版权限码，内部转换为新权限码检查）
    """
    def checker(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        if user.role == "ADMIN":
            return user

        # 将旧权限码转换为新权限码列表
        required_new_perms = LEGACY_TO_NEW_PERMISSIONS.get(permission, [permission])

        # 获取用户所有权限
        user_perms = PermissionService.get_user_permissions(db, user.id)
        perm_set = set(user_perms)

        # 检查是否拥有任一所需权限（OR 逻辑）
        has_any = any(p in perm_set for p in required_new_perms)
        if not has_any:
            raise HTTPException(status_code=403, detail="Permission denied")
        return user
    return checker
