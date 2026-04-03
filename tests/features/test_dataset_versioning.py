"""Dataset versioning helper tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from rl_trade_data import Base, Symbol, build_engine, build_session_factory, session_scope
from rl_trade_data.models import DatasetStatus, Timeframe
from rl_trade_features import DatasetRow, FeatureSetSpec, build_dataset, create_dataset_version, ensure_feature_set


def test_build_dataset_is_deterministic_for_identical_rows() -> None:
    first = build_dataset(
        rows=[
            DatasetRow(
                timestamp=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
                features={"ema_3": Decimal("1.1000"), "pattern_doji": False},
                label="buy",
            )
        ],
        label_name="direction",
    )
    second = build_dataset(
        rows=[
            DatasetRow(
                timestamp=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
                features={"pattern_doji": False, "ema_3": Decimal("1.1000")},
                label="buy",
            )
        ],
        label_name="direction",
        feature_columns=["ema_3", "pattern_doji"],
    )

    assert first.data_hash == second.data_hash
    assert first.version_tag == second.version_tag
    assert first.feature_columns == ("ema_3", "pattern_doji")


def test_dataset_version_helpers_persist_feature_set_and_dataset_version(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'dataset_versioning.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()

        feature_set = ensure_feature_set(
            session,
            spec=FeatureSetSpec(
                name="baseline_forex",
                version="v1",
                description="Baseline deterministic feature set",
                feature_columns=["ema_3", "pattern_doji", "m15_trend"],
                indicator_columns=["ema_3"],
                pattern_columns=["pattern_doji"],
                parameters={"primary_timeframe": "1m"},
            ),
        )
        dataset = build_dataset(
            rows=[
                DatasetRow(
                    timestamp=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
                    features={"ema_3": Decimal("1.1000"), "pattern_doji": False, "m15_trend": 1},
                    label="buy",
                ),
                DatasetRow(
                    timestamp=datetime(2026, 1, 1, 9, 1, tzinfo=UTC),
                    features={"ema_3": Decimal("1.1005"), "pattern_doji": True, "m15_trend": 1},
                    label="no_trade",
                ),
            ],
            label_name="direction",
            feature_columns=["ema_3", "pattern_doji", "m15_trend"],
        )

        dataset_version = create_dataset_version(
            session,
            symbol_id=symbol.id,
            feature_set_id=feature_set.id,
            dataset=dataset,
            primary_timeframe=Timeframe.M1,
            included_timeframes=[Timeframe.M1, Timeframe.M5, Timeframe.M15],
            storage_uri="memory://baseline_forex/v1",
            status=DatasetStatus.READY,
            details={"labeling_strategy": "trade_setup"},
        )

    with session_scope(session_factory) as session:
        stored_feature_set = session.get(type(feature_set), feature_set.id)
        stored_dataset = session.get(type(dataset_version), dataset_version.id)

    assert stored_feature_set is not None
    assert stored_feature_set.feature_columns == ["ema_3", "pattern_doji", "m15_trend"]
    assert stored_dataset is not None
    assert stored_dataset.status is DatasetStatus.READY
    assert stored_dataset.label_name == "direction"
    assert stored_dataset.row_count == 2
    assert stored_dataset.data_hash == dataset.data_hash
    assert stored_dataset.version_tag == dataset.version_tag
    assert stored_dataset.included_timeframes == ["1m", "5m", "15m"]
    assert stored_dataset.details["feature_columns"] == ["ema_3", "pattern_doji", "m15_trend"]
    assert stored_dataset.details["labeling_strategy"] == "trade_setup"
    engine.dispose()


def test_create_dataset_version_is_idempotent_for_same_hash(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'dataset_versioning_idempotent.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()
        feature_set = ensure_feature_set(
            session,
            spec=FeatureSetSpec(name="baseline_forex", version="v1", feature_columns=["ema_3"]),
        )
        dataset = build_dataset(
            rows=[
                DatasetRow(
                    timestamp=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
                    features={"ema_3": Decimal("1.1000")},
                    label="buy",
                )
            ],
            label_name="direction",
        )

        first = create_dataset_version(
            session,
            symbol_id=symbol.id,
            feature_set_id=feature_set.id,
            dataset=dataset,
            primary_timeframe=Timeframe.M1,
            included_timeframes=[Timeframe.M1],
        )
        second = create_dataset_version(
            session,
            symbol_id=symbol.id,
            feature_set_id=feature_set.id,
            dataset=dataset,
            primary_timeframe=Timeframe.M1,
            included_timeframes=[Timeframe.M1],
        )

    assert first.id == second.id
    engine.dispose()
