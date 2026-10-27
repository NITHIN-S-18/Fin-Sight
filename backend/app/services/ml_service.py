from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd
from fastapi import Depends

from app.core.config import get_settings
from app.core.exceptions import ExposureDataUnavailableError, UserNotFoundError
from app.ml.engines.anomaly_engine import FinancialAnomalyEngine
from app.ml.engines.behaviour_engine import BehaviourIntelligenceEngine
from app.ml.engines.distress_engine import FinancialDistressEngine
from app.ml.engines.exposure_forecast_engine import ExposureForecastEngine
from app.ml.base import ProcessedDataset
from app.ml.config import get_ml_config
from app.ml.feature_engineering import FeatureEngineeringPipeline
from app.ml.preprocessing import PreprocessingConfig, PreprocessingPipeline
from app.ml.base import ScalingStrategy
from app.ml.temporal_dataset import TemporalDatasetBuilder
from app.ml.evaluation import evaluate_regression
from app.ml.fusion.intelligence_fusion import EnginePredictionEnvelope, FinancialIntelligenceFusionLayer
from app.ml.insights.insights_generator import AIInsightsLayer
from app.ml.persistence import ModelPersistenceManager
from app.schemas.ml import (
    AnomalyResponse,
    CurrentFinancialState,
    ExposureForecastResponse,
    FinancialDistressResponse,
    FinancialIntelligenceResponseSchema,
    PersonaResponse,
)
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.exposure_service import ExposureService, get_exposure_service
from app.services.financial_rules import TransactionStatus, classify_transaction_status

_BOOTSTRAP_LOCK = Lock()
_QUALITY_METADATA_VERSION = "4.1"


@dataclass(frozen=True)
class MLResultBundle:
    distress: FinancialDistressResponse
    exposure_forecast: ExposureForecastResponse
    persona: PersonaResponse
    anomaly: AnomalyResponse
    fused: FinancialIntelligenceResponseSchema


