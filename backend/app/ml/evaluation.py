from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import sqrt
from typing import Any, Sequence

import pandas as pd
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score as sklearn_f1_score

from app.ml.base import MLTaskType
from app.ml.utils import clamp, ensure_sequence, safe_divide


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ClassificationMetrics:
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float | None = None
    balanced_accuracy: float = 0.0
    macro_f1: float = 0.0
    pr_auc: float | None = None
    brier_score: float | None = None
    average: str = "binary"
    confusion_matrix: dict[str, dict[str, int]] = field(default_factory=dict)
    class_counts: dict[str, int] = field(default_factory=dict)
    positive_rate: float = 0.0


@dataclass(frozen=True)
class RegressionMetrics:
    mae: float
    rmse: float
    r2: float
    median_absolute_error: float = 0.0
    forecast_bias: float = 0.0


@dataclass(frozen=True)
class ClusteringMetrics:
    silhouette_score: float
    cluster_count: int
    sample_count: int


@dataclass(frozen=True)
class EvaluationReport:
    task_type: MLTaskType
    metrics: dict[str, Any]
    generated_at: datetime = field(default_factory=_utc_now)
    sample_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


def evaluate_classification(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    probability_scores: Sequence[float] | None = None,
    positive_label: Any | None = None,
) -> ClassificationMetrics:
    true_values = ensure_sequence(y_true)
    predicted_values = ensure_sequence(y_pred)
    if len(true_values) != len(predicted_values):
        raise ValueError("Classification targets and predictions must have the same length.")

    labels = sorted(set(true_values) | set(predicted_values))
    average = "binary" if len(labels) <= 2 else "macro"
    positive_label = positive_label if positive_label is not None else (labels[-1] if labels else 1)

    accuracy = _accuracy_score(true_values, predicted_values)
    precision = _precision_score(true_values, predicted_values, labels, average, positive_label)
    recall = _recall_score(true_values, predicted_values, labels, average, positive_label)
    f1_score = _f1_from_precision_recall(precision, recall)
    roc_auc = _roc_auc_score(true_values, probability_scores, positive_label) if probability_scores is not None else None
    balanced_accuracy = balanced_accuracy_score(true_values, predicted_values) if labels else 0.0
    macro_f1 = sklearn_f1_score(true_values, predicted_values, average="macro", zero_division=0) if labels else 0.0
    pr_auc = None
    brier_score = None
    if probability_scores is not None and len(set(true_values)) == 2:
        binary_true = [1 if value == positive_label else 0 for value in true_values]
        pr_auc = float(average_precision_score(binary_true, probability_scores))
        brier_score = sum((truth - score) ** 2 for truth, score in zip(binary_true, probability_scores)) / len(binary_true)

    return ClassificationMetrics(
        accuracy=round(accuracy, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1_score, 4),
        roc_auc=round(roc_auc, 4) if roc_auc is not None else None,
        balanced_accuracy=round(float(balanced_accuracy), 4),
        macro_f1=round(float(macro_f1), 4),
        pr_auc=round(pr_auc, 4) if pr_auc is not None else None,
        brier_score=round(brier_score, 4) if brier_score is not None else None,
        average=average,
        confusion_matrix=_confusion_matrix(true_values, predicted_values, labels),
        class_counts={str(label): int(true_values.count(label)) for label in labels},
        positive_rate=round(
            safe_divide(sum(1 for value in true_values if value == positive_label), len(true_values), 0.0),
            4,
        ),
    )


