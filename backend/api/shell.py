from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from models.service import Service
from models.app_service import AppService
from models.server import Server
from models.user import User
from utils.ssh_pool import ssh_pool
from utils.crypto import decrypt
from services.audit_service import log_audit
from core.database import get_db
from core.config import settings
from jose import jwt
import asyncio

router = APIRouter()

async def get_current_user_ws(token: str, db: Session):
    """WebSocket 认证 - 从 query 参数获取 token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(User).filter(User.username == username).first()
        if user is None or not user.is_active:
            return None
        return user
    except Exception:
        return None

@router.websocket("/shell/ws/{service_id}")
async def websocket_shell(
    websocket: WebSocket, 
    service_id: int, 
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    # 先认证用户
    user = await get_current_user_ws(token, db)
    if not user:
        await websocket.accept()
        await websocket.send_text("Authentication failed")
        await websocket.close()
        return
    
    await websocket.accept()
    
    # 先尝试从 AppService 表查找（服务管理页面使用的模型）
    service = db.query(AppService).filter(AppService.id == service_id).first()
    
    if service:
        # AppService 模型
        ip = service.ip
        ssh_port = service.ssh_port or 22
        username = service.username
        password = decrypt(service.password) if service.password else None
        private_key = None
        work_dir = None
        service_code = service.func_desc
        server_id = None
        
    else:
        # 尝试从 Service 表查找（旧模型）
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            await websocket.send_text("Service not found")
            await websocket.close()
            return
        
        server = db.query(Server).filter(Server.id == service.server_id).first()
        if not server:
            await websocket.send_text("Server not found")
            await websocket.close()
            return
        
        ip = server.ip
        ssh_port = server.ssh_port or 22
        username = server.username
        password = decrypt(server.password) if server.password else None
        private_key = decrypt(server.private_key) if server.private_key else None
        work_dir = service.work_dir
        service_code = service.service_code
        server_id = server.id
    
    conn = await ssh_pool.get_connection(ip, ssh_port, username, password, private_key)
    if not conn:
        await websocket.send_text("SSH connection failed")
        await websocket.close()
        return
    
    shell = None
    buffer = ""
    
    try:
        shell = await conn.invoke_shell()
        if work_dir:
            shell.send(f"cd {work_dir}\n")
        
        async def read_from_shell():
            while True:
                if shell.recv_ready():
                    output = shell.recv(4096).decode('utf-8', errors='ignore')
                    await websocket.send_text(output)
                await asyncio.sleep(0.1)
        
        asyncio.create_task(read_from_shell())
        
        while True:
            data = await websocket.receive_text()
            buffer += data
            
            if '\r' in buffer or '\n' in buffer:
                commands = buffer.split('\r') if '\r' in buffer else buffer.split('\n')
                for cmd in commands:
                    if cmd.strip():
                        # AppService 模型没有 server_id，所以不写入 service_id 和 server_id
                        log_audit(db, user.id, user.username, "SHELL", 
                                  service_code=service_code,
                                  ip=ip, result="success", output=cmd.strip())
                
                buffer = ""
            
            shell.send(data)
    
    except WebSocketDisconnect:
        pass
    finally:
        if shell:
            shell.close()
