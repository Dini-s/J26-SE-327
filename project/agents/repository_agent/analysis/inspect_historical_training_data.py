from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "labels" / "hrim_historical_training_table_v1.csv"

df = pd.read_csv(DATA)

target = "architecture_change_proxy_label"

metadata = {
    "sample_id",
    "repository",
    "package_path",
    "feature_snapshot_date",
    "label_observation_snapshot_date",
    "feature_commit_hash",
    target,
}

features = [c for c in df.columns if c not in metadata]

print("=" * 60)
print("HRIM HISTORICAL TRAINING DATA INSPECTION")
print("=" * 60)

print("\nShape:", df.shape)
print("\nColumns:")
print(df.columns.tolist())

print("\nFeature columns:")
print(features)

print("\nFeature data types:")
print(df[features].dtypes)

print("\nMissing feature values:")
print(df[features].isna().sum())

print("\nInfinite numeric values:")
numeric = df[features].select_dtypes(include="number")
print((~numeric.map(lambda x: pd.notna(x) and abs(x) != float("inf"))).sum())

print("\nTarget distribution:")
print(df[target].value_counts(dropna=False))

print("\nRows per repository:")
print(df.groupby("repository").size().sort_values(ascending=False))

print("\nPotentially repeated packages:")
print(
    "Unique repository/package pairs:",
    df[["repository", "package_path"]].drop_duplicates().shape[0],
)
print("Unique sample IDs:", df["sample_id"].nunique())

print("\nInspection completed.")
