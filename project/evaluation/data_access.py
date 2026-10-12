"""The only door to the Component 1 task files.

`load_task` serves train/val rows and refuses `test`. The frozen test rows are available only through
`load_test_for_final_evaluation`, which first verifies `frozen_test_ids.csv` and the task file against `manifest.json` (SHA-256).
Training and tuning code must never call it; `tests/test_baselines.py` enforces that.
"""
import hashlib
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data" / "component1"
TASKS = DATA / "processed" / "tasks"
RAW = DATA / "raw"
TRAINING_SPLITS = ("train", "val")


class FrozenTestError(RuntimeError):
    """Raised when the frozen test split is requested the wrong way or fails verification."""


def _read(name):
    return pd.read_csv(TASKS / f"{name}.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)


def load_task(name, splits=TRAINING_SPLITS, tasks_dir=None):
    """Rows of `tasks/<name>.csv` for the requested splits (train and/or val only)."""
    if any(s == "test" for s in splits) or not set(splits) <= set(TRAINING_SPLITS):
        raise FrozenTestError("The test split is frozen: use load_test_for_final_evaluation() from the final evaluation only.")
    df = pd.read_csv((Path(tasks_dir) if tasks_dir else TASKS) / f"{name}.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    out = df[df.split.isin(splits)].reset_index(drop=True)
    assert not (out.split == "test").any()
    return out


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_frozen_test(name, tasks_dir=None):
    """Check frozen_test_ids.csv and tasks/<name>.csv against manifest.json, and that the test ids match. Raises FrozenTestError."""
    tdir = Path(tasks_dir) if tasks_dir else TASKS
    manifest = json.loads((tdir / "manifest.json").read_text(encoding="utf-8"))
    frozen_path = tdir / "frozen_test_ids.csv"
    if sha256_file(frozen_path) != manifest["frozen_test_ids_sha256"]:
        raise FrozenTestError("frozen_test_ids.csv does not match the SHA-256 in manifest.json")
    task_file = f"{name}.csv"
    if task_file in manifest["file_sha256"] and sha256_file(tdir / task_file) != manifest["file_sha256"][task_file]:
        raise FrozenTestError(f"{task_file} does not match the SHA-256 in manifest.json")
    frozen = pd.read_csv(frozen_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    frozen_ids = set(frozen[frozen.task == name].record_id)
    df = pd.read_csv(tdir / task_file, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    if set(df[df.split == "test"].record_id) != frozen_ids:
        raise FrozenTestError(f"test rows of {task_file} differ from frozen_test_ids.csv")
    return len(frozen_ids)


def load_test_for_final_evaluation(name, tasks_dir=None):
    """Verified test rows. Call only from the final evaluation step."""
    verify_frozen_test(name, tasks_dir)
    df = pd.read_csv((Path(tasks_dir) if tasks_dir else TASKS) / f"{name}.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    return df[df.split == "test"].reset_index(drop=True)
