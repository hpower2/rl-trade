"""Evaluation persistence and approval-gating services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from rl_trade_api.schemas.evaluations import (
    ApprovalDecisionResponse,
    ApprovedSymbolResponse,
    ModelEvaluationCreate,
    ModelEvaluationResponse,
    ModelEvaluationSummaryResponse,
    ModelRegistryEntryResponse,
)
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common import Settings
from rl_trade_data import (
    ApprovedModel,
    AuditLog,
    ModelEvaluation,
    RLModel,
    SupervisedModel,
    Symbol,
)
from rl_trade_data.models import AuditOutcome, ModelStatus, ModelType
from rl_trade_trading import evaluate_model_approval, get_active_approved_model, normalize_symbol_input


@dataclass(frozen=True, slots=True)
class ResolvedModelRecord:
    model_type: ModelType
    model_id: int
    symbol_id: int
    dataset_version_id: int | None
    model_name: str
    algorithm: str
    status: ModelStatus
    storage_uri: str | None
    supervised_model: SupervisedModel | None = None
    rl_model: RLModel | None = None


def create_model_evaluation(
    *,
    session: Session,
    settings: Settings,
    principal: AuthPrincipal,
    payload: ModelEvaluationCreate,
    event_broadcaster: EventBroadcaster | None = None,
) -> ModelEvaluationResponse:
    resolved = _resolve_model(session=session, model_type=payload.model_type, model_id=payload.model_id)
    if resolved.status is ModelStatus.TRAINING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model {payload.model_id} is still training and cannot be evaluated.",
        )

    symbol = session.get(Symbol, resolved.symbol_id)
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {resolved.symbol_id} for model {payload.model_id} was not found.",
        )

    dataset_version_id = payload.dataset_version_id or resolved.dataset_version_id
    if payload.dataset_version_id is not None and resolved.dataset_version_id not in {None, payload.dataset_version_id}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model {payload.model_id} does not belong to dataset version {payload.dataset_version_id}.",
        )

    decision = evaluate_model_approval(
        settings=settings,
        confidence=payload.confidence,
        risk_to_reward=payload.risk_to_reward,
        sample_size=payload.sample_size,
        max_drawdown=payload.max_drawdown,
        has_critical_data_issue=payload.has_critical_data_issue,
    )
    evaluation = ModelEvaluation(
        supervised_model_id=resolved.supervised_model.id if resolved.supervised_model is not None else None,
        rl_model_id=resolved.rl_model.id if resolved.rl_model is not None else None,
        dataset_version_id=dataset_version_id,
        evaluation_type=payload.evaluation_type,
        confidence=Decimal(str(payload.confidence)),
        risk_to_reward=Decimal(str(payload.risk_to_reward)),
        sharpe_ratio=Decimal(str(payload.sharpe_ratio)) if payload.sharpe_ratio is not None else None,
        max_drawdown=Decimal(str(payload.max_drawdown)) if payload.max_drawdown is not None else None,
        metrics={
            **dict(payload.metrics),
            "sample_size": payload.sample_size,
            "has_critical_data_issue": payload.has_critical_data_issue,
            "notes": payload.notes,
            "decision_reasons": list(decision.reasons),
        },
    )
    session.add(evaluation)
    session.flush()

    approved_model_id: int | None = None
    if decision.approved:
        _deactivate_active_approvals(
            session,
            symbol_id=symbol.id,
            model_type=payload.model_type,
            except_model_id=payload.model_id,
        )
        approval = _upsert_approval(
            session=session,
            resolved=resolved,
            principal=principal,
            confidence=payload.confidence,
            risk_to_reward=payload.risk_to_reward,
            reason=payload.notes or "approved_by_backend_gate",
        )
        approved_model_id = approval.id
        _set_model_status(resolved, ModelStatus.APPROVED)
    else:
        _revoke_model_approval(session, resolved=resolved)
        _set_model_status(resolved, ModelStatus.REJECTED)

    _append_audit_log(
        session=session,
        principal=principal,
        payload=payload,
        symbol=symbol,
        resolved=resolved,
        evaluation=evaluation,
        decision=decision,
    )
    session.flush()
    _publish_evaluation_events(
        event_broadcaster=event_broadcaster,
        evaluation=evaluation,
        resolved=resolved,
        symbol=symbol,
        decision=decision,
        approved_model_id=approved_model_id,
    )

    return ModelEvaluationResponse(
        evaluation_id=evaluation.id,
        model_type=payload.model_type,
        model_id=payload.model_id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        evaluation_type=payload.evaluation_type,
        confidence=payload.confidence,
        risk_to_reward=payload.risk_to_reward,
        sample_size=payload.sample_size,
        max_drawdown=payload.max_drawdown,
        approved_model_id=approved_model_id,
        model_status=resolved.status.value,
        decision=ApprovalDecisionResponse(
            approved=decision.approved,
            reasons=list(decision.reasons),
            min_confidence=decision.min_confidence,
            min_risk_reward=decision.min_risk_reward,
            min_sample_size=decision.min_sample_size,
            max_approved_drawdown=decision.max_approved_drawdown,
        ),
    )


def _publish_evaluation_events(
    *,
    event_broadcaster: EventBroadcaster | None,
    evaluation: ModelEvaluation,
    resolved: ResolvedModelRecord,
    symbol: Symbol,
    decision: Any,
    approved_model_id: int | None,
) -> None:
    if event_broadcaster is None:
        return

    occurred_at = _normalize_timestamp(evaluation.evaluated_at)
    event_broadcaster.publish_event(
        event_type="evaluation_status",
        entity_type="model_evaluation",
        entity_id=str(evaluation.id),
        occurred_at=occurred_at,
        payload={
            "evaluation_id": evaluation.id,
            "model_type": resolved.model_type.value,
            "model_id": resolved.model_id,
            "symbol_id": symbol.id,
            "symbol_code": symbol.code,
            "evaluation_type": evaluation.evaluation_type.value,
            "confidence": float(evaluation.confidence),
            "risk_to_reward": float(evaluation.risk_to_reward),
            "sample_size": (evaluation.metrics or {}).get("sample_size"),
            "max_drawdown": float(evaluation.max_drawdown) if evaluation.max_drawdown is not None else None,
            "approved": decision.approved,
            "decision_reasons": list(decision.reasons),
            "model_status": resolved.status.value,
        },
    )
    event_broadcaster.publish_event(
        event_type="approval_status",
        entity_type="approved_model" if approved_model_id is not None else f"{resolved.model_type.value}_model",
        entity_id=str(approved_model_id if approved_model_id is not None else resolved.model_id),
        occurred_at=occurred_at,
        payload={
            "approved_model_id": approved_model_id,
            "model_type": resolved.model_type.value,
            "model_id": resolved.model_id,
            "symbol_id": symbol.id,
            "symbol_code": symbol.code,
            "approved": decision.approved,
            "is_active_approval": approved_model_id is not None,
            "model_status": resolved.status.value,
            "decision_reasons": list(decision.reasons),
        },
    )


def list_approved_symbols(
    *,
    session: Session,
    symbol_code: str | None = None,
    model_type: ModelType | None = None,
) -> list[ApprovedSymbolResponse]:
    statement = select(ApprovedModel).where(
        ApprovedModel.is_active.is_(True),
        ApprovedModel.revoked_at.is_(None),
    )
    if model_type is not None:
        statement = statement.where(ApprovedModel.model_type == model_type.value)
    approved_models = session.execute(statement.order_by(ApprovedModel.approved_at.desc())).scalars().all()

    normalized_code = normalize_symbol_input(symbol_code) if symbol_code else None
    responses: list[ApprovedSymbolResponse] = []
    for approval in approved_models:
        symbol = session.get(Symbol, approval.symbol_id)
        if symbol is None:
            continue
        if normalized_code and symbol.code != normalized_code:
            continue
        resolved = _resolve_approved_model(session, approval)
        responses.append(
            ApprovedSymbolResponse(
                approved_model_id=approval.id,
                symbol_id=symbol.id,
                symbol_code=symbol.code,
                model_type=_normalize_model_type(approval.model_type),
                model_id=resolved.id,
                model_name=resolved.model_name,
                algorithm=resolved.algorithm,
                confidence=float(approval.confidence),
                risk_to_reward=float(approval.risk_to_reward),
                approved_at=_normalize_approved_at(approval.approved_at),
            )
        )
    return responses


def list_models(
    *,
    session: Session,
    symbol_code: str | None = None,
    model_type: ModelType | None = None,
    status: ModelStatus | None = None,
) -> list[ModelRegistryEntryResponse]:
    symbol = _resolve_symbol_for_filter(session=session, symbol_code=symbol_code)
    active_approvals = _get_active_approval_map(
        session=session,
        symbol_id=symbol.id if symbol is not None else None,
        model_type=model_type,
    )

    entries: list[ModelRegistryEntryResponse] = []
    if model_type in {None, ModelType.SUPERVISED}:
        statement = select(SupervisedModel)
        if symbol is not None:
            statement = statement.where(SupervisedModel.symbol_id == symbol.id)
        if status is not None:
            statement = statement.where(SupervisedModel.status == status)
        models = session.execute(statement.order_by(SupervisedModel.created_at.desc())).scalars().all()
        entries.extend(
            _build_model_registry_entry(
                session=session,
                model_type=ModelType.SUPERVISED,
                model=model,
                active_approvals=active_approvals,
            )
            for model in models
        )

    if model_type in {None, ModelType.RL}:
        statement = select(RLModel)
        if symbol is not None:
            statement = statement.where(RLModel.symbol_id == symbol.id)
        if status is not None:
            statement = statement.where(RLModel.status == status)
        models = session.execute(statement.order_by(RLModel.created_at.desc())).scalars().all()
        entries.extend(
            _build_model_registry_entry(
                session=session,
                model_type=ModelType.RL,
                model=model,
                active_approvals=active_approvals,
            )
            for model in models
        )

    return sorted(entries, key=lambda item: item.created_at, reverse=True)


def list_evaluation_reports(
    *,
    session: Session,
    symbol_code: str | None = None,
    model_type: ModelType | None = None,
    model_id: int | None = None,
) -> list[ModelEvaluationSummaryResponse]:
    symbol = _resolve_symbol_for_filter(session=session, symbol_code=symbol_code)

    reports: list[ModelEvaluationSummaryResponse] = []
    if model_type in {None, ModelType.SUPERVISED}:
        statement = select(ModelEvaluation, SupervisedModel).join(
            SupervisedModel,
            ModelEvaluation.supervised_model_id == SupervisedModel.id,
        )
        if symbol is not None:
            statement = statement.where(SupervisedModel.symbol_id == symbol.id)
        if model_id is not None:
            statement = statement.where(SupervisedModel.id == model_id)
        rows = session.execute(statement.order_by(ModelEvaluation.evaluated_at.desc())).all()
        reports.extend(
            _build_evaluation_summary(
                session=session,
                evaluation=evaluation,
                model_type=ModelType.SUPERVISED,
                model=model,
            )
            for evaluation, model in rows
        )

    if model_type in {None, ModelType.RL}:
        statement = select(ModelEvaluation, RLModel).join(
            RLModel,
            ModelEvaluation.rl_model_id == RLModel.id,
        )
        if symbol is not None:
            statement = statement.where(RLModel.symbol_id == symbol.id)
        if model_id is not None:
            statement = statement.where(RLModel.id == model_id)
        rows = session.execute(statement.order_by(ModelEvaluation.evaluated_at.desc())).all()
        reports.extend(
            _build_evaluation_summary(
                session=session,
                evaluation=evaluation,
                model_type=ModelType.RL,
                model=model,
            )
            for evaluation, model in rows
        )

    return sorted(reports, key=lambda item: item.evaluated_at, reverse=True)


def is_symbol_tradeable_for_api(
    *,
    session: Session,
    symbol_id: int,
    model_type: ModelType | None = None,
) -> bool:
    return get_active_approved_model(session, symbol_id=symbol_id, model_type=model_type) is not None


def _resolve_model(*, session: Session, model_type: ModelType, model_id: int) -> ResolvedModelRecord:
    if model_type is ModelType.SUPERVISED:
        model = session.get(SupervisedModel, model_id)
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervised model {model_id} was not found.",
            )
        return ResolvedModelRecord(
            model_type=model_type,
            model_id=model.id,
            symbol_id=model.symbol_id,
            dataset_version_id=model.dataset_version_id,
            model_name=model.model_name,
            algorithm=model.algorithm,
            status=model.status,
            storage_uri=model.storage_uri,
            supervised_model=model,
        )

    model = session.get(RLModel, model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RL model {model_id} was not found.",
        )
    return ResolvedModelRecord(
        model_type=model_type,
        model_id=model.id,
        symbol_id=model.symbol_id,
        dataset_version_id=model.dataset_version_id,
        model_name=model.model_name,
        algorithm=model.algorithm,
        status=model.status,
        storage_uri=model.storage_uri,
        rl_model=model,
    )


def _resolve_symbol_for_filter(*, session: Session, symbol_code: str | None) -> Symbol | None:
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


def _get_active_approval_map(
    *,
    session: Session,
    symbol_id: int | None,
    model_type: ModelType | None,
) -> dict[tuple[ModelType, int], ApprovedModel]:
    statement = select(ApprovedModel).where(
        ApprovedModel.is_active.is_(True),
        ApprovedModel.revoked_at.is_(None),
    )
    if symbol_id is not None:
        statement = statement.where(ApprovedModel.symbol_id == symbol_id)
    if model_type is not None:
        statement = statement.where(ApprovedModel.model_type == model_type.value)

    approvals = session.execute(statement).scalars().all()
    approval_map: dict[tuple[ModelType, int], ApprovedModel] = {}
    for approval in approvals:
        approval_model_type = _normalize_model_type(approval.model_type)
        resolved_model_id = approval.supervised_model_id if approval_model_type is ModelType.SUPERVISED else approval.rl_model_id
        if resolved_model_id is None:
            continue
        approval_map[(approval_model_type, resolved_model_id)] = approval
    return approval_map


def _build_model_registry_entry(
    *,
    session: Session,
    model_type: ModelType,
    model: SupervisedModel | RLModel,
    active_approvals: dict[tuple[ModelType, int], ApprovedModel],
) -> ModelRegistryEntryResponse:
    symbol = session.get(Symbol, model.symbol_id)
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {model.symbol_id} for model {model.id} was not found.",
        )

    approval = active_approvals.get((model_type, model.id))
    return ModelRegistryEntryResponse(
        model_type=model_type,
        model_id=model.id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        dataset_version_id=model.dataset_version_id,
        feature_set_id=getattr(model, "feature_set_id", None),
        training_job_id=model.training_job_id,
        model_name=model.model_name,
        version_tag=model.version_tag,
        algorithm=model.algorithm,
        status=model.status.value,
        storage_uri=model.storage_uri,
        approved_model_id=approval.id if approval is not None else None,
        is_active_approval=approval is not None,
        created_at=_normalize_timestamp(model.created_at),
    )


def _build_evaluation_summary(
    *,
    session: Session,
    evaluation: ModelEvaluation,
    model_type: ModelType,
    model: SupervisedModel | RLModel,
) -> ModelEvaluationSummaryResponse:
    symbol = session.get(Symbol, model.symbol_id)
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {model.symbol_id} for evaluation {evaluation.id} was not found.",
        )

    metrics = dict(evaluation.metrics or {})
    decision_reasons = metrics.get("decision_reasons") or []
    return ModelEvaluationSummaryResponse(
        evaluation_id=evaluation.id,
        model_type=model_type,
        model_id=model.id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        dataset_version_id=evaluation.dataset_version_id,
        evaluation_type=evaluation.evaluation_type,
        confidence=float(evaluation.confidence),
        risk_to_reward=float(evaluation.risk_to_reward),
        sample_size=metrics.get("sample_size"),
        max_drawdown=float(evaluation.max_drawdown) if evaluation.max_drawdown is not None else None,
        approved=_is_model_currently_approved(
            session=session,
            model_type=model_type,
            model_id=model.id,
        ),
        decision_reasons=[str(reason) for reason in decision_reasons],
        evaluated_at=_normalize_timestamp(evaluation.evaluated_at),
    )


def _upsert_approval(
    *,
    session: Session,
    resolved: ResolvedModelRecord,
    principal: AuthPrincipal,
    confidence: float,
    risk_to_reward: float,
    reason: str,
) -> ApprovedModel:
    statement = select(ApprovedModel).where(
        ApprovedModel.supervised_model_id == (resolved.supervised_model.id if resolved.supervised_model else None),
        ApprovedModel.rl_model_id == (resolved.rl_model.id if resolved.rl_model else None),
    )
    approval = session.execute(statement).scalars().first()
    if approval is None:
        approval = ApprovedModel(
            symbol_id=resolved.symbol_id,
            supervised_model_id=resolved.supervised_model.id if resolved.supervised_model else None,
            rl_model_id=resolved.rl_model.id if resolved.rl_model else None,
            model_type=resolved.model_type.value,
        )
        session.add(approval)

    approval.model_type = resolved.model_type.value
    approval.approved_by = principal.subject
    approval.approval_reason = reason
    approval.confidence = Decimal(str(confidence))
    approval.risk_to_reward = Decimal(str(risk_to_reward))
    approval.is_active = True
    approval.revoked_at = None
    session.flush()
    return approval


def _revoke_model_approval(session: Session, *, resolved: ResolvedModelRecord) -> None:
    approval = get_active_approved_model(session, symbol_id=resolved.symbol_id, model_type=resolved.model_type)
    if approval is None:
        return
    if resolved.model_type is ModelType.SUPERVISED and approval.supervised_model_id != resolved.model_id:
        return
    if resolved.model_type is ModelType.RL and approval.rl_model_id != resolved.model_id:
        return
    approval.is_active = False
    approval.revoked_at = datetime.now(UTC)
    session.add(approval)


def _deactivate_active_approvals(
    session: Session,
    *,
    symbol_id: int,
    model_type: ModelType,
    except_model_id: int,
) -> None:
    approvals = session.execute(
        select(ApprovedModel).where(
            ApprovedModel.symbol_id == symbol_id,
            ApprovedModel.model_type == model_type.value,
            ApprovedModel.is_active.is_(True),
            ApprovedModel.revoked_at.is_(None),
        )
    ).scalars().all()
    for approval in approvals:
        current_model_id = approval.supervised_model_id if model_type is ModelType.SUPERVISED else approval.rl_model_id
        if current_model_id == except_model_id:
            continue
        approval.is_active = False
        approval.revoked_at = datetime.now(UTC)
        session.add(approval)


def _set_model_status(resolved: ResolvedModelRecord, status: ModelStatus) -> None:
    if resolved.supervised_model is not None:
        resolved.supervised_model.status = status
        object.__setattr__(resolved, "status", status)
        return
    if resolved.rl_model is not None:
        resolved.rl_model.status = status
        object.__setattr__(resolved, "status", status)


def _append_audit_log(
    *,
    session: Session,
    principal: AuthPrincipal,
    payload: ModelEvaluationCreate,
    symbol: Symbol,
    resolved: ResolvedModelRecord,
    evaluation: ModelEvaluation,
    decision: Any,
) -> None:
    session.add(
        AuditLog(
            action="model_evaluation",
            actor_type="api_principal",
            actor_id=principal.subject,
            entity_type=f"{resolved.model_type.value}_model",
            entity_id=str(resolved.model_id),
            outcome=AuditOutcome.SUCCESS if decision.approved else AuditOutcome.BLOCKED,
            message=(
                f"Model {resolved.model_type.value}:{resolved.model_id} "
                f"{'approved' if decision.approved else 'rejected'} for symbol {symbol.code}."
            ),
            details={
                "evaluation_id": evaluation.id,
                "evaluation_type": payload.evaluation_type.value,
                "confidence": payload.confidence,
                "risk_to_reward": payload.risk_to_reward,
                "sample_size": payload.sample_size,
                "max_drawdown": payload.max_drawdown,
                "reasons": list(decision.reasons),
            },
        )
    )


def _resolve_approved_model(session: Session, approval: ApprovedModel) -> SupervisedModel | RLModel:
    if _normalize_model_type(approval.model_type) is ModelType.SUPERVISED:
        model = session.get(SupervisedModel, approval.supervised_model_id)
        if model is None:
            raise HTTPException(status_code=404, detail="Approved supervised model could not be resolved.")
        return model
    model = session.get(RLModel, approval.rl_model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Approved RL model could not be resolved.")
    return model


def _normalize_approved_at(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_model_type(value: ModelType | str) -> ModelType:
    if isinstance(value, ModelType):
        return value
    return ModelType(value)


def _is_model_currently_approved(
    *,
    session: Session,
    model_type: ModelType,
    model_id: int,
) -> bool:
    statement = select(ApprovedModel).where(
        ApprovedModel.is_active.is_(True),
        ApprovedModel.revoked_at.is_(None),
    )
    if model_type is ModelType.SUPERVISED:
        statement = statement.where(ApprovedModel.supervised_model_id == model_id)
    else:
        statement = statement.where(ApprovedModel.rl_model_id == model_id)
    return session.execute(statement).scalars().first() is not None
