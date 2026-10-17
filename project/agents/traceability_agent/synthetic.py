"""Does synthetic training data help the stage-1 embedding model (MiniLM)?

0. A hand-made dataset (``data/synthetic/user_domains``: 30 domains x 65 requirement/code pairs, each with 2 hard
   negatives in Java, JavaScript and C) can be used as the synthetic source (``--user-dataset``).
1. ``generate``: for a sample of code files from the *training* projects, the LLM writes short requirement
   sentences that the code could fulfil (``data/synthetic/train_requirements.jsonl``, resumable).
2. ``evaluate``: fine-tune MiniLM on (a) the synthetic pairs, (b) the same number of REAL expert-labelled pairs,
   (c) both, and compare with the untrained model on projects that were never used for training
   (LibEST, CM-1, EBT): recall at k of the true links, embeddings only and fused with TF-IDF.

The test sets are real, expert-labelled datasets; synthetic data is only ever used to train.

    python -m agents.traceability_agent.synthetic generate --per-project 40
    python -m agents.traceability_agent.synthetic evaluate --seeds 3
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SYN_FILE = ROOT / "data" / "synthetic" / "train_requirements.jsonl"
DEVICE = os.getenv("C4_DEVICE", "cpu")  # "cuda" on Colab
TRAIN = ["itrust", "etour", "smos", "eanci"]
TEST = ["libest", "cm1", "ebt"]

SYSTEM = "You are a business analyst who writes software requirements."
USER = """Here is source code from a software system.

CODE:
\"\"\"
{code}
\"\"\"

