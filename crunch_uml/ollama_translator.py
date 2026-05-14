"""
Ollama-based translation backend for crunch_uml.

Activate via the env-var ``CRUNCH_UML_TRANSLATE_BACKEND=ollama``. When that
is set, :func:`crunch_uml.lang.translate` routes every call here, falling
back to the original ``translators`` API only if Ollama is unreachable.

Why a local LLM?

* Lets us push **per-call context** (the section / field we're translating)
  to improve consistency on domain terminology like ``objecttype`` or
  ``attribuutsoort``.
* Removes the dependency on Google/Bing endpoints, so no rate limits, no
  outbound traffic and no per-string network latency.

The implementation is deliberately small: a single ``requests.post`` to
``{OLLAMA_URL}/api/chat`` with a strict system prompt and a deterministic
``temperature=0`` + ``seed=42`` config.

Identifier casing is a real source of LLM mistakes, so the response is
post-processed by :func:`reconcile_case`: if the source is a camelCase /
PascalCase / snake_case / kebab-case / ALL_CAPS token and the LLM gives
back a phrase with spaces, we deterministically re-case it. The casing
contract is also spelled out in the system prompt for the (more common)
case where the LLM already produces the right shape.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger()


# ---------------------------------------------------------------------------
# Defaults / env-vars
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "mistral-small3.1:24b"
DEFAULT_URL = "http://localhost:11434"
DEFAULT_TIMEOUT = 120


def _env_url() -> str:
    return os.environ.get("CRUNCH_UML_OLLAMA_URL", DEFAULT_URL).rstrip("/")


def _env_model() -> str:
    return os.environ.get("CRUNCH_UML_OLLAMA_MODEL", DEFAULT_MODEL)


def _env_timeout() -> int:
    return int(os.environ.get("CRUNCH_UML_OLLAMA_TIMEOUT", str(DEFAULT_TIMEOUT)))


# ---------------------------------------------------------------------------
# Case detection / reconciliation
# ---------------------------------------------------------------------------

_CASE_NONE = "none"
_CASE_CAMEL = "camelCase"
_CASE_PASCAL = "PascalCase"
_CASE_SNAKE = "snake_case"
_CASE_KEBAB = "kebab-case"
_CASE_UPPER = "ALL_CAPS"


def detect_case(s: str) -> str:
    """Classify the identifier-casing style of ``s``.

    Returns one of the ``_CASE_*`` constants. Whitespace anywhere means it's
    a sentence/phrase, not an identifier, and gets ``_CASE_NONE`` so the
    caller leaves the LLM output alone.
    """
    if not s:
        return _CASE_NONE
    if any(c.isspace() for c in s):
        return _CASE_NONE
    # ALL_CAPS / SCREAMING_SNAKE — any letters present and all upper.
    letters = [c for c in s if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return _CASE_UPPER
    if "_" in s:
        return _CASE_SNAKE
    if "-" in s:
        return _CASE_KEBAB
    if s[:1].isupper() and any(c.isupper() for c in s[1:]):
        return _CASE_PASCAL
    if s[:1].isupper() and not any(c.isupper() for c in s[1:]):
        # Single capitalised word (e.g. "Bouwactiviteit") — treat as Pascal
        # so multi-word translations come back joined.
        return _CASE_PASCAL
    if s[:1].islower() and any(c.isupper() for c in s):
        return _CASE_CAMEL
    return _CASE_NONE


def force_case(words: List[str], style: str) -> str:
    """Rejoin ``words`` in the given identifier style."""
    if not words:
        return ""
    if style == _CASE_CAMEL:
        return words[0].lower() + "".join(w.capitalize() for w in words[1:])
    if style == _CASE_PASCAL:
        return "".join(w.capitalize() for w in words)
    if style == _CASE_SNAKE:
        return "_".join(w.lower() for w in words)
    if style == _CASE_KEBAB:
        return "-".join(w.lower() for w in words)
    if style == _CASE_UPPER:
        return "_".join(w.upper() for w in words)
    return " ".join(words)


def _split_words(s: str) -> List[str]:
    """Best-effort split of a translation string into words. Handles spaces,
    underscores, hyphens and CamelCase boundaries."""
    s = s.strip()
    if not s:
        return []
    # First split on obvious separators.
    parts = re.split(r"[\s_\-]+", s)
    out: List[str] = []
    for p in parts:
        if not p:
            continue
        # Split CamelCase / PascalCase into words too, so "startAttendance"
        # → ["start", "Attendance"] → we can re-case correctly.
        sub = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+", p)
        if sub:
            out.extend(sub)
        else:
            out.append(p)
    return out


def reconcile_case(source: str, translation: str) -> str:
    """Make the translation match the source's identifier style.

    No-op when the source is natural language (contains whitespace) or when
    the translation already matches the source's case style. Otherwise the
    translation is split into words and re-joined in the source style.
    """
    if not translation:
        return translation
    src_style = detect_case(source)
    if src_style == _CASE_NONE:
        return translation
    tgt_style = detect_case(translation)
    if src_style == tgt_style:
        return translation
    words = _split_words(translation)
    if not words:
        return translation
    return force_case(words, src_style)


# ---------------------------------------------------------------------------
# Prompt + response handling
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
You are a professional translator specialising in technical Dutch government \
data-modelling terminology (GEMMA, RSGB, BAG, BRP, RGBZ, ...). Translate the \
user message from {from_language} to {to_language}.

Output rules:
- Output ONLY the translation. No preamble, no quotes, no explanations.
- Preserve special tokens verbatim: <memo>, #NOTES#..., line breaks, embedded
  EAID_... identifiers, URLs.
- Keep domain acronyms unchanged: BAG, BRP, RSGB, GEMMA, RGBZ, BGT, BRK.

Case handling (CRITICAL - many inputs are identifiers, not prose):
- camelCase identifier  ->  translate every word, rejoin in camelCase.
    "aanvangAanwezigheid"   ->  "startAttendance"
    "redenWijzigingAdres"   ->  "reasonAddressChange"
- PascalCase class name  ->  translate every word, rejoin in PascalCase.
    "Bouwactiviteit"        ->  "ConstructionActivity"
    "BeschermdeStatus"      ->  "ProtectedStatus"
- snake_case identifier  ->  translate every word, rejoin in snake_case.
    "datum_opname"          ->  "recording_date"
    "indicatie_in_onderzoek"->  "under_investigation_indication"
- kebab-case identifier  ->  rejoin in kebab-case.
    "gemma-type"            ->  "gemma-type"
- ALL_CAPS / SCREAMING_SNAKE_CASE  ->  keep unchanged.
    "BAG", "BRP", "PUBLIC"  ->  "BAG", "BRP", "PUBLIC"
- Natural-language sentence (contains spaces)  ->  normal target-language
  casing and spacing. Translate fluently.
    "Het bouwen van een bouwwerk."  ->  "The construction of a building."
"""


