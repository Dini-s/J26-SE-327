"""Hand-labelling of trace links: a fixed random sample, the saved labels, and precision with a confidence interval.

Labels live in ``data/labels/<project>.json`` (not in Neo4j: C4 only writes its own edges there).
The sample is deterministic, so labelling can be done over several sittings.
"""

import hashlib
import json
import math
import os
import tempfile
from threading import RLock
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

LABELS_DIR = Path(__file__).resolve().parents[2] / "data" / "labels"
_LABEL_LOCK = RLock()

VALID = ("correct", "wrong", "unsure")
BUCKETS = [(0.0, 0.7, "< 0.7"), (0.7, 0.85, "0.7 - 0.85"), (0.85, 1.01, ">= 0.85")]


def _key(requirement: str, code: str) -> str:
    return f"{requirement}||{code}"


def _path(project: str, directory: Path) -> Path:
    return directory / (re.sub(r"[^A-Za-z0-9_-]", "_", project) + ".json")


def sample_links(links: list[dict[str, Any]], n: int = 40, seed: str = "c4") -> list[dict[str, Any]]:
    """A repeatable random sample of the verified links (hash order, so it does not change between visits)."""
    verified = [l for l in links if l.get("status") != "decayed"]
    verified.sort(key=lambda l: (l.get("status") != "pending_review", hashlib.sha256(f"{seed}|{l['requirement']}|{l['code']}".encode()).hexdigest()))
    return verified[: max(1, n)]


def load_labels(project: str, directory: Path = LABELS_DIR) -> dict[str, dict[str, str]]:
    path = _path(project, directory)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("labels", {})


def set_label(project: str, requirement: str, code: str, label: Optional[str], directory: Path = LABELS_DIR) -> dict[str, dict[str, str]]:
    """Save (or clear, with ``None``) one label and return all labels of the project."""
    if label is not None and label not in VALID:
        raise ValueError(f"label must be one of {VALID} or null")
    with _LABEL_LOCK:
        labels = load_labels(project, directory)
        if label is None:
            labels.pop(_key(requirement, code), None)
        else:
            labels[_key(requirement, code)] = {"label": label, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as fh:
                temporary = Path(fh.name)
                json.dump({"project": project, "labels": labels}, fh, indent=1)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temporary, _path(project, directory))
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return labels


def wilson(correct: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a proportion (honest for small samples)."""
    if total == 0:
        return (0.0, 0.0)
    p = correct / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def stats(sample: list[dict[str, Any]], labels: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Precision of the labelled sample, overall and per LLM-confidence bucket. 'unsure' is left out of precision."""
    got = [(l, labels.get(_key(l["requirement"], l["code"]), {}).get("label")) for l in sample]
    correct = sum(1 for _, x in got if x == "correct")
    wrong = sum(1 for _, x in got if x == "wrong")
    unsure = sum(1 for _, x in got if x == "unsure")
    judged = correct + wrong
    lo, hi = wilson(correct, judged)

    by_bucket = []
    for b_lo, b_hi, name in BUCKETS:
        c = sum(1 for l, x in got if x == "correct" and b_lo <= (l.get("confidence") or 0) < b_hi)
        w = sum(1 for l, x in got if x == "wrong" and b_lo <= (l.get("confidence") or 0) < b_hi)
        by_bucket.append({"label": name, "correct": c, "wrong": w, "precision": round(c / (c + w), 3) if c + w else None})

    return {
        "sample": len(sample),
        "labelled": correct + wrong + unsure,
        "correct": correct,
        "wrong": wrong,
        "unsure": unsure,
        "precision": round(correct / judged, 3) if judged else None,
        "ci95": [round(lo, 3), round(hi, 3)] if judged else None,
        "byConfidence": by_bucket,
    }
