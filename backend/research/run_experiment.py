"""FinSight Controlled Model A vs Model B Research Experiment Runner.

Executes a controlled, reproducible scientific comparison between:
- Model A: 27 conventional financial features
- Model B: 41 features (27 baseline + 14 commitment-aware features)

Includes:
1. Strict chronological partitions (Train: 2,463, Val: 559, Test: 422).
2. Train-only preprocessing and class-weight fitting.
3. Untouched test evaluation across 8 standard metrics.
4. Paired user-clustered bootstrap analysis (B=1,000) for differences and 95% CIs.
5. Calibration analysis, threshold sensitivity, and feature group ablations.
6. Export of machine-readable artifacts and test predictions.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

# Set temporary database URL to allow backend imports without PostgreSQL
os.environ.setdefault("DATABASE_URL", "sqlite://")

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.base import ScalingStrategy
from app.ml.preprocessing import PreprocessingConfig, PreprocessingPipeline
from research.pipeline import (
    COMMITMENT_FEATURES,
    MODEL_A_FEATURES,
    MODEL_B_FEATURES,
    TARGET,
    build_research_snapshots,
    temporal_split,
)

SEED = 42
BOOTSTRAP_ROUNDS = 1000
ARTIFACTS_DIR = CURRENT_DIR / "artifacts" / "phase2_controlled_experiment"


def compute_sha256(filepath: Path) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict[str, Any]:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0

    return {
        "average_precision": float(round(average_precision_score(y_true, y_prob), 4)),
        "roc_auc": float(round(roc_auc_score(y_true, y_prob), 4)),
        "balanced_accuracy": float(round(balanced_accuracy_score(y_true, y_pred), 4)),
        "accuracy": float(round(accuracy_score(y_true, y_pred), 4)),
        "precision": float(round(precision_score(y_true, y_pred, zero_division=0), 4)),
        "recall": float(round(recall_score(y_true, y_pred, zero_division=0), 4)),
        "f1": float(round(f1_score(y_true, y_pred, zero_division=0), 4)),
        "brier_score": float(round(brier_score_loss(y_true, y_prob), 4)),
        "specificity": float(round(spec, 4)),
        "npv": float(round(npv, 4)),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }


def fit_model(
    train_df: pd.DataFrame,
    features: tuple[str, ...],
) -> tuple[HistGradientBoostingClassifier, PreprocessingPipeline]:
    preprocessor = PreprocessingPipeline(
        PreprocessingConfig(
            selected_features=list(features),
            random_state=SEED,
            scaling_strategy=ScalingStrategy.STANDARD,
        )
    )
    X_train_raw = train_df[list(features)].astype(float)
    X_train_trans = preprocessor.fit_transform(X_train_raw)

    y_train = train_df[TARGET].to_numpy()
    neg_count = (y_train == 0).sum()
    pos_count = (y_train == 1).sum()
    pos_weight = max(1.0, float(neg_count) / max(pos_count, 1))
    weights = np.where(y_train == 1, pos_weight, 1.0)

    model = HistGradientBoostingClassifier(
        learning_rate=0.06,
        max_iter=180,
        max_leaf_nodes=15,
        min_samples_leaf=25,
        l2_regularization=1.0,
        random_state=SEED,
    )
    model.fit(X_train_trans, y_train, sample_weight=weights)
    return model, preprocessor


def predict(
    model: HistGradientBoostingClassifier,
    preprocessor: PreprocessingPipeline,
    df: pd.DataFrame,
    features: tuple[str, ...],
    threshold: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    X_raw = df[list(features)].astype(float)
    X_trans = preprocessor.transform(X_raw)
    probs = model.predict_proba(X_trans)[:, 1]
    preds = (probs >= threshold).astype(int)
    return preds, probs


def run_paired_bootstrap(
    test_df: pd.DataFrame,
    y_true: np.ndarray,
    probs_a: np.ndarray,
    preds_a: np.ndarray,
    probs_b: np.ndarray,
    preds_b: np.ndarray,
    n_replicates: int = BOOTSTRAP_ROUNDS,
    seed: int = SEED,
) -> dict[str, Any]:
    rng = np.random.RandomState(seed)
    unique_users = test_df["user_id"].unique()
    n_users = len(unique_users)

    # Pre-index user row locations
    user_indices = {u: np.where(test_df["user_id"].to_numpy() == u)[0] for u in unique_users}

    diff_ap: list[float] = []
    diff_roc: list[float] = []
    diff_balacc: list[float] = []
    diff_f1: list[float] = []
    diff_brier: list[float] = []

    valid_replicates = 0
    for _ in range(n_replicates):
        resampled_users = rng.choice(unique_users, size=n_users, replace=True)
        idx_list = [user_indices[u] for u in resampled_users]
        idx = np.concatenate(idx_list)

        y_boot = y_true[idx]
        if len(np.unique(y_boot)) < 2:
            continue

        p_a = probs_a[idx]
        c_a = preds_a[idx]
        p_b = probs_b[idx]
        c_b = preds_b[idx]

        ap_a = average_precision_score(y_boot, p_a)
        ap_b = average_precision_score(y_boot, p_b)
        roc_a = roc_auc_score(y_boot, p_a)
        roc_b = roc_auc_score(y_boot, p_b)
        bal_a = balanced_accuracy_score(y_boot, c_a)
        bal_b = balanced_accuracy_score(y_boot, c_b)
        f1_a = f1_score(y_boot, c_a, zero_division=0)
        f1_b = f1_score(y_boot, c_b, zero_division=0)
        br_a = brier_score_loss(y_boot, p_a)
        br_b = brier_score_loss(y_boot, p_b)

        diff_ap.append(float(ap_b - ap_a))
        diff_roc.append(float(roc_b - roc_a))
        diff_balacc.append(float(bal_b - bal_a))
        diff_f1.append(float(f1_b - f1_a))
        diff_brier.append(float(br_b - br_a))
        valid_replicates += 1

    def _ci(arr: list[float]) -> dict[str, float]:
        a = np.array(arr)
        return {
            "mean": float(round(float(np.mean(a)), 4)),
            "std": float(round(float(np.std(a)), 4)),
            "ci_lower_2_5": float(round(float(np.percentile(a, 2.5)), 4)),
            "ci_upper_97_5": float(round(float(np.percentile(a, 97.5)), 4)),
            "fraction_positive": float(round(float((a > 0).mean()), 4)),
        }

    return {
        "bootstrap_replicates_requested": n_replicates,
        "bootstrap_replicates_valid": valid_replicates,
        "resampling_unit": "user_id (clustered)",
        "differences": {
            "delta_average_precision": _ci(diff_ap),
            "delta_roc_auc": _ci(diff_roc),
            "delta_balanced_accuracy": _ci(diff_balacc),
            "delta_f1": _ci(diff_f1),
            "delta_brier_score": _ci(diff_brier),
        },
    }


def compute_calibration_curve(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> list[dict[str, Any]]:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins) - 1
    curve = []
    for b in range(n_bins):
        mask = bin_indices == b
        count = int(np.sum(mask))
        if count > 0:
            curve.append(
                {
                    "bin": b,
                    "bin_range": [round(float(bins[b]), 2), round(float(bins[b + 1]), 2)],
                    "count": count,
                    "mean_pred_prob": round(float(np.mean(y_prob[mask])), 4),
                    "empirical_positive_rate": round(float(np.mean(y_true[mask])), 4),
                }
            )
        else:
            curve.append(
                {
                    "bin": b,
                    "bin_range": [round(float(bins[b]), 2), round(float(bins[b + 1]), 2)],
                    "count": 0,
                    "mean_pred_prob": round(float((bins[b] + bins[b + 1]) / 2), 4),
                    "empirical_positive_rate": None,
                }
            )
    return curve


def evaluate_threshold_sensitivity(
    y_true: np.ndarray,
    probs: np.ndarray,
    thresholds: list[float] | None = None,
) -> list[dict[str, Any]]:
    if thresholds is None:
        thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    res = []
    for t in thresholds:
        preds = (probs >= t).astype(int)
        res.append(
            {
                "threshold": round(t, 2),
                "balanced_accuracy": round(float(balanced_accuracy_score(y_true, preds)), 4),
                "precision": round(float(precision_score(y_true, preds, zero_division=0)), 4),
                "recall": round(float(recall_score(y_true, preds, zero_division=0)), 4),
                "f1": round(float(f1_score(y_true, preds, zero_division=0)), 4),
            }
        )
    return res


def run_experiment() -> dict[str, Any]:
    dataset_path = BACKEND_DIR / "app" / "data" / "finsight_dataset_v2.csv"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found at: {dataset_path}")

    dataset_hash = compute_sha256(dataset_path)
    raw_df = pd.read_csv(dataset_path)

    print(f"Building research snapshots from {dataset_path.name}...")
    snapshots = build_research_snapshots(raw_df)
    splits = temporal_split(snapshots)

    train = splits.train
    val = splits.validation
    test = splits.test

    print(f"Snapshots: {len(snapshots)} | Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")

    # 1. Fit Model A and Model B
    print("Fitting Model A (27 features)...")
    model_a, prep_a = fit_model(train, MODEL_A_FEATURES)

    print("Fitting Model B (41 features)...")
    model_b, prep_b = fit_model(train, MODEL_B_FEATURES)

    # 2. Validation evaluation (threshold search)
    val_preds_a, val_probs_a = predict(model_a, prep_a, val, MODEL_A_FEATURES, threshold=0.5)
    val_preds_b, val_probs_b = predict(model_b, prep_b, val, MODEL_B_FEATURES, threshold=0.5)

    y_val = val[TARGET].to_numpy()
    val_metrics_a = compute_metrics(y_val, val_preds_a, val_probs_a)
    val_metrics_b = compute_metrics(y_val, val_preds_b, val_probs_b)

    # 3. Test evaluation (untouched test set, N=422)
    y_test = test[TARGET].to_numpy()
    test_preds_a, test_probs_a = predict(model_a, prep_a, test, MODEL_A_FEATURES, threshold=0.5)
    test_preds_b, test_probs_b = predict(model_b, prep_b, test, MODEL_B_FEATURES, threshold=0.5)

    test_metrics_a = compute_metrics(y_test, test_preds_a, test_probs_a)
    test_metrics_b = compute_metrics(y_test, test_preds_b, test_probs_b)

    # Compute metric deltas: Model B - Model A
    deltas = {
        "delta_average_precision": round(test_metrics_b["average_precision"] - test_metrics_a["average_precision"], 4),
        "delta_roc_auc": round(test_metrics_b["roc_auc"] - test_metrics_a["roc_auc"], 4),
        "delta_balanced_accuracy": round(test_metrics_b["balanced_accuracy"] - test_metrics_a["balanced_accuracy"], 4),
        "delta_accuracy": round(test_metrics_b["accuracy"] - test_metrics_a["accuracy"], 4),
        "delta_precision": round(test_metrics_b["precision"] - test_metrics_a["precision"], 4),
        "delta_recall": round(test_metrics_b["recall"] - test_metrics_a["recall"], 4),
        "delta_f1": round(test_metrics_b["f1"] - test_metrics_a["f1"], 4),
        "delta_brier_score": round(test_metrics_b["brier_score"] - test_metrics_a["brier_score"], 4),
        "delta_specificity": round(test_metrics_b["specificity"] - test_metrics_a["specificity"], 4),
        "delta_npv": round(test_metrics_b["npv"] - test_metrics_a["npv"], 4),
    }

    # 4. Paired user-clustered bootstrap analysis
    print(f"Running paired user-clustered bootstrap ({BOOTSTRAP_ROUNDS} replicates)...")
    bootstrap_results = run_paired_bootstrap(
        test_df=test,
        y_true=y_test,
        probs_a=test_probs_a,
        preds_a=test_preds_a,
        probs_b=test_probs_b,
        preds_b=test_preds_b,
        n_replicates=BOOTSTRAP_ROUNDS,
        seed=SEED,
    )

    # 5. Robustness & Diagnostics: Calibration & Thresholds
    cal_a = compute_calibration_curve(y_test, test_probs_a)
    cal_b = compute_calibration_curve(y_test, test_probs_b)
    thresh_a = evaluate_threshold_sensitivity(y_test, test_probs_a)
    thresh_b = evaluate_threshold_sensitivity(y_test, test_probs_b)

    # 6. Feature Ablation Analysis
    print("Running commitment feature group ablations...")
    ablation_groups = {
        "A_baseline_27": MODEL_A_FEATURES,
        "A_plus_commit_history_ratios": MODEL_A_FEATURES + (
            "previous_committed",
            "committed_3m",
            "committed_6m",
            "commitment_ratio",
            "commitment_count",
            "commitment_growth",
        ),
        "A_plus_commit_burdens_diversity": MODEL_A_FEATURES + (
            "subscription_burden",
            "emi_burden",
            "bnpl_burden",
            "recurring_payment_burden",
            "commitment_diversity",
        ),
        "A_plus_commit_projections": MODEL_A_FEATURES + (
            "expected_committed_expenses",
            "expected_total_expenses",
            "expected_net_cash",
        ),
        "B_all_41": MODEL_B_FEATURES,
    }
    ablation_results = {}
    for grp_name, grp_feats in ablation_groups.items():
        m_grp, p_grp = fit_model(train, grp_feats)
        preds_grp, probs_grp = predict(m_grp, p_grp, test, grp_feats)
        met = compute_metrics(y_test, preds_grp, probs_grp)
        ablation_results[grp_name] = {
            "feature_count": len(grp_feats),
            "average_precision": met["average_precision"],
            "roc_auc": met["roc_auc"],
            "balanced_accuracy": met["balanced_accuracy"],
            "f1": met["f1"],
            "brier_score": met["brier_score"],
        }

    # 7. Permutation feature importance on test set
    print("Computing permutation feature importance on test set...")
    X_test_b = prep_b.transform(test[list(MODEL_B_FEATURES)].astype(float))
    perm_b = permutation_importance(model_b, X_test_b, y_test, n_repeats=5, random_state=SEED, scoring="average_precision")
    importances_b = [
        {"feature": feat, "importance_mean": round(float(perm_b.importances_mean[i]), 5), "importance_std": round(float(perm_b.importances_std[i]), 5)}
        for i, feat in enumerate(MODEL_B_FEATURES)
    ]
    importances_b = sorted(importances_b, key=lambda x: x["importance_mean"], reverse=True)

    # 8. Save artifacts
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # Save test predictions table
    predictions_df = pd.DataFrame(
        {
            "user_id": test["user_id"].to_numpy(),
            "feature_month": test["feature_month"].to_numpy(),
            "outcome_month": test["outcome_month"].to_numpy(),
            "y_true": y_test,
            "model_a_prob": np.round(test_probs_a, 5),
            "model_a_pred": test_preds_a,
            "model_b_prob": np.round(test_probs_b, 5),
            "model_b_pred": test_preds_b,
        }
    )
    predictions_path = ARTIFACTS_DIR / "test_predictions.csv"
    predictions_df.to_csv(predictions_path, index=False)

    # Save full metrics comparison
    comparison_payload = {
        "experiment_name": "Phase 2 Controlled Shortfall Model A vs Model B Comparison",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_hash_sha256": dataset_hash,
        "sample_counts": {
            "total_snapshots": len(snapshots),
            "train": len(train),
            "validation": len(val),
            "test": len(test),
            "unique_users_total": int(snapshots["user_id"].nunique()),
            "unique_users_test": int(test["user_id"].nunique()),
            "test_positive_shortfall": int((y_test == 1).sum()),
            "test_negative_non_shortfall": int((y_test == 0).sum()),
        },
        "model_a": {
            "name": "Model A (Conventional Financial Features Baseline)",
            "feature_count": len(MODEL_A_FEATURES),
            "validation_metrics": val_metrics_a,
            "test_metrics": test_metrics_a,
        },
        "model_b": {
            "name": "Model B (Commitment-Aware Model)",
            "feature_count": len(MODEL_B_FEATURES),
            "validation_metrics": val_metrics_b,
            "test_metrics": test_metrics_b,
        },
        "metric_differences_test": deltas,
        "bootstrap_paired_test": bootstrap_results,
    }
    metrics_path = ARTIFACTS_DIR / "metrics_comparison.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(comparison_payload, f, indent=2)

    # Save experiment configuration
    config_payload = {
        "dataset_path": str(dataset_path),
        "dataset_sha256": dataset_hash,
        "random_seed": SEED,
        "model_class": "sklearn.ensemble.HistGradientBoostingClassifier",
        "hyperparameters": {
            "learning_rate": 0.06,
            "max_iter": 180,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 25,
            "l2_regularization": 1.0,
            "random_state": SEED,
        },
        "preprocessing": "StandardScaler with SimpleImputer(strategy='median'), fitted on train partition only",
        "sample_weighting": "Inverse class frequency for positive instances on train partition only",
        "partitions": {
            "train_periods": sorted(train["feature_month"].unique().tolist()),
            "val_periods": sorted(val["feature_month"].unique().tolist()),
            "test_periods": sorted(test["feature_month"].unique().tolist()),
        },
        "feature_specifications": {
            "model_a_features_27": list(MODEL_A_FEATURES),
            "commitment_features_14": list(COMMITMENT_FEATURES),
            "model_b_features_41": list(MODEL_B_FEATURES),
            "excluded_redundant_aliases_4": [
                "total_monthly_commitments",
                "active_recurring_count",
                "commitment_burden",
                "commitment_change",
            ],
        },
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "pandas_version": pd.__version__,
            "numpy_version": np.__version__,
        },
    }
    config_path = ARTIFACTS_DIR / "experiment_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_payload, f, indent=2)

    # Save calibration & threshold diagnostics
    with open(ARTIFACTS_DIR / "calibration_diagnostics.json", "w", encoding="utf-8") as f:
        json.dump({"calibration_model_a": cal_a, "calibration_model_b": cal_b}, f, indent=2)

    with open(ARTIFACTS_DIR / "threshold_sensitivity.json", "w", encoding="utf-8") as f:
        json.dump({"threshold_sensitivity_model_a": thresh_a, "threshold_sensitivity_model_b": thresh_b}, f, indent=2)

    with open(ARTIFACTS_DIR / "ablation_results.json", "w", encoding="utf-8") as f:
        json.dump({"ablation_results": ablation_results, "permutation_importances_model_b": importances_b[:15]}, f, indent=2)

    # Save markdown summary
    summary_path = ARTIFACTS_DIR / "run_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# FinSight Phase 2 Controlled Experiment Run Summary\n\n")
        f.write(f"**Date (UTC):** {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"**Dataset SHA-256:** `{dataset_hash}`\n\n")
        f.write("## 1. Test Performance Comparison (N=422 untouched snapshots)\n\n")
        f.write("| Metric | Model A (27 Baseline) | Model B (41 Commitment-Aware) | Difference (B - A) | 95% Bootstrap CI (Paired) |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: |\n")
        f.write(f"| **Average Precision** | {test_metrics_a['average_precision']:.4f} | {test_metrics_b['average_precision']:.4f} | {deltas['delta_average_precision']:+.4f} | [{bootstrap_results['differences']['delta_average_precision']['ci_lower_2_5']:+.4f}, {bootstrap_results['differences']['delta_average_precision']['ci_upper_97_5']:+.4f}] |\n")
        f.write(f"| **ROC-AUC** | {test_metrics_a['roc_auc']:.4f} | {test_metrics_b['roc_auc']:.4f} | {deltas['delta_roc_auc']:+.4f} | [{bootstrap_results['differences']['delta_roc_auc']['ci_lower_2_5']:+.4f}, {bootstrap_results['differences']['delta_roc_auc']['ci_upper_97_5']:+.4f}] |\n")
        f.write(f"| **Balanced Accuracy** | {test_metrics_a['balanced_accuracy']*100:.2f}% | {test_metrics_b['balanced_accuracy']*100:.2f}% | {deltas['delta_balanced_accuracy']*100:+.2f}% | [{bootstrap_results['differences']['delta_balanced_accuracy']['ci_lower_2_5']*100:+.2f}%, {bootstrap_results['differences']['delta_balanced_accuracy']['ci_upper_97_5']*100:+.2f}%] |\n")
        f.write(f"| **F1 Score** | {test_metrics_a['f1']*100:.2f}% | {test_metrics_b['f1']*100:.2f}% | {deltas['delta_f1']*100:+.2f}% | [{bootstrap_results['differences']['delta_f1']['ci_lower_2_5']*100:+.2f}%, {bootstrap_results['differences']['delta_f1']['ci_upper_97_5']*100:+.2f}%] |\n")
        f.write(f"| **Brier Score** | {test_metrics_a['brier_score']:.4f} | {test_metrics_b['brier_score']:.4f} | {deltas['delta_brier_score']:+.4f} | [{bootstrap_results['differences']['delta_brier_score']['ci_lower_2_5']:+.4f}, {bootstrap_results['differences']['delta_brier_score']['ci_upper_97_5']:+.4f}] |\n\n")

    print(f"Phase 2 experiment completed successfully! Artifacts written to: {ARTIFACTS_DIR}")
    return comparison_payload


if __name__ == "__main__":
    run_experiment()
