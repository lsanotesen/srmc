from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.service import Service
from models.sql_exec_history import SqlExecHistory
from schemas.sql import SqlExecuteRequest, SqlExecuteResponse, SqlHistoryResponse
from schemas.common import ResponseModel
from utils.database_adapter import DatabaseConnectorFactory
from services.audit_service import log_audit
from core.database import get_db
from api.dependencies import require_permission

router = APIRouter()

@router.post("/sql/execute", response_model=ResponseModel)
async def execute_sql(request: SqlExecuteRequest, db: Session = Depends(get_db), user = Depends(require_permission("sql_execute"))):
    service = db.query(Service).filter(Service.id == request.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    connector = DatabaseConnectorFactory.create_connector(service.service_type, service.ip, service.port, service.extra_config)
    if not connector:
        raise HTTPException(status_code=400, detail="Unsupported database type")
    
    try:
        await connector.connect()
        result = await connector.execute(request.sql)
        
        history = SqlExecHistory(
            user_id=user.id,
            username=user.username,
            service_id=service.id,
            service_code=service.service_code,
            sql_statement=request.sql,
            execution_time=result.get('execution_time', 0),
            result_count=result.get('rows_affected', 0),
            error_message=result.get('error')
        )
        db.add(history)
        db.commit()
        
        log_audit(db, user.id, user.username, "SQL", service_id=service.id, service_code=service.service_code,
                  ip=service.ip, result="success" if 'error' not in result else "failed",
                  output=request.sql[:500])
        
        if 'error' in result:
            return ResponseModel(code=1, message=result['error'], data={"error": result['error']})
        
        return ResponseModel(data={
            "success": True,
            "columns": result.get('columns', []),
            "data": result.get('data', []),
            "rows_affected": result.get('rows_affected', 0)
        })
    finally:
        await connector.close()

@router.get("/sql/databases/{service_id}", response_model=ResponseModel)
async def get_databases(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("sql_execute"))):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    connector = DatabaseConnectorFactory.create_connector(service.service_type, service.ip, service.port, service.extra_config)
    if not connector:
        raise HTTPException(status_code=400, detail="Unsupported database type")
    
    try:
        await connector.connect()
        databases = await connector.fetch_databases()
        return ResponseModel(data=databases)
    finally:
        await connector.close()

@router.get("/sql/history", response_model=ResponseModel)
async def get_sql_history(db: Session = Depends(get_db), user = Depends(require_permission("sql_execute"))):
    history = db.query(SqlExecHistory).filter(SqlExecHistory.user_id == user.id).order_by(SqlExecHistory.created_at.desc()).limit(50).all()
    return ResponseModel(data=history)
