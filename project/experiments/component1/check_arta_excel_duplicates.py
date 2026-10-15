
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "component1" / "raw" / "arta_evaluation"

files = [
    "001_dataset1kv1.xlsx",
    "003_dataset1kv1_ARTA_result.xlsx",
    "005_dataset1kv1_Smella_result.xlsx",
]

for name in files:
    path = DATA_DIR / name
    df = pd.read_excel(path)

    text_col = "Requirement_text"
    label_cols = [c for c in df.columns if c not in [text_col, "File"]]

    normalized = (
        df[text_col]
        .fillna("")
        .astype(str)
        .str.casefold()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    duplicates = df[normalized.duplicated(keep=False)].copy()
    duplicates["_normalized_text"] = normalized[normalized.duplicated(keep=False)]

    print(f"\n{'=' * 70}")
    print(name)
    print("Total rows:", len(df))
    print("Duplicate rows involved:", len(duplicates))
    print("Unique duplicated requirement texts:",
          duplicates["_normalized_text"].nunique())

    if not duplicates.empty:
        conflicts = 0

        for _, group in duplicates.groupby("_normalized_text"):
            if any(group[col].nunique(dropna=False) > 1 for col in label_cols):
                conflicts += 1

        print("Duplicated requirement groups with label conflicts:", conflicts)
        print("\nDuplicate examples:")
        print(
            duplicates[[text_col, "File", *label_cols]]
            .head(8)
            .to_string(index=False)
        )
