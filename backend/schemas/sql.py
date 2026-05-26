from pydantic import BaseModel, Field
from typing import Optional, List

class SqlExecuteRequest(BaseModel):
    service_id: int
    sql: str = Field(..., max_length=10000)

class SqlExecuteResponse(BaseModel):
    success: bool
    columns: List[str] = []
    data: List[dict] = []
    rows_affected: int = 0
    execution_time: int = 0
    error: Optional[str] = None

class SqlHistoryResponse(BaseModel):
    id: int
    service_code: str
    sql_statement: str
    execution_time: int
    result_count: Optional[int]
    error_message: Optional[str]
    created_at: str

    class Config:
        from_attributes = True
