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

async def check_server_services(server: Server, db: Session):
    services = db.query(Service).filter(Service.server_id == server.id).all()
    if not services:
        return
    
    password = decrypt(server.password) if server.password else None
    private_key = decrypt(server.private_key) if server.private_key else None
    
    try:
        conn = await asyncio.wait_for(
            ssh_pool.get_connection(server.ip, server.ssh_port, server.username, password, private_key),
            timeout=5
        )
    except asyncio.TimeoutError:
        for service in services:
            redis_client.set(f"service_status:{service.id}", "UNKNOWN", ex=12)
        return
    except Exception:
        for service in services:
            redis_client.set(f"service_status:{service.id}", "UNKNOWN", ex=12)
        return
    
    if not conn:
        for service in services:
            redis_client.set(f"service_status:{service.id}", "UNKNOWN", ex=12)
        return
    
    try:
        for service in services:
            try:
                status = await asyncio.wait_for(
                    check_service_status(service, server),
                    timeout=3
                )
                redis_client.set(f"service_status:{service.id}", status, ex=12)
            except (asyncio.TimeoutError, Exception):
                redis_client.set(f"service_status:{service.id}", "UNKNOWN", ex=12)
    finally:
        conn.close()

async def update_all_service_statuses(db: Session):
    servers = db.query(Server).all()
    
    if not servers:
        return
    
    tasks = [check_server_services(server, db) for server in servers]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    await ssh_pool.close_idle_connections()

def get_service_status(service_id: int):
    status = redis_client.get(f"service_status:{service_id}")
    return status.decode() if status else "UNKNOWN"

async def start_process(process):
    import subprocess
    import os
    
    try:
        if process.work_dir:
            os.chdir(process.work_dir)
        
        if process.start_command:
            subprocess.Popen(
                process.start_command,
                shell=True,
                cwd=process.work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return True
        return False
    except Exception as e:
        print(f"Error starting process: {e}")
        return False

async def stop_process(process):
    import subprocess
    
    try:
        if process.stop_command:
            result = subprocess.run(
                process.stop_command,
                shell=True,
                cwd=process.work_dir,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        elif process.pid:
            result = subprocess.run(
                f"kill {process.pid}",
                shell=True,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        return False
    except Exception as e:
        print(f"Error stopping process: {e}")
        return False

async def restart_process(process):
    await stop_process(process)
    return await start_process(process)

async def check_process_status(process):
    import subprocess
    
    try:
        check_type = process.check_type
        check_keyword = process.check_keyword
        
        if check_type == "PROCESS":
            result = subprocess.run(
                f"ps -ef | grep {check_keyword} | grep -v grep",
                shell=True,
                capture_output=True,
                text=True
            )
            return "RUNNING" if result.returncode == 0 and result.stdout.strip() else "STOPPED"
        
        elif check_type == "PORT":
            result = subprocess.run(
                f"ss -lntp | grep :{check_keyword}",
                shell=True,
                capture_output=True,
                text=True
            )
            return "RUNNING" if result.returncode == 0 and result.stdout.strip() else "STOPPED"
        
        elif check_type == "PID" and process.pid:
            result = subprocess.run(
                f"ps -p {process.pid} -o comm=",
                shell=True,
                capture_output=True,
                text=True
            )
            return "RUNNING" if result.returncode == 0 and result.stdout.strip() else "STOPPED"
        
        elif check_type == "TCP" and process.ip and process.port:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            try:
                result = sock.connect_ex((process.ip, process.port))
                return "RUNNING" if result == 0 else "STOPPED"
            finally:
                sock.close()
        
        else:
            return "UNKNOWN"
    except Exception as e:
        print(f"Error checking process status: {e}")
        return "UNKNOWN"
