"""The evidence shown on the dashboard's Results tab, built from the saved result files in ``data/results``.

Every number the page shows comes from a file here (nothing is typed into the page), so the page and the
measurements cannot drift apart. Missing files simply leave their part out. Pure functions over the parsed JSON
so they can be tested without the files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

RESULTS_DIR = Path(__file__).resolve().parents[2] / "data" / "results"


def read(name: str, folder: Path = RESULTS_DIR) -> Any:
    path = folder / name
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (OSError, ValueError):
        return None


def llm_comparison(raw: Optional[dict[str, Any]]) -> Optional[list[dict[str, Any]]]:
    """Precision / recall / F1 / time of each verifier LLM on the same labelled pairs.

    A pair where the model gave no usable answer (``linked`` is null) counts as "not linked" and is reported.
    """
    if not raw or not raw.get("models"):
        return None
    out = []
    for name, rows in raw["models"].items():
        if not rows:
            continue
        linked = lambda r: bool(r.get("linked"))  # noqa: E731
        tp = sum(r["label"] == 1 and linked(r) for r in rows)
        fp = sum(r["label"] == 0 and linked(r) for r in rows)
        fn = sum(r["label"] == 1 and not linked(r) for r in rows)
        precision, recall = tp / max(1, tp + fp), tp / max(1, tp + fn)
        seconds = [r["seconds"] for r in rows if r.get("seconds") is not None]
        out.append({"model": name.split(":")[0], "pairs": len(rows), "precision": round(precision, 3), "recall": round(recall, 3),
                    "f1": round(2 * precision * recall / max(1e-9, precision + recall), 3),
                    "seconds": round(sum(seconds) / len(seconds)) if seconds else None,
                    "noAnswer": sum(r.get("linked") is None for r in rows)})
    return out or None


def codebert_real_projects(raw: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Before (TF-IDF + MiniLM) against after (+ fine-tuned CodeBERT) on the real projects, recall@10 and MRR."""
    if not raw or not raw.get("projects"):
        return None
    before, after = "TF-IDF + MiniLM (before)", "TF-IDF + MiniLM + CodeBERT (after)"
    rows = []
    for project, v in raw["projects"].items():
        table = v.get("table", {})
        if before in table and after in table:
            rows.append({"project": project, "before": table[before]["recall@10"], "after": table[after]["recall@10"],
                         "links": v.get("true_links")})
    mean = raw.get("mean_over_projects", {})
    if not rows or before not in mean or after not in mean:
        return None
    return {"rows": rows, "meanBefore": mean[before]["recall@10"], "meanAfter": mean[after]["recall@10"],
            "mrrBefore": mean[before]["MRR"], "mrrAfter": mean[after]["MRR"],
            "better": sum(r["after"] > r["before"] for r in rows), "worse": sum(r["after"] < r["before"] for r in rows)}


def prompt_comparison(raw: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Expert prompt against the evidence prompt on hand-labelled links."""
    s = (raw or {}).get("summary")
    if not s:
        return None
    return {"project": raw.get("project"), "judged": s.get("links_judged"), "expertPrecision": s.get("standard_precision"),
            "evidencePrecision": s.get("evidence_precision"), "evidenceKept": s.get("evidence_kept"),
            "correctKept": s.get("correct_links_kept"), "wrongRejected": s.get("wrong_links_rejected")}


def decay_comparison(plain: Optional[dict[str, Any]], with_check: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Decay detection by the LLM alone against the LLM plus the meaning-change check."""
    if not plain or not with_check:
        return None
    return {"llmOnly": plain["decay_detection_accuracy"], "llmOnlyCi": plain.get("decay_detection_ci95"),
            "withCheck": with_check["decay_detection_accuracy"], "withCheckCi": with_check.get("decay_detection_ci95"),
            "falseAlarms": with_check.get("false_decay_rate"), "links": with_check.get("links_used")}


def targets(summary: Optional[dict[str, Any]], decay: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """The four headline targets, with the measured value taken from the result files."""
    summary = summary or {}
    prf = summary.get("prf") or []
    full = next((r for r in prf if "full pipeline" in str(r.get("method", "")).lower()), None)
    recall10 = (((summary.get("stage1_recall") or {}).get("iTrust") or {}).get("10") or {}).get("hybrid")
    latency = next((n for n in summary.get("nfr") or [] if "latency" in str(n.get("name", "")).lower()), None)
    seconds = None
    if latency:
        m = re.search(r"(\d+(?:\.\d+)?)\s*s", str(latency.get("measured", "")))
        seconds = float(m.group(1)) if m else None
    rows: list[dict[str, Any]] = []
    if full:
        rows.append({"key": "precision", "label": "LLM precision", "value": full["precision"], "format": "percent", "target": 0.9,
                     "higherIsBetter": True, "note": str(full.get("dataset", ""))})
    if seconds is not None:
        rows.append({"key": "latency", "label": "LLM time per link", "value": seconds, "format": "seconds", "target": 5,
                     "higherIsBetter": False, "note": str(latency.get("measured", ""))})
    if decay:
        rows.append({"key": "decay", "label": "Decay detection", "value": decay["decay_detection_accuracy"], "format": "percent", "target": 0.85,
                     "higherIsBetter": True, "note": f"{decay.get('links_used', decay.get('sample_links'))} links, false alarms {decay.get('false_decay_rate', 0):.0%}"})
    if recall10 is not None:
        rows.append({"key": "recall", "label": "Stage-1 recall (top-10)", "value": recall10, "format": "percent", "target": 0.8,
                     "higherIsBetter": True, "note": "iTrust, hybrid shortlist; the LLM cannot recover a missed link"})
    for r in rows:
        r["met"] = r["value"] >= r["target"] if r["higherIsBetter"] else r["value"] <= r["target"]
    return rows


def still_pending(summary: Optional[dict[str, Any]], decay: Optional[dict[str, Any]]) -> list[str]:
    """The "still pending" notes of summary.json, without the ones that have been measured since.

    summary.json is a record of the earlier measurements and is not edited; the decay-injection rate was measured
    afterwards (``decay_injection_v*.json``), so that note would contradict the page.
    """
    notes = list((summary or {}).get("pending") or [])
    if decay:
        notes = [n for n in notes if "decay-injection" not in n.lower()]
    return notes


def build(folder: Path = RESULTS_DIR) -> dict[str, Any]:
    """Everything the Results tab needs beyond summary.json."""
    summary = read("summary.json", folder)
    decay_files = sorted(folder.glob("decay_injection_v*.json")) if folder.exists() else []
    plain = read("decay_injection_v2.json", folder)
    with_check = read("decay_injection_v3.json", folder)
    latest_decay = with_check or (json.loads(decay_files[-1].read_text(encoding="utf-8")) if decay_files else None)
    return {
        "targets": targets(summary, latest_decay),
        "pending": still_pending(summary, latest_decay),
        "llmComparison": llm_comparison(read("llm_compare.json", folder)),
        "codebert": codebert_real_projects(read("stage1_codebert_real_projects.json", folder)),
        "prompt": prompt_comparison(read("evidence_ab_spring-petclinic.json", folder)),
        "decay": decay_comparison(plain, with_check),
    }
