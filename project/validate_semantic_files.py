import glob
import os
import pandas as pd

files = glob.glob(
    "data/processed/semantic/*_aligned_semantic_features.csv"
)

print("Aligned repositories:", len(files))

for file in sorted(files):
    df = pd.read_csv(file)
    semantic_columns = [
        column for column in df.columns
        if column.startswith("semantic_")
    ]

    duplicate_keys = df.duplicated(
        ["repository", "package_path"]
    ).sum()

    print(
        os.path.basename(file),
        "| rows:", len(df),
        "| semantic dimensions:", len(semantic_columns),
        "| duplicate keys:", duplicate_keys
    )
