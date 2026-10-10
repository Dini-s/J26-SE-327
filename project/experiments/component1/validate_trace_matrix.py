from pathlib import Path
import pandas as pd

path = Path(
    "project/data/component1/processed/"
    "promise_trace_relationships.csv"
)

df = pd.read_csv(path)

print("=" * 55)
print("TRACEABILITY CSV VALIDATION")
print("=" * 55)

print("\nShape:", df.shape)
print("\nColumns:", df.columns.tolist())
print("\nMissing values:\n", df.isnull().sum())

print("\nRelationship distribution:")
print(df["relationship"].value_counts())

print("\nRelationship percentages:")
print(
    (df["relationship"].value_counts(normalize=True) * 100)
    .round(2)
)

print("\nProjects and relationship counts:")
print(
    pd.crosstab(df["project"], df["relationship"])
)

print("\nDuplicate relationship rows:",
      df.duplicated().sum())

print("\nUnique projects:", df["project"].nunique())
print("Unique FR IDs:", df["fr_id"].nunique())
print("Unique NFR IDs:", df["nfr_id"].nunique())

print("\nSample records:")
print(df.head(10).to_string(index=False))

print("\nValidation report completed.")