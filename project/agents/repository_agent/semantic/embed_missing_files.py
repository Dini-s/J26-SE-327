import sys
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from agents.repository_agent.semantic.graphcodebert_encoder import (
    MODEL_NAME,
    embed_file,
)


REPO = Path("data/raw/R05_lucene").resolve()
OUTPUT = Path("data/processed/semantic")
REPO_ID = "R05_lucene"

TARGETS = (
    "lucene/analysis/common/src/java/org/apache/lucene/analysis/charfilter/HTMLStripCharFilter.java",
    "lucene/analysis/common/src/java/org/apache/lucene/analysis/email/UAX29URLEmailTokenizerImpl.java",
)


def main():
    from agents.repository_agent.semantic.graphcodebert_encoder import (
        find_java_files,
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)

    files = find_java_files(REPO, production_only=True)
    files = [
        path
        for path in files
        if any(target in path.relative_to(REPO).as_posix() for target in TARGETS)
    ]

    print(f"Files to embed: {len(files)}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    model.eval()

    vectors = []
    records = []

    for index, path in enumerate(files):
        source = path.read_text(encoding="utf-8", errors="replace")
        if not source.strip():
            print(f"Skipping empty file: {path}")
            continue

        vector, token_count, chunk_count = embed_file(source, tokenizer, model, device)

        vectors.append(vector)
        records.append(
            {
                "embedding_index": index,
                "repository_id": REPO_ID,
                "file_path": path.relative_to(REPO).as_posix(),
                "token_count": token_count,
                "chunk_count": chunk_count,
                "model_name": MODEL_NAME,
            }
        )

        print(f"[{index + 1}/{len(files)}] {path.name}")

    if not vectors:
        raise SystemExit("No embeddings were generated.")

    np.save(OUTPUT / f"{REPO_ID}_missing_embeddings.npy", np.stack(vectors))

    with (OUTPUT / f"{REPO_ID}_missing_metadata.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    print(f"Embedded: {len(vectors)}")
    print("Saved missing embeddings and metadata.")


if __name__ == "__main__":
    main()
