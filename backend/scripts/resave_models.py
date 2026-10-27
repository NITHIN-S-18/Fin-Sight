import json
import pickle
from pathlib import Path

from app.ml.persistence import ModelPersistenceManager

# Base directory inside this repo where we want the canonical saved models
BASE_DIR = Path(__file__).resolve().parents[1] / "app" / "ml" / "saved_models"

# The metadata files in saved_models directories may reference model_path locations in a worktree.
# For each model folder that has a metadata.json, attempt to load the referenced model.pkl and
# re-save it into this repo's saved_models using ModelPersistenceManager.save(bundle).

def resave_models():
    base = BASE_DIR
    manager = ModelPersistenceManager(base_dir=base)
    if not base.exists():
        print(f"Saved models base dir does not exist: {base}")
        return

    for model_dir in base.iterdir():
        if not model_dir.is_dir():
            continue
        for version_dir in model_dir.iterdir():
            if not version_dir.is_dir():
                continue
            metadata_path = version_dir / "metadata.json"
            if not metadata_path.exists():
                print(f"Skipping (no metadata): {version_dir}")
                continue
            with metadata_path.open("r", encoding="utf-8") as fh:
                metadata = json.load(fh)
            model_path_str = metadata.get("model_path")
            if not model_path_str:
                print(f"No model_path in metadata for {version_dir}")
                continue
            model_path = Path(model_path_str)
            if not model_path.exists():
                print(f"Model file referenced by metadata not found: {model_path} (skipping)")
                continue

            print(f"Loading persisted bundle from: {model_path}")
            with model_path.open("rb") as handle:
                bundle = pickle.load(handle)

            # Re-save into canonical base using the persistence manager
            print(f"Re-saving model bundle for {bundle.artifact.model_name} v{bundle.artifact.model_version}")
            persisted = manager.save(bundle)
            print(f"Saved to: {persisted.artifact.model_path}")

if __name__ == '__main__':
    resave_models()
