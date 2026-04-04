"""Paper-trading signal services."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rl_trade_api.schemas.trading import (
    PaperTradeOrderCreate,
    PaperTradeOrderListResponse,
    PaperTradeOrderResponse,
    PaperTradingSyncResponse,
    PaperTradingStatusResponse,
    PaperTradePositionCloseResponse,
    PaperTradePositionListResponse,
    PaperTradePositionResponse,
    PaperTradeSignalCreate,
    PaperTradeSignalListResponse,
    PaperTradeSignalResponse,
)
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common import Settings
from rl_trade_data import (
    ApprovedModel,
    AuditLog,
    EquitySnapshot,
    MT5Account,
    PaperTradeOrder,
    PaperTradePosition,
    PaperTradeSignal,
    Symbol,
    TradeExecution,
)
from rl_trade_data.models import AuditOutcome, OrderStatus, PositionStatus, SignalStatus, TradeSide
from rl_trade_trading import (
    MT5Gateway,
    MT5HistoricalOrderRecord,
    MT5PositionRecord,
    calculate_risk_to_reward,
    evaluate_paper_trade,
    normalize_symbol_input,
)


def create_signal(
    *,
    session: Session,
    settings: Settings,
    principal: AuthPrincipal,
    gateway: MT5Gateway,
    payload: PaperTradeSignalCreate,
    event_broadcaster: EventBroadcaster | None = None,
) -> PaperTradeSignalResponse:
    normalized_code = normalize_symbol_input(payload.symbol_code)
    symbol = session.scalar(select(Symbol).where(Symbol.code == normalized_code))
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {normalized_code} was not found.",
        )

    try:
        risk_to_reward = calculate_risk_to_reward(
            side=payload.side,
            entry_price=payload.entry_price,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    connection_state = gateway.get_connection_state(settings)
    decision = evaluate_paper_trade(
        session,
        settings=settings,
        symbol_id=symbol.id,
        confidence=payload.confidence,
        risk_to_reward=risk_to_reward,
        connection_state=connection_state,
        model_type=payload.model_type,
    )
    signal_time = _normalize_signal_time(payload.signal_time)

    if not decision.allowed or decision.approved_model is None:
        detail = f"Paper-trade signal blocked: {', '.join(decision.reasons)}."
        _append_signal_audit_log(
            session=session,
            principal=principal,
            symbol=symbol,
            signal=None,
            outcome=AuditOutcome.BLOCKED,
            message=f"Paper-trade signal blocked for symbol {symbol.code}.",
            details={
                "reasons": list(decision.reasons),
                "confidence": payload.confidence,
                "risk_to_reward": risk_to_reward,
                "model_type": payload.model_type.value if payload.model_type else None,
                "signal_time": signal_time.isoformat(),
            },
        )
        session.commit()
        _publish_alert_event(
            event_broadcaster=event_broadcaster,
            entity_type="paper_trade_signal",
            entity_id=str(symbol.id),
            occurred_at=signal_time,
            severity="warning",
            alert_code="paper_trade_signal_blocked",
            message=detail,
            source="trading_guard",
            details={
                "symbol_id": symbol.id,
                "symbol_code": symbol.code,
                "reasons": list(decision.reasons),
                "operation": "create_signal",
            },
        )
        raise HTTPException(
            status_code=_resolve_decision_status_code(decision.reasons),
            detail=detail,
        )

    signal = PaperTradeSignal(
        approved_model_id=decision.approved_model.id,
        symbol_id=symbol.id,
        timeframe=payload.timeframe,
        side=payload.side,
        status=SignalStatus.ACCEPTED,
        signal_time=signal_time,
        confidence=Decimal(str(payload.confidence)),
        entry_price=Decimal(str(payload.entry_price)),
        stop_loss=Decimal(str(payload.stop_loss)),
        take_profit=Decimal(str(payload.take_profit)),
        rationale=dict(payload.rationale),
    )
    session.add(signal)
    session.flush()

    _append_signal_audit_log(
        session=session,
        principal=principal,
        symbol=symbol,
        signal=signal,
        outcome=AuditOutcome.SUCCESS,
        message=f"Paper-trade signal accepted for symbol {symbol.code}.",
        details={
            "approved_model_id": decision.approved_model.id,
            "confidence": payload.confidence,
            "risk_to_reward": risk_to_reward,
            "model_type": payload.model_type.value if payload.model_type else None,
        },
    )
    session.commit()
    session.refresh(signal)
    response = _build_signal_response(signal=signal, symbol=symbol, risk_to_reward=risk_to_reward)
    _publish_signal_event(
        event_broadcaster=event_broadcaster,
        signal=response,
        source="api_request",
    )
    return response


def list_signals(
    *,
    session: Session,
    symbol_code: str | None = None,
    status_filter: SignalStatus | None = None,
) -> PaperTradeSignalListResponse:
    symbol: Symbol | None = None
    if symbol_code is not None:
        normalized_code = normalize_symbol_input(symbol_code)
        symbol = session.scalar(select(Symbol).where(Symbol.code == normalized_code))
        if symbol is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Symbol {normalized_code} was not found.",
            )

    statement = select(PaperTradeSignal).order_by(PaperTradeSignal.signal_time.desc(), PaperTradeSignal.id.desc())
    if symbol is not None:
        statement = statement.where(PaperTradeSignal.symbol_id == symbol.id)
    if status_filter is not None:
        statement = statement.where(PaperTradeSignal.status == status_filter)

    signals = session.execute(statement).scalars().all()
    symbols_by_id = {
        existing_symbol.id: existing_symbol
        for existing_symbol in session.execute(
            select(Symbol).where(Symbol.id.in_({signal.symbol_id for signal in signals}))
        ).scalars()
    }

    return PaperTradeSignalListResponse(
        signals=[
            _build_signal_response(
                signal=signal,
                symbol=symbols_by_id[signal.symbol_id],
                risk_to_reward=calculate_risk_to_reward(
                    side=signal.side,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                ),
            )
            for signal in signals
        ]
    )


def create_order(
    *,
    session: Session,
    settings: Settings,
    principal: AuthPrincipal,
    gateway: MT5Gateway,
    payload: PaperTradeOrderCreate,
    event_broadcaster: EventBroadcaster | None = None,
) -> PaperTradeOrderResponse:
    signal = session.get(PaperTradeSignal, payload.signal_id)
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper-trade signal {payload.signal_id} was not found.",
        )

    symbol = session.get(Symbol, signal.symbol_id)
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {signal.symbol_id} for signal {signal.id} was not found.",
        )

    approved_model = session.get(ApprovedModel, signal.approved_model_id)
    if approved_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved model {signal.approved_model_id} for signal {signal.id} was not found.",
        )
    if not approved_model.is_active or approved_model.revoked_at is not None:
        signal.status = SignalStatus.REJECTED
        session.add(signal)
        detail = "Paper-trade order blocked: signal approval is no longer active."
        _append_order_audit_log(
            session=session,
            principal=principal,
            symbol=symbol,
            order=None,
            outcome=AuditOutcome.BLOCKED,
            message=f"Paper-trade order blocked for revoked approval on symbol {symbol.code}.",
            details={"signal_id": signal.id, "approved_model_id": approved_model.id},
        )
        session.commit()
        _publish_alert_event(
            event_broadcaster=event_broadcaster,
            entity_type="paper_trade_signal",
            entity_id=str(signal.id),
            occurred_at=datetime.now(UTC),
            severity="warning",
            alert_code="paper_trade_order_blocked",
            message=detail,
            source="approval_guard",
            details={
                "signal_id": signal.id,
                "symbol_id": symbol.id,
                "symbol_code": symbol.code,
                "approved_model_id": approved_model.id,
                "operation": "create_order",
                "reasons": ["approval_inactive"],
            },
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )
    if signal.status is not SignalStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Paper-trade signal {signal.id} cannot be submitted from status {signal.status.value}.",
        )

    risk_to_reward = calculate_risk_to_reward(
        side=signal.side,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
    )
    connection_state = gateway.get_connection_state(settings)
    decision = evaluate_paper_trade(
        session,
        settings=settings,
        symbol_id=symbol.id,
        confidence=float(signal.confidence),
        risk_to_reward=risk_to_reward,
        connection_state=connection_state,
        model_type=approved_model.model_type,
    )
    if not decision.allowed:
        signal.status = SignalStatus.REJECTED
        session.add(signal)
        detail = f"Paper-trade order blocked: {', '.join(decision.reasons)}."
        _append_order_audit_log(
            session=session,
            principal=principal,
            symbol=symbol,
            order=None,
            outcome=AuditOutcome.BLOCKED,
            message=f"Paper-trade order blocked for symbol {symbol.code}.",
            details={"signal_id": signal.id, "reasons": list(decision.reasons)},
        )
        session.commit()
        _publish_alert_event(
            event_broadcaster=event_broadcaster,
            entity_type="paper_trade_signal",
            entity_id=str(signal.id),
            occurred_at=datetime.now(UTC),
            severity="warning",
            alert_code="paper_trade_order_blocked",
            message=detail,
            source="trading_guard",
            details={
                "signal_id": signal.id,
                "symbol_id": symbol.id,
                "symbol_code": symbol.code,
                "operation": "create_order",
                "reasons": list(decision.reasons),
            },
        )
        raise HTTPException(
            status_code=_resolve_decision_status_code(decision.reasons),
            detail=detail,
        )

    order_result = gateway.submit_paper_order(
        settings,
        symbol_code=symbol.code,
        side=signal.side.value,
        quantity=payload.quantity,
        price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        comment=f"signal:{signal.id}",
    )

    order = PaperTradeOrder(
        signal_id=signal.id,
        symbol_id=symbol.id,
        side=signal.side,
        status=(
            OrderStatus.FILLED
            if order_result.accepted and order_result.filled
            else OrderStatus.SUBMITTED
            if order_result.accepted
            else OrderStatus.REJECTED
        ),
        broker_order_id=order_result.broker_order_id,
        requested_quantity=Decimal(str(payload.quantity)),
        filled_quantity=order_result.execution_quantity,
        requested_price=signal.entry_price,
        filled_price=order_result.execution_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        submitted_at=order_result.execution_time,
        filled_at=order_result.execution_time if order_result.accepted and order_result.filled else None,
        rejection_reason=order_result.rejection_reason,
    )
    session.add(order)
    session.flush()

    signal.status = SignalStatus.EXECUTED if order_result.accepted else SignalStatus.REJECTED
    session.add(signal)

    if order_result.accepted and order_result.filled:
        position = PaperTradePosition(
            order_id=order.id,
            symbol_id=symbol.id,
            side=order.side,
            status=PositionStatus.OPEN,
            opened_at=order_result.execution_time or datetime.now(UTC),
            quantity=order_result.execution_quantity or Decimal(str(payload.quantity)),
            open_price=order_result.execution_price or signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
        )
        session.add(position)
        session.flush()
        session.add(
            TradeExecution(
                order_id=order.id,
                position_id=position.id,
                execution_type="open",
                execution_time=order_result.execution_time or datetime.now(UTC),
                price=order_result.execution_price or signal.entry_price,
                quantity=order_result.execution_quantity or Decimal(str(payload.quantity)),
                raw_execution=dict(order_result.raw_result),
            )
        )

    _append_order_audit_log(
        session=session,
        principal=principal,
        symbol=symbol,
        order=order,
        outcome=AuditOutcome.SUCCESS if order_result.accepted else AuditOutcome.BLOCKED,
        message=(
            f"Paper-trade order {'submitted' if order_result.accepted else 'rejected'} for symbol {symbol.code}."
        ),
        details={
            "signal_id": signal.id,
            "broker_order_id": order_result.broker_order_id,
            "status": order.status.value,
            "rejection_reason": order_result.rejection_reason,
        },
    )
    session.commit()
    session.refresh(signal)
    session.refresh(order)
    order_response = _build_order_response(order=order, symbol=symbol)
    signal_response = _build_signal_response(signal=signal, symbol=symbol, risk_to_reward=risk_to_reward)
    _publish_signal_event(
        event_broadcaster=event_broadcaster,
        signal=signal_response,
        source="order_submission",
        order=order_response,
    )
    if order_result.accepted and order_result.filled:
        position = session.scalar(select(PaperTradePosition).where(PaperTradePosition.order_id == order.id))
        if position is not None:
            session.refresh(position)
            _publish_position_event(
                event_broadcaster=event_broadcaster,
                position=_build_position_response(position=position, symbol=symbol),
                source="order_fill",
                order=order_response,
            )
    return order_response


def list_orders(
    *,
    session: Session,
    symbol_code: str | None = None,
    status_filter: OrderStatus | None = None,
) -> PaperTradeOrderListResponse:
    symbol = _resolve_symbol_filter(session=session, symbol_code=symbol_code)
    statement = select(PaperTradeOrder).order_by(PaperTradeOrder.created_at.desc(), PaperTradeOrder.id.desc())
    if symbol is not None:
        statement = statement.where(PaperTradeOrder.symbol_id == symbol.id)
    if status_filter is not None:
        statement = statement.where(PaperTradeOrder.status == status_filter)
    orders = session.execute(statement).scalars().all()
    symbols_by_id = _load_symbols_by_id(session=session, symbol_ids={order.symbol_id for order in orders})
    return PaperTradeOrderListResponse(
        orders=[
            _build_order_response(order=order, symbol=symbols_by_id[order.symbol_id])
            for order in orders
        ]
    )


def list_positions(
    *,
    session: Session,
    symbol_code: str | None = None,
    status_filter: PositionStatus | None = None,
) -> PaperTradePositionListResponse:
    symbol = _resolve_symbol_filter(session=session, symbol_code=symbol_code)
    statement = select(PaperTradePosition).order_by(
        PaperTradePosition.created_at.desc(),
        PaperTradePosition.id.desc(),
    )
    if symbol is not None:
        statement = statement.where(PaperTradePosition.symbol_id == symbol.id)
    if status_filter is not None:
        statement = statement.where(PaperTradePosition.status == status_filter)
    positions = session.execute(statement).scalars().all()
    symbols_by_id = _load_symbols_by_id(session=session, symbol_ids={position.symbol_id for position in positions})
    return PaperTradePositionListResponse(
        positions=[
            _build_position_response(position=position, symbol=symbols_by_id[position.symbol_id])
            for position in positions
        ]
    )


def close_position(
    *,
    session: Session,
    settings: Settings,
    principal: AuthPrincipal,
    gateway: MT5Gateway,
    position_id: int,
    event_broadcaster: EventBroadcaster | None = None,
) -> PaperTradePositionCloseResponse:
    position = session.get(PaperTradePosition, position_id)
    if position is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper-trade position {position_id} was not found.",
        )
    if position.status is not PositionStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Paper-trade position {position_id} cannot be closed from status {position.status.value}.",
        )

    opening_order = session.get(PaperTradeOrder, position.order_id)
    if opening_order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opening order {position.order_id} for position {position.id} was not found.",
        )

    signal = session.get(PaperTradeSignal, opening_order.signal_id)
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {opening_order.signal_id} for position {position.id} was not found.",
        )

    symbol = session.get(Symbol, position.symbol_id)
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {position.symbol_id} for position {position.id} was not found.",
        )

    approved_model = session.get(ApprovedModel, signal.approved_model_id)
    if approved_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved model {signal.approved_model_id} for position {position.id} was not found.",
        )

    risk_to_reward = calculate_risk_to_reward(
        side=signal.side,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
    )
    connection_state = gateway.get_connection_state(settings)
    decision = evaluate_paper_trade(
        session,
        settings=settings,
        symbol_id=symbol.id,
        confidence=float(signal.confidence),
        risk_to_reward=risk_to_reward,
        connection_state=connection_state,
        model_type=approved_model.model_type,
    )
    if not decision.allowed:
        detail = f"Paper-trade close blocked: {', '.join(decision.reasons)}."
        _append_order_audit_log(
            session=session,
            principal=principal,
            symbol=symbol,
            order=None,
            outcome=AuditOutcome.BLOCKED,
            message=f"Paper-trade close blocked for symbol {symbol.code}.",
            details={"position_id": position.id, "reasons": list(decision.reasons)},
        )
        session.commit()
        _publish_alert_event(
            event_broadcaster=event_broadcaster,
            entity_type="paper_trade_position",
            entity_id=str(position.id),
            occurred_at=datetime.now(UTC),
            severity="warning",
            alert_code="paper_trade_close_blocked",
            message=detail,
            source="trading_guard",
            details={
                "position_id": position.id,
                "symbol_id": symbol.id,
                "symbol_code": symbol.code,
                "operation": "close_position",
                "reasons": list(decision.reasons),
            },
        )
        raise HTTPException(
            status_code=_resolve_decision_status_code(decision.reasons),
            detail=detail,
        )

    close_side = _opposite_trade_side(position.side)
    close_result = gateway.submit_paper_order(
        settings,
        symbol_code=symbol.code,
        side=close_side.value,
        quantity=position.quantity,
        price=position.open_price,
        stop_loss=position.stop_loss or position.open_price,
        take_profit=position.take_profit or position.open_price,
        comment=f"close_position:{position.id}",
    )

    closing_order = PaperTradeOrder(
        signal_id=opening_order.signal_id,
        symbol_id=symbol.id,
        side=close_side,
        status=(
            OrderStatus.FILLED
            if close_result.accepted and close_result.filled
            else OrderStatus.SUBMITTED
            if close_result.accepted
            else OrderStatus.REJECTED
        ),
        broker_order_id=close_result.broker_order_id,
        requested_quantity=position.quantity,
        filled_quantity=close_result.execution_quantity,
        requested_price=position.open_price,
        filled_price=close_result.execution_price,
        stop_loss=position.stop_loss,
        take_profit=position.take_profit,
        submitted_at=close_result.execution_time,
        filled_at=close_result.execution_time if close_result.accepted and close_result.filled else None,
        rejection_reason=close_result.rejection_reason,
    )
    session.add(closing_order)
    session.flush()

    if close_result.accepted and close_result.filled:
        close_price = close_result.execution_price or position.open_price
        position.status = PositionStatus.CLOSED
        position.closed_at = close_result.execution_time or datetime.now(UTC)
        position.close_price = close_price
        position.realized_pnl = _calculate_realized_pnl(
            side=position.side,
            quantity=position.quantity,
            open_price=position.open_price,
            close_price=close_price,
        )
        position.unrealized_pnl = Decimal("0")
        session.add(position)
        session.add(
            TradeExecution(
                order_id=closing_order.id,
                position_id=position.id,
                execution_type="close",
                execution_time=close_result.execution_time or datetime.now(UTC),
                price=close_price,
                quantity=close_result.execution_quantity or position.quantity,
                raw_execution=dict(close_result.raw_result),
            )
        )

    _append_order_audit_log(
        session=session,
        principal=principal,
        symbol=symbol,
        order=closing_order,
        outcome=AuditOutcome.SUCCESS if close_result.accepted else AuditOutcome.BLOCKED,
        message=(
            f"Paper-trade position close {'submitted' if close_result.accepted else 'rejected'} for symbol {symbol.code}."
        ),
        details={
            "position_id": position.id,
            "broker_order_id": close_result.broker_order_id,
            "status": closing_order.status.value,
            "rejection_reason": close_result.rejection_reason,
        },
    )
    session.commit()
    session.refresh(closing_order)
    session.refresh(position)
    position_response = _build_position_response(position=position, symbol=symbol)
    closing_order_response = _build_order_response(order=closing_order, symbol=symbol)
    if close_result.accepted and close_result.filled:
        _publish_position_event(
            event_broadcaster=event_broadcaster,
            position=position_response,
            source="position_close",
            order=closing_order_response,
        )
    return PaperTradePositionCloseResponse(
        position=position_response,
        closing_order=closing_order_response,
    )


def get_trading_status(
    *,
    session: Session,
    settings: Settings,
    gateway: MT5Gateway,
) -> PaperTradingStatusResponse:
    connection_state = gateway.get_connection_state(settings)
    account = _resolve_runtime_account(session=session, connection_state=connection_state)
    counts = _load_trading_counts(session=session)

    details = dict(account.details or {}) if account is not None and account.details else {}
    enabled = bool(details.get("paper_trading_enabled", False))

    return PaperTradingStatusResponse(
        enabled=enabled,
        connection_status=connection_state.status.value,
        account_login=account.account_login if account is not None else connection_state.account_login,
        server_name=account.server_name if account is not None else connection_state.server_name,
        account_name=account.account_name if account is not None else connection_state.account_name,
        is_demo=account.is_demo if account is not None else connection_state.is_demo,
        is_trade_allowed=account.is_trade_allowed if account is not None else connection_state.trade_allowed,
        paper_trading_allowed=connection_state.paper_trading_allowed,
        reason=connection_state.reason,
        approved_symbol_count=counts["approved_symbol_count"],
        accepted_signal_count=counts["accepted_signal_count"],
        open_order_count=counts["open_order_count"],
        open_position_count=counts["open_position_count"],
        last_started_at=_coerce_optional_datetime(details.get("last_started_at")),
        last_started_by=_coerce_optional_str(details.get("last_started_by")),
        last_stopped_at=_coerce_optional_datetime(details.get("last_stopped_at")),
        last_stopped_by=_coerce_optional_str(details.get("last_stopped_by")),
    )


def start_trading(
    *,
    session: Session,
    settings: Settings,
    principal: AuthPrincipal,
    gateway: MT5Gateway,
    event_broadcaster: EventBroadcaster | None = None,
) -> PaperTradingStatusResponse:
    connection_state = gateway.get_connection_state(settings)
    if not connection_state.paper_trading_allowed:
        detail = f"Paper trading start blocked: {connection_state.reason or 'paper_trading_not_allowed'}."
        _append_runtime_audit_log(
            session=session,
            principal=principal,
            outcome=AuditOutcome.BLOCKED,
            message="Paper trading start blocked.",
            details={"reason": connection_state.reason, "connection_status": connection_state.status.value},
        )
        session.commit()
        _publish_alert_event(
            event_broadcaster=event_broadcaster,
            entity_type="paper_trading_runtime",
            entity_id="default",
            occurred_at=datetime.now(UTC),
            severity="warning",
            alert_code="paper_trading_start_blocked",
            message=detail,
            source="runtime_guard",
            details={
                "operation": "start_trading",
                "reason": connection_state.reason,
                "connection_status": connection_state.status.value,
                "account_login": connection_state.account_login,
                "server_name": connection_state.server_name,
            },
        )
        raise HTTPException(
            status_code=_resolve_runtime_status_code(connection_state),
            detail=detail,
        )

    account = _upsert_mt5_account(session=session, connection_state=connection_state)
    details = dict(account.details or {})
    details["paper_trading_enabled"] = True
    details["last_started_at"] = datetime.now(UTC).isoformat()
    details["last_started_by"] = principal.subject
    account.details = details
    session.add(account)
    _append_runtime_audit_log(
        session=session,
        principal=principal,
        outcome=AuditOutcome.SUCCESS,
        message="Paper trading started.",
        details={"account_login": account.account_login, "server_name": account.server_name},
    )
    session.commit()
    session.refresh(account)
    return get_trading_status(session=session, settings=settings, gateway=gateway)


def stop_trading(
    *,
    session: Session,
    settings: Settings,
    principal: AuthPrincipal,
    gateway: MT5Gateway,
) -> PaperTradingStatusResponse:
    connection_state = gateway.get_connection_state(settings)
    account = _resolve_runtime_account(session=session, connection_state=connection_state)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No paper-trading runtime state was found.",
        )

    details = dict(account.details or {})
    details["paper_trading_enabled"] = False
    details["last_stopped_at"] = datetime.now(UTC).isoformat()
    details["last_stopped_by"] = principal.subject
    account.details = details
    session.add(account)
    _append_runtime_audit_log(
        session=session,
        principal=principal,
        outcome=AuditOutcome.SUCCESS,
        message="Paper trading stopped.",
        details={"account_login": account.account_login, "server_name": account.server_name},
    )
    session.commit()
    session.refresh(account)
    return get_trading_status(session=session, settings=settings, gateway=gateway)


def sync_trading_state(
    *,
    session: Session,
    settings: Settings,
    principal: AuthPrincipal,
    gateway: MT5Gateway,
    event_broadcaster: EventBroadcaster | None = None,
) -> PaperTradingSyncResponse:
    connection_state = gateway.get_connection_state(settings)
    if not connection_state.paper_trading_allowed:
        detail = f"Paper-trading sync blocked: {connection_state.reason or 'paper_trading_not_allowed'}."
        _append_sync_audit_log(
            session=session,
            principal=principal,
            outcome=AuditOutcome.BLOCKED,
            message="Paper-trading sync blocked.",
            details={"reason": connection_state.reason, "connection_status": connection_state.status.value},
        )
        session.commit()
        _publish_alert_event(
            event_broadcaster=event_broadcaster,
            entity_type="paper_trading_sync",
            entity_id="default",
            occurred_at=datetime.now(UTC),
            severity="warning",
            alert_code="paper_trading_sync_blocked",
            message=detail,
            source="runtime_guard",
            details={
                "operation": "sync_trading_state",
                "reason": connection_state.reason,
                "connection_status": connection_state.status.value,
                "account_login": connection_state.account_login,
                "server_name": connection_state.server_name,
            },
        )
        raise HTTPException(
            status_code=_resolve_runtime_status_code(connection_state),
            detail=detail,
        )

    account = _upsert_mt5_account(session=session, connection_state=connection_state)
    sync_started_at = datetime.now(UTC)
    history_records = gateway.list_order_history(
        settings,
        start_time=_resolve_sync_start_time(session=session),
        end_time=sync_started_at,
    )
    broker_positions = gateway.list_open_positions(settings)

    history_by_broker_id = {
        record.broker_order_id: record for record in history_records if record.broker_order_id is not None
    }
    broker_positions_by_order_id = {
        record.broker_order_id: record for record in broker_positions if record.broker_order_id is not None
    }

    orders_updated = 0
    positions_updated = 0
    executions_created = 0
    affected_position_ids: set[int] = set()

    submitted_orders = session.execute(
        select(PaperTradeOrder).where(
            PaperTradeOrder.status == OrderStatus.SUBMITTED,
            PaperTradeOrder.broker_order_id.is_not(None),
        )
    ).scalars().all()
    for order in submitted_orders:
        history_record = history_by_broker_id.get(order.broker_order_id)
        if history_record is None:
            continue
        order_was_updated, position_ids, execution_delta = _apply_history_to_submitted_order(
            session=session,
            order=order,
            history_record=history_record,
        )
        orders_updated += int(order_was_updated)
        positions_updated += len(position_ids)
        affected_position_ids.update(position_ids)
        executions_created += execution_delta

    open_positions = session.execute(
        select(PaperTradePosition).where(PaperTradePosition.status == PositionStatus.OPEN)
    ).scalars().all()
    for position in open_positions:
        opening_order = session.get(PaperTradeOrder, position.order_id)
        if opening_order is None or opening_order.broker_order_id is None:
            continue
        broker_position = broker_positions_by_order_id.get(opening_order.broker_order_id)
        if broker_position is None:
            continue
        if _apply_broker_position_to_local_position(position=position, broker_position=broker_position):
            session.add(position)
            positions_updated += 1
            affected_position_ids.add(position.id)

    session.flush()
    equity_snapshot = _create_equity_snapshot(
        session=session,
        account=account,
        connection_state=connection_state,
        snapshot_time=sync_started_at,
    )

    details = dict(account.details or {})
    details["last_synced_at"] = sync_started_at.isoformat()
    details["last_synced_by"] = principal.subject
    account.details = details
    session.add(account)
    _append_sync_audit_log(
        session=session,
        principal=principal,
        outcome=AuditOutcome.SUCCESS,
        message="Paper-trading sync completed.",
        details={
            "account_login": account.account_login,
            "history_records_seen": len(history_records),
            "broker_positions_seen": len(broker_positions),
            "orders_updated": orders_updated,
            "positions_updated": positions_updated,
            "executions_created": executions_created,
        },
    )
    session.commit()

    for position_id in sorted(affected_position_ids):
        position = session.get(PaperTradePosition, position_id)
        if position is None:
            continue
        symbol = session.get(Symbol, position.symbol_id)
        if symbol is None:
            continue
        order = session.get(PaperTradeOrder, position.order_id)
        order_response = _build_order_response(order=order, symbol=symbol) if order is not None else None
        _publish_position_event(
            event_broadcaster=event_broadcaster,
            position=_build_position_response(position=position, symbol=symbol),
            source="sync_reconciliation",
            order=order_response,
        )

    _publish_equity_event(
        event_broadcaster=event_broadcaster,
        snapshot=equity_snapshot,
        account=account,
        source="sync_reconciliation",
    )

    return PaperTradingSyncResponse(
        synced_at=sync_started_at,
        connection_status=connection_state.status.value,
        paper_trading_allowed=connection_state.paper_trading_allowed,
        account_login=account.account_login,
        orders_updated=orders_updated,
        positions_updated=positions_updated,
        executions_created=executions_created,
        history_records_seen=len(history_records),
        broker_positions_seen=len(broker_positions),
    )


def _normalize_signal_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _build_signal_response(
    *,
    signal: PaperTradeSignal,
    symbol: Symbol,
    risk_to_reward: float,
) -> PaperTradeSignalResponse:
    return PaperTradeSignalResponse(
        signal_id=signal.id,
        approved_model_id=signal.approved_model_id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        timeframe=signal.timeframe,
        side=signal.side,
        status=signal.status,
        signal_time=_normalize_signal_time(signal.signal_time),
        confidence=float(signal.confidence),
        risk_to_reward=risk_to_reward,
        entry_price=float(signal.entry_price),
        stop_loss=float(signal.stop_loss),
        take_profit=float(signal.take_profit),
        rationale=dict(signal.rationale or {}),
    )


def _build_order_response(*, order: PaperTradeOrder, symbol: Symbol) -> PaperTradeOrderResponse:
    return PaperTradeOrderResponse(
        order_id=order.id,
        signal_id=order.signal_id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        side=order.side,
        status=order.status,
        broker_order_id=order.broker_order_id,
        requested_quantity=float(order.requested_quantity),
        filled_quantity=float(order.filled_quantity) if order.filled_quantity is not None else None,
        requested_price=float(order.requested_price),
        filled_price=float(order.filled_price) if order.filled_price is not None else None,
        stop_loss=float(order.stop_loss) if order.stop_loss is not None else None,
        take_profit=float(order.take_profit) if order.take_profit is not None else None,
        submitted_at=_normalize_signal_time(order.submitted_at) if order.submitted_at is not None else None,
        filled_at=_normalize_signal_time(order.filled_at) if order.filled_at is not None else None,
        rejection_reason=order.rejection_reason,
    )


def _build_position_response(*, position: PaperTradePosition, symbol: Symbol) -> PaperTradePositionResponse:
    return PaperTradePositionResponse(
        position_id=position.id,
        order_id=position.order_id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        side=position.side,
        status=position.status,
        opened_at=_normalize_signal_time(position.opened_at),
        closed_at=_normalize_signal_time(position.closed_at) if position.closed_at is not None else None,
        quantity=float(position.quantity),
        open_price=float(position.open_price),
        close_price=float(position.close_price) if position.close_price is not None else None,
        stop_loss=float(position.stop_loss) if position.stop_loss is not None else None,
        take_profit=float(position.take_profit) if position.take_profit is not None else None,
        unrealized_pnl=float(position.unrealized_pnl) if position.unrealized_pnl is not None else None,
        realized_pnl=float(position.realized_pnl) if position.realized_pnl is not None else None,
    )


def _publish_signal_event(
    *,
    event_broadcaster: EventBroadcaster | None,
    signal: PaperTradeSignalResponse,
    source: str,
    order: PaperTradeOrderResponse | None = None,
) -> None:
    if event_broadcaster is None:
        return
    payload = signal.model_dump(mode="json")
    payload["source"] = source
    if order is not None:
        payload["order"] = order.model_dump(mode="json")
    event_broadcaster.publish_event(
        event_type="signal_event",
        entity_type="paper_trade_signal",
        entity_id=str(signal.signal_id),
        occurred_at=signal.signal_time,
        payload=payload,
    )


def _publish_position_event(
    *,
    event_broadcaster: EventBroadcaster | None,
    position: PaperTradePositionResponse,
    source: str,
    order: PaperTradeOrderResponse | None = None,
) -> None:
    if event_broadcaster is None:
        return
    occurred_at = position.closed_at or position.opened_at
    payload = position.model_dump(mode="json")
    payload["source"] = source
    if order is not None:
        payload["order"] = order.model_dump(mode="json")
    event_broadcaster.publish_event(
        event_type="position_update",
        entity_type="paper_trade_position",
        entity_id=str(position.position_id),
        occurred_at=occurred_at,
        payload=payload,
    )


def _publish_equity_event(
    *,
    event_broadcaster: EventBroadcaster | None,
    snapshot: EquitySnapshot | None,
    account: MT5Account,
    source: str,
) -> None:
    if event_broadcaster is None or snapshot is None:
        return
    event_broadcaster.publish_event(
        event_type="equity_update",
        entity_type="equity_snapshot",
        entity_id=str(snapshot.id),
        occurred_at=snapshot.snapshot_time,
        payload={
            "snapshot_id": snapshot.id,
            "account_login": account.account_login,
            "server_name": account.server_name,
            "snapshot_time": snapshot.snapshot_time.isoformat(),
            "balance": float(snapshot.balance),
            "equity": float(snapshot.equity),
            "margin": float(snapshot.margin) if snapshot.margin is not None else None,
            "free_margin": float(snapshot.free_margin) if snapshot.free_margin is not None else None,
            "open_positions_count": snapshot.open_positions_count,
            "details": dict(snapshot.details or {}),
            "source": source,
        },
    )


def _publish_alert_event(
    *,
    event_broadcaster: EventBroadcaster | None,
    entity_type: str,
    entity_id: str,
    occurred_at: datetime,
    severity: str,
    alert_code: str,
    message: str,
    source: str,
    details: dict[str, object],
) -> None:
    if event_broadcaster is None:
        return
    event_broadcaster.publish_event(
        event_type="alert",
        entity_type=entity_type,
        entity_id=entity_id,
        occurred_at=occurred_at,
        payload={
            "severity": severity,
            "alert_code": alert_code,
            "message": message,
            "source": source,
            **details,
        },
    )


def _opposite_trade_side(side: TradeSide) -> TradeSide:
    return TradeSide.SHORT if side is TradeSide.LONG else TradeSide.LONG


def _calculate_realized_pnl(
    *,
    side: TradeSide,
    quantity: Decimal,
    open_price: Decimal,
    close_price: Decimal,
) -> Decimal:
    if side is TradeSide.LONG:
        return (close_price - open_price) * quantity
    return (open_price - close_price) * quantity


def _apply_history_to_submitted_order(
    *,
    session: Session,
    order: PaperTradeOrder,
    history_record: MT5HistoricalOrderRecord,
) -> tuple[bool, set[int], int]:
    updated = False
    position_ids: set[int] = set()
    executions_created = 0

    if history_record.status == "filled":
        if order.status is not OrderStatus.FILLED:
            order.status = OrderStatus.FILLED
            updated = True
        if history_record.execution_quantity is not None and order.filled_quantity != history_record.execution_quantity:
            order.filled_quantity = history_record.execution_quantity
            updated = True
        if history_record.execution_price is not None and order.filled_price != history_record.execution_price:
            order.filled_price = history_record.execution_price
            updated = True
        if history_record.execution_time is not None and order.filled_at != history_record.execution_time:
            order.filled_at = history_record.execution_time
            updated = True
        if history_record.execution_time is not None and order.submitted_at != history_record.execution_time:
            order.submitted_at = history_record.execution_time
            updated = True
        if order.rejection_reason is not None:
            order.rejection_reason = None
            updated = True

        affected_positions, execution_delta = _apply_filled_order_history(
            session=session,
            order=order,
            history_record=history_record,
        )
        position_ids.update(affected_positions)
        executions_created += execution_delta
    elif history_record.status in {"rejected", "cancelled"}:
        target_status = OrderStatus.REJECTED if history_record.status == "rejected" else OrderStatus.CANCELLED
        if order.status is not target_status:
            order.status = target_status
            updated = True
        if order.rejection_reason != history_record.rejection_reason:
            order.rejection_reason = history_record.rejection_reason
            updated = True
        if history_record.execution_time is not None and order.submitted_at != history_record.execution_time:
            order.submitted_at = history_record.execution_time
            updated = True

    if updated:
        session.add(order)
    return updated, position_ids, executions_created


def _apply_filled_order_history(
    *,
    session: Session,
    order: PaperTradeOrder,
    history_record: MT5HistoricalOrderRecord,
) -> tuple[set[int], int]:
    executions_created = 0
    position_ids: set[int] = set()
    comment = history_record.comment or ""

    if comment.startswith("close_position:"):
        position_id = _parse_trailing_identifier(comment)
        if position_id is None:
            return set(), 0
        position = session.get(PaperTradePosition, position_id)
        if position is None:
            return set(), 0
        execution_exists = session.scalar(
            select(TradeExecution.id).where(
                TradeExecution.order_id == order.id,
                TradeExecution.execution_type == "close",
            )
        )
        if position.status is not PositionStatus.CLOSED:
            close_price = history_record.execution_price or order.filled_price or position.open_price
            position.status = PositionStatus.CLOSED
            position.closed_at = history_record.execution_time or order.filled_at or datetime.now(UTC)
            position.close_price = close_price
            position.realized_pnl = _calculate_realized_pnl(
                side=position.side,
                quantity=position.quantity,
                open_price=position.open_price,
                close_price=close_price,
            )
            position.unrealized_pnl = Decimal("0")
            session.add(position)
            position_ids.add(position.id)
        if execution_exists is None:
            session.add(
                TradeExecution(
                    order_id=order.id,
                    position_id=position.id,
                    execution_type="close",
                    execution_time=history_record.execution_time or order.filled_at or datetime.now(UTC),
                    price=history_record.execution_price or order.filled_price or position.open_price,
                    quantity=history_record.execution_quantity or order.filled_quantity or position.quantity,
                    raw_execution=dict(history_record.raw_record),
                )
            )
            executions_created += 1
        return position_ids, executions_created

    position = session.scalar(select(PaperTradePosition).where(PaperTradePosition.order_id == order.id))
    if position is None:
        signal = session.get(PaperTradeSignal, order.signal_id)
        if signal is None:
            return set(), 0
        position = PaperTradePosition(
            order_id=order.id,
            symbol_id=order.symbol_id,
            side=order.side,
            status=PositionStatus.OPEN,
            opened_at=history_record.execution_time or order.filled_at or datetime.now(UTC),
            quantity=history_record.execution_quantity or order.filled_quantity or order.requested_quantity,
            open_price=history_record.execution_price or order.filled_price or order.requested_price,
            stop_loss=order.stop_loss or signal.stop_loss,
            take_profit=order.take_profit or signal.take_profit,
        )
        session.add(position)
        session.flush()
        position_ids.add(position.id)

    execution_exists = session.scalar(
        select(TradeExecution.id).where(
            TradeExecution.order_id == order.id,
            TradeExecution.execution_type == "open",
        )
    )
    if execution_exists is None:
        session.add(
            TradeExecution(
                order_id=order.id,
                position_id=position.id,
                execution_type="open",
                execution_time=history_record.execution_time or order.filled_at or datetime.now(UTC),
                price=history_record.execution_price or order.filled_price or order.requested_price,
                quantity=history_record.execution_quantity or order.filled_quantity or order.requested_quantity,
                raw_execution=dict(history_record.raw_record),
            )
        )
        executions_created += 1
    return position_ids, executions_created


def _apply_broker_position_to_local_position(
    *,
    position: PaperTradePosition,
    broker_position: MT5PositionRecord,
) -> bool:
    updated = False
    if broker_position.unrealized_pnl is not None and position.unrealized_pnl != broker_position.unrealized_pnl:
        position.unrealized_pnl = broker_position.unrealized_pnl
        updated = True
    if broker_position.stop_loss is not None and position.stop_loss != broker_position.stop_loss:
        position.stop_loss = broker_position.stop_loss
        updated = True
    if broker_position.take_profit is not None and position.take_profit != broker_position.take_profit:
        position.take_profit = broker_position.take_profit
        updated = True
    return updated


def _parse_trailing_identifier(comment: str) -> int | None:
    try:
        return int(comment.rsplit(":", maxsplit=1)[-1])
    except ValueError:
        return None


def _append_signal_audit_log(
    *,
    session: Session,
    principal: AuthPrincipal,
    symbol: Symbol,
    signal: PaperTradeSignal | None,
    outcome: AuditOutcome,
    message: str,
    details: dict[str, object],
) -> None:
    session.add(
        AuditLog(
            action="paper_trade_signal",
            actor_type="api_principal",
            actor_id=principal.subject,
            entity_type="paper_trade_signal" if signal is not None else "symbol",
            entity_id=str(signal.id) if signal is not None else str(symbol.id),
            outcome=outcome,
            message=message,
            details={
                "symbol_code": symbol.code,
                **details,
            },
        )
    )


def _append_order_audit_log(
    *,
    session: Session,
    principal: AuthPrincipal,
    symbol: Symbol,
    order: PaperTradeOrder | None,
    outcome: AuditOutcome,
    message: str,
    details: dict[str, object],
) -> None:
    session.add(
        AuditLog(
            action="paper_trade_order",
            actor_type="api_principal",
            actor_id=principal.subject,
            entity_type="paper_trade_order" if order is not None else "symbol",
            entity_id=str(order.id) if order is not None else str(symbol.id),
            outcome=outcome,
            message=message,
            details={"symbol_code": symbol.code, **details},
        )
    )


def _resolve_symbol_filter(*, session: Session, symbol_code: str | None) -> Symbol | None:
    if symbol_code is None:
        return None
    normalized_code = normalize_symbol_input(symbol_code)
    symbol = session.scalar(select(Symbol).where(Symbol.code == normalized_code))
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {normalized_code} was not found.",
        )
    return symbol


def _load_symbols_by_id(*, session: Session, symbol_ids: set[int]) -> dict[int, Symbol]:
    if not symbol_ids:
        return {}
    return {
        symbol.id: symbol
        for symbol in session.execute(select(Symbol).where(Symbol.id.in_(symbol_ids))).scalars()
    }


def _upsert_mt5_account(*, session: Session, connection_state) -> MT5Account:
    if connection_state.account_login is None or not connection_state.server_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MT5 account information is unavailable.",
        )

    account = session.scalar(
        select(MT5Account).where(
            MT5Account.account_login == connection_state.account_login,
            MT5Account.server_name == connection_state.server_name,
        )
    )
    if account is None:
        account = MT5Account(
            account_login=connection_state.account_login,
            server_name=connection_state.server_name,
        )
        session.add(account)

    account.account_name = connection_state.account_name
    account.account_currency = connection_state.account_currency
    account.leverage = connection_state.leverage
    account.is_demo = bool(connection_state.is_demo)
    account.connection_status = connection_state.status
    account.is_trade_allowed = bool(connection_state.trade_allowed)
    account.last_seen_at = datetime.now(UTC)
    details = dict(account.details or {})
    details["paper_trading_allowed"] = connection_state.paper_trading_allowed
    details["reason"] = connection_state.reason
    account.details = details
    session.add(account)
    session.flush()
    return account


def _resolve_runtime_account(*, session: Session, connection_state) -> MT5Account | None:
    if connection_state.account_login is not None and connection_state.server_name:
        account = session.scalar(
            select(MT5Account).where(
                MT5Account.account_login == connection_state.account_login,
                MT5Account.server_name == connection_state.server_name,
            )
        )
        if account is not None:
            return account

    return session.scalar(
        select(MT5Account).order_by(MT5Account.updated_at.desc(), MT5Account.id.desc())
    )


def _load_trading_counts(*, session: Session) -> dict[str, int]:
    approved_symbol_count = int(
        session.scalar(
            select(func.count()).select_from(ApprovedModel).where(
                ApprovedModel.is_active.is_(True),
                ApprovedModel.revoked_at.is_(None),
            )
        )
        or 0
    )
    accepted_signal_count = int(
        session.scalar(
            select(func.count()).select_from(PaperTradeSignal).where(PaperTradeSignal.status == SignalStatus.ACCEPTED)
        )
        or 0
    )
    open_order_count = int(
        session.scalar(
            select(func.count()).select_from(PaperTradeOrder).where(
                PaperTradeOrder.status.in_([OrderStatus.PENDING, OrderStatus.SUBMITTED])
            )
        )
        or 0
    )
    open_position_count = int(
        session.scalar(
            select(func.count()).select_from(PaperTradePosition).where(PaperTradePosition.status == PositionStatus.OPEN)
        )
        or 0
    )
    return {
        "approved_symbol_count": approved_symbol_count,
        "accepted_signal_count": accepted_signal_count,
        "open_order_count": open_order_count,
        "open_position_count": open_position_count,
    }


def _create_equity_snapshot(
    *,
    session: Session,
    account: MT5Account,
    connection_state,
    snapshot_time: datetime,
) -> EquitySnapshot | None:
    if connection_state.balance is None or connection_state.equity is None:
        return None

    open_positions_count = int(
        session.scalar(
            select(func.count()).select_from(PaperTradePosition).where(PaperTradePosition.status == PositionStatus.OPEN)
        )
        or 0
    )
    total_unrealized_pnl = session.scalar(
        select(func.sum(PaperTradePosition.unrealized_pnl)).where(PaperTradePosition.status == PositionStatus.OPEN)
    ) or Decimal("0")

    snapshot = EquitySnapshot(
        mt5_account_id=account.id,
        snapshot_time=snapshot_time,
        balance=connection_state.balance,
        equity=connection_state.equity,
        margin=connection_state.margin,
        free_margin=connection_state.free_margin,
        open_positions_count=open_positions_count,
        details={
            "account_currency": account.account_currency,
            "total_unrealized_pnl": float(total_unrealized_pnl),
        },
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def _resolve_sync_start_time(*, session: Session) -> datetime:
    earliest_submitted_at = session.scalar(
        select(func.min(PaperTradeOrder.submitted_at)).where(PaperTradeOrder.status == OrderStatus.SUBMITTED)
    )
    earliest_opened_at = session.scalar(
        select(func.min(PaperTradePosition.opened_at)).where(PaperTradePosition.status == PositionStatus.OPEN)
    )
    candidates = [
        _normalize_signal_time(candidate)
        for candidate in (earliest_submitted_at, earliest_opened_at)
        if candidate is not None
    ]
    if not candidates:
        return datetime.now(UTC).replace(microsecond=0)
    return min(candidates)


def _append_runtime_audit_log(
    *,
    session: Session,
    principal: AuthPrincipal,
    outcome: AuditOutcome,
    message: str,
    details: dict[str, object],
) -> None:
    session.add(
        AuditLog(
            action="paper_trading_runtime",
            actor_type="api_principal",
            actor_id=principal.subject,
            entity_type="paper_trading_runtime",
            entity_id="default",
            outcome=outcome,
            message=message,
            details=details,
        )
    )


def _append_sync_audit_log(
    *,
    session: Session,
    principal: AuthPrincipal,
    outcome: AuditOutcome,
    message: str,
    details: dict[str, object],
) -> None:
    session.add(
        AuditLog(
            action="paper_trading_sync",
            actor_type="api_principal",
            actor_id=principal.subject,
            entity_type="paper_trading_sync",
            entity_id="default",
            outcome=outcome,
            message=message,
            details=details,
        )
    )


def _resolve_runtime_status_code(connection_state) -> int:
    if connection_state.status.value != "connected":
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_409_CONFLICT


def _coerce_optional_datetime(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return _normalize_signal_time(value)
    try:
        return _normalize_signal_time(datetime.fromisoformat(str(value)))
    except ValueError:
        return None


def _coerce_optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _resolve_decision_status_code(reasons: tuple[str, ...]) -> int:
    if "mt5_unavailable" in reasons:
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_409_CONFLICT
