"""Schema and validation for the optional Part B generation output.

pydantic is not a dependency of this project, so the schema is a plain JSON-Schema dict (`OUTPUT_SCHEMA`, documentation and tooling) and
`validate_output` is the check the code actually uses. A model reply is valid when, after taking the text from the first "{" to the last "}":
  status "ok"                 user_story matches ^As an? .+, I want .+, so that .+\\.?$ ; technical_task and rationale are non-empty strings;
                              acceptance_criteria is a list of 2 to 6 strings, each "Given ... when ... then ..." (case-insensitive)
  status "needs_clarification"  clarification_questions is a non-empty list of non-empty strings; rationale is a non-empty string
Extra keys are ignored.
"""
import json
import re

STORY_RE = re.compile(r"^As an? .+, I want .+, so that .+\.?$")
GWT_RE = re.compile(r"^\s*given\b.+\bwhen\b.+\bthen\b.+", re.IGNORECASE | re.DOTALL)
MIN_CRITERIA, MAX_CRITERIA = 2, 6
STATUSES = ("ok", "needs_clarification")

OUTPUT_SCHEMA = {
    "oneOf": [
        {
            "type": "object",
            "required": ["status", "user_story", "technical_task", "acceptance_criteria", "rationale"],
            "properties": {
                "status": {"const": "ok"},
                "user_story": {"type": "string", "pattern": STORY_RE.pattern},
                "technical_task": {"type": "string", "minLength": 1},
                "acceptance_criteria": {"type": "array", "minItems": MIN_CRITERIA, "maxItems": MAX_CRITERIA,
                                        "items": {"type": "string", "pattern": "(?i)^\\s*given\\b.+\\bwhen\\b.+\\bthen\\b.+"}},
                "rationale": {"type": "string", "minLength": 1},
            },
        },
        {
            "type": "object",
            "required": ["status", "clarification_questions", "rationale"],
            "properties": {
                "status": {"const": "needs_clarification"},
                "clarification_questions": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                "rationale": {"type": "string", "minLength": 1},
            },
        },
    ]
}


def extract_json(raw):
    """Parse the JSON object between the first "{" and the last "}" of a reply. Returns (dict or None, error text)."""
    if not isinstance(raw, str):
        return None, "reply is not text"
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None, "no JSON object found"
    try:
        value = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc.msg}"
    if not isinstance(value, dict):
        return None, "JSON is not an object"
    return value, ""


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_output(obj):
    """List of problems with a parsed reply (empty list = valid)."""
    problems = []
    status = obj.get("status")
    if status not in STATUSES:
        return [f"status must be one of {list(STATUSES)}, got {status!r}"]
    if not _text(obj.get("rationale")):
        problems.append("rationale missing or empty")
    if status == "ok":
        story = obj.get("user_story")
        if not _text(story) or not STORY_RE.match(story.strip()):
            problems.append("user_story does not match 'As a ..., I want ..., so that ...'")
        if not _text(obj.get("technical_task")):
            problems.append("technical_task missing or empty")
        crit = obj.get("acceptance_criteria")
        if not isinstance(crit, list) or not MIN_CRITERIA <= len(crit) <= MAX_CRITERIA:
            problems.append(f"acceptance_criteria must be a list of {MIN_CRITERIA} to {MAX_CRITERIA} items")
        else:
            for i, c in enumerate(crit, 1):
                if not isinstance(c, str) or not GWT_RE.match(c):
                    problems.append(f"acceptance criterion {i} is not 'Given ... when ... then ...'")
    else:
        q = obj.get("clarification_questions")
        if not isinstance(q, list) or not q or not all(_text(x) for x in q):
            problems.append("clarification_questions must be a non-empty list of non-empty strings")
    return problems
