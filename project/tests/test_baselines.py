"""Tests for the Component 1 baselines: no test-set leakage, metrics on toy examples, reproducibility.

Run from the project directory:  pytest tests/test_baselines.py -q
"""
import ast
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from agents.requirement_agent import ambiguity as amb
from agents.requirement_agent import classifier as clf
from evaluation import data_access as da
from evaluation import metrics as M
from evaluation import run_baselines as rb

ROOT = Path(__file__).resolve().parents[1]
TASK_NAMES = ["classification_fr_nfr", "classification_nfr_subtype", "ambiguity"]


# --------------------------------------------------------------------------------------------------------------------------
# no test-set leakage
# --------------------------------------------------------------------------------------------------------------------------
class TestNoTestLeakage:
    def test_load_task_refuses_test_split(self):
        for splits in (("test",), ("train", "test"), ("val", "test"), ("train", "val", "test")):
            with pytest.raises(da.FrozenTestError):
                da.load_task("ambiguity", splits)

    def test_training_loader_never_returns_frozen_ids(self):
        frozen = pd.read_csv(da.TASKS / "frozen_test_ids.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
        for name in TASK_NAMES:
            ids = set(frozen[frozen.task == name].record_id)
            assert ids, name
            got = da.load_task(name)
            assert set(got.split) <= {"train", "val"}
            assert not (set(got.record_id) & ids), f"{name}: frozen test ids reachable from load_task"

    def test_training_modules_do_not_know_the_test_loader(self):
        for rel in ("agents/requirement_agent/features.py", "agents/requirement_agent/classifier.py",
                    "agents/requirement_agent/ambiguity.py", "evaluation/metrics.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            for banned in ("load_test_for_final_evaluation", "data_access", "frozen_test_ids", "read_csv"):
                assert banned not in src, f"{rel} mentions {banned}"

    def test_test_loader_only_called_from_final_functions(self):
        tree = ast.parse((ROOT / "evaluation/run_baselines.py").read_text(encoding="utf-8"))
        allowed = {"final_fr_nfr", "final_ambiguity", "main"}
        callers = set()
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "load_test_for_final_evaluation":
                    callers.add(fn.name)
        assert callers and callers <= allowed, callers
        # develop-phase code must not reference the loader at all
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith(("run_", "develop", "cross_validate"))]:
            assert "load_test_for_final_evaluation" not in ast.unparse(fn), fn.name

    def test_only_one_split_name_loads_in_development(self, monkeypatch):
        """Run the development phase on a tiny fixture with a booby-trapped test loader."""
        def boom(*a, **k):
            raise AssertionError("test split touched during development")
        monkeypatch.setattr(da, "load_test_for_final_evaluation", boom)
        train, val = _fixture_frames()
        res = rb.Results("fr_nfr")
        exp = rb.SingleLabel(res, "fr_nfr", ["FR", "NFR"], ["majority", "rules", "tfidf_lr"], lambda d: d.requirement_type.isin(["FR", "NFR"]),
                             lambda d: d.requirement_type.values, "fr_nfr", lambda d: {"pooled": np.ones(len(d), bool)})
        exp.develop(train, val, n_boot=20)
        exp.cross_validate(n_boot=20)
        assert len(res.metrics) > 0


class TestFrozenVerification:
    @pytest.fixture()
    def tasks_copy(self, tmp_path):
        for f in ("manifest.json", "frozen_test_ids.csv", "ambiguity.csv"):
            shutil.copy(da.TASKS / f, tmp_path / f)
        return tmp_path

    def test_real_files_verify(self):
        for name in TASK_NAMES:
            assert da.verify_frozen_test(name) > 0

    def test_tampered_frozen_ids_are_rejected(self, tasks_copy):
        p = tasks_copy / "frozen_test_ids.csv"
        p.write_bytes(p.read_bytes() + b"ambiguity,X:fake\n")
        with pytest.raises(da.FrozenTestError):
            da.load_test_for_final_evaluation("ambiguity", tasks_dir=tasks_copy)

    def test_tampered_task_file_is_rejected(self, tasks_copy):
        p = tasks_copy / "ambiguity.csv"
        df = pd.read_csv(p, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        df.loc[df.split == "test", "split"] = "train"
        df.to_csv(p, index=False, encoding="utf-8-sig", lineterminator="\n")
        with pytest.raises(da.FrozenTestError):
            da.verify_frozen_test("ambiguity", tasks_dir=tasks_copy)

    def test_clean_copy_returns_only_test_rows(self, tasks_copy):
        test = da.load_test_for_final_evaluation("ambiguity", tasks_dir=tasks_copy)
        assert set(test.split) == {"test"} and len(test) > 0


# --------------------------------------------------------------------------------------------------------------------------
# metrics on toy examples
# --------------------------------------------------------------------------------------------------------------------------
class TestMetrics:
    y_true = ["FR", "FR", "FR", "NFR", "NFR", "NFR", "NFR", "NFR"]
    y_pred = ["FR", "FR", "NFR", "NFR", "NFR", "NFR", "FR", "FR"]

    def test_confusion_matrix(self):
        cm = M.confusion_matrix(self.y_true, self.y_pred, ["FR", "NFR"])
        assert cm.tolist() == [[2, 1], [2, 3]]

    def test_precision_recall_f1(self):
        m = M.classification_metrics(self.y_true, self.y_pred, ["FR", "NFR"])
        assert m["precision[FR]"] == pytest.approx(2 / 4)
        assert m["recall[FR]"] == pytest.approx(2 / 3)
        assert m["f1[FR]"] == pytest.approx(2 * 0.5 * (2 / 3) / (0.5 + 2 / 3))
        assert m["precision[NFR]"] == pytest.approx(3 / 4)
        assert m["recall[NFR]"] == pytest.approx(3 / 5)
        assert m["macro_f1"] == pytest.approx((m["f1[FR]"] + m["f1[NFR]"]) / 2)
        assert m["accuracy"] == pytest.approx(5 / 8)
        assert m["support[FR]"] == 3 and m["support[NFR]"] == 5

    def test_matches_sklearn(self):
        from sklearn.metrics import f1_score, precision_score, recall_score
        m = M.classification_metrics(self.y_true, self.y_pred, ["FR", "NFR"])
        assert m["macro_f1"] == pytest.approx(f1_score(self.y_true, self.y_pred, average="macro"))
        assert m["macro_precision"] == pytest.approx(precision_score(self.y_true, self.y_pred, average="macro"))
        assert m["macro_recall"] == pytest.approx(recall_score(self.y_true, self.y_pred, average="macro"))

    def test_absent_class_does_not_inflate_macro(self):
        m = M.classification_metrics(["a", "a", "b"], ["a", "a", "b"], ["a", "b", "c"])
        assert m["macro_f1"] == pytest.approx(1.0)  # class c never occurs in y_true

    def test_bootstrap_ci_brackets_point_estimate_and_is_seeded(self):
        yt, yp = self.y_true * 20, self.y_pred * 20
        a = M.bootstrap_ci(yt, yp, ["FR", "NFR"], n_boot=200, seed=1)
        b = M.bootstrap_ci(yt, yp, ["FR", "NFR"], n_boot=200, seed=1)
        assert a == b
        point = M.classification_metrics(yt, yp, ["FR", "NFR"])["macro_f1"]
        lo, hi = a["macro_f1"]
        assert lo <= point <= hi and hi - lo > 0

    def test_perfect_prediction_has_degenerate_ci(self):
        ci = M.bootstrap_ci(["a", "b"] * 10, ["a", "b"] * 10, ["a", "b"], n_boot=50)
        assert ci["macro_f1"] == (1.0, 1.0)

    def test_multilabel_toy(self):
        Yt = np.array([[1, 0], [1, 1], [0, 1], [0, 0]])
        Yp = np.array([[1, 0], [0, 1], [0, 1], [1, 0]])
        m = M.multilabel_metrics(Yt, Yp, ["x", "y"])
        assert m["precision[x]"] == pytest.approx(1 / 2) and m["recall[x]"] == pytest.approx(1 / 2)
        assert m["precision[y]"] == pytest.approx(1.0) and m["recall[y]"] == pytest.approx(1.0)  # y: tp=2, fn=0
        assert m["micro_precision"] == pytest.approx(3 / 4) and m["micro_recall"] == pytest.approx(3 / 4)
        assert m["support[x]"] == 2 and m["support[y]"] == 2

    def test_grouped_folds_never_split_a_group(self):
        groups = np.array(list("aabbccddeeffgghh"))
        y = np.array(["p", "n"] * 8)
        for tr, te in M.grouped_folds(y, groups, n_splits=4, seed=3):
            assert not (set(groups[tr]) & set(groups[te]))

    def test_leave_one_group_out_holds_out_each_group(self):
        seen = {}
        def fp(Xtr, ytr, Xte):
            seen[len(Xte)] = True
            return ["a"] * len(Xte)
        out = M.leave_one_group_out(fp, ["t1", "t2", "t3", "t4"], ["a", "b", "a", "b"], ["g1", "g1", "g2", "g3"])
        assert sorted(out) == ["g1", "g2", "g3"] and len(out["g1"][0]) == 2


# --------------------------------------------------------------------------------------------------------------------------
# rules and QuRE weak words
# --------------------------------------------------------------------------------------------------------------------------
class TestRules:
    def test_fr_nfr_rule(self):
        assert clf.rule_fr_nfr("The system shall encrypt all stored passwords.") == "NFR"
        assert clf.rule_fr_nfr("The system shall allow a clerk to add a customer record.") == "FR"
        assert clf.rule_security("Users must authenticate before access.") == "1"

    def test_weak_word_rule_whole_word(self):
        model = amb.WeakWordRuleModel(weak_words=["fast", "adequate"]).fit([], None)
        assert list(model.predict(["The system must be fast.", "A breakfast menu.", "Provide adequate support.", "Print the invoice."])) == ["defect", "ok", "defect", "ok"]
        assert amb.RULE_NAME == "qure_weak_word_rule"

    def test_weak_words_parse(self):
        assert amb.weak_words_from_evidence(["defect=ok;weak_word=Detail", "-", "defect=defect;weak_word=close"]) == ["close", "detail"]

    def test_effective_groups_split_ungrouped_rows(self):
        df = pd.DataFrame({"group_id": ["FR_NFR:ungrouped", "FR_NFR:ungrouped", "PROMISE_P1"], "record_id": ["r1", "r2", "r3"]})
        g = rb.effective_groups(df)
        assert len(set(g)) == 3 and g[2] == "PROMISE_P1"


# --------------------------------------------------------------------------------------------------------------------------
# reproducibility
# --------------------------------------------------------------------------------------------------------------------------
def _fixture_frames():
    """Small real slice of the FR/NFR train/val rows (train and val only)."""
    tr, va = da.load_task("classification_fr_nfr", ("train",)), da.load_task("classification_fr_nfr", ("val",))
    pick = lambda d, n: d.assign(_o=d.record_id.map(rb.order_key)).sort_values("_o", kind="stable").head(n).drop(columns="_o")  # noqa: E731
    return pick(tr, 400).reset_index(drop=True), pick(va, 150).reset_index(drop=True)


class TestReproducibility:
    def _run(self):
        train, val = _fixture_frames()
        res = rb.Results("fr_nfr")
        exp = rb.SingleLabel(res, "fr_nfr", ["FR", "NFR"], ["majority", "rules", "tfidf_lr", "tfidf_svm"], lambda d: d.requirement_type.isin(["FR", "NFR"]),
                             lambda d: d.requirement_type.values, "fr_nfr", lambda d: {"pooled": np.ones(len(d), bool)})
        exp.develop(train, val, n_boot=30)
        exp.cross_validate(n_boot=30)
        return pd.DataFrame(res.metrics), pd.DataFrame(res.tuning), exp.best

    def test_two_runs_are_identical(self):
        m1, t1, b1 = self._run()
        m2, t2, b2 = self._run()
        pd.testing.assert_frame_equal(m1, m2)
        pd.testing.assert_frame_equal(t1, t2)
        assert b1 == b2

    def test_tuning_uses_only_validation_scores(self):
        train, val = _fixture_frames()
        model, C, rows = clf.tune_and_fit("tfidf_lr", train.requirement_text_normalized, train.requirement_type.values,
                                          val.requirement_text_normalized, val.requirement_type.values)
        assert C in clf.C_GRID["tfidf_lr"] and len(rows) == len(clf.C_GRID["tfidf_lr"])
        assert max(r["val_score"] for r in rows) == [r for r in rows if r["C"] == C][0]["val_score"]

    def test_order_key_is_stable(self):
        assert rb.order_key("abc") == rb.order_key("abc") and rb.order_key("abc") != rb.order_key("abd")
