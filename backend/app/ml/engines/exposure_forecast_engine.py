from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from app.ml.base import MLTaskType, PredictionResult, ProcessedDataset
from app.ml.config import get_ml_config
from app.ml.feature_engineering import FeatureEngineeringPipeline
from app.ml.inference import InferenceEngine
from app.ml.training import TrainingPipeline


class ExposureForecastEngine:
    model_name = "exposure_forecast"
    algorithm_name = "Random Forest Regressor"

    def __init__(self) -> None:
        self._ml_config = get_ml_config()
        self._feature_pipeline = FeatureEngineeringPipeline()
        self._training_pipeline = TrainingPipeline()
        self._inference_engine = InferenceEngine()

    def build_features(self, snapshot: Any) -> pd.DataFrame:
        feature_row = self._feature_pipeline.build_feature_row(snapshot)
        return pd.DataFrame([feature_row])

    def train(self, dataset: ProcessedDataset, model_version: str | None = None, metadata: dict[str, Any] | None = None) -> Any:
        estimator = RandomForestRegressor(random_state=self._ml_config.default_random_seed, n_estimators=30)
        return self._training_pipeline.train(
            model=estimator,
            dataset=dataset,
            model_name=self.model_name,
            model_version=model_version,
            task_type=MLTaskType.REGRESSION,
            metadata=metadata,
        )

    def predict(self, snapshot: Any, model_version: str | None = None) -> PredictionResult:
        features = self.build_features(snapshot)
        return self._inference_engine.predict(features, model_name=self.model_name, model_version=model_version)
