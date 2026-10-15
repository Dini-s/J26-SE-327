
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FILE = (
    ROOT / "data" / "component1" / "raw"
    / "arta_evaluation" / "001_dataset1kv1.xlsx"
)
OUT = (
    ROOT / "data" / "component1" / "audit_reports_component1"
    / "arta_excel_label_conflicts.csv"
)

df = pd.read_excel(FILE)

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

df["_normalized_text"] = normalized
conflict_groups = []

for text, group in df.groupby("_normalized_text", dropna=False):
    if len(group) < 2:
        continue

    differing = [
        col for col in label_cols
        if group[col].nunique(dropna=False) > 1
    ]

    if differing:
        for _, row in group.iterrows():
            record = row.drop(labels=["_normalized_text"]).to_dict()
            record["ConflictingColumns"] = ", ".join(differing)
            conflict_groups.append(record)

result = pd.DataFrame(conflict_groups)
result.to_csv(OUT, index=False, encoding="utf-8-sig")

print("Conflicting records:", len(result))
print("Conflicting columns by group:")

if not result.empty:
    print(
        result.groupby("ConflictingColumns")
        .size()
        .to_string()
    )
    print("\nDetailed records:")
    print(result.to_string(index=False))

print("\nReport saved:", OUT)
