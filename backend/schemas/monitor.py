from pydantic import BaseModel
from typing import Optional, List

class ServiceStatusResponse(BaseModel):
    service_id: int
    service_code: str
    service_name: str
    status: str  # RUNNING, STOPPED, UNKNOWN
    ip: str
    port: Optional[int]
    check_type: Optional[str]

class BatchStatusResponse(BaseModel):
    results: List[ServiceStatusResponse]
    total: int
    running: int
    stopped: int
    unknown: int
