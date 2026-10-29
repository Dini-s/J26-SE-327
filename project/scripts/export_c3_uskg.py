from agents.quality_agent import (
    config,
)

from agents.quality_agent.integration.uskg_exporter import (
    C3USKGExporter,
)


def main() -> None:
    exporter = (
        C3USKGExporter()
    )

    graph = (
        exporter.export()
    )

    print()
    print(
        "=" * 72
    )

    print(
        "ASPIRE COMPONENT 3 USKG EXPORT"
    )

    print(
        "=" * 72
    )

    print(
        "Nodes         :",
        graph[
            "summary"
        ][
            "node_count"
        ],
    )

    print(
        "Relationships :",
        graph[
            "summary"
        ][
            "relationship_count"
        ],
    )

    print(
        "Output        :",
        config.USKG_EXPORT_PATH,
    )

    print(
        "=" * 72
    )


if __name__ == "__main__":
    main()