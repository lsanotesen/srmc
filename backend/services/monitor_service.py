import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from models.service import Service
from models.server import Server
from utils.ssh_pool import ssh_pool
from utils.crypto import decrypt
from utils.redis_client import redis_client
from core.config import settings

async def check_service_status(service: Service, server: Server):
    check_type = service.check_type
    check_keyword = service.check_keyword
    pid_file = service.pid_file
    ip = server.ip
    port = server.ssh_port
    username = server.username
    password = decrypt(server.password) if server.password else None
    private_key = decrypt(server.private_key) if server.private_key else None
    
    conn = await ssh_pool.get_connection(ip, port, username, password, private_key)
    if not conn:
        return "UNKNOWN"
    
    try:
        if check_type == "PROCESS":
            output, error, success = await conn.execute_command(f"ps -ef | grep {check_keyword} | grep -v grep")
            return "RUNNING" if success and output.strip() else "STOPPED"
        
        elif check_type == "PORT":
            output, error, success = await conn.execute_command(f"ss -lntp | grep :{check_keyword}")
            return "RUNNING" if success and output.strip() else "STOPPED"
        
        elif check_type == "PID":
            output, error, success = await conn.execute_command(f"cat {pid_file}")
            if success and output.strip():
                pid = output.strip()
                output2, error2, success2 = await conn.execute_command(f"ps -p {pid} -o comm=")
                return "RUNNING" if success2 and output2.strip() else "STOPPED"
            return "STOPPED"
        
        elif check_type == "TCP":
            output, error, success = await conn.execute_command(f"timeout 2 bash -c 'echo > /dev/tcp/{service.ip}/{service.port}'")
            return "RUNNING" if success and not error else "STOPPED"
        
        elif check_type == "HTTP":
            output, error, success = await conn.execute_command(f"curl -s -o /dev/null -w '%{{http_code}}' http://{service.ip}:{service.port}/health")
            return "RUNNING" if success and output.strip() in ["200", "201"] else "STOPPED"
        
        else:
            return "UNKNOWN"
    except Exception as e:
        return "UNKNOWN"

async def update_all_service_statuses(db: Session):
    servers = db.query(Server).all()
    
    for server in servers:
        services = db.query(Service).filter(Service.server_id == server.id).all()
        if not services:
            continue
        
        password = decrypt(server.password) if server.password else None
        private_key = decrypt(server.private_key) if server.private_key else None
        
        conn = await ssh_pool.get_connection(server.ip, server.ssh_port, server.username, password, private_key)
        if not conn:
            for service in services:
                redis_client.set(f"service_status:{service.id}", "UNKNOWN", ex=12)
            continue
        
        for service in services:
            try:
                status = await check_service_status(service, server)
                redis_client.set(f"service_status:{service.id}", status, ex=12)
            except Exception as e:
                redis_client.set(f"service_status:{service.id}", "UNKNOWN", ex=12)
    
    await ssh_pool.close_idle_connections()

def get_service_status(service_id: int):
    status = redis_client.get(f"service_status:{service_id}")
    return status.decode() if status else "UNKNOWN"
