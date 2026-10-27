from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ml.base import ScalingStrategy
from app.ml.cashflow_forecast import (
    FEATURES,
    TARGETS,
    CashFlowForecastDatasetBuilder,
    CashFlowExample,
)
from app.ml.evaluation import evaluate_regression
from app.ml.preprocessing import PreprocessingConfig, PreprocessingPipeline
from app.ml.config import get_ml_config


def metrics(actual: list[float], predicted: list[float]) -> dict[str, float]:
    report = evaluate_regression(actual, predicted)
    errors = sorted(abs(truth - prediction) for truth, prediction in zip(actual, predicted))
    return {
        "mae": report.mae,
        "rmse": report.rmse,
        "r2": report.r2,
        "median_absolute_error": report.median_absolute_error,
        "p90_absolute_error": round(errors[min(len(errors) - 1, int(len(errors) * 0.9))], 4)
        if errors
        else 0.0,
    }


def split_examples(examples: list[CashFlowExample]) -> dict[str, list[CashFlowExample]]:
    months = sorted({example.feature_month for example in examples})
    train_end = max(1, int(len(months) * 0.70))
    validation_end = max(train_end + 1, int(len(months) * 0.85))
    month_sets = {
        "train": set(months[:train_end]),
        "validation": set(months[train_end:validation_end]),
        "test": set(months[validation_end:]),
    }
    if not all(month_sets.values()):
        raise ValueError("The fixed chronological split must contain all three partitions.")
    return {
        name: [example for example in examples if example.feature_month in selected_months]
        for name, selected_months in month_sets.items()
    }


def month_range(examples: list[CashFlowExample]) -> list[str]:
    months = sorted({example.feature_month for example in examples})
    outcomes = sorted({example.outcome_month for example in examples})
    return [months[0], months[-1], outcomes[0], outcomes[-1]]


def feature_frame(examples: list[CashFlowExample]) -> pd.DataFrame:
    return pd.DataFrame(
        [{feature: getattr(example, feature) for feature in FEATURES} for example in examples]
    )


def target_values(examples: list[CashFlowExample], target: str) -> list[float]:
    return [float(getattr(example, target)) for example in examples]


def baseline_values(examples: list[CashFlowExample], target: str, name: str) -> list[float]:
    feature_name = {
        "previous_month": f"feature_{target}",
        "three_month_average": f"feature_{target}_3m",
        "six_month_average": f"feature_{target}_6m",
    }[name]
    return [float(getattr(example, feature_name)) for example in examples]


def _model(seed: int) -> XGBRegressor:
    return XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=seed,
        n_jobs=1,
        tree_method="hist",
    )


def run() -> dict[str, Any]:
    data_dir = ROOT / "app/data/ml_dataset_v3"
    transactions = pd.read_csv(data_dir / "finsight_ml_dataset_v3.csv")
    examples = CashFlowForecastDatasetBuilder().build(transactions)
    split = split_examples(examples)
    seed = get_ml_config().default_random_seed

    pipeline = PreprocessingPipeline(
        PreprocessingConfig(
            scaling_strategy=ScalingStrategy.STANDARD,
            random_state=seed,
        )
    )
    train_features = pipeline.fit_transform(feature_frame(split["train"]))
    validation_features = pipeline.transform(feature_frame(split["validation"]))
    test_features = pipeline.transform(feature_frame(split["test"]))

    result: dict[str, Any] = {
        "dataset": "finsight_ml_dataset_v3",
        "snapshots": len(examples),
        "split": {
            name: {
                "count": len(rows),
                "feature_month_range": month_range(rows)[:2],
                "target_month_range": month_range(rows)[2:],
            }
            for name, rows in split.items()
        },
        "xgboost_version": __import__("xgboost").__version__,
        "targets": {},
    }
    selected: dict[str, str] = {}
    models: dict[str, Any] = {}

    for target in TARGETS:
        validation_actual = target_values(split["validation"], target)
        baseline_reports = {
            name: metrics(validation_actual, baseline_values(split["validation"], target, name))
            for name in ("previous_month", "three_month_average", "six_month_average")
        }
        strongest_name = min(baseline_reports, key=lambda name: baseline_reports[name]["mae"])
        hgb = HistGradientBoostingRegressor(
            max_iter=100,
            learning_rate=0.05,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=seed,
        )
        hgb.fit(train_features, target_values(split["train"], target))
        hgb_report = metrics(
            validation_actual,
            [max(0.0, float(value)) for value in hgb.predict(validation_features)],
        )
        xgb = _model(seed)
        xgb.fit(train_features, target_values(split["train"], target))
        xgb_report = metrics(
            validation_actual,
            [max(0.0, float(value)) for value in xgb.predict(validation_features)],
        )
        strongest_mae = baseline_reports[strongest_name]["mae"]
        current_selected = "HistGradientBoosting" if hgb_report["mae"] < strongest_mae * 0.95 else strongest_name
        if xgb_report["mae"] < min(strongest_mae, hgb_report["mae"]) * 0.95:
            selected[target] = "XGBoost"
            models[target] = xgb
        else:
            selected[target] = current_selected
            models[target] = hgb if current_selected == "HistGradientBoosting" else None
        result["targets"][target] = {
            "strongest_baseline": {"name": strongest_name, **baseline_reports[strongest_name]},
            "baselines": baseline_reports,
            "HistGradientBoosting": hgb_report,
            "XGBoost": xgb_report,
            "selected": selected[target],
        }

    test_results: dict[str, Any] = {}
    for target in TARGETS:
        decision = selected[target]
        actual = target_values(split["test"], target)
        if decision == "XGBoost":
            prediction = [max(0.0, float(value)) for value in models[target].predict(test_features)]
        elif decision == "HistGradientBoosting":
            model = HistGradientBoostingRegressor(
                max_iter=100,
                learning_rate=0.05,
                max_leaf_nodes=15,
                l2_regularization=1.0,
                random_state=seed,
            )
            model.fit(train_features, target_values(split["train"], target))
            prediction = [max(0.0, float(value)) for value in model.predict(test_features)]
        else:
            prediction = baseline_values(split["test"], target, decision)
        strongest_name = result["targets"][target]["strongest_baseline"]["name"]
        test_results[target] = {
            "selected": decision,
            "metrics": metrics(actual, prediction),
            "strongest_baseline": {
                "name": strongest_name,
                **metrics(actual, baseline_values(split["test"], target, strongest_name)),
            },
        }
    result["selected_forecasters"] = selected
    result["test"] = test_results
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
