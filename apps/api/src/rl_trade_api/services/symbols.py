"""Symbol validation and persistence helpers."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from rl_trade_api.schemas.symbols import SymbolValidationResponse
from rl_trade_common import Settings
from rl_trade_data import Symbol, SymbolValidationResult
from rl_trade_trading import MT5IntegrationError, SymbolValidationDecision, SymbolValidationProvider


def validate_symbol(
    *,
    session: Session,
    provider: SymbolValidationProvider,
    settings: Settings,
    requested_symbol: str,
) -> SymbolValidationResponse:
    stripped_symbol = requested_symbol.strip()
    try:
        decision = provider.validate_symbol(settings, stripped_symbol)
    except MT5IntegrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MT5 symbol validation unavailable: {exc.reason}.",
        ) from exc

    symbol = _get_or_create_symbol(session, decision)

    validation_result = SymbolValidationResult(
        symbol_id=symbol.id if symbol is not None else None,
        requested_symbol=stripped_symbol,
        normalized_symbol=decision.normalized_symbol,
        provider=decision.provider,
        is_valid=decision.is_valid,
        reason=decision.reason,
        details={
            "normalized_input": decision.normalized_input,
            **decision.details,
        },
    )
    session.add(validation_result)
    session.flush()
    session.commit()

    return SymbolValidationResponse(
        validation_result_id=validation_result.id,
        symbol_id=symbol.id if symbol is not None else None,
        requested_symbol=stripped_symbol,
        normalized_input=decision.normalized_input,
        normalized_symbol=decision.normalized_symbol,
        provider=decision.provider,
        is_valid=decision.is_valid,
        reason=decision.reason,
        base_currency=decision.base_currency,
        quote_currency=decision.quote_currency,
        details=validation_result.details or {},
    )


def _get_or_create_symbol(session: Session, decision: SymbolValidationDecision) -> Symbol | None:
    if not decision.is_valid or not decision.normalized_symbol:
        return None

    existing_symbol = session.scalar(select(Symbol).where(Symbol.code == decision.normalized_symbol))
    if existing_symbol is not None:
        return existing_symbol

    symbol = Symbol(
        code=decision.normalized_symbol,
        base_currency=decision.base_currency or "UNK",
        quote_currency=decision.quote_currency or "UNK",
        provider=decision.provider,
        asset_class="forex",
        is_active=True,
    )
    session.add(symbol)
    session.flush()
    return symbol
