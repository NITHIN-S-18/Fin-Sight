from __future__ import annotations

from dataclasses import dataclass, replace
from random import Random
from typing import Any

import pandas as pd

from app.ml.base import MissingValueStrategy, PreprocessingState, ProcessedDataset, ScalingStrategy
from app.ml.config import MLConfig, get_ml_config
from app.ml.utils import coerce_float, median_or_default, validate_dataframe


@dataclass(frozen=True)
class PreprocessingConfig:
    missing_value_strategy: MissingValueStrategy = MissingValueStrategy.MEDIAN
    scaling_strategy: ScalingStrategy = ScalingStrategy.STANDARD
    selected_features: tuple[str, ...] = ()
    dropped_features: tuple[str, ...] = ()
    constant_fill_value: float = 0.0
    test_size: float = 0.2
    random_state: int = 42
    stratify: bool = False

    @classmethod
    def from_ml_config(cls, config: MLConfig | None = None) -> "PreprocessingConfig":
        ml_config = config or get_ml_config()
        return cls(
            missing_value_strategy=MissingValueStrategy(ml_config.default_missing_value_strategy),
            scaling_strategy=ScalingStrategy(ml_config.default_scaling_strategy),
            test_size=ml_config.default_test_split_ratio,
            random_state=ml_config.default_random_seed,
        )


