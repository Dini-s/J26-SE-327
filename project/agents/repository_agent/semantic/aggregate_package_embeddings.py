import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd


PACKAGE_PATTERN = re.compile(
    r"^\s*package\s+([\w.]+)\s*;",
    re.MULTILINE,
)

EXCLUDED_DIRS = {
    "test",
    "tests",
    "testing",
    "testfixtures",
    "test-fixtures",
    "benchmark",
    "benchmarks",
    "jmh",
    "target",
    "build",
    "generated",
    "out",
}


def is_production_source(file_path: str) -> bool:
    path = file_path.replace("\\", "/").lstrip("./")
    parts = path.split("/")
    lower = [part.lower() for part in parts]

    if not path.lower().endswith(".java"):
        return False
    if parts[-1].lower() == "module-info.java":
        return False
    if any(part.startswith(".") for part in parts):
        return False
    if any(part in EXCLUDED_DIRS for part in lower):
        return False

    if re.search(r"(^|/)src/main/java/", path, re.I):
        return True
    if re.search(r"(^|/)src/java/", path, re.I):
        return True
    if re.match(r"^modules/[^/]+/src/.+\.java$", path, re.I):
        return True
    if re.match(r"^src/[^/]+/src/.+\.java$", path, re.I):
        return True

    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--embeddings", required=True)
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--output-dir", default="data/processed/semantic")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = pd.read_csv(args.metadata)
    embeddings = np.load(args.embeddings)

    required = {"embedding_index", "repository_id", "file_path"}
    missing = required - set(metadata.columns)
    if missing:
        raise ValueError(f"Missing metadata columns: {sorted(missing)}")
    if embeddings.ndim != 2 or embeddings.shape[1] != 768:
        raise ValueError(f"Unexpected embedding shape: {embeddings.shape}")
    if len(metadata) != len(embeddings):
        raise ValueError("Metadata and embedding counts differ.")
    if metadata["embedding_index"].duplicated().any():
        raise ValueError("Duplicate embedding indices.")
    if not np.isfinite(embeddings).all():
        raise ValueError("Non-finite embedding values detected.")

    rows = metadata[metadata["repository_id"].astype(str).eq(args.repo_id)].copy()

    selected = rows[rows["file_path"].astype(str).map(is_production_source)].copy()

    print("Embedded metadata rows:", len(rows))
    print("Production candidates:", len(selected))

    records = []
    skipped = []

    for _, row in selected.iterrows():
        relative = str(row["file_path"]).replace("\\", "/")
        source_path = (repo_path / relative).resolve()

        try:
            source_path.relative_to(repo_path)
            source = source_path.read_text(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            skipped.append(relative)
            continue

        match = PACKAGE_PATTERN.search(source)
        if not match:
            skipped.append(relative)
            continue

        records.append(
            {
                "package_path": match.group(1),
                "embedding_index": int(row["embedding_index"]),
                "model_name": (
                    str(row["model_name"]) if "model_name" in row.index else ""
                ),
            }
        )

    if not records:
        raise ValueError(
            "No eligible Java files found. Check metadata file_path format."
        )

    production = pd.DataFrame(records)
    vectors = []
    package_records = []

    for package_path, group in production.groupby("package_path", sort=True):
        indices = group["embedding_index"].to_numpy(dtype=int)
        if (indices < 0).any() or (indices >= len(embeddings)).any():
            raise ValueError("Embedding index out of bounds.")

        vector = embeddings[indices].mean(axis=0)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm

        vectors.append(vector.astype(np.float32))
        package_records.append(
            {
                "repository_id": args.repo_id,
                "package_path": package_path,
                "java_file_count": len(group),
                "semantic_embedding_index": len(package_records),
                "model_name": group["model_name"].iloc[0],
            }
        )

    package_vectors = np.vstack(vectors)
    package_metadata = pd.DataFrame(package_records)
    prefix = output_dir / args.repo_id

    np.save(
        prefix.with_name(prefix.name + "_package_embeddings.npy"),
        package_vectors,
    )
    package_metadata.to_csv(
        prefix.with_name(prefix.name + "_package_metadata.csv"),
        index=False,
    )

    print("Files aggregated:", len(production))
    print("Files skipped:", len(skipped))
    print("Packages represented:", len(package_metadata))
    print("Package embedding shape:", package_vectors.shape)
    print("Skipped path examples:", skipped[:10])


if __name__ == "__main__":
    main()
