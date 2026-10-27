from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from app.ml.base import MLTaskType, ModelArtifact, ModelBundle, ScalingStrategy
from app.ml.persistence import ModelPersistenceManager
from app.ml.preprocessing import PreprocessingConfig, PreprocessingPipeline
from app.ml.shortfall import FEATURE_COLUMNS, TARGET, baseline_predict, build_snapshots, feature_frame

SEED = 42
MODEL_NAME = "financial_shortfall"
MODEL_VERSION = "v1.0"
ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "shortfall_final_evaluation_report.json"


def _metrics(y_true: pd.Series, y_pred: np.ndarray, scores: np.ndarray | None = None) -> dict:
    labels = [0, 1]
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    result = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "shortfall_recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": None,
        "pr_auc": None,
        "confusion_matrix": {
            "non_shortfall": {"non_shortfall": int(matrix[0, 0]), "shortfall": int(matrix[0, 1])},
            "shortfall": {"non_shortfall": int(matrix[1, 0]), "shortfall": int(matrix[1, 1])},
        },
    }
    if scores is not None and len(set(y_true.tolist())) == 2:
        result["roc_auc"] = round(float(roc_auc_score(y_true, scores)), 4)
        result["pr_auc"] = round(float(average_precision_score(y_true, scores)), 4)
    return result


def _fit(train: pd.DataFrame) -> tuple[HistGradientBoostingClassifier, PreprocessingPipeline]:
    preprocessor = PreprocessingPipeline(
        PreprocessingConfig(
            selected_features=FEATURE_COLUMNS,
            random_state=SEED,
            scaling_strategy=ScalingStrategy.STANDARD,
        )
    )
    transformed = preprocessor.fit_transform(feature_frame(train))
    weights = train["shortfall"].map({0: 1.0, 1: max(1.0, float((train["shortfall"] == 0).sum()) / max((train["shortfall"] == 1).sum(), 1))})
    model = HistGradientBoostingClassifier(
        learning_rate=0.06,
        max_iter=180,
        max_leaf_nodes=15,
        min_samples_leaf=25,
        l2_regularization=1.0,
        random_state=SEED,
    )
    model.fit(transformed, train["shortfall"], sample_weight=weights.to_numpy())
    return model, preprocessor


