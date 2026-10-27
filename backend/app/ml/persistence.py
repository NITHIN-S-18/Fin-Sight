from __future__ import annotations

import json
import pickle
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.ml.base import ModelArtifact, ModelBundle, PreprocessingState
from app.ml.config import get_ml_config
from app.ml.utils import ensure_directory, sanitize_component_name


class ModelPersistenceManager:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._ml_config = get_ml_config()
        self._base_dir = ensure_directory(base_dir or Path(__file__).resolve().parent / "saved_models")

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    _LOADED_BUNDLE_CACHE: dict[tuple[str, float], ModelBundle] = {}

    def _bundle_directory(self, model_name: str, model_version: str) -> Path:
        return self._model_storage_path(self._base_dir, sanitize_component_name(model_name), sanitize_component_name(model_version))

    def save(self, bundle: ModelBundle) -> ModelBundle:
        bundle_directory = ensure_directory(self._bundle_directory(bundle.artifact.model_name, bundle.artifact.model_version))
        model_path = bundle_directory / "model.pkl"
        metadata_path = bundle_directory / "metadata.json"

        artifact = replace(
            bundle.artifact,
            model_path=str(model_path),
            metadata_path=str(metadata_path),
        )
        persisted_bundle = replace(bundle, artifact=artifact)

        with model_path.open("wb") as handle:
            pickle.dump(persisted_bundle, handle)

        metadata_payload = self._artifact_to_json(artifact)
        metadata_path.write_text(json.dumps(metadata_payload, indent=2, ensure_ascii=True, default=str), encoding="utf-8")
        mtime = model_path.stat().st_mtime
        self._LOADED_BUNDLE_CACHE[(str(model_path), mtime)] = persisted_bundle
        return persisted_bundle

    def load(self, model_name: str, model_version: str | None = None) -> ModelBundle:
        model_directory = self._resolve_model_directory(model_name, model_version)
        model_path = model_directory / "model.pkl"
        if not model_path.exists():
            raise FileNotFoundError(f"Model bundle not found: {model_path}")

        mtime = model_path.stat().st_mtime
        cache_key = (str(model_path), mtime)
        cached = self._LOADED_BUNDLE_CACHE.get(cache_key)
        if cached is not None:
            return cached

        with model_path.open("rb") as handle:
            bundle = pickle.load(handle)

        if not isinstance(bundle, ModelBundle):
            raise TypeError("Persisted object is not a ModelBundle instance.")
        normalized = self._normalize_bundle(bundle)
        self._LOADED_BUNDLE_CACHE[cache_key] = normalized
        return normalized

    def load_latest(self, model_name: str) -> ModelBundle:
        model_directory = self._latest_model_directory(model_name)
        model_path = model_directory / "model.pkl"
        if not model_path.exists():
            raise FileNotFoundError(f"Model bundle not found: {model_path}")

        mtime = model_path.stat().st_mtime
        cache_key = (str(model_path), mtime)
        cached = self._LOADED_BUNDLE_CACHE.get(cache_key)
        if cached is not None:
            return cached

        with model_path.open("rb") as handle:
            bundle = pickle.load(handle)

        if not isinstance(bundle, ModelBundle):
            raise TypeError("Persisted object is not a ModelBundle instance.")
        normalized = self._normalize_bundle(bundle)
        self._LOADED_BUNDLE_CACHE[cache_key] = normalized
        return normalized

    def list_models(self) -> dict[str, list[str]]:
        model_inventory: dict[str, list[str]] = {}
        if not self._base_dir.exists():
            return model_inventory

        for model_path in self._base_dir.iterdir():
            if not model_path.is_dir():
                continue
            versions = sorted(child.name for child in model_path.iterdir() if child.is_dir())
            if versions:
                model_inventory[model_path.name] = versions
        return model_inventory

    def _resolve_model_directory(self, model_name: str, model_version: str | None) -> Path:
        safe_name = sanitize_component_name(model_name)
        model_root = self._base_dir / safe_name
        if model_version is not None:
            return model_root / sanitize_component_name(model_version)
        return self._latest_model_directory(model_name)

    def _latest_model_directory(self, model_name: str) -> Path:
        model_root = self._base_dir / sanitize_component_name(model_name)
        if not model_root.exists():
            raise FileNotFoundError(f"No saved models found for {model_name}.")

        version_directories = [child for child in model_root.iterdir() if child.is_dir()]
        if not version_directories:
            raise FileNotFoundError(f"No saved model versions found for {model_name}.")

        return max(version_directories, key=lambda path: path.stat().st_mtime)

    def _artifact_to_json(self, artifact: Any) -> dict[str, Any]:
        return {
            "model_name": artifact.model_name,
            "model_version": artifact.model_version,
            "task_type": artifact.task_type.value,
            "pipeline_version": artifact.pipeline_version,
            "feature_version": artifact.feature_version,
            "framework_version": artifact.framework_version,
            "python_version": artifact.python_version,
            "created_at": artifact.created_at.isoformat(),
            "feature_columns": list(artifact.feature_columns),
            "target_column": artifact.target_column,
            "metrics": artifact.metrics,
            "metadata": artifact.metadata,
            "model_path": artifact.model_path,
            "metadata_path": artifact.metadata_path,
            "storage_framework_version": self._ml_config.framework_version,
        }

    def _normalize_bundle(self, bundle: ModelBundle) -> ModelBundle:
        artifact = bundle.artifact
        normalized_artifact = ModelArtifact(
            model_name=getattr(artifact, "model_name"),
            model_version=getattr(artifact, "model_version"),
            task_type=getattr(artifact, "task_type"),
            pipeline_version=getattr(artifact, "pipeline_version", self._ml_config.default_pipeline_version),
            feature_version=getattr(artifact, "feature_version", self._ml_config.default_feature_version),
            framework_version=getattr(artifact, "framework_version", self._ml_config.framework_version),
            python_version=getattr(artifact, "python_version", ""),
            created_at=getattr(artifact, "created_at"),
            feature_columns=tuple(getattr(artifact, "feature_columns", ())),
            target_column=getattr(artifact, "target_column", None),
            metrics=dict(getattr(artifact, "metrics", {})),
            metadata=dict(getattr(artifact, "metadata", {})),
            model_path=getattr(artifact, "model_path", None),
            metadata_path=getattr(artifact, "metadata_path", None),
        )
        return ModelBundle(
            artifact=normalized_artifact,
            model=bundle.model,
            preprocessor_state=self._normalize_preprocessing_state(bundle.preprocessor_state),
            trained_at=getattr(bundle, "trained_at", normalized_artifact.created_at),
        )

    @staticmethod
    def _normalize_preprocessing_state(state: Any) -> Any:
        if state is None:
            return None
        return PreprocessingState(
            input_columns=getattr(state, "input_columns", ()),
            transformed_columns=getattr(state, "transformed_columns", ()),
            numeric_columns=getattr(state, "numeric_columns", ()),
            categorical_columns=getattr(state, "categorical_columns", ()),
            categorical_levels=getattr(state, "categorical_levels", {}),
            categorical_fill_values=getattr(state, "categorical_fill_values", {}),
            numeric_statistics=getattr(state, "numeric_statistics", {}),
            missing_value_strategy=getattr(state, "missing_value_strategy", "median"),
            scaling_strategy=getattr(state, "scaling_strategy", "standard"),
            feature_selection=getattr(state, "feature_selection", ()),
        )

    @staticmethod
    def _model_storage_path(base_dir: Path, model_name: str, model_version: str) -> Path:
        return base_dir / model_name / model_version
