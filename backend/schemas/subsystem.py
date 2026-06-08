from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class SubsystemBase(BaseModel):
    subsystem_name: str = Field(..., max_length=100, description="子系统名称")
    subsystem_code: str = Field(..., max_length=50, description="子系统编码")
    display_order: int = Field(0, description="显示顺序")
    description: Optional[str] = Field(None, description="描述")

class SubsystemCreate(SubsystemBase):
    project_id: int = Field(..., description="项目ID")

class SubsystemUpdate(BaseModel):
    subsystem_name: Optional[str] = Field(None, max_length=100)
    subsystem_code: Optional[str] = Field(None, max_length=50)
    display_order: Optional[int] = None
    description: Optional[str] = None

class SubsystemResponse(SubsystemBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True