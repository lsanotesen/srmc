from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List


class UserCreate(BaseModel):
    username: str = Field(..., max_length=64)
    password: str = Field(..., min_length=6)
    role: Optional[str] = Field("READONLY", pattern="^(SUPER_ADMIN|ORG_ADMIN|DEPT_ADMIN|DEPT_MEMBER|READONLY)$")
    role_ids: Optional[List[int]] = Field(default_factory=list, description="RBAC角色ID列表")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    organization_id: Optional[int] = None
    department_id: Optional[int] = None
    job_title: Optional[str] = None


class UserUpdate(BaseModel):
    password: Optional[str] = Field(None, min_length=6)
    role: Optional[str] = Field(None, pattern="^(SUPER_ADMIN|ORG_ADMIN|DEPT_ADMIN|DEPT_MEMBER|READONLY)$")
    role_ids: Optional[List[int]] = Field(None, description="RBAC角色ID列表")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None
    organization_id: Optional[int] = None
    department_id: Optional[int] = None
    job_title: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    roles: Optional[List[dict]] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    organization_id: Optional[int] = None
    organization_name: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    job_title: Optional[str] = None
    status: Optional[int] = None
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
