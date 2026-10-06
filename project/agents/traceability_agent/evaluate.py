"""Evaluate the traceability pipeline and its baselines against a gold standard.

Usage (from the project root):
    # offline baseline, no API keys or database needed
    python -m agents.traceability_agent.evaluate --gold data/processed/cm1/gold.json \
        --artifacts data/processed/cm1/artifacts.json --method tfidf --sweep

    # the full pipeline (needs OPENAI_API_KEY + the embedding model; artifacts come
    # from the JSON file via an in-memory graph, or from Neo4j if --artifacts is omitted)
    python -m agents.traceability_agent.evaluate --gold ... --artifacts ... --method full

``--gold`` is a JSON list of ``[source_id, target_id, is_true_link]`` triples
(see scripts/load_dataset.py), or fill in ``GOLD_STANDARD`` below.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from agents.traceability_agent.config import CHUNK_WORDS

GoldTriple = tuple[str, str, bool]
NO_CUTOFF = float("-inf")  # rank by top-k only

# (source_id, target_id, is_true_link) -- fill in or pass --gold.
GOLD_STANDARD: list[GoldTriple] = []


def compute_metrics(
    predicted: set[tuple[str, str]], gold: Sequence[GoldTriple]
) -> dict[str, float]:
    """Compute precision, recall and F1 of predicted links against gold labels.

    Only labelled pairs are scored. A predicted pair absent from the gold set
    has an unknown truth value, so it is counted under ``ignored`` rather than
    being treated as a false positive.

    Args:
        predicted: ``(source_id, target_id)`` pairs the method confirmed.
        gold: Labelled ``(source_id, target_id, is_true_link)`` triples.

    Returns:
        Dict with ``precision``, ``recall``, ``f1``, ``tp``, ``fp``, ``fn``, ``ignored``.
    """
    true_pairs = {(s, t) for s, t, is_true in gold if is_true}
    false_pairs = {(s, t) for s, t, is_true in gold if not is_true}

    tp = len(predicted & true_pairs)
    fp = len(predicted & false_pairs)
    fn = len(true_pairs - predicted)
    ignored = len(predicted - true_pairs - false_pairs)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "ignored": ignored,
    }


def load_gold(path: str) -> list[GoldTriple]:
    """Load gold triples from a JSON file.

    Args:
        path: Path to a JSON list of ``[source_id, target_id, is_true_link]``.

    Returns:
        The parsed triples.
    """
    with open(path, encoding="utf-8") as fh:
        return [(str(s), str(t), bool(flag)) for s, t, flag in json.load(fh)]


def print_metrics(label: str, m: dict[str, float], n_pred: int) -> None:
    """Print one result line block."""
    print(f"[{label}] predicted={n_pred}  TP={m['tp']} FP={m['fp']} FN={m['fn']} "
          f"(unlabelled ignored: {m['ignored']})")
    print(f"[{label}] precision={m['precision']:.3f}  recall={m['recall']:.3f}  f1={m['f1']:.3f}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the chosen method (without writing to the graph) and print precision/recall/F1."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gold", help="JSON file of [source_id, target_id, is_true_link]")
    parser.add_argument("--artifacts", type=Path, help="artifacts.json; use an in-memory graph instead of Neo4j")
    parser.add_argument("--method", choices=["full", "embeddings", "tfidf", "hybrid"], default="full")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--threshold", type=float, help="similarity cutoff (default: none for full/hybrid, 0.5 embeddings, 0.1 tfidf)")
    parser.add_argument("--limit-sources", type=int, help="only use the first N requirements (cheaper LLM runs); gold is filtered to match")
    parser.add_argument("--embedding-model", help="sentence-transformers model name (default: EMBEDDING_MODEL_NAME)")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_WORDS, help="words per chunk; 0 = whole text (default: config.CHUNK_WORDS)")
    parser.add_argument("--raw-text", action="store_true", help="skip code cleaning (imports/identifier splitting) to compare")
    parser.add_argument("--retrieval", choices=["embeddings", "tfidf", "hybrid"], default="hybrid", help="stage-1 method for --method full")
    parser.add_argument("--ceiling", action="store_true", help="print stage-1 recall ceiling (threshold 0) for several top-k, then exit")
    parser.add_argument("--sweep", action="store_true", help="tfidf/embeddings: print metrics across thresholds")
    args = parser.parse_args(argv)

    gold = load_gold(args.gold) if args.gold else GOLD_STANDARD
    if not gold:
        print("No gold standard: pass --gold FILE or fill in GOLD_STANDARD.", file=sys.stderr)
        return 1

    from agents.traceability_agent import baselines
    from shared.schemas.traceability import Artifact

    if args.artifacts:
        from shared.uskg.memory import InMemoryUSKG

        store = InMemoryUSKG(Artifact(**a) for a in json.loads(args.artifacts.read_text(encoding="utf-8")))
    else:
        from shared.uskg.client import USKGClient

        store = USKGClient()

    sources = [a for t in ("requirement",) for a in store.get_artifacts(t)]
    targets = [a for t in ("code", "test", "design") for a in store.get_artifacts(t)]
    if args.limit_sources:
        sources = sources[: args.limit_sources]
        kept = {a.id for a in sources}
        gold = [g for g in gold if g[0] in kept]
    print(f"Gold pairs: {len(gold)} ({sum(g[2] for g in gold)} true)   sources={len(sources)} targets={len(targets)}")

    from agents.traceability_agent.preprocess import retrieval_text

    text_fn = (lambda a: a.text) if args.raw_text else retrieval_text
    chunk = args.chunk_size or None

    if args.ceiling:
        from shared.embeddings.embedder import Embedder

        embedder = Embedder(args.embedding_model)
        true = {(s, t) for s, t, flag in gold if flag}
        recall = lambda c: len({(x.source.id, x.target.id) for x in c} & true) / len(true)
        print(f"Stage-1 recall ceiling (no LLM; raw_text={args.raw_text}) over {len(true)} true links")
        print(f"{'top_k':>6} {'tfidf':>8} {'embeddings':>11} {'hybrid':>8} {'candidates':>11}")
        for k in (10, 20, 50):
            print(
                f"{k:>6} {recall(baselines.tfidf_candidates(sources, targets, k, 0.0, text_fn, chunk)):>8.3f} "
                f"{recall(baselines.embedding_candidates(sources, targets, embedder, k, -1.0, text_fn, chunk)):>11.3f} "
                f"{recall(baselines.hybrid_candidates(sources, targets, embedder, k, NO_CUTOFF, text_fn, chunk)):>8.3f} "
                f"{len(sources) * k:>11}"
            )
        return 0

    if args.method == "tfidf":
        thresholds = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3] if args.sweep else [args.threshold if args.threshold is not None else 0.1]
        for th in thresholds:
            cands = baselines.tfidf_candidates(sources, targets, args.top_k, th, text_fn, chunk)
            pred = {(c.source.id, c.target.id) for c in cands}
            print_metrics(f"tfidf th={th}", compute_metrics(pred, gold), len(pred))
        return 0

    from agents.traceability_agent.agent import TraceabilityAgent
    from shared.embeddings.embedder import Embedder

    agent = TraceabilityAgent(
        uskg=store, embedder=Embedder(args.embedding_model), retrieval=args.retrieval, top_k=args.top_k,
        chunk_size=chunk,
    )
    th = args.threshold  # None = agent default (no cutoff, rank by top-k)
    if args.method == "hybrid":
        cands = baselines.hybrid_candidates(sources, targets, agent.embedder, args.top_k, NO_CUTOFF, text_fn, chunk)
        pred = {(c.source.id, c.target.id) for c in cands}
        print_metrics("hybrid", compute_metrics(pred, gold), len(pred))
        return 0
    if args.method == "embeddings":
        thresholds = [0.3, 0.4, 0.5, 0.6] if args.sweep else [th if th is not None else 0.5]
        for t in thresholds:
            cands = baselines.embedding_candidates(sources, targets, agent.embedder, args.top_k, t, text_fn, chunk)
            pred = {(c.source.id, c.target.id) for c in cands}
            print_metrics(f"embeddings th={t}", compute_metrics(pred, gold), len(pred))
        return 0

    from agents.traceability_agent.run_log import RunLogger

    runs_dir = Path(__file__).resolve().parents[2] / "data" / "runs"
    logger = RunLogger.new(runs_dir, f"{args.retrieval}-top{args.top_k}")
    agent.run_logger = logger  # the dashboard (apps/web) reads this file live
    logger.emit(
        "run_start",
        dataset=args.artifacts.parent.name if args.artifacts else "neo4j",
        method="full",
        retrieval=args.retrieval,
        top_k=args.top_k,
        chunk_size=chunk,
        sources=[a.id for a in sources],
        n_targets=len(targets),
        gold_pairs=len(gold),
        true_links=sum(g[2] for g in gold),
    )
    candidates = agent.find_candidates(sources, targets, args.top_k, th)
    links = agent.verify_candidates(candidates)  # evaluation never writes to the graph
    pred = {(l.source_id, l.target_id) for l in links}
    metrics = compute_metrics(pred, gold)
    print_metrics("full", metrics, len(pred))
    lat = sorted(agent.verification_latencies)
    logger.emit(
        "run_end",
        metrics=metrics,
        mean_latency=round(sum(lat) / len(lat), 2) if lat else None,
        p95_latency=round(lat[int(0.95 * (len(lat) - 1))], 2) if lat else None,
    )
    print(f"[full] run log: {logger.path}")
    if lat:
        print(f"[full] LLM calls={len(lat)}  mean latency={sum(lat)/len(lat):.2f}s  "
              f"p95={lat[int(0.95 * (len(lat) - 1))]:.2f}s  (target <= 5s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
