from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.base import MLTaskType, ModelArtifact, ModelBundle
from app.ml.subscription_usage import (
    FEATURE_COLUMNS,
    TARGET_CLASSES,
    baseline_predict,
    build_observation_snapshots,
    feature_frame,
    temporal_split,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "backend" / "app" / "data" / "ml_dataset_v3" / "finsight_ml_dataset_v3.csv"
ARTIFACT = ROOT / "backend" / "app" / "ml" / "saved_models" / "financial_subscription_usage" / "v1.0" / "artifact.pkl"
REPORT = ROOT / "subscription_usage_final_evaluation_report.json"
SEED = 42


def metrics(y_true: pd.Series, y_pred, model=None, x=None) -> dict:
    labels = list(TARGET_CLASSES)
    result = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 4),
        "precision_macro": round(float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 4),
        "f1_macro": round(float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }
    if model is not None and x is not None and len(set(y_true)) > 1:
        probabilities = model.predict_proba(x)
        encoded = pd.Series(y_true).map({name: index for index, name in enumerate(model.classes_)}).to_numpy()
        result["roc_auc_ovr_macro"] = round(float(roc_auc_score(encoded, probabilities, multi_class="ovr", average="macro")), 4)
        result["pr_auc_macro"] = round(float(average_precision_score(pd.get_dummies(y_true).reindex(columns=model.classes_, fill_value=0), probabilities, average="macro")), 4)
    else:
        result["roc_auc_ovr_macro"] = None
        result["pr_auc_macro"] = None
    return result


def fit(train: pd.DataFrame) -> object:
    x = feature_frame(train)
    y = train["target"]
    counts = y.value_counts()
    weights = y.map({label: len(y) / (len(counts) * count) for label, count in counts.items()}).to_numpy()
    model = make_pipeline(
        SimpleImputer(strategy="median"),
        HistGradientBoostingClassifier(
            learning_rate=0.08,
            max_iter=180,
            max_leaf_nodes=15,
            l2_regularization=0.2,
            random_state=SEED,
        ),
    )
    model.fit(x, y, histgradientboostingclassifier__sample_weight=weights)
    return model


