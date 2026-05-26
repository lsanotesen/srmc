from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from models.service import Service
from models.server import Server
from utils.ssh_pool import ssh_pool
from utils.crypto import decrypt
from services.audit_service import log_audit
from core.database import get_db
from api.dependencies import get_current_user

router = APIRouter()

@router.websocket("/shell/ws/{service_id}")
async def websocket_shell(websocket: WebSocket, service_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    await websocket.accept()
    
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
    
    password = decrypt(server.password) if server.password else None
    private_key = decrypt(server.private_key) if server.private_key else None
    
    conn = await ssh_pool.get_connection(server.ip, server.ssh_port, server.username, password, private_key)
    if not conn:
        await websocket.send_text("SSH connection failed")
        await websocket.close()
        return
    
    shell = None
    buffer = ""
    
    try:
        shell = await conn.invoke_shell()
        if service.work_dir:
            shell.send(f"cd {service.work_dir}\n")
        
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
                        log_audit(db, user.id, user.username, "SHELL", service_id=service_id, service_code=service.service_code,
                                  server_id=server.id, ip=server.ip, result="success", output=cmd.strip())
                
                buffer = ""
            
            shell.send(data)
    
    except WebSocketDisconnect:
        pass
    finally:
        if shell:
            shell.close()
