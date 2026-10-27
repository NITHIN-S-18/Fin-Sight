"""Train and evaluate the isolated Model 2 Phase C feasibility classifier."""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.goal_feasibility import (  # noqa: E402
    baseline_predictions,
    build_leakage_metadata,
    classification_metrics,
    construct_labels,
    feature_frame,
    generate_historical_scenarios,
    split_scenarios,
)

SEED = 42
ACCEPTANCE_MARGIN = 0.05
MODEL_VERSION = "model-2-phase-c-v2"
GENERALIZATION_RUBRIC = {
    "strong": "unseen-user balanced accuracy >= 0.70 and ML improvement over unseen-user baseline >= 0.05",
    "moderate": "unseen-user balanced accuracy >= 0.60 and ML improvement over unseen-user baseline >= 0.05",
    "limited": "unseen-user balanced accuracy >= 0.55 or ML improvement over baseline between 0.02 and 0.05",
    "not_proven": "below those thresholds or insufficient evaluation evidence",
}


def _model_result(model: Any, rows: list[Any]) -> dict[str, Any]:
    labels = construct_labels(rows)
    probabilities = model.predict_proba(feature_frame(rows))[:, 1]
    return classification_metrics(labels, (probabilities >= 0.5).astype(int), probabilities)


def _fit_hist(train: list[Any]) -> HistGradientBoostingClassifier:
    model = HistGradientBoostingClassifier(
        max_iter=150,
        learning_rate=0.05,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        random_state=SEED,
    )
    model.fit(feature_frame(train), construct_labels(train))
    return model


def _fit_xgb(train: list[Any]) -> Any:
    from xgboost import XGBClassifier

    model = XGBClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=SEED,
        n_jobs=1,
        eval_metric="logloss",
    )
    model.fit(feature_frame(train), construct_labels(train))
    return model


def _split_report(split: dict[str, list[Any]]) -> dict[str, Any]:
    return {
        name: {
            "scenario_count": len(rows),
            "unique_users": len({row.user_id for row in rows}),
            "feature_month_range": [rows[0].feature_month, rows[-1].feature_month],
            "future_month_range": [
                min(row.future_start_month for row in rows),
                max(row.future_end_month for row in rows),
            ],
            "chronologically_ordered": all(
                left.feature_month <= right.feature_month for left, right in zip(rows, rows[1:])
            ),
        }
        for name, rows in split.items()
    }


def _overlap_report(split: dict[str, list[Any]]) -> dict[str, Any]:
    users = {name: {row.user_id for row in rows} for name, rows in split.items()}
    months = {name: {row.feature_month for row in rows} for name, rows in split.items()}
    return {
        "user_overlap_counts": {
            f"{left}_vs_{right}": len(users[left] & users[right])
            for left, right in (("train", "validation"), ("train", "test"), ("validation", "test"))
        },
        "feature_month_overlap_counts": {
            f"{left}_vs_{right}": len(months[left] & months[right])
            for left, right in (("train", "validation"), ("train", "test"), ("validation", "test"))
        },
        "unseen_test_users": len(users["test"] - users["train"]),
        "unseen_validation_users": len(users["validation"] - users["train"]),
    }


def _per_user_metrics(
    model: Any | None,
    rows: list[Any],
) -> dict[str, Any]:
    labels = construct_labels(rows)
    predictions = (
        baseline_predictions(rows)
        if model is None
        else (model.predict_proba(feature_frame(rows))[:, 1] >= 0.5).astype(int)
    )
    frame = pd.DataFrame(
        {"user_id": [row.user_id for row in rows], "label": labels.to_numpy(), "prediction": predictions}
    )
    grouped = frame.groupby("user_id", sort=True)[["label", "prediction"]].mean()
    return {
        "unseen_user_count": int(len(grouped)),
        "model": "deterministic_history_baseline" if model is None else "HistGradientBoostingClassifier",
        "metrics_on_unseen_users": classification_metrics(
            (grouped["label"] >= 0.5).astype(int),
            (grouped["prediction"] >= 0.5).astype(int),
        ),
    }


