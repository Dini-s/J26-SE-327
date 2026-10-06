"""Code cleaning for retrieval and LLM prompts."""

from agents.traceability_agent.preprocess import (
    llm_text,
    retrieval_text,
    split_identifiers,
    strip_boilerplate,
)
from shared.schemas.traceability import Artifact

JAVA = """/* Copyright (c) 2005 Some University. All rights reserved. */
package edu.ncsu.csc.itrust.action;

import java.sql.Connection;
import edu.ncsu.csc.itrust.beans.PatientBean;

/**
 * Lets a health care professional add a new patient.
 */
public class AddPatientAction {
    public long addPatient(PatientBean bean) { return 1; }
}
"""


def code(text: str, **meta) -> Artifact:
    return Artifact(id="C", type="code", text=text, metadata=meta)


def test_split_identifiers_handles_camel_snake_and_acronyms():
    assert split_identifiers("addPatientRecord") == "add patient record"
    assert split_identifiers("MAX_RETRY_COUNT") == "max retry count"
    assert split_identifiers("parseHTTPResponse") == "parse http response"


def test_split_identifiers_drops_keywords_digits_and_single_letters():
    assert split_identifiers("public static int x1 = 42;") == ""
    assert split_identifiers("return userName;") == "user name"


def test_strip_boilerplate_removes_imports_package_and_legal_header_keeps_javadoc():
    out = strip_boilerplate(code(JAVA))
    assert "import " not in out and "package " not in out and "Copyright" not in out
    assert "Lets a health care professional add a new patient" in out
    assert "addPatient" in out


def test_retrieval_text_surfaces_meaningful_words_first():
    words = retrieval_text(code(JAVA)).split()
    assert words[:3] == ["lets", "health", "care"]
    assert "patient" in words and "package" not in words


def test_jsp_directives_and_tags_are_stripped_but_scriptlet_code_kept():
    jsp = '<%@ page import="java.util.*" %>\n<html><body><h1>Edit Patient</h1>\n<% patient.updateRecord(); %></body></html>'
    out = strip_boilerplate(code(jsp, language="jsp"))
    assert "<html>" not in out and "page import" not in out
    assert "Edit Patient" in out and "patient.updateRecord()" in out


def test_non_code_artifacts_are_untouched():
    req = Artifact(id="R", type="requirement", text="The HCP shall add a patient (UC1).")
    assert retrieval_text(req) == req.text and llm_text(req) == req.text
