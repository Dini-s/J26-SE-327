from pathlib import Path
import pandas as pd

# Project root: ...\project
PROJECT_ROOT = Path(__file__).resolve().parents[3]

BASE = PROJECT_ROOT / "data" / "processed"
SEMANTIC_DIR = BASE / "semantic"

HRIM_FILE = BASE / "hrim_fused_features.csv"
OUTPUT_FILE = BASE / "hrim_semantic_fused_features.csv"

if OUTPUT_FILE.exists():
    raise FileExistsError(
        f"{OUTPUT_FILE} already exists. "
        "Inspect it before deciding whether to replace it."
    )

hrim = pd.read_csv(HRIM_FILE)
key_cols = ["repository", "package_path"]

if hrim.duplicated(key_cols).any():
    raise ValueError("HRIM contains duplicate repository/package keys.")

files = sorted(SEMANTIC_DIR.glob("*_aligned_semantic_features.csv"))

if len(files) != 7:
    raise ValueError(f"Expected 7 aligned files, found {len(files)}.")

frames = []
expected_semantic_cols = None

for file in files:
    df = pd.read_csv(file)

    if not set(key_cols).issubset(df.columns):
        raise ValueError(f"Missing join keys in {file.name}")

    semantic_cols = [c for c in df.columns if c.startswith("semantic_")]

    if len(semantic_cols) != 768:
        raise ValueError(
            f"{file.name}: expected 768 semantic columns, found {len(semantic_cols)}"
        )

    if expected_semantic_cols is None:
        expected_semantic_cols = semantic_cols
    elif set(semantic_cols) != set(expected_semantic_cols):
        raise ValueError(f"Semantic column names differ in {file.name}")

    part = df[key_cols + semantic_cols].copy()

    if part.duplicated(key_cols).any():
        raise ValueError(f"Duplicate keys in {file.name}")

    frames.append(part)

semantic = pd.concat(frames, ignore_index=True)

if semantic.duplicated(key_cols).any():
    raise ValueError("Duplicate keys across semantic files.")

result = hrim.merge(semantic, on=key_cols, how="left", validate="one_to_one")

semantic_cols = expected_semantic_cols
result["semantic_features_available"] = result[semantic_cols].notna().all(axis=1)

result.to_csv(OUTPUT_FILE, index=False)

print("Saved:", OUTPUT_FILE)
print("HRIM rows:", len(hrim))
print("Merged rows:", len(result))
print("Semantic dimensions:", len(semantic_cols))
print(
    "Packages with semantic vectors:", int(result["semantic_features_available"].sum())
)
print(
    "Packages without semantic vectors:",
    int((~result["semantic_features_available"]).sum()),
)
print("Duplicate package keys:", int(result.duplicated(key_cols).sum()))
print("Missing semantic values by repository:")
print(
    result.groupby("repository")["semantic_features_available"]
    .agg(["count", "sum"])
    .to_string()
)
