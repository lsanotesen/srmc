from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ServiceGroupBase(BaseModel):
    group_name: str = Field(..., max_length=100, description="分类名称")
    group_code: str = Field(..., max_length=50, description="分类编码")
    display_order: int = Field(0, description="显示顺序")
    description: Optional[str] = Field(None, description="描述")

class ServiceGroupCreate(ServiceGroupBase):
    pass

class ServiceGroupUpdate(BaseModel):
    group_name: Optional[str] = Field(None, max_length=100)
    group_code: Optional[str] = Field(None, max_length=50)
    display_order: Optional[int] = None
    description: Optional[str] = None

class ServiceGroupResponse(ServiceGroupBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
