# FinSight Phase 2 Controlled Experiment Run Summary

**Date (UTC):** 2026-10-26T10:48:56.022510+00:00
**Dataset SHA-256:** `66c8db0d836886d7ea83e034ff7d0f2b7f83d8e2e5254c3a1981d6d411ec1936`

## 1. Test Performance Comparison (N=422 untouched snapshots)

| Metric | Model A (27 Baseline) | Model B (41 Commitment-Aware) | Difference (B - A) | 95% Bootstrap CI (Paired) |
| :--- | :---: | :---: | :---: | :---: |
| **Average Precision** | 0.9564 | 0.9617 | +0.0053 | [-0.0038, +0.0151] |
| **ROC-AUC** | 0.9446 | 0.9561 | +0.0115 | [-0.0051, +0.0272] |
| **Balanced Accuracy** | 89.20% | 90.07% | +0.87% | [-1.22%, +2.98%] |
| **F1 Score** | 88.49% | 89.35% | +0.86% | [-1.41%, +3.07%] |
| **Brier Score** | 0.0834 | 0.0745 | -0.0089 | [-0.0190, +0.0012] |

