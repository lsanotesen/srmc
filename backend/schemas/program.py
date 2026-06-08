from pydantic import BaseModel, Field, IPvAnyAddress
from typing import Optional, List
from datetime import datetime

class ProgramCreate(BaseModel):
    func_desc: str = Field(..., max_length=255)
    module: Optional[str] = Field(None, max_length=100)
    ip: IPvAnyAddress
    username: str = Field(..., max_length=100)
    password: str = Field(..., max_length=500)
    program_path: str = Field(..., max_length=500)
    start_script: Optional[str] = Field(None, max_length=500)
    stop_script: Optional[str] = Field(None, max_length=500)
    restart_script: Optional[str] = Field(None, max_length=500)
    log_path: Optional[str] = Field(None, max_length=500)
    port: Optional[int] = Field(None, ge=1, le=65535)
    owner: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = None

class ProgramUpdate(BaseModel):
    func_desc: Optional[str] = Field(None, max_length=255)
    module: Optional[str] = Field(None, max_length=100)
    ip: Optional[IPvAnyAddress] = None
    username: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, max_length=500)
    program_path: Optional[str] = Field(None, max_length=500)
    start_script: Optional[str] = Field(None, max_length=500)
    stop_script: Optional[str] = Field(None, max_length=500)
    restart_script: Optional[str] = Field(None, max_length=500)
    log_path: Optional[str] = Field(None, max_length=500)
    port: Optional[int] = Field(None, ge=1, le=65535)
    owner: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = None

class ProgramResponse(BaseModel):
    id: int
    func_desc: str
    module: Optional[str]
    ip: str
    username: str
    program_path: str
    start_script: Optional[str]
    stop_script: Optional[str]
    restart_script: Optional[str]
    log_path: Optional[str]
    port: Optional[int]
    owner: Optional[str]
    remark: Optional[str]
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ProgramStatusResponse(BaseModel):
    id: int
    status: str

class ProgramOperationResult(BaseModel):
    success: bool
    message: str
    output: Optional[str] = None

class ProgramImportResult(BaseModel):
    success: bool
    message: str
    added: int = 0
    updated: int = 0
    failed: int = 0
    failed_items: List[dict] = []