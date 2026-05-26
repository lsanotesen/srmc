import asyncio
from sqlalchemy.orm import Session
from models.service import Service
from models.server import Server
from utils.ssh_pool import ssh_pool
from utils.crypto import decrypt
from services.audit_service import log_audit
from core.config import settings

semaphore = asyncio.Semaphore(settings.BATCH_MAX_WORKERS)

async def execute_service_operation(service_id: int, operation: str, db: Session, user_id: int, username: str):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        return {"service_id": service_id, "success": False, "message": "Service not found"}
    
    server = db.query(Server).filter(Server.id == service.server_id).first()
    if not server:
        return {"service_id": service_id, "success": False, "message": "Server not found"}
    
    password = decrypt(server.password) if server.password else None
    private_key = decrypt(server.private_key) if server.private_key else None
    
    async with semaphore:
        conn = await ssh_pool.get_connection(server.ip, server.ssh_port, server.username, password, private_key)
        if not conn:
            log_audit(db, user_id, username, operation, service_id, service.service_code, server.id, server.ip, "failed", "SSH connection failed")
            return {"service_id": service_id, "success": False, "message": "SSH connection failed"}
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            if operation == "START":
                script = service.start_script or "start.sh"
            elif operation == "STOP":
                script = service.stop_script or "stop.sh"
            elif operation == "RESTART":
                script = service.restart_script
                if not script:
                    await execute_service_operation(service_id, "STOP", db, user_id, username)
                    await asyncio.sleep(1)
                    script = service.start_script or "start.sh"
            else:
                return {"service_id": service_id, "success": False, "message": "Invalid operation"}
            
            work_dir = service.work_dir or "/"
            command = f"cd {work_dir} && ./{script}"
            
            output, error, success = await conn.execute_command(command)
            duration = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            result = "success" if success else "failed"
            log_output = output[:2000] if output else error[:2000] if error else ""
            log_audit(db, user_id, username, operation, service_id, service.service_code, server.id, server.ip, result, log_output, duration)
            
            return {
                "service_id": service_id,
                "success": success,
                "message": output.strip() if success else error.strip(),
                "duration": duration
            }
        finally:
            pass
