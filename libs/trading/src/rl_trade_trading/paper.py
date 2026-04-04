"""Paper-trading backend gating helpers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from rl_trade_common import Settings
from rl_trade_data import ApprovedModel
from rl_trade_data.models import ConnectionStatus, ModelType, TradeSide
from rl_trade_trading.approval import get_active_approved_model
from rl_trade_trading.mt5 import MT5ConnectionState


@dataclass(frozen=True, slots=True)
class PaperTradeDecision:
    allowed: bool
    reasons: tuple[str, ...]
    approved_model: ApprovedModel | None
    symbol_id: int
    model_type: ModelType | None
    confidence: float
    risk_to_reward: float


def calculate_risk_to_reward(
    *,
    side: TradeSide,
    entry_price: Decimal | float | int | str,
    stop_loss: Decimal | float | int | str,
    take_profit: Decimal | float | int | str,
) -> float:
    entry = Decimal(str(entry_price))
    stop = Decimal(str(stop_loss))
    target = Decimal(str(take_profit))

    if side is TradeSide.LONG:
        risk = entry - stop
        reward = target - entry
    else:
        risk = stop - entry
        reward = entry - target

    if risk <= 0:
        raise ValueError("stop_loss_must_define_positive_risk")
    if reward <= 0:
        raise ValueError("take_profit_must_define_positive_reward")

    return float(reward / risk)


def evaluate_paper_trade(
    session: Session,
    *,
    settings: Settings,
    symbol_id: int,
    confidence: float,
    risk_to_reward: float,
    connection_state: MT5ConnectionState,
    model_type: ModelType | None = None,
) -> PaperTradeDecision:
    reasons: list[str] = []

    approved_model = get_active_approved_model(session, symbol_id=symbol_id, model_type=model_type)
    if approved_model is None:
        reasons.append("symbol_not_approved")

    reasons.extend(_evaluate_connection_reasons(connection_state))

    if confidence < settings.model_approval_min_confidence:
        reasons.append("confidence_below_threshold")
    if risk_to_reward < settings.model_approval_min_risk_reward:
        reasons.append("risk_to_reward_below_threshold")

    return PaperTradeDecision(
        allowed=not reasons,
        reasons=tuple(reasons),
        approved_model=approved_model,
        symbol_id=symbol_id,
        model_type=model_type,
        confidence=confidence,
        risk_to_reward=risk_to_reward,
    )


def _evaluate_connection_reasons(connection_state: MT5ConnectionState) -> list[str]:
    if connection_state.paper_trading_allowed:
        return []

    if connection_state.status is not ConnectionStatus.CONNECTED:
        return ["mt5_unavailable"]
    if connection_state.is_demo is False:
        return ["live_account_blocked"]
    if connection_state.trade_allowed is False:
        return ["trade_not_allowed"]
    return ["paper_trading_not_allowed"]
