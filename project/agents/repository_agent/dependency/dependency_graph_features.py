import argparse
from pathlib import Path

import networkx as nx
import pandas as pd


def calculate_graph_features(edge_path: Path, repository: str) -> pd.DataFrame:
    """Calculate package-level graph features from a directed edge CSV."""
    edges = pd.read_csv(edge_path)

    required = {"source_package", "target_package"}
    missing = required - set(edges.columns)
    if missing:
        raise ValueError(f"{edge_path}: missing columns {sorted(missing)}")

    edges = edges[["source_package", "target_package"]].copy()
    edges["source_package"] = edges["source_package"].astype("string").str.strip()
    edges["target_package"] = edges["target_package"].astype("string").str.strip()

    # Invalid edges are reported rather than silently included.
    invalid = (
        edges["source_package"].isna()
        | edges["target_package"].isna()
        | edges["source_package"].eq("")
        | edges["target_package"].eq("")
    )
    if invalid.any():
        raise ValueError(f"{edge_path}: {int(invalid.sum())} invalid edge rows")

    duplicate_count = int(edges.duplicated().sum())
    edges = edges.drop_duplicates()

    graph = nx.DiGraph()
    graph.add_edges_from(edges.itertuples(index=False, name=None))

    if graph.number_of_nodes() == 0:
        return pd.DataFrame()

    in_degree = dict(graph.in_degree())
    out_degree = dict(graph.out_degree())
    pagerank = nx.pagerank(graph)
    betweenness = nx.betweenness_centrality(graph, normalized=True)
    component_ids = {}

    components = sorted(
        nx.weakly_connected_components(graph),
        key=lambda component: min(component),
    )
    for component_id, component in enumerate(components):
        for package in component:
            component_ids[package] = component_id

    result = pd.DataFrame(
        {
            "repository": repository,
            "package_path": list(graph.nodes()),
        }
    )

    result["graph_in_degree"] = result["package_path"].map(in_degree)
    result["graph_out_degree"] = result["package_path"].map(out_degree)
    result["graph_total_degree"] = (
        result["graph_in_degree"] + result["graph_out_degree"]
    )
    result["graph_pagerank"] = result["package_path"].map(pagerank)
    result["graph_betweenness"] = result["package_path"].map(betweenness)
    result["graph_component_id"] = result["package_path"].map(component_ids)

    print(
        f"{repository}: nodes={graph.number_of_nodes()}, "
        f"edges={graph.number_of_edges()}, "
        f"duplicate_edges_removed={duplicate_count}, "
        f"components={len(components)}"
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dependencies-dir", default="data/dependencies")
    parser.add_argument(
        "--output", default="data/processed/dependency_graph_features.csv"
    )
    args = parser.parse_args()

    dependencies_dir = Path(args.dependencies_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(dependencies_dir.glob("*_dependencies.csv"))
    if not files:
        raise SystemExit(f"No dependency CSVs found in {dependencies_dir}")

    frames = []
    for path in files:
        repository = path.name.removesuffix("_dependencies.csv")
        features = calculate_graph_features(path, repository)
        if not features.empty:
            frames.append(features)

    if not frames:
        raise SystemExit("No graph features were generated.")

    result = pd.concat(frames, ignore_index=True)

    if result.duplicated(["repository", "package_path"]).any():
        raise ValueError("Duplicate repository/package keys in graph features.")

    result.to_csv(output_path, index=False)
    print(f"\nTotal package nodes: {len(result)}")
    print(f"Saved features: {output_path}")


if __name__ == "__main__":
    main()
