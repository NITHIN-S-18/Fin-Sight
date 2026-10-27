from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class MLConfig:
	default_random_seed: int = 42
	default_test_split_ratio: float = 0.2
	default_missing_value_strategy: str = "median"
	default_scaling_strategy: str = "standard"
	default_pipeline_version: str = "1.0"
	default_feature_version: str = "1.0"
	framework_version: str = "1.0"


@lru_cache(maxsize=1)
def get_ml_config() -> MLConfig:
	return MLConfig()
