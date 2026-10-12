
from pathlib import Path
import json
import pandas as pd

# Project paths
PROJECT_DIR = Path(__file__).resolve().parents[1]
INVENTORY_FILE = PROJECT_DIR / "data" / "dataset_inventory.csv"
REPORT_DIR = PROJECT_DIR / "data" / "audit_reports"

LABEL_KEYWORDS = (
    "label", "class", "type", "category", "functional",
    "nfr", "fr", "ambigu", "defect", "quality",
    "smell", "security", "reliability", "performance",
    "target", "risk"
)


def main():
    if not INVENTORY_FILE.exists():
        print(f"Inventory not found: {INVENTORY_FILE}")
        print("Run inventory_datasets.py first.")
        return

    inventory = pd.read_csv(INVENTORY_FILE)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    summaries = []
    label_summaries = []

    for _, item in inventory.iterrows():
        extension = str(item["extension"]).lower()

        if extension not in {".csv", ".xlsx", ".xls"}:
            continue

        file_path = Path(item["source_path"])

        if not file_path.is_file():
            print(f"SKIP: File not found: {file_path}")
            continue

        try:
            if extension == ".csv":
                df = pd.read_csv(
                    file_path,
                    encoding="utf-8",
                    on_bad_lines="skip"
                )
            else:
                df = pd.read_excel(file_path)

            missing = df.isna().sum()
            duplicate_rows = int(df.duplicated().sum())

            summaries.append({
                "file_name": file_path.name,
                "source_path": str(file_path),
                "rows": len(df),
                "columns_count": len(df.columns),
                "column_names": json.dumps(
                    [str(col) for col in df.columns],
                    ensure_ascii=False
                ),
                "missing_cells": int(missing.sum()),
                "duplicate_rows": duplicate_rows,
                "read_status": "success"
            })

            print(f"\n{'=' * 60}")
            print(f"Dataset: {file_path.name}")
            print(f"Rows: {len(df)} | Columns: {len(df.columns)}")
            print(f"Missing cells: {int(missing.sum())}")
            print(f"Duplicate rows: {duplicate_rows}")
            print("Columns:", list(df.columns))

            for col in df.columns:
                col_name = str(col)
                normalized = col_name.lower().replace(" ", "_")

                if not any(
                    keyword in normalized
                    for keyword in LABEL_KEYWORDS
                ):
                    continue

                counts = (
                    df[col]
                    .fillna("<MISSING>")
                    .astype(str)
                    .value_counts()
                    .head(50)
                )

                for label, count in counts.items():
                    label_summaries.append({
                        "file_name": file_path.name,
                        "column": col_name,
                        "label": label,
                        "count": int(count)
                    })

                print(f"\nPossible label column: {col_name}")
                print(counts.head(15).to_string())

        except Exception as error:
            summaries.append({
                "file_name": file_path.name,
                "source_path": str(file_path),
                "rows": None,
                "columns_count": None,
                "column_names": None,
                "missing_cells": None,
                "duplicate_rows": None,
                "read_status": f"error: {error}"
            })
            print(f"\nERROR reading {file_path.name}: {error}")

    pd.DataFrame(summaries).to_csv(
        REPORT_DIR / "dataset_summary.csv",
        index=False,
        encoding="utf-8-sig"
    )

    pd.DataFrame(label_summaries).to_csv(
        REPORT_DIR / "label_summary.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print("\n" + "=" * 60)
    print("DATASET AUDIT FINISHED")
    print(f"Datasets inspected: {len(summaries)}")
    print(f"Summary: {REPORT_DIR / 'dataset_summary.csv'}")
    print(f"Labels:  {REPORT_DIR / 'label_summary.csv'}")


if __name__ == "__main__":
    main()
