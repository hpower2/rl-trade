"""Supervised-training helpers for baseline and PyTorch model comparison."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any

from rl_trade_features import BuiltDataset

CLASS_LABELS = ("buy", "sell", "no_trade")
LABEL_TO_INDEX = {label: index for index, label in enumerate(CLASS_LABELS)}
INDEX_TO_LABEL = {index: label for label, index in LABEL_TO_INDEX.items()}


@dataclass(frozen=True, slots=True)
class StandardScalerState:
    means: dict[str, float]
    stds: dict[str, float]


@dataclass(frozen=True, slots=True)
class BaselineComparison:
    algorithm: str
    validation_accuracy: float
    walk_forward_accuracy: float
    predicted_labels: tuple[str, ...]
    confidences: tuple[float, ...]
    setup_qualities: tuple[float, ...]
    model_payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SupervisedTrainingArtifacts:
    chosen_algorithm: str
    scaler: StandardScalerState
    feature_columns: tuple[str, ...]
    label_name: str
    train_row_count: int
    validation_row_count: int
    device: str
    comparisons: tuple[BaselineComparison, ...]
    checkpoint_state: dict[str, Any] | None = None

    @property
    def metrics(self) -> dict[str, Any]:
        best = next(item for item in self.comparisons if item.algorithm == self.chosen_algorithm)
        return {
            "chosen_algorithm": self.chosen_algorithm,
            "train_row_count": self.train_row_count,
            "validation_row_count": self.validation_row_count,
            "device": self.device,
            "validation_accuracy": round(best.validation_accuracy, 6),
            "walk_forward_accuracy": round(best.walk_forward_accuracy, 6),
            "comparisons": [
                {
                    "algorithm": item.algorithm,
                    "validation_accuracy": round(item.validation_accuracy, 6),
                    "walk_forward_accuracy": round(item.walk_forward_accuracy, 6),
                }
                for item in self.comparisons
            ],
        }


@dataclass(frozen=True, slots=True)
class SavedSupervisedArtifacts:
    feature_schema: dict[str, Any]
    scaler_state: dict[str, Any]
    model_state: dict[str, Any]
    metrics: dict[str, Any]


def train_supervised_baselines(
    dataset: BuiltDataset,
    *,
    validation_ratio: float = 0.2,
    walk_forward_folds: int = 3,
) -> SupervisedTrainingArtifacts:
    if dataset.row_count < 6:
        raise ValueError("Supervised training requires at least 6 dataset rows.")

    split_index = max(3, int(round(dataset.row_count * (1.0 - validation_ratio))))
    split_index = min(split_index, dataset.row_count - 1)
    train_rows = dataset.rows[:split_index]
    validation_rows = dataset.rows[split_index:]
    if len(train_rows) < 3 or len(validation_rows) < 1:
        raise ValueError("Supervised training requires both training and validation rows.")

    scaler = fit_standard_scaler(rows=train_rows, feature_columns=dataset.feature_columns)
    scaled_train = [scale_row(row=row, scaler=scaler, feature_columns=dataset.feature_columns) for row in train_rows]
    scaled_validation = [scale_row(row=row, scaler=scaler, feature_columns=dataset.feature_columns) for row in validation_rows]

    majority_payload = fit_majority_baseline(labels=[str(row.label) for row in train_rows])
    majority_predictions = [predict_majority(majority_payload) for _ in validation_rows]
    majority_comparison = BaselineComparison(
        algorithm="majority_class",
        validation_accuracy=compute_accuracy(
            truth=[str(row.label) for row in validation_rows],
            predicted=[prediction["label"] for prediction in majority_predictions],
        ),
        walk_forward_accuracy=compute_walk_forward_accuracy(
            dataset=dataset,
            feature_columns=dataset.feature_columns,
            walk_forward_folds=walk_forward_folds,
            trainer="majority_class",
        ),
        predicted_labels=tuple(prediction["label"] for prediction in majority_predictions),
        confidences=tuple(prediction["confidence"] for prediction in majority_predictions),
        setup_qualities=tuple(prediction["setup_quality"] for prediction in majority_predictions),
        model_payload=majority_payload,
    )

    centroid_payload = fit_centroid_baseline(
        rows=scaled_train,
        labels=[str(row.label) for row in train_rows],
        feature_columns=dataset.feature_columns,
    )
    centroid_predictions = [
        predict_centroid(
            centroid_payload,
            features=features,
            feature_columns=dataset.feature_columns,
        )
        for features in scaled_validation
    ]
    centroid_comparison = BaselineComparison(
        algorithm="nearest_centroid",
        validation_accuracy=compute_accuracy(
            truth=[str(row.label) for row in validation_rows],
            predicted=[prediction["label"] for prediction in centroid_predictions],
        ),
        walk_forward_accuracy=compute_walk_forward_accuracy(
            dataset=dataset,
            feature_columns=dataset.feature_columns,
            walk_forward_folds=walk_forward_folds,
            trainer="nearest_centroid",
        ),
        predicted_labels=tuple(prediction["label"] for prediction in centroid_predictions),
        confidences=tuple(prediction["confidence"] for prediction in centroid_predictions),
        setup_qualities=tuple(prediction["setup_quality"] for prediction in centroid_predictions),
        model_payload=centroid_payload,
    )

    comparisons = tuple(
        sorted(
            (majority_comparison, centroid_comparison),
            key=lambda item: (item.validation_accuracy, item.walk_forward_accuracy, item.algorithm == "nearest_centroid"),
            reverse=True,
        )
    )
    return SupervisedTrainingArtifacts(
        chosen_algorithm=comparisons[0].algorithm,
        scaler=scaler,
        feature_columns=tuple(dataset.feature_columns),
        label_name=dataset.label_name,
        train_row_count=len(train_rows),
        validation_row_count=len(validation_rows),
        device="cpu",
        comparisons=comparisons,
    )


def train_torch_mlp(
    dataset: BuiltDataset,
    *,
    validation_ratio: float = 0.2,
    walk_forward_folds: int = 3,
    hidden_dim: int = 16,
    epochs: int = 25,
    learning_rate: float = 0.01,
    seed: int = 7,
) -> SupervisedTrainingArtifacts:
    torch, nn = _require_torch()

    if dataset.row_count < 6:
        raise ValueError("Supervised training requires at least 6 dataset rows.")

    split_index = max(3, int(round(dataset.row_count * (1.0 - validation_ratio))))
    split_index = min(split_index, dataset.row_count - 1)
    train_rows = dataset.rows[:split_index]
    validation_rows = dataset.rows[split_index:]
    if len(train_rows) < 3 or len(validation_rows) < 1:
        raise ValueError("Supervised training requires both training and validation rows.")

    scaler = fit_standard_scaler(rows=train_rows, feature_columns=dataset.feature_columns)
    device = resolve_torch_device(torch)
    model, comparison = _train_torch_model(
        torch=torch,
        nn=nn,
        train_rows=train_rows,
        validation_rows=validation_rows,
        scaler=scaler,
        feature_columns=dataset.feature_columns,
        hidden_dim=hidden_dim,
        epochs=epochs,
        learning_rate=learning_rate,
        device=device,
        seed=seed,
    )
    walk_forward_accuracy = compute_torch_walk_forward_accuracy(
        torch=torch,
        nn=nn,
        dataset=dataset,
        feature_columns=dataset.feature_columns,
        walk_forward_folds=walk_forward_folds,
        hidden_dim=hidden_dim,
        epochs=max(3, epochs // 2),
        learning_rate=learning_rate,
        device=device,
        seed=seed,
    )
    comparison = BaselineComparison(
        algorithm="torch_mlp",
        validation_accuracy=comparison.validation_accuracy,
        walk_forward_accuracy=walk_forward_accuracy,
        predicted_labels=comparison.predicted_labels,
        confidences=comparison.confidences,
        setup_qualities=comparison.setup_qualities,
        model_payload={
            **comparison.model_payload,
            "hidden_dim": hidden_dim,
            "epochs": epochs,
            "learning_rate": learning_rate,
        },
    )

    return SupervisedTrainingArtifacts(
        chosen_algorithm="torch_mlp",
        scaler=scaler,
        feature_columns=tuple(dataset.feature_columns),
        label_name=dataset.label_name,
        train_row_count=len(train_rows),
        validation_row_count=len(validation_rows),
        device=device,
        comparisons=(comparison,),
        checkpoint_state={
            "algorithm": "torch_mlp",
            "input_dim": len(dataset.feature_columns),
            "hidden_dim": hidden_dim,
            "output_dim": len(CLASS_LABELS),
            "feature_columns": list(dataset.feature_columns),
            "label_name": dataset.label_name,
            "device": device,
            "state_dict": model.state_dict(),
        },
    )


def fit_standard_scaler(*, rows: tuple[Any, ...] | list[Any], feature_columns: tuple[str, ...]) -> StandardScalerState:
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    for column in feature_columns:
        values = [to_float(row.features[column]) for row in rows]
        mean_value = sum(values) / len(values)
        variance = sum((value - mean_value) ** 2 for value in values) / len(values)
        means[column] = mean_value
        stds[column] = sqrt(variance) or 1.0
    return StandardScalerState(means=means, stds=stds)


def scale_row(*, row: Any, scaler: StandardScalerState, feature_columns: tuple[str, ...]) -> dict[str, float]:
    return {
        column: (to_float(row.features[column]) - scaler.means[column]) / scaler.stds[column]
        for column in feature_columns
    }


def fit_majority_baseline(*, labels: list[str]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    total = sum(counts.values())
    probabilities = {label: count / total for label, count in counts.items()}
    majority_label = max(probabilities, key=probabilities.get)
    return {
        "algorithm": "majority_class",
        "majority_label": majority_label,
        "class_probabilities": probabilities,
    }


def predict_majority(payload: dict[str, Any]) -> dict[str, float | str]:
    probabilities = payload["class_probabilities"]
    label = str(payload["majority_label"])
    confidence = float(probabilities[label])
    directional_confidence = max(float(probabilities.get("buy", 0.0)), float(probabilities.get("sell", 0.0)))
    return {
        "label": label,
        "confidence": confidence,
        "setup_quality": max(0.0, directional_confidence - float(probabilities.get("no_trade", 0.0))),
    }


def fit_centroid_baseline(
    *,
    rows: list[dict[str, float]],
    labels: list[str],
    feature_columns: tuple[str, ...],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, float]]] = {}
    for row, label in zip(rows, labels, strict=True):
        grouped.setdefault(label, []).append(row)

    centroids = {
        label: {
            column: sum(sample[column] for sample in samples) / len(samples)
            for column in feature_columns
        }
        for label, samples in grouped.items()
    }
    return {
        "algorithm": "nearest_centroid",
        "centroids": centroids,
        "feature_columns": list(feature_columns),
    }


def predict_centroid(
    payload: dict[str, Any],
    *,
    features: dict[str, float],
    feature_columns: tuple[str, ...],
) -> dict[str, float | str]:
    distances: dict[str, float] = {}
    for label, centroid in payload["centroids"].items():
        squared_distance = sum((features[column] - float(centroid[column])) ** 2 for column in feature_columns)
        distances[str(label)] = sqrt(squared_distance)

    inverse_scores = {label: 1.0 / (1.0 + distance) for label, distance in distances.items()}
    normalization = sum(inverse_scores.values()) or 1.0
    probabilities = {label: score / normalization for label, score in inverse_scores.items()}
    label = max(probabilities, key=probabilities.get)
    return {
        "label": label,
        "confidence": probabilities[label],
        "setup_quality": max(0.0, max(probabilities.get("buy", 0.0), probabilities.get("sell", 0.0)) - probabilities.get("no_trade", 0.0)),
    }


def resolve_torch_device(torch: Any) -> str:
    if not torch.cuda.is_available():
        return "cpu"

    try:
        probe = torch.nn.Linear(1, 1).to("cuda")
        sample = torch.zeros((1, 1), device="cuda")
        with torch.no_grad():
            probe(sample)
        return "cuda"
    except Exception:
        return "cpu"


def compute_torch_walk_forward_accuracy(
    *,
    torch: Any,
    nn: Any,
    dataset: BuiltDataset,
    feature_columns: tuple[str, ...],
    walk_forward_folds: int,
    hidden_dim: int,
    epochs: int,
    learning_rate: float,
    device: str,
    seed: int,
) -> float:
    min_train_rows = max(3, len(dataset.rows) // 2)
    remaining = len(dataset.rows) - min_train_rows
    if remaining <= 0:
        return 0.0

    actual_folds = min(max(walk_forward_folds, 1), remaining)
    fold_size = max(1, remaining // actual_folds)
    accuracies: list[float] = []

    for fold_index in range(actual_folds):
        train_end = min_train_rows + (fold_index * fold_size)
        validation_end = min(len(dataset.rows), train_end + fold_size)
        train_rows = dataset.rows[:train_end]
        validation_rows = dataset.rows[train_end:validation_end]
        if len(train_rows) < 3 or not validation_rows:
            continue

        scaler = fit_standard_scaler(rows=train_rows, feature_columns=feature_columns)
        _, comparison = _train_torch_model(
            torch=torch,
            nn=nn,
            train_rows=train_rows,
            validation_rows=validation_rows,
            scaler=scaler,
            feature_columns=feature_columns,
            hidden_dim=hidden_dim,
            epochs=epochs,
            learning_rate=learning_rate,
            device=device,
            seed=seed + fold_index + 1,
        )
        accuracies.append(comparison.validation_accuracy)

    return sum(accuracies) / len(accuracies) if accuracies else 0.0


def compute_walk_forward_accuracy(
    *,
    dataset: BuiltDataset,
    feature_columns: tuple[str, ...],
    walk_forward_folds: int,
    trainer: str,
) -> float:
    min_train_rows = max(3, len(dataset.rows) // 2)
    remaining = len(dataset.rows) - min_train_rows
    if remaining <= 0:
        return 0.0

    actual_folds = min(max(walk_forward_folds, 1), remaining)
    fold_size = max(1, remaining // actual_folds)
    accuracies: list[float] = []

    for fold_index in range(actual_folds):
        train_end = min_train_rows + (fold_index * fold_size)
        validation_end = min(len(dataset.rows), train_end + fold_size)
        train_rows = dataset.rows[:train_end]
        validation_rows = dataset.rows[train_end:validation_end]
        if len(train_rows) < 3 or not validation_rows:
            continue

        scaler = fit_standard_scaler(rows=train_rows, feature_columns=feature_columns)
        if trainer == "majority_class":
            payload = fit_majority_baseline(labels=[str(row.label) for row in train_rows])
            predicted = [predict_majority(payload)["label"] for _ in validation_rows]
        else:
            payload = fit_centroid_baseline(
                rows=[scale_row(row=row, scaler=scaler, feature_columns=feature_columns) for row in train_rows],
                labels=[str(row.label) for row in train_rows],
                feature_columns=feature_columns,
            )
            predicted = [
                predict_centroid(
                    payload,
                    features=scale_row(row=row, scaler=scaler, feature_columns=feature_columns),
                    feature_columns=feature_columns,
                )["label"]
                for row in validation_rows
            ]

        accuracies.append(
            compute_accuracy(
                truth=[str(row.label) for row in validation_rows],
                predicted=[str(label) for label in predicted],
            )
        )

    return sum(accuracies) / len(accuracies) if accuracies else 0.0


def compute_accuracy(*, truth: list[str], predicted: list[str]) -> float:
    if not truth:
        return 0.0
    matches = sum(1 for actual, guess in zip(truth, predicted, strict=True) if actual == guess)
    return matches / len(truth)


def _require_torch() -> tuple[Any, Any]:
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("torch is required for torch_mlp training.") from exc
    return torch, nn


def _build_mlp_model(*, nn: Any, input_dim: int, hidden_dim: int, output_dim: int) -> Any:
    return nn.Sequential(
        nn.Linear(input_dim, hidden_dim),
        nn.ReLU(),
        nn.Linear(hidden_dim, output_dim),
    )


def _train_torch_model(
    *,
    torch: Any,
    nn: Any,
    train_rows: tuple[Any, ...] | list[Any],
    validation_rows: tuple[Any, ...] | list[Any],
    scaler: StandardScalerState,
    feature_columns: tuple[str, ...],
    hidden_dim: int,
    epochs: int,
    learning_rate: float,
    device: str,
    seed: int,
) -> tuple[Any, BaselineComparison]:
    torch.manual_seed(seed)
    model = _build_mlp_model(
        nn=nn,
        input_dim=len(feature_columns),
        hidden_dim=hidden_dim,
        output_dim=len(CLASS_LABELS),
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = nn.CrossEntropyLoss()

    train_features = torch.tensor(
        [[scale_row(row=row, scaler=scaler, feature_columns=feature_columns)[column] for column in feature_columns] for row in train_rows],
        dtype=torch.float32,
        device=device,
    )
    train_labels = torch.tensor(
        [LABEL_TO_INDEX[str(row.label)] for row in train_rows],
        dtype=torch.long,
        device=device,
    )

    for _ in range(max(1, epochs)):
        optimizer.zero_grad()
        logits = model(train_features)
        loss = loss_fn(logits, train_labels)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        validation_features = torch.tensor(
            [
                [scale_row(row=row, scaler=scaler, feature_columns=feature_columns)[column] for column in feature_columns]
                for row in validation_rows
            ],
            dtype=torch.float32,
            device=device,
        )
        probabilities = torch.softmax(model(validation_features), dim=1).cpu().tolist()

    predicted_labels = tuple(INDEX_TO_LABEL[int(max(range(len(scores)), key=lambda idx: scores[idx]))] for scores in probabilities)
    confidences = tuple(float(max(scores)) for scores in probabilities)
    setup_qualities = tuple(float(max(scores[LABEL_TO_INDEX["buy"]], scores[LABEL_TO_INDEX["sell"]]) - scores[LABEL_TO_INDEX["no_trade"]]) for scores in probabilities)
    validation_accuracy = compute_accuracy(
        truth=[str(row.label) for row in validation_rows],
        predicted=list(predicted_labels),
    )
    return model, BaselineComparison(
        algorithm="torch_mlp",
        validation_accuracy=validation_accuracy,
        walk_forward_accuracy=0.0,
        predicted_labels=predicted_labels,
        confidences=confidences,
        setup_qualities=setup_qualities,
        model_payload={
            "algorithm": "torch_mlp",
            "class_labels": list(CLASS_LABELS),
        },
    )


def artifact_payload(training: SupervisedTrainingArtifacts) -> dict[str, Any]:
    best = next(item for item in training.comparisons if item.algorithm == training.chosen_algorithm)
    return {
        "chosen_algorithm": training.chosen_algorithm,
        "label_name": training.label_name,
        "feature_columns": list(training.feature_columns),
        "device": training.device,
        "scaler": {
            "means": training.scaler.means,
            "stds": training.scaler.stds,
        },
        "comparisons": [
            {
                "algorithm": item.algorithm,
                "validation_accuracy": item.validation_accuracy,
                "walk_forward_accuracy": item.walk_forward_accuracy,
                "predicted_labels": list(item.predicted_labels),
                "confidences": list(item.confidences),
                "setup_qualities": list(item.setup_qualities),
            }
            for item in training.comparisons
        ],
        "selected_model": best.model_payload,
    }


def load_supervised_artifacts(*, artifact_dir: str | Path) -> SavedSupervisedArtifacts:
    root = Path(artifact_dir)
    model_json_path = root / "model.json"
    checkpoint_path = root / "checkpoint.pt"
    return SavedSupervisedArtifacts(
        feature_schema=load_json_artifact(root / "feature_schema.json"),
        scaler_state=load_json_artifact(root / "scaler.json"),
        model_state=load_json_artifact(model_json_path) if model_json_path.exists() else load_torch_checkpoint(checkpoint_path),
        metrics=load_json_artifact(root / "metrics.json"),
    )


def load_json_artifact(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_torch_checkpoint(path: str | Path) -> dict[str, Any]:
    torch, _ = _require_torch()
    return torch.load(Path(path), map_location="cpu")


def to_float(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)
