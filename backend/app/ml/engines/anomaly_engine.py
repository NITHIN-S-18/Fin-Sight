from __future__ import annotations

from dataclasses import replace
from typing import Any

import pandas as pd
from sklearn.ensemble import IsolationForest

from app.ml.base import MLTaskType, PredictionItem, PredictionResult, ProcessedDataset
from app.ml.config import get_ml_config
from app.ml.feature_engineering import FeatureEngineeringPipeline
from app.ml.inference import InferenceEngine
from app.ml.persistence import ModelPersistenceManager
from app.ml.preprocessing import PreprocessingPipeline
from app.ml.utils import validate_dataframe
from app.ml.training import TrainingPipeline


class FinancialAnomalyEngine:
    model_name = "financial_anomaly"
    algorithm_name = "Isolation Forest"

    def __init__(self) -> None:
        self._ml_config = get_ml_config()
        self._feature_pipeline = FeatureEngineeringPipeline()
        self._training_pipeline = TrainingPipeline()
        self._inference_engine = InferenceEngine()

    def build_features(self, snapshot: Any) -> pd.DataFrame:
        feature_row = self._feature_pipeline.build_feature_row(snapshot)
        return pd.DataFrame([feature_row])

    def train(self, dataset: ProcessedDataset, model_version: str | None = None, metadata: dict[str, Any] | None = None) -> Any:
        estimator = IsolationForest(
            random_state=self._ml_config.default_random_seed,
            n_estimators=25,
            max_samples=10000,
            contamination="auto",
        )
        training_dataset = replace(
            dataset,
            train_features=dataset.train_features.sample(
                n=min(len(dataset.train_features), 20000),
                random_state=42,
            ),
            train_target=None,
        )
        return self._training_pipeline.train(
            model=estimator,
            dataset=training_dataset,
            model_name=self.model_name,
            model_version=model_version,
            task_type=MLTaskType.CLUSTERING,
            metadata=metadata,
        )

    def predict(self, snapshot: Any, model_version: str | None = None) -> PredictionResult:
        features = self.build_features(snapshot)
        return self._inference_engine.predict(features, model_name=self.model_name, model_version=model_version)

    def predict_with_score(self, snapshot: Any, model_version: str | None = None) -> PredictionItem:
        features = self.build_features(snapshot)
        bundle = self._inference_engine.persistence_manager.load_latest(self.model_name) if model_version is None else self._inference_engine.persistence_manager.load(self.model_name, model_version)
        prepared = self._prepare_features(features, bundle)
        model = bundle.model
        prediction_values = model.predict(prepared)
        predicted_label = prediction_values[0] if hasattr(prediction_values, "__getitem__") else prediction_values
        score = self._decision_score(model, prepared)
        confidence = self._confidence_from_score(score, predicted_label)
        return PredictionItem(
            sample_index=prepared.index[0] if not prepared.empty else 0,
            prediction=score,
            confidence=confidence,
            metadata={
                "label": predicted_label,
                "model_name": bundle.artifact.model_name,
                "model_version": bundle.artifact.model_version,
                "decision_score": score,
                "artifact_metrics": dict(bundle.artifact.metrics),
                "artifact_metadata": dict(bundle.artifact.metadata),
            },
        )

    @staticmethod
    def anomaly_flag(score: float) -> bool:
        return score < 0.0

    @staticmethod
    def _prepare_features(features: pd.DataFrame, bundle: Any) -> pd.DataFrame:
        frame = validate_dataframe(features)
        if bundle.preprocessor_state is not None:
            preprocessor = PreprocessingPipeline.from_state(bundle.preprocessor_state)
            frame = preprocessor.transform(frame)
        expected_columns = list(bundle.artifact.feature_columns)
        if expected_columns:
            missing_columns = [column for column in expected_columns if column not in frame.columns]
            if missing_columns:
                raise ValueError(f"Inference input is missing required features: {', '.join(missing_columns)}")
            frame = frame.reindex(columns=expected_columns, fill_value=0.0)
        return frame

    @staticmethod
    def _decision_score(model: Any, features: pd.DataFrame) -> float:
        if hasattr(model, "decision_function"):
            values = model.decision_function(features)
            if hasattr(values, "tolist"):
                values = values.tolist()
            if isinstance(values, (list, tuple)) and values:
                return float(values[0])
            if isinstance(values, (int, float)):
                return float(values)
        if hasattr(model, "score_samples"):
            values = model.score_samples(features)
            if hasattr(values, "tolist"):
                values = values.tolist()
            if isinstance(values, (list, tuple)) and values:
                return float(values[0])
            if isinstance(values, (int, float)):
                return float(values)
        values = model.predict(features)
        if hasattr(values, "tolist"):
            values = values.tolist()
        if isinstance(values, (list, tuple)) and values:
            return float(values[0])
        return float(values)

    @staticmethod
    def _confidence_from_score(score: float, predicted_label: Any) -> float:
        if float(predicted_label) < 0:
            return round(min(max(abs(score), 0.0), 1.0), 4)
        return round(min(max(1.0 - abs(score), 0.0), 1.0), 4)