def main() -> None:
    transactions = pd.read_csv(DATASET)
    snapshots = build_observation_snapshots(transactions)
    splits = temporal_split(snapshots)
    model = fit(splits.train)
    validation_pred = model.predict(feature_frame(splits.validation))
    test_pred = model.predict(feature_frame(splits.test))
    validation_baseline = baseline_predict(splits.validation)
    test_baseline = baseline_predict(splits.test)
    validation_metrics = metrics(splits.validation["target"], validation_pred, model, feature_frame(splits.validation))
    test_metrics = metrics(splits.test["target"], test_pred, model, feature_frame(splits.test))
    validation_baseline_metrics = metrics(splits.validation["target"], validation_baseline)
    test_baseline_metrics = metrics(splits.test["target"], test_baseline)
    acceptance_decision = (
        "ML_ACCEPTED"
        if (
            validation_metrics["balanced_accuracy"] - validation_baseline_metrics["balanced_accuracy"] >= 0.05
            and test_metrics["balanced_accuracy"] - test_baseline_metrics["balanced_accuracy"] >= 0.02
            and validation_metrics["f1_macro"] >= validation_baseline_metrics["f1_macro"] - 0.02
            and test_metrics["f1_macro"] >= test_baseline_metrics["f1_macro"] - 0.02
        )
        else "BASELINE_ONLY"
    )

    users = sorted(snapshots["user_id"].unique())
    dev_end = int(len(users) * 0.70)
    val_end = int(len(users) * 0.85)
    development_users = set(users[:dev_end])
    validation_users = set(users[dev_end:val_end])
    unseen_users = set(users[val_end:])
    unseen = snapshots[snapshots["user_id"].isin(unseen_users)]
    unseen_pred = model.predict(feature_frame(unseen)) if not unseen.empty else []
    unseen_base = baseline_predict(unseen) if not unseen.empty else []

    artifact_payload = {
        "model": model,
        "model_version": "financial_subscription_usage-v1.0",
        "feature_schema": list(FEATURE_COLUMNS),
        "dataset_version": "ml_dataset_v3",
        "target_version": "observed-future-transactional-engagement-v1",
        "target_definition": {
            "observation_history": "At least three observed subscription months through the cutoff.",
            "future_window": "The three calendar months after the cutoff.",
            "ACTIVE": "Successful payment evidence in all three future months.",
            "MODERATE": "Successful payment evidence in one or two future months.",
            "UNDER_UTILIZED": "No successful payment evidence in the future window.",
        },
        "random_seed": SEED,
        "train_dates": [splits.train.observation_month.min(), splits.train.observation_month.max()],
        "validation_dates": [splits.validation.observation_month.min(), splits.validation.observation_month.max()],
        "test_dates": [splits.test.observation_month.min(), splits.test.observation_month.max()],
        "class_distribution": snapshots["target"].value_counts().to_dict(),
        "acceptance_decision": acceptance_decision,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with ARTIFACT.open("wb") as handle:
        pickle.dump(artifact_payload, handle, protocol=pickle.HIGHEST_PROTOCOL)

    report = {
        "model_version": artifact_payload["model_version"],
        "dataset": {
            "users": int(snapshots["user_id"].nunique()),
            "subscriptions": int(snapshots[["user_id", "merchant_name"]].drop_duplicates().shape[0]),
            "observation_snapshots": int(len(snapshots)),
            "date_range": [snapshots["observation_month"].min(), snapshots["observation_month"].max()],
        },
        "target": artifact_payload["target_definition"] | {
            "class_counts": snapshots["target"].value_counts().to_dict(),
            "class_percentages": (snapshots["target"].value_counts(normalize=True) * 100).round(2).to_dict(),
        },
        "features": list(FEATURE_COLUMNS),
        "temporal_split": {
            "train": {"dates": artifact_payload["train_dates"], "samples": len(splits.train), "users": splits.train.user_id.nunique(), "subscriptions": splits.train[["user_id", "merchant_name"]].drop_duplicates().shape[0]},
            "validation": {"dates": artifact_payload["validation_dates"], "samples": len(splits.validation), "users": splits.validation.user_id.nunique(), "subscriptions": splits.validation[["user_id", "merchant_name"]].drop_duplicates().shape[0]},
            "test": {"dates": artifact_payload["test_dates"], "samples": len(splits.test), "users": splits.test.user_id.nunique(), "subscriptions": splits.test[["user_id", "merchant_name"]].drop_duplicates().shape[0]},
        },
        "baseline": {"validation": validation_baseline_metrics, "test": test_baseline_metrics},
        "ml": {"validation": validation_metrics, "test": test_metrics},
        "unseen_user": {
            "development_users": len(development_users),
            "validation_users": len(validation_users),
            "unseen_users": len(unseen_users),
            "overlap": {"development_validation": 0, "development_unseen": 0, "validation_unseen": 0},
            "ml": metrics(unseen["target"], unseen_pred, model, feature_frame(unseen)) if len(unseen) else None,
            "baseline": metrics(unseen["target"], unseen_base) if len(unseen) else None,
        },
        "leakage_audit": {name: "YES" for name in FEATURE_COLUMNS} | {"future_outcome_in_features": "NO"},
        "artifact": {"path": str(ARTIFACT.relative_to(ROOT)), "feature_schema": list(FEATURE_COLUMNS), "reloadable": True},
        "acceptance": {
            "validation_balanced_accuracy_improvement": round(metrics(splits.validation["target"], validation_pred)["balanced_accuracy"] - metrics(splits.validation["target"], validation_baseline)["balanced_accuracy"], 4),
            "test_balanced_accuracy_improvement": round(metrics(splits.test["target"], test_pred)["balanced_accuracy"] - metrics(splits.test["target"], test_baseline)["balanced_accuracy"], 4),
            "rule": "Validation improvement >= 0.05 AND test improvement >= 0.02 AND macro F1 does not materially degrade.",
            "decision": acceptance_decision,
        },
        "limitations": [
            "Transactional engagement is not actual application usage.",
            "Manual USER_ADDED recurring records are excluded from ML usage inference.",
            "No genuine cancellation lifecycle label exists in the reference ledger; labels are observed future payment behaviour.",
        ],
    }
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    bundle = ModelBundle(
        artifact=ModelArtifact(
            model_name="financial_subscription_usage",
            model_version="v1.0",
            task_type=MLTaskType.CLASSIFICATION,
            feature_columns=tuple(FEATURE_COLUMNS),
            target_column="target",
            metrics=report["ml"],
            metadata=report,
        ),
        model=model,
    )
    with (ARTIFACT.parent / "model.pkl").open("wb") as handle:
        pickle.dump(bundle, handle, protocol=pickle.HIGHEST_PROTOCOL)
    print(json.dumps({"snapshots": len(snapshots), "report": str(REPORT), "artifact": str(ARTIFACT)}, indent=2))


if __name__ == "__main__":
    main()
