from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

import pandas as pd

from app.services.financial_rules import classify_transaction_status, TransactionStatus
from app.ml.evaluation import evaluate_regression
from app.ml.base import MLTaskType, ModelArtifact, ModelBundle
from app.ml.persistence import ModelPersistenceManager
from app.ml.preprocessing import PreprocessingConfig, PreprocessingPipeline
from app.ml.base import ScalingStrategy
from app.ml.config import get_ml_config
from sklearn.ensemble import HistGradientBoostingRegressor


@dataclass(frozen=True)
class CashFlowExample:
    user_id: str
    feature_month: str
    outcome_month: str
    history_months: int
    income: float
    committed: float
    variable: float
    feature_income: float
    feature_committed: float
    feature_variable: float
    feature_income_3m: float
    feature_committed_3m: float
    feature_variable_3m: float
    feature_income_6m: float
    feature_committed_6m: float
    feature_variable_6m: float


TARGETS = ("income", "committed", "variable")
FEATURES = (
    "feature_income", "feature_committed", "feature_variable",
    "feature_income_3m", "feature_committed_3m", "feature_variable_3m",
    "feature_income_6m", "feature_committed_6m", "feature_variable_6m",
)


def _positive_successful(values: pd.Series, statuses: pd.Series) -> pd.Series:
    successful = statuses.map(classify_transaction_status).eq(TransactionStatus.SUCCESSFUL)
    return values.clip(lower=0.0).where(successful, 0.0)


def _boolean_values(values: pd.Series, default: bool = False) -> pd.Series:
    if values.dtype == bool:
        return values.fillna(default)
    normalized = values.fillna("").astype(str).str.strip().str.lower()
    return normalized.isin({"1", "true", "yes", "y", "t"})


