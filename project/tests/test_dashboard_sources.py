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


# ---------- pipeline stages, run summaries, offline graph, demo guard ----------
def test_pipeline_stages_follow_a_link_run_and_a_monitor_pass():
    start = ev("run_start", dataset="neo4j", method="link", retrieval="hybrid", top_k=3, sources=["R1", "R2"], n_targets=5)
    shortlist = [ev("shortlist", source_id="R1", targets=[{"id": "C1", "score": 1.0}]), ev("shortlist", source_id="R2", targets=[{"id": "C2", "score": 1.0}])]
    verdicts = [ev("verdict", index=1, source_id="R1", target_id="C1", similarity=1.0, is_linked=True, confidence=0.9, reasoning="r", latency=40.0, kept=True)]
    neo = {"connected": True, "counts": {"verified_traces": 1}}

    def states(events, monitor=()):
        return {s["key"]: s["state"] for s in sources.pipeline_stages(list(events), list(monitor), neo)}

    assert states([])["load"] == "pending"
    mid = states([start] + shortlist + [ev("verify_start", total=2)] + verdicts)
    assert mid["load"] == mid["clean"] == mid["stage1"] == "done"
    assert mid["llm"] == "active" and mid["save"] == "active" and mid["monitor"] == "pending" and mid["score"] == "done"
    end = states([start] + shortlist + [ev("verify_start", total=2)] + verdicts + [ev("run_end", written=True)])
    assert end["llm"] == "done" and end["save"] == "done"
    mon = [ev("run_start", method="monitor"), ev("recheck", source_id="R1", target_id="C1", previous_confidence=0.9, new_confidence=0.2, decayed=True, published=False, reason="x")]
    assert states([start], mon)["monitor"] == "active"
    detail = {s["key"]: s["detail"] for s in sources.pipeline_stages([start], mon, neo)}["monitor"]
    assert "1 re-checked, 1 decayed" in detail


def test_evaluation_runs_do_not_claim_to_save_to_the_graph():
    start = ev("run_start", dataset="itrust", method="full", retrieval="hybrid", top_k=5, sources=["R1"], n_targets=3)
    save = next(s for s in sources.pipeline_stages([start], [], {"connected": False}) if s["key"] == "save")
    assert save["state"] == "skipped"


def test_run_graph_without_gold_labels_does_not_invent_correctness():
    events = [ev("run_start", dataset="neo4j", sources=["R1"], n_targets=2),
              ev("shortlist", source_id="R1", targets=[{"id": "C1", "score": 1.0}, {"id": "C2", "score": 0.5}]),
              ev("verdict", index=1, source_id="R1", target_id="C1", similarity=1.0, is_linked=True, confidence=0.9, reasoning="a", latency=1.0, kept=True),
              ev("verdict", index=2, source_id="R1", target_id="C2", similarity=0.5, is_linked=False, confidence=0.1, reasoning="b", latency=1.0, kept=False)]
    graph = sources.build_run_graph(events, {}, set())
    assert {e["to"][2:]: e["category"] for e in graph["edges"]} == {"C1": "verified", "C2": "rejected"}
    assert all(e["truth"] is None for e in graph["edges"])


def test_file_graph_builds_an_offline_preview_from_processed_data():
    graph = sources.file_graph("cm1", max_requirements=3)
    kinds = {n["kind"] for n in graph["nodes"]}
    assert graph["source"] == "files" and kinds <= {"requirement", "code"} and "requirement" in kinds
    assert all(e["category"] == "truth" for e in graph["edges"])


def test_demo_is_refused_for_a_non_local_database_and_when_disabled(monkeypatch):
    from apps.api import demo

    monkeypatch.setenv("NEO4J_URI", "bolt://db.example.com:7687")
    assert not demo.allowed()["allowed"] and "not local" in demo.allowed()["reason"]
    with __import__("pytest").raises(demo.DemoError):
        demo.reset()
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    assert demo.allowed()["allowed"]
    monkeypatch.setenv("DASHBOARD_ALLOW_DEMO", "0")
    assert not demo.allowed()["allowed"]


