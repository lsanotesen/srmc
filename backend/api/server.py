from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.server import Server
from schemas.server import ServerCreate, ServerUpdate, ServerResponse
from schemas.common import ResponseModel
from services.audit_service import log_audit
from utils.crypto import encrypt, decrypt
from utils.ssh_pool import ssh_pool
from core.database import get_db
from api.dependencies import get_current_user, require_permission

router = APIRouter()

@router.get("/servers", response_model=ResponseModel)
async def get_servers(db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    servers = db.query(Server).all()
    return ResponseModel(data=servers)

@router.get("/servers/{server_id}", response_model=ResponseModel)
async def get_server(server_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return ResponseModel(data=server)

@router.post("/servers", response_model=ResponseModel)
async def create_server(server_create: ServerCreate, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    existing = db.query(Server).filter(Server.ip == str(server_create.ip)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Server with this IP already exists")
    
    server = Server(
        hostname=server_create.hostname,
        ip=str(server_create.ip),
        ssh_port=server_create.ssh_port,
        username=server_create.username,
        password=encrypt(server_create.password) if server_create.password else None,
        private_key=encrypt(server_create.private_key) if server_create.private_key else None,
        os_type=server_create.os_type
    )
    db.add(server)
    db.commit()
    
    log_audit(db, user.id, user.username, "CREATE", server_id=server.id, ip=server.ip, result="success")
    
    return ResponseModel(data=server)

@router.put("/servers/{server_id}", response_model=ResponseModel)
async def update_server(server_id: int, server_update: ServerUpdate, db: Session = Depends(get_db), user = Depends(require_permission("user_manage"))):
    server = db.query(Server).filter(Server.id == server_id).first()
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
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    db.delete(server)
    db.commit()
    
    log_audit(db, user.id, user.username, "DELETE", server_id=server.id, ip=server.ip, result="success")
    
    return ResponseModel(message="Server deleted successfully")

@router.post("/servers/{server_id}/test-connection", response_model=ResponseModel)
async def test_connection(server_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    server = db.query(Server).filter(Server.id == server_id).first()
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
