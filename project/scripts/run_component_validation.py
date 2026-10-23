from __future__ import annotations

import subprocess
import sys


COMMANDS = [
    [
        sys.executable,
        "-m",
        "scripts.validate_requirements_dataset",
    ],
    [
        sys.executable,
        "-m",
        "scripts.build_c3_dataset",
    ],
    [
        sys.executable,
        "-m",
        "scripts.run_c3_pipeline",
    ],
    [
        sys.executable,
        "-m",
        "scripts.validate_c3_outputs",
    ],
    [
        sys.executable,
        "-m",
        "scripts.run_c3_intelligence",
    ],
    [
        sys.executable,
        "-m",
        "scripts.validate_intelligence_outputs",
    ],
    [
        sys.executable,
        "-m",
        "scripts.run_c3_revalidation",
    ],
    [
        sys.executable,
        "-m",
        "scripts.validate_revalidation_cases",
    ],
    [
        sys.executable,
        "-m",
        "pytest",
        "-c",
        "pytest-c3.ini",
        "-q",
    ],
]


def main() -> None:
    print()
    print("=" * 72)
    print(
        "ASPIRE COMPONENT 3 VALIDATION"
    )
    print("=" * 72)

    for command in COMMANDS:
        print()
        print(
            ">",
            " ".join(command),
        )

        result = subprocess.run(
            command,
            check=False,
        )

        if result.returncode != 0:
            print()
            print("=" * 72)
            print(
                "COMPONENT VALIDATION FAILED"
            )
            print("=" * 72)

            raise SystemExit(
                result.returncode
            )

    print()
    print("=" * 72)
    print(
        "COMPONENT VALIDATION PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()