Write {n} different requirements, each one sentence starting with "The system shall", that a stakeholder could have written and that this code helps to fulfil. Describe what users or data are involved and what the system does. Do NOT mention class names, method names or other code identifiers.
Return only JSON: {{"requirements": ["...", "..."]}}"""


# ----------------------------------------------------------------------------- metrics
def per_requirement_hits(scores: np.ndarray, reqs: Sequence[Any], targets: Sequence[Any], gold: set[tuple[str, str]], ks: Sequence[int]) -> dict[int, list[tuple[int, int]]]:
    """For every requirement with true links: (true links in its top-k, true links) for each k."""
    out: dict[int, list[tuple[int, int]]] = {k: [] for k in ks}
    tid = [t.id for t in targets]
    for i, r in enumerate(reqs):
        true = {t for (s, t) in gold if s == r.id and t in tid}
        if not true:
            continue
        order = np.argsort(-scores[i], kind="stable")
        for k in ks:
            top = {tid[j] for j in order[:k]}
            out[k].append((len(top & true), len(true)))
    return out


def pooled_recall(rows: Sequence[tuple[int, int]]) -> float:
    hit = sum(h for h, _ in rows)
    total = sum(n for _, n in rows)
    return hit / total if total else 0.0


def bootstrap_diff(a: Sequence[tuple[int, int]], b: Sequence[tuple[int, int]], n: int = 2000, seed: int = 1) -> tuple[float, float, float]:
    """Mean and 95% interval of recall(a) - recall(b), resampling requirements (same requirements in both lists)."""
    rng = np.random.default_rng(seed)
    idx = np.arange(len(a))
    diffs = []
    for _ in range(n):
        s = rng.choice(idx, size=len(idx), replace=True)
        diffs.append(pooled_recall([a[i] for i in s]) - pooled_recall([b[i] for i in s]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(pooled_recall(a) - pooled_recall(b)), float(lo), float(hi)


def macro_recall(by_dataset: dict[str, Sequence[tuple[int, int]]]) -> float:
    """Mean of the per-dataset pooled recall: a small dataset counts as much as a big one."""
    return float(np.mean([pooled_recall(rows) for rows in by_dataset.values()]))


def macro_bootstrap_diff(a: dict[str, Sequence[tuple[int, int]]], b: dict[str, Sequence[tuple[int, int]]], n: int = 1000, seed: int = 1) -> tuple[float, float, float]:
    """Mean and 95% interval of macro_recall(a) - macro_recall(b), resampling requirements inside each dataset."""
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n):
        ra, rb = {}, {}
        for name in a:
            idx = rng.choice(len(a[name]), size=len(a[name]), replace=True)
            ra[name], rb[name] = [a[name][i] for i in idx], [b[name][i] for i in idx]
        diffs.append(macro_recall(ra) - macro_recall(rb))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(macro_recall(a) - macro_recall(b)), float(lo), float(hi)


def load_user_dataset(directories: Any) -> list[tuple[str, str, list[str]]]:
    """(requirement, correct code, hard-negative code) from ``*.json`` files of ``{requirement, code, hard_negatives}``.

    One folder or several. A requirement that appears twice is kept once, and a hard negative shorter than 40
    characters (a truncated answer) is dropped.
    """
    folders = [Path(directories)] if isinstance(directories, (str, Path)) else [Path(d) for d in directories]
    seen: set[str] = set()
    out = []
    for directory in folders:
        for path in sorted(directory.glob("*.json")):
            for item in json.loads(path.read_text(encoding="utf-8")):
                key = " ".join(str(item["requirement"]).lower().split())
                if key in seen or len(str(item["code"]).strip()) < 40:
                    continue
                seen.add(key)
                negatives = [str(n) for n in item.get("hard_negatives", []) if len(str(n).strip()) >= 40]
                out.append((item["requirement"], item["code"], negatives))
    return out


# ----------------------------------------------------------------------------- generate
def _code_for_prompt(artifact: Any, max_chars: int = 1800) -> str:
    from agents.traceability_agent.preprocess import strip_boilerplate

    return strip_boilerplate(artifact)[:max_chars]


def cmd_generate(args: argparse.Namespace) -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from agents.traceability_agent.reranker.data import _load
    from shared.llm.client import LLMClient

    llm = LLMClient(system_prompt=SYSTEM)
    SYN_FILE.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["code_id"] for l in SYN_FILE.read_text().splitlines()} if SYN_FILE.exists() else set()
    for name in args.datasets:
        _, code, _, label = _load(name)
        rng = random.Random(args.seed)
        picked = [c for c in code if len("".join(_code_for_prompt(c).split())) > 200]
        rng.shuffle(picked)
        for art in picked[: args.per_project]:
            if art.id in done:
                continue
            t0 = time.time()
            try:
                reply = llm.client.chat.completions.create(
                    model=llm.model, temperature=0.4, response_format={"type": "json_object"},
                    messages=[{"role": "system", "content": SYSTEM},
                              {"role": "user", "content": USER.format(code=_code_for_prompt(art), n=args.n)}],
                )
                reqs = [str(x).strip() for x in json.loads(reply.choices[0].message.content)["requirements"] if str(x).strip()]
            except Exception as exc:  # a failed file is skipped, not retried forever
                print(f"skip {art.id}: {type(exc).__name__}", flush=True)
                continue
            with SYN_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"project": label, "dataset": name, "code_id": art.id, "requirements": reqs[: args.n]}) + "\n")
            print(f"{name} {art.id}: {len(reqs)} requirements ({time.time() - t0:.0f} s)", flush=True)
    print(f"done: {sum(1 for _ in SYN_FILE.open())} files in {SYN_FILE}")
    return 0


# ----------------------------------------------------------------------------- batches for a chat model
BATCH_PROMPT = """You are a business analyst who writes software requirements for a requirements specification.

Below are {n} source-code files, each with an ID. For EACH file write {per} different requirements that a stakeholder could have written and that this code helps to fulfil.

Rules:
- One sentence each, starting with "The system shall" (a few may start "When ..., the system shall ...").
- Describe what the users or the data are and what the system does, in business language. Do NOT mention class names, method names, variables or file names.
- Each requirement must really be something THIS code does, not a generic statement that fits any file.
- Make the {per} requirements different in focus: for example one about the main behaviour, one about a validation / rule / constraint, one about data or security. Vary the length and wording.
- Do not copy comments or strings from the code word for word.

Return ONLY a JSON array, nothing else, exactly in this form (use the IDs exactly as given):
[{{"id": "F0001", "requirements": ["The system shall ...", "The system shall ...", "The system shall ..."]}}]

