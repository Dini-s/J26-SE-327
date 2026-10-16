"""Data for the cross-encoder reranker: dataset preparation and training / test pairs.

Two commands (run from the project root):

    python -m agents.traceability_agent.reranker.data prepare
        Turns the SMOS, eANCI (translated to English, see data/translated_en) and EBT datasets into the same
        ``data/processed/<name>/{artifacts,traces,gold}.json`` format as the other datasets.

    python -m agents.traceability_agent.reranker.data pairs [--retrieval hybrid|tfidf]
        Writes ``data/reranker/{train,valid,test_candidates}.jsonl`` and ``meta.json``.

The split is by dataset, never by pair, so a test project is never seen in training:

    train: iTrust, SMOS, eANCI, eTour        test: LibEST, CM-1, EBT

Train pairs are the true links plus *hard* negatives (candidates that stage-1 retrieval ranks highly but that
are not true links) plus a few random negatives. Test data are the stage-1 top-K candidates of every
requirement with their gold label, so the reranker is measured on exactly what it would see in the pipeline.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from agents.traceability_agent.config import CHUNK_WORDS
from agents.traceability_agent.preprocess import retrieval_text, split_identifiers, strip_boilerplate
from agents.traceability_agent.retrieval import chunk_words, hybrid_matrix, tfidf_matrix
from shared.schemas.traceability import Artifact

ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"
TRANSLATED = ROOT / "data" / "translated_en"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "reranker"

TRAIN = ["itrust", "smos", "eanci", "etour"]
TEST = ["libest", "cm1", "ebt"]
SEED = 13


# ---------------------------------------------------------------- dataset preparation
def _read(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _write_dataset(name: str, label: str, reqs: dict[str, str], code: dict[str, str], links: set[tuple[str, str]], language: str) -> dict[str, int]:
    """Write artifacts / traces / gold for one dataset in the format of the existing processed datasets."""
    links = {(s, t) for s, t in links if s in reqs and t in code}
    artifacts = [{"id": i, "type": "requirement", "text": t, "metadata": {"dataset": label, "layer": "requirement"}} for i, t in reqs.items()]
    artifacts += [{"id": i, "type": "code", "text": t, "metadata": {"dataset": label, "layer": "code", "language": language}} for i, t in code.items()]
    traces = [{"source_id": s, "target_id": t, "link_type": "requirement_to_code", "confidence": 1.0,
               "justification": "Ground truth: expert-labelled link in the dataset.", "status": "verified",
               "text_hash": None, "verified_at": None, "last_checked_at": None} for s, t in sorted(links)]
    gold = [[s, t, (s, t) in links] for s in reqs for t in code]
    out = PROCESSED / name
    out.mkdir(parents=True, exist_ok=True)
    for fname, payload in (("artifacts.json", artifacts), ("traces.json", traces), ("gold.json", gold)):
        (out / fname).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"requirements": len(reqs), "code": len(code), "links": len(links)}


def _coest_xml(name: str, label: str) -> dict[str, int]:
    """SMOS / eANCI: translated requirements and code, links from answer_req_code.xml."""
    base = TRANSLATED / label
    reqs = json.loads((base / "requirements_en.json").read_text(encoding="utf-8"))
    code = {p.stem: _read(p) for p in sorted((base / "code_en").glob("*.txt"))}
    xml = (base / "answer_req_code.xml").read_text(encoding="utf-8", errors="replace")
    links = set(re.findall(r"<source_artifact_id>(.*?)</source_artifact_id><target_artifact_id>(.*?)</target_artifact_id>", xml))
    return _write_dataset(name, label, reqs, code, links, "java")


def _ebt() -> dict[str, int]:
    base = RAW / "EBT"
    reqs = {}
    for line in _read(base / "requirements.txt").splitlines():
        if "\t" in line:
            rid, text = line.split("\t", 1)
            reqs[rid.strip()] = text.strip()
    code = {p.name: _read(p) for p in sorted((base / "source_code").glob("*.java"))}
    links = set()
    for line in _read(base / "code_ground.txt").splitlines():
        parts = line.split()
        links |= {(parts[0], t) for t in parts[1:]}
    return _write_dataset("ebt", "EBT", reqs, code, links, "java")


def prepare() -> None:
    for name, stats in (("smos", _coest_xml("smos", "SMOS")), ("eanci", _coest_xml("eanci", "eANCI")), ("ebt", _ebt())):
        print(f"{name:6} requirements={stats['requirements']:3} code={stats['code']:4} true links={stats['links']:4}")


# ---------------------------------------------------------------- pairs
class Focus:
    """Chooses, for each (requirement, code file), the code chunks that fit a 512-token input.

    CodeBERT reads about 512 tokens, so a long file cannot be passed whole. The two chunks that look most like the
    requirement (TF-IDF) are kept, in their original order, so the cross-encoder sees the relevant part of the file.
    """

    def __init__(self, reqs: list[Artifact], code: list[Artifact], words: int = 80, keep: int = 2) -> None:
        self.words, self.keep = words, keep
        self.chunks: dict[str, list[str]] = {}
        retr: dict[str, list[str]] = {}
        for c in code:
            body = strip_boilerplate(c) if c.type == "code" else c.text
            pieces = chunk_words(body, words)
            self.chunks[c.id] = pieces
            retr[c.id] = [split_identifiers(p) if c.type == "code" else p for p in pieces]
        corpus = [retrieval_text(r) for r in reqs] + [t for ts in retr.values() for t in ts]
        self.vec = TfidfVectorizer(lowercase=True, stop_words="english").fit(corpus)
        self.req_vec = {r.id: self.vec.transform([retrieval_text(r)]) for r in reqs}
        self.chunk_vec = {cid: self.vec.transform(ts) for cid, ts in retr.items()}

    def text(self, req_id: str, code_id: str) -> str:
        pieces = self.chunks[code_id]
        if len(pieces) <= self.keep:
            return " ".join(pieces)
        scores = (self.chunk_vec[code_id] @ self.req_vec[req_id].T).toarray().ravel()
        best = sorted(np.argsort(-scores, kind="stable")[: self.keep])
        return " ... ".join(pieces[i] for i in best)


def _load(name: str) -> tuple[list[Artifact], list[Artifact], set[tuple[str, str]], str]:
    base = PROCESSED / name
    arts = [Artifact(**a) for a in json.loads((base / "artifacts.json").read_text(encoding="utf-8"))]
    traces = json.loads((base / "traces.json").read_text(encoding="utf-8"))
    reqs = [a for a in arts if a.type == "requirement"]
    targets = [a for a in arts if a.type != "requirement"]
    label = str(arts[0].metadata.get("dataset", name))
    return reqs, targets, {(t["source_id"], t["target_id"]) for t in traces}, label


def _similarity(reqs: list[Artifact], code: list[Artifact], retrieval: str, embedder: Any) -> np.ndarray:
    if retrieval == "tfidf":
        return tfidf_matrix(reqs, code, retrieval_text, CHUNK_WORDS)
    return hybrid_matrix(reqs, code, embedder, retrieval_text, CHUNK_WORDS)


def build_pairs(retrieval: str = "hybrid", hard: int = 6, random_neg: int = 3, test_k: int = 20, valid_fraction: float = 0.1) -> dict[str, Any]:
    rng = random.Random(SEED)
    embedder = None
    if retrieval == "hybrid":
        from shared.embeddings.embedder import Embedder

        embedder = Embedder()
    OUT.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {"retrieval": retrieval, "hard_per_requirement": hard, "random_per_requirement": random_neg,
                            "test_k": test_k, "train": TRAIN, "test": TEST, "seed": SEED, "datasets": {}}
    train_rows: list[dict] = []
    valid_rows: list[dict] = []
    test_rows: list[dict] = []
    for name in TRAIN + TEST:
        reqs, code, links, label = _load(name)
        focus = Focus(reqs, code)
        sims = _similarity(reqs, code, retrieval, embedder)
        true_by_req: dict[str, set[str]] = {}
        for s, t in links:
            true_by_req.setdefault(s, set()).add(t)
        info = {"requirements": len(reqs), "code": len(code), "true_links": len(links)}
        if name in TRAIN:
            linked = [r for r in reqs if r.id in true_by_req]
            valid_ids = {r.id for r in rng.sample(linked, max(1, int(len(linked) * valid_fraction)))}
            n = {"pos": 0, "hard": 0, "random": 0}
            for i, r in enumerate(reqs):
                pos = true_by_req.get(r.id, set())
                if not pos:
                    continue  # a requirement without any true link says nothing about what a true link looks like
                order = [j for j in np.argsort(-sims[i], kind="stable") if code[j].id not in pos]
                chosen = [(code[j].id, "hard") for j in order[:hard]]
                pool = [c.id for c in code if c.id not in pos and c.id not in {x for x, _ in chosen}]
                chosen += [(cid, "random") for cid in rng.sample(pool, min(random_neg, len(pool)))]
                rows = [(cid, 1, "pos") for cid in sorted(pos) if cid in focus.chunks] + [(cid, 0, kind) for cid, kind in chosen]
                target = valid_rows if r.id in valid_ids else train_rows
                for cid, label_, kind in rows:
                    target.append({"dataset": label, "source_id": r.id, "target_id": cid, "query": r.text, "doc": focus.text(r.id, cid), "label": label_, "kind": kind})
                    n[kind] += 1 if target is train_rows else 0
            info.update({"train_pairs": dict(n), "valid_requirements": len(valid_ids)})
        else:
            hits = 0
            for i, r in enumerate(reqs):
                for rank, j in enumerate(np.argsort(-sims[i], kind="stable")[:test_k], start=1):
                    is_true = code[j].id in true_by_req.get(r.id, set())
                    hits += is_true
                    test_rows.append({"dataset": label, "source_id": r.id, "target_id": code[j].id, "query": r.text, "doc": focus.text(r.id, code[j].id),
                                      "label": int(is_true), "stage1_rank": rank, "stage1_score": round(float(sims[i, j]), 4)})
            info.update({"stage1_recall_at_k": round(hits / len(links), 3) if links else None, "candidates": len(reqs) * min(test_k, len(code))})
        meta["datasets"][label] = info
    for fname, rows in (("train.jsonl", train_rows), ("valid.jsonl", valid_rows), ("test_candidates.jsonl", test_rows)):
        with (OUT / fname).open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    meta["rows"] = {"train": len(train_rows), "valid": len(valid_rows), "test_candidates": len(test_rows)}
    meta["train_label_balance"] = {"positive": sum(r["label"] for r in train_rows), "negative": sum(1 - r["label"] for r in train_rows)}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def bundle(out: Path) -> Path:
    """Zip what the Colab notebooks need (train.py, evaluate.py, learning_curve.py and the pair files) into ``out``."""
    import zipfile

    here = Path(__file__).resolve().parent
    needed = [OUT / n for n in ("train.jsonl", "valid.jsonl", "test_candidates.jsonl", "meta.json")]
    missing = [p.name for p in needed if not p.exists()]
    if missing:
        raise SystemExit(f"missing {missing}: run `python -m agents.traceability_agent.reranker.data pairs` first")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(here / "train.py", "train.py")
        z.write(here / "evaluate.py", "evaluate.py")
        z.write(here / "learning_curve.py", "learning_curve.py")
        for p in needed:
            z.write(p, f"data/reranker/{p.name}")
    return out


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare", help="build processed datasets for SMOS, eANCI and EBT")
    b = sub.add_parser("bundle", help="zip train.py, evaluate.py, learning_curve.py and the pair files for the Colab notebooks")
    b.add_argument("--out", type=Path, default=ROOT / "data" / "reranker_colab.zip")
    p = sub.add_parser("pairs", help="write train / valid / test pair files")
    p.add_argument("--retrieval", choices=["hybrid", "tfidf"], default="hybrid", help="stage-1 method used for hard negatives and test candidates")
    p.add_argument("--hard", type=int, default=6)
    p.add_argument("--random", type=int, default=3, dest="random_neg")
    p.add_argument("--test-k", type=int, default=20)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        prepare()
        return 0
    if args.command == "bundle":
        print("written", bundle(args.out))
        return 0
    meta = build_pairs(args.retrieval, args.hard, args.random_neg, args.test_k)
    print(json.dumps(meta, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
