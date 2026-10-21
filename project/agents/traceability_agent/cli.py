"""Command-line entrypoint: ``python -m agents.traceability_agent <command>``.

Commands:
    setup    create the Neo4j indexes the queries rely on
    link     find and verify trace links, writing VERIFIED_TRACE edges (use --dry-run to skip)
    monitor  re-verify changed links and flag decayed ones (loops; --once to run a single pass)
    score    traceability completeness per requirement, plus orphan requirements
    selfcheck  check C4's own links and scores against the graph and ground truth (no LLM)
    report   write the traceability matrix, link list and orphan / broken-link report to a folder
    changed  react to one commit: re-check links of changed files, link new files / requirements
    listen   wait for change messages from C2 on Redis and handle each one

Evaluation lives in ``python -m agents.traceability_agent.evaluate`` and
``... decay_injection``.
"""

import argparse
import os
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
    from dotenv import load_dotenv
    from shared.llm.client import LLMClient

    load_dotenv()
    short = (os.getenv("LLM_SHORT_REASONING") or "").strip().lower() in ("1", "true", "yes")
    shorten = prompts.with_short_reasoning if short else (lambda text: text)
    if prompt == "evidence":
        return LLMClient(system_prompt=shorten(prompts.EVIDENCE_SYSTEM_PROMPT), response_mode="evidence")
    if prompt == "generic":
        return LLMClient(system_prompt=shorten(prompts.GENERIC_SYSTEM_PROMPT), user_prompt_template=prompts.GENERIC_USER_PROMPT_TEMPLATE)
    return LLMClient(system_prompt=shorten(prompts.SYSTEM_PROMPT), user_prompt_template=prompts.USER_PROMPT_TEMPLATE)


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
    from shared.embeddings.embedder import Embedder, configured_extra_embedders
    from shared.uskg.client import USKGClient

    with USKGClient() as uskg:
        logger = RunLogger.new(RUNS_DIR, f"link-{args.retrieval}-top{args.top_k}")
        agent = TraceabilityAgent(
            uskg=uskg, embedder=Embedder(), llm=_build_llm(args.prompt), retrieval=args.retrieval,
            top_k=args.top_k, run_logger=logger, project=args.project,
            # TF-IDF + MiniLM + the fine-tuned CodeBERT (when present), see configured_extra_embedders
            extra_embedders=configured_extra_embedders() if args.retrieval == "hybrid" else [],
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
                    gold_pairs=0, true_links=0, project=args.project,
                    embedders=[agent.embedder.model_name, *[e.model_name for e in agent.extra_embedders]])
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
    from shared.embeddings.embedder import Embedder, configured_extra_embedders
    from shared.uskg.client import USKGClient

    with USKGClient() as uskg:
        return apply_change(change, uskg, _build_llm("expert"), Embedder(), RUNS_DIR,
                            publisher=_make_publisher(no_redis), top_k=top_k,
                            extra_embedders=configured_extra_embedders())


