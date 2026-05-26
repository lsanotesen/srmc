from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from schemas.common import ResponseModel
from services.log_service import get_log_content
from core.database import get_db
from api.dependencies import require_permission
import asyncio

router = APIRouter()

@router.get("/logs/{service_id}", response_model=ResponseModel)
async def get_logs(
    service_id: int,
    lines: int = Query(100, ge=0),
    keyword: str = Query(None),
    db: Session = Depends(get_db),
    user = Depends(require_permission("log_view"))
):
    content, error = await get_log_content(service_id, lines, keyword, db)
    if error:
        return ResponseModel(code=1, message=error)
    return ResponseModel(data={"content": content, "lines": len(content.split('\n')) if content else 0})

@router.websocket("/logs/ws/{service_id}")
async def websocket_logs(websocket: WebSocket, service_id: int):
    await websocket.accept()
    from services.log_service import tail_log
    
    async def send_logs():
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from core.config import settings
        
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            await tail_log(service_id, websocket, db)
        finally:
            db.close()
    
    try:
        await send_logs()
    except WebSocketDisconnect:
        pass
