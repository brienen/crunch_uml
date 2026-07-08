"""Per-element LLM translation via Ollama, plus the deterministic checks
that decide when a result is trusted.

One model element (package, class, attribute, …) is translated in a single
``POST /api/chat`` call carrying *all* its translatable fields as one JSON
object. Translating name and definition together is what keeps them
consistent: the definition disambiguates the term, and the chosen term is
guaranteed to be used inside the translated definition. The response format
is enforced with Ollama's ``format`` parameter (a JSON schema over exactly
the element's fields), ``temperature: 0`` and a configurable seed keep it
reproducible.

The prompt carries a compact context header — deliberately *not* the whole
model: model name + definition, package path, the owning class (for
attributes), sibling names as a single line, and the **binding glossary**
(termbank picks and translations fixed by higher levels of the hierarchy).

This module also provides the deterministic quality checks used by the
pipeline's voting design:

* :func:`names_agree` — normalised comparison of two name translations
  (the two-workhorse vote);
* :func:`glossary_violations` — does a translated text actually use the
  binding glossary terms whose source terms occur in the source text?

Identifier casing is reconciled with the existing
:func:`crunch_uml.ollama_translator.reconcile_case`.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import requests

from crunch_uml.ollama_translator import _strip_response, reconcile_case
from crunch_uml.translation.config import TranslationConfig
from crunch_uml.translation.termbank import Candidate

logger = logging.getLogger()

# Fields whose values are identifiers/names: casing is reconciled after
# translation and the "name" field carries the two-workhorse vote.
NAME_FIELDS = ("name", "alias")

# Common terms can have dozens of termbank candidates (IATE lists regional
# variants per member state); a long tail of near-duplicates dilutes the
# prompt. The candidates are already deterministically sorted by (source
# priority, reliability, uri), so the cap keeps the strongest ones.
MAX_PROMPT_CANDIDATES = 8


@dataclass
class Element:
    """One translatable model element: its source fields plus the compact
    context the prompt needs."""

    section: str  # tabelnaam: packages, classes, attributes, ...
    key: str  # GUID van het element
    fields: Dict[str, str] = field(default_factory=dict)  # veld -> bronwaarde
    context: Dict[str, str] = field(default_factory=dict)  # model/package/parent(-definities)/siblings
    candidates: List[Candidate] = field(default_factory=list)  # termbankkandidaten voor de naam


SYSTEM_PROMPT_TEMPLATE = """\
You are a professional translator specialising in technical Dutch government \
data-modelling terminology (GEMMA, RSGB, BAG, BRP, RGBZ, ...). You translate \
fields of one UML model element from {from_language} to {to_language}.

