from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR, HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from api.auth import router as auth_router
from api.server import router as server_router
from api.service import router as service_router
from api.processes import router as processes_router
from api.programs import router as programs_router
from api.monitor import router as monitor_router
from api.log import router as log_router
from api.shell import router as shell_router
from api.sql import router as sql_router
from api.es import router as es_router
from api.user import router as user_router
from api.audit import router as audit_router
from api.import_export import router as import_export_router
from api.projects import router as projects_router
from api.services import router as services_router
from api.subsystems import router as subsystems_router
from api.service_groups import router as service_groups_router
from api.subsystem_groups import router as subsystem_groups_router
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

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": 422,
            "message": "Validation error",
            "data": None,
            "details": exc.errors()
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "data": None,
            "details": None
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "Internal server error",
            "data": None,
            "details": traceback.format_exc()
        }
    )

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(server_router, prefix="/api", tags=["server"])
app.include_router(service_router, prefix="/api/monitor", tags=["service"])
app.include_router(processes_router, prefix="/api", tags=["processes"])
app.include_router(programs_router, prefix="/api", tags=["programs"])
app.include_router(monitor_router, prefix="/api", tags=["monitor"])
app.include_router(log_router, prefix="/api", tags=["log"])
app.include_router(shell_router, prefix="/api", tags=["shell"])
app.include_router(sql_router, prefix="/api", tags=["sql"])
app.include_router(es_router, prefix="/api", tags=["es"])
app.include_router(user_router, prefix="/api", tags=["user"])
app.include_router(audit_router, prefix="/api", tags=["audit"])
app.include_router(import_export_router, prefix="/api", tags=["import_export"])
app.include_router(projects_router, prefix="/api", tags=["projects"])
app.include_router(services_router, prefix="/api", tags=["services"])
app.include_router(subsystems_router, prefix="/api", tags=["subsystems"])
app.include_router(service_groups_router, prefix="/api", tags=["service_groups"])
app.include_router(subsystem_groups_router, prefix="/api", tags=["subsystem_groups"])

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    from sqlalchemy import text
    try:
        db.execute(text("SELECT 1"))
        return ResponseModel(data={"status": "healthy"})
    except Exception as e:
        return ResponseModel(code=1, message=f"Database connection failed: {str(e)}")

@app.on_event("startup")
async def startup_event():
    scheduler = AsyncIOScheduler()
    # 将状态检查间隔从10秒改为60秒，减少对API请求的影响
    scheduler.add_job(update_all_service_statuses, 'interval', seconds=60, args=[next(get_db())], max_instances=1)
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    from utils.ssh_pool import ssh_pool
    await ssh_pool.close_all()
