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
import re
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence

from agents.traceability_agent.config import PASS_THRESHOLD
from agents.traceability_agent.decay import DecayDetector
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
    out = out.replace("==", "!=").replace("True", "False")
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


def run_injection(
    links: Sequence[TraceabilityLink],
    artifacts: Sequence[Artifact],
    llm: object,
    pass_threshold: float = PASS_THRESHOLD,
) -> dict:
    """Apply each mutation to each link's target and see whether the link decays.

    Mutations that leave the text unchanged for a given artifact are skipped for
    that artifact (they would not be a real injection).

    Args:
        links: Known-good links.
        artifacts: All artifacts (requirements and targets).
        llm: Object with ``verify_link(source, target)`` (``LLMClient`` or a mock).
        pass_threshold: Decay threshold passed to the detector.

    Returns:
        ``{"per_mutation": {name: {"injected", "detected"}}, "decay_detection_accuracy",
        "false_decay_rate"}``.
    """
    by_id = {a.id: a for a in artifacts}
    stats: dict[str, dict[str, int]] = {}
    mutations = {**BREAKING_MUTATIONS, CONTROL_MUTATION[0]: CONTROL_MUTATION[1]}

    for name, mutate in mutations.items():
        stats[name] = {"injected": 0, "detected": 0}
        for link in links:
            source, target = by_id[link.source_id], by_id[link.target_id]
            mutated_text = mutate(target.text)
            if mutated_text == target.text:
                continue
            mutated = target.model_copy(update={"text": mutated_text})
            verified = link.model_copy(
                update={"status": "verified", "text_hash": content_hash(source, target)}
            )
            store = InMemoryUSKG([source, mutated], [verified])
            results = DecayDetector(store, llm, pass_threshold=pass_threshold).run()  # type: ignore[arg-type]
            stats[name]["injected"] += 1
            stats[name]["detected"] += int(any(r.decayed for r in results))

    breaking = [stats[n] for n in BREAKING_MUTATIONS]
    injected = sum(s["injected"] for s in breaking)
    detected = sum(s["detected"] for s in breaking)
    control = stats[CONTROL_MUTATION[0]]
    return {
        "per_mutation": stats,
        "decay_detection_accuracy": detected / injected if injected else 0.0,
        "false_decay_rate": control["detected"] / control["injected"] if control["injected"] else 0.0,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: run the harness with the real LLM and print the results."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifacts", type=Path, help="artifacts.json (omit with --neo4j)")
    parser.add_argument("--links", type=Path, help="traces.json of known-good links (omit with --neo4j)")
    parser.add_argument("--neo4j", action="store_true", help="read artifacts and VERIFIED links from the USKG (read-only; mutations are applied in memory)")
    parser.add_argument("--sample", type=int, default=10, help="number of links to use")
    args = parser.parse_args(argv)

    if args.neo4j:
        from shared.uskg.client import USKGClient

        with USKGClient() as uskg:
            artifacts = [a for t in ("requirement", "code", "test", "design") for a in uskg.get_artifacts(t)]
            links = uskg.get_traces(status="verified")
    elif args.artifacts and args.links:
        artifacts = [Artifact(**a) for a in json.loads(args.artifacts.read_text(encoding="utf-8"))]
        links = [TraceabilityLink(**l) for l in json.loads(args.links.read_text(encoding="utf-8"))]
    else:
        parser.error("pass --neo4j, or both --artifacts and --links")
    if not links:
        print("No verified links to mutate. Run the `link` command first.", file=sys.stderr)
        return 1
    links = links[: args.sample]

    from agents.traceability_agent.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
    from shared.llm.client import LLMClient

    llm = LLMClient(system_prompt=SYSTEM_PROMPT, user_prompt_template=USER_PROMPT_TEMPLATE)
    report = run_injection(links, artifacts, llm)
    for name, s in report["per_mutation"].items():
        print(f"{name:26s} detected {s['detected']}/{s['injected']}")
    print(f"Decay detection accuracy: {report['decay_detection_accuracy']:.3f}")
    print(f"False decay rate (control): {report['false_decay_rate']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
