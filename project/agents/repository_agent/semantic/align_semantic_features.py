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

    for path in (Path(args.hrim), metadata_path, embeddings_path):
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

    hrim = pd.read_csv(args.hrim)
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
        raise ValueError(f"Missing metadata columns: {sorted(missing)}")

    if embeddings.ndim != 2 or embeddings.shape[1] != 768:
        raise ValueError(f"Expected 768-dimensional vectors; got {embeddings.shape}")

    if len(metadata) != len(embeddings):
        raise ValueError("Metadata row count does not match embedding count.")

    if not np.isfinite(embeddings).all():
        raise ValueError("Embeddings contain non-finite values.")

    hrim_repo = hrim[hrim["repository"] == repo_id].copy()
    semantic = metadata[metadata["repository_id"] == repo_id].copy()

    if hrim_repo.empty:
        raise ValueError(f"No HRIM records found for {repo_id}.")

    if semantic.empty:
        raise ValueError(f"No semantic metadata found for {repo_id}.")

    if hrim_repo.duplicated(["repository", "package_path"]).any():
        raise ValueError("Duplicate package keys in HRIM.")

    if semantic.duplicated(["repository_id", "package_path"]).any():
        raise ValueError("Duplicate package keys in semantic metadata.")

    if semantic["semantic_embedding_index"].isna().any():
        raise ValueError("Missing semantic embedding indices.")

    indices = semantic["semantic_embedding_index"].astype(int).to_numpy()

    if (indices < 0).any() or (indices >= len(embeddings)).any():
        raise ValueError("An embedding index is out of range.")

    if len(np.unique(indices)) != len(indices):
        raise ValueError("Duplicate embedding indices.")

    if set(indices) != set(range(len(embeddings))):
        raise ValueError("Embedding indices do not cover every vector row.")

    vector_columns = [f"semantic_emb_{i:03d}" for i in range(embeddings.shape[1])]

    vector_frame = pd.DataFrame(
        embeddings[indices],
        columns=vector_columns,
    )

    semantic_features = pd.concat(
        [
            semantic[
                [
                    "repository_id",
                    "package_path",
                    "java_file_count",
                    "model_name",
                ]
            ]
            .rename(columns={"repository_id": "repository"})
            .reset_index(drop=True),
            vector_frame,
        ],
        axis=1,
    )

    hrim_keys = hrim_repo[["repository", "package_path"]]
    semantic_keys = semantic_features[["repository", "package_path"]]

    # Check package matching in both directions.
    hrim_check = hrim_keys.merge(
        semantic_keys,
        on=["repository", "package_path"],
        how="left",
        indicator=True,
    )

    semantic_check = semantic_keys.merge(
        hrim_keys,
        on=["repository", "package_path"],
        how="left",
        indicator=True,
    )

    missing_vectors = int((hrim_check["_merge"] == "left_only").sum())
    extra_vectors = int((semantic_check["_merge"] == "left_only").sum())

    # Print the exact package keys that do not match.
    missing_hrim_packages = hrim_check.loc[
        hrim_check["_merge"] == "left_only",
        ["repository", "package_path"],
    ]

    extra_semantic_packages = semantic_check.loc[
        semantic_check["_merge"] == "left_only",
        ["repository", "package_path"],
    ]

    print("\nHRIM packages missing semantic vectors:")
    print(missing_hrim_packages.to_string(index=False))

    print("\nSemantic packages missing HRIM records:")
    print(extra_semantic_packages.to_string(index=False))

    # Preserve every HRIM package, even if a semantic vector is missing.
    aligned = hrim_repo.merge(
        semantic_features,
        on=["repository", "package_path"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    matched = int((aligned["_merge"] == "both").sum())
    aligned = aligned.drop(columns="_merge")

    aligned.to_csv(output_path, index=False)

    print(f"Repository: {repo_id}")
    print(f"HRIM packages: {len(hrim_repo)}")
    print(f"Semantic packages: {len(semantic_features)}")
    print(f"Matched packages: {matched}")
    print(f"HRIM packages missing semantic vectors: {missing_vectors}")
    print(f"Semantic packages missing HRIM records: {extra_vectors}")
    print(f"Semantic dimensions: {len(vector_columns)}")
    print(f"Aligned dataset shape: {aligned.shape}")
    print(f"Saved: {output_path}")

    if missing_vectors or extra_vectors:
        print("WARNING: Review unmatched package keys before model training.")
    else:
        print("SUCCESS: All package keys match in both directions.")


if __name__ == "__main__":
    main()
