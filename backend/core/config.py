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
    
    BATCH_MAX_WORKERS: int = 5
    
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
