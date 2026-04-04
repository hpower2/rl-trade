"""Shared settings and safety guards."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "rl-trade"
    app_env: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_port: int = 5173
    api_auth_mode: Literal["disabled", "static_token"] = "disabled"
    api_auth_token: SecretStr | None = None
    api_auth_subject: str = "operator"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/rl_trade"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    worker_queues: str = "ingestion,preprocessing,supervised_training,rl_training,evaluation,trading,maintenance"
    worker_concurrency: int = Field(default=1, ge=1)
    worker_prefetch_multiplier: int = Field(default=1, ge=1)
    scheduler_heartbeat_interval_seconds: int = Field(default=60, ge=1)
    scheduler_max_interval_seconds: int = Field(default=10, ge=1)
    artifacts_root_dir: str = ".artifacts"

    mt5_terminal_path: str = "/opt/metatrader5/terminal64.exe"
    mt5_login: str | None = None
    mt5_password: SecretStr | None = None
    mt5_server: str | None = None

    paper_trading_only: bool = True
    allow_live_trading: bool = False
    model_approval_min_confidence: float = Field(default=70.0, ge=0.0, le=100.0)
    model_approval_min_risk_reward: float = Field(default=2.0, ge=0.0)
    model_approval_min_sample_size: int = Field(default=100, ge=1)
    model_approval_max_drawdown: float = Field(default=20.0, ge=0.0)

    @property
    def effective_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def effective_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @model_validator(mode="after")
    def enforce_safety_guards(self) -> "Settings":
        if not self.paper_trading_only:
            raise ValueError("paper_trading_only must remain enabled.")
        if self.allow_live_trading:
            raise ValueError("allow_live_trading must remain disabled.")
        if self.api_auth_mode == "disabled" and self.app_env in {"staging", "prod"}:
            raise ValueError("api_auth_mode cannot be disabled for staging or prod.")
        if self.api_auth_mode == "static_token":
            token = self.api_auth_token.get_secret_value().strip() if self.api_auth_token else ""
            if not token:
                raise ValueError("api_auth_token is required when api_auth_mode=static_token.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
