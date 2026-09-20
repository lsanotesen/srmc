from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    
    DATABASE_URL: str
    REDIS_URL: str
    
    AUDIT_LOG_RETENTION_DAYS: int = 90
    
    SSH_CONNECT_TIMEOUT: int = 10
    SSH_COMMAND_TIMEOUT: int = 30
    SSH_IDLE_TIMEOUT: int = 600
    SSH_RETRY_COUNT: int = 2

    # SSH 操作线程池大小。SSH 连接/执行命令/打开 SFTP 都是阻塞 IO，
    # 统一丢到该线程池执行。100 台 Agent 规模下建议不低于 64，
    # 否则慢连接会占满线程导致后续请求排队。
    SSH_POOL_MAX_WORKERS: int = 64

    # 端口检测线程池大小。端口检测超时 3s，批量检测时并发度需求较高。
    PORT_CHECK_MAX_WORKERS: int = 64

    # 通用阻塞任务线程池大小（心跳落库、审计日志等）。
    # 该池同时被 asyncio 默认 executor 复用，需覆盖心跳并发量。
    BLOCKING_POOL_MAX_WORKERS: int = 64

    BATCH_MAX_WORKERS: int = 5
    
    LOG_LEVEL: str = "INFO"
    
    AGENT_TOKEN: str = ""
    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
