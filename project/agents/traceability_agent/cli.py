"""Command-line entrypoint: ``python -m agents.traceability_agent <command>``.

Commands:
    setup    create the Neo4j indexes the queries rely on
    link     find and verify trace links, writing VERIFIED_TRACE edges (use --dry-run to skip)
    monitor  re-verify changed links and flag decayed ones (loops; --once to run a single pass)
    score    traceability completeness per requirement, plus orphan requirements
    changed  react to one commit: re-check links of changed files, link new files / requirements
    listen   wait for change messages from C2 on Redis and handle each one

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

    if prompt == "evidence":
        return LLMClient(system_prompt=prompts.EVIDENCE_SYSTEM_PROMPT, response_mode="evidence")
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

    reranker = None
    if args.reranker:  # optional stage 1.5: a cross-encoder re-orders the stage-1 pool before the LLM
        from agents.traceability_agent.reranker.rerank import CrossEncoderReranker

        reranker = CrossEncoderReranker(args.reranker, weight=args.rerank_weight)
    with USKGClient() as uskg:
        logger = RunLogger.new(RUNS_DIR, f"link-{args.retrieval}-top{args.top_k}{'-rerank' if reranker else ''}")
        agent = TraceabilityAgent(
            uskg=uskg, embedder=Embedder(), llm=_build_llm(args.prompt), retrieval=args.retrieval,
            top_k=args.top_k, run_logger=logger, project=args.project,
            reranker=reranker, rerank_pool=args.rerank_pool,
        )
        sources, targets = agent.load_artifacts()
        if args.requirement:  # link only these requirements (e.g. a newly added one)
            wanted = set(args.requirement)
            sources = [a for a in sources if a.id in wanted]
            if not sources:
                print(f"None of the requirements {sorted(wanted)} exist in the graph.", file=sys.stderr)
                return 1
        elif args.only_unlinked:  # requirements that no verified link points from yet (the ones C1 wrote and nobody linked)
            linked = {t.source_id for t in uskg.get_traces(project=args.project)}
            sources = [a for a in sources if a.id not in linked]
            if not sources:
                print("Every requirement already has a trace link.")
                return 0
        elif args.limit_sources:
            sources = sources[: args.limit_sources]
        logger.emit("run_start", dataset="neo4j", method="link", retrieval=args.retrieval, prompt=args.prompt,
                    top_k=args.top_k, sources=[a.id for a in sources], n_targets=len(targets),
                    gold_pairs=0, true_links=0, project=args.project)
        candidates = agent.find_candidates(sources, targets)
        existing = {(t.source_id, t.target_id) for t in uskg.get_traces()}
        candidates = [c for c in candidates if (c.source.id, c.target.id) not in existing]
        # each confirmed link is written immediately, so a failure mid-run keeps what was found
        links = agent.verify_candidates(candidates, on_link=None if args.dry_run else uskg.write_link)
        logger.emit("run_end", metrics={}, links=len(links), written=not args.dry_run)
    print(f"{len(sources)} requirements, {len(candidates)} candidates verified, {len(links)} links "
          f"{'found (dry run, nothing written)' if args.dry_run else 'written'}. Run log: {logger.path}")
    return 0


def _make_publisher(no_redis: bool):  # noqa: ANN202
    """A decay-event publisher, or ``None`` if disabled or the redis package is missing."""
    if no_redis:
        return None
    try:
        import redis  # noqa: F401
    except ImportError:
        print("warning: the 'redis' package is not installed; decay events will not be published", file=sys.stderr)
        return None
    from agents.traceability_agent.events import DecayEventPublisher

    return DecayEventPublisher()


def cmd_monitor(args: argparse.Namespace) -> int:
    """Poll verified links for changes and flag decayed ones."""
    from agents.traceability_agent.decay import DecayDetector
    from shared.uskg.client import USKGClient

    publisher = _make_publisher(args.no_redis)
    from agents.traceability_agent.run_log import RunLogger

    with USKGClient() as uskg:
        logger = RunLogger.new(RUNS_DIR, "monitor")
        logger.emit("run_start", method="monitor", force=args.force, redis=publisher is not None, project=args.project)
        detector = DecayDetector(uskg, _build_llm("expert"), publisher=publisher, run_logger=logger)
        while True:
            results = detector.run(force=args.force, project=args.project)
            decayed = [r for r in results if r.decayed]
            logger.emit("pass_end", rechecked=len(results), decayed=len(decayed))
            print(f"{time.strftime('%H:%M:%S')} rechecked {len(results)} link(s), {len(decayed)} decayed")
            for r in decayed:
                print(f"  DECAYED {r.link.source_id} -> {r.link.target_id}  "
                      f"{r.link.confidence:.2f} -> {r.new_confidence:.2f}  event published: {r.published}")
            if args.once:
                logger.emit("run_end", rechecked=len(results), decayed=len(decayed))
                return 0
            time.sleep(args.interval)


def _apply(change, no_redis: bool, top_k: int) -> dict:  # noqa: ANN001
    from agents.traceability_agent.changes import apply_change
    from shared.embeddings.embedder import Embedder
    from shared.uskg.client import USKGClient

    with USKGClient() as uskg:
        return apply_change(change, uskg, _build_llm("expert"), Embedder(), RUNS_DIR,
                            publisher=_make_publisher(no_redis), top_k=top_k)


def cmd_changed(args: argparse.Namespace) -> int:
    """Handle one repository change: re-check links of changed files, link new files / requirements."""
    from agents.traceability_agent.changes import ChangeError, parse_change

    try:
        change = parse_change({"project": args.project, "changed": args.code_changed, "added": args.code_added,
                               "requirementsAdded": args.requirement_added})
    except ChangeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    result = _apply(change, args.no_redis, args.top_k)
    print(f"rechecked {result['rechecked']} link(s), {result['decayed']} decayed; "
          f"{result['candidates']} new candidate(s), {result['linked']} link(s) written")
    return 0


def cmd_listen(args: argparse.Namespace) -> int:
    """Wait for change messages on the Redis channel and handle each one (the C2 -> C4 hook)."""
    from agents.traceability_agent.changes import ChangeError, parse_change
    from agents.traceability_agent.config import CHANGE_CHANNEL

    try:
        import redis
    except ImportError:
        print("error: the 'redis' package is not installed", file=sys.stderr)
        return 1
    import os

    client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(CHANGE_CHANNEL)
    print(f"listening on '{CHANGE_CHANNEL}' (Ctrl+C to stop)")
    for message in pubsub.listen():
        try:
            change = parse_change(message["data"])
        except ChangeError as exc:
            print(f"ignored a malformed message: {exc}", file=sys.stderr)
            continue
        result = _apply(change, args.no_redis, args.top_k)
        print(f"{time.strftime('%H:%M:%S')} {change.project or '-'}: rechecked {result['rechecked']}, "
              f"{result['decayed']} decayed, {result['linked']} new link(s)")
        if args.once:
            return 0
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    """Print completeness scores and list orphan requirements."""
    from agents.traceability_agent.completeness import completeness_scores
    from shared.uskg.client import USKGClient

    evidence = json.loads(Path(args.evidence).read_text()) if args.evidence else None
    with USKGClient() as uskg:
        scope = {"project": args.project} if args.project else {}
        results = completeness_scores(uskg.get_artifacts("requirement", **scope), uskg.get_traces(**scope), evidence)
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
    p.add_argument("--only-unlinked", action="store_true", help="only requirements that have no trace link yet")
    p.add_argument("--requirement", action="append", help="link only this requirement id (repeatable)")
    p.add_argument("--project", help="only this project / repository")
    p.add_argument("--retrieval", choices=["hybrid", "embeddings", "tfidf"], default="hybrid")
    p.add_argument("--prompt", choices=["expert", "generic", "evidence"], default="expert")
    p.add_argument("--dry-run", action="store_true", help="verify but do not write")
    p.add_argument("--reranker", help="optional cross-encoder (model folder or Hugging Face name, e.g. cross-encoder/ms-marco-MiniLM-L-6-v2) that re-orders the stage-1 pool before the LLM")
    p.add_argument("--rerank-pool", type=int, default=20, help="candidates per requirement handed to the reranker (it keeps --top-k of them)")
    p.add_argument("--rerank-weight", type=float, default=0.5, help="weight of the cross-encoder z-score against the stage-1 z-score")
    p.set_defaults(func=cmd_link)

    p = sub.add_parser("monitor", help="decay detection")
    p.add_argument("--once", action="store_true")
    p.add_argument("--force", action="store_true", help="re-check even unchanged links")
    p.add_argument("--interval", type=int, default=300, help="seconds between polls")
    p.add_argument("--no-redis", action="store_true")
    p.add_argument("--project", help="only this project / repository")
    p.set_defaults(func=cmd_monitor)

    p = sub.add_parser("changed", help="react to a commit: re-check links of changed files, link new files/requirements")
    p.add_argument("--project", help="the repository / project the change belongs to")
    p.add_argument("--code-changed", action="append", default=[], metavar="ID", help="a code entity whose text changed (repeatable)")
    p.add_argument("--code-added", action="append", default=[], metavar="ID", help="a new code entity (repeatable)")
    p.add_argument("--requirement-added", action="append", default=[], metavar="ID", help="a new requirement (repeatable)")
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--no-redis", action="store_true")
    p.set_defaults(func=cmd_changed)

    p = sub.add_parser("listen", help="wait for change messages on Redis and handle them")
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--no-redis", action="store_true", help="do not publish decay events")
    p.add_argument("--once", action="store_true", help="handle one message, then exit")
    p.set_defaults(func=cmd_listen)

    p = sub.add_parser("score", help="completeness score + orphans")
    p.add_argument("--evidence", help="JSON {requirement_id: coverage 0..1} from C3")
    p.add_argument("--json", action="store_true")
    p.add_argument("--project", help="only this project / repository")
    p.set_defaults(func=cmd_score)

    logging.basicConfig(level=logging.WARNING)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