def _build_messages(
    value: str,
    to_language: str,
    from_language: str,
    context: Optional[Dict[str, Any]],
) -> List[Dict[str, str]]:
    system = SYSTEM_PROMPT_TEMPLATE.format(from_language=from_language, to_language=to_language)
    if context:
        # Compact human-readable hint, kept short on purpose.
        bits = []
        sec = context.get("section")
        fld = context.get("field")
        parent = context.get("parent")
        if sec and fld:
            bits.append(f"This is the '{fld}' field of a {sec} entry.")
        elif sec:
            bits.append(f"This is part of a {sec} entry.")
        if parent:
            bits.append(f"It belongs to '{parent}'.")
        ctx_line = " ".join(bits) if bits else ""
        if ctx_line:
            user = f"Context: {ctx_line}\n\nSource text:\n{value}"
        else:
            user = value
    else:
        user = value
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# Tokens we never send to the LLM — they have no meaningful translation and
# their presence in a translation request tends to make the model
# hallucinate (e.g. "expand <memo>" into a fictional schema, or try to
# camelCase a 32-char GUID). Each pattern matches the *entire* value.
_PRESERVE_PATTERNS: List[re.Pattern] = [
    # Single XML/HTML-like tag with no whitespace: <memo>, <typing>, </br>
    re.compile(r"^</?[a-zA-Z][a-zA-Z0-9:_./-]*/?>$"),
    # EA-generated identifiers — opaque, must stay verbatim.
    re.compile(r"^(EAID|EAPK)(_[A-Za-z0-9]+)+$"),
    # URLs
    re.compile(r"^https?://\S+$"),
    re.compile(r"^www\.\S+$"),
    # ISO-ish dates / timestamps
    re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$"),
    # Pure punctuation / symbols (no letters)
    re.compile(r"^[^A-Za-z]+$"),
]


