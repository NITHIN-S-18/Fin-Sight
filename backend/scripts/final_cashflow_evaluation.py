from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

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
from app.ml.preprocessing import PreprocessingConfig, PreprocessingPipeline
from app.ml.config import get_ml_config


def metrics(actual: list[float], predicted: list[float]) -> dict[str, float]:
    report = evaluate_regression(actual, predicted)
    errors = sorted(abs(a - p) for a, p in zip(actual, predicted))
    return {
        "mae": report.mae,
        "rmse": report.rmse,
        "r2": report.r2,
        "median_absolute_error": report.median_absolute_error,
        "p90_absolute_error": round(errors[min(len(errors) - 1, int(len(errors) * 0.9))], 4)
        if errors
        else 0.0,
        "mean_actual": round(sum(actual) / len(actual), 4) if actual else 0.0,
        "mean_predicted": round(sum(predicted) / len(predicted), 4) if predicted else 0.0,
        "prediction_bias": round((sum(predicted) - sum(actual)) / len(actual), 4)
        if actual
        else 0.0,
    }


def frame(rows: list[CashFlowExample]) -> pd.DataFrame:
    return pd.DataFrame([{feature: getattr(row, feature) for feature in FEATURES} for row in rows])


def targets(rows: list[CashFlowExample], target: str) -> list[float]:
    return [float(getattr(row, target)) for row in rows]


def baseline(rows: list[CashFlowExample], target: str, name: str) -> list[float]:
    feature = {
        "previous_month": f"feature_{target}",
        "three_month_average": f"feature_{target}_3m",
        "six_month_average": f"feature_{target}_6m",
    }[name]
    return [float(getattr(row, feature)) for row in rows]


def month_range(rows: list[CashFlowExample]) -> list[str]:
    feature_months = sorted({row.feature_month for row in rows})
    target_months = sorted({row.outcome_month for row in rows})
    return [feature_months[0], feature_months[-1], target_months[0], target_months[-1]]


def temporal_split(rows: list[CashFlowExample]) -> dict[str, list[CashFlowExample]]:
    months = sorted({row.feature_month for row in rows})
    train_end = int(len(months) * 0.70)
    validation_end = int(len(months) * 0.85)
    periods = {
        "train": set(months[:train_end]),
        "validation": set(months[train_end:validation_end]),
        "test": set(months[validation_end:]),
    }
    return {name: [row for row in rows if row.feature_month in selected] for name, selected in periods.items()}


def user_split(rows: list[CashFlowExample]) -> dict[str, list[CashFlowExample]]:
    users = sorted({row.user_id for row in rows})
    development_end = int(len(users) * 0.70)
    validation_end = int(len(users) * 0.85)
    populations = {
        "development": set(users[:development_end]),
        "validation": set(users[development_end:validation_end]),
        "unseen_test": set(users[validation_end:]),
    }
    return {name: [row for row in rows if row.user_id in selected] for name, selected in populations.items()}


def user_population_report(rows: list[CashFlowExample]) -> dict[str, Any]:
    users = sorted({row.user_id for row in rows})
    return {
        "user_count": len(users),
        "user_id_range": [users[0], users[-1]],
        "snapshot_count": len(rows),
        "target_month_range": sorted({row.outcome_month for row in rows})[::max(1, len({row.outcome_month for row in rows}) - 1)],
    }


def train_model(train_rows: list[CashFlowExample], validation_rows: list[CashFlowExample]) -> tuple[dict[str, Any], dict[str, Any]]:
    seed = get_ml_config().default_random_seed
    pipeline = PreprocessingPipeline(
        PreprocessingConfig(scaling_strategy=ScalingStrategy.STANDARD, random_state=seed)
    )
    train_features = pipeline.fit_transform(frame(train_rows))
    validation_features = pipeline.transform(frame(validation_rows))
    models: dict[str, Any] = {}
    selection: dict[str, str] = {}
    validation_report: dict[str, Any] = {}
    for target in TARGETS:
        actual = targets(validation_rows, target)
        baselines = {
            name: metrics(actual, baseline(validation_rows, target, name))
            for name in ("previous_month", "three_month_average", "six_month_average")
        }
        strongest = min(baselines, key=lambda name: baselines[name]["mae"])
        model = HistGradientBoostingRegressor(
            max_iter=100,
            learning_rate=0.05,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=seed,
        )
        model.fit(train_features, targets(train_rows, target))
        predicted = [max(0.0, float(value)) for value in model.predict(validation_features)]
        ml_report = metrics(actual, predicted)
        improvement = (
            (baselines[strongest]["mae"] - ml_report["mae"]) / baselines[strongest]["mae"] * 100
            if baselines[strongest]["mae"]
            else 0.0
        )
        selected = "HistGradientBoosting" if target == "variable" and improvement >= 5.0 else strongest
        selection[target] = selected
        models[target] = model
        validation_report[target] = {
            "strongest_baseline": {"name": strongest, **baselines[strongest]},
            "HistGradientBoosting": {**ml_report, "improvement_percent": round(improvement, 4)},
            "selected": selected,
        }
    return {"pipeline": pipeline, "models": models, "selection": selection}, validation_report


