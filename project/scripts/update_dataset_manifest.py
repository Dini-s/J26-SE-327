import json
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

DATA_ROOT = (
    PROJECT_ROOT
    / "data"
    / "component3"
)

MANIFEST_PATH = (
    DATA_ROOT
    / "manifests"
    / "dataset_manifest.json"
)


def load_json(
    path: Path,
    default,
):
    if not path.exists():
        return default

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(
            file
        )


def count_surefire_testcases(
    root: Path,
) -> int:

    total = 0

    for path in root.glob(
        "TEST-*.xml"
    ):
        try:
            total += sum(
                1
                for _
                in (
                    ET.parse(path)
                    .getroot()
                    .iter("testcase")
                )
            )

        except ET.ParseError:
            pass

    return total


def main() -> None:
    manifest = load_json(
        MANIFEST_PATH,
        {},
    )

    requirements = load_json(
        (
            DATA_ROOT
            / "raw"
            / "requirements"
            / "requirements.json"
        ),
        [],
    )

    manual = load_json(
        (
            DATA_ROOT
            / "raw"
            / "manual_tests"
            / "manual_tests.json"
        ),
        [],
    )

    performance = load_json(
        (
            DATA_ROOT
            / "raw"
            / "performance"
            / "performance_evidence.json"
        ),
        [],
    )

    junit_root = (
        DATA_ROOT
        / "raw"
        / "junit"
        / "petclinic"
    )

    surefire_root = (
        DATA_ROOT
        / "raw"
        / "surefire"
        / "petclinic"
    )

    manifest[
        "dataset_name"
    ] = (
        "ASPIRE C3 Standalone "
        "Development Corpus"
    )

    manifest[
        "dataset_version"
    ] = (
        manifest.get(
            "dataset_version",
            "0.1.0",
        )
    )

    manifest[
        "dataset_stage"
    ] = "development"

    manifest[
        "primary_system"
    ] = "Spring PetClinic"

    manifest[
        "corpus_statistics"
    ] = {
        "requirements":
        len(requirements),

        "functional_requirements":
        sum(
            1
            for item in requirements
            if (
                item.get("type")
                == "FUNCTIONAL"
            )
        ),

        "non_functional_requirements":
        sum(
            1
            for item in requirements
            if (
                item.get("type")
                == "NON_FUNCTIONAL"
            )
        ),

        "acceptance_criteria":
        sum(
            len(
                item.get(
                    "acceptance_criteria",
                    [],
                )
            )
            for item
            in requirements
        ),

        "junit_source_files":
        len(
            list(
                junit_root.rglob(
                    "*.java"
                )
            )
        )
        if junit_root.exists()
        else 0,

        "surefire_report_files":
        len(
            list(
                surefire_root.glob(
                    "TEST-*.xml"
                )
            )
        )
        if surefire_root.exists()
        else 0,

        "surefire_testcases":
        count_surefire_testcases(
            surefire_root
        ),

        "manual_evidence_records":
        len(manual),

        "performance_evidence_records":
        len(performance),
    }

    manifest[
        "provenance_policy"
    ] = {
        "petclinic_requirements":
        "PETCLINIC_CURATED",

        "controlled_requirements":
        "C3_CONTROLLED_FIXTURE",

        "manual_execution_results_fabricated":
        False,

        "controlled_performance_fixtures_explicitly_labelled":
        True,
    }

    manifest[
        "final_gold_standard"
    ] = False

    MANIFEST_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with MANIFEST_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            manifest,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        "Dataset manifest updated:"
    )

    print(
        json.dumps(
            manifest[
                "corpus_statistics"
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()