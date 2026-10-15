import argparse
import csv
from pathlib import Path

import numpy as np
import pandas as pd


def package_from_file_path(file_path: str) -> str:
    """Derive a Java package name from its source-file path."""
    path = Path(file_path.replace("\\", "/"))
    parent_parts = path.parent.parts

    # src/main/java/org/example/package_name/Class.java
    try:
        java_index = parent_parts.index("java")
    except ValueError:
        return ""

    package_parts = parent_parts[java_index + 1 :]
    if not package_parts:
        return "(default package)"

    return ".".join(package_parts)


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate GraphCodeBERT file embeddings into package embeddings."
    )
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--embeddings", required=True)
    parser.add_argument("--output-dir", default="data/processed/semantic")
    args = parser.parse_args()

    metadata_path = Path(args.metadata)
    embeddings_path = Path(args.embeddings)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = pd.read_csv(metadata_path)
    embeddings = np.load(embeddings_path)

    required_columns = {
        "embedding_index",
        "repository_id",
        "file_path",
    }
    missing_columns = required_columns - set(metadata.columns)
    if missing_columns:
        raise ValueError(f"Missing metadata columns: {sorted(missing_columns)}")

    if len(metadata) != len(embeddings):
        raise ValueError(
            f"Metadata rows ({len(metadata)}) do not match "
            f"embedding rows ({len(embeddings)})."
        )

    if metadata["embedding_index"].duplicated().any():
        raise ValueError("Duplicate embedding_index values found.")

    if not np.isfinite(embeddings).all():
        raise ValueError("Embedding matrix contains non-finite values.")

    if embeddings.ndim != 2 or embeddings.shape[1] != 768:
        raise ValueError(
            f"Expected a 2D matrix with 768 dimensions; got {embeddings.shape}."
        )

    # Select only production Java files for this repository.
    repo_rows = metadata[metadata["repository_id"].astype(str) == args.repo_id].copy()

    normalized_paths = (
        repo_rows["file_path"].astype(str).str.replace("\\", "/", regex=False)
    )
    production_mask = normalized_paths.str.contains("src/main/java/", regex=False)

    production = repo_rows.loc[production_mask].copy()
    if production.empty:
        raise ValueError(
            f"No src/main/java/ files found for repository {args.repo_id}."
        )

    production["package_path"] = production["file_path"].apply(package_from_file_path)
    production = production[production["package_path"] != ""].copy()

    if production.empty:
        raise ValueError("No valid package paths could be derived.")

    # Use embedding_index to align metadata rows with embedding vectors.
    indices = production["embedding_index"].astype(int).to_numpy()
    if (indices < 0).any() or (indices >= len(embeddings)).any():
        raise ValueError("An embedding_index is outside the embedding matrix.")

    production["embedding_index"] = indices

    package_vectors = []
    package_records = []

    for package_path, group in production.groupby("package_path", sort=True):
        group_indices = group["embedding_index"].to_numpy()
        package_vector = embeddings[group_indices].mean(axis=0)

        # Normalize the mean vector for consistent downstream similarity use.
        norm = np.linalg.norm(package_vector)
        if norm > 0:
            package_vector = package_vector / norm

        package_vectors.append(package_vector.astype(np.float32))
        package_records.append(
            {
                "repository_id": args.repo_id,
                "package_path": package_path,
                "java_file_count": len(group),
                "semantic_embedding_index": len(package_records),
                "model_name": (
                    str(group["model_name"].iloc[0])
                    if "model_name" in group.columns
                    else ""
                ),
            }
        )

    vectors = np.vstack(package_vectors).astype(np.float32)
    package_metadata = pd.DataFrame(package_records)

    output_prefix = output_dir / args.repo_id
    vector_file = output_prefix.with_name(
        output_prefix.name + "_package_embeddings.npy"
    )
    metadata_file = output_prefix.with_name(
        output_prefix.name + "_package_metadata.csv"
    )

    np.save(vector_file, vectors)
    package_metadata.to_csv(metadata_file, index=False)

    print(f"Repository: {args.repo_id}")
    print(f"Production Java files: {len(production)}")
    print(f"Packages represented: {len(package_metadata)}")
    print(f"Package embedding matrix shape: {vectors.shape}")
    print(f"Saved vectors: {vector_file}")
    print(f"Saved metadata: {metadata_file}")


if __name__ == "__main__":
    main()