def _should_preserve_unchanged(value: str) -> bool:
    """Return True if ``value`` should be returned verbatim, skipping the LLM."""
    if not isinstance(value, str):
        return True
    s = value.strip()
    if not s:
        return True
    return any(p.fullmatch(s) for p in _PRESERVE_PATTERNS)


_TRIPLE_BACKTICK_RE = re.compile(r"^```(?:[a-zA-Z]+)?\n?(.*?)\n?```$", re.DOTALL)


def _strip_response(text: str) -> str:
    """Remove surrounding quotes / fences that the LLM sometimes adds."""
    if text is None:
        return ""
    s = text.strip()
    # Triple backticks (with optional language tag) — strip wrapper.
    m = _TRIPLE_BACKTICK_RE.match(s)
    if m:
        s = m.group(1).strip()
    # Pair of matching surrounding quotes.
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"', "`"):
        s = s[1:-1].strip()
    return s


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def translate(
    value: str,
    to_language: str,
    from_language: str,
    *,
    context: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    url: Optional[str] = None,
    timeout: Optional[int] = None,
) -> str:
    """Translate ``value`` via the Ollama ``/api/chat`` endpoint.

    Raises :class:`requests.RequestException` (or any other ``Exception``
    bubbling up from the HTTP call) when Ollama is unreachable so the
    caller in :mod:`crunch_uml.lang` can apply the fallback.
    """
    if not isinstance(value, str) or value == "":
        return value

    # Fast-path: opaque tokens we never want the LLM to "translate" (it
    # tends to hallucinate around lone GUIDs / XML tags).
    if _should_preserve_unchanged(value):
        return value

    chat_url = f"{(url or _env_url()).rstrip('/')}/api/chat"
    # Cap the response length: a translation is never more than a small
    # multiple of the input, but without num_predict the LLM occasionally
    # runs away (e.g. when it sees a bare special token like ``<memo>``
    # and tries to explain it). 4× input tokens + 128 is a generous ceiling
    # that still lets reasonable paragraphs through unchanged.
    estimated_in_tokens = max(8, len(value) // 4)
    num_predict = min(2048, 4 * estimated_in_tokens + 128)

    payload: Dict[str, Any] = {
        "model": model or _env_model(),
        "messages": _build_messages(value, to_language, from_language, context),
        "stream": False,
        "options": {
            "temperature": 0,
            "seed": 42,
            "num_predict": num_predict,
        },
    }
    logger.debug(
        "Ollama translate: model=%s, len(value)=%d, context=%s",
        payload["model"],
        len(value),
        bool(context),
    )

    resp = requests.post(chat_url, json=payload, timeout=timeout or _env_timeout())
    resp.raise_for_status()
    data = resp.json()
    raw = (data.get("message") or {}).get("content", "")
    cleaned = _strip_response(raw)
    return reconcile_case(value, cleaned) or value
