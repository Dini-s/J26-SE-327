"""The numbers on the dashboard's Results tab are computed from the result files, never typed into the page."""

import json

from apps.api import evidence as ev


def test_llm_comparison_counts_a_missing_answer_as_not_linked_and_reports_it():
    raw = {"models": {"gemma2-8k:latest": [
        {"label": 1, "linked": True, "seconds": 10}, {"label": 1, "linked": None, "seconds": 30},
        {"label": 0, "linked": True, "seconds": 20}, {"label": 0, "linked": False, "seconds": 20}]}}
    (row,) = ev.llm_comparison(raw)
    assert row["model"] == "gemma2-8k" and row["noAnswer"] == 1
    assert (row["precision"], row["recall"]) == (0.5, 0.5) and row["f1"] == 0.5 and row["seconds"] == 20 and row["pairs"] == 4


def test_llm_comparison_without_data_is_none():
    assert ev.llm_comparison(None) is None and ev.llm_comparison({"models": {}}) is None


def test_codebert_before_and_after_per_project():
    b, a = "TF-IDF + MiniLM (before)", "TF-IDF + MiniLM + CodeBERT (after)"
    raw = {"projects": {"x": {"true_links": 10, "table": {b: {"recall@10": 0.5}, a: {"recall@10": 0.6}}},
                        "y": {"true_links": 5, "table": {b: {"recall@10": 0.7}, a: {"recall@10": 0.6}}}},
           "mean_over_projects": {b: {"recall@10": 0.6, "MRR": 0.7}, a: {"recall@10": 0.6, "MRR": 0.71}}}
    out = ev.codebert_real_projects(raw)
    assert out["better"] == 1 and out["worse"] == 1 and out["meanBefore"] == 0.6 and out["mrrAfter"] == 0.71
    assert ev.codebert_real_projects({"projects": {}}) is None


def test_targets_are_taken_from_the_result_files_and_judged_in_the_right_direction():
    summary = {"prf": [{"dataset": "iTrust", "method": "Full pipeline (hybrid + Llama 3.1 8B)", "precision": 0.375}],
               "stage1_recall": {"iTrust": {"10": {"hybrid": 0.416}}},
               "nfr": [{"name": "LLM verification latency", "measured": "typical 52 s, p95 80 s"}]}
    rows = {r["key"]: r for r in ev.targets(summary, {"decay_detection_accuracy": 0.957, "links_used": 11, "false_decay_rate": 0.0})}
    assert rows["precision"]["value"] == 0.375 and rows["precision"]["met"] is False
    assert rows["latency"]["value"] == 52.0 and rows["latency"]["met"] is False        # lower is better: 52 s > 5 s
    assert rows["decay"]["met"] is True and rows["recall"]["value"] == 0.416 and rows["recall"]["met"] is False
    assert ev.targets(None, None) == []


def test_build_reads_the_files_in_a_folder_and_skips_missing_ones(tmp_path):
    (tmp_path / "decay_injection_v2.json").write_text(json.dumps({"decay_detection_accuracy": 0.76, "decay_detection_ci95": [0.6, 0.86]}))
    (tmp_path / "decay_injection_v3.json").write_text(json.dumps({"decay_detection_accuracy": 0.96, "decay_detection_ci95": [0.85, 0.99], "false_decay_rate": 0.0, "links_used": 11}))
    out = ev.build(tmp_path)
    assert out["decay"]["llmOnly"] == 0.76 and out["decay"]["withCheck"] == 0.96
    assert out["llmComparison"] is None and out["codebert"] is None and out["prompt"] is None
    assert [r["key"] for r in out["targets"]] == ["decay"]


def test_the_real_result_files_produce_every_section():
    out = ev.build()
    assert {r["key"] for r in out["targets"]} == {"precision", "latency", "decay", "recall"}
    assert out["llmComparison"] and out["codebert"] and out["prompt"] and out["decay"]
    assert out["decay"]["withCheck"] > out["decay"]["llmOnly"]


def test_a_pending_note_that_has_since_been_measured_is_not_shown():
    summary = {"pending": ["Persona ablation (expert vs generic prompt)", "Decay-injection detection rate (target >= 85%)"]}
    assert ev.still_pending(summary, {"decay_detection_accuracy": 0.95}) == ["Persona ablation (expert vs generic prompt)"]
    assert len(ev.still_pending(summary, None)) == 2 and ev.still_pending(None, None) == []
