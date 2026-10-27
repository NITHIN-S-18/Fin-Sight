from __future__ import annotations

import pandas as pd
import pytest
from types import SimpleNamespace

from app.ml.engines.anomaly_engine import FinancialAnomalyEngine
from app.ml.engines.behaviour_engine import BehaviourIntelligenceEngine
from app.ml.base import FinancialIntelligenceSnapshot
from app.ml.preprocessing import PreprocessingPipeline
from app.ml.temporal_dataset import TemporalDatasetBuilder
from app.ml.feature_engineering import FeatureEngineeringPipeline
from app.ml.insights.insights_generator import AIInsightsLayer, InsightContext
from app.services.ml_service import MLService
from app.ml.evaluation import evaluate_classification


def test_preprocessing_fits_statistics_on_training_rows_only() -> None:
    features = pd.DataFrame({"signal": [0.0, 0.0, 0.0, 100.0]})

    dataset = PreprocessingPipeline().split_dataset(features, test_size=0.25, random_state=0)

    assert len(dataset.train_features) == 3
    assert dataset.metadata["preprocessing_fit_rows"] == 3
    assert dataset.preprocessing_state is not None
    assert dataset.preprocessing_state.numeric_statistics["signal"]["max"] == 0.0


def test_behaviour_candidate_evaluation_reports_cluster_quality() -> None:
    features = pd.DataFrame(
        {
            "commitment_ratio": [0.0, 0.1, 0.9, 1.0, 0.05, 0.95],
            "financial_flexibility": [1.0, 0.9, 0.1, 0.0, 0.95, 0.05],
        }
    )

    results = BehaviourIntelligenceEngine.evaluate_cluster_candidates(features, candidate_counts=(2, 3))

    assert set(results) == {"2", "3"}
    assert all("silhouette_score" in result for result in results.values())
    assert all(sum(result["cluster_sizes"].values()) == len(features) for result in results.values())


def test_anomaly_score_is_not_treated_as_probability() -> None:
    assert FinancialAnomalyEngine.anomaly_flag(-0.01) is True
    assert FinancialAnomalyEngine.anomaly_flag(0.01) is False


def test_ml_context_reconciles_current_exposure_from_commitments_and_capacity() -> None:
    service = object.__new__(MLService)
    service._feature_pipeline = SimpleNamespace(
        build_feature_row=lambda snapshot: {
            "financial_flexibility": 0.75,
            "spending_variance": 0.0,
            "income_stability": 1.0,
            "autopay_coverage": 0.0,
            "subscription_density": 0.0,
            "emi_burden_ratio": 0.0,
        }
    )
    snapshot = FinancialIntelligenceSnapshot(
        user_id="AUTH-1",
        user_record={},
        transactions=pd.DataFrame([{"amount": 1}]),
        financial_profile={
            "monthly_financial_capacity": 85000,
            "monthly_commitments": 20621,
            "exposure_score": 0.06,
            "transaction_success_rate": "100%",
        },
    )

    context = service._financial_context(snapshot)

    assert context["exposure_score"] == 24.26
    assert context["commitment_ratio"] == 20621 / 85000


def test_ml_distress_context_uses_transaction_statuses_and_marks_missing_reliability_unavailable() -> None:
    service = object.__new__(MLService)
    service._feature_pipeline = SimpleNamespace(
        build_feature_row=lambda snapshot: {
            "financial_flexibility": 0.75,
            "spending_variance": 0.0,
            "income_stability": 1.0,
            "autopay_coverage": 0.0,
            "subscription_density": 0.0,
            "emi_burden_ratio": 0.0,
        }
    )
    snapshot = FinancialIntelligenceSnapshot(
        user_id="AUTH-1",
        user_record={},
        transactions=pd.DataFrame(
            [
                {"transaction_status": "Success"},
                {"transaction_status": "failed"},
                {"transaction_status": "pending"},
            ]
        ),
        financial_profile={
            "monthly_financial_capacity": 85000,
            "monthly_commitments": 20621,
            "exposure_score": 0.06,
            "transaction_success_rate": "0.0",
        },
    )

    context = service._financial_context(snapshot)
    assert context["exposure_score"] == 24.26
    assert context["payment_reliability"] == pytest.approx(1 / 3, abs=0.0001)

    missing_status_snapshot = snapshot.__class__(
        user_id="AUTH-1",
        user_record={},
        transactions=pd.DataFrame([{"amount": 100}]),
        financial_profile=snapshot.financial_profile,
    )
    missing_context = service._financial_context(missing_status_snapshot)
    assert missing_context["payment_reliability"] is None

    insight = AIInsightsLayer().build_distress_insight(
        "Low Risk",
        0.9,
        ["Exposure score is 24.26%."],
        InsightContext(
            snapshot_metrics={**missing_context, "payment_reliability": None},
            prediction_metadata={},
        ),
    )
    assert "current exposure is 24.3%" in insight.explanation
    assert "next-month failed-transaction event prediction" in insight.explanation
    assert "payment reliability is Unavailable" in insight.explanation


