import asyncio
from datetime import datetime
import paramiko
import stat
from core.config import settings
from concurrent.futures import ThreadPoolExecutor

# 创建线程池，避免阻塞事件循环
executor = ThreadPoolExecutor(max_workers=10)

class SSHConnection:
    def __init__(self, host, port, username, password=None, private_key=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.client = None
        self.last_used = datetime.now()
        self.shell = None
    
    def _connect_sync(self):
        """同步连接方法，将在线程池中执行"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.private_key:
                key = paramiko.RSAKey(data=paramiko.base64.decodebytes(self.private_key.encode()))
                self.client.connect(
                    self.host, 
                    port=self.port, 
                    username=self.username, 
                    pkey=key,
                    timeout=settings.SSH_CONNECT_TIMEOUT,
                    banner_timeout=10,
                    auth_timeout=10,
                    look_for_keys=False,
                    allow_agent=False
                )
            else:
                self.client.connect(
                    self.host, 
                    port=self.port, 
                    username=self.username, 
                    password=self.password,
                    timeout=settings.SSH_CONNECT_TIMEOUT,
                    banner_timeout=10,
                    auth_timeout=10,
                    look_for_keys=False,
                    allow_agent=False
                )
            self.last_used = datetime.now()
            return True
        except Exception as e:
            if self.client:
                try:
                    self.client.close()
                except:
                    pass
                self.client = None
            return False
    
    async def connect(self):
        """异步连接方法，使用线程池执行同步操作"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, self._connect_sync)
    
    async def execute_command(self, command):
        if not self.client or not self.client.get_transport().is_active():
            if not await self.connect():
                return None, None, False
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=settings.SSH_COMMAND_TIMEOUT)
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')
            self.last_used = datetime.now()
            return output, error, True
        except Exception as e:
            return None, str(e), False
    
    def _invoke_shell_sync(self, term_type='xterm', width=80, height=24):
        """同步创建shell，将在线程池中执行"""
        try:
            if not self.client:
                return None
            transport = self.client.get_transport()
            if not transport or not transport.is_active():
                return None
            
            # 使用transport打开session并请求PTY
            self.shell = transport.open_session()
            # 请求PTY伪终端
            self.shell.get_pty(
                term=term_type,
                width=width,
                height=height,
                width_pixels=width * 8,
                height_pixels=height * 24
            )
            # 启动shell
            self.shell.invoke_shell()
            self.shell.settimeout(0.05)
            self.last_used = datetime.now()
            return self.shell
        except Exception as e:
            return None
    
    async def invoke_shell(self, term_type='xterm', width=80, height=24):
        """异步创建shell，使用线程池执行同步操作"""
        if not self.client:
            if not await self.connect():
                return None
        transport = self.client.get_transport()
        if not transport or not transport.is_active():
            if not await self.connect():
                return None
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, self._invoke_shell_sync, term_type, width, height)
    
    def _open_sftp_sync(self):
        """同步打开SFTP会话"""
        try:
            if not self.client or not self.client.get_transport().is_active():
                return None
            self.sftp = self.client.open_sftp()
            return self.sftp
        except Exception as e:
            return None
    
    async def open_sftp(self):
        """异步打开SFTP会话"""
        if not self.client:
            if not await self.connect():
                return None
        transport = self.client.get_transport()
        if not transport or not transport.is_active():
            if not await self.connect():
                return None
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, self._open_sftp_sync)
    
    async def sftp_upload(self, local_path, remote_path):
        """上传文件"""
        sftp = await self.open_sftp()
        if not sftp:
            return False, "无法打开SFTP连接"
        
        try:
            sftp.put(local_path, remote_path)
            self.last_used = datetime.now()
            return True, "上传成功"
        except Exception as e:
            return False, str(e)
        finally:
            try:
                sftp.close()
            except:
                pass
    
    async def sftp_download(self, remote_path, local_path):
        """下载文件"""
        sftp = await self.open_sftp()
        if not sftp:
            return False, "无法打开SFTP连接"
        
        try:
            sftp.get(remote_path, local_path)
            self.last_used = datetime.now()
            return True, "下载成功"
        except Exception as e:
            return False, str(e)
        finally:
            try:
                sftp.close()
            except:
                pass
    
    async def sftp_listdir(self, remote_path='.'):
        """列出目录内容"""
        sftp = await self.open_sftp()
        if not sftp:
            return None, "无法打开SFTP连接"
        
        try:
            files = sftp.listdir_attr(remote_path)
            result = []
            
            # 添加父目录（..），但根目录不需要
            if remote_path != '/' and remote_path != '.':
                result.append({
                    'filename': '..',
                    'size': 0,
                    'modify_time': 0,
                    'is_directory': True
                })
            
            for f in files:
                result.append({
                    'filename': f.filename,
                    'size': f.st_size,
                    'modify_time': f.st_mtime,
                    'is_directory': stat.S_ISDIR(f.st_mode)
                })
            self.last_used = datetime.now()
            return result, None
        except Exception as e:
            return None, str(e)
        finally:
            try:
                sftp.close()
            except:
                pass
    
    def close(self):
        if self.shell:
            try:
                self.shell.close()
            except:
                pass
            self.shell = None
        if hasattr(self, 'sftp') and self.sftp:
            try:
                self.sftp.close()
            except:
                pass
            self.sftp = None
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None

    def is_idle(self):
        return (datetime.now() - self.last_used).seconds > settings.SSH_IDLE_TIMEOUT

class SSHConnectionPool:
    def __init__(self):
        self.pool = {}
        self.lock = asyncio.Lock()
    
    async def get_connection(self, host, port, username, password=None, private_key=None):
        key = (host, port, username)
        
        async with self.lock:
            if key in self.pool:
                conn = self.pool[key]
                if conn.is_idle():
                    conn.close()
                    del self.pool[key]
                else:
                    conn.last_used = datetime.now()
                    return conn
            
            conn = SSHConnection(host, port, username, password, private_key)
            if await conn.connect():
                self.pool[key] = conn
                return conn
            return None
    
    async def close_idle_connections(self):
        async with self.lock:
            keys_to_remove = []
            for key, conn in self.pool.items():
                if conn.is_idle():
                    conn.close()
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.pool[key]
    
    async def close_all(self):
        async with self.lock:
            for conn in self.pool.values():
                conn.close()
            self.pool.clear()

ssh_pool = SSHConnectionPool()