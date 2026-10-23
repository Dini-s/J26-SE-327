import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(
        description="Align package-level GraphCodeBERT embeddings with HRIM."
    )
    parser.add_argument("--repo-id", required=True)
    parser.add_argument(
        "--hrim",
        default="data/processed/hrim_package_features.csv",
    )
    parser.add_argument(
        "--semantic-dir",
        default="data/processed/semantic",
    )
    args = parser.parse_args()

    repo_id = args.repo_id
    semantic_dir = Path(args.semantic_dir)

    metadata_path = semantic_dir / f"{repo_id}_package_metadata.csv"
    embeddings_path = semantic_dir / f"{repo_id}_package_embeddings.npy"
    output_path = semantic_dir / f"{repo_id}_aligned_semantic_features.csv"

    # 1. Validate input files
    hrim_path = Path(args.hrim)

    for path in (hrim_path, metadata_path, embeddings_path):
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

    # 2. Load HRIM, semantic metadata, and embeddings
    hrim = pd.read_csv(hrim_path)
    metadata = pd.read_csv(metadata_path)
    embeddings = np.load(embeddings_path)

    required_hrim = {"repository", "package_path"}

    required_metadata = {
        "repository_id",
        "package_path",
        "semantic_embedding_index",
        "java_file_count",
        "model_name",
    }

    if missing := required_hrim - set(hrim.columns):
        raise ValueError(f"Missing HRIM columns: {sorted(missing)}")

    if missing := required_metadata - set(metadata.columns):
        raise ValueError(f"Missing semantic metadata columns: {sorted(missing)}")

    if embeddings.ndim != 2 or embeddings.shape[1] != 768:
        raise ValueError(f"Expected 768-dimensional embeddings; got {embeddings.shape}")

    if len(metadata) != len(embeddings):
        raise ValueError("Metadata row count does not match embedding count.")

    if not np.isfinite(embeddings).all():
        raise ValueError("Embeddings contain non-finite values.")

    # 3. Select semantic metadata for the registered repository
    semantic = metadata[metadata["repository_id"].astype(str) == repo_id].copy()

    if semantic.empty:
        raise ValueError(f"No semantic metadata found for repository ID {repo_id}.")

    # 4. Find corresponding HRIM repository records

    # First try an exact repository ID match.
    hrim_repo = hrim[hrim["repository"].astype(str) == repo_id].copy()

    if hrim_repo.empty:
        # For newly registered repositories, identify a historical
        # HRIM repository by an exact match of the complete package set.
        semantic_package_paths = set(semantic["package_path"].dropna().astype(str))

        candidates = []

        for repository_name, group in hrim.groupby("repository"):
            hrim_package_paths = set(group["package_path"].dropna().astype(str))

            if hrim_package_paths == semantic_package_paths:
                candidates.append(repository_name)

        if len(candidates) != 1:
            raise ValueError(
                f"Could not uniquely match repository {repo_id} "
                f"to an HRIM repository. Candidates: {candidates}"
            )

        matched_repository = candidates[0]

        hrim_repo = hrim[hrim["repository"] == matched_repository].copy()

        # Use the matched HRIM repository key for package merging.
        semantic["repository"] = matched_repository

        print(
            "Matched HRIM repository by exact package paths:",
            matched_repository,
        )

    else:
        semantic["repository"] = repo_id

    # 5. Validate package keys and embedding indices
    if hrim_repo.empty:
        raise ValueError(f"No HRIM records found for {repo_id}.")

    if hrim_repo.duplicated(["repository", "package_path"]).any():
        raise ValueError("Duplicate package keys in HRIM.")

    if semantic.duplicated(["repository", "package_path"]).any():
        raise ValueError("Duplicate package keys in semantic metadata.")

    if semantic["semantic_embedding_index"].isna().any():
        raise ValueError("Missing semantic embedding indices.")

    numeric_indices = pd.to_numeric(
        semantic["semantic_embedding_index"],
        errors="raise",
    )

    if not np.equal(
        numeric_indices.to_numpy(),
        np.floor(numeric_indices.to_numpy()),
    ).all():
        raise ValueError("Embedding indices must be integers.")

    indices = numeric_indices.astype(int).to_numpy()

    if (indices < 0).any() or (indices >= len(embeddings)).any():
        raise ValueError("An embedding index is out of range.")

    if len(np.unique(indices)) != len(indices):
        raise ValueError("Duplicate embedding indices.")

    if set(indices) != set(range(len(embeddings))):
        raise ValueError("Embedding indices do not cover every vector row.")

    # 6. Build package-level semantic feature table
    vector_columns = [f"semantic_emb_{i:03d}" for i in range(embeddings.shape[1])]

    vector_frame = pd.DataFrame(
        embeddings[indices],
        columns=vector_columns,
    )

    semantic_features = pd.concat(
        [
            semantic[
                [
                    "repository",
                    "package_path",
                    "java_file_count",
                    "model_name",
                ]
            ].reset_index(drop=True),
            vector_frame,
        ],
        axis=1,
    )

    # 7. Check package matching in both directions
    hrim_keys = hrim_repo[["repository", "package_path"]]
    semantic_keys = semantic_features[["repository", "package_path"]]

    hrim_check = hrim_keys.merge(
        semantic_keys,
        on=["repository", "package_path"],
        how="left",
        indicator=True,
        validate="one_to_one",
    )

    semantic_check = semantic_keys.merge(
        hrim_keys,
        on=["repository", "package_path"],
        how="left",
        indicator=True,
        validate="one_to_one",
    )

    missing_vectors = int((hrim_check["_merge"] == "left_only").sum())

    extra_vectors = int((semantic_check["_merge"] == "left_only").sum())

    print("\nHRIM packages missing semantic vectors:")
    print(
        hrim_check.loc[
            hrim_check["_merge"] == "left_only",
            ["repository", "package_path"],
        ].to_string(index=False)
    )

    print("\nSemantic packages missing HRIM records:")
    print(
        semantic_check.loc[
            semantic_check["_merge"] == "left_only",
            ["repository", "package_path"],
        ].to_string(index=False)
    )

    # 8. Merge while preserving all HRIM package records
    aligned = hrim_repo.merge(
        semantic_features,
        on=["repository", "package_path"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    matched = int((aligned["_merge"] == "both").sum())
    aligned = aligned.drop(columns="_merge")

    # 9. Save to a separate output file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    aligned.to_csv(output_path, index=False)

    # 10. Print summary
    print("\n--- Semantic Alignment Summary ---")
    print(f"Registered repository ID: {repo_id}")
    print(f"HRIM repository key: {hrim_repo['repository'].iloc[0]}")
    print(f"HRIM packages: {len(hrim_repo)}")
    print(f"Semantic packages: {len(semantic_features)}")
    print(f"Matched packages: {matched}")
    print(f"HRIM packages missing semantic vectors: {missing_vectors}")
    print(f"Semantic packages missing HRIM records: {extra_vectors}")
    print(f"Semantic dimensions: {len(vector_columns)}")
    print(f"Aligned dataset shape: {aligned.shape}")
    print(f"Saved: {output_path}")

    if missing_vectors or extra_vectors:
        print(
            "WARNING: Review unmatched package keys before "
            "using these features for model evaluation."
        )
    else:
        print("SUCCESS: All package keys match in both directions.")


if __name__ == "__main__":
    main()
