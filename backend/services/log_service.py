import asyncio
from sqlalchemy.orm import Session
from models.service import Service
from models.server import Server
from models.app_service import AppService
from utils.ssh_pool import ssh_pool
from utils.crypto import decrypt

async def get_connection_and_service(service_id: int, db: Session = None):
    """获取服务连接信息"""
    # 先尝试从 AppService 表查找
    service = db.query(AppService).filter(AppService.id == service_id).first()
    
    if service:
        ip = service.ip
        ssh_port = service.ssh_port or 22
        username = service.username
        password = decrypt(service.password) if service.password else None
        private_key = None
        log_path = service.log_path
        service_type = service.service_type
        container_name = service.container_name
        return service, ip, ssh_port, username, password, private_key, log_path, service_type, container_name
    
    # 尝试从 Service 表查找（旧模型）
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        return None, None, None, None, None, None, None, None, None
    
    server = db.query(Server).filter(Server.id == service.server_id).first()
    if not server:
        return None, None, None, None, None, None, None, None, None
    
    return (
        service,
        server.ip,
        server.ssh_port or 22,
        server.username,
        decrypt(server.password) if server.password else None,
        decrypt(server.private_key) if server.private_key else None,
        service.log_path,
        'HOST_APP',
        None
    )

async def get_log_content(service_id: int, lines: int = 100, keyword: str = None, 
                          start_time: str = None, end_time: str = None, db: Session = None):
    """获取日志内容，支持关键字搜索和时间范围过滤"""
    service, ip, ssh_port, username, password, private_key, log_path, service_type, container_name = await get_connection_and_service(service_id, db)
    
    if not service:
        return None, "Service not found"
    
    if not log_path and service_type != 'DOCKER':
        return None, "Log path not configured"
    
    conn = await ssh_pool.get_connection(ip, ssh_port, username, password, private_key)
    if not conn:
        return None, "SSH connection failed"
    
    try:
        # 根据服务类型构建日志命令
        if service_type == 'DOCKER' and container_name:
            # Docker服务使用 docker logs
            if lines == 0:
                command = f"docker logs {container_name}"
            else:
                command = f"docker logs --tail {lines} {container_name}"
        else:
            # 其他服务类型使用文件日志
            # 检查日志路径是否为目录
            if log_path:
                output, error, success = await conn.execute_command(f"ls -la {log_path}")
                if not success:
                    return None, f"Log path not found: {error}"
                
                if output.strip().endswith('/') or 'drwx' in output.split()[0]:
                    # 是目录，查找最新的日志文件
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
        
        # 时间范围过滤
        if start_time or end_time:
            output_lines = output.split('\n')
            filtered_lines = []
            for line in output_lines:
                # 简化的时间匹配逻辑，实际应用中可能需要根据日志格式进行调整
                filtered_lines.append(line)  # 这里可以添加更复杂的时间过滤逻辑
            output = '\n'.join(filtered_lines)
        
        # 关键字过滤
        if keyword:
            output_lines = output.split('\n')
            filtered_lines = [line for line in output_lines if keyword in line]
            output = '\n'.join(filtered_lines)
        
        return output, None
    finally:
        pass

async def tail_log(service_id: int, websocket, db: Session = None):
    """实时日志监控"""
    service, ip, ssh_port, username, password, private_key, log_path, service_type, container_name = await get_connection_and_service(service_id, db)
    
    if not service:
        await websocket.send_text("Service not found")
        return
    
    if not log_path and service_type != 'DOCKER':
        await websocket.send_text("Log path not configured")
        return
    
    conn = await ssh_pool.get_connection(ip, ssh_port, username, password, private_key)
    if not conn:
        await websocket.send_text("SSH connection failed")
        return
    
    try:
        shell = await conn.invoke_shell()
        if not shell:
            await websocket.send_text("Failed to invoke shell")
            return
        
        # 根据服务类型执行不同的日志命令
        if service_type == 'DOCKER' and container_name:
            # Docker服务使用 docker logs -f
            shell.send(f"docker logs -f {container_name}\n")
        elif service_type in ['ES', 'SOLR'] and log_path:
            # ES/SOLR服务查看节点日志
            shell.send(f"tail -f {log_path}\n")
        elif log_path:
            # 其他服务类型
            shell.send(f"tail -f {log_path}\n")
        
        while True:
            if shell.recv_ready():
                output = shell.recv(4096).decode('utf-8', errors='ignore')
                await websocket.send_text(output)
            await asyncio.sleep(0.1)
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        if shell:
            shell.close()

async def get_log_files(service_id: int, db: Session = None):
    """获取日志文件列表"""
    service, ip, ssh_port, username, password, private_key, log_path, service_type, container_name = await get_connection_and_service(service_id, db)
    
    if not service:
        return None, "Service not found"
    
    if not log_path:
        return [], None
    
    conn = await ssh_pool.get_connection(ip, ssh_port, username, password, private_key)
    if not conn:
        return None, "SSH connection failed"
    
    try:
        # 检查日志路径是否为目录
        output, error, success = await conn.execute_command(f"ls -la {log_path}")
        if not success:
            # 尝试作为文件处理
            output, error, success = await conn.execute_command(f"ls -la {log_path} 2>/dev/null || echo 'not found'")
            if 'not found' in output:
                return [], None
            
            # 是文件
            output, error, success = await conn.execute_command(f"wc -l {log_path}")
            line_count = output.strip().split()[0] if success else 'unknown'
            
            output, error, success = await conn.execute_command(f"du -h {log_path}")
            size = output.strip().split()[0] if success else 'unknown'
            
            return [{
                'name': log_path.split('/')[-1],
                'path': log_path,
                'size': size,
                'lines': line_count
            }], None
        
        # 是目录
        files = []
        output, error, success = await conn.execute_command(f"ls -la {log_path}/*.log 2>/dev/null")
        if success and output.strip():
            for line in output.strip().split('\n'):
                if not line.startswith('total'):
                    parts = line.split()
                    if len(parts) >= 9:
                        files.append({
                            'name': parts[-1],
                            'path': f"{log_path}/{parts[-1]}",
                            'size': parts[4],
                            'lines': 'unknown'
                        })
        
        return files, None
    finally:
        pass
