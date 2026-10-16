# English translations of the Italian CoEST datasets (SMOS, eANCI)

Made for the C4 cross-encoder experiments. **Originals are untouched** (they live in the downloaded zips); these are derived files.

| File | Content |
|---|---|
| `SMOS/requirements_en.json` | 67 use cases, id -> English text (all of SMOS) |
| `eANCI/requirements_en.json` | 39 use cases, id -> English text. Only the 39 that appear in the gold links (`answer_req_code.xml`); the other 101 `uc/` files have no gold link and were not translated. |
| `SMOS/code_en/`, `eANCI/code_en/` | The 100 SMOS and 55 eANCI Java files as UTF-8 copies with the **comments / Javadoc translated** (code and identifiers unchanged). Unique comments are listed in `*/comments_it_en.json` (translated ones have an `en` value; the others are English or commented-out code and were left as is). |
| `glossary_it_en.json` | 430 Italian identifier tokens (class/method/field name parts of SMOS and eANCI code) -> English, for use in `retrieval_text` |
| `requirements_it_cleaned.json` | The Italian source text after cleaning (RTF removed for eANCI), so every translation can be compared with its source |

## How they were made / caveats
- Translated by Claude (an LLM), not by a certified translator. Domain terms were kept literal where there is no English equivalent (e.g. *pratica* = administrative application file, *matricola* = employee number, *ATA staff*).
- Text layout was normalised: stray bullets, broken table layout and RTF markup were removed, "Utente/Sistema" columns were merged into one "Event sequence". Numbering and meaning are kept.
- EA23 is an exact duplicate of EA22 in the source; kept as is.
- Comments: SMOS 807 of 923 comment occurrences and eANCI 376 of 413 were replaced; the rest are English comments or commented-out code. About 19 comment blocks still contain Italian: Javadoc blocks that only hold `@param` / `@return` text (these tags were not translated). `@author` / `@version` tags were kept and moved onto the one-line comment.
- Identifiers inside the Java files are not translated; they are covered only by the glossary (tokens, not full names). Glossary translations are short and may be ambiguous (e.g. `via` = street, `stato` = state/status).
- Cite the original dataset (Gethers et al., ICSM 2011) and say "translated version" when reporting results; they are not directly comparable with published numbers on the Italian originals.
- Have an Italian speaker spot-check a sample before relying on it in the report.
