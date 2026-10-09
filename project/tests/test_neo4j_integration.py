"""Integration tests against a REAL Neo4j (skipped automatically if none is reachable).

All test data uses ids starting with ``__c4test__`` and is removed afterwards; the tests never
touch other nodes. They exercise the real Cypher in shared/uskg/client.py, which the mocked
unit tests cannot.
"""

import time
from unittest.mock import MagicMock

import pytest
from dotenv import load_dotenv

from agents.traceability_agent.decay import DecayDetector
from agents.traceability_agent.utils import content_hash
from shared.schemas.traceability import Artifact, TraceabilityLink
from shared.uskg.client import USKGClient

load_dotenv()
P = "__c4test__"


@pytest.fixture(scope="module")
def uskg():
    try:
        client = USKGClient()
        client._driver.verify_connectivity()
    except Exception as exc:  # no Neo4j / bad credentials
        pytest.skip(f"Neo4j not available: {type(exc).__name__}")
    client.ensure_schema()
    yield client
    client.close()


def _purge(uskg: USKGClient) -> None:
    for query in (
        f"MATCH (d:DecayFlag) WHERE d.codeEntityId STARTS WITH '{P}' DETACH DELETE d",
        f"MATCH (n) WHERE (n:Requirement OR n:CodeEntity) AND n.id STARTS WITH '{P}' DETACH DELETE n",
    ):
        uskg._driver.execute_query(query)


@pytest.fixture
def graph(uskg):
    """Two test requirements and two test code entities, created as C1/C2 would."""
    _purge(uskg)
    uskg._driver.execute_query(
        "CREATE (:Requirement {id: $r1, text: 'Tokens expire after 15 minutes.'}),"
        "(:Requirement {id: $r2, text: 'Unrelated requirement.'}),"
        "(:CodeEntity {id: $c1, text: 'TOKEN_TTL_SECONDS = 900', kind: 'code'}),"
        "(:CodeEntity {id: $c2, text: 'def render(): pass', kind: 'design'})",
        r1=P + "R1", r2=P + "R2", c1=P + "C1", c2=P + "C2",
    )
    yield
    _purge(uskg)


def link(**kw) -> TraceabilityLink:
    base = dict(source_id=P + "R1", target_id=P + "C1", link_type="requirement_to_code",
                confidence=0.9, justification="implements expiry", text_hash="h1")
    base.update(kw)
    return TraceabilityLink(**base)


def edges(uskg):
    records, _, _ = uskg._driver.execute_query(
        f"MATCH (r)-[v:VERIFIED_TRACE]->(c) WHERE r.id STARTS WITH '{P}' RETURN count(v) AS n")
    return records[0]["n"]


def test_get_artifacts_reads_requirements_and_code_by_kind(uskg, graph):
    reqs = {a.id: a for a in uskg.get_artifacts("requirement") if a.id.startswith(P)}
    assert set(reqs) == {P + "R1", P + "R2"} and reqs[P + "R1"].type == "requirement"
    assert reqs[P + "R1"].text.startswith("Tokens expire")
    code = [a.id for a in uskg.get_artifacts("code") if a.id.startswith(P)]
    design = [a.id for a in uskg.get_artifacts("design") if a.id.startswith(P)]
    assert code == [P + "C1"] and design == [P + "C2"]


def test_write_link_is_idempotent_and_updates_in_place(uskg, graph):
    assert uskg.write_link(link()) is True
    assert uskg.write_link(link(confidence=0.7, justification="updated")) is True
    assert edges(uskg) == 1  # MERGE: no duplicate edge
    (stored,) = [t for t in uskg.get_traces() if t.source_id.startswith(P)]
    assert stored.confidence == pytest.approx(0.7) and stored.justification == "updated"
    assert stored.status == "verified" and stored.text_hash == "h1"
    assert stored.verified_at is not None and stored.last_checked_at is not None
    assert stored.verified_at <= stored.last_checked_at


def test_write_link_to_missing_node_writes_nothing(uskg, graph):
    assert uskg.write_link(link(target_id=P + "DOES_NOT_EXIST")) is False
    assert edges(uskg) == 0