FILES:
"""


def cmd_inputs(args: argparse.Namespace) -> int:
    """Write numbered batch files to paste into a chat model, plus the id map used by ``ingest``."""
    from agents.traceability_agent.reranker.data import _load

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["code_id"] for l in SYN_FILE.read_text().splitlines()} if SYN_FILE.exists() else set()
    files: list[tuple[str, str, str]] = []
    for name in args.datasets:
        _, code, _, _ = _load(name)
        picked = [c for c in code if len("".join(_code_for_prompt(c).split())) > 200 and c.id not in done]
        random.Random(args.seed).shuffle(picked)
        files += [(name, c.id, _code_for_prompt(c, args.max_chars)) for c in picked[: args.per_project]]
    random.Random(args.seed).shuffle(files)
    mapping = {}
    for b in range(0, len(files), args.batch):
        chunk = files[b : b + args.batch]
        text = BATCH_PROMPT.format(n=len(chunk), per=args.per_file)
        for name, code_id, code in chunk:
            fid = f"F{len(mapping) + 1:04d}"
            mapping[fid] = {"dataset": name, "code_id": code_id}
            text += f"\n=== {fid} ===\n{code}\n"
        (out / f"batch_{b // args.batch + 1:03d}.txt").write_text(text, encoding="utf-8")
    (out / "map.json").write_text(json.dumps(mapping, indent=1), encoding="utf-8")
    print(f"{len(files)} files in {-(-len(files) // args.batch)} batch files in {out}/ (paste each one into the chat model; save its reply as replies/batch_NNN.json)")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Read the chat model's replies (one file per batch) into the training file."""
    import re

    mapping = json.loads((Path(args.batches) / "map.json").read_text(encoding="utf-8"))
    done = {json.loads(l)["code_id"] for l in SYN_FILE.read_text().splitlines()} if SYN_FILE.exists() else set()
    added = bad = 0
    SYN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SYN_FILE.open("a", encoding="utf-8") as f:
        for path in sorted(Path(args.replies).glob("*")):
            if path.suffix not in (".json", ".txt", ".md"):
                continue
            raw = path.read_text(encoding="utf-8")
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            try:
                items = json.loads(m.group(0)) if m else []
            except json.JSONDecodeError:
                print(f"{path.name}: not valid JSON, skipped")
                continue
            for it in items:
                info = mapping.get(str(it.get("id")))
                reqs = [str(r).strip() for r in it.get("requirements", []) if str(r).strip().lower().startswith(("the system", "when"))]
                if not info or not reqs or info["code_id"] in done:
                    bad += 1
                    continue
                f.write(json.dumps({"project": info["dataset"], "dataset": info["dataset"], "code_id": info["code_id"], "requirements": reqs, "source": "chat_model"}) + "\n")
                done.add(info["code_id"])
                added += 1
    print(f"added {added} files ({bad} skipped: unknown id, duplicate, or no valid requirement); training file now has {len(done)} files")
    return 0


PAIRS_FILE = ROOT / "data" / "synthetic" / "pairs.jsonl"


def cmd_ingest_pairs(args: argparse.Namespace) -> int:
    """Read fully synthetic (requirement, code, hard negatives) replies from a chat model into pairs.jsonl."""
    import re

    seen = {json.loads(l)["requirement"].strip().lower() for l in PAIRS_FILE.read_text().splitlines()} if PAIRS_FILE.exists() else set()
    added = bad = 0
    PAIRS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PAIRS_FILE.open("a", encoding="utf-8") as f:
        for path in sorted(Path(args.replies).glob("*")):
            if path.suffix not in (".json", ".txt", ".md"):
                continue
            m = re.search(r"\[.*\]", path.read_text(encoding="utf-8"), re.DOTALL)
            try:
                items = json.loads(m.group(0)) if m else []
            except json.JSONDecodeError:
                print(f"{path.name}: not valid JSON, skipped")
                continue
            for it in items:
                req, code = str(it.get("requirement", "")).strip(), str(it.get("code", "")).strip()
                negs = [str(n).strip() for n in it.get("hard_negatives", []) if len(str(n).strip()) >= 40][:3]
                if len(req) < 20 or len(code) < 40 or req.lower() in seen:
                    bad += 1
                    continue
                seen.add(req.lower())
                f.write(json.dumps({"requirement": req, "code": code, "hard_negatives": negs, "source": path.name}) + "\n")
                added += 1
    print(f"added {added} pairs ({bad} skipped: too short or duplicate); {len(seen)} pairs in {PAIRS_FILE}")
    return 0


