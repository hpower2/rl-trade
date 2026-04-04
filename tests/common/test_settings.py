"""Safety and settings tests for the shared config layer."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rl_trade_common.settings import Settings


def test_settings_defaults_remain_safe() -> None:
    settings = Settings(_env_file=None)

    assert settings.paper_trading_only is True
    assert settings.allow_live_trading is False
    assert settings.model_approval_min_confidence == 70.0
    assert settings.model_approval_min_risk_reward == 2.0
    assert settings.model_approval_min_sample_size == 100
    assert settings.model_approval_max_drawdown == 20.0
    assert settings.artifacts_root_dir == ".artifacts"


def test_celery_urls_fall_back_to_redis() -> None:
    settings = Settings(_env_file=None, redis_url="redis://cache:6379/9")

    assert settings.effective_celery_broker_url == "redis://cache:6379/9"
    assert settings.effective_celery_result_backend == "redis://cache:6379/9"


def test_static_token_auth_requires_token() -> None:
    with pytest.raises(ValidationError, match="api_auth_token is required when api_auth_mode=static_token."):
        Settings(_env_file=None, api_auth_mode="static_token")


@pytest.mark.parametrize("app_env", ["staging", "prod"])
def test_non_local_environments_require_auth(app_env: str) -> None:
    with pytest.raises(ValidationError, match="api_auth_mode cannot be disabled for staging or prod."):
        Settings(_env_file=None, app_env=app_env, api_auth_mode="disabled")


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("paper_trading_only", False, "paper_trading_only must remain enabled."),
        ("allow_live_trading", True, "allow_live_trading must remain disabled."),
    ],
)
def test_settings_reject_unsafe_trading_flags(
    field_name: str,
    value: bool,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **{field_name: value})
