
from pathlib import Path
import pandas as pd

ROOT = Path("project/data/component1/raw")
REPORT_DIR = Path("project/data/component1/audit_reports_component1")

FILES = ["DS1.xlsx", "DS2.xlsx", "DS3.xlsx", "DS4.xlsx"]


def normalize(text):
    import re

    text = str(text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


TEXT_COLUMNS = {
    "DS1.xlsx": "Requirement_text",
    "DS2.xlsx": "text",
    "DS3.xlsx": "text",
    "DS4.xlsx": "Requirement",
}

frames = []

for filename in FILES:
    path = ROOT / filename
    df = pd.read_excel(path)
    text_col = TEXT_COLUMNS[filename]

    df["source_file"] = filename
    df["source_row"] = range(2, len(df) + 2)
    df["normalized_requirement"] = df[text_col].fillna("").map(normalize)

    # Exclude empty requirements
    df = df[df["normalized_requirement"] != ""].copy()

    frames.append(df)

all_data = pd.concat(frames, ignore_index=True)

# Keep only requirements that appear in more than one row
counts = all_data["normalized_requirement"].value_counts()
duplicate_texts = counts[counts > 1].index

duplicates = all_data[
    all_data["normalized_requirement"].isin(duplicate_texts)
].copy()

# Keep source file, row, requirement, and annotation columns
metadata = {
    "source_file",
    "source_row",
    "normalized_requirement",
}

annotation_columns = [
    col for col in duplicates.columns
    if col not in metadata
    and col not in {
        "Requirement_text", "text", "Requirement",
        "filename", "File", "File name"
    }
]

output_columns = [
    "source_file",
    "source_row",
    "normalized_requirement",
]

for col in ["Requirement_text", "text", "Requirement"]:
    if col in duplicates.columns:
        output_columns.append(col)

output_columns += annotation_columns

output_columns = list(dict.fromkeys(
    col for col in output_columns if col in duplicates.columns
))

REPORT_DIR.mkdir(parents=True, exist_ok=True)

output_file = REPORT_DIR / "arta_duplicate_label_comparison.csv"
duplicates[output_columns].to_csv(
    output_file, index=False, encoding="utf-8-sig"
)

print("Duplicate rows:", len(duplicates))
print("Unique duplicate requirement groups:", len(duplicate_texts))
print("Report saved:", output_file)
print("\nAnnotation columns:")
print(annotation_columns)