# ----------------------------------------------------------------------------- evaluate
class _STEmbedder:
    """Adapter so retrieval.embedding_matrix can use a fine-tuned SentenceTransformer."""

    def __init__(self, model: Any) -> None:
        self.model = model

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return self.model.encode(list(texts), batch_size=32, convert_to_numpy=True, show_progress_bar=False).tolist()


def _closest_chunk(req: str, code: str, model: Any, chunk: int) -> str:
    """The chunk of ``code`` the untrained model finds closest to ``req`` (what stage 1 will compare at test time)."""
    from agents.traceability_agent.retrieval import chunk_words

    chunks = chunk_words(code, chunk)
    if len(chunks) == 1:
        return chunks[0]
    e = model.encode([req] + chunks, convert_to_numpy=True, show_progress_bar=False)
    e = e / np.maximum(np.linalg.norm(e, axis=1, keepdims=True), 1e-9)
    return chunks[int(np.argmax(e[1:] @ e[0]))]


def _best_chunk_pairs(pairs: list[tuple], model: Any, chunk: int) -> list[tuple]:
    """(requirement, code[, hard negative]) -> the same with each code replaced by its closest chunk."""
    return [(p[0], _closest_chunk(p[0], p[1], model, chunk)) + ((_closest_chunk(p[0], p[2], model, chunk),) if len(p) > 2 and p[2] else ()) for p in pairs]


def _train(base: str, pairs: list[Any], seed: int, epochs: int, batch_size: int = 16, max_len: int = 128, lr: float = 2e-5, scale: float = 20.0) -> Any:
    """Fine-tune with in-batch negatives (a plain loop, so no extra package is needed). A batch never holds the same code twice.

    A pair may carry a third item, a list of hard-negative code texts that join the candidates of its batch.
    """
    import torch
    from sentence_transformers import SentenceTransformer

    torch.manual_seed(seed)
    rng = random.Random(seed)
    model = SentenceTransformer(base, device=DEVICE)
    model.max_seq_length = max_len  # chunks are 60 words; a shorter limit keeps memory low (long padded batches got the process killed)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)

    def embed(texts: list[str]) -> Any:
        # newer sentence-transformers versions add non-tensor entries (a "modality" string): move tensors only
        feats = {k: (v.to(model.device) if hasattr(v, "to") else v) for k, v in model.tokenize(texts).items()}
        out = model(feats)["sentence_embedding"]
        return torch.nn.functional.normalize(out, dim=1)

    model.train()
    for _ in range(epochs):
        order = pairs[:]
        rng.shuffle(order)
        batches: list[list[tuple]] = []
        for pair in order:  # greedy: put the pair in the first batch that has room and not the same code
            for batch in batches:
                if len(batch) < batch_size and all(pair[1] != q[1] for q in batch):
                    batch.append(pair)
                    break
            else:
                batches.append([pair])
        for batch in batches:
            if len(batch) < 2:
                continue
            # the third item is one hard-negative text or a list of them (a bare string must not be iterated: that gave one-letter "texts")
            extra = [n for x in batch if len(x) > 2 for n in ([x[2]] if isinstance(x[2], str) else list(x[2]))]
            q, c = embed([x[0] for x in batch]), embed([x[1] for x in batch] + extra)
            loss = torch.nn.functional.cross_entropy(q @ c.T * scale, torch.arange(len(batch), device=model.device))
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    return model


