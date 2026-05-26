from pydantic import BaseModel, Field
from typing import Optional

class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    username: str
    action: str
    service_id: Optional[int]
    service_code: Optional[str]
    server_id: Optional[int]
    ip: Optional[str]
    result: str
    output: Optional[str]
    duration: Optional[int]
    created_at: str

    class Config:
        from_attributes = True
