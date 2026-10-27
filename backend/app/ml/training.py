from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.ml.base import EstimatorProtocol, MLTaskType, ModelArtifact, ModelBundle, ProcessedDataset
from app.ml.config import get_ml_config
from app.ml.evaluation import (
    EvaluationReport,
    build_evaluation_report,
    evaluate_classification,
    evaluate_clustering,
    evaluate_regression,
)
from app.ml.persistence import ModelPersistenceManager
from app.ml.utils import build_version_tag


@dataclass(frozen=True)
class TrainingResult:
    bundle: ModelBundle
    evaluation_report: EvaluationReport | None
    training_rows: int
    validation_rows: int
    validation_predictions: list[Any] = field(default_factory=list)
    validation_probabilities: list[Any] = field(default_factory=list)


class TrainingPipeline:
    def __init__(self, persistence_manager: ModelPersistenceManager | None = None) -> None:
        self._ml_config = get_ml_config()
        self._persistence_manager = persistence_manager or ModelPersistenceManager()

    @property
    def persistence_manager(self) -> ModelPersistenceManager:
        return self._persistence_manager

    def train(
        self,
        model: EstimatorProtocol,
        dataset: ProcessedDataset,
        model_name: str,
        model_version: str | None = None,
        task_type: MLTaskType = MLTaskType.CLASSIFICATION,
        metadata: dict[str, Any] | None = None,
    ) -> TrainingResult:
        self._validate_model(model)
        self._validate_dataset(dataset)

        fitted_model = self._fit_model(model, dataset.train_features, dataset.train_target)
        validation_features = (
            dataset.validation_features
            if dataset.validation_features is not None and not dataset.validation_features.empty
            else dataset.test_features
            if not dataset.test_features.empty
            else dataset.train_features
        )
        validation_target = (
            dataset.validation_target
            if dataset.validation_target is not None
            and dataset.validation_features is not None
            and not dataset.validation_features.empty
            else dataset.test_target
            if dataset.test_target is not None and not dataset.test_features.empty
            else dataset.train_target
        )
        validation_predictions = self._predict(fitted_model, validation_features)
        validation_probabilities = self._predict_probabilities(fitted_model, validation_features)
        validation_report = self._evaluate(
            task_type,
            validation_target,
            validation_features,
            validation_predictions,
            validation_probabilities,
            evaluate_unsupervised=bool((metadata or {}).get("evaluate_unsupervised", False)),
        )
        final_features = dataset.test_features if not dataset.test_features.empty else validation_features
        final_target = dataset.test_target if dataset.test_target is not None and not dataset.test_features.empty else validation_target
        final_predictions = self._predict(fitted_model, final_features)
        final_probabilities = self._predict_probabilities(fitted_model, final_features)
        evaluation_report = self._evaluate(
            task_type,
            final_target,
            final_features,
            final_predictions,
            final_probabilities,
            evaluate_unsupervised=bool((metadata or {}).get("evaluate_unsupervised", False)),
        )

        artifact = ModelArtifact(
            model_name=model_name,
            model_version=model_version or build_version_tag(),
            task_type=task_type,
            pipeline_version=dataset.pipeline_version or self._ml_config.default_pipeline_version,
            feature_version=dataset.feature_version or self._ml_config.default_feature_version,
            framework_version=self._ml_config.framework_version,
            python_version=self._python_version(),
            feature_columns=dataset.feature_columns,
            target_column=dataset.target_column,
            metrics=evaluation_report.metrics if evaluation_report is not None else {},
            metadata={
                "pipeline_version": dataset.pipeline_version,
                "feature_version": dataset.feature_version,
                "random_seed": self._ml_config.default_random_seed,
                "target_summary": {
                    "train": self._target_summary(
                        dataset.train_target, task_type == MLTaskType.CLASSIFICATION
                    ),
                    "validation": self._target_summary(
                        dataset.validation_target, task_type == MLTaskType.CLASSIFICATION
                    ),
                    "test": self._target_summary(
                        dataset.test_target, task_type == MLTaskType.CLASSIFICATION
                    ),
                },
                "validation_metrics": dict(validation_report.metrics) if validation_report is not None else {},
                **(metadata or {}),
            },
        )
        bundle = ModelBundle(
            artifact=artifact,
            model=fitted_model,
            preprocessor_state=dataset.preprocessing_state,
        )
        persisted_bundle = self._persistence_manager.save(bundle)

        return TrainingResult(
            bundle=persisted_bundle,
            evaluation_report=evaluation_report,
            training_rows=len(dataset.train_features),
            validation_rows=len(validation_features),
            validation_predictions=self._normalize_predictions(validation_predictions),
            validation_probabilities=self._normalize_probabilities(validation_probabilities),
        )

    def _validate_model(self, model: EstimatorProtocol) -> None:
        if not hasattr(model, "fit") or not hasattr(model, "predict"):
            raise TypeError("Model must provide fit and predict methods.")

    def _validate_dataset(self, dataset: ProcessedDataset) -> None:
        if dataset.train_features.empty:
            raise ValueError("Training dataset cannot be empty.")
        if dataset.target_column is not None and dataset.train_target is None:
            raise ValueError("Training target is missing.")

    def _fit_model(self, model: EstimatorProtocol, features: pd.DataFrame, target: pd.Series | None) -> EstimatorProtocol:
        if target is None:
            model.fit(features)
            return model
        try:
            model.fit(features, target)
            return model
        except TypeError:
            model.fit(features)
            return model

    def _predict(self, model: EstimatorProtocol, features: pd.DataFrame) -> list[Any]:
        predictions = model.predict(features)
        return self._normalize_predictions(predictions)

    def _predict_probabilities(self, model: EstimatorProtocol, features: pd.DataFrame) -> list[Any]:
        if not hasattr(model, "predict_proba"):
            return []
        probabilities = model.predict_proba(features)
        return self._normalize_probabilities(probabilities)

    def _evaluate(
        self,
        task_type: MLTaskType,
        target: pd.Series | None,
        validation_features: pd.DataFrame,
        predictions: list[Any],
        probabilities: list[Any],
        evaluate_unsupervised: bool = False,
    ) -> EvaluationReport | None:
        if target is None and not (task_type == MLTaskType.CLUSTERING and evaluate_unsupervised):
            return None

        target_values = target.tolist() if target is not None else None
        if task_type == MLTaskType.CLASSIFICATION:
            if target_values is None:
                return None
            probability_scores = None
            if probabilities and isinstance(probabilities[0], (int, float)):
                probability_scores = [float(value) for value in probabilities]
            elif probabilities and isinstance(probabilities[0], (list, tuple)) and len(probabilities[0]) == 2:
                probability_scores = [float(pair[-1]) for pair in probabilities]

            metrics = evaluate_classification(target_values, predictions, probability_scores=probability_scores)
        elif task_type == MLTaskType.REGRESSION:
            if target_values is None:
                return None
            metrics = evaluate_regression(target_values, predictions)
        else:
            if len(validation_features) > 1000:
                sample_indices = validation_features.sample(n=1000, random_state=42).index
                sampled_features = validation_features.loc[sample_indices]
                sampled_positions = validation_features.index.get_indexer(sample_indices)
                sampled_predictions = [predictions[position] for position in sampled_positions]
                metrics = evaluate_clustering(sampled_features, sampled_predictions)
            else:
                metrics = evaluate_clustering(validation_features, predictions)

        return build_evaluation_report(task_type, metrics, sample_count=len(predictions))

    @staticmethod
    def _normalize_predictions(predictions: Any) -> list[Any]:
        if isinstance(predictions, pd.Series):
            return predictions.tolist()
        if isinstance(predictions, pd.Index):
            return predictions.tolist()
        if isinstance(predictions, (list, tuple)):
            return list(predictions)
        if hasattr(predictions, "tolist"):
            return predictions.tolist()
        return [predictions]

    @staticmethod
    def _normalize_probabilities(probabilities: Any) -> list[Any]:
        if probabilities is None:
            return []
        if isinstance(probabilities, pd.DataFrame):
            return probabilities.to_dict(orient="records")
        if isinstance(probabilities, pd.Series):
            return probabilities.tolist()
        if isinstance(probabilities, (list, tuple)):
            return [item.tolist() if hasattr(item, "tolist") else item for item in probabilities]
        if hasattr(probabilities, "tolist"):
            return probabilities.tolist()
        return [probabilities]

    @staticmethod
    def _python_version() -> str:
        import sys

        return sys.version.split()[0]

    @staticmethod
    def _target_summary(target: pd.Series | None, classification: bool) -> dict[str, Any]:
        if target is None:
            return {"available": False, "count": 0, "class_counts": {}}
        values = target.dropna().tolist()
        if not classification:
            numeric_values = [float(value) for value in values]
            return {
                "available": True,
                "count": len(numeric_values),
                "min": min(numeric_values) if numeric_values else None,
                "max": max(numeric_values) if numeric_values else None,
                "mean": sum(numeric_values) / len(numeric_values) if numeric_values else None,
            }
        counts: dict[str, int] = {}
        for value in values:
            counts[str(value)] = counts.get(str(value), 0) + 1
        return {
            "available": True,
            "count": len(values),
            "class_counts": counts,
            "positive_count": counts.get("1", 0),
            "positive_rate": round(
                sum(1 for value in values if value == 1) / len(values), 4
            ) if values else 0.0,
        }
