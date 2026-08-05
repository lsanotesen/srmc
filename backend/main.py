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
from api.shell import router as shell_router
from api.sftp import router as sftp_router
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
from api.metrics import router as metrics_router
from api.agent import router as agent_router
from api.organization import router as organization_router
from api.rbac import router as rbac_router
from api.project_member import router as project_member_router
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
app.include_router(shell_router, prefix="/api", tags=["shell"])
app.include_router(sftp_router, prefix="/api/sftp", tags=["sftp"])
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
app.include_router(metrics_router, prefix="", tags=["metrics"])
app.include_router(agent_router, prefix="/api", tags=["agents"])
app.include_router(organization_router, prefix="/api", tags=["organization"])
app.include_router(rbac_router, prefix="/api/rbac", tags=["rbac"])
app.include_router(project_member_router, prefix="/api", tags=["project_member"])

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
    # 初始化程序分类
    await init_service_groups()

    # 初始化企业级权限数据
    await init_permission_data()
    
    scheduler = AsyncIOScheduler()
    # 定时任务自己管理数据库连接
    scheduler.add_job(update_all_service_statuses, 'interval', seconds=60, max_instances=1)
    scheduler.start()

async def init_service_groups():
    """初始化程序分类（如果不存在则创建）"""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        from models.service_group import ServiceGroup
        
        # 定义默认的程序分类
        default_groups = [
            {"group_name": "分析程序", "group_code": "ANALYSIS", "display_order": 1, "description": "数据分析、处理相关程序"},
            {"group_name": "索引程序", "group_code": "INDEX", "display_order": 2, "description": "索引构建、搜索相关程序"},
            {"group_name": "管理程序", "group_code": "MANAGEMENT", "display_order": 3, "description": "系统管理、配置相关程序"},
            {"group_name": "API服务", "group_code": "API", "display_order": 4, "description": "对外API接口服务"},
            {"group_name": "定时任务", "group_code": "CRON", "display_order": 5, "description": "定时调度任务"},
            # 中间件分类
            {"group_name": "Redis", "group_code": "REDIS", "display_order": 10, "description": "Redis缓存服务"},
            {"group_name": "MySQL", "group_code": "MYSQL", "display_order": 11, "description": "MySQL数据库服务"},
            {"group_name": "PostgreSQL", "group_code": "POSTGRESQL", "display_order": 12, "description": "PostgreSQL数据库服务"},
            {"group_name": "MongoDB", "group_code": "MONGODB", "display_order": 13, "description": "MongoDB数据库服务"},
            {"group_name": "Elasticsearch", "group_code": "ELASTICSEARCH", "display_order": 14, "description": "Elasticsearch搜索引擎"},
            {"group_name": "Kafka", "group_code": "KAFKA", "display_order": 15, "description": "Kafka消息队列"},
            {"group_name": "RabbitMQ", "group_code": "RABBITMQ", "display_order": 16, "description": "RabbitMQ消息队列"},
            {"group_name": "Nginx", "group_code": "NGINX", "display_order": 17, "description": "Nginx反向代理"},
            {"group_name": "Tomcat", "group_code": "TOMCAT", "display_order": 18, "description": "Tomcat应用服务器"},
            {"group_name": "其他中间件", "group_code": "OTHER_MIDDLEWARE", "display_order": 19, "description": "其他中间件服务"},
        ]
        
        for group_info in default_groups:
            existing = db.query(ServiceGroup).filter(ServiceGroup.group_code == group_info["group_code"]).first()
            if not existing:
                new_group = ServiceGroup(
                    group_name=group_info["group_name"],
                    group_code=group_info["group_code"],
                    display_order=group_info["display_order"],
                    description=group_info["description"]
                )
                db.add(new_group)
        
        db.commit()
    finally:
        db.close()

async def init_permission_data():
    """初始化企业级权限数据"""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        from models.organization import Organization
        from models.department import Department
        from models.user import User
        from services.role_permission_service import RolePermissionService

        org = db.query(Organization).filter(Organization.code == "DEFAULT").first()
        if not org:
            org = Organization(name="默认组织", code="DEFAULT", description="系统默认组织", status=1)
            db.add(org)
            db.commit()
            print("[Permission] 创建默认组织")

        dept = db.query(Department).filter(Department.organization_id == org.id).first()
        if not dept:
            dept = Department(
                organization_id=org.id,
                parent_id=None,
                name="根部门",
                code="ROOT",
                description="组织根部门",
                status=1,
                sort_order=0,
            )
            db.add(dept)
            db.commit()
            print("[Permission] 创建根部门")

        users = db.query(User).filter(User.organization_id.is_(None)).all()
        for user in users:
            user.organization_id = org.id
            user.department_id = dept.id
        if users:
            db.commit()
            print(f"[Permission] 为 {len(users)} 个用户分配组织和部门")

        RolePermissionService.initialize_default_data(db)
        print("[Permission] 角色和权限初始化完成")
    except Exception as e:
        print(f"[Permission] 权限数据初始化失败: {e}")
        db.rollback()
    finally:
        db.close()

@app.on_event("shutdown")
async def shutdown_event():
    from utils.ssh_pool import ssh_pool
    await ssh_pool.close_all()