class CashFlowForecastDatasetBuilder:
    """Build observed monthly T -> T+1 cash-flow examples without future leakage."""

    minimum_history_months = 6

    def build(self, transactions: pd.DataFrame) -> list[CashFlowExample]:
        if transactions.empty:
            return []
        frame = transactions.copy()
        frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce")
        frame = frame.dropna(subset=["transaction_date"]).copy()
        if frame.empty:
            return []
        frame["user_id"] = frame.get("user_id", "").astype(str)
        frame["month"] = frame["transaction_date"].dt.to_period("M")
        frame["amount_value"] = pd.to_numeric(frame.get("amount", 0), errors="coerce").fillna(0.0)
        status = frame.get("transaction_status", pd.Series("", index=frame.index)).fillna("")
        transaction_class = frame.get("transaction_class", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
        income_flag = _boolean_values(frame.get("income_flag", pd.Series(False, index=frame.index)))
        income_flag = income_flag | transaction_class.isin({"income", "salary"})
        successful_amount = _positive_successful(frame["amount_value"], status)
        committed_flag = transaction_class.isin({"subscription", "emi", "bnpl"})
        income = successful_amount.where(income_flag, 0.0)
        committed = successful_amount.where(committed_flag & ~income_flag, 0.0)
        variable = successful_amount.where(~income_flag & ~committed_flag, 0.0)

        monthly = pd.DataFrame(
            {
                "income": income.to_numpy(),
                "committed": committed.to_numpy(),
                "variable": variable.to_numpy(),
            },
            index=pd.MultiIndex.from_arrays([frame["user_id"], frame["month"]], names=["user_id", "month"]),
        ).groupby(level=["user_id", "month"]).sum()
        examples: list[CashFlowExample] = []
        for user_id, group in monthly.groupby(level="user_id", sort=False):
            group = group.droplevel("user_id").sort_index()
            months = list(group.index)
            for position in range(len(months) - 1):
                feature_month = months[position]
                outcome_month = feature_month + 1
                if outcome_month not in group.index:
                    continue
                history_months = position + 1
                if history_months < self.minimum_history_months:
                    continue
                outcome = group.loc[outcome_month]
                examples.append(
                    CashFlowExample(
                        user_id=str(user_id),
                        feature_month=str(feature_month),
                        outcome_month=str(outcome_month),
                        history_months=history_months,
                        income=float(outcome["income"]),
                        committed=float(outcome["committed"]),
                        variable=float(outcome["variable"]),
                        feature_income=float(group.loc[months[max(0, position)], "income"]),
                        feature_committed=float(group.loc[months[max(0, position)], "committed"]),
                        feature_variable=float(group.loc[months[max(0, position)], "variable"]),
                        feature_income_3m=float(group.loc[months[max(0, position - 2):position + 1], "income"].mean()),
                        feature_committed_3m=float(group.loc[months[max(0, position - 2):position + 1], "committed"].mean()),
                        feature_variable_3m=float(group.loc[months[max(0, position - 2):position + 1], "variable"].mean()),
                        feature_income_6m=float(group.loc[months[max(0, position - 5):position + 1], "income"].mean()),
                        feature_committed_6m=float(group.loc[months[max(0, position - 5):position + 1], "committed"].mean()),
                        feature_variable_6m=float(group.loc[months[max(0, position - 5):position + 1], "variable"].mean()),
                    )
                )
        return sorted(examples, key=lambda example: (example.feature_month, example.user_id))

    def monthly_series(self, transactions: pd.DataFrame) -> pd.DataFrame:
        if transactions.empty:
            return pd.DataFrame(columns=["income", "committed", "variable"])
        frame = transactions.copy()
        frame["transaction_date"] = pd.to_datetime(frame["transaction_date"], errors="coerce")
        frame = frame.dropna(subset=["transaction_date"]).copy()
        frame["month"] = frame["transaction_date"].dt.to_period("M")
        frame["amount_value"] = pd.to_numeric(frame.get("amount", 0), errors="coerce").fillna(0.0)
        status = frame.get("transaction_status", pd.Series("", index=frame.index)).fillna("")
        classes = frame.get("transaction_class", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
        income_flag = _boolean_values(frame.get("income_flag", pd.Series(False, index=frame.index))) | classes.isin({"income", "salary"})
        amount = _positive_successful(frame["amount_value"], status)
        return pd.DataFrame(
            {
                "income": amount.where(income_flag, 0.0).to_numpy(),
                "committed": amount.where(classes.isin({"subscription", "emi", "bnpl"}), 0.0).to_numpy(),
                "variable": amount.where(~income_flag & ~classes.isin({"subscription", "emi", "bnpl"}), 0.0).to_numpy(),
            },
            index=frame["month"],
        ).groupby(level=0).sum().sort_index()

    def current_example(self, transactions: pd.DataFrame) -> CashFlowExample | None:
        monthly = self.monthly_series(transactions)
        if monthly.empty or len(monthly) < self.minimum_history_months:
            return None
        position = len(monthly) - 1
        months = list(monthly.index)
        feature_month = months[position]
        values = {
            "income": "feature_income",
            "committed": "feature_committed",
            "variable": "feature_variable",
        }
        return CashFlowExample(
            user_id=str(transactions["user_id"].iloc[0]),
            feature_month=str(feature_month),
            outcome_month=str(feature_month + 1),
            history_months=len(months),
            income=0.0,
            committed=0.0,
            variable=0.0,
            feature_income=float(monthly.loc[months[position], "income"]),
            feature_committed=float(monthly.loc[months[position], "committed"]),
            feature_variable=float(monthly.loc[months[position], "variable"]),
            feature_income_3m=float(monthly.iloc[max(0, position - 2):position + 1]["income"].mean()),
            feature_committed_3m=float(monthly.iloc[max(0, position - 2):position + 1]["committed"].mean()),
            feature_variable_3m=float(monthly.iloc[max(0, position - 2):position + 1]["variable"].mean()),
            feature_income_6m=float(monthly.iloc[max(0, position - 5):position + 1]["income"].mean()),
            feature_committed_6m=float(monthly.iloc[max(0, position - 5):position + 1]["committed"].mean()),
            feature_variable_6m=float(monthly.iloc[max(0, position - 5):position + 1]["variable"].mean()),
        )


def _metrics(actual: list[float], predicted: list[float], baseline_mae: float | None = None) -> dict[str, float | None]:
    errors = [abs(a - p) for a, p in zip(actual, predicted)]
    mae = sum(errors) / len(errors) if errors else 0.0
    rmse = sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual)) if actual else 0.0
    mean_actual = sum(actual) / len(actual) if actual else 0.0
    total = sum((a - mean_actual) ** 2 for a in actual)
    r2 = 1.0 - (sum((a - p) ** 2 for a, p in zip(actual, predicted)) / total) if total else 0.0
    sorted_errors = sorted(errors)
    p90 = sorted_errors[min(len(sorted_errors) - 1, int(len(sorted_errors) * 0.9))] if sorted_errors else 0.0
    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "r2": round(r2, 4),
        "median_absolute_error": round(float(pd.Series(errors).median()), 2) if errors else 0.0,
        "percentile_90_absolute_error": round(p90, 2),
        "improvement_over_baseline_percent": round((baseline_mae - mae) * 100 / baseline_mae, 2) if baseline_mae else None,
    }


