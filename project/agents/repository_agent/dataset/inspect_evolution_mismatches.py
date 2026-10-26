import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FEATURES = ROOT / "data/processed/hrim_package_features.csv"
EVOLUTION_DIR = ROOT / "data/evolution"
OUTPUT = ROOT / "data/processed/evolution_mismatch_audit.csv"


def read_csv(path):
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


features = read_csv(FEATURES)
audit = []

for repo in sorted({r["repository"] for r in features}):
    unmatched = [
        r
        for r in features
        if r["repository"] == repo and r["evolution_status"] != "exact_package_match"
    ]

    candidates = sorted(EVOLUTION_DIR.glob(f"{repo}_package_evolution*.csv"))

    # Use the same preferred-file order as the dataset builder.
    preferred = [
        f"{repo}_package_evolution_all_history.csv",
        f"{repo}_package_evolution_fast.csv",
        f"{repo}_package_evolution.csv",
        f"{repo}_package_evolution_v2.csv",
        f"{repo}_package_evolution_2025.csv",
    ]

    by_name = {p.name: p for p in candidates}
    selected = next(
        (by_name[name] for name in preferred if name in by_name),
        None,
    )

    evolution_names = set()
    if selected:
        evolution_names = {
            row.get("package_path", "").strip() for row in read_csv(selected)
        }

    for row in unmatched:
        package = row["package_path"]

        # Diagnostic only: suffix similarity is not a valid join.
        possible = [
            name
            for name in evolution_names
            if name and (package.endswith("." + name) or name.endswith("." + package))
        ]

        audit.append(
            {
                "repository": repo,
                "package_path": package,
                "package_origin": row["package_origin"],
                "evolution_file": selected.name if selected else "",
                "exact_match_exists": package in evolution_names,
                "suffix_candidates": "; ".join(sorted(possible)[:5]),
            }
        )

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

fields = [
    "repository",
    "package_path",
    "package_origin",
    "evolution_file",
    "exact_match_exists",
    "suffix_candidates",
]

with OUTPUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(audit)

print("Unmatched packages audited:", len(audit))
print("Audit saved to:", OUTPUT)

for row in audit:
    print(
        row["repository"],
        "|",
        row["package_path"],
        "| suffix candidates:",
        row["suffix_candidates"] or "(none)",
    )
