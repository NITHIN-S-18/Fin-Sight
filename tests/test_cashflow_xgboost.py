from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_xgboost_comparison_preserves_frozen_model_decision() -> None:
    pytest.importorskip("xgboost")
    report_path = Path(__file__).parents[1] / "cashflow_xgboost_report.json"
    if not report_path.exists():
        pytest.fail("Run backend/scripts/evaluate_cashflow_xgboost.py before this regression test.")
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["xgboost_version"] == "3.4.1"
    assert report["split"]["train"]["count"] == 60000
    assert report["split"]["validation"]["count"] == 15000
    assert report["split"]["test"]["count"] == 15000
    assert report["selected_forecasters"] == {
        "income": "six_month_average",
        "committed": "three_month_average",
        "variable": "HistGradientBoosting",
    }
    assert (
        report["targets"]["variable"]["XGBoost"]["mae"]
        < report["targets"]["variable"]["HistGradientBoosting"]["mae"]
    )
    assert (
        report["targets"]["variable"]["HistGradientBoosting"]["mae"]
        - report["targets"]["variable"]["XGBoost"]["mae"]
    ) < 0.01 * report["targets"]["variable"]["HistGradientBoosting"]["mae"]