def evaluate_baselines(examples: list[CashFlowExample]) -> tuple[dict[str, dict[str, float | None]], dict[str, str]]:
    if not examples:
        return {}, {}
    split_at = max(1, int(len(examples) * 0.70))
    validation_end = max(split_at + 1, int(len(examples) * 0.85))
    validation = examples[split_at:validation_end]
    targets = TARGETS
    selected: dict[str, str] = {}
    reports: dict[str, dict[str, float | None]] = {}
    for target in targets:
        candidates: dict[str, tuple[list[float], list[float]]] = {}
        for name in ("previous_month", "three_month_average", "six_month_average"):
            actual = [getattr(example, target) for example in validation]
            feature_name = {
                "previous_month": f"feature_{target}",
                "three_month_average": f"feature_{target}_3m",
                "six_month_average": f"feature_{target}_6m",
            }[name]
            predicted = [getattr(example, feature_name) for example in validation]
            candidates[name] = (actual, predicted)
        winner = min(candidates, key=lambda name: sum(abs(a - p) for a, p in zip(*candidates[name])) / max(len(validation), 1))
        selected[target] = winner
        actual, predicted = candidates[winner]
        reports[target] = _metrics(actual, predicted)
    reports["_split"] = {
        "train_snapshots": split_at,
        "validation_snapshots": len(validation),
        "test_snapshots": max(len(examples) - validation_end, 0),
        "train_users": len({example.user_id for example in examples[:split_at]}),
        "validation_users": len({example.user_id for example in examples[split_at:validation_end]}),
        "test_users": len({example.user_id for example in examples[validation_end:]}),
    }
    return reports, selected


