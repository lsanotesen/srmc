from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    username: str = Field(..., max_length=64)
    password: str = Field(..., min_length=6)
    role: str = Field("READONLY", pattern="^(ADMIN|OPS|DEV|READONLY)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)

class UserUpdate(BaseModel):
    password: Optional[str] = Field(None, min_length=6)
    role: Optional[str] = Field(None, pattern="^(ADMIN|OPS|DEV|READONLY)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    email: Optional[str]
    phone: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