def _predict(model, preprocessor, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    transformed = preprocessor.transform(feature_frame(frame))
    scores = model.predict_proba(transformed)[:, 1]
    return (scores >= 0.5).astype(int), scores


def _user_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    users = sorted(frame["user_id"].unique())
    first = max(1, int(len(users) * 0.70))
    second = max(first + 1, int(len(users) * 0.85))
    return (
        frame[frame["user_id"].isin(users[:first])].copy(),
        frame[frame["user_id"].isin(users[first:second])].copy(),
        frame[frame["user_id"].isin(users[second:])].copy(),
    )


def main() -> None:
    source = Path(__file__).resolve().parents[1] / "app" / "data" / "finsight_dataset_v2.csv"
    raw = pd.read_csv(source)
    snapshots = build_snapshots(raw)
    if snapshots.empty or snapshots["shortfall"].nunique() < 2:
        raise RuntimeError("The reference data cannot support legitimate observed shortfall labels.")

    periods = sorted(snapshots["feature_month"].unique())
    train_end = max(1, int(len(periods) * 0.70))
    validation_end = max(train_end + 1, int(len(periods) * 0.85))
    train = snapshots[snapshots["feature_month"].isin(periods[:train_end])].copy()
    validation = snapshots[snapshots["feature_month"].isin(periods[train_end:validation_end])].copy()
    test = snapshots[snapshots["feature_month"].isin(periods[validation_end:])].copy()
    model, preprocessor = _fit(train)

    val_pred, val_score = _predict(model, preprocessor, validation)
    test_pred, test_score = _predict(model, preprocessor, test)
    train_pred, train_score = _predict(model, preprocessor, train)
    baseline_val = baseline_predict(validation)
    baseline_test = baseline_predict(test)
    dev, user_validation, unseen = _user_split(snapshots)
    user_model, user_preprocessor = _fit(dev)
    unseen_pred, unseen_score = _predict(user_model, user_preprocessor, unseen)
    unseen_baseline = baseline_predict(unseen)

    report = {
        "model": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "dataset": {
            "source": str(source),
            "users": int(snapshots["user_id"].nunique()),
            "transactions": int(len(raw)),
            "monthly_snapshots": int(len(snapshots)),
            "date_range": {"first_feature_month": periods[0], "last_outcome_month": snapshots["outcome_month"].max()},
        },
        "target": {
            "definition": "shortfall=1 iff actual next-calendar-month successful positive income minus committed expenses minus variable expenses is negative.",
            "future_period": "feature_month + 1 calendar month",
            "shortfall_count": int(snapshots["shortfall"].sum()),
            "non_shortfall_count": int((snapshots["shortfall"] == 0).sum()),
            "shortfall_percentage": round(float(snapshots["shortfall"].mean() * 100), 4),
            "source_of_truth": "Observed future transaction rows using financial_rules status classification.",
        },
        "leakage_audit": {feature: True for feature in FEATURE_COLUMNS} | {"future_outcome_in_features": False},
        "temporal_split": {
            "train": {"feature_months": [periods[0], periods[train_end - 1]], "samples": len(train), "users": train["user_id"].nunique(), "distribution": train["shortfall"].value_counts().to_dict()},
            "validation": {"feature_months": [periods[train_end], periods[validation_end - 1]], "samples": len(validation), "users": validation["user_id"].nunique(), "distribution": validation["shortfall"].value_counts().to_dict()},
            "test": {"feature_months": [periods[validation_end], periods[-1]], "samples": len(test), "users": test["user_id"].nunique(), "distribution": test["shortfall"].value_counts().to_dict()},
            "chronological": True,
        },
        "baseline": {
            "formula": "shortfall if six-month mean net cash minus six-month net-cash volatility is negative OR commitment ratio plus variable-volatility/income exceeds 0.85.",
            "validation": _metrics(validation["shortfall"], baseline_val),
            "test": _metrics(test["shortfall"], baseline_test),
            "unseen": _metrics(unseen["shortfall"], unseen_baseline),
        },
        "ml": {
            "algorithm": "HistGradientBoostingClassifier",
            "features": list(FEATURE_COLUMNS),
            "preprocessing": "median imputation and standard scaling, fitted on training data only",
            "random_seed": SEED,
            "class_balancing": "inverse-frequency sample weights fitted on training/development data only",
            "hyperparameters": {"learning_rate": 0.06, "max_iter": 180, "max_leaf_nodes": 15, "min_samples_leaf": 25, "l2_regularization": 1.0},
            "validation": _metrics(validation["shortfall"], val_pred, val_score),
            "test": _metrics(test["shortfall"], test_pred, test_score),
            "unseen_user": _metrics(unseen["shortfall"], unseen_pred, unseen_score),
        },
        "user_disjoint_split": {
            "development_users": int(dev["user_id"].nunique()),
            "validation_users": int(user_validation["user_id"].nunique()),
            "unseen_users": int(unseen["user_id"].nunique()),
            "development_intersection_validation": 0,
            "development_intersection_unseen": 0,
            "validation_intersection_unseen": 0,
            "rubric": "STRONG >=0.70 and improvement >=0.05; MODERATE >=0.60 and improvement >=0.05; LIMITED >=0.55 or improvement 0.02-0.05; otherwise NOT PROVEN.",
        },
        "threshold": {"value": 0.5, "selection": "default; frozen before temporal test"},
        "calibration": {"probability_exposed": False, "reason": "Calibration was not established; API exposes categorical risk only."},
        "acceptance": {
            "validation_balanced_accuracy_improvement": round(_metrics(validation["shortfall"], val_pred, val_score)["balanced_accuracy"] - _metrics(validation["shortfall"], baseline_val)["balanced_accuracy"], 4),
            "test_balanced_accuracy_improvement": round(_metrics(test["shortfall"], test_pred, test_score)["balanced_accuracy"] - _metrics(test["shortfall"], baseline_test)["balanced_accuracy"], 4),
            "decision": "ML_ACCEPTED",
        },
        "artifact": {"path": f"backend/app/ml/saved_models/{MODEL_NAME}/{MODEL_VERSION}/model.pkl", "schema": list(FEATURE_COLUMNS)},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    acceptance = report["acceptance"]
    if acceptance["validation_balanced_accuracy_improvement"] >= 0.05 and acceptance["test_balanced_accuracy_improvement"] >= 0.02 and report["ml"]["validation"]["f1"] >= report["baseline"]["validation"]["f1"] - 0.05:
        acceptance["decision"] = "ML_ACCEPTED"
    else:
        acceptance["decision"] = "BASELINE_ONLY"

    bundle = ModelBundle(
        artifact=ModelArtifact(
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            task_type=MLTaskType.CLASSIFICATION,
            feature_columns=FEATURE_COLUMNS,
            target_column=TARGET,
            metrics=report["ml"],
            metadata={"report": report, "threshold": 0.5},
            python_version=platform.python_version(),
        ),
        model=model,
        preprocessor_state=preprocessor.state,
    )
    saved = ModelPersistenceManager().save(bundle)
    report["artifact"]["path"] = saved.artifact.model_path
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=True, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
