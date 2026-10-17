"""Analytics over a project's trace links: distributions, hotspots, weakest links and a timeline.

Pure functions over the payload of ``sources.neo4j_links`` so they can be tested without Neo4j.
"""

from collections import Counter, defaultdict
from typing import Any

TRUSTED_THRESHOLD = 0.85  # hand-labelling showed ~91% of links at or above this are correct, ~44% in 0.7-0.85
BUCKETS = [(0.0, 0.5, "< 0.5"), (0.5, 0.7, "0.5 - 0.7"), (0.7, 0.85, "0.7 - 0.85"), (0.85, 1.01, ">= 0.85")]


def _day(value: Any) -> str:
    return str(value)[:10] if value else ""


def _name(path: str) -> str:
    return str(path).split("/")[-1].split(":")[-1]


def _risk(payload: dict[str, Any], links: list[dict[str, Any]], top: int) -> list[dict[str, Any]]:
    """Requirements ranked by how likely their traceability is wrong or about to be.

    Points: never linked 3; only broken links 3; has a broken link 2; one single link 1;
    best verified confidence < 0.7 gives 2, < 0.85 gives 1.
    """
    by_req: dict[str, list[dict[str, Any]]] = defaultdict(list)
    text: dict[str, str] = {}
    for l in links:
        by_req[l["requirement"]].append(l)
        text[l["requirement"]] = l.get("requirementText", "")
    for o in payload.get("orphans", []):
        by_req.setdefault(o["requirement"], [])
        text[o["requirement"]] = o.get("requirementText", "")

    rows = []
    for rid, ls in by_req.items():
        ok = [l for l in ls if l.get("status") != "decayed"]
        broken = len(ls) - len(ok)
        reasons, points = [], 0
        if not ls:
            reasons.append("never linked to any code")
            points += 3
        elif not ok:
            reasons.append("every link is broken")
            points += 3
        else:
            if broken:
                reasons.append(f"{broken} broken link{'s' if broken > 1 else ''}")
                points += 2
            if len(ok) == 1:
                reasons.append("depends on a single file")
                points += 1
            best = max(l.get("confidence") or 0 for l in ok)
            if best < 0.7:
                reasons.append(f"best confidence only {best:.2f}")
                points += 2
            elif best < 0.85:
                reasons.append(f"best confidence {best:.2f}")
                points += 1
        if points:
            rows.append({"requirement": rid, "text": (text.get(rid) or "")[:200], "points": points, "reasons": reasons, "level": "high" if points >= 3 else "medium"})
    rows.sort(key=lambda r: (-r["points"], r["requirement"]))
    return rows[:top]


def _completeness_trend(links: list[dict[str, Any]], flags: list[dict[str, Any]], total_req: int, days: list[str]) -> list[dict[str, Any]]:
    """Approximate completeness (mean over all requirements of the mean confidence of valid links) after each day.

    Rebuilt from link ``verifiedAt`` and DecayFlag ``flaggedAt`` using today's confidences, so it shows the
    shape of the history, not exact past scores (flags removed by an undo are not in the data).
    """
    if not total_req:
        return []
    flagged: dict[tuple[str, str], str] = {}
    for f in flags:
        key = (f["requirement"], f["code"])
        d = _day(f.get("flaggedAt"))
        if d and (key not in flagged or d < flagged[key]):
            flagged[key] = d
    out = []
    for d in days:
        by_req: dict[str, list[float]] = defaultdict(list)
        for l in links:
            v = _day(l.get("verifiedAt"))
            if not v or v > d:
                continue
            f = flagged.get((l["requirement"], l["code"]))
            if f and f <= d:
                continue
            by_req[l["requirement"]].append(l.get("confidence") or 0)
        score = sum(sum(c) / len(c) for c in by_req.values()) / total_req * 100
        out.append({"day": d, "score": round(score, 1)})
    return out


def build(payload: dict[str, Any], top: int = 10) -> dict[str, Any]:
    """Summarise ``neo4j_links`` output.

    Returns coverage, a confidence histogram, links-per-requirement histogram, the files that the most
    requirements depend on (change hotspots), files that decayed most, the weakest verified links,
    and per-day counts of links created and links that decayed.
    """
    links = payload.get("links", [])
    flags = payload.get("decayFlags", [])
    total_req = payload.get("requirements", 0)
    verified = [l for l in links if l.get("status") != "decayed"]

    linked_reqs = {l["requirement"] for l in verified}
    per_req = Counter(l["requirement"] for l in verified)
    histogram = Counter(per_req[r] for r in linked_reqs)
    never = max(0, total_req - len(linked_reqs))
    links_per_req = [{"label": "0", "count": never}] + [
        {"label": str(n) if n < 4 else "4+", "count": sum(c for k, c in histogram.items() if (k == n if n < 4 else k >= 4))} for n in (1, 2, 3, 4)
    ]

    confidence = [
        {"label": label, "count": sum(1 for l in verified if lo <= (l.get("confidence") or 0) < hi)} for lo, hi, label in BUCKETS
    ]

    by_code: dict[str, set[str]] = defaultdict(set)
    for l in verified:
        by_code[l["code"]].add(l["requirement"])
    hotspots = sorted(
        ({"code": c, "name": _name(c), "requirements": len(r)} for c, r in by_code.items()), key=lambda x: (-x["requirements"], x["name"])
    )[:top]

    decay_by_code = Counter(f["code"] for f in flags)
    unstable = [{"code": c, "name": _name(c), "decays": n} for c, n in decay_by_code.most_common(top)]

    weakest = sorted(verified, key=lambda l: (l.get("confidence") or 0, l["requirement"]))[:top]
    weakest = [
        {"requirement": l["requirement"], "code": l["code"], "name": _name(l["code"]), "confidence": l.get("confidence"), "reason": l.get("reason", "")[:240]}
        for l in weakest
    ]

    created = Counter(_day(l.get("verifiedAt")) for l in links if l.get("verifiedAt"))
    decayed = Counter(_day(f.get("flaggedAt")) for f in flags if f.get("flaggedAt"))
    days = sorted(set(created) | set(decayed))
    timeline, running = [], 0
    for d in days:
        running += created.get(d, 0)
        timeline.append({"day": d, "created": created.get(d, 0), "decayed": decayed.get(d, 0), "total": running})

    confs = [l.get("confidence") or 0 for l in verified]
    return {
        "project": payload.get("project"),
        "requirements": total_req,
        "linkedRequirements": len(linked_reqs),
        "coverage": round(len(linked_reqs) / total_req, 3) if total_req else 0.0,
        "verifiedLinks": len(verified),
        "decayedLinks": len(links) - len(verified),
        "decayEvents": len(flags),
        "trustedThreshold": TRUSTED_THRESHOLD,
        "trustedLinks": sum(1 for c in confs if c >= TRUSTED_THRESHOLD),
        "reviewLinks": sum(1 for c in confs if c < TRUSTED_THRESHOLD),
        "meanConfidence": round(sum(confs) / len(confs), 3) if confs else 0.0,
        "confidenceHistogram": confidence,
        "linksPerRequirement": links_per_req,
        "hotspots": hotspots,
        "unstableFiles": unstable,
        "weakestLinks": weakest,
        "timeline": timeline,
        "completenessTrend": _completeness_trend(links, flags, total_req, days),
        "riskRequirements": _risk(payload, links, top),
    }
