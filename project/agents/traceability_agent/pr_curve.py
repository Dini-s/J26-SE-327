"""Precision and recall of the stored links as the confidence threshold rises (the operating-point choice).

A stricter threshold keeps fewer links, so precision goes up and recall goes down. Showing the whole curve lets a
user pick a high-precision mode on purpose instead of quoting one number. Recall counts only the true links of the
requirements C4 has already processed, so it is not diluted by requirements nobody has linked yet.
"""

from typing import Any, Iterable, Optional, Sequence

from shared.schemas.traceability import TraceabilityLink

TARGET_PRECISION = 0.85


def pr_curve(
    traces: Sequence[TraceabilityLink],
    gold: Iterable[tuple[str, str]],
    target_precision: float = TARGET_PRECISION,
) -> dict[str, Any]:
    """Precision / recall of the verified links kept at each distinct confidence level.

    Returns ``{"rows": [...], "operating_point": row | None, "gold_links": n, "processed_requirements": n}``;
    ``operating_point`` is the loosest threshold whose precision reaches ``target_precision`` (most links kept).
    """
    gold_set = set(gold)
    verified = [t for t in traces if t.status != "decayed"]
    processed = {t.source_id for t in traces}
    gold_processed = {g for g in gold_set if g[0] in processed}
    levels = sorted({round(t.confidence, 2) for t in verified})
    rows: list[dict[str, Any]] = []
    for level in levels:
        kept = [t for t in verified if round(t.confidence, 2) >= level]
        correct = sum(1 for t in kept if (t.source_id, t.target_id) in gold_set)
        p = correct / len(kept) if kept else 0.0
        r = correct / len(gold_processed) if gold_processed else 0.0
        rows.append({
            "threshold": level, "kept": len(kept), "correct": correct,
            "precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
        })
    ok = [r for r in rows if r["precision"] >= target_precision]
    return {
        "rows": rows,
        "operating_point": ok[0] if ok else None,
        "target_precision": target_precision,
        "gold_links": len(gold_processed),
        "processed_requirements": len(processed),
    }


def pr_curve_project(uskg: Any, project: Optional[str]) -> Optional[dict[str, Any]]:
    """The curve for one project from the graph (read-only), or None if it has no ground truth."""
    import json

    from agents.traceability_agent.selfcheck import gold_path

    path = gold_path(project)
    if path is None:
        return None
    gold = [(g["source_id"], g["target_id"]) for g in json.loads(path.read_text(encoding="utf-8"))]
    scope = {"project": project} if project else {}
    out = pr_curve(uskg.get_traces(**scope), gold)
    out["project"] = project
    return out
