import pandas as pd
from pathlib import Path

source = Path(
    r"C:\Users\shero\OneDrive - Sri Lanka Institute of Information Technology"
    r"\Research Project\DataSets\ARTADataset_release1\Datasets"
)

output = Path(
    "project/data/component1/audit_reports_component1"
)
output.mkdir(parents=True, exist_ok=True)

report = []

for file in sorted(source.glob("*.xlsx")):
    df = pd.read_excel(file)
    print(f"\n{'=' * 60}\nFILE: {file.name}\nRows: {len(df)}")

    for col in df.columns:
        if col.lower() in {
            "requirement_text", "text", "requirement",
            "file", "filename", "file name", "word", "similarity"
        }:
            continue

        counts = df[col].fillna("<MISSING>").astype(str).value_counts()

        print(f"\nColumn: {col}")
        print(counts.head(10).to_string())

        for value, count in counts.items():
            report.append({
                "file": file.name,
                "column": col,
                "value": value,
                "count": count
            })

result = pd.DataFrame(report)
destination = output / "arta_label_value_audit.csv"
result.to_csv(destination, index=False, encoding="utf-8-sig")

print(f"\nReport saved: {destination}")
