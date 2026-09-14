from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import false
from sqlalchemy.orm import Session
from models.server import Server
from schemas.server import ServerCreate, ServerUpdate, ServerResponse
from schemas.common import ResponseModel
from services.audit_service import log_audit
from services.data_scope_service import DataScopeService
from utils.crypto import encrypt, decrypt
from utils.ssh_pool import ssh_pool
from core.database import get_db
from api.dependencies import get_current_user, require_permission

router = APIRouter()


def _scope_server_query(query, user):
    """组织隔离：超级管理员可见全部，普通用户仅可见本组织服务器。"""
    if DataScopeService._is_super_admin(user):
        return query
    if user.organization_id is not None:
        return query.filter(Server.organization_id == user.organization_id)
    # 无组织的普通用户看不到任何服务器
    return query.filter(false())


@router.get("/servers", response_model=ResponseModel)
async def get_servers(
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_view")),
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = _scope_server_query(db.query(Server), user)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            (Server.hostname.ilike(like))
            | (Server.ip.ilike(like))
            | (Server.username.ilike(like))
        )

    total = query.count()
    servers = query.order_by(Server.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ResponseModel(data={"items": servers, "total": total, "page": page, "page_size": page_size})

@router.get("/servers/{server_id}", response_model=ResponseModel)
async def get_server(server_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    server = _scope_server_query(db.query(Server), user).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return ResponseModel(data=server)

@router.post("/servers", response_model=ResponseModel)
async def create_server(server_create: ServerCreate, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    existing = db.query(Server).filter(
        Server.ip == str(server_create.ip),
        Server.organization_id == user.organization_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Server with this IP already exists in your organization")
    
    server = Server(
        hostname=server_create.hostname,
        ip=str(server_create.ip),
        ssh_port=server_create.ssh_port,
        username=server_create.username,
        password=encrypt(server_create.password) if server_create.password else None,
        private_key=encrypt(server_create.private_key) if server_create.private_key else None,
        os_type=server_create.os_type,
        organization_id=user.organization_id
    )
    db.add(server)
    db.commit()
    
    log_audit(db, user.id, user.username, "CREATE", server_id=server.id, ip=server.ip, result="success")
    
    return ResponseModel(data=server)

@router.put("/servers/{server_id}", response_model=ResponseModel)
async def update_server(server_id: int, server_update: ServerUpdate, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    server = _scope_server_query(db.query(Server), user).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if server_update.password:
        server_update.password = encrypt(server_update.password)
    if server_update.private_key:
        server_update.private_key = encrypt(server_update.private_key)
    
    for key, value in server_update.dict(exclude_unset=True).items():
        setattr(server, key, value)
    
    db.commit()
    
    log_audit(db, user.id, user.username, "UPDATE", server_id=server.id, ip=server.ip, result="success")
    
    return ResponseModel(data=server)

@router.delete("/servers/{server_id}", response_model=ResponseModel)
async def delete_server(server_id: int, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    server = _scope_server_query(db.query(Server), user).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    db.delete(server)
    db.commit()
    
    log_audit(db, user.id, user.username, "DELETE", server_id=server.id, ip=server.ip, result="success")
    
    return ResponseModel(message="Server deleted successfully")

@router.post("/servers/{server_id}/test-connection", response_model=ResponseModel)
async def test_connection(server_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    server = _scope_server_query(db.query(Server), user).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    password = decrypt(server.password) if server.password else None
    private_key = decrypt(server.private_key) if server.private_key else None
    
    conn = await ssh_pool.get_connection(server.ip, server.ssh_port, server.username, password, private_key)
    
    if conn:
        output, error, success = await conn.execute_command("echo 'Connection test successful'")
        if success:
            return ResponseModel(message="Connection successful")
    
    return ResponseModel(code=1, message="Connection failed")
