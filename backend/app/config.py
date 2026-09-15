from pydantic_settings import BaseSettings
from typing import List
import json
import os


class Settings(BaseSettings):
    APP_NAME: str = "FastAPI-RBAC"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://postgres:123456@localhost:5432/fastapi_rbac"

    # Redis
    # 注意：Windows 下 Redis 通常只监听 IPv4，用 localhost 会先解析到 ::1 导致连接超时
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

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
    # 仅保留总开关、单轮推理超时与 bash 工具的工作目录根。
    AGENT_ENABLED: bool = False
    AGENT_INVOKE_TIMEOUT: int = 180
    # bash 工具的顶层工作目录（沙箱根）。每个 Agent 的工作目录固定为
    # {该目录}/user_<用户ID>/agent_<AgentID>，创建 Agent 时自动创建，
    # 用户无需也不能指定。留空则默认取 backend/agent_workspaces。
    AGENT_WORKSPACE_ROOT: str = ""

    # LLM 请求的限流退避：供应商返回 429（TPM/RPM 超限）时按 initial * 2^n 重试，
    # 单次等待上限 RETRY_MAX_DELAY，服务端返回 Retry-After 时优先遵循。
    # openai SDK 默认只有 0.5s*2^n（单次上限 8s），对按分钟计的配额窗口往往不够。
    # 0 次即沿用 SDK 默认退避；修改后需重建 Agent 实例（重启服务）生效。
    AGENT_LLM_MAX_RETRIES: int = 3
    AGENT_LLM_RETRY_INITIAL_DELAY: float = 5.0
    AGENT_LLM_RETRY_MAX_DELAY: float = 30.0

    # ==================== 定时执行（调度器，随应用进程内嵌运行） ====================
    # 多 worker 场景下"到点判定/认领"已 DB 化（条件更新），不会重复触发
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TICK_SECONDS: int = 30
    # 任务运行超时阈值：超过该时长仍标记 running 视为僵尸并自动复位
    SCHEDULER_ZOMBIE_TIMEOUT_HOURS: int = 4

    # ==================== 自动化用例执行 ====================
    # 单个 pytest 用例执行超时（秒）；超过则强杀子进程并记为失败。
    # 部分用例（如 OTA 升级、组网、长距离测试）耗时远超 120s，可按需调大
    EXEC_TIMEOUT_SECONDS: int = 120

    # ==================== 企业微信机器人通知 ====================
    # 推送消息中"查看完整报告"链接的前缀（如 http://127.0.0.1:8080），为空则不附加链接
    NOTIFY_FRONTEND_URL: str | None = None

    # ==================== Python 环境管理（Miniconda） ====================
    # 环境一律以 `conda create -p <path>`（prefix 模式）创建，路径完全由
    # CONDA_ENV_ROOT 决定，不写入 Miniconda 自带的 envs 目录。
    CONDA_ENABLED: bool = False
    # Miniconda 安装根目录（用于推导 conda 可执行文件）
    CONDA_HOME: str | None = None
    # conda 可执行文件显式路径；非空时优先于 CONDA_HOME 推导
    CONDA_EXE: str | None = None
    # 虚拟环境存放根目录；为空视为未配置，创建环境时直接报错
    CONDA_ENV_ROOT: str = ""
    # 单条 conda 命令超时（秒）；首次创建环境可能耗时数分钟
    CONDA_CMD_TIMEOUT: int = 600
    # 可供选择的 Python 版本（逗号分隔），供创建环境时下拉
    CONDA_PYTHON_VERSIONS: str = "3.9,3.10,3.11,3.12"

    # ==================== 项目自动化代码初始化 ====================
    # 全局自动化根目录：所有项目的代码包统一解压到此目录下。
    # 需预先存在且可写；每个项目的 auto_root_path = {BASE_DIR}/<项目目录名>/tests
    # 为空视为未配置，上传代码包时直接报错
    PROJECT_CODE_BASE_DIR: str = ""
    # 上传 zip 大小上限（MB）
    PROJECT_CODE_UPLOAD_MAX_MB: int = 200
    # 解压后总体积上限（MB），防 zip bomb
    PROJECT_CODE_MAX_UNCOMPRESSED_MB: int = 2000
    # 压缩包条目数上限
    PROJECT_CODE_MAX_FILES: int = 20000
    # pip install 超时（秒）；依赖较多时可能很久
    PROJECT_CODE_INIT_TIMEOUT: int = 1800
    # 上传临时目录；为空则使用系统临时目录
    PROJECT_CODE_TMP_DIR: str = ""

    # ==================== 加密（api_key 敏感字段） ====================
    # 用于 Fernet 对称加密；生产环境务必更换为随机 base64 字符串（32 bytes url-safe base64）。
    ENCRYPTION_KEY: str = "D4GbYVEXicX0l9ckg9UwP1LavrUEfkgJex5yJRx4T_s="

    @property
    def agent_workspace_root(self) -> str:
        """bash 工具顶层工作目录；未配置时取 backend 目录下的 agent_workspaces"""
        raw = (self.AGENT_WORKSPACE_ROOT or "").strip()
        if raw:
            return raw
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(backend_dir, "agent_workspaces")

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

    @property
    def conda_exe(self) -> str | None:
        """conda 可执行文件路径：CONDA_EXE 优先，否则由 CONDA_HOME 按平台推导"""
        if self.CONDA_EXE:
            return self.CONDA_EXE
        if not self.CONDA_HOME:
            return None
        if os.name == "nt":
            return os.path.join(self.CONDA_HOME, "Scripts", "conda.exe")
        return os.path.join(self.CONDA_HOME, "bin", "conda")

    @property
    def conda_python_versions(self) -> List[str]:
        """可选的 Python 版本列表（配置文件逗号分隔）"""
        return [v.strip() for v in self.CONDA_PYTHON_VERSIONS.split(",") if v.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
