"""Dashboard data layer: run-log parsing, live metrics and graph categories (no server needed)."""

import json

from apps.api import sources

TRUTH = {("R1", "C1"), ("R1", "C2"), ("R2", "C9")}


def ev(type_, **kw):
    return {"type": type_, "ts": "2026-01-01T00:00:00+00:00", **kw}


EVENTS = [
    ev("run_start", dataset="d", retrieval="hybrid", top_k=3, sources=["R1", "R2"], n_targets=10),
    ev("shortlist", source_id="R1", targets=[{"id": "C1", "score": 2.0}, {"id": "C2", "score": 1.0}, {"id": "C3", "score": 0.5}]),
    ev("shortlist", source_id="R2", targets=[{"id": "C4", "score": 1.5}]),
    ev("verify_start", total=4),
    ev("verdict", index=1, source_id="R1", target_id="C1", similarity=2.0, is_linked=True, confidence=0.9, reasoning="a", latency=40.0, kept=True),
    ev("verdict", index=2, source_id="R1", target_id="C2", similarity=1.0, is_linked=False, confidence=0.2, reasoning="b", latency=60.0, kept=False),
    ev("verdict", index=3, source_id="R1", target_id="C3", similarity=0.5, is_linked=True, confidence=0.8, reasoning="c", latency=50.0, kept=True),
]


def test_summarize_run_live_metrics_and_stage1_ceiling():
    s = sources.summarize_run(EVENTS, TRUTH)
    assert s["state"] == "verifying" and (s["done"], s["total"]) == (3, 4)
    assert (s["tp"], s["fp"], s["fn"]) == (1, 1, 2)  # C1 correct, C3 wrong; C2 and R2->C9 not kept
    assert s["precision"] == 0.5 and abs(s["recall"] - 1 / 3) < 1e-9
    assert s["true_links"] == 3 and s["shortlisted_true"] == 2  # R2->C9 was never shortlisted
    assert s["mean_latency"] == 50.0


def test_summarize_run_states():
    assert sources.summarize_run([], TRUTH) == {"state": "none"}
    assert sources.summarize_run(EVENTS[:3], TRUTH)["state"] == "shortlisting"
    assert sources.summarize_run(EVENTS + [ev("run_end", metrics={})], TRUTH)["state"] == "finished"


def test_run_graph_edge_categories():
    graph = sources.build_run_graph(EVENTS, {"R1": {"text": "req one"}}, TRUTH)
    cat = {(e["from"][2:], e["to"][2:]): e["category"] for e in graph["edges"]}
    assert cat[("R1", "C1")] == "verified_correct"
    assert cat[("R1", "C2")] == "rejected_true"
    assert cat[("R1", "C3")] == "verified_wrong"
    assert cat[("R2", "C4")] == "pending"
    assert cat[("R2", "C9")] == "missed"
    kinds = {n["id"]: n["kind"] for n in graph["nodes"]}
    assert kinds["r:R1"] == "requirement" and kinds["c:C1"] == "code"
    assert next(n for n in graph["nodes"] if n["id"] == "r:R1")["text"] == "req one"


def test_read_events_ignores_half_written_line_and_latest_run_picks_newest(tmp_path):
    old, new = tmp_path / "20260101-000000-a", tmp_path / "20260102-000000-b"
    for d in (old, new):
        d.mkdir()
    (old / "events.jsonl").write_text(json.dumps(EVENTS[0]) + "\n")
    (new / "events.jsonl").write_text(json.dumps(EVENTS[0]) + "\n" + '{"type": "shortl')
    assert sources.latest_run_dir(tmp_path) == new
    assert len(sources.read_events(new)) == 1
    assert sources.latest_run_dir(tmp_path / "missing") is None


def test_neo4j_status_reports_offline_without_raising(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://127.0.0.1:1")
    sources._neo_cache.update(at=0.0, value=None)
    status = sources.neo4j_status(ttl=0)
    assert status["connected"] is False and "error" in status


def test_llm_status_not_configured(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert sources.llm_status() == {"configured": False}


def test_vetted_write_statements_pass_the_ownership_guard():
    import pytest as _pytest

    from shared.uskg import client

    for query in client._WRITE_QUERIES:
        client.validate_write_query(query)
    for bad in ("MATCH (n) DETACH DELETE n", "MERGE (n:CodeEntity {id: 'x'})", "CREATE (n:Requirement)"):
        with _pytest.raises(PermissionError):
            client.validate_write_query(bad)


def test_neo4j_completeness_shape(monkeypatch):
    from unittest.mock import MagicMock

    from shared.schemas.traceability import Artifact, TraceabilityLink

    uskg = MagicMock()
    uskg.__enter__.return_value = uskg
    uskg.get_artifacts.return_value = [Artifact(id="R1", type="requirement", text="a"), Artifact(id="R2", type="requirement", text="b")]
    uskg.get_traces.return_value = [TraceabilityLink(source_id="R1", target_id="C1", link_type="t", confidence=0.8, justification="j")]
    monkeypatch.setattr("shared.uskg.client.USKGClient", lambda: uskg)
    result = sources.neo4j_completeness()
    assert result["orphans"] == ["R2"] and result["requirements"] == 2
    assert result["rows"][0]["requirement_id"] == "R2" and abs(result["mean_score"] - 40.0) < 1e-9
