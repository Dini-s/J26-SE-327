
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "component1" / "raw" / "arta_evaluation"

for file_path in sorted(DATA_DIR.glob("*.xlsx")):
    print(f"\n{'=' * 80}")
    print(f"FILE: {file_path.name}")

    try:
        workbook = pd.ExcelFile(file_path)
        print("Sheets:", workbook.sheet_names)

        for sheet in workbook.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet)

            print(f"\n  Sheet: {sheet}")
            print(f"  Rows: {len(df)}")
            print(f"  Columns ({len(df.columns)}): {list(df.columns)}")
            print(f"  Missing cells: {int(df.isna().sum().sum())}")
            print(f"  Duplicate rows: {int(df.duplicated().sum())}")

    except Exception as exc:
        print(f"Could not audit this workbook: {exc}")
