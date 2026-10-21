
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "component1" / "raw"
AUDIT_DIR = PROJECT_ROOT / "data" / "component1" / "audit_reports_component1"

TARGET_FILES = [
    "FR_NFR_Dataset.xlsx",
    "PROMISE-relabeled-NICE.csv",
    "QuRE.csv",
    "software_requirements_extended.csv",
    "security_requirements.csv",
    "user_stories.csv",
    "basic.csv",
    "context.csv",
    "context_role.csv",
    "brown.csv",
    "Cornelius_2025_user_story_ambiguity_dataset.xlsx",
    "Cornelius_research_subsets.xlsx",
    "Cornelius_user_story_data_dictionary.xlsx",
]

def read_csv_safely(path):
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unable to read {path.name}")

def load_file(path):
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return read_csv_safely(path)

    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)

    raise ValueError(f"Unsupported file type: {suffix}")

def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    column_rows = []
    label_rows = []

    for filename in TARGET_FILES:
        path = RAW_DIR / filename

        if not path.exists():
            print(f"NOT FOUND: {filename}")
            continue

        print(f"\nAuditing: {filename}")

        try:
            df = load_file(path)

            normalized_columns = [
                str(col).strip().casefold()
                for col in df.columns
            ]

            summary_rows.append({
                "file": filename,
                "rows": len(df),
                "columns": len(df.columns),
                "missing_cells": int(df.isna().sum().sum()),
                "fully_duplicate_rows": int(df.duplicated().sum()),
                "duplicate_column_names": (
                    len(normalized_columns)
                    - len(set(normalized_columns))
                ),
                "memory_mb": round(
                    df.memory_usage(deep=True).sum() / (1024 ** 2), 2
                ),
            })

            for column in df.columns:
                series = df[column]

                column_rows.append({
                    "file": filename,
                    "column": str(column),
                    "dtype": str(series.dtype),
                    "missing": int(series.isna().sum()),
                    "unique_non_missing": int(series.nunique(dropna=True)),
                })

                # Save value distributions for columns with manageable
                # numbers of distinct values. These are candidates for
                # labels, not automatically confirmed label columns.
                counts = series.value_counts(dropna=False)

                if 1 < len(counts) <= 30:
                    for value, count in counts.items():
                        label_rows.append({
                            "file": filename,
                            "column": str(column),
                            "value": str(value),
                            "count": int(count),
                        })

            print(f"  Rows: {len(df)}")
            print(f"  Columns: {len(df.columns)}")
            print(f"  Missing cells: {int(df.isna().sum().sum())}")
            print(f"  Duplicate rows: {int(df.duplicated().sum())}")
            print(f"  Column names: {list(df.columns)}")

        except Exception as exc:
            print(f"  ERROR: {type(exc).__name__}: {exc}")

            summary_rows.append({
                "file": filename,
                "error": f"{type(exc).__name__}: {exc}",
            })

    outputs = [
        (
            summary_rows,
            "remaining_dataset_summary.csv",
        ),
        (
            column_rows,
            "remaining_dataset_columns.csv",
        ),
        (
            label_rows,
            "remaining_dataset_value_counts.csv",
        ),
    ]

    for rows, output_name in outputs:
        output_path = AUDIT_DIR / output_name
        pd.DataFrame(rows).to_csv(
            output_path,
            index=False,
            encoding="utf-8-sig",
        )
        print(f"\nSaved: {output_path}")

    print("\nDataset audit completed.")

if __name__ == "__main__":
    main()
