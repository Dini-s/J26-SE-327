import pandas as pd
from pathlib import Path

base = Path("data/evolution")

targets = {
    "R03_jabref": ["(default package)"],
    "R05_lucene": [
        "(default package)",
        "org.apache.lucene.gradle.plugins.java",
    ],
    "R06_hadoop": [
        "(default package)",
        "org.apache.hadoop.ipc.protobuf",
    ],
    "R07_junit": ["(default package)"],
    "R08_apache_maven": ["(default package)"],
    "R09_kafca": [
        "(default package)",
        "org.apache.kafka.jmh.core",
    ],
    "R11_key_cloak": ["(default package)"],
}

for repo, packages in targets.items():
    print(f"\n--- {repo} ---")
    files = sorted(base.glob(f"{repo}_package_evolution*.csv"))

    for file in files:
        try:
            df = pd.read_csv(file)

            if "package_path" not in df.columns:
                continue

            matches = df[df["package_path"].isin(packages)]

            if not matches.empty:
                print(f"\nFile: {file.name}")
                print(matches["package_path"].to_list())

        except Exception as exc:
            print(f"Error reading {file.name}: {exc}")
