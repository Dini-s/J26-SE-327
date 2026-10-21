"""Build the Component 1 master requirement table (processed/master_requirements.csv).

Reads (never modifies) raw/ and the already-parsed files in processed/, and writes:
  processed/master_requirements.csv       one row per source record after within-source de-duplication
  processed/master_label_conflicts.csv    same normalized text with conflicting labels (never resolved)

Rules implemented here (see processed/DATA_CARD.md for the full account):
  * original text is kept untouched; normalized text is a separate column;
  * exact duplicates on normalized text WITHIN a source keep one row (count recorded); if the duplicates carry
    conflicting labels none is kept in the master, they are moved to master_label_conflicts.csv;
  * promise.csv is the canonical PROMISE text; NICE flags, nfr_labeled, test_labeled and software_extended copies
    are collapsed into it as cross-check provenance (they do not create new master rows);
  * the same text with conflicting labels across trusted sources is never resolved: the master rows stay, flagged
    with exclusion_reason=label_conflict, and the pair is listed in master_label_conflicts.csv;
  * unknown labels stay empty; no synthetic data; TCS-derived rows are held (boundary_status=auto_unverified);
  * pure_subset.csv is decoded line by line (UTF-8 first, cp1252 fallback) because the file mixes both encodings.

Deterministic and idempotent: re-running reproduces byte-identical files. An existing output that differs from what
would be written stops the script (outputs are never overwritten).

Run from the project directory:   ..\\.venv\\Scripts\\python.exe experiments\\component1\\build_master.py
"""
import codecs
import csv
import hashlib
import json
import re
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPONENT = PROJECT_ROOT / "data" / "component1"
RAW = COMPONENT / "raw"
PROCESSED = COMPONENT / "processed"
AUDIT = COMPONENT / "audit_reports_component1"
OUT_MASTER = PROCESSED / "master_requirements.csv"
OUT_CONFLICTS = PROCESSED / "master_label_conflicts.csv"

MIN_WORDS = 6  # texts shorter than this are never used as cross-dataset links and never enter task files

MASTER_COLUMNS = [
    "record_id", "source_dataset", "source_file", "source_record_id", "source_project_or_document", "group_id",
    "text_type", "requirement_text_original", "requirement_text_normalized", "text_key", "word_count",
    "requirement_type", "nfr_subtype", "nfr_subtype_scheme", "ambiguity_label", "ambiguity_label_basis",
    "security_label", "reliability_label", "review_status", "exclusion_reason", "label_conflict_dimensions",
    "boundary_status", "is_synthetic", "license_note", "provenance", "source_label_raw", "crosscheck_labels",
    "also_in_sources", "dup_count_in_source", "encoding_fix_applied",
]
CONFLICT_COLUMNS = ["conflict_id", "dimension", "scope", "text_key", "example_text", "labels_by_source", "n_records",
                    "source_datasets", "source_record_ids", "master_record_ids", "excluded_from"]


# ----------------------------------------------------------------------------- text helpers
def collapse(value):
    return re.sub(r"\s+", " ", str(value).replace(" ", " ")).strip()


_MOJIBAKE = re.compile("[\u00c3\u00c2\u00e2][\u0080-\u00bf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc"
                       "\u2013\u2014\u2018-\u201e\u2020-\u2022\u2026\u2030\u2039\u203a\u20ac\u2122]{1,2}")


def repair_mojibake(text):
    """Repair UTF-8-read-as-cp1252 sequences (e.g. 'Â§', 'â€™'). Used for the normalized column only."""
    def fix(match):
        try:
            return match.group(0).encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return match.group(0)
    fixed = _MOJIBAKE.sub(fix, text)
    return fixed, fixed != text


_OUTER_QUOTES = re.compile(r"^(['\"“‘`]+)(.*?)(['\"”’`]+)$", re.S)


