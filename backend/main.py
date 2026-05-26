from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from api.auth import router as auth_router
from api.server import router as server_router
from api.service import router as service_router
from api.monitor import router as monitor_router
from api.log import router as log_router
from api.shell import router as shell_router
from api.sql import router as sql_router
from api.es import router as es_router
from api.user import router as user_router
from api.audit import router as audit_router
from api.import_export import router as import_export_router
from services.monitor_service import update_all_service_statuses
from core.database import get_db
from schemas.common import ResponseModel

app = FastAPI(title="Service Resource Management Center", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(server_router, prefix="/api", tags=["server"])
app.include_router(service_router, prefix="/api", tags=["service"])
app.include_router(monitor_router, prefix="/api", tags=["monitor"])
app.include_router(log_router, prefix="/api", tags=["log"])
app.include_router(shell_router, prefix="/api", tags=["shell"])
app.include_router(sql_router, prefix="/api", tags=["sql"])
app.include_router(es_router, prefix="/api", tags=["es"])
app.include_router(user_router, prefix="/api", tags=["user"])
app.include_router(audit_router, prefix="/api", tags=["audit"])
app.include_router(import_export_router, prefix="/api", tags=["import_export"])

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        return ResponseModel(data={"status": "healthy"})
    except Exception as e:
        return ResponseModel(code=1, message=f"Database connection failed: {str(e)}")

@app.on_event("startup")
async def startup_event():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_all_service_statuses, 'interval', seconds=10, args=[next(get_db())])
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    from utils.ssh_pool import ssh_pool
    await ssh_pool.close_all()
