from pydantic import BaseModel, Field, IPvAnyAddress
from typing import Optional

class ServerCreate(BaseModel):
    hostname: str = Field(..., max_length=128)
    ip: IPvAnyAddress
    ssh_port: int = Field(22, ge=1, le=65535)
    username: str = Field(..., max_length=64)
    password: Optional[str] = None
    private_key: Optional[str] = None
    os_type: str = Field("LINUX", pattern="^(LINUX|UNIX)$")

class ServerUpdate(BaseModel):
    hostname: Optional[str] = Field(None, max_length=128)
    ip: Optional[IPvAnyAddress] = None
    ssh_port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, max_length=64)
    password: Optional[str] = None
    private_key: Optional[str] = None
    os_type: Optional[str] = Field(None, pattern="^(LINUX|UNIX)$")

class ServerResponse(BaseModel):
    id: int
    hostname: str
    ip: str
    ssh_port: int
    username: str
    os_type: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