def cmd_evaluate(args: argparse.Namespace) -> int:
    from agents.traceability_agent.preprocess import retrieval_text
    from agents.traceability_agent.reranker.data import _load
    from agents.traceability_agent.retrieval import chunk_words, embedding_matrix, tfidf_matrix, zscore_fuse
    from agents.traceability_agent.config import CHUNK_WORDS
    from shared.embeddings.embedder import Embedder

    base_name = Embedder().model_name
    from sentence_transformers import SentenceTransformer

    base = SentenceTransformer(base_name, device=DEVICE)

    # training pairs
    syn_rows = [json.loads(l) for l in SYN_FILE.read_text(encoding="utf-8").splitlines()] if SYN_FILE.exists() else []
    code_text: dict[str, str] = {}
    for name in TRAIN:
        _, code, _, _ = _load(name)
        code_text.update({c.id: retrieval_text(c) for c in code})
    syn = [(r, code_text[row["code_id"]]) for row in syn_rows if row["code_id"] in code_text for r in row["requirements"]]

    real_all: list[tuple[str, str]] = []
    for name in TRAIN:
        reqs, code, links, _ = _load(name)
        rt = {r.id: r.text for r in reqs}
        ct = {c.id: retrieval_text(c) for c in code}
        real_all += [(rt[s], ct[t]) for s, t in links if s in rt and t in ct]
    rng = random.Random(args.seed)
    rng.shuffle(real_all)
    # fully synthetic (requirement, code, hard negatives): a hand-made folder (--user-dataset) or pairs.jsonl from a chat model
    rows: list[dict[str, Any]] = []
    if args.user_dataset:
        rows = [{"requirement": r, "code": c, "hard_negatives": h} for r, c, h in load_user_dataset(args.user_dataset)]
        random.Random(args.seed).shuffle(rows)
        rows = rows[: args.pairs]
    elif PAIRS_FILE.exists():
        rows = [json.loads(l) for l in PAIRS_FILE.read_text(encoding="utf-8").splitlines()]
    n_syn = len(syn) or len(rows)
    real = real_all[:n_syn]
    print(f"requirements written for real code: {len(syn)} from {len(syn_rows)} files; fully synthetic pairs: {len(rows)}; "
          f"real expert pairs used for comparison: {len(real)} (of {len(real_all)})", flush=True)

    arms: dict[str, list[Any]] = {}
    if syn:
        arms["synthetic requirements, real code"] = _best_chunk_pairs(syn, base, CHUNK_WORDS)
    if rows:
        best = _best_chunk_pairs([(r["requirement"], r["code"]) for r in rows], base, CHUNK_WORDS)
        arms["fully synthetic pairs"] = best
        with_hard = [(q, c, _closest_chunk(q, r["hard_negatives"][0], base, CHUNK_WORDS)) for (q, c), r in zip(best, rows) if r["hard_negatives"]]
        arms["fully synthetic pairs + hard negatives"] = with_hard
    arms["real (same number)"] = _best_chunk_pairs(real, base, CHUNK_WORDS)
    if rows:
        arms["real + fully synthetic pairs + hard negatives"] = arms["real (same number)"] + arms["fully synthetic pairs + hard negatives"]
    results_extra = {"fully_synthetic_pairs": len(rows), "user_dataset": args.user_dataset, "arm_sizes": {a: len(p) for a, p in arms.items()}}

    tests = {n: _load(n) for n in TEST}
    ks = [5, 10]

    def evaluate(model: Any) -> dict[str, dict[int, dict[str, list[tuple[int, int]]]]]:
        """kind -> k -> dataset -> per-requirement (hits, true links)."""
        emb = _STEmbedder(model)
        res: dict[str, dict[int, dict[str, list[tuple[int, int]]]]] = {kind: {k: {} for k in ks} for kind in ("embeddings", "hybrid")}
        for name, (reqs, targets, gold, _) in tests.items():
            e = embedding_matrix(reqs, targets, emb, retrieval_text, CHUNK_WORDS)
            h = zscore_fuse([tfidf_matrix(reqs, targets, retrieval_text, CHUNK_WORDS), e])
            for kind, m in (("embeddings", e), ("hybrid", h)):
                rows = per_requirement_hits(m, reqs, targets, gold, ks)
                for k in ks:
                    res[kind][k][name] = rows[k]
        return res

    def summary(res: dict) -> dict:
        return {kind: {str(k): {"macro": round(macro_recall(res[kind][k]), 4), **{n: round(pooled_recall(r), 4) for n, r in res[kind][k].items()}} for k in ks} for kind in res}

    results: dict[str, Any] = {"arm_sizes": {a: len(p) for a, p in arms.items()}, "user_dataset": args.user_dataset, "files": len(syn_rows), "seeds": args.seeds, "epochs": args.epochs,
                               **results_extra, "test_sets": TEST, "metric": "recall of the true links in the top-k of each requirement (macro = mean over the three test sets)", "arms": {}}
    untrained = evaluate(base)
    results["arms"]["untrained"] = summary(untrained)
    print("untrained", results["arms"]["untrained"], flush=True)

    cache_file = ROOT / "data" / "synthetic" / f"_cache_{args.pairs}_{args.epochs}.json"  # finished runs survive an interruption
    cache: dict[str, Any] = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    for arm, pairs in arms.items():
        per_seed, gains = [], {kind: {k: [] for k in ks} for kind in ("embeddings", "hybrid")}
        for s in range(args.seeds):
            key = f"{arm}|{s}|{len(pairs)}"
            if key not in cache:
                model = _train(base_name, pairs, seed=s, epochs=args.epochs)
                res = evaluate(model)
                del model
                import gc

                gc.collect()
                cache[key] = {"summary": summary(res), "gain": {kind: {str(k): macro_bootstrap_diff(res[kind][k], untrained[kind][k]) for k in ks} for kind in res}}
                cache_file.write_text(json.dumps(cache), encoding="utf-8")
            per_seed.append(cache[key]["summary"])
            for kind in cache[key]["gain"]:
                for k in ks:
                    gains[kind][k].append(cache[key]["gain"][kind][str(k)])
            print(arm, "seed", s, {kind: {k: v["macro"] for k, v in d.items()} for kind, d in per_seed[-1].items()}, flush=True)
        results["arms"][arm] = {
            "per_seed": per_seed,
            "macro_mean": {kind: {str(k): round(float(np.mean([p[kind][str(k)]["macro"] for p in per_seed])), 4) for k in ks} for kind in ("embeddings", "hybrid")},
            "gain_vs_untrained": {kind: {str(k): {"mean": round(float(np.mean([d[0] for d in gains[kind][k]])), 4),
                                                  "ci95_first_seed": [round(gains[kind][k][0][1], 4), round(gains[kind][k][0][2], 4)]} for k in ks}
                                  for kind in ("embeddings", "hybrid")},
        }
    out = ROOT / "data" / "results" / "synthetic_minilm.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    shown = {}
    for arm, v in results["arms"].items():
        shown[arm] = v["macro_mean"] if "macro_mean" in v else {kind: {k: x["macro"] for k, x in d.items()} for kind, d in v.items()}
    print(json.dumps(shown, indent=1))
    print(f"saved {out}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="LLM writes requirements for sampled training code files")
    g.add_argument("--datasets", nargs="+", default=TRAIN)
    g.add_argument("--per-project", type=int, default=40)
    g.add_argument("-n", type=int, default=2, help="requirements per file")
    g.add_argument("--seed", type=int, default=7)
    g.set_defaults(func=cmd_generate)
    i = sub.add_parser("inputs", help="write batch files to paste into a chat model (ChatGPT, Claude ...)")
    i.add_argument("--datasets", nargs="+", default=TRAIN)
    i.add_argument("--per-project", type=int, default=80)
    i.add_argument("--batch", type=int, default=8, help="code files per batch file")
    i.add_argument("--per-file", type=int, default=3, help="requirements per file")
    i.add_argument("--max-chars", type=int, default=1500)
    i.add_argument("--seed", type=int, default=11)
    i.add_argument("--out", default=str(ROOT / "data" / "synthetic" / "batches"))
    i.set_defaults(func=cmd_inputs)
    q = sub.add_parser("ingest-pairs", help="read fully synthetic (requirement, code, hard negatives) replies into pairs.jsonl")
    q.add_argument("--replies", default=str(ROOT / "data" / "synthetic" / "pair_replies"))
    q.set_defaults(func=cmd_ingest_pairs)
    n = sub.add_parser("ingest", help="read the chat model's replies into data/synthetic/train_requirements.jsonl")
    n.add_argument("--batches", default=str(ROOT / "data" / "synthetic" / "batches"))
    n.add_argument("--replies", default=str(ROOT / "data" / "synthetic" / "replies"))
    n.set_defaults(func=cmd_ingest)
    e = sub.add_parser("evaluate", help="fine-tune MiniLM on synthetic / real / both and test on unseen real projects")
    e.add_argument("--user-dataset", nargs="+", help="one or more folders of {requirement, code, hard_negatives} json files")
    e.add_argument("--pairs", type=int, default=1000, help="pairs used from the user dataset (and the same number of real pairs)")
    e.add_argument("--seeds", type=int, default=3)
    e.add_argument("--epochs", type=int, default=3)
    e.add_argument("--seed", type=int, default=7)
    e.set_defaults(func=cmd_evaluate)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
