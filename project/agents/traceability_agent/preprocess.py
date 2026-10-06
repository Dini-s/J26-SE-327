"""Text preparation for retrieval and LLM prompts.

Source files are poor retrieval input as-is: the first lines are ``package`` /
``import`` boilerplate (a 256-token embedding model never gets past them), and
identifiers like ``addPatientRecord`` share no tokens with prose such as "add a
patient". Requirements and other prose are left untouched.
"""

import re

from shared.schemas.traceability import Artifact

# Language keywords carry no meaning for matching requirements to code.
_CODE_STOPWORDS = frozenset(
    "public private protected static final void class interface enum import package return new this "
    "null true false int long double float char byte short boolean string extends implements throws "
    "throw try catch finally if else for while do switch case break continue default abstract "
    "synchronized instanceof super override".split()
)

_IMPORT_PACKAGE = re.compile(r"^\s*(?:import|package)\s+[^\n]*$", re.MULTILINE)
_JSP_DIRECTIVE = re.compile(r"<%@.*?%>", re.DOTALL)
_JSP_MARKERS = re.compile(r"<%[=!-]?|%>")
_HTML_TAG = re.compile(r"<[a-zA-Z/!][^>]*>")
_LEADING_COMMENT = re.compile(r"\A\s*/\*(?!\*)(.*?)\*/", re.DOTALL)
_LEGAL = re.compile(r"copyright|licen[sc]e", re.IGNORECASE)


def _is_jsp(artifact: Artifact) -> bool:
    return artifact.metadata.get("language") == "jsp" or "<%" in artifact.text[:2000]


def strip_boilerplate(artifact: Artifact) -> str:
    """Remove non-informative boilerplate from code, keeping readable content.

    For code artifacts this drops ``import``/``package`` lines, a leading
    non-Javadoc licence comment, and (for JSP) directives and HTML tag syntax.
    Javadoc and ordinary comments are kept because they contain natural language.
    Non-code artifacts are returned unchanged.

    Args:
        artifact: The artifact to clean.

    Returns:
        The cleaned text (suitable for LLM prompts as well as retrieval).
    """
    if artifact.type != "code":
        return artifact.text
    text = artifact.text
    if _is_jsp(artifact):
        text = _JSP_DIRECTIVE.sub(" ", text)
        text = _HTML_TAG.sub(" ", text)
        text = _JSP_MARKERS.sub(" ", text)
    text = _IMPORT_PACKAGE.sub("", text)
    match = _LEADING_COMMENT.match(text)
    if match and _LEGAL.search(match.group(1)):
        text = text[match.end():]
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_identifiers(text: str) -> str:
    """Break camelCase / snake_case identifiers into lowercase words.

    ``addPatientRecord`` -> ``add patient record``. Digits and punctuation are
    dropped, as are one-letter tokens and language keywords.

    Args:
        text: Source text.

    Returns:
        Space-separated lowercase word tokens.
    """
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    tokens = re.findall(r"[A-Za-z]+", text.replace("_", " "))
    return " ".join(t for t in (t.lower() for t in tokens) if len(t) > 1 and t not in _CODE_STOPWORDS)


def retrieval_text(artifact: Artifact) -> str:
    """Text used for embedding / TF-IDF retrieval.

    Code is stripped of boilerplate and identifier-split; prose is unchanged.
    """
    if artifact.type != "code":
        return artifact.text
    return split_identifiers(strip_boilerplate(artifact))


def llm_text(artifact: Artifact) -> str:
    """Text shown to the LLM verifier: boilerplate removed, otherwise original.

    Removing imports matters because prompts are truncated; otherwise they would
    spend the character budget on import lines.
    """
    return strip_boilerplate(artifact)
