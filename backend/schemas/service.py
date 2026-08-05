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
    program_path: Optional[str] = Field(None, max_length=500)
    start_script: Optional[str] = Field(None, max_length=500)
    stop_script: Optional[str] = Field(None, max_length=500)
    log_path: Optional[str] = Field(None, max_length=500)
    log_type: Optional[str] = Field(None, max_length=50)
    port: Optional[int] = Field(None, ge=1, le=65535)
    owner: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = None
    service_type: Optional[str] = Field(None, max_length=50)
    deploy_type: Optional[str] = Field(None, max_length=50)
    instance_name: Optional[str] = Field(None, max_length=255)
    container_name: Optional[str] = Field(None, max_length=255)
    image_name: Optional[str] = Field(None, max_length=255)
    image_tag: Optional[str] = Field(None, max_length=100)
    port_mapping: Optional[str] = Field(None, max_length=500)
    volume_mapping: Optional[str] = Field(None, max_length=1000)
    network_mode: Optional[str] = Field(None, max_length=100)
    agent_uuid: Optional[str] = Field(None, max_length=64)

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
    log_type: Optional[str] = Field(None, max_length=50)
    port: Optional[int] = Field(None, ge=1, le=65535)
    owner: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = None
    service_type: Optional[str] = Field(None, max_length=50)
    deploy_type: Optional[str] = Field(None, max_length=50)
    instance_name: Optional[str] = Field(None, max_length=255)
    container_name: Optional[str] = Field(None, max_length=255)
    image_name: Optional[str] = Field(None, max_length=255)
    image_tag: Optional[str] = Field(None, max_length=100)
    port_mapping: Optional[str] = Field(None, max_length=500)
    volume_mapping: Optional[str] = Field(None, max_length=1000)
    network_mode: Optional[str] = Field(None, max_length=100)
    agent_uuid: Optional[str] = Field(None, max_length=64)

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
    program_path: Optional[str]
    start_script: Optional[str]
    stop_script: Optional[str]
    log_path: Optional[str]
    port: Optional[int]
    owner: Optional[str]
    remark: Optional[str]
    created_at: datetime
    updated_at: datetime
    service_type: Optional[str]
    deploy_type: Optional[str]
    instance_name: Optional[str]
    container_name: Optional[str]
    image_name: Optional[str]
    image_tag: Optional[str]
    container_id: Optional[str]
    port_mapping: Optional[str]
    volume_mapping: Optional[str]
    network_mode: Optional[str]
    log_type: Optional[str]

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