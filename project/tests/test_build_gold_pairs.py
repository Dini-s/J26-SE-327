"""build_gold_pairs: the rules that decide which labelled pairs reach all_projects_clean.csv (small fixtures, no real data)."""

import csv
import json

import pytest

from scripts import build_gold_pairs as b


@pytest.fixture
def processed(tmp_path, monkeypatch):
    root = tmp_path / "processed"
    proj = root / "demo"
    proj.mkdir(parents=True)
    artifacts = [
        {"id": "R1", "type": "requirement", "text": "The system shall log in users.\n  Quickly."},
        {"id": "R2", "type": "requirement", "text": "The system shall store pets."},
        {"id": "C1", "type": "code", "text": "package a.b;\nimport x.Y;\npublic class Login { void go() {} }"},
        {"id": "C2", "type": "code", "text": "package a.b;\nimport x.Z;\n"},            # empty after boilerplate removal
        {"id": "D1", "type": "design", "text": "Design document in prose."},              # not code
        {"id": "C3", "type": "code", "text": "public class Pet { }"},
    ]
    (proj / "artifacts.json").write_text(json.dumps(artifacts))
    gold = [["R1", "C1", True], ["R1", "C2", False], ["R1", "D1", False], ["R2", "C3", True], ["R1", "C1", True], ["R2", "NOPE", False]]
    (proj / "gold.json").write_text(json.dumps(gold))
    monkeypatch.setattr(b, "PROCESSED", root)
    return root


def test_step_a_keeps_labelled_pairs_once_and_collapses_whitespace(processed, tmp_path):
    path, report = b.step_a(tmp_path / "out")
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert [(r["requirement_id"], r["code_id"], r["gold"]) for r in rows] == [("R1", "C1", "1"), ("R1", "C2", "0"), ("R1", "D1", "0"), ("R2", "C3", "1")]
    assert rows[0]["requirement_text"] == "The system shall log in users. Quickly."
    assert report["dropped"] == {"duplicate_pair": 1, "missing_artifact": 1}


def test_step_b_drops_non_code_targets_and_empty_code_and_removes_boilerplate(processed, tmp_path):
    a_path, _ = b.step_a(tmp_path / "out")
    path, report = b.step_b(a_path, tmp_path / "out")
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert [r["code_id"] for r in rows] == ["C1", "C3"]                       # C2 empty after cleaning, D1 not code
    assert "package" not in rows[0]["code_text"] and "import" not in rows[0]["code_text"]
    assert report["rows_dropped_not_code_target"] == 1 and report["rows_dropped_code_empty"] == 1 and report["rows_written"] == 2


def test_build_writes_both_files_and_the_report(processed, tmp_path):
    b.build(tmp_path / "final")
    assert (tmp_path / "final" / "all_projects.csv").exists()
    assert (tmp_path / "final" / "all_projects_clean.csv").exists()
    assert json.loads((tmp_path / "final" / "clean_code_report.json").read_text())["rows_written"] == 2
