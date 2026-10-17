"""Decay-injection harness: does the detector catch deliberately broken links?

Takes known-good links, mutates the target's text in ways that should break the
trace, runs the decay detector (real LLM) and measures how many are flagged.
A "control" mutation that changes nothing functional measures false decays.

Usage (from the project root; needs OPENAI_API_KEY):
    python -m agents.traceability_agent.decay_injection \
        --artifacts data/processed/cm1/artifacts.json \
        --links data/processed/cm1/traces.json --sample 10
"""

import argparse
import json
from datetime import datetime, timezone
import re
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence

from agents.traceability_agent.config import PASS_THRESHOLD
from agents.traceability_agent.decay import DecayDetector
from agents.traceability_agent.preprocess import llm_text
from agents.traceability_agent.semdiff import fingerprint_pair
from agents.traceability_agent.utils import content_hash
from shared.schemas.traceability import Artifact, TraceabilityLink
from shared.uskg.memory import InMemoryUSKG

UNRELATED = "The cafeteria menu rotates weekly and includes soup, salad and a vegetarian option."


def unrelated_replacement(text: str) -> str:
    """Replace the content entirely with unrelated text."""
    return UNRELATED


def negate_behavior(text: str) -> str:
    """Invert the described behaviour (shall -> shall not, ==/!=, True/False)."""
    out = re.sub(r"\bshall\b(?! not)", "shall not", text)
    out = out.replace("==", "!=").replace("&&", "||").replace(" > ", " < ")
    out = re.sub(r"\bTrue\b", "False", out)
    out = re.sub(r"\btrue\b", "false", out)
    return out


def change_numbers(text: str) -> str:
    """Change every number (e.g. thresholds, limits) to a very different value."""
    return re.sub(r"\d+", lambda m: str(int(m.group()) * 100 + 7), text)


def strip_to_first_sentence(text: str) -> str:
    """Drop everything after the first sentence/line (removes most of the behaviour)."""
    return re.split(r"(?<=[.!?])\s|\n", text.strip(), maxsplit=1)[0]


def cosmetic_change(text: str) -> str:
    """Functionally irrelevant edit; the link should NOT decay (false-decay control)."""
    return text + "\n(Reformatted; no functional change.)"


BREAKING_MUTATIONS: dict[str, Callable[[str], str]] = {
    "unrelated_replacement": unrelated_replacement,
    "negate_behavior": negate_behavior,
    "change_numbers": change_numbers,
    "strip_to_first_sentence": strip_to_first_sentence,
}
CONTROL_MUTATION = ("cosmetic_control", cosmetic_change)

# The requirement changes instead of the code: the link should decay when the requirement now asks for something else.
REQUIREMENT_BREAKING_MUTATIONS: dict[str, Callable[[str], str]] = {
    "requirement_unrelated": unrelated_replacement,
    "requirement_negated": negate_behavior,
}
REQUIREMENT_CONTROL = ("requirement_cosmetic_control", cosmetic_change)


