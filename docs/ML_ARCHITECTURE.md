# ML_ARCHITECTURE.md

# FinSight Machine Learning Architecture

## Overview

FinSight uses a hybrid architecture: deterministic services calculate the current financial state, and the ML layer prepares reusable infrastructure for future prediction models.

Machine learning must consume the existing financial intelligence layer instead of duplicating it.

---

## Layering

Transactions
↓
DatasetService
↓
Feature Engineering
↓
Preprocessing
↓
Training
↓
Evaluation
↓
Persistence
↓
Inference

The rule-based services remain the source of truth for current exposure, health, and commitment intelligence.

---

## ML Package Structure

The ML layer lives under [backend/app/ml](../backend/app/ml).

Implemented modules:

- [base.py](../backend/app/ml/base.py)
- [config.py](../backend/app/ml/config.py)
- [feature_engineering.py](../backend/app/ml/feature_engineering.py)
- [preprocessing.py](../backend/app/ml/preprocessing.py)
- [training.py](../backend/app/ml/training.py)
- [evaluation.py](../backend/app/ml/evaluation.py)
- [inference.py](../backend/app/ml/inference.py)
- [persistence.py](../backend/app/ml/persistence.py)
- [utils.py](../backend/app/ml/utils.py)
- [temporal_dataset.py](../backend/app/ml/temporal_dataset.py)
- [saved_models/](../backend/app/ml/saved_models)

Each module has a single responsibility.

---

## Base Contracts

The base layer defines reusable contracts and data structures:

- `MLTaskType`
- `FeatureDefinition`
- `FinancialIntelligenceSnapshot`
- `FeatureFrame`
- `PreprocessingState`
- `ProcessedDataset`
- `ModelArtifact`
- `ModelBundle`
- `PredictionItem`
- `PredictionResult`
- estimator and transformer protocols

These contracts let future models plug into the infrastructure without rewriting plumbing.

---

## Central Configuration

`MLConfig` is the single source of truth for infrastructure defaults.

It defines:

- default random seed
- default test split ratio
- default missing value strategy
- default scaling strategy
- default pipeline version
- default feature version
- framework version

This keeps defaults consistent across preprocessing, training, inference, and persistence.

---

## Feature Engineering

Feature engineering is registry-based and extensible.

The current default feature set includes:

- Commitment ratio
- Subscription density
- EMI burden ratio
- BNPL dependency
- Exposure utilization
- Financial flexibility
- Commitment diversity
- Payment reliability
- AutoPay coverage
- Spending variance
- Income stability

Each feature can also carry a category for metadata-only organization such as Exposure, Commitment, Income, Behaviour, Payment, or Capacity.

The pipeline builds features from a `FinancialIntelligenceSnapshot`, which is assembled from `DatasetService` outputs.

This keeps feature generation aligned with the current deterministic intelligence layer.

---

## Versioning

The ML infrastructure tracks two stable version axes:

- `pipeline_version` for preprocessing and training infrastructure
- `feature_version` for the engineered feature set

These are persisted in the model artifact and bundled output so future changes remain traceable without breaking older models.

---

## Preprocessing

The preprocessing framework is model-agnostic.

Responsibilities:

- dataset validation
- missing value handling
- categorical encoding
- numeric scaling
- feature selection
- chronological train/validation/test splitting for temporal datasets

Categorical imputation can use `MODE` when explicitly selected. Existing behavior remains unchanged for the other strategies.

The pipeline stores its fitted state separately so future inference can reconstruct the same transformations.

---

## Training

The training framework is generic and accepts any estimator that follows the shared protocol.

Responsibilities:

- fit the model on processed data
- evaluate the untouched test period
- record validation-period metrics separately
- persist the trained bundle

The framework does not hardcode a specific algorithm.

---

## Evaluation

The evaluation layer remains independent from training.

Supported metrics:

Classification

- Accuracy
- Precision
- Recall
- F1 Score
- ROC AUC
- Balanced Accuracy
- Macro F1
- PR AUC
- Brier Score

Regression

- MAE
- RMSE
- R²
- Median Absolute Error
- Forecast Bias

Clustering

- Silhouette Score

---

## Inference

Inference loads a persisted model bundle, validates inputs, applies stored preprocessing when available, and returns structured prediction items.

Inference never retrains a model.

---

## Persistence

Models are stored under [saved_models/](../backend/app/ml/saved_models).

Each persisted bundle contains:

- the fitted model
- the artifact metadata
- the fitted preprocessing state, when present

The metadata includes reproducibility details such as pipeline version, feature version, Python version, creation time, and framework version.

This keeps future model integrations small and repeatable.

---

## Design Principles

The ML layer is designed to remain:

- modular
- reusable
- extensible
- independent from business services

The ML layer must not change the deterministic financial calculations.

It consumes financial intelligence, feature extracts from it, and prepares future predictive infrastructure.

---

## Temporal Training

Reference models use `TemporalDatasetBuilder` to construct leakage-safe monthly
examples. Features are computed from transactions through snapshot month `T`;
targets are computed only from observed transactions in the adjacent month
`T+1`.

- Distress target: a binary next-month failed/declined/rejected event.
- Exposure target: successful next-month commitment burden divided by
  successful positive next-month income.
- Exposure rows without positive next-month income are excluded from exposure
  training rather than assigned a fabricated fallback target.
- Splits are chronological, and preprocessing is fitted on training rows only.
- Current exposure remains deterministic and is not replaced by the forecast.
- Exposure artifacts record comparison against a naive current-month exposure
  baseline.
- Temporal artifacts record train/validation/test periods, user counts,
  target class counts, positive rates, and exposure-target coverage. Test
  periods with sparse positive examples remain explicitly reported rather than
  being rebalanced or augmented.
- Snapshot capacity is derived only from income observed through T. A static
  full-ledger profile is never used as a fallback for an early snapshot.
- Behaviour clustering evaluates supported candidate K values and records the
  selected K, silhouette scores, and cluster sizes. Behaviour output is
  descriptive only.
- Classification evaluation persists confusion matrices, class counts, and
  positive rates alongside precision, recall, F1, balanced accuracy, ROC-AUC,
  PR-AUC, and Brier score. Probability outputs are not considered calibrated
  unless calibration has been separately demonstrated.

---

## Future Integration

Later phases can plug in prediction models by implementing the shared estimator protocol and reusing the existing preprocessing, evaluation, inference, and persistence layers.

That keeps future work focused on model logic instead of infrastructure duplication.

## Model 2: Financial goal feasibility

Model 2 consumes the frozen cash-flow forecast and authenticated transaction
history. Its current accepted production policy is the deterministic
`observed-history-flexibility-baseline`: it estimates category-level
reductions from the user's historical lower-quartile spending and never
reduces committed or protected categories. All goal arithmetic is derived
deterministically from Model 1 outputs.

A supervised classifier is not exposed yet. The available reference data does
not provide an independent observed future-goal outcome, so training labels
would otherwise reproduce the same arithmetic being evaluated or become
fabricated. Evaluation metadata explicitly records `ml_status:
not_accepted` and `probability_exposed: false` rather than presenting an
uncalibrated probability.