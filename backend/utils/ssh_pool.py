import asyncio
from datetime import datetime
import paramiko
from core.config import settings

class SSHConnection:
    def __init__(self, host, port, username, password=None, private_key=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.client = None
        self.last_used = datetime.now()
    
    async def connect(self):
        for attempt in range(settings.SSH_RETRY_COUNT + 1):
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
                        timeout=settings.SSH_CONNECT_TIMEOUT
                    )
                else:
                    self.client.connect(
                        self.host, 
                        port=self.port, 
                        username=self.username, 
                        password=self.password,
                        timeout=settings.SSH_CONNECT_TIMEOUT
                    )
                self.last_used = datetime.now()
                return True
            except Exception as e:
                if attempt < settings.SSH_RETRY_COUNT:
                    await asyncio.sleep(1)
                    continue
                return False
    
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
    
    async def invoke_shell(self):
        if not self.client or not self.client.get_transport().is_active():
            if not await self.connect():
                return None
        
        try:
            shell = self.client.invoke_shell()
            self.last_used = datetime.now()
            return shell
        except Exception as e:
            return None
    
    def close(self):
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
