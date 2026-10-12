"""Build task-specific datasets with leakage-safe train/val/test splits from processed/master_requirements.csv.

Run order (each script is deterministic and idempotent; none overwrites a differing file):
    build_master.py  ->  build_srs_requirements.py  ->  build_task_datasets.py

Outputs
  processed/tasks/classification_fr_nfr.csv, classification_nfr_subtype.csv, ambiguity.csv, dependency_pairs.csv,
  generation_inputs.csv, pipeline_test_cornelius.csv, dependency_spot_check.csv,
  frozen_test_ids.csv, manifest.json
  processed/DATA_CARD.md
  audit_reports_component1/processed_build_report.csv
  audit_reports_component1/proposed_suitability_decisions_processed.csv   (the tracker itself is NOT edited)
  (duplicate_candidates.csv is created only when real labeled pairs exist; none do, which is recorded in the data card.)

Split method (decision B)
  1. A task-eligible pool is taken from the master: no exclusion_reason (so no TCS, needs-review, provenance-unconfirmed,
     pipeline-test-only or label-conflict rows) and at least MIN_WORDS words (shorter texts are dropped from all task files).
  2. Rows are assigned to train/val/test at the level of their SOURCE group (PROMISE project, PURE document, ARTA file, user-story
     project; sources without a document column use the text itself as the group), separately per source, greedily towards 70/15/15
     of that source's rows. PROMISE projects P1-P10 follow the project-level 7/1/2 split of the dependency task so that the
     two tasks do not leak into each other.
  3. Any text (alnum-only key) present in train anywhere in the pool is removed from val and test everywhere; a text present in
     both test and val keeps only the test copy. group_id is kept in every file, so PROMISE can also be evaluated leave-one-project-out.
  4. Within each task file there is exactly one row per text key.
"""
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_master as bm  # noqa: E402
from build_master import AUDIT, PROCESSED, RAW, MIN_WORDS, normalize_text, text_key, write_safe  # noqa: E402

SEED = 327
TARGETS = {"train": 0.70, "val": 0.15, "test": 0.15}
SPLITS = ["train", "val", "test"]
TASKS = PROCESSED / "tasks"
OUT_REPORT = AUDIT / "processed_build_report.csv"
OUT_SUITABILITY = AUDIT / "proposed_suitability_decisions_processed.csv"
OUT_CARD = PROCESSED / "DATA_CARD.md"
TRACE_RELATIONS = PROCESSED / "promise_trace_relationships.csv"
TRACE_DIR = RAW / "nfr_fr_trace"
SOURCE_PRIORITY = ["PROMISE", "PROMISE_NICE", "nfr_labeled", "FR_NFR", "PURE", "security_requirements", "QuRE", "DS1", "DS3", "DS2", "DS4",
                   "user_stories"]


def h(*parts):
    return hashlib.sha256("|".join(str(p) for p in (SEED,) + parts).encode("utf-8")).hexdigest()


