from pydantic import BaseModel, Field, IPvAnyAddress
from typing import Optional, List
from datetime import datetime

class ServiceCreate(BaseModel):
    project_id: int = Field(..., ge=1)
    subsystem_id: Optional[int] = Field(None, ge=1)
    group_id: Optional[int] = Field(None, ge=1)
    func_desc: str = Field(..., max_length=255)
    module: Optional[str] = Field(None, max_length=100)
    ip: str = Field(..., max_length=50)
    ssh_port: Optional[int] = Field(22, ge=1, le=65535)
    username: str = Field(..., max_length=100)
    password: str = Field(..., max_length=500)
    program_path: str = Field(..., max_length=500)
    start_script: Optional[str] = Field(None, max_length=500)
    stop_script: Optional[str] = Field(None, max_length=500)
    log_path: Optional[str] = Field(None, max_length=500)
    port: Optional[int] = Field(None, ge=1, le=65535)
    owner: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = None

class ServiceUpdate(BaseModel):
    project_id: Optional[int] = Field(None, ge=1)
    subsystem_id: Optional[int] = Field(None, ge=1)
    group_id: Optional[int] = Field(None, ge=1)
    func_desc: Optional[str] = Field(None, max_length=255)
    module: Optional[str] = Field(None, max_length=100)
    ip: Optional[IPvAnyAddress] = None
    ssh_port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, max_length=500)
    program_path: Optional[str] = Field(None, max_length=500)
    start_script: Optional[str] = Field(None, max_length=500)
    stop_script: Optional[str] = Field(None, max_length=500)
    log_path: Optional[str] = Field(None, max_length=500)
    port: Optional[int] = Field(None, ge=1, le=65535)
    owner: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = None

class ServiceResponse(BaseModel):
    id: int
    project_id: int
    project_name: Optional[str]
    subsystem_id: Optional[int]
    subsystem_name: Optional[str]
    group_id: Optional[int]
    group_name: Optional[str]
    func_desc: str
    module: Optional[str]
    ip: str
    ssh_port: int
    username: str
    program_path: str
    start_script: Optional[str]
    stop_script: Optional[str]
    log_path: Optional[str]
    port: Optional[int]
    owner: Optional[str]
    remark: Optional[str]
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ServiceOperationResult(BaseModel):
    success: bool
    message: str
    output: Optional[str] = None

class ServiceImportResult(BaseModel):
    success: bool
    message: str
    added: int = 0
    updated: int = 0
    failed: int = 0
    failed_items: List[dict] = []