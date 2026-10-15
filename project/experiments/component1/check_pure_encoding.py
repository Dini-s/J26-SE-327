
from pathlib import Path
import pandas as pd

dataset_folder = Path(
    r"C:\Users\shero\OneDrive - Sri Lanka Institute of Information Technology\Research Project\DataSets"
)

file_path = next(dataset_folder.rglob("pure_subset.csv"))
df = pd.read_csv(file_path, encoding="cp1252", low_memory=False)

print("=" * 55)
print("PURE DATASET - QUALITY AUDIT")
print("=" * 55)

print(f"\nTotal rows: {len(df)}")
print(f"Total columns: {len(df.columns)}")

print("\n1. Missing values:")
print(df.isnull().sum().to_string())

print("\n2. Empty requirement sentences:")
sentences = df["sentence"].fillna("").astype(str).str.strip()
print("Empty sentences:", sentences.eq("").sum())

print("\n3. Duplicate sentence analysis:")
normalised = sentences.str.lower().str.replace(r"\s+", " ", regex=True)
print("Exact duplicate sentences:", sentences.duplicated().sum())
print("Duplicate normalised sentences:", normalised.duplicated().sum())
print("Unique normalised sentences:", normalised.nunique())

print("\n4. Label distributions:")
for column in ["security", "reliability", "NFR_boolean"]:
    print(f"\n{column}:")
    print(df[column].value_counts(dropna=False).sort_index().to_string())
    print("\nPercentages:")
    print(
        (df[column].value_counts(normalize=True, dropna=False) * 100)
        .round(2)
        .to_string()
    )

print("\n5. Sample requirements:")
print(df[["sentence", "security", "reliability", "NFR_boolean"]].head(5).to_string(index=False))

print("\nAudit completed. Original dataset was not modified.")