def test_mark_decayed_keeps_edge_and_creates_flag(uskg, graph):
    uskg.write_link(link(confidence=0.88))
    assert uskg.mark_decayed(link(), new_confidence=0.4, reason="code changed") is True
    (stored,) = [t for t in uskg.get_traces() if t.source_id.startswith(P)]
    assert stored.status == "decayed" and stored.confidence == pytest.approx(0.4)
    flags, _, _ = uskg._driver.execute_query(
        "MATCH (r:Requirement {id: $r})-[:HAS_DECAY]->(d:DecayFlag) RETURN d.previousConfidence AS prev, "
        "d.reason AS reason, d.codeEntityId AS code, d.flaggedAt AS at", r=P + "R1")
    assert len(flags) == 1
    assert flags[0]["prev"] == pytest.approx(0.88) and flags[0]["reason"] == "code changed"
    assert flags[0]["code"] == P + "C1" and flags[0]["at"] is not None
    assert [t.source_id for t in uskg.get_traces(status="verified") if t.source_id.startswith(P)] == []


def test_decay_detector_end_to_end_on_real_graph(uskg, graph):
    req = next(a for a in uskg.get_artifacts("requirement") if a.id == P + "R1")
    code = next(a for a in uskg.get_artifacts("code") if a.id == P + "C1")
    uskg.write_link(link(text_hash=content_hash(req, code)))

    llm = MagicMock()
    llm.verify_link.return_value = {"is_linked": True, "confidence": 0.9, "reasoning": "ok"}
    publisher = MagicMock()
    detector = DecayDetector(uskg, llm, publisher=publisher)
    assert [r for r in detector.run() if r.link.source_id.startswith(P)] == []  # unchanged -> no recheck

    # C2 edits the code entity; C4 notices on its next poll and the link no longer holds
    uskg._driver.execute_query("MATCH (c:CodeEntity {id: $c}) SET c.text = 'TOKEN_TTL_SECONDS = 99999'", c=P + "C1")
    llm.verify_link.return_value = {"is_linked": False, "confidence": 0.2, "reasoning": "ttl changed"}
    results = [r for r in detector.run() if r.link.source_id.startswith(P)]
    assert len(results) == 1 and results[0].decayed
    publisher.publish.assert_called_once_with(P + "R1", P + "C1", pytest.approx(0.9), pytest.approx(0.2))
    assert [t.status for t in uskg.get_traces() if t.source_id.startswith(P)] == ["decayed"]
    assert edges(uskg) == 1  # history preserved


def test_write_layer_rejects_statements_on_other_components_types(uskg):
    with pytest.raises(PermissionError):
        uskg._write_count("MATCH (n:Requirement) DETACH DELETE n RETURN 0 AS written", "written")
    with pytest.raises(PermissionError):
        uskg._write_count("MERGE (n:Requirement {id: 'x'}) RETURN 1 AS written", "written")


def test_scales_to_10k_nodes_under_two_seconds(uskg):
    """NFR: >= 10,000 nodes without any query exceeding 2 s."""
    _purge(uskg)
    try:
        uskg._driver.execute_query(
            "UNWIND range(1, 10000) AS i CREATE (:CodeEntity {id: $p + 'N' + toString(i), text: 'x', kind: 'code'})",
            p=P)
        uskg._driver.execute_query(
            "CREATE (:Requirement {id: $p + 'RQ', text: 'req'})", p=P)
        timings = {}
        t = time.perf_counter()
        uskg.write_link(link(source_id=P + "RQ", target_id=P + "N5000"))
        timings["write_link"] = time.perf_counter() - t
        t = time.perf_counter()
        uskg.get_traces()
        timings["get_traces"] = time.perf_counter() - t
        t = time.perf_counter()
        n = len(uskg.get_artifacts("code"))
        timings["get_artifacts(code)"] = time.perf_counter() - t
        assert n >= 10000
        print("timings:", {k: round(v, 3) for k, v in timings.items()})
        assert all(v < 2.0 for v in timings.values()), timings
    finally:
        _purge(uskg)
