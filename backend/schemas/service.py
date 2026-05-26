from pydantic import BaseModel, Field, IPvAnyAddress
from typing import Optional, List

class ServiceCreate(BaseModel):
    service_name: str = Field(..., max_length=128)
    service_code: str = Field(..., max_length=64)
    service_type: str = Field(..., pattern="^(APP|NGINX|REDIS|MYSQL|KINGBASE|DAMENG|ELASTICSEARCH|RABBITMQ|OTHER)$")
    module: Optional[str] = Field(None, max_length=64)
    environment: str = Field(..., pattern="^(DEV|TEST|STAGING|PROD)$")
    server_id: Optional[int] = None
    ip: IPvAnyAddress
    port: Optional[int] = Field(None, ge=1, le=65535)
    service_path: Optional[str] = Field(None, max_length=512)
    work_dir: Optional[str] = Field(None, max_length=512)
    start_script: Optional[str] = Field(None, max_length=512)
    stop_script: Optional[str] = Field(None, max_length=512)
    restart_script: Optional[str] = Field(None, max_length=512)
    log_path: Optional[str] = Field(None, max_length=512)
    check_type: Optional[str] = Field(None, pattern="^(PROCESS|PORT|PID|SCRIPT|HTTP|TCP)$")
    check_keyword: Optional[str] = Field(None, max_length=256)
    pid_file: Optional[str] = Field(None, max_length=512)
    owner: Optional[str] = Field(None, max_length=64)
    remark: Optional[str] = None
    extra_config: Optional[str] = None

class ServiceUpdate(BaseModel):
    service_name: Optional[str] = Field(None, max_length=128)
    service_type: Optional[str] = Field(None, pattern="^(APP|NGINX|REDIS|MYSQL|KINGBASE|DAMENG|ELASTICSEARCH|RABBITMQ|OTHER)$")
    module: Optional[str] = Field(None, max_length=64)
    environment: Optional[str] = Field(None, pattern="^(DEV|TEST|STAGING|PROD)$")
    server_id: Optional[int] = None
    ip: Optional[IPvAnyAddress] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    service_path: Optional[str] = Field(None, max_length=512)
    work_dir: Optional[str] = Field(None, max_length=512)
    start_script: Optional[str] = Field(None, max_length=512)
    stop_script: Optional[str] = Field(None, max_length=512)
    restart_script: Optional[str] = Field(None, max_length=512)
    log_path: Optional[str] = Field(None, max_length=512)
    check_type: Optional[str] = Field(None, pattern="^(PROCESS|PORT|PID|SCRIPT|HTTP|TCP)$")
    check_keyword: Optional[str] = Field(None, max_length=256)
    pid_file: Optional[str] = Field(None, max_length=512)
    owner: Optional[str] = Field(None, max_length=64)
    remark: Optional[str] = None
    extra_config: Optional[str] = None

class ServiceResponse(BaseModel):
    id: int
    service_name: str
    service_code: str
    service_type: str
    module: Optional[str]
    environment: str
    server_id: Optional[int]
    ip: str
    port: Optional[int]
    service_path: Optional[str]
    work_dir: Optional[str]
    start_script: Optional[str]
    stop_script: Optional[str]
    restart_script: Optional[str]
    log_path: Optional[str]
    check_type: Optional[str]
    check_keyword: Optional[str]
    pid_file: Optional[str]
    owner: Optional[str]
    remark: Optional[str]
    extra_config: Optional[str]
    capabilities: List[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

class ServiceImportResult(BaseModel):
    success: bool
    message: str
    added: int = 0
    updated: int = 0
    failed: int = 0
    failed_items: List[dict] = []
