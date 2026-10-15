import pandas as pd
from pathlib import Path

path = Path("data/processed/hrim_package_features.csv")
df = pd.read_csv(path)

print("Dataset shape:", df.shape)
print("\nColumns:")
print(df.columns.tolist())

print("\nEvolution match status:")
print(df["evolution_status"].value_counts(dropna=False))

print("\nMissing evolution metrics:")
metrics = [
    "commit_count",
    "contributor_count",
    "files_changed",
    "total_insertions",
    "total_deletions",
    "total_churn",
]

print(df[metrics].isna().sum())

print("\nMissing evolution packages by repository:")
missing = df[df["evolution_status"] != "exact_package_match"]

print(
    missing.groupby("repository")
    .agg(
        missing_packages=("package_path", "count"),
        examples=("package_path", lambda x: ", ".join(x.head(5))),
    )
    .to_string()
)

print("\nPackage origin:")
print(df["package_origin"].value_counts(dropna=False))

print("\nDuplicate repository-package pairs:")
duplicates = df.duplicated(
    subset=["repository", "package_path"],
    keep=False,
)
print(df.loc[duplicates, ["repository", "package_path"]])
