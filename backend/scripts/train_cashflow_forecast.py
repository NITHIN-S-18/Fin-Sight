from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ml.base import ScalingStrategy
from app.ml.cashflow_forecast import (
    FEATURES,
    TARGETS,
    CashFlowExample,
    CashFlowForecastDatasetBuilder,
)
from app.ml.evaluation import evaluate_regression
from app.ml.persistence import ModelPersistenceManager
from app.ml.preprocessing import PreprocessingConfig, PreprocessingPipeline
from app.ml.base import MLTaskType, ModelArtifact, ModelBundle
from app.ml.config import get_ml_config


def _metrics(actual: list[float], predicted: list[float]) -> dict[str, float | None]:
    report = evaluate_regression(actual, predicted)
    errors = sorted(abs(actual_value - predicted_value) for actual_value, predicted_value in zip(actual, predicted))
    return {
        "mae": report.mae,
        "rmse": report.rmse,
        "r2": report.r2,
        "median_absolute_error": report.median_absolute_error,
        "p90_absolute_error": round(errors[min(len(errors) - 1, int(len(errors) * 0.9))], 4) if errors else 0.0,
    }


def _audit(users: pd.DataFrame, transactions: pd.DataFrame) -> dict[str, Any]:
    dates = pd.to_datetime(transactions["transaction_date"], errors="coerce")
    return {
        "dataset_location": str((ROOT / "app/data/ml_dataset_v3").resolve()),
        "users": len(users),
        "transactions": len(transactions),
        "unique_transaction_users": int(transactions["user_id"].nunique()),
        "date_range": [str(dates.min().date()), str(dates.max().date())],
        "invalid_dates": int(dates.isna().sum()),
        "exact_duplicate_rows": int(transactions.duplicated().sum()),
        "duplicate_user_date_amount_rows": int(
            transactions.duplicated(subset=["user_id", "transaction_date", "amount"]).sum()
        ),
        "missing_values": {key: int(value) for key, value in transactions.isna().sum().items()},
        "status_counts": transactions["transaction_status"].fillna("").value_counts().to_dict(),
        "negative_amounts": int((pd.to_numeric(transactions["amount"], errors="coerce") < 0).sum()),
    }


def _split(examples: list[CashFlowExample]) -> dict[str, list[CashFlowExample]]:
    months = sorted({example.feature_month for example in examples})
    train_end = max(1, int(len(months) * 0.70))
    validation_end = max(train_end + 1, int(len(months) * 0.85))
    boundaries = {
        "train": set(months[:train_end]),
        "validation": set(months[train_end:validation_end]),
        "test": set(months[validation_end:]),
    }
    if not all(boundaries.values()):
        raise ValueError("Reference data does not provide non-empty chronological train/validation/test periods.")
    return {
        name: [example for example in examples if example.feature_month in period]
        for name, period in boundaries.items()
    }


def _feature_frame(examples: list[CashFlowExample]) -> pd.DataFrame:
    return pd.DataFrame([{feature: getattr(example, feature) for feature in FEATURES} for example in examples])


def _targets(examples: list[CashFlowExample], target: str) -> list[float]:
    return [float(getattr(example, target)) for example in examples]


def _baseline_predictions(examples: list[CashFlowExample], target: str, name: str) -> list[float]:
    feature = {
        "previous_month": f"feature_{target}",
        "three_month_average": f"feature_{target}_3m",
        "six_month_average": f"feature_{target}_6m",
    }[name]
    return [float(getattr(example, feature)) for example in examples]


def _target_period(examples: list[CashFlowExample]) -> list[str]:
    return sorted({example.outcome_month for example in examples})


