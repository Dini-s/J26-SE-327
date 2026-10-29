from agents.quality_agent.agent import (
    QualityAgent,
)


def main() -> None:
    result = (
        QualityAgent()
        .analyze_quality()
    )

    print()
    print("=" * 72)
    print(
        "ASPIRE C3 QUALITY INTELLIGENCE"
    )
    print("=" * 72)

    for key, value in result.items():
        print(
            f"{key:<24}: {value}"
        )

    print("=" * 72)


if __name__ == "__main__":
    main()