class PreprocessingPipeline:
    def __init__(self, config: PreprocessingConfig | None = None) -> None:
        self._ml_config = get_ml_config()
        self._config = config or PreprocessingConfig.from_ml_config(self._ml_config)
        self._state: PreprocessingState | None = None

    @property
    def config(self) -> PreprocessingConfig:
        return self._config

    @property
    def state(self) -> PreprocessingState | None:
        return self._state

    @classmethod
    def from_state(cls, state: PreprocessingState) -> "PreprocessingPipeline":
        normalized_state = PreprocessingState(
            input_columns=getattr(state, "input_columns", ()),
            transformed_columns=getattr(state, "transformed_columns", ()),
            numeric_columns=getattr(state, "numeric_columns", ()),
            categorical_columns=getattr(state, "categorical_columns", ()),
            categorical_levels=getattr(state, "categorical_levels", {}),
            categorical_fill_values=getattr(state, "categorical_fill_values", {}),
            numeric_statistics=getattr(state, "numeric_statistics", {}),
            missing_value_strategy=getattr(state, "missing_value_strategy", MissingValueStrategy.MEDIAN.value),
            scaling_strategy=getattr(state, "scaling_strategy", ScalingStrategy.STANDARD.value),
            feature_selection=getattr(state, "feature_selection", ()),
        )
        config = PreprocessingConfig(
            missing_value_strategy=MissingValueStrategy(normalized_state.missing_value_strategy),
            scaling_strategy=ScalingStrategy(normalized_state.scaling_strategy),
            selected_features=normalized_state.feature_selection,
        )
        pipeline = cls(config=config)
        pipeline._state = normalized_state
        return pipeline

    def fit(self, features: pd.DataFrame) -> PreprocessingState:
        feature_frame = self._prepare_input(features)
        input_columns = tuple(feature_frame.columns)
        numeric_columns = tuple(feature_frame.select_dtypes(include=["number", "bool"]).columns)
        categorical_columns = tuple(column for column in feature_frame.columns if column not in numeric_columns)

        numeric_statistics: dict[str, dict[str, float]] = {}
        for column in numeric_columns:
            series = pd.to_numeric(feature_frame[column], errors="coerce")
            values = [coerce_float(value) for value in series.dropna().tolist()]
            if self._config.missing_value_strategy == MissingValueStrategy.MEAN:
                fill_value = float(series.mean()) if not series.dropna().empty else self._config.constant_fill_value
            elif self._config.missing_value_strategy == MissingValueStrategy.MEDIAN:
                fill_value = median_or_default(values, default=self._config.constant_fill_value)
            else:
                fill_value = self._config.constant_fill_value

            numeric_statistics[column] = {
                "fill_value": float(fill_value),
                "mean": float(series.fillna(fill_value).mean()) if not series.empty else 0.0,
                "std": float(series.fillna(fill_value).std(ddof=0)) if not series.empty else 0.0,
                "min": float(series.fillna(fill_value).min()) if not series.empty else 0.0,
                "max": float(series.fillna(fill_value).max()) if not series.empty else 0.0,
            }

        categorical_levels: dict[str, tuple[str, ...]] = {}
        for column in categorical_columns:
            values = feature_frame[column].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
            categorical_levels[column] = tuple(sorted(values.unique().tolist()))

        provisional_state = PreprocessingState(
            input_columns=input_columns,
            transformed_columns=(),
            numeric_columns=numeric_columns,
            categorical_columns=categorical_columns,
            categorical_levels=categorical_levels,
            categorical_fill_values=self._build_categorical_fill_values(feature_frame, categorical_columns),
            numeric_statistics=numeric_statistics,
            missing_value_strategy=self._config.missing_value_strategy.value,
            scaling_strategy=self._config.scaling_strategy.value,
            feature_selection=tuple(self._config.selected_features),
        )

        transformed_frame = self._transform_with_state(feature_frame, provisional_state)
        self._state = replace(provisional_state, transformed_columns=tuple(transformed_frame.columns))
        return self._state

    def transform(self, features: pd.DataFrame) -> pd.DataFrame:
        if self._state is None:
            raise ValueError("Preprocessing pipeline must be fit before transform.")
        feature_frame = self._prepare_input(features)
        transformed_frame = self._transform_with_state(feature_frame, self._state)
        return transformed_frame.reindex(columns=list(self._state.transformed_columns), fill_value=0.0)

    def fit_transform(self, features: pd.DataFrame) -> pd.DataFrame:
        self.fit(features)
        return self.transform(features)

    def split_dataset(
        self,
        features: pd.DataFrame,
        target: pd.Series | None = None,
        test_size: float | None = None,
        random_state: int | None = None,
    ) -> ProcessedDataset:
        split_test_size = test_size if test_size is not None else self._config.test_size
        split_random_state = random_state if random_state is not None else self._config.random_state

        feature_frame = self._prepare_input(features)
        train_indices, test_indices = self._split_indices(feature_frame, target, split_test_size, split_random_state)

        train_raw = feature_frame.loc[train_indices].copy()
        test_raw = feature_frame.loc[test_indices].copy()
        self.fit(train_raw)
        train_features = self.transform(train_raw)
        test_features = self.transform(test_raw)

        train_target = target.loc[train_indices].copy() if target is not None else None
        test_target = target.loc[test_indices].copy() if target is not None else None

        return ProcessedDataset(
            train_features=train_features,
            test_features=test_features,
            train_target=train_target,
            test_target=test_target,
            feature_columns=tuple(train_features.columns),
            target_column=target.name if target is not None else None,
            pipeline_version=self._ml_config.default_pipeline_version,
            feature_version=self._ml_config.default_feature_version,
            preprocessing_state=self._state,
            metadata={
                "test_size": split_test_size,
                "random_state": split_random_state,
                "row_count": int(len(feature_frame)),
                "preprocessing_fit_rows": int(len(train_features)),
            },
        )

    def split_temporal_dataset(
        self,
        features: pd.DataFrame,
        target: pd.Series | None = None,
        validation_fraction: float = 0.2,
        test_fraction: float = 0.2,
    ) -> ProcessedDataset:
        if not isinstance(features.index, pd.MultiIndex) or "snapshot_month" not in features.index.names:
            raise ValueError("Temporal datasets require a snapshot_month MultiIndex.")
        if target is not None and not target.index.equals(features.index):
            target = target.reindex(features.index)
        months = sorted(features.index.get_level_values("snapshot_month").unique())
        if len(months) < 3:
            raise ValueError("Temporal datasets require at least three snapshot months.")
        test_start = max(1, int(len(months) * (1.0 - test_fraction)))
        validation_start = max(1, int(test_start - max(1, len(months) * validation_fraction)))
        validation_start = min(validation_start, test_start - 1)
        train_months = set(months[:validation_start])
        validation_months = set(months[validation_start:test_start])
        test_months = set(months[test_start:])
        train_mask = features.index.get_level_values("snapshot_month").isin(train_months)
        validation_mask = features.index.get_level_values("snapshot_month").isin(validation_months)
        test_mask = features.index.get_level_values("snapshot_month").isin(test_months)
        train_raw = features.loc[train_mask].copy()
        validation_raw = features.loc[validation_mask].copy()
        test_raw = features.loc[test_mask].copy()
        if train_raw.empty or validation_raw.empty or test_raw.empty:
            raise ValueError("Temporal split must contain train, validation, and test rows.")
        self.fit(train_raw)
        train_features = self.transform(train_raw)
        validation_features = self.transform(validation_raw)
        test_features = self.transform(test_raw)
        return ProcessedDataset(
            train_features=train_features,
            test_features=test_features,
            train_target=target.loc[train_raw.index].copy() if target is not None else None,
            test_target=target.loc[test_raw.index].copy() if target is not None else None,
            feature_columns=tuple(train_features.columns),
            target_column=target.name if target is not None else None,
            pipeline_version=self._ml_config.default_pipeline_version,
            feature_version=self._ml_config.default_feature_version,
            preprocessing_state=self._state,
            metadata={
                "split_strategy": "chronological",
                "training_period": [min(train_months), max(train_months)],
                "validation_period": [min(validation_months), max(validation_months)],
                "test_period": [min(test_months), max(test_months)],
                "training_rows": int(len(train_features)),
                "validation_rows": int(len(validation_features)),
                "test_rows": int(len(test_features)),
                "preprocessing_fit_rows": int(len(train_features)),
                "training_user_count": int(train_raw.index.get_level_values("user_id").nunique()),
                "validation_user_count": int(validation_raw.index.get_level_values("user_id").nunique()),
                "test_user_count": int(test_raw.index.get_level_values("user_id").nunique()),
                "training_target_summary": self._target_summary(
                    target.loc[train_raw.index] if target is not None else None
                ),
                "validation_target_summary": self._target_summary(
                    target.loc[validation_raw.index] if target is not None else None
                ),
                "test_target_summary": self._target_summary(
                    target.loc[test_raw.index] if target is not None else None
                ),
            },
            validation_features=validation_features,
            validation_target=target.loc[validation_raw.index].copy() if target is not None else None,
        )

    @staticmethod
    def _target_summary(target: pd.Series | None) -> dict[str, Any]:
        if target is None:
            return {"count": 0, "class_counts": {}, "positive_count": 0, "positive_rate": 0.0}
        values = target.dropna().tolist()
        counts: dict[str, int] = {}
        for value in values:
            counts[str(value)] = counts.get(str(value), 0) + 1
        return {
            "count": len(values),
            "class_counts": counts,
            "positive_count": counts.get("1", 0),
            "positive_rate": round(
                sum(1 for value in values if value == 1) / len(values), 4
            ) if values else 0.0,
        }

    def _prepare_input(self, features: pd.DataFrame) -> pd.DataFrame:
        feature_frame = validate_dataframe(features)

        if self._config.selected_features:
            missing_selected = [column for column in self._config.selected_features if column not in feature_frame.columns]
            if missing_selected:
                raise ValueError(f"Selected features are missing: {', '.join(missing_selected)}")
            feature_frame = feature_frame.loc[:, list(self._config.selected_features)]

        if self._config.dropped_features:
            feature_frame = feature_frame.drop(columns=[column for column in self._config.dropped_features if column in feature_frame.columns], errors="ignore")

        return feature_frame

    def _build_categorical_fill_values(self, features: pd.DataFrame, categorical_columns: tuple[str, ...]) -> dict[str, Any]:
        fill_values: dict[str, Any] = {}
        for column in categorical_columns:
            fill_values[column] = self._resolve_categorical_fill_value(features[column] if column in features.columns else pd.Series(dtype=object))
        return fill_values

    def _resolve_categorical_fill_value(self, series: pd.Series) -> Any:
        if self._config.missing_value_strategy == MissingValueStrategy.MODE:
            values = series.dropna().astype(str).str.strip().replace("", pd.NA).dropna()
            if not values.empty:
                mode_values = values.mode(dropna=True)
                if not mode_values.empty:
                    return mode_values.iloc[0]
            return "Unknown"
        return "Unknown"

    def _transform_with_state(self, features: pd.DataFrame, state: PreprocessingState) -> pd.DataFrame:
        transformed_columns: list[pd.DataFrame] = []

        for column in state.numeric_columns:
            numeric_series = pd.to_numeric(features[column], errors="coerce") if column in features.columns else pd.Series([state.numeric_statistics[column]["fill_value"]] * len(features), index=features.index)
            fill_value = state.numeric_statistics[column]["fill_value"]
            numeric_series = numeric_series.fillna(fill_value)
            if state.scaling_strategy == ScalingStrategy.STANDARD.value:
                mean_value = state.numeric_statistics[column]["mean"]
                std_value = state.numeric_statistics[column]["std"] or 1.0
                numeric_series = (numeric_series - mean_value) / std_value
            elif state.scaling_strategy == ScalingStrategy.MINMAX.value:
                minimum = state.numeric_statistics[column]["min"]
                maximum = state.numeric_statistics[column]["max"]
                denominator = (maximum - minimum) or 1.0
                numeric_series = (numeric_series - minimum) / denominator
            transformed_columns.append(numeric_series.rename(column).to_frame())

        for column in state.categorical_columns:
            column_values = features[column] if column in features.columns else pd.Series(["Unknown"] * len(features), index=features.index)
            fill_value = state.categorical_fill_values.get(column, "Unknown")
            column_values = column_values.fillna(fill_value).astype(str).str.strip().replace("", fill_value)
            dummy_frame = pd.get_dummies(column_values, prefix=column, prefix_sep="__", dtype=float)
            expected_levels = state.categorical_levels.get(column, ())
            expected_columns = [f"{column}__{level}" for level in expected_levels]
            dummy_frame = dummy_frame.reindex(columns=expected_columns, fill_value=0.0)
            transformed_columns.append(dummy_frame)

        if not transformed_columns:
            return pd.DataFrame(index=features.index)

        return pd.concat(transformed_columns, axis=1)

    def _split_indices(
        self,
        features: pd.DataFrame,
        target: pd.Series | None,
        test_size: float,
        random_state: int,
    ) -> tuple[list[Any], list[Any]]:
        if not 0 < test_size < 1:
            raise ValueError("test_size must be between 0 and 1.")

        indices = list(features.index)
        if len(indices) < 2:
            return indices, []

        if target is not None and self._config.stratify:
            return self._stratified_split_indices(indices, target, test_size, random_state)

        rng = Random(random_state)
        rng.shuffle(indices)
        split_point = max(1, int(round(len(indices) * (1.0 - test_size))))
        split_point = min(split_point, len(indices) - 1)
        return indices[:split_point], indices[split_point:]

    def _stratified_split_indices(
        self,
        indices: list[Any],
        target: pd.Series,
        test_size: float,
        random_state: int,
    ) -> tuple[list[Any], list[Any]]:
        rng = Random(random_state)
        grouped: dict[Any, list[Any]] = {}
        for index, label in target.loc[indices].items():
            grouped.setdefault(label, []).append(index)

        train_indices: list[Any] = []
        test_indices: list[Any] = []
        for label_indices in grouped.values():
            rng.shuffle(label_indices)
            split_point = max(1, int(round(len(label_indices) * (1.0 - test_size))))
            split_point = min(split_point, len(label_indices))
            train_indices.extend(label_indices[:split_point])
            test_indices.extend(label_indices[split_point:])

        rng.shuffle(train_indices)
        rng.shuffle(test_indices)
        if not test_indices and train_indices:
            test_indices = train_indices[-1:]
            train_indices = train_indices[:-1]
        return train_indices, test_indices
