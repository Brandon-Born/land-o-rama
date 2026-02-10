from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import FeatureVector, Feedback, ModelTrainingRun, Opportunity


@dataclass(slots=True)
class PersonalizationModel:
    version: str
    features: list[str]
    weights: list[float]
    bias: float


@dataclass(slots=True)
class TrainingRow:
    values: list[float]
    label: int


_FEATURES = [
    "market_growth",
    "development_pressure",
    "accessibility",
    "liquidity",
    "risk_inverse",
    "base_score",
    "price_norm",
    "acreage_norm",
]


def count_labels(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(Feedback).where(Feedback.vote.in_(["up", "down"]))
    ) or 0


def load_active_model() -> PersonalizationModel | None:
    settings = get_settings()
    path = Path(settings.personalization_model_path)
    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None

    features = payload.get("features")
    weights = payload.get("weights")
    bias = payload.get("bias")
    version = payload.get("version")
    if not isinstance(features, list) or not isinstance(weights, list) or len(features) != len(weights):
        return None
    if not isinstance(version, str):
        return None

    return PersonalizationModel(
        version=version,
        features=[str(item) for item in features],
        weights=[float(item) for item in weights],
        bias=float(bias),
    )


def train_if_threshold_met(db: Session, threshold: int | None = None) -> ModelTrainingRun | None:
    settings = get_settings()
    effective_threshold = threshold if threshold is not None else settings.personalization_threshold
    label_count = count_labels(db)
    if label_count < effective_threshold:
        return None

    rows = _training_rows(db)
    if len(rows) < effective_threshold:
        training_run = ModelTrainingRun(
            model_version="insufficient-data",
            labels_used=len(rows),
            status="failed",
            metrics_json={"reason": "insufficient joined feature rows"},
            error_summary="Feedback labels did not have matching opportunity feature vectors.",
        )
        db.add(training_run)
        db.commit()
        db.refresh(training_run)
        return training_run

    model = _train_logistic(rows, epochs=700, learning_rate=0.2)
    metrics = _classification_metrics(model, rows)

    version = f"pers-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    artifact_path = Path(settings.personalization_model_path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "version": version,
                "features": _FEATURES,
                "weights": model.weights,
                "bias": model.bias,
                "trained_at": datetime.now(UTC).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    training_run = ModelTrainingRun(
        model_version=version,
        labels_used=len(rows),
        status="success",
        metrics_json=metrics,
        artifact_path=str(artifact_path),
    )
    db.add(training_run)
    db.commit()
    db.refresh(training_run)
    return training_run


def score_personalization(
    model: PersonalizationModel,
    *,
    market_growth_score: float,
    development_pressure_score: float,
    accessibility_score: float,
    liquidity_score: float,
    risk_penalty_score: float,
    base_score: float,
    price: float,
    acreage: float,
) -> float:
    feature_values = _feature_vector(
        market_growth_score=market_growth_score,
        development_pressure_score=development_pressure_score,
        accessibility_score=accessibility_score,
        liquidity_score=liquidity_score,
        risk_penalty_score=risk_penalty_score,
        base_score=base_score,
        price=price,
        acreage=acreage,
    )

    z = model.bias + sum(weight * value for weight, value in zip(model.weights, feature_values, strict=True))
    probability = _sigmoid(z)
    return round(probability * 100.0, 2)


def _training_rows(db: Session) -> list[TrainingRow]:
    feedback_rows = db.scalars(
        select(Feedback).where(Feedback.vote.in_(["up", "down"])).order_by(Feedback.created_at.asc(), Feedback.id.asc())
    ).all()

    rows: list[TrainingRow] = []
    for feedback in feedback_rows:
        opportunity = db.get(Opportunity, feedback.opportunity_id)
        if not opportunity:
            continue
        feature = db.scalar(
            select(FeatureVector)
            .where(
                FeatureVector.run_id == opportunity.run_id,
                FeatureVector.parcel_id == opportunity.parcel_id,
            )
            .order_by(desc(FeatureVector.created_at))
            .limit(1)
        )
        if not feature:
            continue

        values = _feature_vector(
            market_growth_score=feature.market_growth_score,
            development_pressure_score=feature.development_pressure_score,
            accessibility_score=feature.accessibility_score,
            liquidity_score=feature.liquidity_score,
            risk_penalty_score=feature.risk_penalty_score,
            base_score=opportunity.base_score,
            price=opportunity.price,
            acreage=opportunity.acreage,
        )
        rows.append(TrainingRow(values=values, label=1 if feedback.vote == "up" else 0))
    return rows


def _feature_vector(
    *,
    market_growth_score: float,
    development_pressure_score: float,
    accessibility_score: float,
    liquidity_score: float,
    risk_penalty_score: float,
    base_score: float,
    price: float,
    acreage: float,
) -> list[float]:
    return [
        _normalize_score(market_growth_score),
        _normalize_score(development_pressure_score),
        _normalize_score(accessibility_score),
        _normalize_score(liquidity_score),
        _normalize_score(100 - risk_penalty_score),
        _normalize_score(base_score),
        max(0.0, min(1.0, price / 6000.0)),
        max(0.0, min(1.0, acreage / 5.0)),
    ]


def _normalize_score(value: float) -> float:
    return max(0.0, min(1.0, value / 100.0))


def _train_logistic(rows: list[TrainingRow], *, epochs: int, learning_rate: float) -> PersonalizationModel:
    weights = [0.0 for _ in _FEATURES]
    bias = 0.0

    for _ in range(epochs):
        grad_w = [0.0 for _ in _FEATURES]
        grad_b = 0.0
        for row in rows:
            z = bias + sum(weight * value for weight, value in zip(weights, row.values, strict=True))
            probability = _sigmoid(z)
            error = probability - row.label
            for idx, value in enumerate(row.values):
                grad_w[idx] += error * value
            grad_b += error

        scale = 1.0 / len(rows)
        for idx in range(len(weights)):
            weights[idx] -= learning_rate * grad_w[idx] * scale
        bias -= learning_rate * grad_b * scale

    return PersonalizationModel(version="training", features=_FEATURES.copy(), weights=weights, bias=bias)


def _classification_metrics(model: PersonalizationModel, rows: list[TrainingRow]) -> dict[str, float]:
    if not rows:
        return {"accuracy": 0.0}

    correct = 0
    for row in rows:
        z = model.bias + sum(weight * value for weight, value in zip(model.weights, row.values, strict=True))
        pred = 1 if _sigmoid(z) >= 0.5 else 0
        if pred == row.label:
            correct += 1

    return {"accuracy": round(correct / len(rows), 4)}


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp_value = math.exp(-value)
        return 1.0 / (1.0 + exp_value)
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)
