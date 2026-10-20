from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "historical" / "R01_spring_petclinic"
OUTPUT = ROOT / "data" / "processed" / "R01_petclinic_package_changes.csv"

METRICS = [
    "java_files",
    "nonempty_lines",
    "fan_in",
    "fan_out",
    "total_coupling",
    "instability",
]


def main():
    files = sorted(f for f in DATA.glob("*_architecture.csv") if f.name != "all_snapshots_architecture.csv")
    if len(files) < 2:
        raise ValueError("At least two architecture snapshots are required.")

    snapshots = []
    for file in files:
        df = pd.read_csv(file)
        required = {"snapshot_date", "package_path", *METRICS}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"{file.name} is missing columns: {sorted(missing)}")

        df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
        df = df.set_index("package_path")
        snapshots.append((df["snapshot_date"].iloc[0].strftime("%Y-%m-%d"), df))

    rows = []

    for (previous_date, previous), (current_date, current) in zip(
        snapshots, snapshots[1:]
    ):
        previous_packages = set(previous.index)
        current_packages = set(current.index)

        for package in sorted(previous_packages | current_packages):
            existed_before = package in previous_packages
            exists_now = package in current_packages

            row = {
                "repository": "R01_spring_petclinic",
                "previous_snapshot": previous_date,
                "current_snapshot": current_date,
                "package_path": package,
                "change_status": (
                    "added" if not existed_before
                    else "removed" if not exists_now
                    else "retained"
                ),
            }

            for metric in METRICS:
                old_value = previous.loc[package, metric] if existed_before else None
                new_value = current.loc[package, metric] if exists_now else None

                row[f"previous_{metric}"] = old_value
                row[f"current_{metric}"] = new_value

                if existed_before and exists_now:
                    row[f"{metric}_delta"] = float(new_value - old_value)
                else:
                    row[f"{metric}_delta"] = None

            rows.append(row)

    result = pd.DataFrame(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT, index=False)

    print("Package-transition rows:", len(result))
    print("\nChange status:")
    print(result["change_status"].value_counts().to_string())
    print(f"\nSaved: {OUTPUT}")
    print("These are observed metric changes, not verified drift labels.")


if __name__ == "__main__":
    main()