def write_text_safe(path, text):
    data = text.encode("utf-8")
    if path.exists():
        if path.read_bytes() == data:
            print(f"unchanged: {path.name}")
            return
        raise SystemExit(f"STOP: {path} already exists and differs from what would be written. Not overwriting; ask the owner.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"written:   {path.name}")


# ----------------------------------------------------------------------------- dependency task (project split first)
def dependency_project_split():
    projects = [f"P{n}" for n in range(1, 11)]
    order = sorted(projects, key=lambda p: h("dependency_project", p))
    return {**{p: "test" for p in order[:2]}, **{p: "val" for p in order[2:3]}, **{p: "train" for p in order[3:]}}


def parse_trace_text():
    """(project_number, index) -> (text, label) from the '% proj,idx, text, label' comment lines of the trace ARFFs."""
    texts, line_re = {}, re.compile(r"^%\s*(\d+)\s*,\s*(\d+)\s*,\s*(.*)$")
    for path in sorted(TRACE_DIR.glob("P*_NFR_FR_trace.arff")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = line_re.match(line.strip())
            if not m:
                continue
            rest = m.group(3)
            if "," not in rest:
                continue
            text, label = rest.rsplit(",", 1)
            texts[(int(m.group(1)), int(m.group(2)))] = (text.strip(), label.strip())
    return texts


# ----------------------------------------------------------------------------- split assignment
def assign_groups(pool, forced, fixed=None):
    """Greedy group-level assignment per source toward 70/15/15 of that source's rows. Deterministic.
    `fixed` maps row index -> split for rows whose split is inherited (they count toward the totals but are not re-assigned)."""
    fixed = fixed or {}
    split_of_row = dict(fixed)
    for source, part in pool.groupby("source_dataset", sort=True):
        total = len(part)
        current = {s: 0 for s in SPLITS}
        for i in part.index:
            if i in fixed:
                current[fixed[i]] += 1
        part = part[~part.index.isin(fixed)]
        if part.empty:
            continue
        group_key = part.apply(lambda r: ("ROW:" + r.text_key) if r.group_id.endswith(":ungrouped") else r.group_id, axis=1)
        sizes = group_key.value_counts().to_dict()
        assignment = {}
        for g, split in forced.items():
            if g in sizes:
                assignment[g] = split
                current[split] += sizes[g]
        for g in sorted((g for g in sizes if g not in assignment), key=lambda g: (-sizes[g], h("group", source, g))):
            best = max(SPLITS, key=lambda s: ((TARGETS[s] * total - current[s]) / (TARGETS[s] * total), -SPLITS.index(s)))
            assignment[g] = best
            current[best] += sizes[g]
        for idx, g in zip(part.index, group_key):
            split_of_row[idx] = assignment[g]
    return pd.Series(split_of_row).reindex(pool.index)


def remove_text_overlap(pool):
    """train > test > val priority across the whole pool (all tasks, all sources)."""
    by_key = pool.groupby("text_key")["split0"].agg(lambda s: set(s))
    def resolve(row):
        splits = by_key[row.text_key]
        if row.split0 == "train":
            return row.split0, ""
        if "train" in splits:
            return "", "text_in_train"
        if row.split0 == "val" and "test" in splits:
            return "", "text_in_test"
        return row.split0, ""
    resolved = pool.apply(resolve, axis=1, result_type="expand")
    pool = pool.copy()
    pool["split"], pool["removed_reason"] = resolved[0], resolved[1]
    return pool


# ----------------------------------------------------------------------------- task builders
def first_per_key(df, order):
    rank = {s: i for i, s in enumerate(order)}
    ranked = df.assign(_rank=df.source_dataset.map(lambda s: rank.get(s, len(rank)))).sort_values(["_rank", "record_id"], kind="stable")
    return ranked.drop_duplicates("text_key", keep="first").drop(columns="_rank")


def also_in(df_all_pool, kept):
    sources = df_all_pool.groupby("text_key")["source_dataset"].agg(lambda s: ";".join(sorted(set(s))))
    return kept.text_key.map(sources)


COMMON = ["record_id", "split", "group_id", "source_dataset", "requirement_text_original", "requirement_text_normalized", "text_key"]


def task_fr_nfr(pool):
    d = pool[pool.split.isin(SPLITS) & pool.requirement_type.isin(["FR", "NFR"]) & pool.source_dataset.isin(["PROMISE", "PROMISE_NICE", "nfr_labeled", "FR_NFR"])]
    d = first_per_key(d, SOURCE_PRIORITY)
    d = d.assign(label_source=d.source_dataset, also_in_sources=also_in(pool, d))
    return d[COMMON + ["requirement_type", "label_source", "also_in_sources"]]


def task_subtype(pool):
    d = pool[pool.split.isin(SPLITS) & pool.source_dataset.isin(["PROMISE", "PROMISE_NICE", "nfr_labeled", "PURE", "security_requirements"])
             & ((pool.nfr_subtype != "") | (pool.security_label != "") | (pool.reliability_label != ""))]
    d = first_per_key(d, SOURCE_PRIORITY)
    scheme = d.apply(lambda r: r.nfr_subtype_scheme or {"PURE": "PURE_security_reliability", "security_requirements": "SECURITY_BINARY"}.get(r.source_dataset, ""), axis=1)
    d = d.assign(label_scheme=scheme, label_source=d.source_dataset, also_in_sources=also_in(pool, d),
                 reliability_eval_status=d.reliability_label.map(lambda v: "too_sparse_to_evaluate" if v != "" else ""),
                 metrics_include_reliability=False)
    return d[COMMON + ["requirement_type", "label_scheme", "nfr_subtype", "security_label", "reliability_label",
                       "reliability_eval_status", "metrics_include_reliability", "label_source", "also_in_sources"]]


def task_ambiguity(pool):
    d = pool[pool.split.isin(SPLITS) & pool.ambiguity_label.isin(["defect", "ok"]) & ~pool.source_dataset.isin(["Cornelius"])]
    d = first_per_key(d, SOURCE_PRIORITY)
    d = d.assign(also_in_sources=also_in(pool, d))
    return d[COMMON + ["ambiguity_label", "ambiguity_label_basis", "source_label_raw", "also_in_sources"]].rename(
        columns={"source_label_raw": "smell_evidence"})


def task_generation(pool):
    d = pool[pool.split.isin(SPLITS)]
    d = first_per_key(d, SOURCE_PRIORITY)
    d = d.assign(record_type=d.text_type.map({"requirement": "requirement_text", "user_story": "user_story_reference"}),
                 pairing="unpaired", also_in_sources=also_in(pool, d))
    return d[COMMON + ["record_type", "pairing", "requirement_type", "nfr_subtype", "also_in_sources"]]


def task_dependency(master, proj_split, trace_texts):
    rel = pd.read_csv(TRACE_RELATIONS, dtype=str, keep_default_na=False)
    key_to_master = master.drop_duplicates("text_key").set_index("text_key").record_id.to_dict()
    rows, stats = [], Counter()
    for r in rel.itertuples(index=False):
        pnum = int(r.project[1:])
        fr_idx, nfr_idx = int(r.fr_id[1:]), int(re.sub(r"\D", "", r.nfr_id))
        fr, nfr = trace_texts.get((pnum, fr_idx)), trace_texts.get((pnum, nfr_idx))
        if not fr or not nfr:
            stats["dropped_text_missing"] += 1
            continue
        fr_key, nfr_key = text_key(normalize_text(fr[0])), text_key(normalize_text(nfr[0]))
        if len(normalize_text(fr[0]).split()) < MIN_WORDS or len(normalize_text(nfr[0]).split()) < MIN_WORDS:
            stats["dropped_short_text"] += 1
            continue
        if fr_key not in key_to_master or nfr_key not in key_to_master:
            stats["dropped_not_in_master"] += 1
            continue
        check = "label_consistent" if (fr[1] == "F" and nfr[1] != "F") else "label_inconsistent"
        rows.append({
            "record_id": f"DEP:{r.project}:{r.fr_id}:{r.nfr_id}", "split": proj_split[r.project], "group_id": f"PROMISE_{r.project}",
            "source_dataset": "promise_trace_relationships", "project": r.project, "fr_id": r.fr_id, "nfr_id": r.nfr_id,
            "fr_text": fr[0], "nfr_text": nfr[0], "fr_text_key": fr_key, "nfr_text_key": nfr_key,
            "fr_master_record_id": key_to_master.get(fr_key, ""), "nfr_master_record_id": key_to_master.get(nfr_key, ""),
            "relationship": r.relationship, "semantics": "unconfirmed", "text_join_status": "inferred_unverified",
            "text_join_check": check, "license_note": "CC BY-SA 3.0 (PROMISE trace matrices)"})
    d = pd.DataFrame(rows)
    # text overlap train > test > val over both text sides
    texts_by_split = defaultdict(set)
    for r in d.itertuples():
        texts_by_split[r.split].update([r.fr_text_key, r.nfr_text_key])
    keep = []
    for r in d.itertuples():
        keys = {r.fr_text_key, r.nfr_text_key}
        if r.split != "train" and keys & texts_by_split["train"]:
            stats["dropped_text_in_train"] += 1
            keep.append(False)
        elif r.split == "val" and keys & texts_by_split["test"]:
            stats["dropped_text_in_test"] += 1
            keep.append(False)
        else:
            keep.append(True)
    d = d[keep].reset_index(drop=True)
    stats["rows_in"] = len(rel)
    return d, stats


# ----------------------------------------------------------------------------- orchestration
def compute():
    master_built, conflicts, report_rows, _ = bm.build()
    master_built = bm.clean_master(master_built)
    on_disk = pd.read_csv(bm.OUT_MASTER, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    assert bm.to_bytes(master_built) == bm.OUT_MASTER.read_bytes(), "master_requirements.csv on disk is stale: rerun build_master.py"
    master = on_disk
    master["word_count"] = master.word_count.astype(int)

    proj_split = dependency_project_split()
    forced = {f"PROMISE_{p}": s for p, s in proj_split.items()}

    eligible = master[(master.exclusion_reason == "")]
    short = eligible[eligible.word_count < MIN_WORDS]
    pool = eligible[eligible.word_count >= MIN_WORDS].copy()

    # Pure decision B (every source assigned independently), kept only to report what the refinement below changes.
    pure_b = remove_text_overlap(pool.assign(split0=assign_groups(pool, forced)))

    # Refinement: copies of PROMISE texts in other sources inherit the split of their PROMISE project, so PROMISE keeps real val/test rows.
    promise_rows = pool[pool.source_dataset == "PROMISE"]
    promise_split = assign_groups(promise_rows, forced)
    anchor = dict(zip(promise_rows.text_key, promise_split))
    others = pool[pool.source_dataset != "PROMISE"]
    fixed = {i: anchor[k] for i, k in zip(others.index, others.text_key) if k in anchor}
    split0 = pd.concat([promise_split, assign_groups(others, {}, fixed)]).reindex(pool.index)
    pool = remove_text_overlap(pool.assign(split0=split0))
    anchoring = {
        "rows_inheriting_promise_split": len(fixed),
        "promise_rows_in_val_test_pure_B": int(((pure_b.source_dataset == "PROMISE") & pure_b.split.isin(["val", "test"])).sum()),
        "promise_rows_in_val_test_with_anchoring": int(((pool.source_dataset == "PROMISE") & pool.split.isin(["val", "test"])).sum()),
        "rows_removed_pure_B": int((pure_b.split == "").sum()), "rows_removed_with_anchoring": int((pool.split == "").sum())}

    # Held-out projects: a row whose project group sits in the test split but which itself landed in train or val is excluded, never moved
    # (moving it would add a row to the frozen test split). Applied after the text-overlap removal so the test split cannot change.
    test_projects = set(pool[(pool.split == "test") & pool.group_id.str.match(r"^PROMISE_P\d+$")].group_id)
    conflict = pool.group_id.isin(test_projects) & pool.split.isin(["train", "val"])
    pool.loc[conflict, "split"] = ""
    pool.loc[conflict, "removed_reason"] = "held_out_project_split_conflict"
    anchoring["held_out_project_conflict_rows_excluded"] = int(conflict.sum())

    tasks = {
        "classification_fr_nfr": task_fr_nfr(pool),
        "classification_nfr_subtype": task_subtype(pool),
        "ambiguity": task_ambiguity(pool),
        "generation_inputs": task_generation(pool),
    }
    dependency, dep_stats = task_dependency(master, proj_split, parse_trace_text())
    tasks["dependency_pairs"] = dependency

    # pipeline test sample from Cornelius (templated data: never main training/evaluation data)
    cor = master[master.source_dataset == "Cornelius"].copy()
    cor["_o"] = cor.record_id.map(lambda r: h("cornelius", r))
    sample = pd.concat([cor[cor.ambiguity_label == lab].sort_values("_o").head(100) for lab in ("defect", "ok")])
    sample["split"] = sample.record_id.map(lambda r: "train" if int(h("cornelius_split", r), 16) % 100 < 70 else ("val" if int(h("cornelius_split", r), 16) % 100 < 85 else "test"))
    tasks["pipeline_test_cornelius"] = sample.sort_values("record_id")[COMMON + ["ambiguity_label", "ambiguity_label_basis"]].assign(
        pipeline_test_only=True)

    for name, df in tasks.items():
        tasks[name] = df.sort_values("record_id", kind="stable").reset_index(drop=True)

    # dependency spot check: 15 trace + 5 anti_trace, seeded
    d = tasks["dependency_pairs"].copy()
    d["_o"] = d.record_id.map(lambda r: h("spot", r))
    spot = pd.concat([d[d.relationship == "trace"].sort_values("_o").head(15), d[d.relationship == "anti_trace"].sort_values("_o").head(5)])
    spot = spot.sort_values("_o")[["record_id", "project", "fr_id", "nfr_id", "fr_text", "nfr_text", "relationship", "semantics",
                                   "text_join_status", "text_join_check", "split"]].assign(manual_check_text_matches_id="", manual_notes="")
    tasks["dependency_spot_check"] = spot.reset_index(drop=True)

    return master, conflicts, report_rows, pool, short, tasks, dep_stats, proj_split, anchoring


def _canon(term):
    return re.sub(r"[^a-z]", "", term.lower())


def _same_category(a, b):
    a, b = _canon(a), _canon(b)
    return a.startswith(b) or b.startswith(a) or a[:10] == b[:10]


def arta_conflict_analysis(master, conflicts):
    """Explain the cross-source ARTA ambiguity conflicts: which smell categories the 'defect' side flagged, and whether the
    'ok' side's file even annotates that category. Returns (per-conflict frame, 20-row sample)."""
    mi = master.set_index("record_id")
    headers = {}
    for name in ("DS1", "DS2", "DS3", "DS4"):
        cols = list(pd.read_excel(RAW / f"{name}.xlsx", dtype=str, nrows=0).columns)
        headers[name] = cols[2:]
    rows = []
    arta = conflicts[conflicts.dimension == "ambiguity_label[ARTA]"]
    for c in arta.itertuples():
        recs = [mi.loc[x] for x in c.master_record_ids.split(";") if x in mi.index and mi.loc[x].source_dataset.startswith("DS")]
        defect = [r for r in recs if r.ambiguity_label == "defect"]
        ok = [r for r in recs if r.ambiguity_label == "ok"]
        if not defect or not ok:
            continue
        terms = sorted({t.split("=")[0] for r in defect for t in r.source_label_raw.split(";") if t and t != "-"})
        not_annotated = [t for t in terms if not any(_same_category(t, hc) for r in ok for hc in headers[r.source_dataset])]
        reason = ("defect_side_flags_only_categories_the_ok_file_does_not_annotate" if terms and len(not_annotated) == len(terms)
                  else "category_annotated_in_both_files_but_labels_differ")
        rows.append({"conflict_id": c.conflict_id, "defect_in": ";".join(r.source_dataset for r in defect), "ok_in": ";".join(r.source_dataset for r in ok),
                     "defect_side_smell_terms": ";".join(terms), "terms_not_annotated_by_ok_file": ";".join(not_annotated), "reason": reason,
                     "text": c.example_text, "defect_record_ids": ";".join(r.name for r in defect), "ok_record_ids": ";".join(r.name for r in ok)})
    allc = pd.DataFrame(rows)
    order = allc.conflict_id.map(lambda x: h("arta_conflict_sample", x))
    sample = allc.assign(_o=order).sort_values("_o", kind="stable").head(20).drop(columns="_o").sort_values("conflict_id", kind="stable").reset_index(drop=True)
    sample.insert(0, "sample_no", range(1, len(sample) + 1))
    return allc, sample


def srs_spot_check(srs, counts):
    """100 rows for manual checking: round 1 one row per document, then up to 3 rows for each very-low-density document, then fill with second rows."""
    low = set(counts[counts.suspicious_count_flags.str.contains("very_low_density")].source_document)
    srs = srs.assign(_o=srs.srs_record_id.map(lambda x: h("srs_spot", x))).sort_values("_o", kind="stable")
    rank = srs.groupby("source_document").cumcount() + 1
    srs = srs.assign(_rank=rank)
    picked = srs[srs._rank == 1]
    extra_low = srs[srs.source_document.isin(low) & srs._rank.isin([2, 3])]
    second = srs[(srs._rank == 2) & ~srs.source_document.isin(low)]
    picked = pd.concat([picked, extra_low, second.head(max(0, 100 - len(picked) - len(extra_low)))]).head(100)
    out = picked.sort_values(["source_document", "position"], key=lambda c: c.astype(int) if c.name == "position" else c, kind="stable")
    out = out[["srs_record_id", "source_document", "source_format", "line_start", "clause_label", "cleaned_text", "candidate_type", "extraction_rule"]].copy()
    out["is_requirement"] = ""
    out["reviewer_note"] = ""
    return out.reset_index(drop=True)


SEED_QUOTAS = {"FR": {"FR_NFR": 50, "PROMISE": 25}, "NFR": {"FR_NFR": 25, "PROMISE": 25, "PURE": 25}}
EVAL_QUOTAS = {"FR": {"FR_NFR": 35, "PROMISE": 15}, "NFR": {"FR_NFR": 20, "PROMISE": 15, "PURE": 15}}


def _jaccard(a, b):
    sa, sb = set(re.findall(r"[a-z0-9]+", a)), set(re.findall(r"[a-z0-9]+", b))
    return len(sa & sb) / max(len(sa | sb), 1)


def select_stratified(gen, split, quotas, max_words, tag, near_dup_jaccard=None):
    """Deterministic stratified pick of `requirement_text` rows of one split: quotas per (FR/NFR, source), 6..max_words words, one row
    per normalized text, optionally no two picked texts with word-Jaccard >= near_dup_jaccard. A source that cannot fill its quota hands
    the shortfall to FR_NFR. Returns the selected rows of `gen`."""
    pool = gen[(gen.split == split) & (gen.record_type == "requirement_text") & gen.requirement_type.isin(["FR", "NFR"])].copy()
    wc = pool.requirement_text_normalized.str.split().str.len()
    pool = pool[(wc >= MIN_WORDS) & (wc <= max_words)].drop_duplicates("text_key")
    pool = pool.assign(_o=pool.record_id.map(lambda r: h(tag, r))).sort_values("_o", kind="stable")
    picked, taken_texts = [], []
    for label, per_source in quotas.items():
        shortfall = 0
        for source, quota in per_source.items():
            cand = pool[(pool.requirement_type == label) & (pool.source_dataset == source) & ~pool.record_id.isin([r.record_id for r in picked])]
            got = []
            for r in cand.itertuples():
                if len(got) >= quota + (shortfall if source == "FR_NFR" else 0):
                    break
                if near_dup_jaccard is not None and any(_jaccard(r.requirement_text_normalized, t) >= near_dup_jaccard for t in taken_texts):
                    continue
                got.append(r)
                taken_texts.append(r.requirement_text_normalized)
            picked += got
            if source != "FR_NFR":
                shortfall += max(0, quota - len(got))
    return gen[gen.record_id.isin([r.record_id for r in picked])].copy()


def seed_and_eval_files(gen):
    """synthetic_seed_inputs (150 train rows with text) and generation_eval_ids (100 test ids, no text, nothing else)."""
    seeds = select_stratified(gen, "train", SEED_QUOTAS, 60, "synthetic_seed", near_dup_jaccard=0.9)
    seeds = seeds.sort_values("record_id", kind="stable")
    seed_df = pd.DataFrame({"id": seeds.record_id.values, "source": seeds.source_dataset.values,
                            "requirement_text": seeds.requirement_text_original.values, "requirement_type": seeds.requirement_type.values})
    ev = select_stratified(gen, "test", EVAL_QUOTAS, 60, "generation_eval")
    eval_df = pd.DataFrame({"id": sorted(ev.record_id)})
    eval_counts = ev.groupby(["requirement_type", "source_dataset"]).size().rename("rows").reset_index()
    return seed_df, eval_df, eval_counts


def frozen_test(tasks):
    rows = []
    for name in ("classification_fr_nfr", "classification_nfr_subtype", "ambiguity", "dependency_pairs", "generation_inputs"):
        t = tasks[name]
        for rid in t[t.split == "test"].record_id:
            rows.append({"task": name, "record_id": rid})
    return pd.DataFrame(rows).sort_values(["task", "record_id"], kind="stable").reset_index(drop=True)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def distribution_lines(tasks):
    lines = []
    for name in ("classification_fr_nfr", "classification_nfr_subtype", "ambiguity", "generation_inputs", "dependency_pairs", "pipeline_test_cornelius"):
        t = tasks[name]
        lines.append(f"\n**{name}.csv** - {len(t)} rows. Split sizes: " + ", ".join(f"{s}={int((t.split == s).sum())}" for s in SPLITS))
        if name == "classification_fr_nfr":
            tab = pd.crosstab(t.requirement_type, t.split).reindex(columns=SPLITS, fill_value=0)
        elif name == "classification_nfr_subtype":
            ex = t.assign(security_label=t.security_label.replace("", "(none)"), label_scheme=t.label_scheme)
            tab = pd.crosstab(ex.label_scheme + " / security=" + ex.security_label, ex.split).reindex(columns=SPLITS, fill_value=0)
        elif name == "ambiguity":
            tab = pd.crosstab(t.ambiguity_label_basis + " / " + t.ambiguity_label, t.split).reindex(columns=SPLITS, fill_value=0)
        elif name == "generation_inputs":
            tab = pd.crosstab(t.record_type + " / " + t.source_dataset, t.split).reindex(columns=SPLITS, fill_value=0)
        elif name == "dependency_pairs":
            tab = pd.crosstab(t.relationship, t.split).reindex(columns=SPLITS, fill_value=0)
        else:
            tab = pd.crosstab(t.ambiguity_label, t.split).reindex(columns=SPLITS, fill_value=0)
        lines.append("\n| class | train | val | test |\n|---|---|---|---|\n" + "\n".join(
            f"| {i} | {r['train']} | {r['val']} | {r['test']} |" for i, r in tab.iterrows()))
    return "\n".join(lines)


def main():
    master, conflicts, report_rows, pool, short, tasks, dep_stats, proj_split, anchoring = compute()

    # ---- task files
    TASKS.mkdir(parents=True, exist_ok=True)
    for name, df in tasks.items():
        write_safe(TASKS / f"{name}.csv", df)
    frozen = frozen_test(tasks)
    write_safe(TASKS / "frozen_test_ids.csv", frozen)

    # ---- review aids (not part of the manifest: they are not task data)
    arta_all, arta_sample = arta_conflict_analysis(master, conflicts)
    write_safe(TASKS / "ambiguity_arta_conflict_samples.csv", arta_sample)
    srs_all = pd.read_csv(PROCESSED / "srs_requirements_extracted.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    srs_counts = pd.read_csv(AUDIT / "srs_requirements_per_document_counts.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    spot = srs_spot_check(srs_all, srs_counts)
    write_safe(TASKS / "srs_extraction_spot_check.csv", spot)

    # ---- seed inputs for synthetic generation (train) and reserved evaluation ids (test: ids only)
    seed_df, eval_df, eval_counts = seed_and_eval_files(tasks["generation_inputs"])
    write_safe(TASKS / "synthetic_seed_inputs.csv", seed_df)
    write_safe(TASKS / "generation_eval_ids.csv", eval_df)

    # ---- manifest
    files = {}
    for name in tasks:
        files[f"{name}.csv"] = sha256_bytes((TASKS / f"{name}.csv").read_bytes())
    files["frozen_test_ids.csv"] = sha256_bytes((TASKS / "frozen_test_ids.csv").read_bytes())
    manifest = {"seed": SEED, "min_words": MIN_WORDS, "targets": TARGETS, "split_method": "per-source group assignment, then train>test>val text-overlap removal",
                "dependency_project_split": proj_split, "frozen_test_ids_sha256": files["frozen_test_ids.csv"],
                "frozen_test_ids_rows": len(frozen), "promise_anchoring": anchoring, "file_sha256": files,
                "duplicate_candidates": "not created: no real labeled duplicate pairs exist in the sources"}
    write_text_safe(TASKS / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    # ---- per-file build report
    in_tasks = set()
    for name in ("classification_fr_nfr", "classification_nfr_subtype", "ambiguity", "generation_inputs"):
        in_tasks |= set(tasks[name].record_id)
    master["_in_task"] = master.record_id.isin(in_tasks)
    by_file = master.groupby("source_file")
    removed = pool[pool.split == ""].groupby("source_file").size().to_dict()
    short_by = short.groupby("source_file").size().to_dict()
    report = []
    for r in report_rows:
        f = r["input_file"]
        g = master[master.source_file == f]
        report.append({**{k: v for k, v in r.items() if k not in ("stage",)}, "stage": "master", "rows_out": r["rows_out"],
                       "rows_flagged_excluded_from_tasks": int((g.exclusion_reason != "").sum()),
                       "rows_short_text_dropped_from_tasks": int(short_by.get(f, 0)),
                       "rows_removed_for_text_overlap": int(removed.get(f, 0)),
                       "rows_in_task_files": int(g._in_task.sum())})
    counts = pd.read_csv(AUDIT / "srs_requirements_per_document_counts.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    for c in counts.itertuples():
        report.append({"input_file": f"{c.source_document}.{c.source_format}", "stage": "srs_extraction", "note": c.suspicious_count_flags,
                       "rows_in": int(c.blocks_examined), "rows_out": int(c.rows_extracted), "rows_flagged_excluded_from_tasks": int(c.rows_extracted)})
    report.append({"input_file": "promise_trace_relationships.csv", "stage": "dependency_pairs", "note": "text joined from trace ARFF comment lines (inferred_unverified)",
                   "rows_in": dep_stats["rows_in"], "rows_dropped_empty": dep_stats["dropped_text_missing"],
                   "rows_dropped_other": dep_stats["dropped_not_in_master"],
                   "rows_short_text_dropped_from_tasks": dep_stats["dropped_short_text"],
                   "rows_removed_for_text_overlap": dep_stats["dropped_text_in_train"] + dep_stats["dropped_text_in_test"],
                   "rows_out": len(tasks["dependency_pairs"]), "rows_in_task_files": len(tasks["dependency_pairs"])})
    cols = ["input_file", "stage", "note", "rows_in", "rows_dropped_empty", "rows_dropped_duplicates", "rows_moved_to_conflicts",
            "rows_collapsed_into_canonical", "rows_missing_label_kept", "rows_dropped_other", "rows_out", "rows_flagged_excluded_from_tasks",
            "rows_short_text_dropped_from_tasks", "rows_removed_for_text_overlap", "rows_in_task_files"]
    rep = pd.DataFrame([{c: row.get(c, "") for c in cols} for row in report], columns=cols).astype(object)
    write_safe(OUT_REPORT, rep)

    # ---- proposed suitability (tracker untouched)
    tracker = pd.read_csv(AUDIT / "dataset_suitability_tracker.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    cur = dict(zip(tracker.file_name, tracker.suitability))
    n_task = master.groupby("source_dataset")["_in_task"].sum().to_dict()
    proposals = [
        ("promise.csv", "CANONICAL_TEXT_FOR_PROMISE_FR_NFR", "fr_nfr, nfr_subtype (via NICE flags), dependency joins", "PROMISE", "commas intact; 26 PROMISE-vs-NICE label disagreements are excluded, not resolved"),
        ("PROMISE-relabeled-NICE.csv", "SECOND_LABEL_SET_FOR_PROMISE", "nfr_subtype labels, security flag; collapsed into promise.csv", "PROMISE", "Both-flag/no-flag rows leave requirement_type empty"),
        ("nfr_labeled.txt / test_labeled.txt", "DUPLICATE_COPY_OF_PROMISE", "none (collapsed as provenance)", "nfr_labeled", "commas stripped in the parsed copy; use promise.csv text"),
        ("software_requirements_extended.csv", "PROVENANCE_UNCONFIRMED", "none until provenance is confirmed", "software_extended", "PROMISE copy plus rows of unknown origin"),
        ("FR_NFR_Dataset.xlsx", "CANDIDATE_FR_NFR_TRAINING_EVALUATION_SOURCE", "fr_nfr", "FR_NFR", "no source-document column; 31 unlabeled rows kept empty; duplicates/conflicts removed"),
        ("pure_subset.csv", "CANDIDATE_SECURITY_RELIABILITY_SOURCE", "nfr_subtype (security); reliability kept but too sparse to evaluate", "PURE", "mixed UTF-8/cp1252 bytes decoded; regulatory documents dominate; NFR_boolean=0 meaning unconfirmed so not used for FR/NFR"),
        ("security_requirements.csv", "CANDIDATE_SECURITY_BINARY_SOURCE", "nfr_subtype (security)", "security_requirements", "one stray label value left unlabeled"),
        ("QuRE.csv", "CANDIDATE_AMBIGUITY_DEFECT_SOURCE", "ambiguity", "QuRE", "defect definition differs from ARTA; reported by ambiguity_label_basis"),
        ("DS1.xlsx", "CANDIDATE_AMBIGUITY_SOURCE", "ambiguity (defect = any smell term)", "DS1", "label derived from smell columns; cross-DS disagreements excluded"),
        ("DS2.xlsx", "CANDIDATE_AMBIGUITY_SOURCE_TCS_ROWS_HELD", "ambiguity", "DS2", "1999-tcs rows held out (tcs_hold)"),
        ("DS3.xlsx", "CANDIDATE_AMBIGUITY_SOURCE", "ambiguity", "DS3", "overlaps PROMISE and DS1; cross-DS disagreements excluded"),
        ("DS4.xlsx", "CANDIDATE_AMBIGUITY_SOURCE_TCS_ROWS_HELD", "ambiguity", "DS4", "1999-tcs rows held out (tcs_hold)"),
        ("arta_evaluation/003,005", "TOOL_OUTPUT_NOT_GROUND_TRUTH", "none", "", "ARTA/Smella tool results, not human labels"),
        ("user_stories.csv", "REFERENCE_USER_STORIES", "generation_inputs (reference outputs, unpaired)", "user_stories", "no requirement-to-story pairing exists"),
        ("Cornelius dataset", "PIPELINE_TEST_ONLY", "pipeline_test_cornelius.csv (200 rows)", "Cornelius", "templated, low diversity: never main training/evaluation data"),
        ("basic/context/context_role.csv", "NEEDS_REVIEW_EXCLUDED", "none", "basic", "provenance and labels unconfirmed"),
        ("nfr_fr_trace P1-P10", "DEPENDENCY_PAIRS_SEMANTICS_UNCONFIRMED", "dependency_pairs (relation semantics unconfirmed; text join inferred)", "", "0/1 meaning not confirmed; CC BY-SA 3.0"),
        ("SRS documents (76 txt + 3 html)", "CANDIDATE_REQUIREMENT_EXTRACTION_SOURCE_AUTO_UNVERIFIED", "srs_requirements_extracted.csv only; no splits", "", "boundaries unverified; TCS manual review on hold"),
    ]
    sug = pd.DataFrame([{
        "dataset": d, "current_tracker_suitability": cur.get(d.split(" / ")[0].split(",")[0], ""),
        "proposed_suitability": p, "proposed_use": u, "rows_in_task_files": int(n_task.get(src, 0)) if src else "", "caveats": c}
        for d, p, u, src, c in proposals])
    write_safe(OUT_SUITABILITY, sug)

    # ---- data card
    write_text_safe(OUT_CARD, data_card(master, conflicts, rep, tasks, frozen, manifest, pool, short, dep_stats, proj_split, counts, anchoring, arta_all, spot, seed_df, eval_df, eval_counts))


def md_table(df):
    cols = list(df.columns)
    return "| " + " | ".join(cols) + " |\n|" + "|".join("---" for _ in cols) + "|\n" + "\n".join(
        "| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False))


def data_card(master, conflicts, rep, tasks, frozen, manifest, pool, short, dep_stats, proj_split, counts, anchoring, arta_all, spot, seed_df, eval_df, eval_counts):
    master_rep = rep[rep.stage == "master"][["input_file", "rows_in", "rows_dropped_empty", "rows_dropped_duplicates", "rows_moved_to_conflicts",
                                             "rows_collapsed_into_canonical", "rows_out"]]
    srs = pd.read_csv(PROCESSED / "srs_requirements_extracted.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    removal = pool[pool.split == ""].groupby(["source_dataset", "removed_reason"]).size().rename("rows").reset_index()
    confl = conflicts.groupby(["scope", "dimension"]).size().rename("pairs").reset_index()
    labels = master.groupby("source_dataset").agg(rows=("record_id", "size"), FR=("requirement_type", lambda s: int((s == "FR").sum())),
                                                   NFR=("requirement_type", lambda s: int((s == "NFR").sum())),
                                                   defect=("ambiguity_label", lambda s: int((s == "defect").sum())),
                                                   ok=("ambiguity_label", lambda s: int((s == "ok").sum())),
                                                   security_1=("security_label", lambda s: int((s == "1").sum())),
                                                   reliability_1=("reliability_label", lambda s: int((s == "1").sum()))).reset_index()
    excl = Counter(x for v in master.exclusion_reason for x in v.split("|") if x)
    return f"""# Component 1 - processed data card

Generated by `experiments/component1/build_master.py`, `build_srs_requirements.py` and `build_task_datasets.py`
(seed {SEED}; deterministic; re-running reproduces identical bytes). Nothing under `raw/` was modified, the dataset tracker
was not edited, and no model was trained. Every row has `is_synthetic=False`.

## Output files

| file | made by | rows | purpose |
|---|---|---|---|
| `processed/master_requirements.csv` | build_master.py | {len(master)} | one row per source record after within-source de-duplication, with provenance |
| `processed/master_label_conflicts.csv` | build_master.py | {len(conflicts)} | same text with conflicting labels (never resolved) |
| `processed/srs_requirements_extracted.csv` | build_srs_requirements.py | {len(srs)} | candidate requirements from 76 SRS text files + 3 HTML documents; all `auto_unverified`, excluded from splits |
| `audit_reports_component1/srs_requirements_per_document_counts.csv` | build_srs_requirements.py | {len(counts)} | per-document counts and suspicious-count flags |
| `processed/tasks/classification_fr_nfr.csv` | build_task_datasets.py | {len(tasks['classification_fr_nfr'])} | FR/NFR classification |
| `processed/tasks/classification_nfr_subtype.csv` | build_task_datasets.py | {len(tasks['classification_nfr_subtype'])} | NFR subtype / security / reliability |
| `processed/tasks/ambiguity.csv` | build_task_datasets.py | {len(tasks['ambiguity'])} | defect/ok (QuRE + ARTA, identifiable by `ambiguity_label_basis`) |
| `processed/tasks/dependency_pairs.csv` | build_task_datasets.py | {len(tasks['dependency_pairs'])} | FR-NFR pairs, semantics unconfirmed |
| `processed/tasks/generation_inputs.csv` | build_task_datasets.py | {len(tasks['generation_inputs'])} | unpaired pools: requirement texts and user-story references |
| `processed/tasks/pipeline_test_cornelius.csv` | build_task_datasets.py | {len(tasks['pipeline_test_cornelius'])} | pipeline smoke test only |
| `processed/tasks/dependency_spot_check.csv` | build_task_datasets.py | {len(tasks['dependency_spot_check'])} | 20 random joined pairs for manual checking |
| `processed/tasks/ambiguity_arta_conflict_samples.csv` | build_task_datasets.py | 20 | 20 DS1/DS3-type ARTA conflicts with the reason each disagrees |
| `processed/tasks/srs_extraction_spot_check.csv` | build_task_datasets.py | {len(spot)} | SRS rows for manual checking; `is_requirement` and `reviewer_note` are intentionally empty |
| `processed/tasks/synthetic_seed_inputs.csv` | build_task_datasets.py | {len(seed_df)} | seed requirements (train split only) for synthetic generation: id, source, requirement_text, requirement_type |
| `processed/tasks/generation_eval_ids.csv` | build_task_datasets.py | {len(eval_df)} | **ids only** (no text) of test requirements reserved for the final base-vs-fine-tuned generation comparison |
| `processed/tasks/frozen_test_ids.csv` | build_task_datasets.py | {len(frozen)} | frozen test record ids (SHA-256 in `manifest.json`) |
| `processed/tasks/manifest.json` | build_task_datasets.py | - | seed, settings, SHA-256 of every task file |
| `audit_reports_component1/processed_build_report.csv` | build_task_datasets.py | {len(rep)} | one row per input file: rows in / dropped / out |
| `audit_reports_component1/proposed_suitability_decisions_processed.csv` | build_task_datasets.py | - | proposed decisions (the tracker is untouched) |

`duplicate_candidates.csv` was **not created**: no real labeled duplicate or near-duplicate pairs exist in the sources. The duplicates
found here are exact-text duplicates detected by the build itself, which are not human labels.

## How the master table was made

Original text and original labels are kept in their own columns; `requirement_text_normalized` (lower case, quotes stripped, whitespace
collapsed, UTF-8-read-as-cp1252 mojibake repaired in this column only) and `text_key` (alphanumerics only) are derived. Exact duplicates
on normalized text within a source keep one row; if the duplicates carry conflicting labels they are moved to `master_label_conflicts.csv`.
`promise.csv` is the canonical PROMISE text; NICE flags, `nfr_labeled`, `test_labeled` and `software_extended` copies are collapsed into it
as cross-check provenance (see `crosscheck_labels`, `also_in_sources`). Texts shorter than {MIN_WORDS} words are never used as links and are
dropped from every task file. `pure_subset.csv` mixes UTF-8 and cp1252 bytes and is decoded per byte sequence inside `build_master.py`.

### Rows per input (before / after de-duplication)

{md_table(master_rep)}

### Label distributions in the master

{md_table(labels)}

### Label conflicts (never resolved)

{md_table(confl)}

**Why the ARTA files disagree ({len(arta_all)} conflicts, kept excluded).** DS1 annotates 10 smell categories, DS3 only 8 (DS3 lacks Nonverifiable_term, Uncertain_verb and Polysemy and adds open_ended),
so {int((arta_all.reason.str.startswith("defect_side_flags_only")).sum())} of them ("defect in DS1, ok in DS3") are flagged only for categories the other file does not annotate; the rest are real label disagreements on shared categories. Counts over all {len(arta_all)} conflicts:

{md_table(arta_all.groupby('reason').size().rename('conflicts').reset_index())}

Most frequent smell terms on the defect side (a conflict can carry several):

{md_table(pd.Series([t for v in arta_all.defect_side_smell_terms for t in v.split(';') if t]).value_counts().head(8).rename_axis('smell_term').rename('conflicts').reset_index())}

A 20-row sample with the reason per row is in `processed/tasks/ambiguity_arta_conflict_samples.csv`. The split and the exclusion are unchanged.

Conflict rows are excluded from every task file. Cross-source conflicts keep their master rows (flagged `label_conflict`); within-source conflicts are removed from the master and listed only in the conflicts file.

### Exclusion flags in the master

{', '.join(f'{k}: {v}' for k, v in sorted(excl.items()))}. TCS-derived ARTA rows (`tcs_hold`) carry `boundary_status=auto_unverified`.

## Splits

Group-level assignment per source toward 70/15/15 (PROMISE projects P1-P10 follow the dependency task's 7/1/2 project split: {json.dumps(proj_split, sort_keys=True)}),
then any text that appears in train is removed from val and test across the whole pool (train > test > val). `group_id` is kept so PROMISE can also be evaluated leave-one-project-out.

**PROMISE anchoring (a refinement of decision B).** Under pure B every source is assigned independently and PROMISE keeps only
{anchoring['promise_rows_in_val_test_pure_B']} val+test rows, because its copies in PURE (`promisedataALL`), DS3 and FR_NFR fall in train and force the PROMISE
copies out. Here the {anchoring['rows_inheriting_promise_split']} copies of PROMISE texts in other sources inherit the split of their PROMISE project, which keeps
{anchoring['promise_rows_in_val_test_with_anchoring']} PROMISE rows in val+test and lowers the rows removed for text overlap from {anchoring['rows_removed_pure_B']} to {anchoring['rows_removed_with_anchoring']}.
To use pure B instead, remove the anchoring block in `compute()` and regenerate (the build will not overwrite existing outputs).

Rows removed for text overlap, by source:

{md_table(removal)}

Rows below {MIN_WORDS} words dropped from tasks: {len(short)}. Dependency pairs dropped: {dict(dep_stats)}.

### Resulting class counts per split
{distribution_lines(tasks)}

Frozen test ids: `{manifest['frozen_test_ids_sha256']}` (SHA-256 of `frozen_test_ids.csv`, {manifest['frozen_test_ids_rows']} rows).

## Generation seeds and reserved evaluation ids

`synthetic_seed_inputs.csv`: {len(seed_df)} `requirement_text` rows from the **train** split, 6-60 words, labelled FR or NFR, stratified by label and source
(seed {SEED}), with exact normalized-text duplicates and near-identical texts (word Jaccard >= 0.9) excluded. Counts: {', '.join(f'{k}={v}' for k, v in seed_df.groupby('requirement_type').size().items())}; by source: {', '.join(f'{k}={v}' for k, v in seed_df.groupby('source').size().items())}.

`generation_eval_ids.csv`: the ids of {len(eval_df)} **test** requirement rows (6-60 words, stratified by FR/NFR and source, seed {SEED}); the file has a single `id` column and no text.
They are reserved for the final base-vs-fine-tuned comparison and must not be used for prompt tuning, training, seeds or anything else. By label and source: {', '.join(f'{r.requirement_type}/{r.source_dataset}={r.rows}' for r in eval_counts.itertuples())}.
Neither file is in `manifest.json` (the test ids are already covered by `frozen_test_ids.csv`); a test checks that no seed text occurs in any val or test row.

## SRS extraction

{len(srs)} candidate rows from {len(counts)} documents (76 text + 3 HTML). Rules: drop TOC lines, repeated headers/footers, page numbers, headings,
notes/examples and deleted entries; keep sentences with shall/must/should/will/is required to, and numbered/ID-tagged clauses (with or without a modal), so documents
that never say "shall" are handled. `candidate_type` is FR/NFR only on a clear cue, else `unknown`. Every row is `boundary_status=auto_unverified`; the TCS document is
additionally on `tcs_manual_review_on_hold`. Per-document counts and suspicious-count flags are in `srs_requirements_per_document_counts.csv`.

## Known caveats

- ARTA DS1-DS4 labels are derived ("defect" = any smell term); the schemas differ between files, so DS1/DS3 disagree on many shared sentences. Those disagreements are listed as conflicts and excluded, not resolved.
- PURE: `NFR_boolean=0` has unconfirmed meaning, so PURE is not used for FR/NFR; reliability has only {int((master.reliability_label == '1').sum())} positives and is marked `too_sparse_to_evaluate` (excluded from subtype metrics).
- PURE is dominated by a few regulatory documents; one of them (`promisedataALL`) contains PROMISE sentences.
- `nfr_labeled`/`test_labeled` lost their commas; `software_extended` has 434 rows of unconfirmed provenance (excluded).
- Some source texts contain unrecoverable corruption (for example `â€?`, U+FFFD); originals are untouched and the affected rows carry `encoding_fix_applied`.
- Trace matrices: meaning of 0/1 unconfirmed; requirement text is joined from ARFF comment lines assuming R/NFR numbers equal comment indexes (`text_join_status=inferred_unverified`).
- Cornelius is templated, low-diversity data: pipeline test only. `basic`, `context`, `context_role` need review and are excluded.
- SRS rows are unverified candidates, not a labelled dataset.
- `SmellyWordsDictionary.xlsx` and `brown.csv` were removed from `raw/` on purpose and are intentionally excluded: no build script, baseline or test reads them. The ambiguity rule baseline uses only the QuRE weak words.

## Licences

PURE: CC BY 4.0. PROMISE trace matrices: CC BY-SA 3.0. All other sources: unconfirmed (`license_note=unconfirmed`).
"""


if __name__ == "__main__":
    main()
