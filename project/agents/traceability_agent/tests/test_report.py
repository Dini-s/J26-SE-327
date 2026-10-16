"""Matrix / link-list / report exports."""

import csv
import io

from agents.traceability_agent.report import links_csv, matrix_csv, report
from shared.schemas.traceability import Artifact, TraceabilityLink


def req(i: str) -> Artifact:
    return Artifact(id=i, type="requirement", text=f"text {i}")


def link(r: str, c: str, conf: float, status: str = "verified") -> TraceabilityLink:
    return TraceabilityLink(source_id=r, target_id=c, link_type="requirement_to_code", confidence=conf, status=status, justification="why")


REQS = [req("R1"), req("R2"), req("R3"), req("R4")]
TRACES = [link("R1", "A.java", 0.9), link("R2", "B.java", 0.5), link("R3", "A.java", 0.3, "decayed")]


def test_matrix_marks_verified_decayed_and_empty_cells():
    rows = list(csv.reader(io.StringIO(matrix_csv(REQS, TRACES))))
    assert rows[0] == ["requirement", "A.java", "B.java"]
    assert rows[1] == ["R1", "0.90", ""]
    assert rows[2] == ["R2", "", "0.50"]
    assert rows[3] == ["R3", "x0.30", ""]
    assert rows[4] == ["R4", "", ""]


def test_links_csv_has_one_row_per_link():
    rows = list(csv.reader(io.StringIO(links_csv(REQS, TRACES))))
    assert len(rows) == 4 and rows[1][0] == "R1" and rows[3][4] == "decayed"


def test_report_separates_orphan_broken_and_weak():
    rep = report(REQS, TRACES)
    assert [r["requirement"] for r in rep["orphans"]] == ["R4"]
    assert [r["requirement"] for r in rep["broken"]] == ["R3"]
    assert [r["requirement"] for r in rep["weak"]] == ["R2"]
    assert len(rep["decayed_links"]) == 1