class MLService:
    def __init__(self, dataset_service: DatasetService, exposure_service: ExposureService | None = None) -> None:
        if not isinstance(dataset_service, DatasetService):
            dataset_service = get_dataset_service()
        self._dataset_service = dataset_service
        if not isinstance(exposure_service, ExposureService):
            exposure_service = get_exposure_service(dataset_service)
        self._exposure_service = exposure_service
        self._ml_config = get_ml_config()
        self._reference_data_dir = self._configured_reference_data_dir()
        self._supervised_model_version = "v3.0" if self._reference_data_dir else "v2.0"
        self._unsupervised_model_version = "v2.0" if self._reference_data_dir else "v1.0"
        self._feature_pipeline = FeatureEngineeringPipeline()
        self._temporal_builder = TemporalDatasetBuilder(self._feature_pipeline)
        self._persistence_manager = ModelPersistenceManager()
        self._distress_engine = FinancialDistressEngine()
        self._exposure_engine = ExposureForecastEngine()
        self._behaviour_engine = BehaviourIntelligenceEngine()
        self._anomaly_engine = FinancialAnomalyEngine()
        self._fusion_layer = FinancialIntelligenceFusionLayer()
        self._insights_layer = AIInsightsLayer()
        self._model_metadata_cache: dict[str, dict[str, Any]] = {}
        self._ensure_bootstrap_models()

    @staticmethod
    def _configured_reference_data_dir() -> Path | None:
        configured = get_settings().ml_reference_data_dir.strip()
        if not configured:
            return None
        directory = Path(configured).expanduser()
        required = (directory / "users.csv", directory / "finsight_ml_dataset_v3.csv")
        if not directory.is_dir() or not all(path.is_file() for path in required):
            raise ValueError(
                "ML_REFERENCE_DATA_DIR must contain users.csv and finsight_ml_dataset_v3.csv"
            )
        return directory

    def _training_data(self) -> tuple[list[dict[str, Any]], pd.DataFrame]:
        if self._reference_data_dir is None:
            return self._dataset_service.get_all_users(), pd.DataFrame(self._dataset_service.get_all_transactions())
        users = pd.read_csv(self._reference_data_dir / "users.csv").to_dict(orient="records")
        transactions = pd.read_csv(self._reference_data_dir / "finsight_ml_dataset_v3.csv")
        transactions["transaction_date"] = pd.to_datetime(transactions["transaction_date"], errors="coerce")
        if transactions["transaction_date"].isna().any():
            raise ValueError("Configured ML reference dataset contains invalid transaction_date values")
        return users, transactions

    def _build_snapshot(self, user_id: str):
        return self._feature_pipeline.build_snapshot(self._dataset_service, user_id, metadata={"phase": 9})

    def _ensure_bootstrap_models(self) -> None:
        with _BOOTSTRAP_LOCK:
            inventory = self._persistence_manager.list_models()
            if not inventory:
                self._bootstrap_and_persist_models()
                return

            self._model_metadata_cache = self._load_all_model_metadata()
            if self._models_need_quality_retraining():
                self._bootstrap_and_persist_models()
            elif not self._metadata_is_complete():
                self._refresh_existing_models()

    def _bootstrap_and_persist_models(self) -> None:
        user_records, transactions = self._training_data()
        temporal = self._temporal_builder.build(user_records, transactions)
        feature_frame = temporal.features
        distress_target = temporal.distress_target
        exposure_target = temporal.exposure_target
        tree_preprocessing = PreprocessingConfig(
            scaling_strategy=ScalingStrategy.NONE,
            test_size=0.2,
            random_state=self._ml_config.default_random_seed,
        )
        distress_dataset = PreprocessingPipeline(tree_preprocessing).split_temporal_dataset(feature_frame, distress_target)
        exposure_mask = exposure_target.notna()
        exposure_dataset = PreprocessingPipeline(tree_preprocessing).split_temporal_dataset(
            feature_frame.loc[exposure_mask],
            exposure_target.loc[exposure_mask],
        )
        dataset_metadata = {
            "bootstrap": True,
            "supervision": "observed_temporal_outcome",
            "reference_dataset": "finsight_ml_dataset_v3" if self._reference_data_dir else "finsight_dataset_v2",
            **temporal.metadata,
            "training_user_count": distress_dataset.metadata["training_user_count"],
            "validation_user_count": distress_dataset.metadata["validation_user_count"],
            "test_user_count": distress_dataset.metadata["test_user_count"],
            "training_period": distress_dataset.metadata["training_period"],
            "validation_period": distress_dataset.metadata["validation_period"],
            "test_period": distress_dataset.metadata["test_period"],
        }
        exposure_metadata = {
            **dataset_metadata,
            "training_period": exposure_dataset.metadata["training_period"],
            "validation_period": exposure_dataset.metadata["validation_period"],
            "test_period": exposure_dataset.metadata["test_period"],
            "training_rows": exposure_dataset.metadata["training_rows"],
            "validation_rows": exposure_dataset.metadata["validation_rows"],
            "test_rows": exposure_dataset.metadata["test_rows"],
        }
        existing_metadata = self._load_all_model_metadata()
        distress_ready = self._artifact_is_current(existing_metadata, self._distress_engine.model_name)
        exposure_ready = self._artifact_is_current(existing_metadata, self._exposure_engine.model_name)
        distress_result = None if distress_ready else self._distress_engine.train(
            distress_dataset,
            model_version=self._supervised_model_version,
            metadata=dataset_metadata,
        )
        exposure_result = None if exposure_ready else self._exposure_engine.train(
            exposure_dataset,
            model_version=self._supervised_model_version,
            metadata=exposure_metadata,
        )
        test_index = exposure_dataset.test_features.index
        naive_target = feature_frame.loc[test_index, "exposure_utilization"].astype(float) * 100.0
        naive_metrics = evaluate_regression(
            exposure_target.loc[test_index].tolist(),
            naive_target.tolist(),
        )
        clustering_dataset = PreprocessingPipeline(tree_preprocessing).split_temporal_dataset(feature_frame)
        unsupervised_metadata = {
            "bootstrap": True,
            "supervision": "unsupervised_temporal_reference_profiles",
            **temporal.metadata,
            "training_user_count": clustering_dataset.metadata["training_user_count"],
            "validation_user_count": clustering_dataset.metadata["validation_user_count"],
            "test_user_count": clustering_dataset.metadata["test_user_count"],
            "training_period": clustering_dataset.metadata["training_period"],
            "validation_period": clustering_dataset.metadata["validation_period"],
            "test_period": clustering_dataset.metadata["test_period"],
        }
        behaviour_result = self._behaviour_engine.train(
            clustering_dataset,
            model_version=self._unsupervised_model_version,
            metadata=unsupervised_metadata,
        )
        anomaly_result = self._anomaly_engine.train(
            clustering_dataset,
            model_version=self._unsupervised_model_version,
            metadata=unsupervised_metadata,
        )

        transformed_features = clustering_dataset.train_features
        cluster_predictions = behaviour_result.bundle.model.predict(transformed_features)
        cluster_profiles = self._behaviour_engine.build_cluster_profiles(feature_frame.loc[transformed_features.index], list(cluster_predictions))

        if distress_result is not None:
            self._persist_training_result(distress_result, self._distress_engine.algorithm_name, feature_frame.shape[1], extra_metadata={"label_strategy": "observed_next_month_distress_event"})
        if exposure_result is not None:
            self._persist_training_result(
                exposure_result,
                self._exposure_engine.algorithm_name,
                feature_frame.shape[1],
                extra_metadata={
                "label_strategy": "observed_next_month_exposure",
                "forecast_horizon_months": 1,
                "baseline": {
                    "name": "current_month_exposure",
                    "metrics": {
                        "mae": naive_metrics.mae,
                        "rmse": naive_metrics.rmse,
                        "r2": naive_metrics.r2,
                        "median_absolute_error": naive_metrics.median_absolute_error,
                        "forecast_bias": naive_metrics.forecast_bias,
                    },
                    "model_beats_baseline": float(
                        (exposure_result.bundle.artifact.metrics if exposure_result else existing_metadata[self._exposure_engine.model_name]).get("mae", float("inf"))
                    ) < naive_metrics.mae,
                },
                },
            )
        cluster_candidates = self._behaviour_engine.evaluate_cluster_candidates(clustering_dataset.train_features)
        anomaly_model = anomaly_result.bundle.model
        anomaly_labels = anomaly_model.predict(clustering_dataset.test_features)
        anomaly_scores = anomaly_model.decision_function(clustering_dataset.test_features)
        anomaly_rate = float(sum(1 for label in anomaly_labels if int(label) < 0) / len(anomaly_labels)) if len(anomaly_labels) else 0.0
        self._persist_training_result(
            behaviour_result,
            self._behaviour_engine.algorithm_name,
            feature_frame.shape[1],
            extra_metadata={"cluster_profiles": cluster_profiles, "cluster_selection": cluster_candidates},
        )
        self._persist_training_result(
            anomaly_result,
            self._anomaly_engine.algorithm_name,
            feature_frame.shape[1],
            extra_metadata={
                "label_strategy": "isolation_based_outlier_detection",
                "contamination": "auto",
                "decision_threshold": 0.0,
                "score_semantics": "IsolationForest decision_function; lower scores are more anomalous; not a probability.",
                "validation_anomaly_rate": round(anomaly_rate, 4),
                "validation_score_range": [round(float(min(anomaly_scores)), 6), round(float(max(anomaly_scores)), 6)] if len(anomaly_scores) else [],
            },
        )
        self._model_metadata_cache = self._load_all_model_metadata()

    def _refresh_existing_models(self) -> None:
        for model_name, algorithm in (
            (self._distress_engine.model_name, self._distress_engine.algorithm_name),
            (self._exposure_engine.model_name, self._exposure_engine.algorithm_name),
            (self._behaviour_engine.model_name, self._behaviour_engine.algorithm_name),
            (self._anomaly_engine.model_name, self._anomaly_engine.algorithm_name),
        ):
            bundle = self._persistence_manager.load_latest(model_name)
            metadata = dict(bundle.artifact.metadata)
            needs_update = self._metadata_needs_update(model_name, metadata)
            if not needs_update:
                continue
            extra_metadata: dict[str, Any] | None = None
            if model_name == self._behaviour_engine.model_name:
                snapshots = [self._feature_pipeline.build_snapshot(self._dataset_service, user["user_id"], metadata={"phase": 9, "metadata_refresh": True}) for user in self._dataset_service.get_all_users()]
                feature_frame = self._feature_pipeline.build_feature_frame(snapshots).data
                transformed_features = PreprocessingPipeline.from_state(bundle.preprocessor_state).transform(feature_frame) if bundle.preprocessor_state is not None else feature_frame
                cluster_predictions = bundle.model.predict(transformed_features)
                extra_metadata = {
                    "cluster_profiles": self._behaviour_engine.build_cluster_profiles(feature_frame.loc[transformed_features.index], list(cluster_predictions)),
                }
            enriched_bundle = replace(
                bundle,
                artifact=replace(
                    bundle.artifact,
                    metadata=self._build_enriched_metadata(bundle, model_name=model_name, algorithm=algorithm, feature_count=len(bundle.artifact.feature_columns), extra_metadata=extra_metadata),
                ),
            )
            self._persistence_manager.save(enriched_bundle)
        self._model_metadata_cache = self._load_all_model_metadata()

    def _persist_training_result(self, training_result: Any, algorithm: str, feature_count: int, extra_metadata: dict[str, Any] | None = None) -> None:
        bundle = training_result.bundle
        enriched_bundle = replace(
            bundle,
            artifact=replace(
                bundle.artifact,
                metadata=self._build_enriched_metadata(bundle, model_name=bundle.artifact.model_name, algorithm=algorithm, feature_count=feature_count, extra_metadata=extra_metadata),
            ),
        )
        self._persistence_manager.save(enriched_bundle)

    def _build_enriched_metadata(self, bundle: Any, *, model_name: str, algorithm: str, feature_count: int, extra_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = dict(bundle.artifact.metadata)
        metadata.update(
            {
                "model_name": model_name,
                "model_version": bundle.artifact.model_version,
                "pipeline_version": bundle.artifact.pipeline_version,
                "feature_version": bundle.artifact.feature_version,
                "training_timestamp": bundle.trained_at.isoformat(),
                "algorithm": algorithm,
                "evaluation_metrics": dict(bundle.artifact.metrics),
                "feature_count": feature_count,
                "target_column": bundle.artifact.target_column,
                "quality_metadata_version": _QUALITY_METADATA_VERSION,
            }
        )
        if extra_metadata:
            metadata.update(extra_metadata)
        return metadata

    def _load_all_model_metadata(self) -> dict[str, dict[str, Any]]:
        expected_versions = {
            self._distress_engine.model_name: self._supervised_model_version,
            self._exposure_engine.model_name: self._supervised_model_version,
            self._behaviour_engine.model_name: self._unsupervised_model_version,
            self._anomaly_engine.model_name: self._unsupervised_model_version,
        }
        metadata_cache: dict[str, dict[str, Any]] = {}
        for model_name, expected_version in expected_versions.items():
            try:
                bundle = self._persistence_manager.load(model_name, expected_version)
            except FileNotFoundError:
                try:
                    bundle = self._persistence_manager.load_latest(model_name)
                except FileNotFoundError:
                    continue
            metadata_cache[model_name] = dict(bundle.artifact.metadata)
        return metadata_cache

    def _metadata_is_complete(self) -> bool:
        required_keys = {
            "algorithm",
            "feature_count",
            "training_timestamp",
            "pipeline_version",
            "feature_version",
            "quality_metadata_version",
        }
        for model_name in (
            self._distress_engine.model_name,
            self._exposure_engine.model_name,
            self._behaviour_engine.model_name,
            self._anomaly_engine.model_name,
        ):
            metadata = self._model_metadata_cache.get(model_name, {})
            if not required_keys.issubset(metadata.keys()):
                return False
        behaviour_metadata = self._model_metadata_cache.get(self._behaviour_engine.model_name, {})
        return bool(behaviour_metadata.get("cluster_profiles"))

    def _models_need_quality_retraining(self) -> bool:
        expected_reference = "finsight_ml_dataset_v3" if self._reference_data_dir else "finsight_dataset_v2"
        expected_versions = {
            self._distress_engine.model_name: self._supervised_model_version,
            self._exposure_engine.model_name: self._supervised_model_version,
            self._behaviour_engine.model_name: self._unsupervised_model_version,
            self._anomaly_engine.model_name: self._unsupervised_model_version,
        }
        for model_name, expected_version in expected_versions.items():
            metadata = self._model_metadata_cache.get(model_name)
            if not metadata:
                return True
            if metadata.get("quality_metadata_version") != _QUALITY_METADATA_VERSION:
                return True
            if metadata.get("model_version") != expected_version:
                return True
            if model_name in (self._distress_engine.model_name, self._exposure_engine.model_name):
                if metadata.get("reference_dataset") != expected_reference:
                    return True
        return False

    def _artifact_is_current(
        self,
        metadata_cache: dict[str, dict[str, Any]],
        model_name: str,
    ) -> bool:
        metadata = metadata_cache.get(model_name, {})
        nested_metadata = metadata.get("metadata", {}) if isinstance(metadata.get("metadata"), dict) else {}
        effective_metadata = {**nested_metadata, **metadata}
        expected_reference = "finsight_ml_dataset_v3" if self._reference_data_dir else "finsight_dataset_v2"
        return (
            effective_metadata.get("reference_dataset") == expected_reference
        )

    def _metadata_needs_update(self, model_name: str, metadata: dict[str, Any]) -> bool:
        required_keys = {
            "algorithm",
            "feature_count",
            "training_timestamp",
            "pipeline_version",
            "feature_version",
            "quality_metadata_version",
        }
        if not required_keys.issubset(metadata.keys()):
            return True
        if model_name == self._behaviour_engine.model_name and not metadata.get("cluster_profiles"):
            return True
        return False

    def _build_snapshot(self, user_id: str):
        return self._feature_pipeline.build_snapshot(self._dataset_service, user_id, metadata={"phase": 9})

    def _financial_context(self, snapshot: Any) -> dict[str, Any]:
        self._ensure_snapshot_has_data(snapshot)
        profile = dict(snapshot.financial_profile or {})
        commitment_ratio = self._safe_rate(profile.get("monthly_commitments"), profile.get("monthly_financial_capacity"))
        monthly_capacity = float(profile.get("monthly_financial_capacity") or 0.0)
        monthly_commitments = float(profile.get("monthly_commitments") or 0.0)
        current_exposure = (
            round(monthly_commitments * 100.0 / monthly_capacity, 2)
            if monthly_capacity > 0.0
            else 0.0
        )
        profile["exposure_score"] = current_exposure
        feature_row = self._feature_pipeline.build_feature_row(
            replace(snapshot, financial_profile=profile)
        )
        payment_reliability = self._payment_reliability(snapshot, profile)
        profile["transaction_success_rate"] = payment_reliability if payment_reliability is not None else 0.0
        bnpl_dependency = self._safe_rate(profile.get("active_bnpl"), profile.get("total_active_commitments"))
        return {
            "monthly_financial_capacity": monthly_capacity,
            "monthly_commitments": monthly_commitments,
            "exposure_score": current_exposure,
            "financial_health": str(profile.get("financial_health") or ""),
            "commitment_ratio": commitment_ratio,
            "payment_reliability": payment_reliability,
            "bnpl_dependency": bnpl_dependency,
            "active_subscriptions": float(profile.get("active_subscriptions") or 0.0),
            "active_emis": float(profile.get("active_emis") or 0.0),
            "active_bnpl": float(profile.get("active_bnpl") or 0.0),
            "financial_flexibility": float(feature_row.get("financial_flexibility", 0.0)),
            "spending_variance": float(feature_row.get("spending_variance", 0.0)),
            "income_stability": float(feature_row.get("income_stability", 0.0)),
            "autopay_coverage": float(feature_row.get("autopay_coverage", 0.0)),
            "subscription_density": float(feature_row.get("subscription_density", 0.0)),
            "emi_burden_ratio": float(feature_row.get("emi_burden_ratio", 0.0)),
            "feature_count": len(feature_row),
        }

    @staticmethod
    def _ensure_snapshot_has_data(snapshot: Any) -> None:
        transactions = getattr(snapshot, "transactions", None)
        profile = getattr(snapshot, "financial_profile", None) or {}
        if (transactions is None or transactions.empty) and not profile:
            user_id = getattr(snapshot, "user_id", "unknown")
            raise ExposureDataUnavailableError(
                f"No financial data available for user: {user_id}"
            )

    def _supporting_factors_for_distress(self, context: dict[str, Any]) -> list[str]:
        factors = [
            f"Exposure score is {context['exposure_score']:.2f}%.",
            f"Monthly commitments consume {context['commitment_ratio'] * 100.0:.1f}% of capacity.",
        ]
        payment_reliability = context.get("payment_reliability")
        factors.append(
            f"Payment reliability is {payment_reliability * 100.0:.1f}%."
            if payment_reliability is not None
            else "Payment reliability is Unavailable."
        )
        if context["bnpl_dependency"] > 0:
            factors.append(f"BNPL dependency accounts for {context['bnpl_dependency'] * 100.0:.1f}% of active commitments.")
        if context["financial_flexibility"] < 0.5:
            factors.append(f"Financial flexibility is limited at {context['financial_flexibility'] * 100.0:.1f}%.")
        return factors

    def _supporting_factors_for_exposure(self, context: dict[str, Any], prediction: float) -> list[str]:
        delta = prediction - context["exposure_score"]
        return [
            f"Current exposure score is {context['exposure_score']:.2f}%.",
            f"Projected exposure score is {prediction:.2f}%.",
            f"Projected change is {delta:+.2f} points.",
            f"Commitment ratio is {context['commitment_ratio'] * 100.0:.1f}% of monthly capacity.",
        ]

    def _supporting_factors_for_persona(self, context: dict[str, Any], persona_name: str) -> list[str]:
        profile = self._model_metadata_cache.get(self._behaviour_engine.model_name, {}).get("cluster_profiles", {})
        cluster_profile = profile.get(str(context.get("cluster")), {}) or {}
        return list(cluster_profile.get("top_features", [])) or [
            f"Persona resolved as {persona_name} from cluster behaviour.",
        ]

    def _supporting_factors_for_anomaly(self, context: dict[str, Any], score: float) -> list[str]:
        return [
            f"Anomaly score is {score:.4f}.",
            f"Spending variance is {context['spending_variance']:.2f}.",
            (
                f"Payment reliability is {context['payment_reliability'] * 100.0:.1f}%."
                if context.get("payment_reliability") is not None
                else "Payment reliability is Unavailable."
            ),
            f"AutoPay coverage is {context['autopay_coverage'] * 100.0:.1f}%.",
        ]

    @classmethod
    def _payment_reliability(cls, snapshot: Any, profile: dict[str, Any]) -> float | None:
        transactions = getattr(snapshot, "transactions", None)
        if transactions is not None and not transactions.empty and "transaction_status" in transactions.columns:
            statuses = transactions["transaction_status"].map(classify_transaction_status)
            if statuses.eq(TransactionStatus.UNKNOWN).all():
                return None
            successful = int(statuses.eq(TransactionStatus.SUCCESSFUL).sum())
            return round(successful / len(statuses), 4)
        if transactions is not None and not transactions.empty:
            return None

        raw_rate = profile.get("transaction_success_rate")
        if raw_rate is None:
            return None
        return cls._normalized_rate(raw_rate)

    @staticmethod
    def _normalized_rate(value: Any) -> float:
        if isinstance(value, str) and value.endswith("%"):
            value = value.rstrip("%")
        rate = float(value or 0.0)
        if rate > 1.0:
            rate /= 100.0
        return max(min(rate, 1.0), 0.0)

    @staticmethod
    def _safe_rate(numerator: Any, denominator: Any) -> float:
        try:
            denominator_value = float(denominator or 0.0)
            numerator_value = float(numerator or 0.0)
        except (TypeError, ValueError):
            return 0.0
        if denominator_value == 0.0:
            return 0.0
        return numerator_value / denominator_value

    def get_distress(
        self,
        user_id: str,
        snapshot: Any | None = None,
        current_state: CurrentFinancialState | None = None,
    ) -> FinancialDistressResponse:
        snapshot = snapshot or self._build_snapshot(user_id)
        context = self._financial_context(snapshot)
        current_state = current_state or self._authoritative_current_state(user_id)
        prediction = self._distress_engine.predict(snapshot, model_version=self._supervised_model_version)
        item = prediction.items[0] if prediction.items else None
        if item is None:
            raise ValueError("No distress prediction available.")
        if isinstance(item.prediction, (int, float)) and int(item.prediction) in {0, 1}:
            label = "High Risk" if int(item.prediction) == 1 else "Low Risk"
        else:
            label = str(item.prediction)
        insight_context = {
            "snapshot_metrics": context,
            "prediction_metadata": prediction.metadata,
        }
        insight = self._insights_layer.build_distress_insight(label, item.confidence, self._supporting_factors_for_distress(context), context=self._to_insight_context(insight_context))
        return FinancialDistressResponse(
            user_id=user_id,
            prediction=label,
            confidence=item.confidence,
            probabilities=item.probabilities,
            prediction_target="Next-month failed, declined, or rejected transaction event.",
            forecast_horizon_months=1,
            confidence_semantics="Maximum Random Forest class probability; not calibrated and not a current financial-risk score.",
            current_state=current_state,
            is_current_risk_score=False,
            supporting_metadata={"model_name": prediction.model_name, "model_version": prediction.model_version},
            insight=insight,
            generated_at=datetime.now(timezone.utc),
        )

    def get_exposure_forecast(
        self,
        user_id: str,
        snapshot: Any | None = None,
        current_state: CurrentFinancialState | None = None,
    ) -> ExposureForecastResponse:
        snapshot = snapshot or self._build_snapshot(user_id)
        context = self._financial_context(snapshot)
        current_state = current_state or self._authoritative_current_state(user_id)
        prediction = self._exposure_engine.predict(snapshot, model_version=self._supervised_model_version)
        item = prediction.items[0] if prediction.items else None
        if item is None:
            raise ValueError("No exposure forecast available.")
        value = float(item.prediction)
        confidence = self._exposure_confidence(context, value, prediction.metadata.get("artifact_metrics", {}))
        coverage = self._exposure_target_coverage()
        insight = self._insights_layer.build_exposure_insight(value, confidence, self._supporting_factors_for_exposure(context, value), context=self._to_insight_context({"snapshot_metrics": context, "prediction_metadata": prediction.metadata}))
        return ExposureForecastResponse(
            user_id=user_id,
            future_exposure=value,
            forecast_exposure=value,
            forecast_horizon_months=1,
            target_definition="Successful next-month commitment amounts divided by successful positive next-month income amounts, multiplied by 100.",
            forecast_available=True,
            availability_status=f"available_model_forecast; reference target coverage is {coverage:.2%}",
            observed_target_coverage=coverage,
            confidence=confidence,
            confidence_semantics="Heuristic forecast-quality signal using test R² and current-to-forecast stability; not a calibrated probability.",
            current_state=current_state,
            insight=insight,
            generated_at=datetime.now(timezone.utc),
        )

    def get_persona(
        self,
        user_id: str,
        snapshot: Any | None = None,
        current_state: CurrentFinancialState | None = None,
    ) -> PersonaResponse:
        snapshot = snapshot or self._build_snapshot(user_id)
        context = self._financial_context(snapshot)
        current_state = current_state or self._authoritative_current_state(user_id)
        prediction = self._behaviour_engine.predict(snapshot, model_version=self._unsupervised_model_version)
        item = prediction.items[0] if prediction.items else None
        if item is None:
            raise ValueError("No persona prediction available.")
        cluster = item.prediction
        persona_name, persona_profile = self._behaviour_engine.describe_persona(cluster, self._model_metadata_cache.get(self._behaviour_engine.model_name, {}))
        context["cluster"] = cluster
        confidence = self._persona_confidence(persona_profile)
        insight = self._insights_layer.build_persona_insight(cluster, confidence, self._supporting_factors_for_persona(context, persona_name), context=self._to_insight_context({"snapshot_metrics": context, "prediction_metadata": {"cluster_profile": persona_profile}, "persona_name": persona_name}))
        return PersonaResponse(
            user_id=user_id,
            cluster=cluster,
            current_profile_cluster=cluster,
            persona_name=persona_name,
            descriptive_only=True,
            cluster_semantics="Descriptive current financial-profile/behavioural cluster; not a future-behaviour prediction.",
            confidence=confidence,
            current_state=current_state,
            insight=insight,
            generated_at=datetime.now(timezone.utc),
        )

    def get_anomaly(
        self,
        user_id: str,
        snapshot: Any | None = None,
        current_state: CurrentFinancialState | None = None,
    ) -> AnomalyResponse:
        snapshot = snapshot or self._build_snapshot(user_id)
        context = self._financial_context(snapshot)
        current_state = current_state or self._authoritative_current_state(user_id)
        item = self._anomaly_engine.predict_with_score(snapshot, model_version=self._unsupervised_model_version)
        score = float(item.prediction)
        anomaly = self._anomaly_engine.anomaly_flag(score)
        insight = self._insights_layer.build_anomaly_insight(anomaly, item.confidence, self._supporting_factors_for_anomaly(context, score), context=self._to_insight_context({"snapshot_metrics": context, "prediction_metadata": {**item.metadata, "decision_score": score}}))
        return AnomalyResponse(
            user_id=user_id,
            anomaly=anomaly,
            score=score,
            reference_population_anomaly=anomaly,
            anomaly_score=score,
            anomaly_status="reference_population_anomalous" if anomaly else "reference_population_typical",
            comparison_population="Temporal reference-population feature snapshots",
            not_fraud_detection=True,
            confidence=item.confidence,
            confidence_semantics="Isolation Forest decision-score strength heuristic; not a calibrated probability.",
            current_state=current_state,
            insight=insight,
            generated_at=datetime.now(timezone.utc),
        )

    def get_intelligence(self, user_id: str) -> FinancialIntelligenceResponseSchema:
        snapshot = self._build_snapshot(user_id)
        current_state = self._authoritative_current_state(user_id)
        distress = self.get_distress(user_id, snapshot=snapshot, current_state=current_state)
        exposure_forecast = self.get_exposure_forecast(user_id, snapshot=snapshot, current_state=current_state)
        persona = self.get_persona(user_id, snapshot=snapshot, current_state=current_state)
        anomaly = self.get_anomaly(user_id, snapshot=snapshot, current_state=current_state)
        fused = self._fusion_layer.fuse(
            user_id,
            predictions=[
                EnginePredictionEnvelope("distress", distress.prediction, distress.confidence, {"model_name": distress.supporting_metadata.get("model_name")}),
                EnginePredictionEnvelope("exposure_forecast", exposure_forecast.future_exposure, exposure_forecast.confidence, {}),
                EnginePredictionEnvelope("persona", persona.persona_name, persona.confidence, {}),
                EnginePredictionEnvelope("anomaly", anomaly.anomaly, anomaly.confidence, {}),
            ],
            metadata={"engines": ["distress", "exposure_forecast", "persona", "anomaly"]},
        )
        model_signals = {
            "distress": {
                "prediction": distress.prediction,
                "probabilities": distress.probabilities,
                "confidence": distress.confidence,
                "confidence_semantics": distress.confidence_semantics,
                "target": distress.prediction_target,
                "horizon_months": distress.forecast_horizon_months,
            },
            "exposure_forecast": {
                "forecast_exposure": exposure_forecast.forecast_exposure,
                "confidence": exposure_forecast.confidence,
                "confidence_semantics": exposure_forecast.confidence_semantics,
                "target_definition": exposure_forecast.target_definition,
                "horizon_months": exposure_forecast.forecast_horizon_months,
                "available": exposure_forecast.forecast_available,
            },
            "persona": {
                "current_profile_cluster": persona.current_profile_cluster,
                "persona_name": persona.persona_name,
                "descriptive_only": persona.descriptive_only,
                "confidence": persona.confidence,
                "confidence_semantics": "Cluster-separation heuristic; descriptive only, not a probability of future behaviour.",
            },
            "anomaly": {
                "reference_population_anomaly": anomaly.reference_population_anomaly,
                "anomaly_score": anomaly.anomaly_score,
                "anomaly_status": anomaly.anomaly_status,
                "confidence": anomaly.confidence,
                "confidence_semantics": anomaly.confidence_semantics,
                "comparison_population": anomaly.comparison_population,
            },
        }
        signal_quality = {
            "overall_status": "per_model_signals_only",
            "universal_probability": False,
            "description": "The legacy weighted summary combines incomparable model-specific heuristics and must not be interpreted as a probability, risk score, or universal AI confidence.",
            "per_model": {
                name: {
                    "available": signal.get("confidence") is not None,
                    "confidence_semantics": signal.get("confidence_semantics"),
                }
                for name, signal in model_signals.items()
            },
        }
        return FinancialIntelligenceResponseSchema(
            user_id=user_id,
            distress=distress,
            exposure_forecast=exposure_forecast,
            persona=persona,
            anomaly=anomaly,
            current_state=current_state,
            model_signals=model_signals,
            signal_quality=signal_quality,
            fused_confidence=fused.confidence,
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _to_insight_context(payload: dict[str, Any]) -> Any:
        from app.ml.insights.insights_generator import InsightContext

        return InsightContext(snapshot_metrics=payload.get("snapshot_metrics", {}), prediction_metadata=payload.get("prediction_metadata", {}), persona_name=payload.get("persona_name"))

    @staticmethod
    def _current_state(context: dict[str, Any]) -> CurrentFinancialState:
        return CurrentFinancialState(
            current_exposure=float(context.get("exposure_score", 0.0)),
            monthly_commitments=float(context.get("monthly_commitments", 0.0)),
            monthly_capacity=float(context.get("monthly_financial_capacity", 0.0)),
            available_capacity=float(context.get("monthly_financial_capacity", 0.0) - context.get("monthly_commitments", 0.0)),
            financial_health=str(context.get("financial_health") or "Unavailable"),
            payment_reliability=context.get("payment_reliability"),
        )

    def _authoritative_current_state(self, user_id: str) -> CurrentFinancialState:
        exposure = self._exposure_service.get_exposure_intelligence(user_id)
        status = exposure.current_financial_status
        return CurrentFinancialState(
            current_exposure=float(status.exposure_score),
            monthly_commitments=float(status.monthly_total_commitments),
            monthly_capacity=float(status.monthly_financial_capacity),
            available_capacity=float(status.available_monthly_capacity),
            financial_health=exposure.financial_health.financial_health_label,
            payment_reliability=exposure.payment_reliability,
        )

    def _exposure_target_coverage(self) -> float:
        metadata = self._model_metadata_cache.get(self._exposure_engine.model_name, {})
        distribution = metadata.get("target_distribution", {}).get("future_exposure", {})
        observed = float(distribution.get("observed", 0.0) or 0.0)
        unavailable = float(distribution.get("missing_no_positive_income", 0.0) or 0.0)
        total = observed + unavailable
        return round(observed / total, 4) if total else 0.0

    @staticmethod
    def _exposure_confidence(context: dict[str, Any], forecast: float, metrics: dict[str, Any]) -> float:
        r2 = float(metrics.get("r2", 0.0) or 0.0)
        mae = float(metrics.get("mae", 0.0) or 0.0)
        delta = abs(forecast - float(context.get("exposure_score", 0.0)))
        scale = max(float(context.get("exposure_score", 0.0)), 1.0)
        quality_score = 0.6 + (0.35 * max(min(r2, 1.0), 0.0))
        stability_score = max(0.0, 1.0 - min(delta / (scale + mae + 1.0), 1.0))
        return round(max(min((quality_score * 0.75) + (stability_score * 0.25), 1.0), 0.0), 4)

    @staticmethod
    def _persona_confidence(profile: dict[str, Any]) -> float:
        separation_score = float(profile.get("separation_score", 0.0) or 0.0)
        cluster_share = float(profile.get("cluster_share", 0.0) or 0.0)
        confidence = 0.55 + min(separation_score * 0.5, 0.30) + min(cluster_share * 0.25, 0.10)
        return round(max(min(confidence, 0.98), 0.0), 4)


@lru_cache(maxsize=1)
def get_ml_service(
    dataset_service: DatasetService = Depends(get_dataset_service),
    exposure_service: ExposureService = Depends(get_exposure_service),
) -> MLService:
    if not isinstance(dataset_service, DatasetService):
        dataset_service = get_dataset_service()
    if not isinstance(exposure_service, ExposureService):
        exposure_service = get_exposure_service(dataset_service)
    return MLService(dataset_service, exposure_service)
