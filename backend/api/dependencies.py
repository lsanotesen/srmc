from fastapi import Depends, HTTPException, status, Header
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from models.user import User
from core.database import get_db
from core.config import settings
from core.capabilities import ROLE_PERMISSIONS

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

def require_permission(permission: str):
    def checker(user: User = Depends(get_current_user)):
        permissions = ROLE_PERMISSIONS.get(user.role, [])
        if permission not in permissions:
            raise HTTPException(status_code=403, detail="Permission denied")
        return user
    return checker