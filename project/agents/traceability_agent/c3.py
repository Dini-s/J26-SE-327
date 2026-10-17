"""Validation coverage per requirement, from the RVUs and evidence that Component 3 stores in the graph.

C3 splits a requirement into RVUs (requirement validation units) and attaches ValidationEvidence (tests) to them.
C4 reads that to answer: how much of each linked requirement is actually validated? The value feeds the
completeness score (``evidence_coverage``) and the impact view (which tests to re-run when code changes).
C4 never writes C3's nodes.
"""

from collections import defaultdict
from typing import Any, Optional

PASSING = {"pass", "passed", "success"}


def _rvc_from_summary(summary: Optional[dict[str, Any]]) -> Optional[float]:
    """C3's own RVC figure (0-1) if its AdequacySummary has one; accepts 0.67 or 66.67, any key case."""
    if not summary:
        return None
    for key, value in summary.items():
        if str(key).lower() in ("rvc", "rvc_percent", "rvcpercent"):
            try:
                v = float(str(value).rstrip("%"))
            except ValueError:
                return None
            return min(1.0, v / 100.0 if v > 1.0 else v)
    return None


def coverage_from_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per requirement: RVU count, validated RVUs (at least one passing evidence), coverage 0-1 and the tests.

    ``coverage`` is C3's RVC when the requirement has an AdequacySummary with one (``source: c3_summary``);
    otherwise validated / total RVUs (``source: computed``).
    """
    by_req: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_req[row["requirement"]].append(row)

    out: dict[str, dict[str, Any]] = {}
    for req, rvus in by_req.items():
        validated, tests = 0, []
        for r in rvus:
            evidence = [e for e in (r.get("evidence") or []) if e]
            passing = [e for e in evidence if str(e.get("execution", "")).strip().lower() in PASSING]
            validated += 1 if passing else 0
            for e in evidence:
                tests.append({"rvu": r["rvu"], "id": e.get("id"), "title": e.get("title") or e.get("name") or e.get("id"), "type": e.get("type"), "execution": e.get("execution")})
        summary_rvc = next((v for v in (_rvc_from_summary(r.get("summary")) for r in rvus) if v is not None), None)
        computed = validated / len(rvus)
        out[req] = {
            "rvus": len(rvus),
            "validated": validated,
            "coverage": round(summary_rvc if summary_rvc is not None else computed, 4),
            "source": "c3_summary" if summary_rvc is not None else "computed",
            "tests": tests,
        }
    return out


def evidence_coverage(rows: list[dict[str, Any]]) -> dict[str, float]:
    """The ``{requirement_id: coverage}`` mapping that ``completeness_scores`` expects."""
    return {req: info["coverage"] for req, info in coverage_from_rows(rows).items()}