def cmd_changed(args: argparse.Namespace) -> int:
    """Handle one repository change: re-check links of changed files, link new files / requirements."""
    from agents.traceability_agent.changes import ChangeError, parse_change

    try:
        change = parse_change({"project": args.project, "changed": args.code_changed, "added": args.code_added,
                               "requirementsAdded": args.requirement_added,
                               "requirementsChanged": args.requirement_changed})
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
        if evidence is None:  # use C3's validation coverage straight from the graph when C3 has written any
            from agents.traceability_agent.c3 import evidence_coverage

            evidence = evidence_coverage(uskg.get_c3_evidence(args.project)) or None
        results = completeness_scores(uskg.get_artifacts("requirement", **scope), uskg.get_traces(**scope), evidence)
    if args.json:
        print(json.dumps([r.model_dump() for r in results], indent=1))
        return 0
    for r in sorted(results, key=lambda r: r.score):
        print(f"{r.requirement_id:24} {r.score:6.1f}%  {'BROKEN' if r.is_broken else 'ORPHAN' if r.is_orphan else ''}")
    orphans = [r for r in results if r.is_orphan and not r.is_broken]
    broken = [r for r in results if r.is_broken]
    print(f"\n{len(results)} requirements, {len(orphans)} orphan(s), {len(broken)} broken, mean score "
          f"{sum(r.score for r in results) / len(results):.1f}%" if results else "no requirements found")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Write the matrix, link list and orphan / broken-link report to a folder."""
    from agents.traceability_agent import report as rep
    from shared.uskg.client import USKGClient

    with USKGClient() as uskg:
        scope = {"project": args.project} if args.project else {}
        reqs, traces = uskg.get_artifacts("requirement", **scope), uskg.get_traces(**scope)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "trace_matrix.csv").write_text(rep.matrix_csv(reqs, traces), encoding="utf-8")
    (out / "trace_links.csv").write_text(rep.links_csv(reqs, traces), encoding="utf-8")
    summary = rep.report(reqs, traces)
    (out / "trace_report.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"{summary['requirements']} requirements: {len(summary['orphans'])} orphan, {len(summary['broken'])} broken, "
          f"{len(summary['weak'])} weak, {len(summary['decayed_links'])} decayed link(s). Files written to {out}/")
    return 0


def cmd_selfcheck(args: argparse.Namespace) -> int:
    """Check C4's own output against the graph and (where the dataset has it) against ground truth."""
    from agents.traceability_agent.selfcheck import selfcheck_project
    from shared.uskg.client import USKGClient

    with USKGClient() as uskg:
        report = selfcheck_project(uskg, args.project)
    if args.json:
        print(json.dumps(report, indent=1))
        return 0
    icon = {"pass": "ok  ", "warn": "WARN", "fail": "FAIL"}
    for c in report["checks"]:
        print(f"[{icon[c['status']]}] {c['name']}: {c['detail']}")
        for item in c["items"][:3]:
            print(f"        {item}")
    s = report["summary"]
    print(f"\n{s['pass']} passed, {s['warn']} warning(s), {s['fail']} failed.")
    g = report["gold"]
    if g:
        print(f"Against ground truth ({report['gold_source']}): precision {g['precision']:.2f}, recall {g['recall']:.2f} "
              f"(of the {g['gold_links_of_processed_requirements']} true links of the {g['requirements_processed']} requirements processed), F1 {g['f1']:.2f}")
    return 1 if s["fail"] else 0


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
    p.add_argument("--prompt", choices=["expert", "generic", "evidence"], default="expert",
                   help="evidence (default): the model must quote code that satisfies the requirement; expert: persona prompt, more lenient; generic: ablation")
    p.add_argument("--dry-run", action="store_true", help="verify but do not write")
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
    p.add_argument("--requirement-changed", action="append", default=[], metavar="ID", help="a requirement whose text was edited: re-check its links (repeatable)")
    p.add_argument("--requirement-added", action="append", default=[], metavar="ID", help="a new requirement (repeatable)")
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--no-redis", action="store_true")
    p.set_defaults(func=cmd_changed)

    p = sub.add_parser("listen", help="wait for change messages on Redis and handle them")
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--no-redis", action="store_true", help="do not publish decay events")
    p.add_argument("--once", action="store_true", help="handle one message, then exit")
    p.set_defaults(func=cmd_listen)

    p = sub.add_parser("selfcheck", help="check C4's own output against the graph and ground truth")
    p.add_argument("--project", help="only this project / repository")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_selfcheck)

    p = sub.add_parser("report", help="export matrix CSV, link list CSV and orphan/broken report JSON")
    p.add_argument("--project", help="only this project / repository")
    p.add_argument("--out", default="data/results/trace_report", help="output folder")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("score", help="completeness score + orphans")
    p.add_argument("--evidence", help="JSON {requirement_id: coverage 0..1}; default: read C3's RVUs and evidence from the graph")
    p.add_argument("--json", action="store_true")
    p.add_argument("--project", help="only this project / repository")
    p.set_defaults(func=cmd_score)

    logging.basicConfig(level=logging.WARNING)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