def train_reference_dataset() -> dict[str, Any]:
    data_dir = ROOT / "app/data/ml_dataset_v3"
    users = pd.read_csv(data_dir / "users.csv")
    transactions = pd.read_csv(data_dir / "finsight_ml_dataset_v3.csv")
    transactions["transaction_date"] = pd.to_datetime(transactions["transaction_date"], errors="coerce")
    builder = CashFlowForecastDatasetBuilder()
    examples = builder.build(transactions)
    split = _split(examples)

    usable_users = {example.user_id for example in examples}
    result: dict[str, Any] = {
        "audit": {
            **_audit(users, transactions),
            "usable_users": len(usable_users),
            "usable_snapshots": len(examples),
            "history_policy": "At least six contiguous observed months before each target month.",
        },
        "split": {},
        "targets": {},
        "acceptance_status": "REJECTED",
        "production_artifact": False,
    }
    for name, rows in split.items():
        result["split"][name] = {
            "snapshot_count": len(rows),
            "unique_users": len({row.user_id for row in rows}),
            "feature_month_range": [rows[0].feature_month, rows[-1].feature_month],
            "target_month_range": _target_period(rows),
        }

    preprocessing = PreprocessingPipeline(
        PreprocessingConfig(
            scaling_strategy=ScalingStrategy.STANDARD,
            random_state=get_ml_config().default_random_seed,
        )
    )
    train_features = preprocessing.fit_transform(_feature_frame(split["train"]))
    validation_features = preprocessing.transform(_feature_frame(split["validation"]))
    test_features = preprocessing.transform(_feature_frame(split["test"]))
    models: dict[str, HistGradientBoostingRegressor] = {}
    selected: dict[str, str] = {}
    validation_baselines: dict[str, dict[str, dict[str, float | None]]] = {}
    validation_ml: dict[str, dict[str, float | None]] = {}
    test_results: dict[str, Any] = {}

    for target in TARGETS:
        validation_actual = _targets(split["validation"], target)
        baseline_reports = {
            name: _metrics(validation_actual, _baseline_predictions(split["validation"], target, name))
            for name in ("previous_month", "three_month_average", "six_month_average")
        }
        strongest_baseline = min(baseline_reports, key=lambda name: baseline_reports[name]["mae"])
        model = HistGradientBoostingRegressor(
            max_iter=100,
            learning_rate=0.05,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=get_ml_config().default_random_seed,
        )
        model.fit(train_features, _targets(split["train"], target))
        validation_prediction = [max(0.0, float(value)) for value in model.predict(validation_features)]
        ml_report = _metrics(validation_actual, validation_prediction)
        baseline_mae = float(baseline_reports[strongest_baseline]["mae"])
        improvement = ((baseline_mae - float(ml_report["mae"])) / baseline_mae * 100) if baseline_mae else 0.0
        decision = "ml" if improvement >= 5.0 else strongest_baseline
        selected[target] = decision
        models[target] = model
        validation_baselines[target] = {
            "strongest": {"name": strongest_baseline, **baseline_reports[strongest_baseline]},
            "all": baseline_reports,
        }
        validation_ml[target] = {**ml_report, "improvement_over_strongest_baseline_percent": round(improvement, 2)}

        test_actual = _targets(split["test"], target)
        test_baselines = {
            name: _metrics(test_actual, _baseline_predictions(split["test"], target, name))
            for name in ("previous_month", "three_month_average", "six_month_average")
        }
        if decision == "ml":
            test_prediction = [max(0.0, float(value)) for value in model.predict(test_features)]
        else:
            test_prediction = _baseline_predictions(split["test"], target, decision)
        test_results[target] = {
            "selected_forecaster": decision,
            "selected_metrics": _metrics(test_actual, test_prediction),
            "strongest_baseline": {
                "name": strongest_baseline,
                **test_baselines[strongest_baseline],
            },
        }
        if decision == "ml":
            importance = permutation_importance(
                model,
                validation_features,
                validation_actual,
                scoring="neg_mean_absolute_error",
                n_repeats=2,
                random_state=get_ml_config().default_random_seed,
            )
            test_results[target]["key_factors"] = {
                feature: round(float(score), 4)
                for feature, score in sorted(
                    zip(FEATURES, importance.importances_mean),
                    key=lambda item: abs(item[1]),
                    reverse=True,
                )[:5]
            }
        result["targets"][target] = {
            "validation_baselines": validation_baselines[target],
            "validation_ml": validation_ml[target],
            "selection": decision,
            "test": test_results[target],
        }

    accepted_targets = [target for target in TARGETS if selected[target] == "ml"]
    result["selected_forecasters"] = selected
    result["acceptance_status"] = "ACCEPTED" if accepted_targets else "REJECTED"
    result["production_artifact"] = bool(accepted_targets)
    if accepted_targets:
        metadata = {
            "algorithm": "HistGradientBoostingRegressor",
            "acceptance_status": result["acceptance_status"],
            "accepted_targets": accepted_targets,
            "selected_forecasters": selected,
            "dataset_version": "finsight_ml_dataset_v3",
            "feature_version": "cash-flow-features-v1",
            "random_seed": get_ml_config().default_random_seed,
            "split": result["split"],
            "validation": validation_ml,
            "test": test_results,
        }
        bundle = ModelBundle(
            artifact=ModelArtifact(
                model_name="cash_flow_forecast",
                model_version="v1.0",
                task_type=MLTaskType.REGRESSION,
                feature_columns=FEATURES,
                target_column="income,committed,variable",
                metrics=test_results,
                metadata=metadata,
            ),
            model={"models": models, "preprocessor": preprocessing, "selected_forecasters": selected},
            preprocessor_state=preprocessing.state,
        )
        ModelPersistenceManager().save(bundle)
    return result


if __name__ == "__main__":
    report = train_reference_dataset()
    print(json.dumps(report, indent=2, default=str))
