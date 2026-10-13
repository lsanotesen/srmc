import socket
import asyncio
from utils.ssh_pool import ssh_pool
from utils.redis_client import get_redis
from core.config import settings
import os
from concurrent.futures import ThreadPoolExecutor

# 独立线程池用于端口检测，避免阻塞 event loop
port_check_executor = ThreadPoolExecutor(max_workers=settings.PORT_CHECK_MAX_WORKERS)

def _check_port_sync(ip: str, port: int) -> bool:
    """同步端口检测（在线程池中执行，不阻塞 event loop）"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)  # 缩短端口检测超时从 30s 到 3s
        result = sock.connect_ex((str(ip), port))
        sock.close()
        return result == 0
    except Exception:
        return False

async def execute_command_with_retry(conn, command, max_retries=2):
    """执行SSH命令，支持重试"""
    for attempt in range(max_retries):
        output, error, success = await conn.execute_command(command)
        if success:
            return output, error, success
        await asyncio.sleep(0.5)
    return "", "Command failed after retries", False

async def check_port_status(ip: str, port: int) -> bool:
    """通过端口检测程序状态（线程池执行，不阻塞 event loop）"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(port_check_executor, _check_port_sync, ip, port)

async def check_process_by_ssh(ip: str, username: str, password: str, program_path: str, ssh_port: int = 22) -> bool:
    """通过SSH执行ps命令检测程序状态"""
    try:
        # 从程序路径提取关键词
        keyword = os.path.basename(program_path)
        if not keyword:
            keyword = os.path.basename(os.path.dirname(program_path))
        
        conn = await ssh_pool.get_connection(ip, ssh_port, username, password)
        if not conn:
            return False
        
        command = f"ps -ef | grep -E '{keyword}' | grep -v grep"
        output, error, success = await conn.execute_command(command)
        return success and output.strip() != ''
    except Exception:
        return False

async def check_docker_container(ip: str, username: str, password: str, container_name: str, ssh_port: int = 22) -> bool:
    """通过SSH检测Docker容器状态"""
    try:
        conn = await ssh_pool.get_connection(ip, ssh_port, username, password)
        if not conn:
            return False
        
        # 检查容器是否运行
        command = f"docker inspect -f '{{{{.State.Running}}}}' {container_name} 2>/dev/null"
        output, error, success = await conn.execute_command(command)
        if success and output.strip() == 'true':
            return True
        
        # 如果容器名称为空，尝试通过docker-compose检测
        if not container_name:
            command = "docker-compose ps -q"
            output, error, success = await conn.execute_command(command)
            return success and output.strip() != ''
        
        return False
    except Exception:
        return False

async def get_program_status(ip: str, username: str, password: str, port: int = None, program_path: str = None, ssh_port: int = 22, deploy_type: str = 'HOST', container_name: str = None) -> str:
    """获取单个程序状态"""
    try:
        # Docker部署优先检测容器状态
        if deploy_type == 'DOCKER':
            if await check_docker_container(ip, username, password, container_name, ssh_port):
                return "RUNNING"
            return "STOPPED"
        
        # 优先检测端口
        if port:
            if await check_port_status(ip, port):
                return "RUNNING"
        
        # 端口检测失败或无端口，尝试SSH检测
        if program_path and username and password:
            if await check_process_by_ssh(ip, username, password, program_path, ssh_port):
                return "RUNNING"
        
        return "STOPPED"
    except Exception:
        return "UNKNOWN"

