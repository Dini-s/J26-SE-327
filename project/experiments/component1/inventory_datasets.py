
from pathlib import Path
import csv
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_FILE = PROJECT_ROOT / "data" / "dataset_inventory.csv"

SUPPORTED_EXTENSIONS = {
    ".csv", ".xlsx", ".xls", ".txt",
    ".pdf", ".doc", ".docx", ".rtf",
    ".arff", ".json", ".jsonl", ".htm", ".html"
}

IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules",
    "__pycache__", "AppData"
}


def main():
    print("\nASPIRE - Dataset Inventory")
    print("--------------------------")

    folder_input = input("Dataset folder path: ").strip().strip('"')
    root = Path(folder_input).expanduser()

    if not root.is_dir():
        print("ERROR: Folder not found. Check the path.")
        return

    project = PROJECT_ROOT.resolve()
    scan_root = root.resolve()

    if (
        scan_root == project
        or project in scan_root.parents
        or scan_root in project.parents
    ):
        print("ERROR: Choose the DataSets folder, not the project folder.")
        return

    rows = []
    skipped = 0

    for path in scan_root.rglob("*"):
        if not path.is_file():
            continue

        if any(part in IGNORED_DIRS for part in path.parts):
            continue

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:
            stat = path.stat()
            rows.append({
                "file_name": path.name,
                "extension": path.suffix.lower(),
                "file_size_bytes": stat.st_size,
                "modified_time": datetime.fromtimestamp(
                    stat.st_mtime
                ).isoformat(timespec="seconds"),
                "source_path": str(path),
            })
        except OSError:
            skipped += 1

    rows.sort(key=lambda item: (
        item["extension"], item["file_name"].lower()
    ))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        fields = [
            "file_name", "extension", "file_size_bytes",
            "modified_time", "source_path"
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nFiles found: {len(rows)}")
    print(f"Files skipped: {skipped}")
    print(f"Report saved to: {OUTPUT_FILE}")

    print("\nFile type summary:")
    for extension in sorted({
        row["extension"] for row in rows
    }):
        count = sum(
            row["extension"] == extension for row in rows
        )
        print(f"{extension}: {count}")


if __name__ == "__main__":
    main()
