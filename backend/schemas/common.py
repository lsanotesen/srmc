from pydantic import BaseModel
from typing import Optional, Any

class ResponseModel(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None

    class Config:
        arbitrary_types_allowed = True
