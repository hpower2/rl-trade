"""Shared model approval and tradeability gate helpers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from rl_trade_common import Settings
from rl_trade_data import ApprovedModel
from rl_trade_data.models import ModelType


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    approved: bool
    reasons: tuple[str, ...]
    confidence: float
    risk_to_reward: float
    sample_size: int
    max_drawdown: float | None
    has_critical_data_issue: bool
    min_confidence: float
    min_risk_reward: float
    min_sample_size: int
    max_approved_drawdown: float


def evaluate_model_approval(
    *,
    settings: Settings,
    confidence: float,
    risk_to_reward: float,
    sample_size: int,
    max_drawdown: float | None,
    has_critical_data_issue: bool,
) -> ApprovalDecision:
    reasons: list[str] = []
    if confidence < settings.model_approval_min_confidence:
        reasons.append("confidence_below_threshold")
    if risk_to_reward < settings.model_approval_min_risk_reward:
        reasons.append("risk_to_reward_below_threshold")
    if sample_size < settings.model_approval_min_sample_size:
        reasons.append("insufficient_sample_size")
    if max_drawdown is not None and max_drawdown > settings.model_approval_max_drawdown:
        reasons.append("drawdown_above_threshold")
    if has_critical_data_issue:
        reasons.append("critical_data_issue")

    return ApprovalDecision(
        approved=not reasons,
        reasons=tuple(reasons),
        confidence=confidence,
        risk_to_reward=risk_to_reward,
        sample_size=sample_size,
        max_drawdown=max_drawdown,
        has_critical_data_issue=has_critical_data_issue,
        min_confidence=settings.model_approval_min_confidence,
        min_risk_reward=settings.model_approval_min_risk_reward,
        min_sample_size=settings.model_approval_min_sample_size,
        max_approved_drawdown=settings.model_approval_max_drawdown,
    )


def is_symbol_tradeable(
    session: Session,
    *,
    symbol_id: int,
    model_type: ModelType | None = None,
) -> bool:
    return get_active_approved_model(session, symbol_id=symbol_id, model_type=model_type) is not None


def get_active_approved_model(
    session: Session,
    *,
    symbol_id: int,
    model_type: ModelType | None = None,
) -> ApprovedModel | None:
    statement = select(ApprovedModel).where(
        ApprovedModel.symbol_id == symbol_id,
        ApprovedModel.is_active.is_(True),
        ApprovedModel.revoked_at.is_(None),
    )
    if model_type is not None:
        statement = statement.where(ApprovedModel.model_type == model_type.value)
    statement = statement.order_by(ApprovedModel.approved_at.desc())
    return session.execute(statement).scalars().first()


def normalize_decimal(value: Decimal | float | int | str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))
