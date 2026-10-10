
from pathlib import Path
from collections import Counter
import csv
import re

data_dir = Path("project/data/component1/raw/user_stories")
output_dir = Path("project/data/component1/audit_reports_component1")
output_dir.mkdir(parents=True, exist_ok=True)

records = []
file_summary = []

def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

for path in sorted(data_dir.glob("*.txt")):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line_number, line in enumerate(lines, start=1):
        records.append({
            "source_file": path.name,
            "line_number": line_number,
            "requirement_text": line,
            "normalized_text": normalize(line),
            "starts_with_as_a_or_an": bool(
                re.match(r"^as an?\s+", line, re.IGNORECASE)
            ),
        })

    file_summary.append({
        "file": path.name,
        "non_empty_lines": len(lines),
        "user_story_style_lines": sum(
            bool(re.match(r"^as an?\s+", line, re.IGNORECASE))
            for line in lines
        ),
        "other_lines": sum(
            not bool(re.match(r"^as an?\s+", line, re.IGNORECASE))
            for line in lines
        ),
    })

counts = Counter(
    r["normalized_text"] for r in records
    if r["normalized_text"]
)

for record in records:
    record["normalized_occurrences"] = counts[
        record["normalized_text"]
    ]

with (output_dir / "user_story_records.csv").open(
    "w", newline="", encoding="utf-8-sig"
) as f:
    writer = csv.DictWriter(f, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)

with (output_dir / "user_story_file_summary.csv").open(
    "w", newline="", encoding="utf-8-sig"
) as f:
    writer = csv.DictWriter(f, fieldnames=file_summary[0].keys())
    writer.writeheader()
    writer.writerows(file_summary)

duplicates = [
    r for r in records
    if r["normalized_text"]
    and r["normalized_occurrences"] > 1
]

with (output_dir / "user_story_duplicates.csv").open(
    "w", newline="", encoding="utf-8-sig"
) as f:
    writer = csv.DictWriter(f, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(duplicates)

print("=" * 55)
print("USER STORY DATASET AUDIT")
print("=" * 55)
print("Files:", len(file_summary))
print("Non-empty lines:", len(records))
print("User-story-style lines:", sum(
    x["user_story_style_lines"] for x in file_summary
))
print("Other lines:", sum(x["other_lines"] for x in file_summary))
print("Unique normalized texts:", len(counts))
print("Duplicate records:", len(duplicates))
print("Audit reports saved to:", output_dir)
