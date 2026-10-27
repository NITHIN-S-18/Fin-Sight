from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

import pandas as pd


def _utc_now() -> datetime:
	return datetime.now(timezone.utc)


class MLTaskType(str, Enum):
	CLASSIFICATION = "classification"
	REGRESSION = "regression"
	CLUSTERING = "clustering"


class ScalingStrategy(str, Enum):
	NONE = "none"
	STANDARD = "standard"
	MINMAX = "minmax"


class MissingValueStrategy(str, Enum):
	CONSTANT = "constant"
	MODE = "mode"
	MEDIAN = "median"
	MEAN = "mean"
	FORWARD_FILL = "forward_fill"


@dataclass(frozen=True)
class FeatureDefinition:
	name: str
	description: str
	source_fields: tuple[str, ...] = ()
	category: str | None = None
	required: bool = True


@dataclass(frozen=True)
class FinancialIntelligenceSnapshot:
	user_id: str | None
	user_record: dict[str, Any]
	financial_profile: dict[str, Any]
	transactions: pd.DataFrame
	metadata: dict[str, Any] = field(default_factory=dict)
	captured_at: datetime = field(default_factory=_utc_now)


@dataclass
class FeatureFrame:
	data: pd.DataFrame
	feature_names: tuple[str, ...]
	feature_version: str
	source_count: int
	generated_at: datetime = field(default_factory=_utc_now)
	metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreprocessingState:
	input_columns: tuple[str, ...]
	transformed_columns: tuple[str, ...]
	numeric_columns: tuple[str, ...]
	categorical_columns: tuple[str, ...]
	categorical_levels: dict[str, tuple[str, ...]]
	categorical_fill_values: dict[str, Any]
	numeric_statistics: dict[str, dict[str, float]]
	missing_value_strategy: str
	scaling_strategy: str
	feature_selection: tuple[str, ...] = ()


@dataclass
class ProcessedDataset:
	train_features: pd.DataFrame
	test_features: pd.DataFrame
	train_target: pd.Series | None
	test_target: pd.Series | None
	feature_columns: tuple[str, ...]
	target_column: str | None
	pipeline_version: str = "1.0"
	feature_version: str = "1.0"
	preprocessing_state: PreprocessingState | None = None
	metadata: dict[str, Any] = field(default_factory=dict)
	validation_features: pd.DataFrame | None = None
	validation_target: pd.Series | None = None


@dataclass(frozen=True)
class ModelArtifact:
	model_name: str
	model_version: str
	task_type: MLTaskType
	pipeline_version: str = "1.0"
	feature_version: str = "1.0"
	framework_version: str = "1.0"
	python_version: str = ""
	created_at: datetime = field(default_factory=_utc_now)
	feature_columns: tuple[str, ...] = ()
	target_column: str | None = None
	metrics: dict[str, Any] = field(default_factory=dict)
	metadata: dict[str, Any] = field(default_factory=dict)
	model_path: str | None = None
	metadata_path: str | None = None


@dataclass
class ModelBundle:
	artifact: ModelArtifact
	model: EstimatorProtocol
	preprocessor_state: PreprocessingState | None = None
	trained_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class PredictionItem:
	sample_index: Any
	prediction: Any
	confidence: float | None = None
	probabilities: dict[str, float] | list[float] | None = None
	metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PredictionResult:
	items: list[PredictionItem]
	model_name: str
	model_version: str
	task_type: MLTaskType
	pipeline_version: str = "1.0"
	feature_version: str = "1.0"
	generated_at: datetime = field(default_factory=_utc_now)
	metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class EstimatorProtocol(Protocol):
	def fit(self, features: pd.DataFrame, target: Any | None = None) -> Any:
		...

	def predict(self, features: pd.DataFrame) -> Any:
		...


@runtime_checkable
class ProbabilityEstimatorProtocol(EstimatorProtocol, Protocol):
	def predict_proba(self, features: pd.DataFrame) -> Any:
		...


@runtime_checkable
class TransformerProtocol(Protocol):
	def fit(self, features: pd.DataFrame, target: Any | None = None) -> Any:
		...

	def transform(self, features: pd.DataFrame) -> pd.DataFrame:
		...
