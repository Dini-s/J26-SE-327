"""Experiment: does an LLM that rewrites a requirement into likely code words improve stage-1 recall?

Stage 1 compares the words of a requirement with the words of the code. Where they differ ("welcome page" versus
``index`` / ``welcome.html``), nothing matches. Here the LLM is asked, ONCE per requirement, for the class, method and file
names that would probably implement it; those words are appended to the requirement before TF-IDF / embedding retrieval.

    python -m agents.traceability_agent.reranker.query_expansion generate --dataset itrust --n 20
    python -m agents.traceability_agent.reranker.query_expansion evaluate --dataset itrust

``generate`` calls the LLM (slow on a CPU server) and stores its answers in ``data/results/query_expansion_<dataset>.json``.
``evaluate`` needs no LLM: it replays the stored answers, so the result can be reproduced exactly.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from agents.traceability_agent.config import CHUNK_WORDS
from agents.traceability_agent.preprocess import retrieval_text
from agents.traceability_agent.retrieval import hybrid_matrix, select_candidates
from shared.schemas.traceability import Artifact

ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "data" / "results"

SYSTEM = (
    "You are a senior software engineer. Given a software requirement, list the names that would most probably appear in the "
    "source code that implements it: class names, method names, JSP/HTML page names. Answer ONLY with JSON: "
    '{"terms": ["...", "..."]} with at most 12 short terms (single identifiers or words).'
)


def load(dataset: str) -> tuple[list[Artifact], list[Artifact], set[tuple[str, str]]]:
    base = PROCESSED / dataset
    arts = [Artifact(**a) for a in json.loads((base / "artifacts.json").read_text(encoding="utf-8"))]
    traces = json.loads((base / "traces.json").read_text(encoding="utf-8"))
    return ([a for a in arts if a.type == "requirement"], [a for a in arts if a.type != "requirement"],
            {(t["source_id"], t["target_id"]) for t in traces})


def _choose(dataset: str, n: int) -> list[Artifact]:
    reqs, _, links = load(dataset)
    linked = {s for s, _ in links}
    return [r for r in reqs if r.id in linked][:n]


def generate(dataset: str, n: int) -> None:
    from shared.llm.client import LLMClient

    out_path = RESULTS / f"query_expansion_{dataset}.json"
    done: dict[str, Any] = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {"dataset": dataset, "model": None, "answers": {}}
    llm = LLMClient(system_prompt=SYSTEM)
    done["model"] = llm.model
    for r in _choose(dataset, n):
        if r.id in done["answers"]:
            continue
        started = time.time()
        try:
            reply = llm.client.chat.completions.create(
                model=llm.model, temperature=0.0, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Requirement:\n{r.text[:1500]}"}])
            terms = json.loads(reply.choices[0].message.content).get("terms", [])
            terms = [str(t) for t in terms if isinstance(t, str)][:12]
        except Exception as exc:  # keep going; a failed requirement is simply not expanded
            terms, err = [], f"{type(exc).__name__}: {str(exc)[:100]}"
            done["answers"][r.id] = {"terms": terms, "error": err, "seconds": round(time.time() - started, 1)}
        else:
            done["answers"][r.id] = {"terms": terms, "seconds": round(time.time() - started, 1)}
        out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        print(r.id, done["answers"][r.id]["seconds"], "s", terms[:6], flush=True)


def recall_table(dataset: str, embedder: Any, ks: tuple[int, ...] = (5, 10, 20)) -> dict[str, Any]:
    """Stage-1 recall (hybrid) of the expanded requirements against the plain ones, on the same requirements."""
    stored = json.loads((RESULTS / f"query_expansion_{dataset}.json").read_text(encoding="utf-8"))
    reqs, code, links = load(dataset)
    chosen = [r for r in reqs if r.id in stored["answers"] and not stored["answers"][r.id].get("error")]
    expanded = [r.model_copy(update={"text": r.text + " " + " ".join(stored["answers"][r.id]["terms"])}) for r in chosen]
    true = {(s, t) for s, t in links if s in {r.id for r in chosen}}
    out: dict[str, Any] = {"requirements": len(chosen), "true_links": len(true), "model": stored.get("model"), "recall": {}}
    for name, sources in (("plain", chosen), ("expanded", expanded)):
        sims = hybrid_matrix(sources, code, embedder, retrieval_text, CHUNK_WORDS)
        out["recall"][name] = {}
        for k in ks:
            cands = select_candidates(sources, code, sims, k, float("-inf"))
            found = {(c.source.id, c.target.id) for c in cands} & true
            out["recall"][name][k] = round(len(found) / len(true), 3) if true else None
    return out


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--dataset", default="itrust")
    g.add_argument("--n", type=int, default=20)
    e = sub.add_parser("evaluate")
    e.add_argument("--dataset", default="itrust")
    args = parser.parse_args(argv)
    if args.command == "generate":
        generate(args.dataset, args.n)
        return 0
    from shared.embeddings.embedder import Embedder

    print(json.dumps(recall_table(args.dataset, Embedder()), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
