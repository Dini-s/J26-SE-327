
from pathlib import Path
import pandas as pd

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "component1" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "component1" / "processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "nfr_labeled.txt": "nfr_labeled",
    "test_labeled.txt": "test_labeled",
}


def parse_labeled_text(file_path: Path) -> pd.DataFrame:
    records = []
    skipped_lines = 0

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            if ":" not in line:
                skipped_lines += 1
                continue

            label, requirement = line.split(":", maxsplit=1)
            label = label.strip()
            requirement = requirement.strip()

            if not label or not requirement:
                skipped_lines += 1
                continue

            records.append({
                "requirement": requirement,
                "label": label,
                "source_file": file_path.name,
                "source_line": line_number,
            })

    df = pd.DataFrame(
        records,
        columns=["requirement", "label", "source_file", "source_line"],
    )

    print(f"\nFile: {file_path.name}")
    print(f"Valid records: {len(df)}")
    print(f"Skipped lines: {skipped_lines}")

    if not df.empty:
        print("\nLabel counts:")
        print(df["label"].value_counts().sort_index().to_string())

    return df


def main():
    for filename, output_name in FILES.items():
        input_path = RAW_DIR / filename

        if not input_path.exists():
            print(f"\nMissing file: {input_path}")
            continue

        df = parse_labeled_text(input_path)

        output_path = PROCESSED_DIR / f"{output_name}_parsed.csv"
        df.to_csv(output_path, index=False, encoding="utf-8-sig")

        print(f"Saved: {output_path}")

    print("\nDataset preparation completed.")


if __name__ == "__main__":
    main()
