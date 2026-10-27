from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.ml.base import EstimatorProtocol, ModelBundle, PredictionItem, PredictionResult
from app.ml.config import get_ml_config
from app.ml.persistence import ModelPersistenceManager
from app.ml.preprocessing import PreprocessingPipeline
from app.ml.utils import validate_dataframe


@dataclass(frozen=True)
class InferenceRequest:
    features: pd.DataFrame
    model_name: str
    model_version: str | None = None
    apply_preprocessing: bool = True


class InferenceEngine:
    def __init__(self, persistence_manager: ModelPersistenceManager | None = None) -> None:
        self._ml_config = get_ml_config()
        self._persistence_manager = persistence_manager or ModelPersistenceManager()
        self._bundle_cache: dict[tuple[str, str | None], ModelBundle] = {}

    @property
    def persistence_manager(self) -> ModelPersistenceManager:
        return self._persistence_manager

    def predict(
        self,
        features: pd.DataFrame,
        model_name: str,
        model_version: str | None = None,
        apply_preprocessing: bool = True,
    ) -> PredictionResult:
        bundle = self._load_bundle(model_name, model_version)
        prepared_features = self._prepare_features(features, bundle, apply_preprocessing)
        predictions = self._predict(bundle.model, prepared_features)
        probabilities = self._predict_probabilities(bundle.model, prepared_features)
        items = self._build_prediction_items(prepared_features, predictions, probabilities, bundle)
        return PredictionResult(
            items=items,
            model_name=bundle.artifact.model_name,
            model_version=bundle.artifact.model_version,
            pipeline_version=bundle.artifact.pipeline_version,
            feature_version=bundle.artifact.feature_version,
            task_type=bundle.artifact.task_type,
            metadata={
                "feature_columns": list(prepared_features.columns),
                "row_count": len(prepared_features),
                "framework_version": self._ml_config.framework_version,
                "artifact_metadata": dict(bundle.artifact.metadata),
                "artifact_metrics": dict(bundle.artifact.metrics),
                "training_timestamp": bundle.trained_at.isoformat(),
                "model_name": bundle.artifact.model_name,
                "model_version": bundle.artifact.model_version,
                "task_type": bundle.artifact.task_type.value,
            },
        )

    def _load_bundle(self, model_name: str, model_version: str | None) -> ModelBundle:
        cache_key = (model_name, model_version)
        cached_bundle = self._bundle_cache.get(cache_key)
        if cached_bundle is not None:
            return cached_bundle

        if model_version is None:
            bundle = self._persistence_manager.load_latest(model_name)
        else:
            bundle = self._persistence_manager.load(model_name, model_version)
        self._bundle_cache[cache_key] = bundle
        return bundle

    def _prepare_features(self, features: pd.DataFrame, bundle: ModelBundle, apply_preprocessing: bool) -> pd.DataFrame:
        frame = validate_dataframe(features)
        if apply_preprocessing and bundle.preprocessor_state is not None:
            preprocessor = PreprocessingPipeline.from_state(bundle.preprocessor_state)
            frame = preprocessor.transform(frame)

        expected_columns = list(bundle.artifact.feature_columns)
        if expected_columns:
            missing_columns = [column for column in expected_columns if column not in frame.columns]
            if missing_columns:
                raise ValueError(f"Inference input is missing required features: {', '.join(missing_columns)}")
            frame = frame.reindex(columns=expected_columns, fill_value=0.0)
        return frame

    def _predict(self, model: EstimatorProtocol, features: pd.DataFrame) -> list[Any]:
        values = model.predict(features)
        if isinstance(values, pd.Series):
            return values.tolist()
        if isinstance(values, (list, tuple)):
            return list(values)
        if hasattr(values, "tolist"):
            return values.tolist()
        return [values]

    def _predict_probabilities(self, model: EstimatorProtocol, features: pd.DataFrame) -> list[Any]:
        if not hasattr(model, "predict_proba"):
            return []
        values = model.predict_proba(features)
        if isinstance(values, pd.DataFrame):
            return values.to_dict(orient="records")
        if isinstance(values, pd.Series):
            return values.tolist()
        if isinstance(values, (list, tuple)):
            return [item.tolist() if hasattr(item, "tolist") else item for item in values]
        if hasattr(values, "tolist"):
            return values.tolist()
        return [values]

    def _build_prediction_items(
        self,
        features: pd.DataFrame,
        predictions: list[Any],
        probabilities: list[Any],
        bundle: ModelBundle,
    ) -> list[PredictionItem]:
        items: list[PredictionItem] = []
        class_labels = list(getattr(bundle.model, "classes_", []))

        for position, (sample_index, prediction) in enumerate(zip(features.index.tolist(), predictions)):
            probability_payload = probabilities[position] if position < len(probabilities) else None
            confidence = self._extract_confidence(probability_payload)
            structured_probabilities = self._structure_probabilities(probability_payload, class_labels)
            items.append(
                PredictionItem(
                    sample_index=sample_index,
                    prediction=prediction,
                    confidence=confidence,
                    probabilities=structured_probabilities,
                    metadata={
                        "position": position,
                        "task_type": bundle.artifact.task_type.value,
                        "pipeline_version": bundle.artifact.pipeline_version,
                        "feature_version": bundle.artifact.feature_version,
                    },
                )
            )
        return items

    @staticmethod
    def _extract_confidence(probability_payload: Any) -> float | None:
        if probability_payload is None:
            return None
        if isinstance(probability_payload, dict):
            values = [float(value) for value in probability_payload.values() if isinstance(value, (int, float))]
            return max(values) if values else None
        if isinstance(probability_payload, (list, tuple)):
            numeric_values = [float(value) for value in probability_payload if isinstance(value, (int, float))]
            return max(numeric_values) if numeric_values else None
        if isinstance(probability_payload, (int, float)):
            return float(probability_payload)
        return None

    @staticmethod
    def _structure_probabilities(probability_payload: Any, class_labels: list[Any]) -> dict[str, float] | list[float] | None:
        if probability_payload is None:
            return None
        if isinstance(probability_payload, dict):
            return {str(key): float(value) for key, value in probability_payload.items() if isinstance(value, (int, float))}
        if isinstance(probability_payload, (list, tuple)):
            numeric_values = [float(value) for value in probability_payload if isinstance(value, (int, float))]
            if class_labels and len(class_labels) == len(numeric_values):
                return {str(label): float(value) for label, value in zip(class_labels, numeric_values)}
            return numeric_values
        if isinstance(probability_payload, (int, float)):
            return [float(probability_payload)]
        return None
