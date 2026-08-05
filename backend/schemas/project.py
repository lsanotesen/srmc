from pydantic import BaseModel, Field
from typing import Optional


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    organization_id: Optional[int] = None
    department_id: Optional[int] = None
    visibility: str = Field("DEPARTMENT", pattern="^(DEPARTMENT|AUTHORIZED|PUBLIC)$")
    owner_id: Optional[int] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    organization_id: Optional[int] = None  # 允许首次设置，已有组织时前端锁定不可修改
    department_id: Optional[int] = None
    visibility: Optional[str] = Field(None, pattern="^(DEPARTMENT|AUTHORIZED|PUBLIC)$")
    owner_id: Optional[int] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    code: Optional[str]
    description: Optional[str]
    organization_id: Optional[int] = None
    organization_name: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    creator_id: Optional[int] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    visibility: Optional[str] = "DEPARTMENT"

    class Config:
        from_attributes = True
