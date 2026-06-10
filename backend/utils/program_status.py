import socket
import asyncio
from utils.ssh_pool import ssh_pool
from utils.redis_client import get_redis
from core.config import settings
import os

async def check_port_status(ip: str, port: int) -> bool:
    """通过端口检测程序状态"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(settings.SSH_COMMAND_TIMEOUT)
        result = sock.connect_ex((str(ip), port))
        sock.close()
        return result == 0
    except Exception:
        return False

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
    """批量获取程序状态，按IP聚合优化"""
    result = {}
    
    # 按IP分组
    ip_groups = {}
    for prog in programs:
        ip = prog['ip']
        if ip not in ip_groups:
            ip_groups[ip] = []
        ip_groups[ip].append(prog)
    
    # 对每个IP分组批量检测
    for ip, progs in ip_groups.items():
        conn = None
        try:
            # 获取该IP的第一个程序的SSH信息（假设同一IP使用相同的用户名密码）
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
                    else:
                        # 主机部署：优先端口检测
                        if prog['port']:
                            if await check_port_status(ip, prog['port']):
                                status = "RUNNING"
                        else:
                            # SSH进程检测
                            if conn and prog['program_path']:
                                keyword = os.path.basename(prog['program_path'])
                                command = f"ps -ef | grep -E '{keyword}' | grep -v grep"
                                output, error, success = await conn.execute_command(command)
                                if success and output.strip() != '':
                                    status = "RUNNING"
                                else:
                                    status = "STOPPED"
                            else:
                                status = "STOPPED"
                except Exception as e:
                    status = "UNKNOWN"
                
                result[prog['id']] = status
                
                # 缓存状态到Redis
                try:
                    redis = get_redis()
                    if redis:
                        redis.setex(f"program_status:{prog['id']}", 12, status)
                except:
                    pass
        except Exception:
            for prog in progs:
                result[prog['id']] = "UNKNOWN"
        finally:
            # 不关闭连接，让连接池管理
            pass
    
    return result