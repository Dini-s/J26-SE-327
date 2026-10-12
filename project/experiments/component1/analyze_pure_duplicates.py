
from pathlib import Path
import pandas as pd

dataset_folder = Path(
    r"C:\Users\shero\OneDrive - Sri Lanka Institute of Information Technology\Research Project\DataSets"
)

file_path = next(dataset_folder.rglob("pure_subset.csv"))
df = pd.read_csv(file_path, encoding="cp1252", low_memory=False)

# Normalize text for duplicate comparison
df["normalized_sentence"] = (
    df["sentence"]
    .fillna("")
    .astype(str)
    .str.lower()
    .str.replace(r"\s+", " ", regex=True)
    .str.strip()
)

label_columns = ["NFR_boolean", "security", "reliability"]

print("=" * 55)
print("PURE DATASET - DUPLICATE AND LABEL CONFLICT AUDIT")
print("=" * 55)

print("\nTotal rows:", len(df))
print("Unique normalized sentences:", df["normalized_sentence"].nunique())

# Keep only sentences that occur more than once
duplicate_rows = df[
    df.duplicated("normalized_sentence", keep=False)
].copy()

print("Rows belonging to repeated sentences:", len(duplicate_rows))
print(
    "Distinct repeated sentences:",
    duplicate_rows["normalized_sentence"].nunique()
)

conflict_reports = []

for label in label_columns:
    # Count distinct labels for each normalized sentence
    label_counts = (
        df.groupby("normalized_sentence")[label]
        .nunique(dropna=False)
    )

    conflict_sentences = label_counts[label_counts > 1].index

    print(f"\n{label}:")
    print("Label distribution:")
    print(df[label].value_counts(dropna=False).sort_index().to_string())
    print("Sentences with conflicting labels:", len(conflict_sentences))

    if len(conflict_sentences) > 0:
        examples = df[
            df["normalized_sentence"].isin(conflict_sentences)
        ][["sentence", label, "id"]].copy()

        examples["label_column"] = label
        conflict_reports.append(examples)

# Save reports inside the project
output_folder = Path("project/data/audit_reports")
output_folder.mkdir(parents=True, exist_ok=True)

duplicate_rows.to_csv(
    output_folder / "pure_duplicate_sentences.csv",
    index=False,
    encoding="utf-8-sig"
)

if conflict_reports:
    conflicts = pd.concat(conflict_reports, ignore_index=True)
else:
    conflicts = pd.DataFrame(
        columns=["sentence", "NFR_boolean", "security",
                 "reliability", "id", "label_column"]
    )

conflicts.to_csv(
    output_folder / "pure_label_conflicts.csv",
    index=False,
    encoding="utf-8-sig"
)

print("\nReports saved:")
print(output_folder / "pure_duplicate_sentences.csv")
print(output_folder / "pure_label_conflicts.csv")
print("\nOriginal dataset was not modified.")
