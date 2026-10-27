from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any

import pandas as pd
from sklearn.cluster import KMeans

from app.ml.base import MLTaskType, PredictionResult, ProcessedDataset
from app.ml.config import get_ml_config
from app.ml.feature_engineering import FeatureEngineeringPipeline
from app.ml.inference import InferenceEngine
from app.ml.training import TrainingPipeline
from app.ml.evaluation import evaluate_clustering


class BehaviourIntelligenceEngine:
    model_name = "behaviour_engine"
    algorithm_name = "KMeans"

    def __init__(self) -> None:
        self._ml_config = get_ml_config()
        self._feature_pipeline = FeatureEngineeringPipeline()
        self._training_pipeline = TrainingPipeline()
        self._inference_engine = InferenceEngine()

    def build_features(self, snapshot: Any) -> pd.DataFrame:
        feature_row = self._feature_pipeline.build_feature_row(snapshot)
        return pd.DataFrame([feature_row])

    def train(self, dataset: ProcessedDataset, model_version: str | None = None, metadata: dict[str, Any] | None = None) -> Any:
        candidate_results = self.evaluate_cluster_candidates(dataset.train_features)
        cluster_count = self.select_cluster_count(candidate_results)
        estimator = KMeans(
            n_clusters=cluster_count,
            random_state=self._ml_config.default_random_seed,
            n_init=3,
            max_iter=100,
        )
        training_dataset = replace(
            dataset,
            train_features=dataset.train_features.sample(
                n=min(len(dataset.train_features), 20000),
                random_state=42,
            ),
            train_target=(
                dataset.train_target.loc[
                    dataset.train_features.sample(
                        n=min(len(dataset.train_features), 20000),
                        random_state=42,
                    ).index
                ]
                if dataset.train_target is not None
                else None
            ),
        )
        return self._training_pipeline.train(
            model=estimator,
            dataset=training_dataset,
            model_name=self.model_name,
            model_version=model_version,
            task_type=MLTaskType.CLUSTERING,
            metadata={
                "evaluate_unsupervised": True,
                "selected_cluster_count": cluster_count,
                "cluster_training_sample_count": len(training_dataset.train_features),
                "cluster_selection": candidate_results,
                **(metadata or {}),
            },
        )

    @staticmethod
    def select_cluster_count(candidate_results: dict[str, dict[str, Any]]) -> int:
        if not candidate_results:
            return 2
        ranked = sorted(
            candidate_results.items(),
            key=lambda item: (
                float(item[1].get("silhouette_score", -1.0)),
                -abs(int(item[0]) - 5),
            ),
            reverse=True,
        )
        return int(ranked[0][0])

    @staticmethod
    def evaluate_cluster_candidates(
        features: pd.DataFrame,
        candidate_counts: tuple[int, ...] = (2, 3, 4, 5, 6, 7, 8),
    ) -> dict[str, dict[str, Any]]:
        if len(features) < 3:
            return {}

        evaluation_features = features.sample(
            n=min(len(features), 1000),
            random_state=42,
        )
        results: dict[str, dict[str, Any]] = {}
        for cluster_count in candidate_counts:
            if cluster_count >= len(evaluation_features):
                continue
            estimator = KMeans(n_clusters=cluster_count, random_state=42, n_init=3, max_iter=100)
            labels = estimator.fit_predict(evaluation_features)
            metrics = evaluate_clustering(evaluation_features, labels)
            counts = Counter(labels)
            results[str(cluster_count)] = {
                "silhouette_score": metrics.silhouette_score,
                "cluster_sizes": {str(label): int(count) for label, count in sorted(counts.items())},
                "evaluation_sample_count": len(evaluation_features),
            }
        return results

    def predict(self, snapshot: Any, model_version: str | None = None) -> PredictionResult:
        features = self.build_features(snapshot)
        return self._inference_engine.predict(features, model_name=self.model_name, model_version=model_version)

    @staticmethod
    def build_cluster_profiles(features: pd.DataFrame, labels: list[Any]) -> dict[str, dict[str, Any]]:
        if features.empty or not labels:
            return {}

        feature_frame = features.reset_index(drop=True).copy()
        feature_frame["__cluster__"] = labels
        overall_means = feature_frame.drop(columns=["__cluster__"]).mean(numeric_only=True)

        profiles: dict[str, dict[str, Any]] = {}
        for cluster_value, group in feature_frame.groupby("__cluster__", dropna=False):
            numeric_group = group.drop(columns=["__cluster__"]).mean(numeric_only=True)
            relative_strength = (numeric_group - overall_means).sort_values(ascending=False)
            top_features = []
            for feature_name, value in relative_strength.head(3).items():
                raw_value = float(numeric_group.get(feature_name, 0.0))
                top_features.append(f"{BehaviourIntelligenceEngine._feature_label(feature_name)} ({raw_value:.2f})")

            persona_name, rationale = BehaviourIntelligenceEngine._infer_persona(numeric_group)
            separation_score = float(relative_strength.abs().mean()) if not relative_strength.empty else 0.0
            profiles[str(cluster_value)] = {
                "persona_name": persona_name,
                "top_features": top_features,
                "cluster_size": int(len(group)),
                "feature_means": {str(key): float(value) for key, value in numeric_group.items()},
                "rationale": rationale,
                "separation_score": separation_score,
                "cluster_share": round(len(group) / len(feature_frame), 4),
            }
        return profiles

    @staticmethod
    def describe_persona(cluster_label: Any, metadata: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
        profiles = (metadata or {}).get("cluster_profiles") or {}
        profile = profiles.get(str(cluster_label)) or {}
        persona_name = profile.get("persona_name") or "Balanced User"
        return persona_name, profile

    @staticmethod
    def _infer_persona(feature_means: pd.Series) -> tuple[str, list[str]]:
        subscription_density = float(feature_means.get("subscription_density", 0.0))
        emi_burden_ratio = float(feature_means.get("emi_burden_ratio", 0.0))
        bnpl_dependency = float(feature_means.get("bnpl_dependency", 0.0))
        commitment_ratio = float(feature_means.get("commitment_ratio", 0.0))
        financial_flexibility = float(feature_means.get("financial_flexibility", 0.0))
        payment_reliability = float(feature_means.get("payment_reliability", 0.0))
        autopay_coverage = float(feature_means.get("autopay_coverage", 0.0))
        spending_variance = float(feature_means.get("spending_variance", 0.0))

        rationale: list[str] = []
        if bnpl_dependency >= max(subscription_density, emi_burden_ratio) and bnpl_dependency >= 0.30:
            rationale.append("BNPL dependency dominates the commitment mix.")
            return "BNPL Dependent User", rationale
        if emi_burden_ratio >= max(subscription_density, bnpl_dependency) and emi_burden_ratio >= 0.30:
            rationale.append("EMI burden dominates the commitment mix.")
            return "EMI Focused User", rationale
        if subscription_density >= max(emi_burden_ratio, bnpl_dependency) and commitment_ratio >= 0.20:
            rationale.append("Subscription density is the strongest commitment signal.")
            return "Subscription Heavy User", rationale
        if financial_flexibility >= 0.60 and payment_reliability >= 0.90 and commitment_ratio < 0.25:
            rationale.append("Capacity headroom and payment discipline remain strong.")
            return "Saver", rationale
        if payment_reliability >= 0.90 and autopay_coverage >= 0.50 and spending_variance <= 0.40:
            rationale.append("Payments are stable and commitment behaviour is balanced.")
            return "Balanced User", rationale
        rationale.append("No single commitment pattern dominates the cluster.")
        return "Balanced User", rationale

    @staticmethod
    def _feature_label(feature_name: str) -> str:
        return feature_name.replace("_", " ").title()
