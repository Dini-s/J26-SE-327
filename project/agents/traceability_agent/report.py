"""Exports of the traceability state: matrix, flat link list, and the orphan / broken-link report."""

import csv
import io
from typing import Sequence

from agents.traceability_agent.completeness import completeness_scores
from shared.schemas.traceability import Artifact, TraceabilityLink

LOW_CONFIDENCE = 0.7


def _csv(rows: Sequence[Sequence[object]]) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(rows)
    return out.getvalue()


def links_csv(requirements: Sequence[Artifact], traces: Sequence[TraceabilityLink]) -> str:
    """One row per link: requirement, code entity, confidence, status, reason."""
    text = {r.id: r.text for r in requirements}
    rows: list[Sequence[object]] = [["requirement", "requirement_text", "code_entity", "confidence", "status", "reason"]]
    for t in sorted(traces, key=lambda t: (t.source_id, -t.confidence)):
        rows.append([t.source_id, (text.get(t.source_id) or "")[:300], t.target_id, round(t.confidence, 3), t.status, t.justification])
    return _csv(rows)


def matrix_csv(requirements: Sequence[Artifact], traces: Sequence[TraceabilityLink]) -> str:
    """Requirement x code matrix. Cell = confidence of a verified link, ``x<confidence>`` for a decayed one, blank if none."""
    codes = sorted({t.target_id for t in traces})
    cell = {(t.source_id, t.target_id): (f"{t.confidence:.2f}" if t.status == "verified" else f"{'x' if t.status == 'decayed' else t.status + ':'}{t.confidence:.2f}") for t in traces}
    rows: list[Sequence[object]] = [["requirement", *codes]]
    for req in sorted(requirements, key=lambda r: r.id):
        rows.append([req.id, *[cell.get((req.id, c), "") for c in codes]])
    return _csv(rows)


def report(requirements: Sequence[Artifact], traces: Sequence[TraceabilityLink]) -> dict:
    """Requirements that need attention, split by reason.

    * ``orphans``: never linked to any code.
    * ``broken``: had links, but all of them decayed.
    * ``weak``: linked, but the best verified link is below ``LOW_CONFIDENCE``.
    * ``decayed_links``: every decayed link (the edge is kept; this is the list to fix).
    """
    scores = {r.requirement_id: r for r in completeness_scores(requirements, traces)}
    text = {r.id: r.text for r in requirements}
    best: dict[str, float] = {}
    for t in traces:
        if t.status == "verified":
            best[t.source_id] = max(best.get(t.source_id, 0.0), t.confidence)

    def row(rid: str) -> dict:
        return {"requirement": rid, "text": (text.get(rid) or "")[:300], "score": scores[rid].score}

    ids = sorted(scores)
    return {
        "requirements": len(ids),
        "orphans": [row(i) for i in ids if scores[i].is_orphan and not scores[i].is_broken],
        "broken": [row(i) for i in ids if scores[i].is_broken],
        "weak": [{**row(i), "best_confidence": round(best[i], 3)} for i in ids if i in best and best[i] < LOW_CONFIDENCE],
        "decayed_links": [
            {"requirement": t.source_id, "code_entity": t.target_id, "confidence": round(t.confidence, 3), "reason": t.justification}
            for t in sorted(traces, key=lambda t: (t.source_id, t.target_id))
            if t.status == "decayed"
        ],
    }
