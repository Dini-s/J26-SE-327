from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]

HRIM_PATH = ROOT / "data" / "processed" / "hrim_package_features.csv"
GRAPH_PATH = ROOT / "data" / "processed" / "dependency_graph_features.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "hrim_fused_features.csv"


def main():
    hrim = pd.read_csv(HRIM_PATH)
    graph = pd.read_csv(GRAPH_PATH)

    keys = ["repository", "package_path"]

    # Normalize join keys without modifying feature values.
    for df in (hrim, graph):
        for column in keys:
            df[column] = df[column].astype("string").str.strip()

    # Verify that each dataset has unique package keys.
    if hrim.duplicated(keys).any():
        raise ValueError("Duplicate repository/package keys in HRIM dataset.")

    if graph.duplicated(keys).any():
        raise ValueError("Duplicate repository/package keys in graph dataset.")

    graph["graph_features_available"] = 1

    # Preserve every HRIM row; do not discard unmatched packages.
    fused = hrim.merge(
        graph,
        on=keys,
        how="left",
        validate="one_to_one",
        indicator=True,
        suffixes=("", "_graph"),
    )

    fused["graph_features_available"] = (fused["_merge"] == "both").astype("int8")

    fused = fused.drop(columns=["_merge"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fused.to_csv(OUTPUT_PATH, index=False)

    print("HRIM rows:", len(hrim))
    print("Graph feature rows:", len(graph))
    print("Fused rows:", len(fused))
    print(
        "Packages with graph features:",
        int(fused["graph_features_available"].sum()),
    )
    print(
        "Packages without graph features:",
        int((fused["graph_features_available"] == 0).sum()),
    )
    print("Saved:", OUTPUT_PATH)

    print("\nMissing graph features by repository:")
    print(
        fused.loc[fused["graph_features_available"] == 0]
        .groupby("repository")
        .size()
        .to_string()
    )


if __name__ == "__main__":
    main()