def evaluate_regression(y_true: Sequence[float], y_pred: Sequence[float]) -> RegressionMetrics:
    true_values = [float(value) for value in ensure_sequence(y_true)]
    predicted_values = [float(value) for value in ensure_sequence(y_pred)]
    if len(true_values) != len(predicted_values):
        raise ValueError("Regression targets and predictions must have the same length.")

    absolute_errors = [abs(true - predicted) for true, predicted in zip(true_values, predicted_values)]
    squared_errors = [(true - predicted) ** 2 for true, predicted in zip(true_values, predicted_values)]
    mae = sum(absolute_errors) / len(absolute_errors) if absolute_errors else 0.0
    rmse = sqrt(sum(squared_errors) / len(squared_errors)) if squared_errors else 0.0
    mean_true = sum(true_values) / len(true_values) if true_values else 0.0
    total_sum_squares = sum((value - mean_true) ** 2 for value in true_values)
    residual_sum_squares = sum(squared_errors)
    r2 = 1.0 - safe_divide(residual_sum_squares, total_sum_squares, 0.0) if total_sum_squares else 0.0
    median_absolute_error = float(pd.Series(absolute_errors).median()) if absolute_errors else 0.0
    forecast_bias = (sum(predicted_values) - sum(true_values)) / len(true_values) if true_values else 0.0

    return RegressionMetrics(
        mae=round(mae, 4),
        rmse=round(rmse, 4),
        r2=round(r2, 4),
        median_absolute_error=round(median_absolute_error, 4),
        forecast_bias=round(forecast_bias, 4),
    )


def evaluate_clustering(features: pd.DataFrame, labels: Sequence[Any]) -> ClusteringMetrics:
    label_values = list(labels)
    if len(features) != len(label_values):
        raise ValueError("Clustering features and labels must have the same length.")

    cluster_labels = sorted(set(label_values))
    silhouette = _silhouette_score(features, label_values)
    return ClusteringMetrics(
        silhouette_score=round(silhouette, 4),
        cluster_count=len(cluster_labels),
        sample_count=len(label_values),
    )


def build_evaluation_report(task_type: MLTaskType, metrics: ClassificationMetrics | RegressionMetrics | ClusteringMetrics, sample_count: int = 0, metadata: dict[str, Any] | None = None) -> EvaluationReport:
    if isinstance(metrics, ClassificationMetrics):
        payload = {
            "accuracy": metrics.accuracy,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "roc_auc": metrics.roc_auc,
            "balanced_accuracy": metrics.balanced_accuracy,
            "macro_f1": metrics.macro_f1,
            "pr_auc": metrics.pr_auc,
            "brier_score": metrics.brier_score,
            "confusion_matrix": metrics.confusion_matrix,
            "class_counts": metrics.class_counts,
            "positive_rate": metrics.positive_rate,
        }
    elif isinstance(metrics, RegressionMetrics):
        payload = {
            "mae": metrics.mae,
            "rmse": metrics.rmse,
            "r2": metrics.r2,
            "median_absolute_error": metrics.median_absolute_error,
            "forecast_bias": metrics.forecast_bias,
        }
    else:
        payload = {
            "silhouette_score": metrics.silhouette_score,
            "cluster_count": float(metrics.cluster_count),
            "sample_count": float(metrics.sample_count),
        }
    return EvaluationReport(task_type=task_type, metrics=payload, sample_count=sample_count, metadata=metadata or {})


def _accuracy_score(y_true: Sequence[Any], y_pred: Sequence[Any]) -> float:
    matches = sum(1 for true_value, predicted_value in zip(y_true, y_pred) if true_value == predicted_value)
    return safe_divide(matches, len(y_true), 0.0)


def _confusion_matrix(
    y_true: Sequence[Any], y_pred: Sequence[Any], labels: Sequence[Any]
) -> dict[str, dict[str, int]]:
    return {
        str(actual): {
            str(predicted): int(
                sum(
                    1
                    for true_value, predicted_value in zip(y_true, y_pred)
                    if true_value == actual and predicted_value == predicted
                )
            )
            for predicted in labels
        }
        for actual in labels
    }


def _precision_score(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    labels: Sequence[Any],
    average: str,
    positive_label: Any,
) -> float:
    if average == "binary":
        return _binary_precision(y_true, y_pred, positive_label)
    return sum(_binary_precision(y_true, y_pred, label) for label in labels) / len(labels) if labels else 0.0


def _recall_score(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    labels: Sequence[Any],
    average: str,
    positive_label: Any,
) -> float:
    if average == "binary":
        return _binary_recall(y_true, y_pred, positive_label)
    return sum(_binary_recall(y_true, y_pred, label) for label in labels) / len(labels) if labels else 0.0


