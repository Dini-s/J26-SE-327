"""Third batch of synthetic-generation seed inputs for Component 1 (no model calls, no LLM).

Reads (never modifies): processed/master_requirements.csv, processed/tasks/{generation_inputs, synthetic_seed_inputs, synthetic_seed_inputs_batch2,
frozen_test_ids, generation_eval_ids, generation_eval_inputs, classification_*, ambiguity, dependency_pairs}.csv and writes NEW files (never
overwritten if different):
  processed/tasks/synthetic_seed_inputs_batch3.csv          id, source, requirement_text          (~2,300 rows)
  processed/tasks/synthetic_seed_inputs_batch3_raw.csv      id, requirement_text_raw              (only rows whose text was cleaned)
  processed/tasks/synthetic_seed_inputs_batch3_report.md    counts per source and rows removed per filter

Pool: `requirement_text` rows of generation_inputs.csv with split == train that are in the master. Never used: the 550 seeds of batches 1-2, any
frozen-test id, any generation_eval id. Cleaning (original kept in the raw sidecar): `\\%` -> `%`, `[SRS024]`-style markers, inline clause numbers
such as (3.1.1), leading section numbers, trailing stray quotes (`',`), repeated spaces. Filters: 6-60 words, ends like a sentence, extraction-noise
and placeholder/garbled checks, same normalized text as any seed / val / test / eval text, MiniLM cosine > 0.90 to an existing seed or to another
selected seed, cosine >= 0.85 to ANY test text or any of the 100 eval inputs (test texts are only embedded in memory for this guard).
Stratified by source like batches 1-2 where the pool allows (PROMISE is nearly exhausted: all clean PROMISE rows are taken).
Deterministic (seed 327).

Run from the project directory:  ..\\.venv\\Scripts\\python.exe experiments\\component1\\build_synthetic_seed_batch3.py
"""
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from build_master import PROCESSED, write_safe  # noqa: E402
from build_synthetic_seed_batch2 import (ends_like_sentence, h, held_out_texts, key, max_cosine, noise_reason,  # noqa: E402
                                         source_group, vague_flag)
from agents.requirement_agent.features import SEED, embed, normalize_for_models  # noqa: E402

TASKS = PROCESSED / "tasks"
OUT = TASKS / "synthetic_seed_inputs_batch3.csv"
OUT_RAW = TASKS / "synthetic_seed_inputs_batch3_raw.csv"
OUT_REPORT = TASKS / "synthetic_seed_inputs_batch3_report.md"
TARGET = 2300
SEED_DUP_COSINE = 0.90
TEST_COSINE = 0.85
VAGUE_SHARE = 0.18
# (label, group) -> desired quota; shortfalls are redistributed (see build)
QUOTAS = {("FR", "FR_NFR"): 560, ("NFR", "FR_NFR"): 560, ("NFR", "PROMISE"): 80, ("FR", "PROMISE"): 60, ("NFR", "PURE"): 330,
          ("", "DS4"): 230, ("", "QuRE"): 230, ("", "other"): 50}

PLACEHOLDER = re.compile(r"(?:\btbd\b|\btbc\b|\bto be (?:determined|defined|decided)\b|<[^>]{1,30}>|\[(?:insert|todo|tbd)[^\]]*\]|\blorem ipsum\b|\bxxx+\b|"
                         r"\?{2,}|\bn/a\b|\.{4,}|_{3,})", re.I)


def clean_text(text):
    """Remove extraction artifacts; returns the cleaned text (may equal the input)."""
    t = str(text).replace("\\%", "%")
    t = re.sub(r"\[[A-Z]{2,6}\s?\d{1,6}(?:\s?,\s?[A-Z]{2,6}\s?\d{1,6})*\]", " ", t)           # [SRS024]
    t = re.sub(r"\(\s*\d+(?:\.\d+){1,6}\s*\)", " ", t)                                        # (3.1.1)
    t = re.sub(r"^\s*(?:section\s+)?\d+(?:\.\d+){1,6}\.?\s+(?=[A-Za-z])", "", t, flags=re.I)  # 5.2.2.39 Upon ...
    t = re.sub(r"^\s*\d{1,2}[.)]\s+(?=[A-Z])", "", t)                                         # 3. The system ...
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"(?<=[.!?])[\"'‘’“”`,;]+\s*$", "", t).strip()                    # trailing stray quote after the final period
    return t


