import numpy as np
import pandas as pd
from pathlib import Path

out = Path("data/processed/semantic")
repo_id = "R05_lucene"

base_vectors_path = out / f"{repo_id}_embeddings.npy"
base_metadata_path = out / f"{repo_id}_metadata.csv"
extra_vectors_path = out / f"{repo_id}_missing_embeddings.npy"
extra_metadata_path = out / f"{repo_id}_missing_metadata.csv"

base_vectors = np.load(base_vectors_path)
extra_vectors = np.load(extra_vectors_path)
base_metadata = pd.read_csv(base_metadata_path)
extra_metadata = pd.read_csv(extra_metadata_path)

if base_vectors.ndim != 2 or extra_vectors.ndim != 2:
    raise ValueError("Both embedding arrays must be 2D.")

if base_vectors.shape[1] != 768 or extra_vectors.shape[1] != 768:
    raise ValueError("Expected 768-dimensional embeddings.")

if len(base_vectors) != len(base_metadata):
    raise ValueError("Original vectors and metadata row counts differ.")

if len(extra_vectors) != len(extra_metadata):
    raise ValueError("Supplemental vectors and metadata row counts differ.")

base_paths = set(base_metadata["file_path"].astype(str))
extra_paths = set(extra_metadata["file_path"].astype(str))

if base_paths & extra_paths:
    raise ValueError("Some supplemental files already exist in original metadata.")

# Preserve original rows and assign fresh indices to supplemental rows.
extra_metadata["embedding_index"] = range(
    len(base_vectors), len(base_vectors) + len(extra_vectors)
)

merged_vectors = np.concatenate([base_vectors, extra_vectors], axis=0)
merged_metadata = pd.concat([base_metadata, extra_metadata], ignore_index=True)

if not np.isfinite(merged_vectors).all():
    raise ValueError("Merged embeddings contain non-finite values.")

# Save to new files first, preserving the originals.
np.save(out / f"{repo_id}_merged_embeddings.npy", merged_vectors)
merged_metadata.to_csv(
    out / f"{repo_id}_merged_metadata.csv",
    index=False,
    encoding="utf-8-sig",
)

print("Original vectors:", base_vectors.shape)
print("Supplemental vectors:", extra_vectors.shape)
print("Merged vectors:", merged_vectors.shape)
print("Merged metadata rows:", len(merged_metadata))
print("Saved merged files without overwriting originals.")
