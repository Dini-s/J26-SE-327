from pathlib import Path
import csv
from collections import Counter

data_dir = Path("project/data/component1/raw/nfr_fr_trace")

for path in sorted(data_dir.glob("*.arff")):
    attributes = []
    records = []
    in_data = False

    with path.open(
        "r", encoding="cp1252", errors="replace"
    ) as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("%"):
                continue

            if not in_data:
                if line.lower().startswith("@attribute"):
                    attributes.append(line)
                elif line.lower() == "@data":
                    in_data = True
                continue

            if line.startswith("{"):
                continue

            records.append(
                next(csv.reader([line], skipinitialspace=True))
            )

    trace_counts = Counter()

    for row in records:
        for value in row[1:]:
            value = value.strip()

            if value == "0":
                trace_counts["trace"] += 1
            elif value == "1":
                trace_counts["anti_trace"] += 1

    print(f"\n{path.name}")
    print(f"FR records: {len(records)}")
    print(f"Trace relationships (0): {trace_counts['trace']}")
    print(f"Anti-trace relationships (1): {trace_counts['anti_trace']}")
    print(f"Relationship cells: {sum(trace_counts.values())}")