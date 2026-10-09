import json
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "component3"
    / "raw"
    / "performance"
    / "performance_evidence.json"
)


PERFORMANCE_EVIDENCE = [
    {
        "evidence_id":
        "PERF-001",

        "title":
        "Owner search p95 response-time evidence",

        "description":
        (
            "Controlled performance fixture "
            "for owner-search response time."
        ),

        "metric":
        "response_time",

        "percentile":
        "p95",

        "measured_value":
        1850.0,

        "threshold":
        2000.0,

        "unit":
        "milliseconds",

        "load":
        100,

        "duration_seconds":
        600,

        "scope":
        "Owner Search",

        "execution_status":
        "PASS",

        "configuration": {
            "users": 100,
            "duration_seconds": 600,
            "target": "Owner Search"
        }
    },

    {
        "evidence_id":
        "PERF-002",

        "title":
        "Owner search failed-request-rate evidence",

        "description":
        (
            "Controlled performance fixture "
            "for owner-search failed-request rate."
        ),

        "metric":
        "error_rate",

        "percentile":
        None,

        "measured_value":
        0.6,

        "threshold":
        1.0,

        "unit":
        "percent",

        "load":
        100,

        "duration_seconds":
        600,

        "scope":
        "Owner Search",

        "execution_status":
        "PASS",

        "configuration": {
            "users": 100,
            "duration_seconds": 600,
            "target": "Owner Search"
        }
    },

    {
        "evidence_id":
        "PERF-003",

        "title":
        "Veterinarian listing p95 response-time evidence",

        "description":
        (
            "Controlled fixture intentionally "
            "exceeding the required "
            "response-time threshold."
        ),

        "metric":
        "response_time",

        "percentile":
        "p95",

        "measured_value":
        1650.0,

        "threshold":
        1500.0,

        "unit":
        "milliseconds",

        "load":
        100,

        "duration_seconds":
        600,

        "scope":
        "Veterinarian Listing",

        "execution_status":
        "FAIL",

        "configuration": {
            "users": 100,
            "duration_seconds": 600,
            "target": "Veterinarian Listing"
        }
    },

    {
        "evidence_id":
        "PERF-004",

        "title":
        "Veterinarian listing failed-request-rate evidence",

        "description":
        (
            "Controlled veterinarian-listing "
            "error-rate fixture."
        ),

        "metric":
        "error_rate",

        "percentile":
        None,

        "measured_value":
        0.4,

        "threshold":
        1.0,

        "unit":
        "percent",

        "load":
        100,

        "duration_seconds":
        600,

        "scope":
        "Veterinarian Listing",

        "execution_status":
        "PASS",

        "configuration": {
            "users": 100,
            "duration_seconds": 600,
            "target": "Veterinarian Listing"
        }
    },

    {
        "evidence_id":
        "PERF-005",

        "title":
        "Visit registration p95 response-time evidence",

        "description":
        (
            "Controlled performance fixture "
            "for visit registration."
        ),

        "metric":
        "response_time",

        "percentile":
        "p95",

        "measured_value":
        1925.0,

        "threshold":
        2000.0,

        "unit":
        "milliseconds",

        "load":
        50,

        "duration_seconds":
        600,

        "scope":
        "Visit Registration",

        "execution_status":
        "PASS",

        "configuration": {
            "users": 50,
            "duration_seconds": 600,
            "target": "Visit Registration"
        }
    },

    {
        "evidence_id":
        "PERF-006",

        "title":
        "Visit registration failed-request-rate evidence",

        "description":
        (
            "Controlled failed-request-rate "
            "fixture for visit registration."
        ),

        "metric":
        "error_rate",

        "percentile":
        None,

        "measured_value":
        0.8,

        "threshold":
        1.0,

        "unit":
        "percent",

        "load":
        50,

        "duration_seconds":
        600,

        "scope":
        "Visit Registration",

        "execution_status":
        "PASS",

        "configuration": {
            "users": 50,
            "duration_seconds": 600,
            "target": "Visit Registration"
        }
    },
]


def main() -> None:
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    records = [
        {
            **item,

            "source_tool":
            (
                "C3_CONTROLLED_"
                "PERFORMANCE_FIXTURE"
            ),

            "source_version":
            "1.0",

            "synthetic":
            True,
        }

        for item
        in PERFORMANCE_EVIDENCE
    ]

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            records,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(
        "ASPIRE C3 Performance Evidence"
    )
    print("=" * 50)

    print(
        f"Evidence records: "
        f"{len(records)}"
    )

    print(
        f"Output: {OUTPUT_PATH}"
    )

    print(
        "Source type: "
        "CONTROLLED RESEARCH FIXTURE"
    )

    print("=" * 50)


if __name__ == "__main__":
    main()