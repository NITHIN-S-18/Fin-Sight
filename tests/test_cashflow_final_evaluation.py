from __future__ import annotations

import json
from pathlib import Path


def test_unseen_user_evaluation_is_disjoint_and_sane() -> None:
    report_path = Path(__file__).parents[1] / "cashflow_final_evaluation_report.json"
    if not report_path.exists():
        raise AssertionError("Run backend/scripts/final_cashflow_evaluation.py before this regression test.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    experiment = report["unseen_user_experiment"]

    assert experiment["split"]["development"]["user_count"] == 3500
    assert experiment["split"]["validation"]["user_count"] == 750
    assert experiment["split"]["unseen_test"]["user_count"] == 750
    assert all(
        not overlaps
        for population in experiment["user_overlap"].values()
        for overlaps in population.values()
    )
    assert report["generalization"]["variable"]["classification"] == "STRONG GENERALIZATION"
    assert report["generalization"]["income"]["classification"] == "NO MEANINGFUL GENERALIZATION"
    assert report["generalization"]["committed"]["classification"] == "NO MEANINGFUL GENERALIZATION"
    assert report["sanity_checks"]["negative_expense_predictions"] == {
        "committed": 0,
        "variable": 0,
    }
    assert report["sanity_checks"]["derived_consistency"] == {
        "total_expenses": True,
        "net_cash": True,
    }
    assert len(report["case_studies"]) == 6
    assert any(case["pattern"].startswith("poor prediction") for case in report["case_studies"])
