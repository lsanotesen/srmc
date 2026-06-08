from pydantic import BaseModel, Field
from typing import Optional

class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    code: Optional[str]
    description: Optional[str]

    class Config:
        from_attributes = True