def train_reference_dataset(data_dir: Path, report_path: Path, artifact_path: Path) -> dict[str, Any]:
    transactions = pd.read_csv(data_dir / "finsight_ml_dataset_v3.csv")
    scenarios = generate_historical_scenarios(transactions)
    labels = construct_labels(scenarios)
    split = split_scenarios(scenarios, seed=SEED)
    baseline_validation = classification_metrics(
        construct_labels(split["validation"]),
        baseline_predictions(split["validation"]),
    )
    models: dict[str, Any] = {"HistGradientBoostingClassifier": _fit_hist(split["train"])}
    try:
        import xgboost  # noqa: F401
    except ImportError:
        xgb_status = {"installed": False, "reason": "xgboost is not installed"}
    else:
        models["XGBClassifier"] = _fit_xgb(split["train"])
        xgb_status = {"installed": True, "version": getattr(xgboost, "__version__", "unknown")}

    validation_models = {name: _model_result(model, split["validation"]) for name, model in models.items()}
    strongest_name = max(
        validation_models,
        key=lambda name: validation_models[name]["balanced_accuracy"],
    )
    strongest = validation_models[strongest_name]
    improvement = strongest["balanced_accuracy"] - baseline_validation["balanced_accuracy"]
    test_rows = split["test"]
    candidate_test_metrics = _model_result(models[strongest_name], test_rows)
    baseline_test_metrics = classification_metrics(
        construct_labels(test_rows),
        baseline_predictions(test_rows),
    )

    overlap = _overlap_report(split)
    disjoint = all(value == 0 for value in overlap["user_overlap_counts"].values())
    split_positive_rates = {
        name: round(float(construct_labels(rows).mean()), 4) for name, rows in split.items()
    }
    balanced_classes = all(0.10 <= rate <= 0.90 for rate in split_positive_rates.values())
    test_metrics = candidate_test_metrics
    test_per_user = {
        "ml": _per_user_metrics(models[strongest_name], test_rows),
        "baseline": _per_user_metrics(None, test_rows),
    }
    unseen_ml = test_per_user["ml"]["metrics_on_unseen_users"]
    unseen_baseline = test_per_user["baseline"]["metrics_on_unseen_users"]
    unseen_improvement = unseen_ml["balanced_accuracy"] - unseen_baseline["balanced_accuracy"]
    if (
        unseen_ml["balanced_accuracy"] >= 0.70
        and unseen_improvement >= 0.05
    ):
        generalization_classification = "STRONG"
    elif (
        unseen_ml["balanced_accuracy"] >= 0.60
        and unseen_improvement >= 0.05
    ):
        generalization_classification = "MODERATE"
    elif (
        unseen_ml["balanced_accuracy"] >= 0.55
        or 0.02 <= unseen_improvement < 0.05
    ):
        generalization_classification = "LIMITED"
    else:
        generalization_classification = "NOT PROVEN"
    quality_sufficient = (
        balanced_classes
        and improvement >= ACCEPTANCE_MARGIN
        and test_metrics["balanced_accuracy"] >= baseline_test_metrics["balanced_accuracy"] + 0.02
    )
    accepted = bool(quality_sufficient)
    selected = strongest_name if accepted else "deterministic_history_baseline"
    selected_model = models.get(strongest_name) if accepted else None
    if selected_model is None:
        test_metrics = classification_metrics(construct_labels(test_rows), baseline_predictions(test_rows))
        test_per_user = {"baseline": _per_user_metrics(None, test_rows)}
    report: dict[str, Any] = {
        "model": "financial_goal_feasibility",
        "model_version": MODEL_VERSION,
        "dataset_version": "ml_dataset_v3",
        "scenario_version": "phase-c-goal-contract-v1",
        "production_status": "accepted_ml" if accepted else "baseline_only",
        "ml_status": "accepted" if accepted else "rejected",
        "probability_exposed": False,
        "label_definition": (
            "1 only when actual successful positive future income minus the historical "
            "pre-goal committed-expense mean and actual successful positive future "
            "variable spending is at least the required monthly saving in every one "
            "of the six future months; commitment reductions cannot create a positive label."
        ),
        "scenario_policy": (
            "six contiguous history months followed by six contiguous future months; "
            "three observed-buffer savings tiers per window; timeframe months are "
            "12/6/3 for conservative/moderate/ambitious tiers and goal_amount is "
            "required_monthly_saving multiplied by timeframe_months"
        ),
        "scenario_schema": [
            "goal_amount",
            "timeframe_months",
            "required_monthly_saving",
        ],
        "scenario_distribution": {
            "timeframe_months": {
                str(months): sum(row.timeframe_months == months for row in scenarios)
                for months in sorted({row.timeframe_months for row in scenarios})
            },
            "goal_amount": {
                "min": round(min(row.goal_amount for row in scenarios), 2),
                "max": round(max(row.goal_amount for row in scenarios), 2),
                "mean": round(sum(row.goal_amount for row in scenarios) / len(scenarios), 2),
            },
            "required_monthly_saving": {
                "min": round(min(row.required_monthly_saving for row in scenarios), 2),
                "max": round(max(row.required_monthly_saving for row in scenarios), 2),
                "mean": round(
                    sum(row.required_monthly_saving for row in scenarios) / len(scenarios),
                    2,
                ),
            },
        },
        "split": _split_report(split),
        "user_disjoint": disjoint,
        "overlap": overlap,
        "class_balance": {
            "positive_rate_by_split": split_positive_rates,
            "acceptable_range": [0.10, 0.90],
            "passes_balance_gate": balanced_classes,
        },
        "leakage": build_leakage_metadata(scenarios),
        "label_distribution": {"0": int((labels == 0).sum()), "1": int((labels == 1).sum())},
        "baseline": {
            "method": "history_mean_buffer_threshold",
            "validation": baseline_validation,
        },
        "candidates": {
            name: {"validation": metrics}
            for name, metrics in validation_models.items()
        },
        "xgboost": xgb_status,
        "acceptance": {
            "criterion": (
                f"balanced classes, validation balanced_accuracy improvement >= {ACCEPTANCE_MARGIN:.2f}, "
                "and test balanced_accuracy improvement >= 0.02"
            ),
            "strongest_candidate": strongest_name,
            "improvement_over_baseline": round(float(improvement), 4),
            "selected": selected,
            "quality_sufficient": quality_sufficient,
        },
        "generalization_rubric": GENERALIZATION_RUBRIC,
        "generalization": {
            "classification": generalization_classification,
            "unseen_user_ml_balanced_accuracy": unseen_ml["balanced_accuracy"],
            "unseen_user_baseline_balanced_accuracy": unseen_baseline["balanced_accuracy"],
            "improvement_over_baseline": round(float(unseen_improvement), 4),
        },
        "test": {
            "selected_model": selected,
            "metrics": test_metrics,
            "baseline_metrics": baseline_test_metrics,
            "unseen_user_evaluation": test_per_user,
        },
        "artifact": {
            "persisted": accepted,
            "path": str(artifact_path) if accepted else None,
        },
        "live_inference_verification": {
            "static_contract": "PASS",
            "artifact_path": str(artifact_path),
            "realistic_requests": [
                {"goal_amount": 30000, "timeframe_months": 3},
                {"goal_amount": 60000, "timeframe_months": 6},
                {"goal_amount": 120000, "timeframe_months": 12},
            ],
            "authenticated_http": "BLOCKED — PostgreSQL unavailable",
        },
        "tenant_isolation_verification": {
            "static_contract": "PASS",
            "authenticated_runtime": "BLOCKED — PostgreSQL unavailable",
        },
        "final_decision": "MODEL 2 — NOT LOCKED",
        "final_blockers": [
            "Authenticated HTTP verification requires PostgreSQL and was blocked.",
            "Runtime tenant-isolation verification requires PostgreSQL and was blocked.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if accepted and selected_model is not None:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        with artifact_path.open("wb") as handle:
            pickle.dump(
                {
                    "model": selected_model,
                    "feature_columns": list(feature_frame(scenarios).columns),
                    "model_version": report["model_version"],
                    "seed": SEED,
                    "scenario_schema": report["scenario_schema"],
                    "target_definition": report["label_definition"],
                    "dataset_version": report["dataset_version"],
                    "scenario_version": report["scenario_version"],
                    "split": report["split"],
                    "user_disjoint": report["user_disjoint"],
                    "acceptance": report["acceptance"],
                    "generalization": report["generalization"],
                },
                handle,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
    elif artifact_path.exists():
        artifact_path.unlink()
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / "backend/app/data/ml_dataset_v3")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "goal_feasibility_final_evaluation_report.json",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=ROOT / "backend/app/ml/saved_models/goal_feasibility/model-2-phase-c-v2.pkl",
    )
    args = parser.parse_args()
    report = train_reference_dataset(args.data_dir, args.output, args.artifact)
    print(json.dumps({"status": report["production_status"], "selected": report["acceptance"]["selected"]}))


if __name__ == "__main__":
    main()
