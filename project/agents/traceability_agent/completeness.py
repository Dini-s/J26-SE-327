"""Traceability completeness score and orphan detection."""

from typing import Mapping, Optional, Sequence

from agents.traceability_agent.config import EVIDENCE_WEIGHT, TRACE_WEIGHT
from shared.schemas.traceability import Artifact, CompletenessResult, TraceabilityLink


def completeness_scores(
    requirements: Sequence[Artifact],
    traces: Sequence[TraceabilityLink],
    evidence_coverage: Optional[Mapping[str, float]] = None,
) -> list[CompletenessResult]:
    """Score how trustworthy each requirement's traceability currently is.

    * A requirement with no ``verified`` link is an orphan and scores 0
      (decayed links do not count as valid traces).
    * Otherwise: ``100 * (TRACE_WEIGHT * mean verified-link confidence +
      EVIDENCE_WEIGHT * evidence coverage)``. If no C3 evidence figure is
      available for the requirement, the score is ``100 * mean confidence`` so
      it is not penalised for data that doesn't exist yet.

    Args:
        requirements: Requirements to score.
        traces: All ``VERIFIED_TRACE`` links (any status).
        evidence_coverage: Per-requirement fraction in ``[0, 1]`` of validation
            units backed by passing evidence, supplied from C3's data.

    Returns:
        One result per requirement, in input order.
    """
    evidence_coverage = evidence_coverage or {}
    results: list[CompletenessResult] = []
    for req in requirements:
        valid = [t for t in traces if t.source_id == req.id and t.status == "verified"]
        if not valid:
            results.append(CompletenessResult(requirement_id=req.id, score=0.0, is_orphan=True))
            continue
        trace_conf = sum(t.confidence for t in valid) / len(valid)
        evidence = evidence_coverage.get(req.id)
        if evidence is None:
            score = 100.0 * trace_conf
        else:
            evidence = min(max(evidence, 0.0), 1.0)
            score = 100.0 * (TRACE_WEIGHT * trace_conf + EVIDENCE_WEIGHT * evidence)
        results.append(
            CompletenessResult(
                requirement_id=req.id,
                score=round(score, 2),
                is_orphan=False,
                trace_confidence=trace_conf,
                evidence_coverage=evidence,
            )
        )
    return results
