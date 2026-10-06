"""Completeness score and orphan detection."""

import pytest

from agents.traceability_agent.completeness import completeness_scores
from shared.schemas.traceability import Artifact, TraceabilityLink


def req(i: str) -> Artifact:
    return Artifact(id=i, type="requirement", text=i)


def trace(src: str, tgt: str, conf: float, status: str = "verified") -> TraceabilityLink:
    return TraceabilityLink(
        source_id=src, target_id=tgt, link_type="requirement_to_code",
        confidence=conf, justification="j", status=status,
    )


def test_requirement_without_links_is_orphan_with_zero_score():
    (r,) = completeness_scores([req("R1")], [])
    assert r.is_orphan and r.score == 0.0 and r.trace_confidence is None


def test_decayed_links_do_not_count():
    (r,) = completeness_scores([req("R1")], [trace("R1", "C1", 0.9, status="decayed")])
    assert r.is_orphan


def test_trace_only_score_uses_mean_confidence():
    (r,) = completeness_scores([req("R1")], [trace("R1", "C1", 0.8), trace("R1", "C2", 0.6)])
    assert not r.is_orphan
    assert r.score == pytest.approx(70.0)
    assert r.evidence_coverage is None


def test_score_combines_trace_confidence_with_evidence():
    (r,) = completeness_scores([req("R1")], [trace("R1", "C1", 0.9)], {"R1": 0.5})
    assert r.score == pytest.approx(100 * (0.6 * 0.9 + 0.4 * 0.5))


def test_evidence_is_clamped_and_other_requirements_unaffected():
    a, b = completeness_scores(
        [req("R1"), req("R2")], [trace("R1", "C1", 1.0), trace("R2", "C2", 0.5)], {"R1": 7.0}
    )
    assert a.evidence_coverage == 1.0 and a.score == pytest.approx(100.0)
    assert b.evidence_coverage is None and b.score == pytest.approx(50.0)
