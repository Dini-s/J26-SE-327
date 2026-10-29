from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import hashlib

from importlib.metadata import (
    PackageNotFoundError,
    version,
)

import json
import os
import platform
import subprocess
import sys

from pathlib import Path

from agents.quality_agent import (
    config,
)


def _sha256_file(
    path: Path,
) -> str:
    digest = (
        hashlib.sha256()
    )

    with path.open(
        "rb"
    ) as handle:
        for block in iter(
            lambda:
                handle.read(
                    1024
                    * 1024
                ),
            b"",
        ):
            digest.update(
                block
            )

    return digest.hexdigest()


def _fingerprint(
    path: Path,
):
    if not path.exists():
        return {
            "exists":
                False,
        }

    if path.is_file():
        return {
            "exists":
                True,

            "type":
                "file",

            "sha256":
                _sha256_file(
                    path
                ),

            "size_bytes":
                path.stat()
                .st_size,
        }

    files = sorted(
        item

        for item
        in path.rglob("*")

        if item.is_file()
    )

    digest = (
        hashlib.sha256()
    )

    total_size = 0

    for item in files:
        relative = (
            item
            .relative_to(
                path
            )
            .as_posix()
        )

        file_hash = (
            _sha256_file(
                item
            )
        )

        total_size += (
            item.stat()
            .st_size
        )

        digest.update(
            relative.encode(
                "utf-8"
            )
        )

        digest.update(
            file_hash.encode(
                "ascii"
            )
        )

    return {
        "exists":
            True,

        "type":
            "directory",

        "file_count":
            len(files),

        "size_bytes":
            total_size,

        "sha256":
            digest.hexdigest(),
    }


def _git(
    *args,
):
    try:
        return (
            subprocess
            .check_output(
                [
                    "git",
                    *args,
                ],
                cwd=(
                    config
                    .PROJECT_ROOT
                ),
                text=True,
                stderr=(
                    subprocess
                    .DEVNULL
                ),
            )
            .strip()
        )

    except Exception:
        return None


def _package_version(
    package: str,
):
    try:
        return version(
            package
        )

    except PackageNotFoundError:
        return None


def build_manifest():
    inputs = {
        "requirements":
            config
            .REQUIREMENTS_PATH,

        "manual_tests":
            config
            .MANUAL_TESTS_PATH,

        "manual_executions":
            config
            .MANUAL_EXECUTIONS_PATH,

        "junit":
            config.JUNIT_ROOT,

        "surefire":
            config.SUREFIRE_ROOT,

        "performance":
            config
            .PERFORMANCE_PATH,

        "revalidation":
            config
            .REVALIDATION_INPUT_PATH,

        "nfr_support":
            config
            .NFR_SUPPORT_MATRIX_PATH,
    }

    outputs = {
        "rvus":
            config.RVUS_PATH,

        "evidence_profiles":
            config
            .EVIDENCE_PROFILES_PATH,

        "normalized_evidence":
            config
            .NORMALIZED_EVIDENCE_PATH,

        "adequacy_assessments":
            config
            .ADEQUACY_ASSESSMENTS_PATH,

        "rvu_adequacy":
            config
            .RVU_ADEQUACY_PATH,

        "rvu_validation":
            config
            .RVU_VALIDATION_PATH,

        "requirement_intelligence":
            config
            .REQUIREMENT_INTELLIGENCE_PATH,

        "analytics":
            config.ANALYTICS_PATH,

        "gaps":
            config.GAPS_PATH,

        "recommendations":
            config
            .RECOMMENDATIONS_PATH,

        "revalidation_results":
            config
            .REVALIDATION_RESULTS_PATH,

        "uskg_export":
            config
            .USKG_EXPORT_PATH,

        "evaluation_results":
            config
            .EVALUATION_RESULTS_PATH,
    }

    manifest = {
        "schema_version":
            "1.0",

        "component":
            "C3",

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "repository": {
            "branch":
                _git(
                    "branch",
                    "--show-current",
                ),

            "commit":
                _git(
                    "rev-parse",
                    "HEAD",
                ),

            "dirty":
                bool(
                    _git(
                        "status",
                        "--porcelain",
                    )
                ),

            "petclinic_commit":
                config
                .PETCLINIC_COMMIT,
        },

        "runtime": {
            "python":
                sys.version,

            "platform":
                platform.platform(),
        },

        "component_configuration": {
            "embedding_model":
                config
                .EMBEDDING_MODEL,

            "top_k":
                config.TOP_K,

            "semantic_threshold":
                config
                .SEMANTIC_THRESHOLD,

            "adequacy_rule_version":
                "c3-adequacy-v1",

            "rves":
                {
                    "status":
                        "EXPERIMENTAL",

                    "weights":
                        {
                            "R_relevance":
                                0.25,

                            "A_adequacy":
                                0.25,

                            "C_completeness":
                                0.25,

                            "E_execution":
                                0.25,
                        },
                },
        },

        "packages": {
            "fastapi":
                _package_version(
                    "fastapi"
                ),

            "pydantic":
                _package_version(
                    "pydantic"
                ),

            "numpy":
                _package_version(
                    "numpy"
                ),

            "pandas":
                _package_version(
                    "pandas"
                ),

            "scikit-learn":
                _package_version(
                    "scikit-learn"
                ),

            "sentence-transformers":
                _package_version(
                    "sentence-transformers"
                ),

            "torch":
                _package_version(
                    "torch"
                ),

            "pytest":
                _package_version(
                    "pytest"
                ),
        },

        "input_fingerprints": {
            name:
                _fingerprint(
                    path
                )

            for name,
                path

            in inputs.items()
        },

        "output_fingerprints": {
            name:
                _fingerprint(
                    path
                )

            for name,
                path

            in outputs.items()
        },

        "provenance_policy": {
            "controlled_fixtures_are_labelled":
                True,

            "synthetic_manual_execution_is_not_observed_validation":
                True,

            "unresolved_execution_is_not_fabricated":
                True,

            "relevance_adequacy_execution_are_separate":
                True,
        },
    }

    config.ensure_directories()

    with (
        config
        .REPRODUCIBILITY_MANIFEST_PATH
        .open(
            "w",
            encoding="utf-8",
        )
    ) as handle:
        json.dump(
            manifest,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    return manifest


def main() -> None:
    manifest = build_manifest()

    print()
    print(
        "=" * 72
    )

    print(
        "C3 REPRODUCIBILITY MANIFEST"
    )

    print(
        "=" * 72
    )

    print(
        "Git commit       :",
        manifest[
            "repository"
        ][
            "commit"
        ],
    )

    print(
        "PetClinic commit :",
        manifest[
            "repository"
        ][
            "petclinic_commit"
        ],
    )

    print(
        "Embedding model  :",
        manifest[
            "component_configuration"
        ][
            "embedding_model"
        ],
    )

    print(
        "Output           :",
        config
        .REPRODUCIBILITY_MANIFEST_PATH,
    )

    print(
        "=" * 72
    )


if __name__ == "__main__":
    main()