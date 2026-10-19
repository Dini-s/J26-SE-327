"""Findings and explanation text, built only from the automatic check results of a requirement (weak words, probabilities, duplicate and conflict partners)."""
from . import conflicts


def build_findings(rec):
    """List of {type, message, related} from one requirement record (see analysis.analyse_project for the keys it reads)."""
    out = []
    if rec["ambiguity_label"] == "defect":
        out.append({"type": "ambiguity", "related": [],
                    "message": f"Ambiguity model: `defect` with probability {rec['ambiguity_probability']:.2f}."})
    if rec["weak_words"]:
        out.append({"type": "weak_word", "related": [],
                    "message": "Weak words found (QuRE list): " + ", ".join(rec["weak_words"]) + "."})
    if rec["is_security"]:
        cues = ", ".join(rec["security_cue_words"]) or "security keyword"
        out.append({"type": "security", "related": [], "message": f"Security-related: keyword rule matched {cues}."})
    for d in rec["duplicate_matches"]:
        out.append({"type": "duplicate", "related": [d["id"]],
                    "message": f"Possible duplicate of {d['id']} (cosine {d['similarity']:.3f}, threshold {rec['duplicate_threshold']:.3f})."})
    for c in rec["conflict_matches"]:
        out.append({"type": "conflict", "related": [c["id"]], "message": f"With {c['id']}: {c['reason']}"})
    return out


def build_explanation(rec):
    parts = [f"Classified as {rec['fr_nfr']} (probability of NFR {rec['nfr_probability']:.2f}, embeddings + logistic regression baseline)."]
    parts += [f["message"] for f in rec["findings"]]
    if not rec["findings"]:
        parts.append("No ambiguity, weak word, security, duplicate or conflict finding from the automatic checks.")
    if rec["risk_level"] != "NONE":
        parts.append(f"Risk {rec['risk_level']} (score {rec['risk_score']}; unvalidated heuristic, not a trained model).")
    if rec["conflict_matches"]:
        parts.append(conflicts.LABEL + ".")
    return " ".join(parts)
