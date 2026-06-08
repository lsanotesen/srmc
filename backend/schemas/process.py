from pydantic import BaseModel, Field
from datetime import datetime

class ProcessCreate(BaseModel):
    process_name: str = Field(..., description="程序名称")
    process_code: str = Field(..., description="程序编码")
    project_id: int = Field(None, description="项目ID")
    language: str = Field(..., description="语言类型")
    module: str = Field(None, description="模块")
    environment: str = Field(..., description="环境")
    ip: str = Field(..., description="IP地址")
    port: int = Field(None, description="端口")
    work_dir: str = Field(None, description="工作目录")
    start_command: str = Field(None, description="启动命令")
    stop_command: str = Field(None, description="停止命令")
    check_type: str = Field(None, description="检测类型")
    check_keyword: str = Field(None, description="检测关键词")
    owner: str = Field(None, description="负责人")
    remark: str = Field(None, description="备注")

class ProcessUpdate(BaseModel):
    process_name: str = Field(None, description="程序名称")
    project_id: int = Field(None, description="项目ID")
    language: str = Field(None, description="语言类型")
    module: str = Field(None, description="模块")
    environment: str = Field(None, description="环境")
    ip: str = Field(None, description="IP地址")
    port: int = Field(None, description="端口")
    work_dir: str = Field(None, description="工作目录")
    start_command: str = Field(None, description="启动命令")
    stop_command: str = Field(None, description="停止命令")
    check_type: str = Field(None, description="检测类型")
    check_keyword: str = Field(None, description="检测关键词")
    owner: str = Field(None, description="负责人")
    remark: str = Field(None, description="备注")

class ProcessResponse(BaseModel):
    id: int
    process_name: str
    process_code: str
    project_id: int
    language: str
    module: str
    environment: str
    ip: str
    port: int
    work_dir: str
    status: str
    owner: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
