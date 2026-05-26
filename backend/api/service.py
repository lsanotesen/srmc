from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from models.service import Service
from models.server import Server
from schemas.service import ServiceCreate, ServiceUpdate, ServiceResponse
from schemas.common import ResponseModel
from services.audit_service import log_audit
from services.monitor_service import get_service_status
from core.database import get_db
from core.capabilities import SERVICE_TYPE_CAPABILITIES, ServiceType
from api.dependencies import get_current_user, require_permission

router = APIRouter()

def add_capabilities_to_service(service):
    capabilities = SERVICE_TYPE_CAPABILITIES.get(ServiceType(service.service_type), [])
    service_dict = service.__dict__.copy()
    service_dict['capabilities'] = [c.value for c in capabilities]
    return service_dict

@router.get("/services", response_model=ResponseModel)
async def get_services(
    service_type: str = Query(None),
    environment: str = Query(None),
    module: str = Query(None),
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_view"))
):
    query = db.query(Service)
    if service_type:
        query = query.filter(Service.service_type == service_type)
    if environment:
        query = query.filter(Service.environment == environment)
    if module:
        query = query.filter(Service.module == module)
    
    services = query.all()
    result = []
    for service in services:
        service_dict = add_capabilities_to_service(service)
        service_dict['status'] = get_service_status(service.id)
        result.append(service_dict)
    
    return ResponseModel(data=result)

@router.get("/services/{service_id}", response_model=ResponseModel)
async def get_service(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    service_dict = add_capabilities_to_service(service)
    service_dict['status'] = get_service_status(service.id)
    
    return ResponseModel(data=service_dict)

@router.post("/services", response_model=ResponseModel)
async def create_service(service_create: ServiceCreate, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    existing = db.query(Service).filter(Service.service_code == service_create.service_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Service code already exists")
    
    server = db.query(Server).filter(Server.ip == str(service_create.ip)).first()
    if not server:
        raise HTTPException(status_code=400, detail="Server with this IP not found")
    
    service = Service(
        service_name=service_create.service_name,
        service_code=service_create.service_code,
        service_type=service_create.service_type,
        module=service_create.module,
        environment=service_create.environment,
        server_id=server.id,
        ip=str(service_create.ip),
        port=service_create.port,
        service_path=service_create.service_path,
        work_dir=service_create.work_dir,
        start_script=service_create.start_script,
        stop_script=service_create.stop_script,
        restart_script=service_create.restart_script,
        log_path=service_create.log_path,
        check_type=service_create.check_type,
        check_keyword=service_create.check_keyword,
        pid_file=service_create.pid_file,
        owner=service_create.owner,
        remark=service_create.remark,
        extra_config=service_create.extra_config
    )
    db.add(service)
    db.commit()
    
    log_audit(db, user.id, user.username, "CREATE", service_id=service.id, service_code=service.service_code, server_id=server.id, ip=server.ip, result="success")
    
    return ResponseModel(data=add_capabilities_to_service(service))

@router.put("/services/{service_id}", response_model=ResponseModel)
async def update_service(service_id: int, service_update: ServiceUpdate, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if service_update.ip:
        server = db.query(Server).filter(Server.ip == str(service_update.ip)).first()
        if server:
            service.server_id = server.id
    
    for key, value in service_update.dict(exclude_unset=True).items():
        if key == 'ip':
            setattr(service, key, str(value))
        else:
            setattr(service, key, value)
    
    db.commit()
    
    log_audit(db, user.id, user.username, "UPDATE", service_id=service.id, service_code=service.service_code, server_id=service.server_id, ip=service.ip, result="success")
    
    return ResponseModel(data=add_capabilities_to_service(service))

@router.delete("/services/{service_id}", response_model=ResponseModel)
async def delete_service(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    db.delete(service)
    db.commit()
    
    log_audit(db, user.id, user.username, "DELETE", service_id=service.id, service_code=service.service_code, server_id=service.server_id, ip=service.ip, result="success")
    
    return ResponseModel(message="Service deleted successfully")

@router.get("/capabilities/{service_type}", response_model=ResponseModel)
async def get_capabilities(service_type: str, user = Depends(require_permission("service_view"))):
    capabilities = SERVICE_TYPE_CAPABILITIES.get(ServiceType(service_type.upper()), [])
    return ResponseModel(data=[c.value for c in capabilities])
