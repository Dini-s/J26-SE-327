from pathlib import Path
from collections import Counter
import csv

data_dir = Path("project/data/component1/raw/nfr_fr_trace")
output_dir = Path("project/data/component1/audit_reports_component1")
output_dir.mkdir(parents=True, exist_ok=True)

summary = []

for path in sorted(data_dir.glob("*.arff")):
    attributes = []
    rows = []
    in_data = False

    with path.open("r", encoding="cp1252", errors="replace") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("%"):
                continue

            if not in_data:
                if line.lower().startswith("@attribute"):
                    attributes.append(line)
                elif line.lower() == "@data":
                    in_data = True
                continue

            try:
                row = next(csv.reader([line], skipinitialspace=True))
                rows.append(row)
            except csv.Error:
                continue

    last_column_counts = Counter(
        row[-1].strip() for row in rows if row
    )

    summary.append({
        "file": path.name,
        "records": len(rows),
        "attribute_count": len(attributes),
        "attributes": " | ".join(attributes),
        "last_column_values": str(dict(last_column_counts)),
        "invalid_column_rows": sum(
            1 for row in rows if len(row) != len(attributes)
        )
    })

    print(f"\n{'=' * 55}")
    print(f"File: {path.name}")
    print(f"Records: {len(rows)}")
    print(f"Attributes: {len(attributes)}")
    print(f"Last-column values: {dict(last_column_counts)}")
    print(f"Invalid column-count rows: {summary[-1]['invalid_column_rows']}")

if not summary:
    print(f"No ARFF files found in: {data_dir.resolve()}")
else:
    report = output_dir / "nfr_fr_trace_summary.csv"

    with report.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)

    print(f"\nAudit completed. Files checked: {len(summary)}")
    print(f"Report saved to: {report}")
