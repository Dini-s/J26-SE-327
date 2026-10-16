"""Hand-labelling: stable sample, saved labels, precision and interval."""

import pytest

from apps.api import labeling


def link(i, conf=0.9, status="verified"):
    return {"requirement": f"R{i}", "code": f"C{i}", "confidence": conf, "status": status}


def test_sample_is_stable_and_skips_decayed():
    links = [link(i) for i in range(30)] + [link(99, status="decayed")]
    a, b = labeling.sample_links(links, 10), labeling.sample_links(list(reversed(links)), 10)
    assert a == b and len(a) == 10 and all(l["requirement"] != "R99" for l in a)


def test_labels_are_saved_and_cleared(tmp_path):
    labeling.set_label("p", "R1", "C1", "correct", tmp_path)
    assert labeling.load_labels("p", tmp_path)["R1||C1"]["label"] == "correct"
    labeling.set_label("p", "R1", "C1", None, tmp_path)
    assert labeling.load_labels("p", tmp_path) == {}
    with pytest.raises(ValueError):
        labeling.set_label("p", "R1", "C1", "maybe", tmp_path)


def test_precision_ignores_unsure_and_buckets_by_confidence():
    sample = [link(1, 0.9), link(2, 0.9), link(3, 0.6), link(4, 0.8), link(5, 0.9)]
    labels = {"R1||C1": {"label": "correct"}, "R2||C2": {"label": "wrong"}, "R3||C3": {"label": "wrong"}, "R4||C4": {"label": "unsure"}}
    s = labeling.stats(sample, labels)
    assert (s["correct"], s["wrong"], s["unsure"], s["labelled"]) == (1, 2, 1, 4)
    assert s["precision"] == round(1 / 3, 3)
    assert {b["label"]: b["precision"] for b in s["byConfidence"]} == {"< 0.7": 0.0, "0.7 - 0.85": None, ">= 0.85": 0.5}


def test_wilson_interval_is_wide_for_small_samples_and_empty_safe():
    lo, hi = labeling.wilson(3, 4)
    assert lo < 0.75 < hi and hi - lo > 0.4
    assert labeling.wilson(0, 0) == (0.0, 0.0)
    assert labeling.stats([], {})["precision"] is None


def test_license_header_is_stripped_from_code_text():
    from apps.api.sources import strip_license

    code = "/*\n * Copyright 2012 X\n * Licensed under Apache\n */\npackage a;\nclass A {}"
    assert strip_license(code) == "package a;\nclass A {}"
    plain = "/* helper */\nclass B {}"
    assert strip_license(plain) == plain


def test_ab_summary_counts_kept_and_rejected_links():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("ab", Path(__file__).resolve().parents[1] / "scripts" / "ab_evidence_mode.py")
    ab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab)
    rows = [
        {"label": "correct", "ev_linked": True}, {"label": "correct", "ev_linked": False},
        {"label": "wrong", "ev_linked": False}, {"label": "wrong", "ev_linked": True},
        {"label": "unsure", "ev_linked": True}, {"label": "correct", "ev_linked": None},
    ]
    s = ab.summarise(rows)
    assert s["links_judged"] == 4 and s["standard_precision"] == 0.5
    assert s["evidence_kept"] == 2 and s["evidence_precision"] == 0.5
    assert s["correct_links_kept"] == "1/2" and s["wrong_links_rejected"] == "1/2"
