
from pathlib import Path
import pandas as pd
import re

RAW_DIR = Path("project/data/component1/raw")
OUTPUT_DIR = Path(
    "project/data/component1/audit_reports_component1"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Excel file and its requirement-text column
DATASETS = {
    "DS1.xlsx": "Requirement_text",
    "DS2.xlsx": "text",
    "DS3.xlsx": "text",
    "DS4.xlsx": "Requirement",
}


def normalize_text(value):
    """Normalize text for duplicate comparison."""
    if pd.isna(value):
        return ""

    text = str(value).lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)

    return text


records = []

for filename, text_column in DATASETS.items():
    file_path = RAW_DIR / filename

    if not file_path.exists():
        print(f"NOT FOUND: {file_path}")
        continue

    df = pd.read_excel(file_path)

    if text_column not in df.columns:
        print(f"COLUMN NOT FOUND: {filename} - {text_column}")
        continue

    for row_number, text in enumerate(df[text_column], start=2):
        normalized = normalize_text(text)

        if normalized:
            records.append({
                "dataset": filename,
                "row_number": row_number,
                "requirement": str(text),
                "normalized_requirement": normalized,
            })

all_data = pd.DataFrame(records)

if all_data.empty:
    print("No requirement records found. Check the file paths.")
    raise SystemExit(1)

# Requirements repeated within or across datasets
duplicate_mask = all_data.duplicated(
    subset=["normalized_requirement"],
    keep=False,
)

duplicates = all_data[duplicate_mask].sort_values(
    "normalized_requirement"
)

duplicates_path = OUTPUT_DIR / "arta_duplicate_requirements.csv"
duplicates.to_csv(
    duplicates_path,
    index=False,
    encoding="utf-8-sig",
)

# Summary of duplicate groups
summary = (
    duplicates.groupby("normalized_requirement")
    .agg(
        occurrences=("normalized_requirement", "size"),
        datasets=("dataset", lambda x: ", ".join(sorted(set(x)))),
        original_examples=("requirement", "first"),
    )
    .reset_index()
    .sort_values("occurrences", ascending=False)
)

summary_path = OUTPUT_DIR / "arta_duplicate_summary.csv"
summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

print("\n===== ARTA DUPLICATE AUDIT =====")
print(f"Requirements inspected: {len(all_data)}")
print(f"Rows belonging to duplicate groups: {len(duplicates)}")
print(f"Unique duplicate groups: {len(summary)}")

print("\nDuplicates by dataset:")
if duplicates.empty:
    print("No normalized duplicates found.")
else:
    print(duplicates.groupby("dataset").size().to_string())

print(f"\nDetailed report: {duplicates_path}")
print(f"Summary report: {summary_path}")
