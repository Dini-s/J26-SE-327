
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "data" / "component1" / "audit_reports_component1"
RAW_DIR = ROOT / "data" / "component1" / "raw"

INVENTORY = REPORT_DIR / "all_source_files.csv"
OUTPUT = REPORT_DIR / "source_vs_project_verification.csv"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_name(name):
    return Path(name).name.casefold()


project_files = {}
for path in RAW_DIR.rglob("*"):
    if path.is_file():
        project_files.setdefault(normalized_name(path.name), []).append(path)

results = []

with INVENTORY.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)

    print("Inventory columns:", reader.fieldnames)

    for row in reader:
        source_name = (row.get("FileName") or "").strip()
        source_folder = (
            row.get("RelativeFolder")
            or row.get("Relative Folder")
            or ""
        ).strip()

        if not source_name:
            continue

        candidates = project_files.get(normalized_name(source_name), [])

        if not candidates:
            status = "MISSING"
            matched_path = ""
            source_hash = ""
            project_hash = ""
        else:
            # If same-name files exist in several locations, inspect each.
            source_hash = ""
            project_hash = ""
            matched_path = ""
            status = "NAME FOUND - SOURCE HASH NEEDED"

        results.append({
            "SourceFolder": source_folder,
            "FileName": source_name,
            "Status": status,
            "ProjectPath": matched_path,
            "SourceSHA256": source_hash,
            "ProjectSHA256": project_hash,
        })

with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "SourceFolder", "FileName", "Status", "ProjectPath",
        "SourceSHA256", "ProjectSHA256"
    ])
    writer.writeheader()
    writer.writerows(results)

print(f"\nInventory entries checked: {len(results)}")
print(f"Saved preliminary report: {OUTPUT}")
print("\nPreliminary filename status:")
for status in sorted({r["Status"] for r in results}):
    count = sum(r["Status"] == status for r in results)
    print(f"  {status}: {count}")
print(
    "\nNote: This is a filename-level preliminary check. "
    "It does not yet establish source/project content matches."
)