def normalize_text(value):
    """Lower-case, whitespace-collapsed text with matching outer quotes removed (punctuation kept)."""
    text = repair_mojibake(collapse(value))[0]
    match = _OUTER_QUOTES.match(text)
    if match:
        text = match.group(2).strip()
    return text.lower()


def text_key(normalized):
    return re.sub(r"[^a-z0-9]", "", normalized)


def word_count(normalized):
    return len(normalized.split())


def record_id(source, file, rid):
    return f"{source}:{hashlib.sha1(f'{file}|{rid}'.encode('utf-8')).hexdigest()[:10]}"


def to_bytes(df):
    return df.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")


def write_safe(path, df):
    """Write only if the file does not exist; an identical existing file is left alone; a different one stops the run."""
    data = to_bytes(df)
    path = Path(path)
    if path.exists():
        if path.read_bytes() == data:
            print(f"unchanged: {path.name}")
            return "unchanged"
        raise SystemExit(f"STOP: {path} already exists and differs from what would be written. Not overwriting; ask the owner.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"written:   {path.name} ({len(df)} rows)")
    return "written"


# ----------------------------------------------------------------------------- loaders
def _utf8_then_cp1252(error):
    """Decode only the invalid bytes as cp1252; valid UTF-8 sequences on the same line stay UTF-8."""
    return error.object[error.start:error.end].decode("cp1252", errors="replace"), error.end


codecs.register_error("utf8_then_cp1252", _utf8_then_cp1252)


def read_pure_lines(path):
    """Decode pure_subset.csv line by line: valid UTF-8 sequences stay UTF-8, stray bytes fall back to cp1252.
    Returns (rows, fallback_flags_per_row)."""
    flags = []

    def lines():
        for chunk in Path(path).read_bytes().split(b"\n"):
            try:
                text, used = chunk.decode("utf-8"), False
            except UnicodeDecodeError:
                text, used = chunk.decode("utf-8", errors="utf8_then_cp1252"), True
            flags.append(used)
            yield text + "\n"

    reader = csv.reader(lines())
    header = next(reader)
    rows, row_flags, previous = [], [], reader.line_num
    for record in reader:
        if not record:
            previous = reader.line_num
            continue
        rows.append(dict(zip(header, record)))
        row_flags.append(any(flags[previous:reader.line_num]))
        previous = reader.line_num
    return rows, row_flags


def read_csv_text(path):
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def load_inputs():
    """Return one list of dicts per input file. Fields not applicable to a source stay ''."""
    inputs = {}

    def base(source, file, rid, project, text, **extra):
        row = {"source_dataset": source, "source_file": file, "source_record_id": str(rid),
               "project_doc": project, "text": text if isinstance(text, str) else "", "requirement_type": "",
               "nfr_subtype": "", "nfr_subtype_scheme": "", "ambiguity_label": "", "ambiguity_label_basis": "",
               "security_label": "", "reliability_label": "", "review_status": "ok", "exclusion_reason": [],
               "boundary_status": "", "text_type": "requirement", "license_note": "unconfirmed",
               "source_label_raw": "", "sig": "", "encoding_fix": [], "role": "primary"}
        row.update(extra)
        return row

    # --- PROMISE family
    nice = read_csv_text(RAW / "PROMISE-relabeled-NICE.csv")
    classes = [c for c in nice.columns if c not in ("ProjectID", "RequirementText", "IsFunctional", "IsQuality")]
    codes = {c: re.search(r"\((\w+)\)$", c).group(1) for c in classes}
    rows = []
    for i, (_, r) in enumerate(nice.iterrows(), start=1):
        flags = {codes[c]: r[c] for c in classes}
        positive = [code for code, v in flags.items() if v == "1" and code != "OT"]
        is_f, is_q = r["IsFunctional"], r["IsQuality"]
        rtype = "FR" if (is_f, is_q) == ("1", "0") else "NFR" if (is_f, is_q) == ("0", "1") else ""
        row = base("PROMISE_NICE", "PROMISE-relabeled-NICE.csv", i, f"PROMISE_P{r['ProjectID']}", r["RequirementText"],
                   requirement_type=rtype, nfr_subtype="|".join(positive), nfr_subtype_scheme="PROMISE_NICE_11",
                   security_label=flags.get("SE", ""), role="promise_family_nice",
                   source_label_raw=f"IsFunctional={is_f};IsQuality={is_q};" + ";".join(f"{k}={v}" for k, v in flags.items() if v == "1"))
        row["sig"] = json.dumps([is_f, is_q, flags], sort_keys=True)
        if rtype == "":
            row["review_status"] = "type_flags_both_or_none"
        rows.append(row)
    inputs["PROMISE-relabeled-NICE.csv"] = rows

    promise = read_csv_text(RAW / "promise.csv")
    rows = []
    for i, r in enumerate(promise.itertuples(index=False), start=1):
        rtype = {"functional": "FR", "non-functional": "NFR"}.get(r.label, "")
        row = base("PROMISE", "promise.csv", i, "", r.requirement, requirement_type=rtype, source_label_raw=r.label,
                   role="promise_canonical")
        row["sig"] = r.label
        rows.append(row)
    inputs["promise.csv"] = rows

    mapping = read_csv_text(PROCESSED / "nfr_label_mapping.csv")
    meaning = dict(zip(mapping.original_label, mapping.proposed_meaning))
    for fname, source in (("nfr_labeled_parsed.csv", "nfr_labeled"), ("test_labeled_parsed.csv", "test_labeled")):
        df = read_csv_text(PROCESSED / fname)
        rows = []
        for r in df.itertuples(index=False):
            code = r.label
            row = base(source, fname, r.source_line, "", r.requirement, source_label_raw=code, role="promise_derivative",
                       requirement_type=("FR" if code == "F" else "NFR" if code in meaning else ""),
                       nfr_subtype=("" if code == "F" else code), nfr_subtype_scheme="PROMISE_12_single",
                       security_label=("1" if code == "SE" else ""))
            row["sig"] = code
            rows.append(row)
        inputs[fname] = rows

    sw = read_csv_text(PROCESSED / "software_requirements_extended_normalized.csv")
    rows = []
    for i, r in enumerate(sw.itertuples(index=False), start=1):
        code = r.original_type
        rtype = code if code in ("FR", "NFR") else "FR" if code == "F" else "NFR" if code in meaning else ""
        row = base("software_extended", "software_requirements_extended_normalized.csv", i, "", r.Requirement,
                   source_label_raw=code, role="promise_derivative", requirement_type=rtype,
                   nfr_subtype=(code if code in meaning and code != "F" else ""), nfr_subtype_scheme="PROMISE_12_single",
                   security_label=("1" if code == "SE" else ""))
        row["sig"] = code
        rows.append(row)
    inputs["software_requirements_extended_normalized.csv"] = rows

    # --- FR_NFR
    fr = pd.read_excel(RAW / "FR_NFR_Dataset.xlsx", sheet_name="datasetFR_NFR_full", dtype=str)
    rows = []
    for i, (_, r) in enumerate(fr.iterrows(), start=2):  # Excel row number
        label = r["Type"] if isinstance(r["Type"], str) and r["Type"].strip() in ("FR", "NFR") else ""
        row = base("FR_NFR", "FR_NFR_Dataset.xlsx", i, "", r["Requirement Text"], requirement_type=label,
                   source_label_raw=("" if not isinstance(r["Type"], str) else r["Type"]), group_label="FR_NFR:ungrouped")
        row["sig"] = label
        if label == "":
            row["review_status"] = "label_missing"
        rows.append(row)
    inputs["FR_NFR_Dataset.xlsx"] = rows

    # --- PURE (mixed encodings)
    pure, fallback = read_pure_lines(RAW / "pure_subset.csv")
    rows = []
    for r, fixed in zip(pure, fallback):
        document = re.sub(r"_\d+$", "", r["id"])
        sec, rel, nfr = r["security"], r["reliability"], r["NFR_boolean"]
        row = base("PURE", "pure_subset.csv", r["id"], document, r["sentence"],
                   requirement_type=("NFR" if nfr == "1" else ""), security_label=sec, reliability_label=rel,
                   nfr_subtype_scheme="PURE_security_reliability", license_note="CC BY 4.0",
                   source_label_raw=f"NFR_boolean={nfr};security={sec};reliability={rel}",
                   encoding_fix=(["pure_mixed_encoding_decoded"] if fixed else []))
        row["sig"] = (nfr, sec, rel)
        rows.append(row)
    inputs["pure_subset.csv"] = rows

    # --- security_requirements
    sec = read_csv_text(RAW / "security_requirements.csv")
    rows = []
    for i, r in enumerate(sec.itertuples(index=False), start=1):
        label = {"sec": "1", "nonsec": "0"}.get(r.contains_sec, "")
        row = base("security_requirements", "security_requirements.csv", i, "", r.requirement, security_label=label,
                   source_label_raw=r.contains_sec, nfr_subtype_scheme="SECURITY_BINARY")
        row["sig"] = label
        if label == "":
            row["review_status"] = "stray_label_value"
        rows.append(row)
    inputs["security_requirements.csv"] = rows

    # --- QuRE
    qure = read_csv_text(RAW / "QuRE.csv")
    rows = []
    for r in qure.itertuples(index=False):
        label = r.defect if r.defect in ("defect", "ok") else ""
        row = base("QuRE", "QuRE.csv", r.id, "", r.requirement, ambiguity_label=label, ambiguity_label_basis="QuRE_defect",
                   source_label_raw=f"defect={r.defect};weak_word={r.weak_word}")
        row["sig"] = label
        rows.append(row)
    inputs["QuRE.csv"] = rows

    # --- ARTA DS1-DS4: label derived from the smell columns
    tcs_hold = []
    for name in ("DS1", "DS2", "DS3", "DS4"):
        df = pd.read_excel(RAW / f"{name}.xlsx", dtype=str)
        text_col, file_col, smell_cols = df.columns[0], df.columns[1], list(df.columns[2:])
        rows = []
        for i, (_, r) in enumerate(df.iterrows(), start=2):
            smells, unknown = [], False
            for c in smell_cols:
                v = r[c]
                if not isinstance(v, str) or v.strip() == "":
                    unknown = True
                elif v.strip() != "-":
                    smells.append(f"{c}={v.strip()}")
            label = "defect" if smells else ("" if unknown else "ok")
            doc = str(r[file_col])
            row = base(name, f"{name}.xlsx", i, doc, r[text_col], ambiguity_label=label,
                       ambiguity_label_basis=f"ARTA_{name}_any_smell_term", source_label_raw=";".join(smells) or "-",
                       group_label=f"ARTA:{name}:{doc}")
            row["sig"] = label
            if "tcs" in doc.lower():
                row["exclusion_reason"].append("tcs_hold")
                row["boundary_status"] = "auto_unverified"
            if label == "":
                row["review_status"] = "label_unknown"
            rows.append(row)
        inputs[f"{name}.xlsx"] = rows

    # --- user stories and Cornelius
    us = read_csv_text(RAW / "user_stories.csv")
    rows = []
    for r in us.itertuples(index=False):
        row = base("user_stories", "user_stories.csv", f"{r.source_file}:{r.line_number}", r.source_file, r.requirement,
                   text_type="user_story", group_label=f"US:{r.source_file}", review_status="reference_user_story")
        row["sig"] = ""
        rows.append(row)
    inputs["user_stories.csv"] = rows

    cor = read_csv_text(PROCESSED / "cornelius_conflict_free_unique.csv")
    rows = []
    for r in cor.itertuples(index=False):
        label = {"True": "defect", "False": "ok"}.get(r.HasAmbiguity, "")
        row = base("Cornelius", "cornelius_conflict_free_unique.csv", r.StoryID, f"{r.CompanyID}-{r.ProjectID}", r.StoryText,
                   text_type="user_story", ambiguity_label=label, ambiguity_label_basis="Cornelius_HasAmbiguity",
                   group_label=f"Cornelius:{r.CompanyID}-{r.ProjectID}", review_status="pipeline_test_only",
                   source_label_raw=f"HasAmbiguity={r.HasAmbiguity}")
        row["exclusion_reason"].append("pipeline_test_only")
        row["sig"] = label
        rows.append(row)
    inputs["cornelius_conflict_free_unique.csv"] = rows

    for name in ("basic", "context", "context_role"):
        df = read_csv_text(RAW / f"{name}.csv")
        rows = []
        for i, r in enumerate(df.itertuples(index=False), start=1):
            row = base(name, f"{name}.csv", i, "", r.requirement, review_status="needs_review",
                       group_label=f"{name}:ungrouped")
            row["exclusion_reason"].append("needs_review")
            row["sig"] = ""
            rows.append(row)
        inputs[f"{name}.csv"] = rows
    return inputs


# ----------------------------------------------------------------------------- build
def build():
    inputs = load_inputs()
    for rows in inputs.values():
        for r in rows:
            r["normalized"] = normalize_text(r["text"])
            r["key"] = text_key(r["normalized"])
            r["words"] = word_count(r["normalized"])
            r["fate"] = "master"
            if repair_mojibake(collapse(r["text"]))[1]:
                r["encoding_fix"] = r["encoding_fix"] + ["normalized_mojibake_repair"]
            if "\ufffd" in r["text"]:
                r["encoding_fix"] = r["encoding_fix"] + ["source_contains_U+FFFD"]

    fate_counts = defaultdict(Counter)  # input_file -> fate counter
    conflicts = []  # dicts

    # 1. drop empty texts
    for fname, rows in inputs.items():
        for r in rows:
            if r["key"] == "":
                r["fate"] = "dropped_empty"

    # 2. within-source de-duplication on normalized text
    within_conflict_keys = defaultdict(set)  # key -> {source}
    for fname, rows in inputs.items():
        by_norm = defaultdict(list)
        for r in rows:
            if r["fate"] == "master":
                by_norm[(r["source_dataset"], r["normalized"])].append(r)
        for (source, norm), group in by_norm.items():
            if len(group) == 1:
                group[0]["dup_count"] = 1
                continue
            sigs = {json.dumps(g["sig"], default=str) for g in group}
            if len(sigs) == 1:
                group[0]["dup_count"] = len(group)
                for g in group[1:]:
                    g["fate"] = "dup_dropped"
            else:
                for g in group:
                    g["fate"] = "conflict_moved"
                conflicts.append({
                    "dimension": "within_source_duplicate_labels", "scope": "within_source", "text_key": group[0]["key"],
                    "example_text": group[0]["normalized"], "n_records": len(group), "source_datasets": source,
                    "labels_by_source": "; ".join(f"{source}[{g['source_record_id']}]={g['source_label_raw'] or g['sig']}" for g in group),
                    "source_record_ids": ";".join(g["source_record_id"] for g in group), "master_record_ids": "",
                    "excluded_from": "all_tasks", "_min_words": group[0]["words"]})
                within_conflict_keys[group[0]["key"]].add(source)

    # 3. PROMISE family: promise.csv is canonical; copies collapse into it
    canon = {r["key"]: r for r in inputs["promise.csv"] if r["fate"] == "master"}
    nice_by_key = {r["key"]: r for r in inputs["PROMISE-relabeled-NICE.csv"] if r["fate"] == "master"}
    project_by_key = {k: r["project_doc"] for k, r in nice_by_key.items()}
    for r in inputs["promise.csv"]:
        r["project_doc"] = project_by_key.get(r["key"], "PROMISE_unknown")
        r["group_label"] = r["project_doc"]
        r["crosscheck"], r["also_in"] = [], []
    for key, n in nice_by_key.items():
        if key in canon:
            n["fate"] = "collapsed"
            c = canon[key]
            c["also_in"].append("PROMISE_NICE")
            c["crosscheck"].append(f"NICE[{n['source_label_raw']}]")
            c["nice"] = n
            c["nfr_subtype"], c["nfr_subtype_scheme"] = n["nfr_subtype"], "PROMISE_NICE_11"
            c["security_label"] = n["security_label"]
        else:
            n["group_label"] = n["project_doc"]
            n["crosscheck"], n["also_in"] = [], []
    family_keys = set(canon) | {k for k, n in nice_by_key.items() if n["fate"] == "master"}
    derivative_obs = []  # (key, source_tag, requirement_type, security)
    for fname in ("nfr_labeled_parsed.csv", "test_labeled_parsed.csv", "software_requirements_extended_normalized.csv"):
        for r in inputs[fname]:
            if r["fate"] != "master":
                continue
            if r["key"] in family_keys:
                r["fate"] = "collapsed"
                target = canon.get(r["key"]) or nice_by_key.get(r["key"])
                target["also_in"].append(r["source_dataset"])
                target["crosscheck"].append(f"{r['source_dataset']}[{r['source_label_raw']}]")
                derivative_obs.append((r["key"], r["source_dataset"], r["requirement_type"], r["security_label"], r["words"],
                                       r["nfr_subtype"]))
                if not target["nfr_subtype"] and r["nfr_subtype"]:
                    target["nfr_subtype"], target["nfr_subtype_scheme"] = r["nfr_subtype"], "PROMISE_12_single"
                if target.get("security_label", "") == "" and r["security_label"] == "1":
                    target["security_label"] = "1"
            else:
                r["group_label"] = f"{r['source_dataset']}:ungrouped"
                r["crosscheck"], r["also_in"] = [], []
                if r["source_dataset"] == "software_extended":
                    r["review_status"] = "provenance_unconfirmed"
                    r["exclusion_reason"].append("provenance_unconfirmed")
                else:
                    r["review_status"] = "commas_stripped_promise_copy"

    # 4. every other source: ensure group_label / crosscheck / also_in exist
    for rows in inputs.values():
        for r in rows:
            r.setdefault("group_label", f"{r['source_dataset']}:{r['project_doc']}" if r["project_doc"] else f"{r['source_dataset']}:ungrouped")
            r.setdefault("crosscheck", [])
            r.setdefault("also_in", [])
            r.setdefault("dup_count", 1)

    # 5. master rows
    master_rows = []
    for fname, rows in inputs.items():
        for r in rows:
            if r["fate"] != "master":
                continue
            master_rows.append(r)
    master = pd.DataFrame([{
        "record_id": record_id(r["source_dataset"], r["source_file"], r["source_record_id"]),
        "source_dataset": r["source_dataset"], "source_file": r["source_file"], "source_record_id": r["source_record_id"],
        "source_project_or_document": r["project_doc"], "group_id": r["group_label"], "text_type": r["text_type"],
        "requirement_text_original": r["text"], "requirement_text_normalized": r["normalized"], "text_key": r["key"],
        "word_count": r["words"], "requirement_type": r["requirement_type"], "nfr_subtype": r["nfr_subtype"],
        "nfr_subtype_scheme": r["nfr_subtype_scheme"], "ambiguity_label": r["ambiguity_label"],
        "ambiguity_label_basis": r["ambiguity_label_basis"], "security_label": r["security_label"],
        "reliability_label": r["reliability_label"], "review_status": r["review_status"],
        "exclusion_reason": "|".join(r["exclusion_reason"]), "label_conflict_dimensions": "",
        "boundary_status": r["boundary_status"], "is_synthetic": False, "license_note": r["license_note"],
        "provenance": f"{r['source_file']}#{r['source_record_id']}", "source_label_raw": r["source_label_raw"],
        "crosscheck_labels": "; ".join(r["crosscheck"]), "also_in_sources": ";".join(sorted(set(r["also_in"]))),
        "dup_count_in_source": r["dup_count"], "encoding_fix_applied": "|".join(r["encoding_fix"]),
        "_role": r["role"], "_rtype_nice": r.get("nice", {}).get("requirement_type", ""),
    } for r in master_rows])
    assert master.record_id.is_unique, "record_id collision"

    # 6. cross-source label conflicts on trusted sources (texts of >= MIN_WORDS words)
    obs = defaultdict(lambda: defaultdict(set))  # (key, dim) -> source_tag -> values
    srcs = defaultdict(set)

    def observe(key, dim, tag, value, words):
        if value != "" and words >= MIN_WORDS:
            obs[(key, dim)][tag].add(value)

    for r in master_rows:
        if "provenance_unconfirmed" in r["exclusion_reason"] or "needs_review" in r["exclusion_reason"] or r["source_dataset"] == "Cornelius":
            continue
        tag = r["source_dataset"]
        observe(r["key"], "requirement_type", tag if tag != "PROMISE_NICE" else "NICE", r["requirement_type"], r["words"])
        observe(r["key"], "security_label", tag if tag not in ("PROMISE",) else "NICE", r["security_label"], r["words"])
        if tag == "PROMISE" and r.get("nice"):
            n = r["nice"]
            observe(r["key"], "requirement_type", "NICE", n["requirement_type"], r["words"])
        if r["ambiguity_label"] and r["source_dataset"].startswith("DS"):
            observe(r["key"], "ambiguity_label[ARTA]", tag, r["ambiguity_label"], r["words"])
        elif r["ambiguity_label"]:
            observe(r["key"], f"ambiguity_label[{tag}]", tag, r["ambiguity_label"], r["words"])
    subtype_conflicts = []
    for key, tag, rtype, sec, words, subtype in derivative_obs:
        observe(key, "requirement_type", tag, rtype, words)
        observe(key, "security_label", tag, sec, words)
        nice_row = canon.get(key, {}).get("nice") or nice_by_key.get(key)
        if subtype and nice_row is not None and words >= MIN_WORDS:
            positive = set(filter(None, nice_row["nfr_subtype"].split("|")))
            if subtype not in positive:
                subtype_conflicts.append((key, tag, subtype, nice_row["nfr_subtype"] or "none"))
    # PURE requirement_type only counts when NFR (=1): handled by value above ('' when 0)
    # PROMISE canonical security comes from NICE (already tagged NICE); drop the duplicate PROMISE tag
    rows_by_key = defaultdict(list)
    for i, row in master.iterrows():
        rows_by_key[row.text_key].append(i)
    conflicted = defaultdict(set)
    for (key, dim), by_tag in sorted(obs.items()):
        values = {v for vs in by_tag.values() for v in vs}
        if len(by_tag) >= 2 and len(values) > 1:
            idxs = rows_by_key.get(key, [])
            conflicts.append({
                "dimension": dim, "scope": "cross_source", "text_key": key,
                "example_text": master.loc[idxs[0], "requirement_text_normalized"] if idxs else "",
                "n_records": len(idxs), "source_datasets": ";".join(sorted({master.loc[i, "source_dataset"] for i in idxs})),
                "labels_by_source": "; ".join(f"{t}={'/'.join(sorted(v))}" for t, v in sorted(by_tag.items())),
                "source_record_ids": ";".join(master.loc[i, "source_record_id"] for i in idxs),
                "master_record_ids": ";".join(master.loc[i, "record_id"] for i in idxs),
                "excluded_from": "all_tasks", "_min_words": MIN_WORDS})
            for i in idxs:
                conflicted[i].add(dim)
    for key, tag, code, nice_codes in subtype_conflicts:
        idxs = rows_by_key.get(key, [])
        conflicts.append({
            "dimension": "nfr_subtype", "scope": "cross_source", "text_key": key,
            "example_text": master.loc[idxs[0], "requirement_text_normalized"] if idxs else "",
            "n_records": len(idxs), "source_datasets": ";".join(sorted({master.loc[i, "source_dataset"] for i in idxs})),
            "labels_by_source": f"NICE={nice_codes}; {tag}={code}",
            "source_record_ids": ";".join(master.loc[i, "source_record_id"] for i in idxs),
            "master_record_ids": ";".join(master.loc[i, "record_id"] for i in idxs),
            "excluded_from": "all_tasks", "_min_words": MIN_WORDS})
        for i in idxs:
            conflicted[i].add("nfr_subtype")
    for key, sources in within_conflict_keys.items():
        for i in rows_by_key.get(key, []):
            conflicted[i].add("within_source:" + "|".join(sorted(sources)))
    for i, dims in conflicted.items():
        master.loc[i, "label_conflict_dimensions"] = "|".join(sorted(dims))
        existing = [x for x in master.loc[i, "exclusion_reason"].split("|") if x]
        master.loc[i, "exclusion_reason"] = "|".join(existing + ["label_conflict"])
    conflicts_df = pd.DataFrame(conflicts)
    if len(conflicts_df):
        conflicts_df = conflicts_df.sort_values(["scope", "dimension", "text_key"]).reset_index(drop=True)
        conflicts_df.insert(0, "conflict_id", [f"C{n:05d}" for n in range(1, len(conflicts_df) + 1)])
        # master_record_ids for within-source conflicts: rows removed from master, so none
    else:
        conflicts_df = pd.DataFrame(columns=CONFLICT_COLUMNS)
    conflicts_df = conflicts_df[CONFLICT_COLUMNS]

    # 7. report rows (per input file)
    report = []
    role_note = {"promise.csv": "canonical PROMISE text", "PROMISE-relabeled-NICE.csv": "second label set (flags) for PROMISE",
                 "nfr_labeled_parsed.csv": "PROMISE copy (commas stripped)", "test_labeled_parsed.csv": "PROMISE copy (commas stripped)",
                 "software_requirements_extended_normalized.csv": "PROMISE copy + 421 provenance-unconfirmed rows"}
    master_by_file = master.groupby("source_file").size().to_dict()
    for fname, rows in inputs.items():
        c = Counter(r["fate"] for r in rows)
        out_rows = [r for r in rows if r["fate"] == "master"]
        report.append({
            "input_file": fname, "stage": "master", "note": role_note.get(fname, ""), "rows_in": len(rows),
            "rows_dropped_empty": c["dropped_empty"], "rows_dropped_duplicates": c["dup_dropped"],
            "rows_moved_to_conflicts": c["conflict_moved"], "rows_collapsed_into_canonical": c["collapsed"],
            "rows_missing_label_kept": sum(1 for r in out_rows if r["review_status"] in ("label_missing", "label_unknown", "stray_label_value")),
            "rows_out": len(out_rows)})
    return master, conflicts_df, report, inputs


def clean_master(master):
    out = master[MASTER_COLUMNS].copy()
    out["is_synthetic"] = out["is_synthetic"].astype(str)
    return out.sort_values(["source_dataset", "source_file", "record_id"], kind="stable").reset_index(drop=True)


def main():
    master, conflicts, report, _ = build()
    master = clean_master(master)
    write_safe(OUT_MASTER, master)
    write_safe(OUT_CONFLICTS, conflicts)
    print(master.groupby("source_dataset").size().to_string())
    print("conflicts:", len(conflicts), dict(Counter(conflicts.scope + ":" + conflicts.dimension)))
    print("excluded:", dict(Counter(x for v in master.exclusion_reason for x in v.split("|") if x)))


if __name__ == "__main__":
    main()