def evaluate_frozen(model_state: dict[str, Any], rows: list[CashFlowExample]) -> dict[str, Any]:
    pipeline = model_state["pipeline"]
    features = pipeline.transform(frame(rows))
    result: dict[str, Any] = {}
    for target in TARGETS:
        actual = targets(rows, target)
        selected = model_state["selection"][target]
        if selected == "HistGradientBoosting":
            predicted = [max(0.0, float(value)) for value in model_state["models"][target].predict(features)]
        else:
            predicted = baseline(rows, target, selected)
        baseline_name = min(
            ("previous_month", "three_month_average", "six_month_average"),
            key=lambda name: metrics(actual, baseline(rows, target, name))["mae"],
        )
        base_report = metrics(actual, baseline(rows, target, baseline_name))
        model_report = metrics(actual, predicted)
        result[target] = {
            "selected": selected,
            "model": model_report,
            "strongest_baseline": {"name": baseline_name, **base_report},
            "improvement_over_baseline_percent": round(
                (base_report["mae"] - model_report["mae"]) / base_report["mae"] * 100, 4
            )
            if base_report["mae"]
            else 0.0,
        }
    return result


def case_studies(model_state: dict[str, Any], rows: list[CashFlowExample]) -> list[dict[str, Any]]:
    summaries = pd.DataFrame(
        [
            {
                "user_id": row.user_id,
                "income": row.income,
                "committed": row.committed,
                "variable": row.variable,
            }
            for row in rows
        ]
    ).groupby("user_id").agg(
        income_mean=("income", "mean"),
        income_std=("income", "std"),
        committed=("committed", "mean"),
        variable=("variable", "mean"),
    )
    summaries["income_cv"] = (
        summaries["income_std"] / summaries["income_mean"].replace(0, pd.NA)
    ).fillna(0)
    categories = {
        "stable income": summaries.sort_values(["income_cv", "income_mean"]).index[0],
        "variable income": summaries.sort_values(["income_cv", "income_mean"], ascending=[False, True]).index[0],
        "high commitments": summaries.sort_values(["committed"], ascending=False).index[0],
        "low commitments": summaries.sort_values(["committed"]).index[0],
        "high discretionary spending": summaries.sort_values(["variable"], ascending=False).index[0],
    }
    selected_rows = []
    for pattern, user_id in categories.items():
        user_rows = [row for row in rows if row.user_id == user_id]
        row = sorted(user_rows, key=lambda item: item.feature_month)[-1]
        predictions = evaluate_frozen(model_state, [row])
        selected_rows.append(
            {
                "pattern": pattern,
                "user_id": user_id,
                "feature_month": row.feature_month,
                "target_month": row.outcome_month,
                "historical": {
                    "income_previous": row.feature_income,
                    "income_6m_average": row.feature_income_6m,
                    "committed_6m_average": row.feature_committed_6m,
                    "variable_6m_average": row.feature_variable_6m,
                },
                "predicted": {
                    target: predictions[target]["model"]["mean_predicted"]
                    for target in TARGETS
                },
                "actual": {target: getattr(row, target) for target in TARGETS},
                "absolute_error": {
                    target: abs(getattr(row, target) - predictions[target]["model"]["mean_predicted"])
                    for target in TARGETS
                },
            }
        )
    all_errors = []
    for row in rows:
        prediction = evaluate_frozen(model_state, [row])
        all_errors.append(
            (
                sum(
                    abs(getattr(row, target) - prediction[target]["model"]["mean_predicted"])
                    for target in TARGETS
                ),
                row,
                prediction,
            )
        )
    _, row, prediction = max(all_errors, key=lambda item: item[0])
    selected_rows.append(
        {
            "pattern": "poor prediction (largest combined absolute error)",
            "user_id": row.user_id,
            "feature_month": row.feature_month,
            "target_month": row.outcome_month,
            "historical": {
                "income_previous": row.feature_income,
                "income_6m_average": row.feature_income_6m,
                "committed_6m_average": row.feature_committed_6m,
                "variable_6m_average": row.feature_variable_6m,
            },
            "predicted": {
                target: prediction[target]["model"]["mean_predicted"]
                for target in TARGETS
            },
            "actual": {target: getattr(row, target) for target in TARGETS},
            "absolute_error": {
                target: abs(getattr(row, target) - prediction[target]["model"]["mean_predicted"])
                for target in TARGETS
            },
        }
    )
    return selected_rows


