from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from schemas.user import LoginRequest, LoginResponse
from schemas.common import ResponseModel
from services.auth_service import authenticate_user, create_access_token
from services.audit_service import log_audit
from core.database import get_db
from core.config import settings

router = APIRouter()

@router.post("/login", response_model=ResponseModel)
async def login(login_request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, login_request)
    if not user:
        log_audit(db, None, login_request.username, "LOGIN", result="failed", output="Invalid credentials")
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id},
        expires_delta=access_token_expires
    )
    
    log_audit(db, user.id, user.username, "LOGIN", result="success")
    
    return ResponseModel(data={
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email,
            "phone": user.phone,
            "is_active": user.is_active,
            "created_at": str(user.created_at),
            "updated_at": str(user.updated_at)
        }
    })

@router.post("/logout", response_model=ResponseModel)
async def logout():
    return ResponseModel(message="Logout successful")