Rules:
- Respond with ONLY a JSON object containing exactly the same keys as the \
input JSON; every value is the translation of the corresponding input value.
- The GLOSSARY is binding official terminology: use those exact translations \
for those terms, both as standalone names and inside definitions.
- When CANDIDATES are listed for the element name, choose the one whose \
meaning matches the element's definition and use it consistently in every \
field.
- Preserve special tokens verbatim: <memo>, #NOTES#..., EAID_... \
identifiers, URLs, line breaks.
- Keep domain acronyms unchanged: BAG, BRP, RSGB, GEMMA, RGBZ, BGT, BRK.
- Identifier casing: for camelCase, PascalCase, snake_case or kebab-case \
values, translate every word and rejoin in the same style \
("aanvangAanwezigheid" -> "startAttendance", "Bouwactiviteit" -> \
"ConstructionActivity", "datum_opname" -> "recording_date").
"""


def _json_schema_for(fields: Sequence[str]) -> Dict:
    """JSON schema forcing the response to contain exactly the element's
    fields, all strings."""
    return {
        "type": "object",
        "properties": {name: {"type": "string"} for name in fields},
        "required": list(fields),
        "additionalProperties": False,
    }


def _context_lines(element: Element) -> List[str]:
    ctx = element.context
    lines = []
    model = ctx.get("model")
    if model:
        model_def = ctx.get("model_definition")
        lines.append(f"- Model: {model}" + (f" — {model_def}" if model_def else ""))
    package = ctx.get("package")
    if package:
        lines.append(f"- Package: {package}")
    parent = ctx.get("parent")
    if parent:
        parent_def = ctx.get("parent_definition")
        lines.append(f"- Belongs to: {parent}" + (f" — {parent_def}" if parent_def else ""))
    siblings = ctx.get("siblings")
    if siblings:
        lines.append(f"- Sibling elements: {siblings}")
    return lines


def build_messages(
    element: Element,
    to_language: str,
    from_language: str,
    glossary: Optional[Dict[str, str]] = None,
) -> List[Dict[str, str]]:
    """Build the chat messages: compact context header, binding glossary,
    termbank candidates, then the source fields as JSON."""
    system = SYSTEM_PROMPT_TEMPLATE.format(from_language=from_language, to_language=to_language)

    parts: List[str] = []
    context_lines = _context_lines(element)
    if context_lines:
        parts.append("Context:\n" + "\n".join(context_lines))

    if glossary:
        glossary_lines = [f"- {src} -> {tgt}" for src, tgt in sorted(glossary.items())]
        parts.append("GLOSSARY (binding):\n" + "\n".join(glossary_lines))

    if element.candidates:
        name = element.fields.get("name", element.key)
        lines = []
        for i, cand in enumerate(element.candidates[:MAX_PROMPT_CANDIDATES], start=1):
            bits = [f"{i}. {cand.term}"]
            if cand.definition:
                bits.append(f"— {cand.definition}")
            meta = [f"source: {cand.source}"]
            if cand.domains:
                meta.append(f"domain: {', '.join(cand.domains)}")
            if cand.reliability is not None:
                meta.append(f"reliability: {cand.reliability}")
            bits.append(f"({'; '.join(meta)})")
            lines.append(" ".join(bits))
        parts.append(f'CANDIDATES for "{name}" (choose the meaning that fits the definition):\n' + "\n".join(lines))

    parts.append(
        f"Translate the values of this JSON object from {from_language} to {to_language}:\n"
        + json.dumps(element.fields, ensure_ascii=False)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def translate_element_once(
    element: Element,
    to_language: str,
    from_language: str,
    model: str,
    config: TranslationConfig,
    glossary: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """One deterministic Ollama call translating all fields of one element.

    Raises on transport errors (the pipeline handles degradation); malformed
    or incomplete JSON degrades per-field to the source value with a warning
    so a single bad response can never corrupt the batch.
    """
    field_names = list(element.fields.keys())
    source_chars = sum(len(v) for v in element.fields.values())
    payload = {
        "model": model,
        "messages": build_messages(element, to_language, from_language, glossary),
        "stream": False,
        "format": _json_schema_for(field_names),
        # Houd het model tussen de passes warm (zie config): voorkomt
        # herladen wanneer een pass van het andere werkpaard langer duurt
        # dan Ollama's eigen 5-minuten-default.
        "keep_alive": config.ollama_keep_alive,
        "options": {
            "temperature": 0,
            "seed": config.seed,
            # Cap the response: translations are a small multiple of the
            # input; without a cap a confused model can run away.
            "num_predict": min(4096, source_chars + 512),
        },
    }
    resp = requests.post(f"{config.ollama_url}/api/chat", json=payload, timeout=config.ollama_timeout)
    resp.raise_for_status()
    raw = (resp.json().get("message") or {}).get("content", "")

    try:
        parsed = json.loads(_strip_response(raw))
        if not isinstance(parsed, dict):
            raise ValueError("respons is geen JSON-object")
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning(
            f"LLM-respons voor element {element.section}/{element.key} is geen geldige JSON ({e});"
            " bronwaarden behouden."
        )
        return dict(element.fields)

    result: Dict[str, str] = {}
    for name, source_value in element.fields.items():
        value = parsed.get(name)
        if not isinstance(value, str) or not value.strip():
            logger.warning(
                f"LLM-respons voor element {element.section}/{element.key} mist veld '{name}';" " bronwaarde behouden."
            )
            result[name] = source_value
            continue
        if name in NAME_FIELDS:
            value = reconcile_case(source_value, value.strip())
        result[name] = value.strip() if isinstance(value, str) else value
    return result


# ---------------------------------------------------------------------------
# Deterministic quality checks (voting + glossary compliance)
# ---------------------------------------------------------------------------


def _normalize_name(name: str) -> str:
    """Reduce a name to its letters/digits, casefolded, so 'StartAttendance',
    'start_attendance' and 'start attendance' all agree."""
    return re.sub(r"[^0-9a-zà-ÿ]+", "", name.casefold())


def names_agree(a: Optional[str], b: Optional[str]) -> bool:
    """The two-workhorse vote on the translated name. Agreement after
    normalisation is evidence of confidence (not proof of correctness);
    disagreement *is* the definition of a hard case."""
    if a is None or b is None:
        return False
    return _normalize_name(a) == _normalize_name(b) and _normalize_name(a) != ""


def _term_in_text(term: str, text: str) -> bool:
    """Word-boundary-ish containment check, case-insensitive."""
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE) is not None


def glossary_violations(source_text: str, translated_text: str, glossary: Dict[str, str]) -> List[Tuple[str, str]]:
    """Return the glossary pairs that are violated: the source term occurs
    in the source text but the required target term is absent from the
    translation. This is the deterministic compliance check for definitions
    (voting does not work there — two LLMs rarely produce the same
    sentence)."""
    violations: List[Tuple[str, str]] = []
    if not source_text or not translated_text:
        return violations
    for src_term, tgt_term in glossary.items():
        if not src_term or not tgt_term:
            continue
        if _term_in_text(src_term, source_text) and not _term_in_text(tgt_term, translated_text):
            violations.append((src_term, tgt_term))
    return violations
