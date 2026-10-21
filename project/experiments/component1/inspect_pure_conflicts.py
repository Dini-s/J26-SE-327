
from pathlib import Path
import pandas as pd

dataset_folder = Path(
    r"C:\Users\shero\OneDrive - Sri Lanka Institute of Information Technology\Research Project\DataSets"
)

file_path = next(dataset_folder.rglob("pure_subset.csv"))
df = pd.read_csv(file_path, encoding="cp1252", low_memory=False)

df["normalized_sentence"] = (
    df["sentence"]
    .fillna("")
    .astype(str)
    .str.lower()
    .str.replace(r"\s+", " ", regex=True)
    .str.strip()
)

for label in ["NFR_boolean", "security", "reliability"]:
    counts = df.groupby("normalized_sentence")[label].nunique()
    conflict_sentences = counts[counts > 1].index

    print("\n" + "=" * 70)
    print(f"CONFLICTS FOR: {label}")
    print("=" * 70)

    if len(conflict_sentences) == 0:
        print("No conflicting sentences found.")
        continue

    for sentence in conflict_sentences:
        group = df[df["normalized_sentence"] == sentence]

        print("\nSentence:", group["sentence"].iloc[0])
        print(
            group[["id", label]].to_string(index=False)
        )

print("\nInspection complete. Original dataset was not modified.")
