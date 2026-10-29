import json
from pathlib import Path
from typing import TypeVar

from pydantic import TypeAdapter

from agents.quality_agent.schemas import (
    RequirementRecord,
)


T = TypeVar("T")


class DatasetService:
    @staticmethod
    def load_json(path: Path):
        if not path.exists():
            raise FileNotFoundError(
                f"Required dataset file not found: {path}"
            )

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    @staticmethod
    def save_json(
        path: Path,
        data,
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

    @staticmethod
    def load_requirements(
        path: Path,
    ) -> list[RequirementRecord]:
        raw = DatasetService.load_json(path)

        adapter = TypeAdapter(
            list[RequirementRecord]
        )

        return adapter.validate_python(raw)