from abc import ABC, abstractmethod
import asyncio
import aiomysql
import psycopg2
import json

class DatabaseConnector(ABC):
    @abstractmethod
    async def connect(self):
        pass
    
    @abstractmethod
    async def execute(self, sql):
        pass
    
    @abstractmethod
    async def fetch_databases(self):
        pass
    
    @abstractmethod
    async def fetch_users(self):
        pass
    
    @abstractmethod
    async def close(self):
        pass

class MySQLConnector(DatabaseConnector):
    def __init__(self, host, port, username, password, database=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.conn = None
    
    async def connect(self):
        try:
            self.conn = await aiomysql.connect(
                host=self.host,
                port=self.port,
                user=self.username,
                password=self.password,
                db=self.database,
                autocommit=True
            )
            return True
        except Exception as e:
            return False
    
    async def execute(self, sql):
        if not self.conn:
            await self.connect()
        
        try:
            async with self.conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql)
                if sql.strip().upper().startswith('SELECT'):
                    result = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    return {'columns': columns, 'data': result, 'rows_affected': len(result)}
                else:
                    rows_affected = cursor.rowcount
                    return {'columns': [], 'data': [], 'rows_affected': rows_affected}
        except Exception as e:
            return {'error': str(e)}
    
    async def fetch_databases(self):
        result = await self.execute('SHOW DATABASES')
        if 'error' in result:
            return []
        return [row['Database'] for row in result['data']]
    
    async def fetch_users(self):
        result = await self.execute("SELECT user, host FROM mysql.user")
        if 'error' in result:
            return []
        return result['data']
    
    async def close(self):
        if self.conn:
            self.conn.close()

class KingbaseConnector(DatabaseConnector):
    def __init__(self, host, port, username, password, database=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database or 'postgres'
        self.conn = None
    
    async def connect(self):
        try:
            loop = asyncio.get_event_loop()
            self.conn = await loop.run_in_executor(None, psycopg2.connect, 
                f"host={self.host} port={self.port} dbname={self.database} user={self.username} password={self.password}"
            )
            return True
        except Exception as e:
            return False
    
    async def execute(self, sql):
        if not self.conn:
            await self.connect()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
            if sql.strip().upper().startswith('SELECT'):
                result = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                return {'columns': columns, 'data': result, 'rows_affected': len(result)}
            else:
                self.conn.commit()
                rows_affected = cursor.rowcount
                return {'columns': [], 'data': [], 'rows_affected': rows_affected}
        except Exception as e:
            return {'error': str(e)}
    
    async def fetch_databases(self):
        result = await self.execute("SELECT datname FROM pg_database WHERE datistemplate = false")
        if 'error' in result:
            return []
        return [row[0] for row in result['data']]
    
    async def fetch_users(self):
        result = await self.execute("SELECT usename FROM pg_user")
        if 'error' in result:
            return []
        return [{'user': row[0], 'host': 'localhost'} for row in result['data']]
    
    async def close(self):
        if self.conn:
            self.conn.close()

class DamengConnector(DatabaseConnector):
    def __init__(self, host, port, username, password, database=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.conn = None
    
    async def connect(self):
        try:
            import dmPython
            loop = asyncio.get_event_loop()
            self.conn = await loop.run_in_executor(None, dmPython.connect,
                f"host={self.host};port={self.port};user={self.username};password={self.password}"
            )
            return True
        except Exception as e:
            return False
    
    async def execute(self, sql):
        if not self.conn:
            await self.connect()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
            if sql.strip().upper().startswith('SELECT'):
                result = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                return {'columns': columns, 'data': result, 'rows_affected': len(result)}
            else:
                self.conn.commit()
                rows_affected = cursor.rowcount
                return {'columns': [], 'data': [], 'rows_affected': rows_affected}
        except Exception as e:
            return {'error': str(e)}
    
    async def fetch_databases(self):
        result = await self.execute("SELECT name FROM v$database")
        if 'error' in result:
            return []
        return [row[0] for row in result['data']]
    
    async def fetch_users(self):
        result = await self.execute("SELECT username FROM dba_users")
        if 'error' in result:
            return []
        return [{'user': row[0], 'host': 'localhost'} for row in result['data']]
    
    async def close(self):
        if self.conn:
            self.conn.close()

class DatabaseConnectorFactory:
    @staticmethod
    def create_connector(service_type, host, port, extra_config):
        config = json.loads(extra_config) if extra_config else {}
        username = config.get('username', '')
        password = config.get('password', '')
        database = config.get('database', '')
        
        if service_type == 'MYSQL':
            return MySQLConnector(host, port, username, password, database)
        elif service_type == 'KINGBASE':
            return KingbaseConnector(host, port, username, password, database)
        elif service_type == 'DAMENG':
            return DamengConnector(host, port, username, password, database)
        return None