def wilson(correct: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a proportion (honest for small samples)."""
    if total == 0:
        return (0.0, 0.0)
    p = correct / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _decayed(link: TraceabilityLink, source: Artifact, target: Artifact, original: tuple[Artifact, Artifact], llm: object,
             pass_threshold: float, force: bool = False, use_fingerprint: bool = True) -> Optional[bool]:
    """Did the detector flag this (possibly mutated) pair? ``None`` if the LLM answer could not be used."""
    verified = link.model_copy(update={"status": "verified", "text_hash": content_hash(*original),
                                       "sem_fingerprint": fingerprint_pair(original[0], original[1], llm_text(original[1])) if use_fingerprint else None})
    store = InMemoryUSKG([source, target], [verified])
    results = DecayDetector(store, llm, pass_threshold=pass_threshold).run(force=force)  # type: ignore[arg-type]
    if not any(r.rechecked for r in results):
        return None
    return any(r.decayed for r in results)


def run_injection(
    links: Sequence[TraceabilityLink],
    artifacts: Sequence[Artifact],
    llm: object,
    pass_threshold: float = PASS_THRESHOLD,
    baseline: bool = False,
    on_link: Optional[Callable[[dict], None]] = None,
    skip: Optional[set[tuple[str, str]]] = None,
    use_fingerprint: bool = True,
) -> dict:
    """Break each link in several ways and see whether the detector flags it.

    Target mutations change the code/design text, requirement mutations change the requirement. Mutations that
    leave a text unchanged are skipped for that artifact. With ``baseline`` a link is only used if the detector
    still accepts the unmodified pair, so a link the LLM would reject anyway cannot count as "detected" or as a
    "false decay" (it is counted in ``baseline_skipped``).

    Args:
        links: Known-good links.
        artifacts: All artifacts (requirements and targets).
        llm: Object with ``verify_link(source, target)`` (``LLMClient`` or a mock).
        pass_threshold: Decay threshold passed to the detector.
        baseline: Check the unmodified pair first and skip links it already fails.
        on_link: Called with one row per finished link (for saving progress).
        skip: (requirement, target) pairs already done.

    Returns:
        ``{"per_mutation", "decay_detection_accuracy", "decay_detection_ci95", "false_decay_rate",
        "baseline_skipped", "per_link"}``.
    """
    by_id = {a.id: a for a in artifacts}
    target_muts = {**BREAKING_MUTATIONS, CONTROL_MUTATION[0]: CONTROL_MUTATION[1]}
    req_muts = {**REQUIREMENT_BREAKING_MUTATIONS, REQUIREMENT_CONTROL[0]: REQUIREMENT_CONTROL[1]}
    breaking = list(BREAKING_MUTATIONS) + list(REQUIREMENT_BREAKING_MUTATIONS)
    controls = [CONTROL_MUTATION[0], REQUIREMENT_CONTROL[0]]
    rows: list[dict] = []

    for link in links:
        if skip and (link.source_id, link.target_id) in skip:
            continue
        source, target = by_id[link.source_id], by_id[link.target_id]
        original = (source, target)
        row: dict = {"requirement": link.source_id, "target": link.target_id, "baseline_pass": None, "outcome": {}}
        if baseline:
            base = _decayed(link, source, target, original, llm, pass_threshold, force=True, use_fingerprint=use_fingerprint)
            row["baseline_pass"] = None if base is None else (not base)
            if not row["baseline_pass"]:
                row["skipped_baseline"] = True
                rows.append(row)
                if on_link:
                    on_link(row)
                continue
        for name, mutate in target_muts.items():
            text = mutate(target.text)
            if text != target.text:
                row["outcome"][name] = _decayed(link, source, target.model_copy(update={"text": text}), original, llm, pass_threshold, use_fingerprint=use_fingerprint)
        for name, mutate in req_muts.items():
            text = mutate(source.text)
            if text != source.text:
                row["outcome"][name] = _decayed(link, source.model_copy(update={"text": text}), target, original, llm, pass_threshold, use_fingerprint=use_fingerprint)
        rows.append(row)
        if on_link:
            on_link(row)
    return summarise_injection(rows, breaking, controls)


def summarise_injection(rows: list[dict], breaking: Optional[list[str]] = None, controls: Optional[list[str]] = None) -> dict:
    """Aggregate per-link rows into per-mutation counts, overall detection and false-decay rates with intervals."""
    breaking = breaking or list(BREAKING_MUTATIONS) + list(REQUIREMENT_BREAKING_MUTATIONS)
    controls = controls or [CONTROL_MUTATION[0], REQUIREMENT_CONTROL[0]]
    stats = {n: {"injected": 0, "detected": 0} for n in breaking + controls}
    for r in rows:
        for name, flagged in r["outcome"].items():
            if flagged is None or name not in stats:
                continue  # unusable LLM answer: not counted either way
            stats[name]["injected"] += 1
            stats[name]["detected"] += int(flagged)
    inj = sum(stats[n]["injected"] for n in breaking)
    det = sum(stats[n]["detected"] for n in breaking)
    cinj = sum(stats[n]["injected"] for n in controls)
    cdet = sum(stats[n]["detected"] for n in controls)
    return {
        "per_mutation": stats,
        "decay_detection_accuracy": det / inj if inj else 0.0,
        "decay_detection_ci95": [round(x, 3) for x in wilson(det, inj)],
        "false_decay_rate": cdet / cinj if cinj else 0.0,
        "false_decay_ci95": [round(x, 3) for x in wilson(cdet, cinj)],
        "baseline_skipped": sum(1 for r in rows if r.get("skipped_baseline")),
        "links_used": sum(1 for r in rows if r["outcome"]),
        "per_link": rows,
    }


def _gold_links(dataset: str, per_dataset: int, seed: int, max_chars: int) -> tuple[list[Artifact], list[TraceabilityLink]]:
    """Ground-truth (CoEST) links of one dataset: a seeded sample whose texts fit the LLM prompt."""
    import random

    root = Path(__file__).resolve().parents[2] / "data" / "processed" / dataset
    artifacts = [Artifact(**a) for a in json.loads((root / "artifacts.json").read_text(encoding="utf-8"))]
    by_id = {a.id: a for a in artifacts}
    links = [TraceabilityLink(**l) for l in json.loads((root / "traces.json").read_text(encoding="utf-8"))]
    links = [l for l in links if l.source_id in by_id and l.target_id in by_id and len(by_id[l.target_id].text) <= max_chars]
    random.Random(seed).shuffle(links)
    return artifacts, links[:per_dataset]


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: run the harness with the real LLM and print the results."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifacts", type=Path, help="artifacts.json (omit with --neo4j / --dataset)")
    parser.add_argument("--links", type=Path, help="traces.json of known-good links (omit with --neo4j / --dataset)")
    parser.add_argument("--neo4j", action="store_true", help="read artifacts and VERIFIED links from the USKG (read-only; mutations are applied in memory)")
    parser.add_argument("--dataset", action="append", help="use ground-truth links of data/processed/<name> (repeatable)")
    parser.add_argument("--per-dataset", type=int, default=10, help="links per --dataset")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-chars", type=int, default=3000, help="only links whose target text is at most this long (the LLM sees ~3000 chars)")
    parser.add_argument("--no-fingerprint", action="store_true", help="do not use the meaning-bearing-change check (reproduces the earlier LLM-only measurement)")
    parser.add_argument("--baseline", action="store_true", help="only use links the detector accepts before any edit")
    parser.add_argument("--out", type=Path, help="result file; an existing file is resumed (finished links are skipped)")
    parser.add_argument("--sample", type=int, default=10, help="number of links to use (--neo4j / --links)")
    args = parser.parse_args(argv)

    artifacts: list[Artifact] = []
    links: list[TraceabilityLink] = []
    if args.dataset:
        for name in args.dataset:
            a, l = _gold_links(name, args.per_dataset, args.seed, args.max_chars)
            artifacts += [x for x in a if x.id not in {y.id for y in artifacts}]
            links += l
        source = "gold:" + ",".join(args.dataset)
    elif args.neo4j:
        from shared.uskg.client import USKGClient

        with USKGClient() as uskg:
            artifacts = [a for t in ("requirement", "code", "test", "design") for a in uskg.get_artifacts(t)]
            links = uskg.get_traces(status="verified")[: args.sample]
        source = "neo4j"
    elif args.artifacts and args.links:
        artifacts = [Artifact(**a) for a in json.loads(args.artifacts.read_text(encoding="utf-8"))]
        links = [TraceabilityLink(**l) for l in json.loads(args.links.read_text(encoding="utf-8"))][: args.sample]
        source = str(args.links)
    else:
        parser.error("pass --dataset, --neo4j, or both --artifacts and --links")
    if not links:
        print("No links to mutate.", file=sys.stderr)
        return 1

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    from agents.traceability_agent.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
    from shared.llm.client import LLMClient

    llm = LLMClient(system_prompt=SYSTEM_PROMPT, user_prompt_template=USER_PROMPT_TEMPLATE)
    out = args.out or Path(__file__).resolve().parents[2] / "data" / "results" / f"decay_injection_{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = json.loads(out.read_text(encoding="utf-8")).get("per_link", []) if out.exists() else []
    done = {(r["requirement"], r["target"]) for r in rows}

    def save(row: dict) -> None:
        rows.append(row)
        report = summarise_injection(rows)
        report.update(sample_links=len(links), source=source, baseline=args.baseline, fingerprint=not args.no_fingerprint, seed=args.seed, model=getattr(llm, "model", None),
                      finished=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        out.write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(f"{len(rows)}/{len(links)} {row['requirement']} -> {row['target']}  {row['outcome'] or 'skipped (baseline)'}", flush=True)

    run_injection(links, artifacts, llm, baseline=args.baseline, on_link=save, skip=done, use_fingerprint=not args.no_fingerprint)
    report = json.loads(out.read_text(encoding="utf-8"))
    for name, st in report["per_mutation"].items():
        print(f"{name:30s} detected {st['detected']}/{st['injected']}")
    print(f"Decay detection accuracy: {report['decay_detection_accuracy']:.3f}  95% interval {report['decay_detection_ci95']}")
    print(f"False decay rate (controls): {report['false_decay_rate']:.3f}  95% interval {report['false_decay_ci95']}")
    print(f"links used {report['links_used']}, skipped by baseline {report['baseline_skipped']}; report saved: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
