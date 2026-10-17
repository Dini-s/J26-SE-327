"""React to a repository change (a commit) instead of re-checking everything.

In the full system C2 watches the repository and tells C4 what a commit touched. This module is
C4's side of that: given the ids of changed / added code entities (and newly added requirements)
it re-verifies only the links that depend on them and looks for links only where something is new.

The message shape is an ASSUMPTION until confirmed with C2::

    {"event": "code_changed", "project": "<repo>", "changed": ["<code id>", ...],
     "added": ["<code id>", ...], "requirementsAdded": ["<requirement id>", ...],
     "requirementsChanged": ["<requirement id>", ...]}

A stand-in for C2 (the dashboard's "Make a commit" button, or ``cli changed``) produces the same call.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from agents.traceability_agent.decay import DecayDetector
from agents.traceability_agent.run_log import RunLogger

_ID = re.compile(r"[^\s\x00-\x1f]{1,200}")  # code ids are file paths / class names, so be permissive but bounded
MAX_IDS = 500


class ChangeError(ValueError):
    """The change message is malformed."""


@dataclass(frozen=True)
class ChangeSet:
    """What one commit (or batch of commits) did, as far as C4 cares."""

    project: Optional[str] = None
    changed: tuple[str, ...] = ()  # code entities whose text changed: re-check their links
    added: tuple[str, ...] = ()  # new code entities: look for requirements they implement
    requirements_added: tuple[str, ...] = ()  # new requirements: look for code that implements them
    requirements_changed: tuple[str, ...] = ()  # edited requirements: re-check the links they already have

    def is_empty(self) -> bool:
        return not (self.changed or self.added or self.requirements_added or self.requirements_changed)


def _ids(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or len(value) > MAX_IDS:
        raise ChangeError(f"{name} must be a list of at most {MAX_IDS} ids")
    if not all(isinstance(v, str) and _ID.fullmatch(v) for v in value):
        raise ChangeError(f"{name} contains an invalid id")
    return tuple(dict.fromkeys(value))  # de-duplicated, order kept


def parse_change(payload: Union[str, bytes, dict[str, Any]]) -> ChangeSet:
    """Validate a change message (JSON text or dict) and turn it into a ``ChangeSet``.

    Raises:
        ChangeError: If it is not JSON, not an object, names unknown keys' wrong types, or has no ids.
    """
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ChangeError(f"not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ChangeError("a change message must be a JSON object")
    project = payload.get("project")
    if project is not None and not (isinstance(project, str) and _ID.fullmatch(project)):
        raise ChangeError("project must be a string")
    change = ChangeSet(
        project=project,
        changed=_ids(payload.get("changed"), "changed"),
        added=_ids(payload.get("added"), "added"),
        requirements_added=_ids(payload.get("requirementsAdded", payload.get("requirements_added")), "requirementsAdded"),
        requirements_changed=_ids(payload.get("requirementsChanged", payload.get("requirements_changed")), "requirementsChanged"),
    )
    if change.is_empty():
        raise ChangeError("the change lists no files and no requirements")
    return change


def apply_change(
    change: ChangeSet,
    uskg: Any,
    llm: Any,
    embedder: Any,
    runs_dir: Path,
    publisher: Optional[Any] = None,
    top_k: int = 3,
    retrieval: str = "hybrid",
) -> dict[str, Any]:
    """Handle one change: re-check affected links, then link anything new.

    Each part writes its own run log, so the dashboard shows the decay pass and the linking run as it
    does for a manual run. Returns a small summary (counts only).
    """
    from agents.traceability_agent.agent import TraceabilityAgent

    summary: dict[str, Any] = {"project": change.project, "rechecked": 0, "decayed": 0, "linked": 0, "candidates": 0}
    if change.changed or change.requirements_changed:
        logger = RunLogger.new(runs_dir, "change-monitor")
        logger.emit("run_start", method="monitor", force=False, redis=publisher is not None,
                    project=change.project, trigger="code_changed" if change.changed else "requirement_changed",
                    changed=list(change.changed), requirements_changed=list(change.requirements_changed))
        results = DecayDetector(uskg, llm, publisher=publisher, run_logger=logger).run(
            project=change.project,
            only_targets=set(change.changed) if change.changed else None,
            only_sources=set(change.requirements_changed) if change.requirements_changed else None)
        summary["rechecked"] = len(results)
        summary["decayed"] = sum(1 for r in results if r.decayed)
        logger.emit("pass_end", rechecked=summary["rechecked"], decayed=summary["decayed"])
        logger.emit("run_end", rechecked=summary["rechecked"], decayed=summary["decayed"])

    if change.added or change.requirements_added:
        logger = RunLogger.new(runs_dir, f"link-{retrieval}-top{top_k}")
        agent = TraceabilityAgent(uskg=uskg, embedder=embedder, llm=llm, retrieval=retrieval, top_k=top_k,
                                  run_logger=logger, project=change.project)
        sources, targets = agent.load_artifacts()
        new_reqs, new_code = set(change.requirements_added), set(change.added)
        if not new_code:  # only new requirements: nothing else needs ranking
            sources = [a for a in sources if a.id in new_reqs]
        existing = {(t.source_id, t.target_id) for t in uskg.get_traces()}
        logger.emit("run_start", dataset="neo4j", method="link", retrieval=retrieval, prompt="expert", top_k=top_k,
                    sources=[a.id for a in sources], n_targets=len(targets),
                    gold_pairs=0, true_links=0, project=change.project, trigger="code_changed")
        # a new requirement is matched against every file; a new file is matched against every requirement
        # (shortlisted per requirement, so a new file only appears if it ranks in that requirement's top-k)
        candidates = agent.find_candidates(sources, targets)
        candidates = [
            c for c in candidates
            if (c.source.id in new_reqs or c.target.id in new_code) and (c.source.id, c.target.id) not in existing
        ]
        summary["candidates"] = len(candidates)
        links = agent.verify_candidates(candidates, on_link=uskg.write_link)
        summary["linked"] = len(links)
        logger.emit("run_end", metrics={}, links=len(links), written=True)
    return summary