def garbled(text):
    letters = sum(c.isalpha() for c in text)
    if len(text) and letters / len(text) < 0.55:
        return "mostly_non_letters"
    if PLACEHOLDER.search(text):
        return "placeholder"
    if re.search(r"(.)\1{5,}", text):
        return "repeated_characters"
    words = text.split()
    if sum(len(w) > 28 for w in words) >= 1 and "http" not in text.lower():
        return "very_long_token"
    return ""


def read(name):
    return pd.read_csv(TASKS / name, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def build():
    gen = read("generation_inputs.csv")
    master_ids = set(pd.read_csv(PROCESSED / "master_requirements.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False, usecols=["record_id"]).record_id)
    existing = pd.concat([read("synthetic_seed_inputs.csv"), read("synthetic_seed_inputs_batch2.csv")])
    frozen_ids, eval_ids = set(read("frozen_test_ids.csv").record_id), set(read("generation_eval_ids.csv").id)
    eval_inputs = read("generation_eval_inputs.csv")
    funnel = []

    pool = gen[(gen.record_type == "requirement_text") & (gen.split == "train") & gen.record_id.isin(master_ids)].copy()
    pool = pool.assign(source=pool.source_dataset, raw=pool.requirement_text_original.str.strip(), group=pool.source_dataset.map(source_group))
    funnel.append(("train requirement_text rows that are in master_requirements.csv", len(pool)))

    def step(label, keep):
        nonlocal pool
        funnel.append((label, int((~keep).sum())))
        pool = pool[keep]

    step("removed: id of an existing seed (batches 1-2), frozen test id or generation_eval id", ~pool.record_id.isin(set(existing.id) | frozen_ids | eval_ids))
    pool = pool.assign(text=pool.raw.map(clean_text))
    funnel.append(("rows whose text was cleaned (artifact removal; kept, not removed)", int((pool.text != pool.raw).sum())))
    wc = pool.text.str.split().str.len()
    step("removed: fewer than 6 or more than 60 words (after cleaning)", (wc >= 6) & (wc <= 60))
    step("removed: empty or does not end like a sentence", pool.text.map(ends_like_sentence))
    g = pool.text.map(garbled)
    for reason in ("mostly_non_letters", "placeholder", "repeated_characters", "very_long_token"):
        funnel.append((f"removed: garbled/placeholder ({reason})", int((g == reason).sum())))
    pool = pool[g == ""]
    noise = pool.text.map(noise_reason)
    for reason in ("page_number", "table_fragment", "all_caps_heading", "url_only", "encoding_noise", "starts_mid_sentence"):
        funnel.append((f"removed: extraction noise ({reason})", int((noise == reason).sum())))
    pool = pool[noise == ""]
    step("removed: unlabeled row of a labelled source (FR_NFR, PROMISE, PURE)", ~((pool.requirement_type == "") & pool.group.isin(["FR_NFR", "PROMISE", "PURE"])))

    test_texts, val_texts = held_out_texts()
    held_keys = {key(t) for t in test_texts} | {key(t) for t in val_texts} | {key(t) for t in eval_inputs.requirement_text} | {key(t) for t in existing.requirement_text}
    pool = pool.assign(nkey=pool.text.map(key))
    step("removed: same normalized text as an existing seed / val / test / eval text", ~pool.nkey.isin(held_keys))
    ordered = pool.assign(_o=pool.record_id.map(lambda r: h("batch3dedupe", r))).sort_values("_o", kind="stable")
    step("removed: same normalized text as another pool row (kept the first by hash order)", ~ordered.duplicated("nkey", keep="first").reindex(pool.index))

    cand = pool.copy()
    emb_c = embed([normalize_for_models(t) for t in cand.text])
    emb_old = embed([normalize_for_models(t) for t in existing.requirement_text])
    test_all = sorted(set(test_texts) | set(eval_inputs.requirement_text))
    emb_test = embed([normalize_for_models(t) for t in test_all])
    cand = cand.assign(cos_old=max_cosine(emb_c, emb_old), cos_test=max_cosine(emb_c, emb_test))
    keep = cand.cos_old <= SEED_DUP_COSINE
    funnel.append((f"removed: cosine > {SEED_DUP_COSINE} to an existing seed (batches 1-2)", int((~keep).sum())))
    cand, emb_c = cand[keep], emb_c[keep.values]
    keep = cand.cos_test < TEST_COSINE
    funnel.append((f"removed: cosine >= {TEST_COSINE} to a test text or an eval input", int((~keep).sum())))
    cand, emb_c = cand[keep], emb_c[keep.values]

    amb = read("ambiguity.csv")
    weak = sorted({p.split("=", 1)[1].strip().lower() for v in amb[(amb.split == "train") & amb.ambiguity_label_basis.str.startswith("QuRE")].smell_evidence
                   for p in v.split(";") if p.startswith("weak_word=")})
    cand = cand.assign(vague=cand.text.map(lambda t: vague_flag(t, weak)),
                       grp2=cand.apply(lambda r: r.source if r.source in ("DS4", "QuRE") else r.group, axis=1))
    funnel.append(("candidates left for the stratified pick", len(cand)))
    avail = {k: int(((cand.requirement_type == k[0]) & (cand.grp2 == k[1])).sum()) if k[0] else int((cand.grp2 == k[1]).sum()) for k in QUOTAS}

    # ---- stratified greedy pick; quotas shrink to what is available, the shortfall is spread over FR_NFR (FR/NFR) and the unlabeled groups
    quotas = dict(QUOTAS)
    for k in quotas:
        quotas[k] = min(quotas[k], avail[k])
    short = TARGET - sum(quotas.values())
    for k in (("FR", "FR_NFR"), ("NFR", "FR_NFR"), ("", "QuRE"), ("", "DS4"), ("", "other"), ("NFR", "PURE")):
        if short <= 0:
            break
        room = avail[k] - quotas[k]
        add = min(room, short)
        quotas[k] += add
        short -= add

    order = cand.assign(_o=cand.record_id.map(lambda r: h("batch3", r))).sort_values("_o", kind="stable")
    pos = {rid: i for i, rid in enumerate(cand.record_id)}
    chosen, chosen_vec, skipped_near = [], [], 0

    def take(frame, n, want_vague):
        nonlocal skipped_near
        got = []
        for r in frame.itertuples():
            if len(got) >= n:
                break
            if bool(r.vague) != want_vague or r.record_id in chosen_set:
                continue
            v = emb_c[pos[r.record_id]]
            if chosen_vec and float(np.max(np.stack(chosen_vec) @ v)) > SEED_DUP_COSINE:
                skipped_near += 1
                continue
            got.append(r.record_id)
            chosen.append(r.record_id)
            chosen_set.add(r.record_id)
            chosen_vec.append(v)
        return got

    chosen_set = set()
    got_by = {}
    for k, quota in quotas.items():
        sub = order[(order.requirement_type == k[0]) & (order.grp2 == k[1])] if k[0] else order[order.grp2 == k[1]]
        n_vague = round(VAGUE_SHARE * quota)
        got = take(sub, n_vague, True)
        got += take(sub, quota - len(got), False)
        if len(got) < quota:
            got += take(sub, quota - len(got), True)
        got_by[k] = len(got)
    # top up to the target from any remaining candidate (hash order), same cosine guard
    if len(chosen) < TARGET:
        take(order, TARGET - len(chosen), False)
    funnel.append((f"skipped during the pick: cosine > {SEED_DUP_COSINE} to an already selected seed", skipped_near))
    sel = cand[cand.record_id.isin(chosen_set)].copy()
    out = pd.DataFrame({"id": sel.record_id, "source": sel.source, "requirement_text": sel.text}).sort_values("id", kind="stable").reset_index(drop=True)
    raw = pd.DataFrame({"id": sel.record_id, "requirement_text_raw": sel.raw})[sel.text.values != sel.raw.values].sort_values("id").reset_index(drop=True)
    ctx = dict(existing=existing, frozen_ids=frozen_ids, eval_ids=eval_ids, emb_sel=emb_c[[pos[r] for r in sel.record_id]], emb_old=emb_old,
               emb_test=emb_test, n_test=len(test_all), avail=avail, quotas=quotas, got_by=got_by, held_keys=held_keys, sel=sel)
    return out, raw, funnel, ctx


def report(out, raw, funnel, ctx):
    em = ctx["emb_sel"]
    sims = em @ em.T
    np.fill_diagonal(sims, 0)
    sel = ctx["sel"].set_index("record_id").loc[out.id]
    lines = ["# Synthetic seed inputs, batch 3: report", "",
             f"File: `processed/tasks/synthetic_seed_inputs_batch3.csv` ({len(out)} rows; target {TARGET}). Seed {SEED}. No model or LLM calls; test texts were embedded "
             "in memory only for the similarity guard and are not printed or written.", "",
             "## Counts per source", "", "| source | rows | FR | NFR | unlabeled |", "|---|---|---|---|---|"]
    for s, n in out.source.value_counts().items():
        t = sel[sel.source == s].requirement_type
        lines.append(f"| {s} | {n} | {int((t == 'FR').sum())} | {int((t == 'NFR').sum())} | {int((t == '').sum())} |")
    lines.append(f"| **all** | {len(out)} | {int((sel.requirement_type == 'FR').sum())} | {int((sel.requirement_type == 'NFR').sum())} | {int((sel.requirement_type == '').sum())} |")
    wc = out.requirement_text.str.split().str.len()
    lines += ["", f"Words per text: min {wc.min()}, median {int(wc.median())}, max {wc.max()}. Rows with a cleaned text (original in `synthetic_seed_inputs_batch3_raw.csv`): {len(raw)}.",
              f"Weak-word / vague / short seeds (so the generator meets needs_clarification cases): {int((sel.vague != '').sum())} ({(sel.vague != '').mean():.0%}).", "",
              "Quotas vs available (label, group): " + "; ".join(f"{k[0] or 'any'}/{k[1]}: wanted {QUOTAS[k]}, available {ctx['avail'][k]}, got {ctx['got_by'][k]}" for k in QUOTAS) +
              ". PROMISE is nearly exhausted by batches 1-2, so it cannot keep its 35 % share; FR_NFR, PURE, DS4 and QuRE make up the difference.", "",
              "## Filter funnel (rows removed by each filter, in order)", "", "| step | rows |", "|---|---|"]
    lines += [f"| {a} | {n} |" for a, n in funnel]
    ids = set(out.id)
    mc_test = float(max_cosine(em, ctx["emb_test"]).max())
    mc_old = float(max_cosine(em, ctx["emb_old"]).max())
    lines += ["", "## Confirmations (computed from the written file)", "",
              f"- ids overlapping frozen_test_ids.csv: **{len(ids & ctx['frozen_ids'])}**",
              f"- ids overlapping generation_eval_ids.csv: **{len(ids & ctx['eval_ids'])}**",
              f"- ids overlapping batches 1-2: **{len(ids & set(ctx['existing'].id))}**",
              f"- texts with the same normalized text as an existing seed / val / test / eval text: **{len({key(t) for t in out.requirement_text} & ctx['held_keys'])}**",
              f"- max cosine of any batch-3 seed to any of the {ctx['n_test']} test/eval texts: **{mc_test:.3f}** (limit {TEST_COSINE}; {'OK' if mc_test < TEST_COSINE else 'VIOLATION'})",
              f"- max cosine to a batch 1-2 seed: {mc_old:.3f} (limit {SEED_DUP_COSINE})",
              f"- max cosine between two batch-3 seeds: {float(sims.max()):.3f} (limit {SEED_DUP_COSINE})"]
    return "\n".join(lines) + "\n"


def main():
    out, raw, funnel, ctx = build()
    if (out.id.isin(ctx["frozen_ids"] | ctx["eval_ids"] | set(ctx["existing"].id))).any():
        raise SystemExit("STOP: a selected id overlaps frozen test / eval / existing seeds")
    text = report(out, raw, funnel, ctx)
    if "VIOLATION" in text or float(re.search(r"between two batch-3 seeds: ([\d.]+)", text).group(1)) > SEED_DUP_COSINE:
        raise SystemExit("STOP: similarity limit violated")
    write_safe(OUT, out)
    write_safe(OUT_RAW, raw)
    if OUT_REPORT.exists() and OUT_REPORT.read_text(encoding="utf-8") != text:
        raise SystemExit(f"STOP: {OUT_REPORT} exists and differs. Not overwriting.")
    OUT_REPORT.write_text(text, encoding="utf-8")
    print(f"batch 3: {len(out)} rows")


if __name__ == "__main__":
    main()
