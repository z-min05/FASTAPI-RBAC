from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    APP_NAME: str = "FastAPI-RBAC"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://postgres:123456@localhost:5432/fastapi_rbac"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 跨域
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:8080"]'

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_FILE_ENABLED: bool = True
    LOG_FILE_DIR: str = "logs"
    LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_FILE_BACKUP_COUNT: int = 5

    # ==================== Agent（AI 助手） ====================
    # V2：LLM/Agent 全部平台化入库管理，不再使用 AGENT_LLM_* 等 env 配置；
    # 仅保留总开关与单轮推理超时。
    AGENT_ENABLED: bool = False
    AGENT_INVOKE_TIMEOUT: int = 180

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