def test_demo_reset_only_touches_c4_types_and_demo_nodes(monkeypatch):
    from unittest.mock import MagicMock

    from apps.api import demo

    queries = []
    driver = MagicMock()
    driver.__enter__.return_value = driver

    def run(query, **kw):
        queries.append(query)
        summary = MagicMock()
        summary.counters.relationships_deleted = 3
        summary.counters.nodes_deleted = 2
        summary.counters.properties_set = 4
        return [], summary, []

    driver.execute_query.side_effect = run
    monkeypatch.setattr(demo, "_neo4j_driver", lambda: driver)
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    result = demo.reset()
    assert result == {"deleted_links": 3, "deleted_flags": 2, "restored_texts": 2}
    joined = " ".join(queries)
    assert "DELETE v" in joined and "DETACH DELETE d" in joined
    assert "dataset IS NOT NULL" in joined  # text restore only on demo nodes
    assert not any(q.strip().startswith("MATCH (n:Requirement") for q in queries)


def test_stages_and_runs_are_marked_interrupted_when_nothing_is_running(tmp_path, monkeypatch):
    start = ev("run_start", dataset="neo4j", method="link", retrieval="hybrid", top_k=3, sources=["R1"], n_targets=2)
    stages = {s["key"]: s["state"] for s in sources.pipeline_stages([start, ev("verify_start", total=2)], [], {"connected": False}, interrupted=True)}
    assert stages["llm"] == "interrupted" and "active" not in stages.values()
    run = tmp_path / "20260101-000000-link-hybrid-top3"
    run.mkdir()
    (run / "events.jsonl").write_text(json.dumps(start) + "\n" + json.dumps(ev("verify_start", total=2)) + "\n")
    monkeypatch.setattr(sources, "RUNS_DIR", tmp_path)
    assert sources.runs_summary(idle=False)[0]["state"] == "verifying"
    assert sources.runs_summary(idle=True)[0]["state"] == "interrupted"


def test_with_one_process_running_only_the_newest_unfinished_run_is_live(tmp_path, monkeypatch):
    start = ev("run_start", dataset="neo4j", method="link", retrieval="hybrid", top_k=3, sources=["R1"], n_targets=2)
    for name in ("20260101-000000-link-a", "20260102-000000-link-b"):
        d = tmp_path / name
        d.mkdir()
        (d / "events.jsonl").write_text(json.dumps(start) + "\n" + json.dumps(ev("verify_start", total=2)) + "\n")
    monkeypatch.setattr(sources, "RUNS_DIR", tmp_path)
    states = {r["id"]: r["state"] for r in sources.runs_summary(idle=False)}
    assert states["20260102-000000-link-b"] == "verifying" and states["20260101-000000-link-a"] == "interrupted"


def test_add_requirement_validates_text_and_id(monkeypatch):
    import pytest as _pytest

    from apps.api import demo

    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    with _pytest.raises(demo.DemoError, match="full sentence"):
        demo.add_requirement("too short")
    with _pytest.raises(demo.DemoError, match="id may only"):
        demo.add_requirement("The system shall do something useful for the user.", "bad id;")
    monkeypatch.setenv("NEO4J_URI", "bolt://db.example.com:7687")
    with _pytest.raises(demo.DemoError, match="not local"):
        demo.add_requirement("The system shall do something useful for the user.")


def test_demo_undo_restores_texts_and_undecays_only_c4_data(monkeypatch):
    from unittest.mock import MagicMock

    from apps.api import demo

    queries = []
    driver = MagicMock()
    driver.__enter__.return_value = driver

    def run(query, **kw):
        queries.append(query)
        summary = MagicMock()
        summary.counters.properties_set = 4
        summary.counters.nodes_deleted = 1
        return [], summary, []

    driver.execute_query.side_effect = run
    monkeypatch.setattr(demo, "_neo4j_driver", lambda: driver)
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    assert demo.undo_changes() == {"restored_texts": 2, "flags_removed": 1}
    joined = " ".join(queries)
    assert "dataset IS NOT NULL" in joined and "original_text" in joined
    assert "SET v.status = 'verified'" in joined and "DETACH DELETE f" in joined
    assert "DELETE v" not in joined.replace("DETACH DELETE f", "")  # never deletes links
    assert "Requirement)" not in joined.split("DETACH DELETE f")[-1]
