"""C3 validation coverage (rows as the graph query returns them)."""

from agents.traceability_agent.c3 import coverage_from_rows, evidence_coverage
from agents.traceability_agent.completeness import completeness_scores
from shared.schemas.traceability import Artifact, TraceabilityLink


def row(rvu, evidence, summary=None, req="R1"):
    return {"requirement": req, "rvu": rvu, "description": "", "evidence": evidence, "summary": summary}


PASS = {"id": "MT-1", "execution": "PASS", "type": "MANUAL_TEST", "title": "t"}
FAIL = {"id": "MT-2", "execution": "FAIL"}


def test_coverage_counts_rvus_with_passing_evidence():
    info = coverage_from_rows([row("V1", [PASS]), row("V2", [FAIL]), row("V3", [])])["R1"]
    assert (info["rvus"], info["validated"], info["source"]) == (3, 1, "computed")
    assert info["coverage"] == round(1 / 3, 4)
    assert [t["id"] for t in info["tests"]] == ["MT-1", "MT-2"]


def test_c3_own_rvc_is_preferred_and_percent_is_normalised():
    rows = [row("V1", [PASS], {"RVC": "66.67%"}), row("V2", [])]
    info = coverage_from_rows(rows)["R1"]
    assert info["source"] == "c3_summary" and info["coverage"] == 0.6667
    assert coverage_from_rows([row("V1", [], {"rvc": 0.5})])["R1"]["coverage"] == 0.5


def test_nothing_from_c3_gives_empty_mapping():
    assert coverage_from_rows([]) == {} and evidence_coverage([]) == {}


def test_coverage_feeds_the_completeness_score():
    req = Artifact(id="R1", type="requirement", text="x")
    link = TraceabilityLink(source_id="R1", target_id="C1", link_type="requirement_to_code", confidence=0.8, status="verified", justification="j")
    plain = completeness_scores([req], [link])[0].score
    with_c3 = completeness_scores([req], [link], evidence_coverage([row("V1", [PASS]), row("V2", [])]))[0].score
    assert plain == 80.0 and with_c3 == 100 * (0.6 * 0.8 + 0.4 * 0.5)
