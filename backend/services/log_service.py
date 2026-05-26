import asyncio
from sqlalchemy.orm import Session
from models.service import Service
from models.server import Server
from utils.ssh_pool import ssh_pool
from utils.crypto import decrypt

async def get_log_content(service_id: int, lines: int = 100, keyword: str = None, db: Session = None):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service or not service.log_path:
        return None, "Service or log path not found"
    
    server = db.query(Server).filter(Server.id == service.server_id).first()
    if not server:
        return None, "Server not found"
    
    password = decrypt(server.password) if server.password else None
    private_key = decrypt(server.private_key) if server.private_key else None
    
    conn = await ssh_pool.get_connection(server.ip, server.ssh_port, server.username, password, private_key)
    if not conn:
        return None, "SSH connection failed"
    
    try:
        log_path = service.log_path
        
        output, error, success = await conn.execute_command(f"ls -la {log_path}")
        if not success:
            return None, f"Log path not found: {error}"
        
        if output.strip().endswith('/') or 'drwx' in output.split()[0]:
            output, error, success = await conn.execute_command(f"ls -la {log_path}/*.log 2>/dev/null | tail -1 | awk '{{print $9}}'")
            if success and output.strip():
                log_path = output.strip()
            else:
                return None, "No log files found in directory"
        
        if lines == 0:
            command = f"cat {log_path}"
        else:
            command = f"tail -n {lines} {log_path}"
        
        output, error, success = await conn.execute_command(command)
        if not success:
            return None, error
        
        if keyword:
            lines = output.split('\n')
            filtered_lines = [line for line in lines if keyword in line]
            output = '\n'.join(filtered_lines)
        
        return output, None
    finally:
        pass

async def tail_log(service_id: int, websocket, db: Session = None):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service or not service.log_path:
        await websocket.send_text("Service or log path not found")
        return
    
    server = db.query(Server).filter(Server.id == service.server_id).first()
    if not server:
        await websocket.send_text("Server not found")
        return
    
    password = decrypt(server.password) if server.password else None
    private_key = decrypt(server.private_key) if server.private_key else None
    
    conn = await ssh_pool.get_connection(server.ip, server.ssh_port, server.username, password, private_key)
    if not conn:
        await websocket.send_text("SSH connection failed")
        return
    
    try:
        shell = await conn.invoke_shell()
        if not shell:
            await websocket.send_text("Failed to invoke shell")
            return
        
        log_path = service.log_path
        shell.send(f"tail -f {log_path}\n")
        
        while True:
            if shell.recv_ready():
                output = shell.recv(4096).decode('utf-8', errors='ignore')
                await websocket.send_text(output)
            await asyncio.sleep(0.1)
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        pass
