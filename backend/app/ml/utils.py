from __future__ import annotations

import random
import re
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any, Iterable, Sequence

import pandas as pd

from app.ml.base import FeatureFrame


def set_random_seed(seed: int) -> None:
    random.seed(seed)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def truthy(value: Any) -> bool:
    return normalize_text(value).lower() in {"1", "true", "yes", "y", "t", "on"}


def coerce_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    try:
        if isinstance(value, str):
            normalized = value.strip().replace(",", "")
            if normalized.endswith("%"):
                return float(normalized[:-1]) / 100.0
            return float(normalized)
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(min(value, maximum), minimum)


def mean_or_default(values: Sequence[float], default: float = 0.0) -> float:
    return float(mean(values)) if values else default


def median_or_default(values: Sequence[float], default: float = 0.0) -> float:
    return float(median(values)) if values else default


def pstdev_or_default(values: Sequence[float], default: float = 0.0) -> float:
    if len(values) < 2:
        return default
    return float(pstdev(values))


def coefficient_of_variation(values: Sequence[float], default: float = 0.0) -> float:
    if len(values) < 2:
        return default
    average = mean_or_default(values)
    if average == 0:
        return default
    return pstdev_or_default(values) / abs(average)


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_component_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return sanitized.strip("._") or "model"


def build_version_tag(prefix: str = "v") -> str:
    from datetime import datetime, timezone

    return f"{prefix}{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


def validate_dataframe(frame: pd.DataFrame, required_columns: Sequence[str] = ()) -> pd.DataFrame:
    if frame is None:
        raise ValueError("DataFrame is required.")
    if frame.empty:
        raise ValueError("DataFrame cannot be empty.")

    missing_columns = [column for column in required_columns if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    return frame.copy()


def validate_feature_frame(feature_frame: pd.DataFrame | FeatureFrame, required_columns: Sequence[str] = ()) -> pd.DataFrame:
    if isinstance(feature_frame, FeatureFrame):
        frame = feature_frame.data
    else:
        frame = feature_frame
    return validate_dataframe(frame, required_columns=required_columns)


def ensure_sequence(value: Iterable[Any] | Any) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, pd.Series):
        return value.tolist()
    return [value]
