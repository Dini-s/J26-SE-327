"""Command-line entrypoint: ``python -m agents.traceability_agent <command>``.

Commands:
    setup    create the Neo4j indexes the queries rely on
    link     find and verify trace links, writing VERIFIED_TRACE edges (use --dry-run to skip)
    monitor  re-verify changed links and flag decayed ones (loops; --once to run a single pass)
    score    traceability completeness per requirement, plus orphan requirements

Evaluation lives in ``python -m agents.traceability_agent.evaluate`` and
``... decay_injection``.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

from agents.traceability_agent.config import TOP_K

RUNS_DIR = Path(__file__).resolve().parents[2] / "data" / "runs"


def _build_llm(prompt: str):  # noqa: ANN202
    from agents.traceability_agent import prompts
    from shared.llm.client import LLMClient

    if prompt == "generic":
        return LLMClient(system_prompt=prompts.GENERIC_SYSTEM_PROMPT, user_prompt_template=prompts.GENERIC_USER_PROMPT_TEMPLATE)
    return LLMClient(system_prompt=prompts.SYSTEM_PROMPT, user_prompt_template=prompts.USER_PROMPT_TEMPLATE)


def cmd_setup(args: argparse.Namespace) -> int:
    """Create indexes."""
    from shared.uskg.client import USKGClient

    with USKGClient() as uskg:
        for statement in uskg.ensure_schema():
            print("ok:", statement)
    return 0


def cmd_link(args: argparse.Namespace) -> int:
    """Run the pipeline against the USKG and (unless --dry-run) write VERIFIED_TRACE edges."""
    from agents.traceability_agent.agent import TraceabilityAgent
    from agents.traceability_agent.run_log import RunLogger
    from shared.embeddings.embedder import Embedder
    from shared.uskg.client import USKGClient

    with USKGClient() as uskg:
        logger = RunLogger.new(RUNS_DIR, f"link-{args.retrieval}-top{args.top_k}")
        agent = TraceabilityAgent(
            uskg=uskg, embedder=Embedder(), llm=_build_llm(args.prompt), retrieval=args.retrieval,
            top_k=args.top_k, run_logger=logger,
        )
        sources, targets = agent.load_artifacts()
        if args.limit_sources:
            sources = sources[: args.limit_sources]
        logger.emit("run_start", dataset="neo4j", method="link", retrieval=args.retrieval, prompt=args.prompt,
                    top_k=args.top_k, sources=[a.id for a in sources], n_targets=len(targets),
                    gold_pairs=0, true_links=0)
        candidates = agent.find_candidates(sources, targets)
        existing = {(t.source_id, t.target_id) for t in uskg.get_traces()}
        candidates = [c for c in candidates if (c.source.id, c.target.id) not in existing]
        links = agent.verify_candidates(candidates)
        if not args.dry_run:
            for link in links:
                uskg.write_link(link)
        logger.emit("run_end", metrics={}, links=len(links), written=not args.dry_run)
    print(f"{len(sources)} requirements, {len(candidates)} candidates verified, {len(links)} links "
          f"{'found (dry run, nothing written)' if args.dry_run else 'written'}. Run log: {logger.path}")
    return 0


def cmd_monitor(args: argparse.Namespace) -> int:
    """Poll verified links for changes and flag decayed ones."""
    from agents.traceability_agent.decay import DecayDetector
    from agents.traceability_agent.events import DecayEventPublisher
    from shared.uskg.client import USKGClient

    publisher: Optional[DecayEventPublisher] = None
    if not args.no_redis:
        try:
            import redis  # noqa: F401

            publisher = DecayEventPublisher()
        except ImportError:
            print("warning: the 'redis' package is not installed; decay events will not be published", file=sys.stderr)
    with USKGClient() as uskg:
        detector = DecayDetector(uskg, _build_llm("expert"), publisher=publisher)
        while True:
            results = detector.run(force=args.force)
            decayed = [r for r in results if r.decayed]
            print(f"{time.strftime('%H:%M:%S')} rechecked {len(results)} link(s), {len(decayed)} decayed")
            for r in decayed:
                print(f"  DECAYED {r.link.source_id} -> {r.link.target_id}  "
                      f"{r.link.confidence:.2f} -> {r.new_confidence:.2f}  event published: {r.published}")
            if args.once:
                return 0
            time.sleep(args.interval)


def cmd_score(args: argparse.Namespace) -> int:
    """Print completeness scores and list orphan requirements."""
    from agents.traceability_agent.completeness import completeness_scores
    from shared.uskg.client import USKGClient

    evidence = json.loads(Path(args.evidence).read_text()) if args.evidence else None
    with USKGClient() as uskg:
        results = completeness_scores(uskg.get_artifacts("requirement"), uskg.get_traces(), evidence)
    if args.json:
        print(json.dumps([r.model_dump() for r in results], indent=1))
        return 0
    for r in sorted(results, key=lambda r: r.score):
        print(f"{r.requirement_id:24} {r.score:6.1f}%  {'ORPHAN' if r.is_orphan else ''}")
    orphans = [r for r in results if r.is_orphan]
    print(f"\n{len(results)} requirements, {len(orphans)} orphan(s), mean score "
          f"{sum(r.score for r in results) / len(results):.1f}%" if results else "no requirements found")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse arguments and dispatch."""
    parser = argparse.ArgumentParser(prog="python -m agents.traceability_agent", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="create Neo4j indexes").set_defaults(func=cmd_setup)

    p = sub.add_parser("link", help="find + verify links and write them")
    p.add_argument("--top-k", type=int, default=TOP_K)
    p.add_argument("--limit-sources", type=int)
    p.add_argument("--retrieval", choices=["hybrid", "embeddings", "tfidf"], default="hybrid")
    p.add_argument("--prompt", choices=["expert", "generic"], default="expert")
    p.add_argument("--dry-run", action="store_true", help="verify but do not write")
    p.set_defaults(func=cmd_link)

    p = sub.add_parser("monitor", help="decay detection")
    p.add_argument("--once", action="store_true")
    p.add_argument("--force", action="store_true", help="re-check even unchanged links")
    p.add_argument("--interval", type=int, default=300, help="seconds between polls")
    p.add_argument("--no-redis", action="store_true")
    p.set_defaults(func=cmd_monitor)

    p = sub.add_parser("score", help="completeness score + orphans")
    p.add_argument("--evidence", help="JSON {requirement_id: coverage 0..1} from C3")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_score)

    logging.basicConfig(level=logging.WARNING)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