class CashFlowModelTrainer:
    """Train separate component regressors and accept only validation winners."""

    model_name = "cash_flow_forecast"
    model_version = "v1.0"

    def train(self, examples: list[CashFlowExample], persistence: ModelPersistenceManager | None = None) -> ModelBundle:
        if len(examples) < 3:
            raise ValueError("Cash-flow model training requires at least three usable snapshots.")
        examples = sorted(examples, key=lambda item: (item.feature_month, item.user_id))
        months = sorted({item.feature_month for item in examples})
        train_end = max(1, int(len(months) * 0.70))
        validation_end = max(train_end + 1, int(len(months) * 0.85))
        train_months = set(months[:train_end])
        validation_months = set(months[train_end:validation_end])
        test_months = set(months[validation_end:])
        if not validation_months or not test_months:
            raise ValueError("Cash-flow model split must contain a test period.")

        frame = pd.DataFrame([{feature: getattr(example, feature) for feature in FEATURES} for example in examples], index=[
            example.feature_month for example in examples
        ])
        targets = {target: pd.Series([getattr(example, target) for example in examples], index=frame.index) for target in TARGETS}
        train_mask = frame.index.isin(train_months)
        validation_mask = frame.index.isin(validation_months)
        test_mask = frame.index.isin(test_months)
        preprocessor = PreprocessingPipeline(
            PreprocessingConfig(scaling_strategy=ScalingStrategy.STANDARD, test_size=0.2, random_state=get_ml_config().default_random_seed)
        )
        train_features = preprocessor.fit_transform(frame.loc[train_mask])
        validation_features = preprocessor.transform(frame.loc[validation_mask])
        test_features = preprocessor.transform(frame.loc[test_mask])
        models: dict[str, HistGradientBoostingRegressor] = {}
        validation_metrics: dict[str, dict[str, float]] = {}
        test_metrics: dict[str, dict[str, float]] = {}
        baseline_metrics: dict[str, dict[str, float | None]] = {}
        for target in TARGETS:
            model = HistGradientBoostingRegressor(
                max_iter=100,
                learning_rate=0.05,
                max_leaf_nodes=15,
                l2_regularization=1.0,
                random_state=get_ml_config().default_random_seed,
            )
            model.fit(train_features, targets[target].loc[train_mask])
            validation_prediction = model.predict(validation_features)
            test_prediction = model.predict(test_features)
            validation_metrics[target] = evaluate_regression(
                targets[target].loc[validation_mask].tolist(), validation_prediction.tolist()
            ).__dict__
            test_metrics[target] = evaluate_regression(
                targets[target].loc[test_mask].tolist(), test_prediction.tolist()
            ).__dict__
            baseline_metrics[target] = self._baseline_metrics(
                examples, target, validation_months
            )
            models[target] = model

        metadata = {
            "algorithm": "HistGradientBoostingRegressor",
            "dataset_version": "cash-flow-reference-v1",
            "feature_version": "cash-flow-features-v1",
            "target_definition": "Observed successful positive next-month income, committed expenses, and variable expenses.",
            "train_period": [min(train_months), max(train_months)],
            "validation_period": [min(validation_months), max(validation_months)],
            "test_period": [min(test_months), max(test_months)],
            "train_snapshots": int(train_mask.sum()),
            "validation_snapshots": int(validation_mask.sum()),
            "test_snapshots": int(test_mask.sum()),
            "validation_metrics": validation_metrics,
            "test_metrics": test_metrics,
            "baseline_metrics": baseline_metrics,
            "acceptance_status": "EVALUATED",
            "random_seed": get_ml_config().default_random_seed,
        }
        bundle = ModelBundle(
            artifact=ModelArtifact(
                model_name=self.model_name,
                model_version=self.model_version,
                task_type=MLTaskType.REGRESSION,
                feature_columns=FEATURES,
                target_column="income,committed,variable",
                metrics=test_metrics,
                metadata=metadata,
            ),
            model={"models": models, "preprocessor": preprocessor},
            preprocessor_state=preprocessor.state,
        )
        return (persistence or ModelPersistenceManager()).save(bundle)

    @staticmethod
    def predict(bundle: ModelBundle, example: CashFlowExample) -> dict[str, float]:
        payload = bundle.model
        frame = pd.DataFrame([{feature: getattr(example, feature) for feature in FEATURES}])
        transformed = payload["preprocessor"].transform(frame)
        return {
            target: max(0.0, round(float(payload["models"][target].predict(transformed)[0]), 2))
            for target in TARGETS
        }

    @staticmethod
    def _baseline_metrics(
        examples: list[CashFlowExample], target: str, validation_months: set[str]
    ) -> dict[str, float | None]:
        validation = [item for item in examples if item.feature_month in validation_months]
        actual = [getattr(item, target) for item in validation]
        predicted = [item.feature_income if target == "income" else item.feature_committed if target == "committed" else item.feature_variable for item in validation]
        return evaluate_regression(actual, predicted).__dict__
