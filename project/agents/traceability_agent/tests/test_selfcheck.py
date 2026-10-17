"""Self-check: each check catches the problem it is for."""

from agents.traceability_agent.selfcheck import run_selfcheck
from shared.schemas.traceability import Artifact, TraceabilityLink

CODE = "public class A {\n  void retryThree() { for (int i = 0; i < 3; i++) call(); }\n}"
REQ1 = Artifact(id="R1", type="requirement", text="Retry three times.")
REQ2 = Artifact(id="R2", type="requirement", text="Other.")
A = Artifact(id="A.java", type="code", text=CODE)


def link(r, c, conf=0.9, status="verified", why="ok"):
    return TraceabilityLink(source_id=r, target_id=c, link_type="requirement_to_code", confidence=conf, status=status, justification=why)


def by_id(report):
    return {c["id"]: c for c in report["checks"]}


def test_clean_graph_passes_everything():
    why = 'retryThree() loops. Evidence: "for (int i = 0; i < 3; i++) call();"'
    rep = run_selfcheck([REQ1, REQ2], [A], [link("R1", "A.java", why=why)], flags=[])
    assert rep["summary"]["fail"] == 0 and rep["summary"]["warn"] == 0
    assert by_id(rep)["quote_in_code"]["checked"] == 1 and by_id(rep)["names_in_code"]["checked"] == 1


def test_missing_endpoints_duplicates_and_bad_confidence_fail():
    rep = run_selfcheck([REQ1], [A], [link("R1", "Gone.java"), link("R1", "A.java"), TraceabilityLink.model_construct(source_id="R1", target_id="A.java", link_type="requirement_to_code", confidence=1.5, status="verified", justification="x")])
    c = by_id(rep)
    assert c["endpoints_exist"]["status"] == "fail" and c["endpoints_exist"]["items"] == ["R1 -> Gone.java"]
    assert c["no_duplicates"]["status"] == "fail"
    assert c["confidence_range"]["status"] == "fail"


def test_link_to_code_that_is_no_longer_there_is_caught():
    emptied = Artifact(id="A.java", type="code", text="package a;\nimport b.C;")
    why = 'retryThree() loops. Evidence: "for (int i = 0; i < 3; i++) call();"'
    rep = run_selfcheck([REQ1], [emptied], [link("R1", "A.java", why=why)])
    c = by_id(rep)
    assert c["targets_have_code"]["status"] == "fail"
    assert c["quote_in_code"]["status"] == "fail" and c["names_in_code"]["status"] == "warn"


def test_weak_verified_and_unflagged_decay_warn():
    rep = run_selfcheck([REQ1, REQ2], [A], [link("R1", "A.java", conf=0.3), link("R2", "A.java", status="decayed")], flags=[])
    c = by_id(rep)
    assert c["verified_above_threshold"]["status"] == "warn"
    assert c["decayed_have_flags"]["status"] == "warn" and c["decayed_have_flags"]["items"] == ["R2 -> A.java"]


def test_gold_comparison_reports_precision_and_recall_on_processed_requirements():
    reqs = [REQ1, REQ2, Artifact(id="R3", type="requirement", text="Third.")]
    traces = [link("R1", "A.java"), link("R2", "A.java")]
    rep = run_selfcheck(reqs, [A], traces, gold=[("R1", "A.java"), ("R2", "B.java"), ("R3", "A.java")])
    g = rep["gold"]
    assert g["verified_links"] == 2 and g["correct"] == 1 and g["precision"] == 0.5
    assert g["gold_links_of_processed_requirements"] == 2 and g["recall"] == 0.5  # R3 was never processed
    assert g["requirements_processed"] == 2 and g["requirements"] == 3
