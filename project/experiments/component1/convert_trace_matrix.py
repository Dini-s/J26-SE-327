from pathlib import Path
import csv

DATA_DIR = Path("project/data/component1/raw/nfr_fr_trace")
OUTPUT_DIR = Path("project/data/component1/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

output_file = OUTPUT_DIR / "promise_trace_relationships.csv"
total_rows = 0

with output_file.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["project", "fr_id", "nfr_id", "relationship"]
    )
    writer.writeheader()

    for path in sorted(DATA_DIR.glob("*.arff")):
        attributes = []
        records = []
        in_data = False

        with path.open(
            "r", encoding="cp1252", errors="replace"
        ) as source:
            for line in source:
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
                    raise ValueError(
                        f"Sparse ARFF row found in {path.name}; "
                        "handle it before conversion."
                    )

                records.append(
                    next(csv.reader([line], skipinitialspace=True))
                )

        project = path.stem.split("_")[0]
        nfr_ids = [
            attr.split()[1]
            for attr in attributes[1:]
        ]

        for record in records:
            if len(record) != len(attributes):
                raise ValueError(
                    f"Column mismatch in {path.name}: {record}"
                )

            fr_id = record[0].strip()

            for nfr_id, value in zip(nfr_ids, record[1:]):
                value = value.strip()

                if value not in {"0", "1"}:
                    raise ValueError(
                        f"Unexpected value {value!r} in {path.name}"
                    )

                writer.writerow({
                    "project": project,
                    "fr_id": fr_id,
                    "nfr_id": nfr_id,
                    "relationship": (
                        "trace" if value == "0" else "anti_trace"
                    )
                })
                total_rows += 1

print(f"Projects processed: {len(list(DATA_DIR.glob('*.arff')))}")
print(f"Relationship rows: {total_rows}")
print(f"Saved to: {output_file}")