async def get_batch_program_status(programs: list) -> dict:
    """批量获取程序状态，按IP聚合并发优化"""
    result = {}
    
    # 按IP分组
    ip_groups = {}
    for prog in programs:
        ip = prog['ip']
        if ip not in ip_groups:
            ip_groups[ip] = []
        ip_groups[ip].append(prog)
    
    # 并发处理每个IP分组（最多5个并发，避免SSH连接风暴）
    sem = asyncio.Semaphore(5)
    
    async def process_ip_group(ip, progs):
        async with sem:
            return await _process_ip_services(ip, progs)
    
    # 并发执行所有IP分组
    tasks = [process_ip_group(ip, progs) for ip, progs in ip_groups.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 合并结果
    for ip_result in results:
        if isinstance(ip_result, dict):
            result.update(ip_result)
    
    return result

async def _process_ip_services(ip, progs):
    """处理单个 IP 下的所有服务"""
    result = {}
    conn = None
    try:
        first_prog = progs[0]
        ssh_port = first_prog.get('ssh_port', 22)
        conn = await ssh_pool.get_connection(ip, ssh_port, first_prog['username'], first_prog['password'])
        
        for prog in progs:
            status = "UNKNOWN"
            try:
                # Docker部署优先检测容器状态
                deploy_type = prog.get('deploy_type', 'HOST')
                if deploy_type == 'DOCKER':
                    container_name = prog.get('container_name', '')
                    if conn:
                        if container_name:
                            command = f"docker inspect -f '{{{{.State.Running}}}}' {container_name} 2>/dev/null"
                            output, error, success = await conn.execute_command(command)
                            if success and output.strip() == 'true':
                                status = "RUNNING"
                            else:
                                status = "STOPPED"
                        else:
                            # 无容器名称，尝试通过docker-compose检测
                            command = "docker-compose ps -q"
                            output, error, success = await conn.execute_command(command)
                            if success and output.strip() != '':
                                status = "RUNNING"
                            else:
                                status = "STOPPED"
                elif deploy_type == 'DOCKER_COMPOSE':
                    # Docker Compose部署：检测compose项目状态
                    if conn:
                        program_path = prog.get('program_path', '')
                        if program_path:
                            command = f"cd {program_path} && docker-compose ps -q 2>/dev/null || docker compose ps -q 2>/dev/null"
                        else:
                            command = "docker-compose ps -q 2>/dev/null || docker compose ps -q 2>/dev/null"
                        output, error, success = await conn.execute_command(command)
                        if success and output.strip() != '':
                            status = "RUNNING"
                        else:
                            status = "STOPPED"
                else:
                    # 主机部署：优先脚本解析，端口检测为辅
                    if conn and prog['program_path']:
                        program_path = prog['program_path']
                        if program_path.startswith('~'):
                            program_path = program_path.replace('~', '/home/' + first_prog['username'])
                        
                        base_dir = os.path.dirname(program_path)
                        
                        # 策略1：解析 start.sh 获取真实启动命令和端口
                        start_sh_path = os.path.join(base_dir, 'start.sh')
                        start_command = f"cat {start_sh_path} 2>/dev/null | head -50"
                        output, error, success = await execute_command_with_retry(conn, start_command)
                        if success and output.strip() != '':
                            import re
                            start_content = output.strip()
                            
                            # 从 start.sh 提取端口
                            port_match = re.search(r'-p\s+(\d+)|--port\s+(\d+)|port=(\d+)', start_content)
                            if port_match:
                                extracted_port = port_match.group(1) or port_match.group(2) or port_match.group(3)
                                if extracted_port and extracted_port.isdigit():
                                    if await check_port_status(ip, int(extracted_port)):
                                        status = "RUNNING"
                                    else:
                                        ssh_port_command = f"netstat -tlnp 2>/dev/null | grep ': {extracted_port} ' || ss -tlnp 2>/dev/null | grep ': {extracted_port} '"
                                        p_output, p_error, p_success = await execute_command_with_retry(conn, ssh_port_command)
                                        if p_success and p_output.strip() != '':
                                            status = "RUNNING"
                                
                            # 从 start.sh 提取启动命令（java/python/node等）
                            if status != "RUNNING":
                                exec_match = re.search(r'(java|python|node|npm)\s+(.+)', start_content)
                                if exec_match:
                                    exec_keyword = exec_match.group(1)
                                    args = exec_match.group(2)
                                    jar_match = re.search(r'(\S+\.jar)', args)
                                    py_match = re.search(r'(\S+\.py)', args)
                                    if jar_match:
                                        exec_keyword = jar_match.group(1)
                                    elif py_match:
                                        exec_keyword = py_match.group(1)
                                    ps_command = f"ps -ef | grep '{exec_keyword}' | grep -v grep"
                                    p_output, p_error, p_success = await execute_command_with_retry(conn, ps_command)
                                    if p_success and p_output.strip() != '':
                                        status = "RUNNING"
                            
                        # 策略2：完整路径匹配
                        if status != "RUNNING":
                            full_path_command = f"ps -ef | grep '{program_path}' | grep -v grep"
                            output, error, success = await execute_command_with_retry(conn, full_path_command)
                            if success and output.strip() != '':
                                status = "RUNNING"
                            
                        # 策略3：端口检测（配置的端口）
                        if status != "RUNNING" and prog['port']:
                            ports = str(prog['port']).split(',')
                            for port in ports:
                                port = port.strip()
                                if port.isdigit():
                                    if await check_port_status(ip, int(port)):
                                        status = "RUNNING"
                                        break
                                    else:
                                        ssh_port_command = f"netstat -tlnp 2>/dev/null | grep ': {port} ' || ss -tlnp 2>/dev/null | grep ': {port} '"
                                        p_output, p_error, p_success = await execute_command_with_retry(conn, ssh_port_command)
                                        if p_success and p_output.strip() != '':
                                            status = "RUNNING"
                                            break
                                
                        # 策略4：父目录名匹配（兜底）
                        if status != "RUNNING":
                            keyword = os.path.basename(base_dir)
                            if keyword in ['server', 'client', 'bin', 'app']:
                                keyword = os.path.basename(os.path.dirname(base_dir))
                            parent_command = f"ps -ef | grep '{keyword}' | grep -v grep"
                            output, error, success = await execute_command_with_retry(conn, parent_command)
                            if success and output.strip() != '':
                                status = "RUNNING"
                            else:
                                status = "STOPPED"
                    else:
                        status = "STOPPED"
            except Exception as e:
                status = "UNKNOWN"
            
            result[prog['id']] = status

            # 【已移除】此处曾将 SSH 检测结果写入 service_status:{id} /
            # service_status_source:{id}，与 Agent 心跳写入的 key 完全重合，
            # 会覆盖 Agent 上报的真实状态并伪标来源为 'SSH'。
            # 状态缓存只能由 Agent 心跳与断连清理写入，本函数仅返回查询结果。
    except Exception:
        for prog in progs:
            result[prog['id']] = "UNKNOWN"
    finally:
        # 不关闭连接，让连接池管理
        pass
    
    return result