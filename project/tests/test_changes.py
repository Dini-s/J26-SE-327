"""A commit should cost LLM calls only for the links it touches."""

import pytest

from agents.traceability_agent.changes import ChangeError, apply_change, parse_change
from agents.traceability_agent.utils import content_hash
from shared.schemas.traceability import Artifact, TraceabilityLink
from shared.uskg.memory import InMemoryUSKG


class CountingLLM:
    def __init__(self, linked=True, confidence=0.9):
        self.calls, self.linked, self.confidence = [], linked, confidence

    def verify_link(self, requirement, target):
        self.calls.append((requirement.id, target.id))
        return {"is_linked": self.linked, "confidence": self.confidence, "reasoning": "r"}


def _store():
    reqs = [Artifact(id=f"R{i}", type="requirement", text=f"requirement {i}", metadata={"dataset": "p1"}) for i in (1, 2)]
    reqs.append(Artifact(id="R9", type="requirement", text="other project", metadata={"dataset": "p2"}))
    code = [Artifact(id=f"C{i}", type="code", text=f"code {i}", metadata={"dataset": "p1"}) for i in (1, 2)]
    code.append(Artifact(id="C9", type="code", text="other", metadata={"dataset": "p2"}))
    store = InMemoryUSKG(reqs + code)
    for r, c in [("R1", "C1"), ("R2", "C2"), ("R9", "C9")]:
        link = TraceabilityLink(source_id=r, target_id=c, link_type="requirement_to_code", confidence=0.9, justification="j", status="verified")
        store.write_link(link.model_copy(update={"text_hash": content_hash(store.artifacts[r], store.artifacts[c])}))
    return store


def test_parse_change_accepts_json_and_rejects_bad_input():
    change = parse_change('{"project": "p1", "changed": ["a.java", "a.java", "b.java"], "requirementsAdded": ["R3"]}')
    assert change.changed == ("a.java", "b.java") and change.requirements_added == ("R3",) and change.project == "p1"
    for bad in ('not json', '[]', '{}', '{"changed": "a.java"}', '{"changed": [1]}', '{"changed": ["a b"]}', '{"project": 5, "changed": ["a"]}'):
        with pytest.raises(ChangeError):
            parse_change(bad)


def test_only_links_to_changed_files_are_rechecked(tmp_path):
    store = _store()
    store.artifacts["C1"] = store.artifacts["C1"].model_copy(update={"text": "code 1 rewritten"})
    store.artifacts["C2"] = store.artifacts["C2"].model_copy(update={"text": "code 2 rewritten"})  # changed but not in the commit
    llm = CountingLLM(linked=False, confidence=0.1)
    result = apply_change(parse_change({"project": "p1", "changed": ["C1"]}), store, llm, embedder=None, runs_dir=tmp_path)
    assert llm.calls == [("R1", "C1")]  # C2 changed too, but the commit did not touch it
    assert result["rechecked"] == 1 and result["decayed"] == 1
    assert store.traces[("R1", "C1")].status == "decayed" and store.traces[("R2", "C2")].status == "verified"


def test_other_projects_are_left_alone(tmp_path):
    store = _store()
    store.artifacts["C9"] = store.artifacts["C9"].model_copy(update={"text": "changed"})
    llm = CountingLLM()
    apply_change(parse_change({"project": "p1", "changed": ["C9"]}), store, llm, embedder=None, runs_dir=tmp_path)
    assert llm.calls == []


def test_touched_but_unchanged_file_costs_nothing(tmp_path):
    llm = CountingLLM()
    result = apply_change(parse_change({"project": "p1", "changed": ["C1"]}), _store(), llm, embedder=None, runs_dir=tmp_path)
    assert llm.calls == [] and result["rechecked"] == 0


def test_new_requirement_is_linked_but_existing_links_are_not_redone(tmp_path):
    store = _store()
    store.artifacts["R3"] = Artifact(id="R3", type="requirement", text="requirement 1 code", metadata={"dataset": "p1"})
    llm = CountingLLM()
    result = apply_change(parse_change({"project": "p1", "requirementsAdded": ["R3"]}), store, llm, embedder=None,
                          runs_dir=tmp_path, top_k=2, retrieval="tfidf")
    assert {c[0] for c in llm.calls} == {"R3"} and result["linked"] == len(llm.calls) == 2
    assert all(t[0] != "R3" or t[1] in ("C1", "C2") for t in store.traces)  # never links into project p2