def _temporal_fixture() -> tuple[list[dict[str, str]], pd.DataFrame]:
    users = [{"user_id": "U1"}]
    transactions = pd.DataFrame(
        [
            {"user_id": "U1", "transaction_date": "2025-01-10", "amount": 1000, "transaction_status": "Success", "income_flag": True, "transaction_class": "Income"},
            {"user_id": "U1", "transaction_date": "2025-01-20", "amount": 200, "transaction_status": "Success", "income_flag": False, "transaction_class": "Subscription"},
            {"user_id": "U1", "transaction_date": "2025-02-10", "amount": 1200, "transaction_status": "Success", "income_flag": True, "transaction_class": "Income"},
            {"user_id": "U1", "transaction_date": "2025-02-15", "amount": 300, "transaction_status": "Success", "income_flag": False, "transaction_class": "Subscription"},
            {"user_id": "U1", "transaction_date": "2025-02-20", "amount": 300, "transaction_status": "Failed", "income_flag": False, "transaction_class": "Subscription"},
            {"user_id": "U1", "transaction_date": "2025-03-10", "amount": 1100, "transaction_status": "Success", "income_flag": True, "transaction_class": "Income"},
        ]
    )
    return users, transactions


def test_temporal_targets_use_only_observed_next_month() -> None:
    users, transactions = _temporal_fixture()
    dataset = TemporalDatasetBuilder(FeatureEngineeringPipeline()).build(users, transactions)

    assert list(dataset.features.index.get_level_values("snapshot_month")) == ["2025-01", "2025-02"]
    assert dataset.distress_target.tolist() == [1, 0]
    assert dataset.exposure_target.tolist() == [25.0, 0.0]
    assert dataset.metadata["examples"][0]["outcome_month"] == "2025-02"
    assert dataset.metadata["exposure_target_coverage"] == 1.0


def test_temporal_features_do_not_change_when_future_outcome_changes() -> None:
    users, transactions = _temporal_fixture()
    original = TemporalDatasetBuilder(FeatureEngineeringPipeline()).build(users, transactions)

    changed = transactions.copy()
    changed.loc[changed["transaction_date"] == "2025-02-15", "amount"] = 99999
    changed.loc[changed["transaction_date"] == "2025-02-20", "transaction_status"] = "Success"
    updated = TemporalDatasetBuilder(FeatureEngineeringPipeline()).build(users, changed)

    pd.testing.assert_frame_equal(
        original.features.loc[[("U1", "2025-01")]],
        updated.features.loc[[("U1", "2025-01")]],
    )
    assert original.distress_target.iloc[0] == 1
    assert updated.distress_target.iloc[0] == 0


def test_exposure_target_is_unavailable_without_positive_future_income() -> None:
    users = [{"user_id": "U1", "monthly_financial_capacity": 999999}]
    transactions = pd.DataFrame(
        [
            {"user_id": "U1", "transaction_date": "2025-01-10", "amount": 1000, "transaction_status": "Success", "income_flag": True, "transaction_class": "Income"},
            {"user_id": "U1", "transaction_date": "2025-02-10", "amount": 300, "transaction_status": "Success", "income_flag": False, "transaction_class": "Subscription"},
        ]
    )

    dataset = TemporalDatasetBuilder(FeatureEngineeringPipeline()).build(users, transactions)

    assert pd.isna(dataset.exposure_target.iloc[0])
    assert dataset.metadata["exposure_target_coverage"] == 0.0


def test_classification_report_contains_imbalance_evidence() -> None:
    metrics = evaluate_classification([0, 0, 1], [0, 1, 1], probability_scores=[0.1, 0.8, 0.9])

    assert metrics.class_counts == {"0": 2, "1": 1}
    assert metrics.positive_rate == pytest.approx(1 / 3, abs=0.0001)
    assert metrics.confusion_matrix["0"]["1"] == 1


def test_temporal_split_is_chronological_and_fits_preprocessing_on_train_only() -> None:
    users, transactions = _temporal_fixture()
    dataset = TemporalDatasetBuilder(FeatureEngineeringPipeline()).build(users, transactions)
    extra = pd.concat([dataset.features.iloc[[0]]] * 3, ignore_index=True)
    extra.index = pd.MultiIndex.from_tuples(
        [("U2", "2025-03"), ("U2", "2025-04"), ("U2", "2025-05")],
        names=dataset.features.index.names,
    )
    features = pd.concat([dataset.features, extra])
    target = pd.concat([dataset.distress_target, pd.Series([0, 1, 0], index=extra.index)])

    processed = PreprocessingPipeline().split_temporal_dataset(features, target)

    assert processed.metadata["split_strategy"] == "chronological"
    assert processed.metadata["training_period"][1] < processed.metadata["validation_period"][0]
    assert processed.metadata["validation_period"][1] < processed.metadata["test_period"][0]
    assert processed.metadata["preprocessing_fit_rows"] == len(processed.train_features)
