
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "data" / "component1" / "audit_reports_component1"
RAW_DIR = ROOT / "data" / "component1" / "raw"
INVENTORY = REPORT_DIR / "all_source_files.csv"
OUTPUT = REPORT_DIR / "source_vs_project_hash_verification.csv"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_relative_path(value):
    return str(value).replace("\\", "/").strip("/").casefold()


project_files = list(path for path in RAW_DIR.rglob("*") if path.is_file())

# Index project files by relative path and by filename.
by_relative_path = {}
by_filename = {}

for path in project_files:
    relative = normalized_relative_path(path.relative_to(RAW_DIR))
    by_relative_path.setdefault(relative, []).append(path)
    by_filename.setdefault(path.name.casefold(), []).append(path)


results = []

with INVENTORY.open("r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        source = Path(row["FullPath"])
        filename = row["FileName"]
        relative_folder = (row.get("RelativeFolder") or "").strip()

        if not source.is_file():
            results.append({
                "FileName": filename,
                "SourcePath": str(source),
                "Status": "SOURCE MISSING",
                "ProjectPath": "",
                "SourceSHA256": "",
                "ProjectSHA256": "",
            })
            continue

        source_hash = sha256(source)

        # First try matching the relative folder structure.
        relative_key = normalized_relative_path(
            f"{relative_folder}/{filename}" if relative_folder else filename
        )
        candidates = by_relative_path.get(relative_key, [])

        # If that does not work, check all files with the same filename.
        if not candidates:
            candidates = by_filename.get(filename.casefold(), [])

        if not candidates:
            status = "PROJECT MISSING"
            matched_path = ""
            project_hash = ""
        else:
            hashes = [(path, sha256(path)) for path in candidates]
            matches = [(path, value) for path, value in hashes
                       if value == source_hash]

            if matches:
                matched_path = str(matches[0][0])
                project_hash = matches[0][1]
                status = "MATCH"
            elif len(candidates) == 1:
                matched_path = str(candidates[0])
                project_hash = hashes[0][1]
                status = "CONTENT DIFFERS"
            else:
                matched_path = "; ".join(str(path) for path in candidates)
                project_hash = "; ".join(value for _, value in hashes)
                status = "SAME NAME - NO HASH MATCH"

        results.append({
            "FileName": filename,
            "SourcePath": str(source),
            "Status": status,
            "ProjectPath": matched_path,
            "SourceSHA256": source_hash,
            "ProjectSHA256": project_hash,
        })


with OUTPUT.open("w", encoding="utf-8-sig", newline="") as file:
    fields = [
        "FileName", "SourcePath", "Status", "ProjectPath",
        "SourceSHA256", "ProjectSHA256"
    ]
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(results)

print(f"Source entries checked: {len(results)}")
print(f"Project files scanned: {len(project_files)}")
print(f"Report saved: {OUTPUT}")
print("\nVerification summary:")

for status in sorted({row["Status"] for row in results}):
    count = sum(row["Status"] == status for row in results)
    print(f"  {status}: {count}")