def sanity_checks(model_state: dict[str, Any], rows: list[CashFlowExample]) -> dict[str, Any]:
    pipeline = model_state["pipeline"]
    features = pipeline.transform(frame(rows))
    predictions: dict[str, list[float]] = {}
    for target in TARGETS:
        selected = model_state["selection"][target]
        if selected == "HistGradientBoosting":
            values = model_state["models"][target].predict(features)
            predictions[target] = [max(0.0, float(value)) for value in values]
        else:
            predictions[target] = baseline(rows, target, selected)
    totals = [predictions["committed"][i] + predictions["variable"][i] for i in range(len(rows))]
    net = [predictions["income"][i] - totals[i] for i in range(len(rows))]
    return {
        "minimum_predictions": {target: min(values) for target, values in predictions.items()},
        "negative_expense_predictions": {
            target: sum(value < 0 for value in predictions[target])
            for target in ("committed", "variable")
        },
        "derived_consistency": {
            "total_expenses": all(
                abs(totals[i] - (predictions["committed"][i] + predictions["variable"][i])) < 1e-9
                for i in range(len(rows))
            ),
            "net_cash": all(
                abs(net[i] - (predictions["income"][i] - totals[i])) < 1e-9
                for i in range(len(rows))
            ),
        },
    }


def main() -> dict[str, Any]:
    data_dir = ROOT / "app/data/ml_dataset_v3"
    users = pd.read_csv(data_dir / "users.csv")
    transactions = pd.read_csv(data_dir / "finsight_ml_dataset_v3.csv")
    transactions["transaction_date"] = pd.to_datetime(transactions["transaction_date"], errors="coerce")
    builder = CashFlowForecastDatasetBuilder()
    rows = builder.build(transactions)
    temporal = temporal_split(rows)
    populations = user_split(rows)
    model_state, unseen_validation = train_model(populations["development"], populations["validation"])
    unseen_test = evaluate_frozen(model_state, populations["unseen_test"])
    unseen_cases = case_studies(model_state, populations["unseen_test"])
    sanity = sanity_checks(model_state, populations["unseen_test"])
    temporal_report = json.loads((ROOT.parent / "cashflow_xgboost_report.json").read_text(encoding="utf-8"))
    temporal_report["targets"] = temporal_report["targets"]

    return {
        "dataset": {
            "name": "finsight_ml_dataset_v3",
            "users": len(users),
            "transactions": len(transactions),
            "date_range": [str(transactions["transaction_date"].min().date()), str(transactions["transaction_date"].max().date())],
            "usable_users": len({row.user_id for row in rows}),
            "usable_snapshots": len(rows),
            "quality": {
                "exact_duplicate_rows": int(transactions.duplicated().sum()),
                "duplicate_user_date_amount": int(transactions.duplicated(["user_id", "transaction_date", "amount"]).sum()),
                "invalid_dates": int(transactions["transaction_date"].isna().sum()),
                "negative_transactions": int((pd.to_numeric(transactions["amount"], errors="coerce") < 0).sum()),
                "status_counts": transactions["transaction_status"].value_counts().to_dict(),
                "class_counts": transactions["transaction_class"].value_counts().to_dict(),
                "missing_values": {key: int(value) for key, value in transactions.isna().sum().items()},
            },
            "income_flag_rule": "Yes is income; No is non-income; only successful positive amounts contribute.",
        },
        "temporal_experiment": {
            "split": {name: {"count": len(part), "range": month_range(part)} for name, part in temporal.items()},
            "comparison": temporal_report["targets"],
            "selected_forecasters": temporal_report["selected_forecasters"],
        },
        "unseen_user_experiment": {
            "split": {name: user_population_report(part) for name, part in populations.items()},
            "validation": unseen_validation,
            "unseen_test": unseen_test,
            "user_overlap": {
                left: {
                    right: bool({row.user_id for row in populations[left]} & {row.user_id for row in populations[right]})
                    for right in populations
                    if right != left
                }
                for left in populations
            },
        },
        "generalization": {
            target: {
                "known_user_test_mae": temporal_report["test"][target]["metrics"]["mae"],
                "unseen_user_mae": unseen_test[target]["model"]["mae"],
                "degradation_percent": round(
                    (unseen_test[target]["model"]["mae"] - temporal_report["test"][target]["metrics"]["mae"])
                    / temporal_report["test"][target]["metrics"]["mae"]
                    * 100,
                    4,
                ),
                "baseline_mae": unseen_test[target]["strongest_baseline"]["mae"],
                "model_improvement_percent": unseen_test[target]["improvement_over_baseline_percent"],
                "classification": (
                    "STRONG GENERALIZATION"
                    if unseen_test[target]["improvement_over_baseline_percent"] >= 5
                    else "MODERATE GENERALIZATION"
                    if unseen_test[target]["improvement_over_baseline_percent"] > 0
                    else "NO MEANINGFUL GENERALIZATION"
                ),
            }
            for target in TARGETS
        },
        "case_studies": unseen_cases,
        "sanity_checks": sanity,
        "production_artifact": "cash_flow_forecast/v1.0 unchanged",
        "derived_outputs": {
            "total_expenses": "committed + variable",
            "net_cash": "income - total expenses",
        },
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
