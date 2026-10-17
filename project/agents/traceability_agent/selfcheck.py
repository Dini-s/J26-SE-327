"""Self-check: does C4's own output hold up against the graph and against ground truth?

Every check compares what C4 stored or reported with something it can verify independently, for example
a link whose justification quotes code that is no longer there, a link to a file that is now empty,
or a completeness score that does not match a recomputation. No LLM is used. Each check returns
``pass`` / ``warn`` / ``fail`` with the offending items, so a problem can be traced.
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from agents.traceability_agent.completeness import completeness_scores
from agents.traceability_agent.config import PASS_THRESHOLD
from agents.traceability_agent.decay import MIN_TARGET_CHARS
from agents.traceability_agent.preprocess import llm_text
from shared.schemas.traceability import Artifact, TraceabilityLink

MAX_ITEMS = 10
_QUOTE = re.compile(r'Evidence:\s*"(.+?)"\s*$', re.DOTALL)
_CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\(\)?")
_BACKTICK = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]{2,})`")


def _norm(text: str) -> str:
    return " ".join(text.split())


def _check(cid: str, name: str, items: list[str], total: int, severity: str, ok: str, bad: str) -> dict[str, Any]:
    status = "pass" if not items else severity
    return {
        "id": cid, "name": name, "status": status, "count": len(items), "checked": total,
        "detail": ok if not items else bad.format(n=len(items), total=total),
        "items": items[:MAX_ITEMS],
    }


def _pair(link: TraceabilityLink) -> str:
    return f"{link.source_id} -> {link.target_id}"


def run_selfcheck(
    requirements: Sequence[Artifact],
    targets: Sequence[Artifact],
    traces: Sequence[TraceabilityLink],
    flags: Optional[Iterable[tuple[str, str]]] = None,
    gold: Optional[Iterable[tuple[str, str]]] = None,
) -> dict[str, Any]:
    """Run every check and return ``{"checks": [...], "summary": {...}, "gold": {...} | None}``.

    Args:
        requirements: Requirement artifacts of the project.
        targets: Code / design / test artifacts of the project.
        traces: All ``VERIFIED_TRACE`` links (any status).
        flags: ``(requirement id, code id)`` pairs that have a DecayFlag (None: skip that check).
        gold: ``(requirement id, code id)`` ground-truth links, if the dataset has them.
    """
    req_by_id = {a.id: a for a in requirements}
    tgt_by_id = {a.id: a for a in targets}
    verified = [t for t in traces if t.status != "decayed"]
    checks: list[dict[str, Any]] = []

    missing = [_pair(t) for t in traces if t.source_id not in req_by_id or t.target_id not in tgt_by_id]
    checks.append(_check("endpoints_exist", "Both ends of every link exist", missing, len(traces), "fail",
                         "Every link points at a requirement and a code entity that exist.",
                         "{n} of {total} links point at something that is not in the graph."))

    dup = [f"{k[0]} -> {k[1]}" for k, n in Counter((t.source_id, t.target_id) for t in traces).items() if n > 1]
    checks.append(_check("no_duplicates", "No duplicate links", dup, len(traces), "fail",
                         "No requirement/code pair is linked twice.", "{n} pairs are linked more than once."))

    bad_conf = [_pair(t) for t in traces if not (0.0 <= t.confidence <= 1.0)]
    checks.append(_check("confidence_range", "Confidence is between 0 and 1", bad_conf, len(traces), "fail",
                         "All confidences are valid.", "{n} links have a confidence outside 0 to 1."))

    weak = [f"{_pair(t)} ({t.confidence:.2f})" for t in verified if t.confidence < PASS_THRESHOLD]
    checks.append(_check("verified_above_threshold", "Verified links pass the threshold", weak, len(verified), "warn",
                         f"Every verified link is at or above {PASS_THRESHOLD}.",
                         "{n} verified links are below the pass threshold (likely written before it was changed)."))

    empty = []
    for t in verified:
        tgt = tgt_by_id.get(t.target_id)
        if tgt is not None and len("".join(llm_text(tgt).split())) < MIN_TARGET_CHARS:
            empty.append(_pair(t))
    checks.append(_check("targets_have_code", "Linked files still contain code", empty, len(verified), "fail",
                         "Every verified link points at a file with real content.",
                         "{n} verified links point at a file that is now empty: the link cannot hold."))

    gone_quote, gone_name, quoted, named = [], [], 0, 0
    for t in verified:
        tgt = tgt_by_id.get(t.target_id)
        if tgt is None:
            continue
        body = _norm(tgt.text)
        m = _QUOTE.search(t.justification or "")
        if m:
            quoted += 1
            if _norm(m.group(1)) not in body:
                gone_quote.append(_pair(t))
        names = set(_BACKTICK.findall(t.justification or "")) | set(_CALL.findall(t.justification or ""))
        names = {n for n in names if not n.isupper()}
        if names:
            named += 1
            missing_names = sorted(n for n in names if n.split(".")[-1] not in tgt.text)
            if missing_names:
                gone_name.append(f"{_pair(t)}: {', '.join(missing_names[:3])}")
    checks.append(_check("quote_in_code", "Quoted evidence is still in the code", gone_quote, quoted, "fail",
                         "Every code quote a link relies on is still in its file." if quoted else "No link stores a code quote (older prompt).",
                         "{n} of {total} links rely on a quote that is no longer in the file."))
    checks.append(_check("names_in_code", "Methods named in the reason still exist", gone_name, named, "warn",
                         "Every method or class a reason mentions is still in its file." if named else "No reason names a method.",
                         "{n} of {total} reasons mention a method or class that is not in the file any more."))

    if flags is not None:
        flagged = set(flags)
        no_flag = [_pair(t) for t in traces if t.status == "decayed" and (t.source_id, t.target_id) not in flagged]
        checks.append(_check("decayed_have_flags", "Every decayed link has its flag", no_flag, sum(1 for t in traces if t.status == "decayed"),
                             "warn", "Every decayed link has a DecayFlag explaining it.", "{n} decayed links have no DecayFlag."))

    scores = completeness_scores(list(requirements), [t for t in traces if 0.0 <= t.confidence <= 1.0])  # invalid ones are reported above
    linked_ids = {t.source_id for t in verified}
    mismatch = [s.requirement_id for s in scores if s.is_orphan == (s.requirement_id in linked_ids)]
    zero_not_orphan = [s.requirement_id for s in scores if s.score == 0 and not s.is_orphan]
    bad = sorted(set(mismatch) | set(zero_not_orphan))
    checks.append(_check("score_consistent", "Completeness matches the links", bad, len(scores), "fail",
                         "Orphans are exactly the requirements without a verified link; scores agree.",
                         "{n} requirements have a score that disagrees with their links."))

    out_gold: Optional[dict[str, Any]] = None
    if gold is not None:
        gold_set = set(gold)
        found = {(t.source_id, t.target_id) for t in verified}
        hit = found & gold_set
        processed = {s for s, _ in found} | {t.source_id for t in traces}
        gold_processed = {g for g in gold_set if g[0] in processed}
        p = len(hit) / len(found) if found else 0.0
        r = len(hit) / len(gold_processed) if gold_processed else 0.0
        out_gold = {
            "verified_links": len(found), "correct": len(hit), "precision": round(p, 3),
            "gold_links_of_processed_requirements": len(gold_processed), "recall": round(r, 3),
            "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
            "requirements_processed": len(processed & set(req_by_id)), "requirements": len(req_by_id),
        }

    counts = Counter(c["status"] for c in checks)
    return {
        "checks": checks,
        "summary": {"pass": counts["pass"], "warn": counts["warn"], "fail": counts["fail"], "total": len(checks)},
        "gold": out_gold,
    }


def gold_path(project: Optional[str]) -> Optional[Path]:
    """``data/processed/<project>/traces.json`` if the project is a ground-truth dataset (iTrust, eTour, CM-1 ...)."""
    if not project:
        return None
    path = Path(__file__).resolve().parents[2] / "data" / "processed" / re.sub(r"[^a-z0-9]", "", project.lower()) / "traces.json"
    return path if path.exists() else None


def selfcheck_project(uskg: Any, project: Optional[str] = None) -> dict[str, Any]:
    """Load one project from the graph (read-only), find its ground truth if it has any, and run the checks."""
    scope = {"project": project} if project else {}
    requirements = uskg.get_artifacts("requirement", **scope)
    targets = [a for t in ("code", "test", "design") for a in uskg.get_artifacts(t, **scope)]
    traces = uskg.get_traces(**scope)
    gold = None
    path = gold_path(project)
    if path is not None:
        gold = [(g["source_id"], g["target_id"]) for g in json.loads(path.read_text(encoding="utf-8"))]
    report = run_selfcheck(requirements, targets, traces, flags=uskg.get_decay_flag_pairs(project), gold=gold)
    report["project"] = project
    report["gold_source"] = str(path.relative_to(path.parents[3])) if path else None
    return report