def _binary_precision(y_true: Sequence[Any], y_pred: Sequence[Any], positive_label: Any) -> float:
    true_positive = sum(1 for true_value, predicted_value in zip(y_true, y_pred) if true_value == positive_label and predicted_value == positive_label)
    predicted_positive = sum(1 for predicted_value in y_pred if predicted_value == positive_label)
    return safe_divide(true_positive, predicted_positive, 0.0)


def _binary_recall(y_true: Sequence[Any], y_pred: Sequence[Any], positive_label: Any) -> float:
    true_positive = sum(1 for true_value, predicted_value in zip(y_true, y_pred) if true_value == positive_label and predicted_value == positive_label)
    actual_positive = sum(1 for true_value in y_true if true_value == positive_label)
    return safe_divide(true_positive, actual_positive, 0.0)


def _f1_from_precision_recall(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _roc_auc_score(y_true: Sequence[Any], scores: Sequence[float] | None, positive_label: Any) -> float | None:
    if scores is None:
        return None
    if len(y_true) != len(scores):
        raise ValueError("Classification targets and probability scores must have the same length.")

    positives = [1 if value == positive_label else 0 for value in y_true]
    positive_count = sum(positives)
    negative_count = len(positives) - positive_count
    if positive_count == 0 or negative_count == 0:
        return None

    ranked_scores = sorted(enumerate(scores), key=lambda item: item[1])
    ranks = [0.0] * len(scores)
    index = 0
    while index < len(ranked_scores):
        start = index
        tied_score = ranked_scores[index][1]
        while index < len(ranked_scores) and ranked_scores[index][1] == tied_score:
            index += 1
        average_rank = (start + index + 1) / 2.0
        for ranked_index in range(start, index):
            original_index = ranked_scores[ranked_index][0]
            ranks[original_index] = average_rank

    sum_positive_ranks = sum(rank for rank, positive in zip(ranks, positives) if positive)
    auc = (sum_positive_ranks - positive_count * (positive_count + 1) / 2.0) / (positive_count * negative_count)
    return clamp(auc, 0.0, 1.0)


def _silhouette_score(features: pd.DataFrame, labels: Sequence[Any]) -> float:
    if len(features) < 2:
        return 0.0

    label_to_indices: dict[Any, list[int]] = {}
    for index, label in enumerate(labels):
        label_to_indices.setdefault(label, []).append(index)
    if len(label_to_indices) < 2:
        return 0.0

    numeric_frame = features.select_dtypes(include=["number", "bool"]).copy()
    if numeric_frame.empty:
        return 0.0

    rows = [tuple(float(value) for value in row) for row in numeric_frame.itertuples(index=False, name=None)]

    def distance(left_index: int, right_index: int) -> float:
        left_row = rows[left_index]
        right_row = rows[right_index]
        return sqrt(sum((left_value - right_value) ** 2 for left_value, right_value in zip(left_row, right_row)))

    silhouettes: list[float] = []
    for current_index, current_label in enumerate(labels):
        own_cluster = label_to_indices[current_label]
        if len(own_cluster) <= 1:
            silhouettes.append(0.0)
            continue

        a_distances = [distance(current_index, cluster_index) for cluster_index in own_cluster if cluster_index != current_index]
        a_value = sum(a_distances) / len(a_distances) if a_distances else 0.0

        b_value = float("inf")
        for label, cluster_indices in label_to_indices.items():
            if label == current_label:
                continue
            cluster_distances = [distance(current_index, cluster_index) for cluster_index in cluster_indices]
            if not cluster_distances:
                continue
            cluster_average = sum(cluster_distances) / len(cluster_distances)
            b_value = min(b_value, cluster_average)

        if b_value == float("inf"):
            silhouettes.append(0.0)
            continue

        denominator = max(a_value, b_value)
        silhouettes.append((b_value - a_value) / denominator if denominator else 0.0)

    return sum(silhouettes) / len(silhouettes) if silhouettes else 0.0
