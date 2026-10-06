"""Convert raw traceability datasets into our Artifact / TraceabilityLink schemas.

Usage (from the project root):
    python scripts/load_dataset.py --dataset itrust   # requirement -> code (primary)
    python scripts/load_dataset.py --dataset cm1      # requirement -> design

Raw files are only read, never modified. Outputs go to ``data/processed/<dataset>/``:
    artifacts.json  list of Artifact (shared.schemas.traceability)
    traces.json     list of TraceabilityLink, one per ground-truth link
    gold.json       [source_id, target_id, is_true_link] for every requirement x target pair,
                    ready for ``python -m agents.traceability_agent.evaluate --gold ...``

Mapping decisions:
    * iTrust: "Use Cases" -> requirement; "Java Code" / "JSP Code" -> code (the agent's
      requirement -> code case). Links already run use case -> code.
    * CM-1: High Level Requirements (SRS...) -> requirement; Low Level Requirements
      (DPUSDS...) -> design; links are flipped to run requirement -> design.
    * Raw trace tables list the true links (CM-1) or label every pair (iTrust). Either
      way, every pair not marked true is a non-link, so gold.json holds the full
      requirement x target cross product. Without the negatives, false positives could
      never be counted and precision would be meaningless.
    * Prose is whitespace-collapsed; code keeps its line structure (only line endings,
      trailing spaces and runs of blank lines are normalised).
"""

import argparse
import csv
import json
import sys
import unicodedata
from itertools import product
from pathlib import Path
from typing import Callable, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.schemas.traceability import Artifact, TraceabilityLink  # noqa: E402

DEFAULT_RAW = Path.home() / "Downloads" / "traceability_datasets"

CM1_LAYERS = {"High Level Requirements": "requirement", "Low Level Requirements": "design"}
ITRUST_LAYERS = {"Use Cases": "requirement", "Java Code": "code", "JSP Code": "code"}


def normalise_prose(text: str) -> str:
    """NFC-normalise and collapse all whitespace runs to single spaces."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def normalise_code(text: str) -> str:
    """NFC-normalise, unify line endings, strip trailing spaces, cap blank-line runs at one."""
    lines = [ln.rstrip() for ln in unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    out: list[str] = []
    for ln in lines:
        if ln == "" and out and out[-1] == "":
            continue
        out.append(ln)
    return "\n".join(out).strip()


def make_artifact(
    seen: dict[str, Artifact], art_id: str, layer: str, content: str, layers: dict[str, str], dataset: str
) -> None:
    """Normalise one raw row into ``seen`` (first occurrence of an id wins)."""
    if layer not in layers:
        raise ValueError(f"Unknown layer {layer!r} for {art_id}")
    type_ = layers[layer]
    text = normalise_prose(content) if type_ != "code" else normalise_code(content)
    if art_id in seen:
        if seen[art_id].text != text:
            print(f"warning: duplicate id {art_id!r} with different text; keeping first")
        return
    metadata = {"dataset": dataset, "layer": layer}
    if layer == "JSP Code":
        metadata["language"] = "jsp"
    elif layer == "Java Code":
        metadata["language"] = "java"
    seen[art_id] = Artifact(id=art_id, type=type_, text=text, metadata=metadata)


def load_cm1(raw: Path) -> tuple[list[Artifact], set[tuple[str, str]]]:
    """Read CM-1 (artifacts.csv + traces.csv) as artifacts and (requirement, design) true pairs."""
    seen: dict[str, Artifact] = {}
    with open(raw / "artifacts.csv", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            make_artifact(seen, row["id"].strip(), row["layer"], row["content"], CM1_LAYERS, "CM-1")
    pairs: set[tuple[str, str]] = set()
    with open(raw / "traces.csv", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["label"].strip() != "1":
                continue
            low, high = row["s_id"].strip(), row["t_id"].strip()
            if low not in seen or high not in seen:
                raise ValueError(f"Trace references unknown artifact: {low} -> {high}")
            if seen[high].type != "requirement" or seen[low].type != "design":
                raise ValueError(f"Trace has unexpected layers: {low} -> {high}")
            pairs.add((high, low))  # flipped to requirement -> design
    return list(seen.values()), pairs


def load_itrust(raw: Path) -> tuple[list[Artifact], set[tuple[str, str]]]:
    """Read iTrust (Parquet) as artifacts and (use case, code) true pairs."""
    import pyarrow.parquet as pq  # only needed for the Parquet datasets

    def table(name: str) -> list[dict]:
        (path,) = sorted((raw / "iTrust" / name).glob("*.parquet"))
        return pq.read_table(path).to_pylist()

    seen: dict[str, Artifact] = {}
    for row in table("artifacts"):
        make_artifact(seen, row["id"], row["layer"], row["content"], ITRUST_LAYERS, "iTrust")
    pairs: set[tuple[str, str]] = set()
    for row in table("traces"):
        if row["label"] != 1:
            continue
        s, t = row["source"], row["target"]
        if s not in seen or t not in seen:
            raise ValueError(f"Trace references unknown artifact: {s} -> {t}")
        if seen[s].type != "requirement" or seen[t].type != "code":
            raise ValueError(f"Trace has unexpected layers: {s} -> {t}")
        pairs.add((s, t))
    return list(seen.values()), pairs


DATASETS: dict[str, Callable[[Path], tuple[list[Artifact], set[tuple[str, str]]]]] = {
    "cm1": load_cm1,
    "itrust": load_itrust,
}


def build_outputs(
    artifacts: Sequence[Artifact], true_pairs: set[tuple[str, str]]
) -> tuple[list[TraceabilityLink], list[list]]:
    """Build ground-truth links and the full labelled gold set (all requirement x target pairs)."""
    types = {a.id: a.type for a in artifacts}
    reqs = [a.id for a in artifacts if a.type == "requirement"]
    targets = [a.id for a in artifacts if a.type != "requirement"]
    links = [
        TraceabilityLink(
            source_id=s,
            target_id=t,
            link_type=f"requirement_to_{types[t]}",
            confidence=1.0,
            justification="Ground truth: expert-labelled link in the dataset.",
        )
        for s, t in sorted(true_pairs)
    ]
    gold = [[s, t, (s, t) in true_pairs] for s, t in product(reqs, targets)]
    return links, gold


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Convert one dataset and write the processed files."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="itrust")
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW, help="dir with the raw dataset files")
    parser.add_argument("--out", type=Path, help="default: data/processed/<dataset>")
    args = parser.parse_args(argv)
    out = args.out or PROJECT_ROOT / "data" / "processed" / args.dataset

    artifacts, true_pairs = DATASETS[args.dataset](args.raw)
    links, gold = build_outputs(artifacts, true_pairs)

    out.mkdir(parents=True, exist_ok=True)
    (out / "artifacts.json").write_text(json.dumps([a.model_dump() for a in artifacts], indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "traces.json").write_text(json.dumps([l.model_dump() for l in links], indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "gold.json").write_text(json.dumps(gold), encoding="utf-8")

    n_req = sum(a.type == "requirement" for a in artifacts)
    linked_reqs = len({s for s, _ in true_pairs})
    print(f"{args.dataset}: {len(artifacts)} artifacts ({n_req} requirement, {len(artifacts) - n_req} targets)")
    print(f"true links: {len(links)} (requirements with >=1 link: {linked_reqs}/{n_req})")
    print(f"gold pairs: {len(gold)} ({len(gold) - len(links)} negatives)")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
