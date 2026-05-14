"""
Tests for the Ollama translation backend.

All tests are mock-based — no real network is contacted, no Ollama server
needs to be running. Three concerns are covered:

* **HTTP wiring** — :func:`crunch_uml.ollama_translator.translate` posts a
  correctly shaped payload to ``/api/chat``, with a deterministic
  ``temperature=0`` config.
* **Case preservation** — :func:`reconcile_case` is the deterministic
  safety net that forces the LLM's output back into the source's
  identifier style (camelCase, PascalCase, snake_case, kebab-case,
  ALL_CAPS). Sentences with whitespace stay untouched.
* **Dispatch + fallback** — :func:`crunch_uml.lang.translate` routes to
  Ollama when ``CRUNCH_UML_TRANSLATE_BACKEND=ollama``, and falls back to
  the ``translators`` library if Ollama raises.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
import requests

import crunch_uml.lang as lang
import crunch_uml.ollama_translator as ot

# ---------------------------------------------------------------------------
# Case reconciliation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source,translation,expected",
    [
        # camelCase source, LLM gave whitespace → re-case in camelCase.
        ("aanvangAanwezigheid", "start attendance", "startAttendance"),
        # PascalCase source, whitespace output → PascalCase.
        ("Bouwactiviteit", "construction activity", "ConstructionActivity"),
        # snake_case source.
        ("datum_opname", "recording date", "recording_date"),
        # ALL_CAPS / acronym must come back upper.
        ("BAG", "bag", "BAG"),
        # LLM already nailed it — no-op.
        ("aanvangAanwezigheid", "startAttendance", "startAttendance"),
        # Natural-language sentence — never re-cased.
        (
            "Het bouwen van een bouwwerk.",
            "The construction of a building.",
            "The construction of a building.",
        ),
        # kebab-case stays kebab-case after rejoin.
        ("gemma-type", "gemma type", "gemma-type"),
    ],
)
def test_reconcile_case_examples(source, translation, expected):
    assert ot.reconcile_case(source, translation) == expected


def test_reconcile_case_passes_through_empty_translation():
    assert ot.reconcile_case("aanvang", "") == ""


def test_detect_case_classifies_known_styles():
    assert ot.detect_case("aanvangAanwezigheid") == ot._CASE_CAMEL
    assert ot.detect_case("Bouwactiviteit") == ot._CASE_PASCAL
    assert ot.detect_case("datum_opname") == ot._CASE_SNAKE
    assert ot.detect_case("gemma-type") == ot._CASE_KEBAB
    assert ot.detect_case("BAG") == ot._CASE_UPPER
    assert ot.detect_case("Het bouwen") == ot._CASE_NONE
    assert ot.detect_case("") == ot._CASE_NONE


# ---------------------------------------------------------------------------
# Response stripping
# ---------------------------------------------------------------------------


def test_strip_response_removes_surrounding_quotes():
    assert ot._strip_response('"hello"') == "hello"
    assert ot._strip_response(" 'hello' ") == "hello"


def test_strip_response_removes_code_fences():
    assert ot._strip_response("```\nhello\n```") == "hello"
    assert ot._strip_response("```en\nhello\n```") == "hello"


def test_strip_response_handles_plain_text():
    assert ot._strip_response("  hello world  ") == "hello world"


# ---------------------------------------------------------------------------
# HTTP wiring
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, body: Dict[str, Any], status_code: int = 200):
        self._body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._body


def _capture(monkeypatch, response_body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Replace ``requests.post`` with a stub and capture each call's args."""
    calls: List[Dict[str, Any]] = []

    def fake_post(url, json=None, timeout=None, **kw):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResponse(response_body)

    monkeypatch.setattr(ot.requests, "post", fake_post)
    return calls


def test_translate_posts_to_chat_endpoint_with_correct_payload(monkeypatch):
    calls = _capture(monkeypatch, {"message": {"content": "hello"}})
    monkeypatch.setenv("CRUNCH_UML_OLLAMA_URL", "http://example:11434")
    monkeypatch.setenv("CRUNCH_UML_OLLAMA_MODEL", "mistral-small3.1:24b")

    out = ot.translate("hallo", to_language="en", from_language="nl")
    assert out == "hello"

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "http://example:11434/api/chat"
    payload = call["json"]
    assert payload["model"] == "mistral-small3.1:24b"
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0
    assert payload["options"]["seed"] == 42
    msgs = payload["messages"]
    assert msgs[0]["role"] == "system"
    assert "translator" in msgs[0]["content"].lower()
    assert msgs[1] == {"role": "user", "content": "hallo"}


def test_translate_with_context_embeds_hint_in_user_message(monkeypatch):
    calls = _capture(monkeypatch, {"message": {"content": "definition"}})
    out = ot.translate(
        "definitie",
        to_language="en",
        from_language="nl",
        context={"section": "classes", "field": "definitie", "parent": "Burger"},
    )
    assert out == "definition"
    user_content = calls[0]["json"]["messages"][1]["content"]
    assert "definitie" in user_content  # source still present
    assert "Context:" in user_content
    assert "classes" in user_content
    assert "Burger" in user_content


def test_translate_reconciles_case_after_llm_response(monkeypatch):
    """End-to-end: LLM returns whitespace for a camelCase source — the
    final returned value must be camelCase again."""
    _capture(monkeypatch, {"message": {"content": "start attendance"}})
    out = ot.translate("aanvangAanwezigheid", to_language="en", from_language="nl")
    assert out == "startAttendance"


def test_translate_strips_surrounding_quotes_before_reconciling(monkeypatch):
    _capture(monkeypatch, {"message": {"content": '"start attendance"'}})
    out = ot.translate("aanvangAanwezigheid", to_language="en", from_language="nl")
    assert out == "startAttendance"


def test_translate_returns_input_when_empty():
    assert ot.translate("", to_language="en", from_language="nl") == ""


# ---------------------------------------------------------------------------
# Preserve-unchanged fast path — skip the LLM for opaque tokens
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "<memo>",
        "<typing>",
        "</br>",
        "<UML:Class>",
        "EAID_54944273_F312_44b2_A78D_43488F915429",
        "EAPK_45B88627_6F44_4b6d_BE77_3EC51BBE679E",
        "EAID_attr_9138",
        "https://gemmaonline.nl/index.php/foo",
        "http://example.com/path?q=1",
        "www.gemmaonline.nl",
        "2024-05-13",
        "2024-05-13T10:30:00",
        "2024-05-13T10:30:00.123Z",
        "----",
        "###",
    ],
)
def test_translate_preserves_opaque_tokens_without_llm(value, monkeypatch):
    """For tokens that have no meaningful translation, return the source
    verbatim. ``requests.post`` must NOT be called."""

    def boom(*a, **kw):
        raise AssertionError("requests.post should not be called for opaque tokens")

    monkeypatch.setattr(ot.requests, "post", boom)
    assert ot.translate(value, to_language="en", from_language="nl") == value


def test_translate_does_not_preserve_legitimate_text(monkeypatch):
    """Sanity: ordinary words and sentences must still hit the LLM path."""
    called = {"count": 0}

    def fake_post(url, json=None, timeout=None, **kw):
        called["count"] += 1
        return _FakeResponse({"message": {"content": "house"}})

    monkeypatch.setattr(ot.requests, "post", fake_post)
    assert ot.translate("huis", to_language="en", from_language="nl") == "house"
    assert called["count"] == 1


# ---------------------------------------------------------------------------
# Dispatch + fallback through lang.translate
# ---------------------------------------------------------------------------


def test_lang_translate_routes_to_ollama_when_backend_env_set(monkeypatch):
    monkeypatch.setenv("CRUNCH_UML_TRANSLATE_BACKEND", "ollama")

    seen: List[Dict[str, Any]] = []

    def fake_ot(value, to_language, from_language, *, context=None):
        seen.append({"value": value, "to": to_language, "ctx": context})
        return "OLLAMA_RESULT"

    # Replace at the import site used in lang.py.
    monkeypatch.setattr(lang, "ollama_translator", SimpleNamespace(translate=fake_ot))

    # If Ollama is taken, the translators library must NOT be touched.
    def boom(*a, **kw):
        raise AssertionError("translators.ts.translate_text should not be called")

    monkeypatch.setattr(lang.ts, "translate_text", boom)

    result = lang.translate("hallo", "en", "nl", context={"section": "classes"})
    assert result == "OLLAMA_RESULT"
    assert seen == [{"value": "hallo", "to": "en", "ctx": {"section": "classes"}}]


def test_lang_translate_falls_back_to_translators_when_ollama_raises(monkeypatch):
    monkeypatch.setenv("CRUNCH_UML_TRANSLATE_BACKEND", "ollama")

    def ollama_raises(*a, **kw):
        raise requests.ConnectionError("Ollama not running")

    monkeypatch.setattr(lang, "ollama_translator", SimpleNamespace(translate=ollama_raises))

    ts_calls: List[Dict[str, Any]] = []

    def fake_ts(value, to_language, from_language, **kw):
        ts_calls.append({"value": value, "to": to_language, "from": from_language})
        return f"TS:{value}"

    monkeypatch.setattr(lang.ts, "translate_text", fake_ts)

    result = lang.translate("hallo", "en", "nl")
    assert result == "TS:hallo"
    assert len(ts_calls) == 1


def test_lang_translate_default_backend_skips_ollama(monkeypatch):
    """Without the env-var set, lang.translate must NOT touch ollama_translator."""
    monkeypatch.delenv("CRUNCH_UML_TRANSLATE_BACKEND", raising=False)

    def boom(*a, **kw):
        raise AssertionError("ollama_translator.translate should not be called")

    monkeypatch.setattr(lang, "ollama_translator", SimpleNamespace(translate=boom))

    def fake_ts(value, to_language, from_language, **kw):
        return f"TS:{value}"

    monkeypatch.setattr(lang.ts, "translate_text", fake_ts)

    result = lang.translate("hallo", "en", "nl")
    assert result == "TS:hallo"


# ---------------------------------------------------------------------------
# CLI arg propagation into env-vars
# ---------------------------------------------------------------------------


def test_cli_args_propagate_to_env(monkeypatch):
    """``--translate_backend``, ``--ollama_model`` etc. on the CLI must end
    up in os.environ so the deeper translation modules pick them up.
    """
    from crunch_uml.cli import _propagate_translate_args_to_env

    for var in (
        "CRUNCH_UML_TRANSLATE_BACKEND",
        "CRUNCH_UML_OLLAMA_MODEL",
        "CRUNCH_UML_OLLAMA_URL",
        "CRUNCH_UML_OLLAMA_TIMEOUT",
        "CRUNCH_UML_TRANSLATE_WORKERS",
        "CRUNCH_UML_TRANSLATE_CONTEXT",
    ):
        monkeypatch.delenv(var, raising=False)

    args = SimpleNamespace(
        translate_backend="ollama",
        ollama_model="mistral-nemo:12b",
        ollama_url="http://other:11434",
        ollama_timeout=60,
        translate_workers=4,
        translate_context=True,
    )
    _propagate_translate_args_to_env(args)

    import os as _os

    assert _os.environ["CRUNCH_UML_TRANSLATE_BACKEND"] == "ollama"
    assert _os.environ["CRUNCH_UML_OLLAMA_MODEL"] == "mistral-nemo:12b"
    assert _os.environ["CRUNCH_UML_OLLAMA_URL"] == "http://other:11434"
    assert _os.environ["CRUNCH_UML_OLLAMA_TIMEOUT"] == "60"
    assert _os.environ["CRUNCH_UML_TRANSLATE_WORKERS"] == "4"
    assert _os.environ["CRUNCH_UML_TRANSLATE_CONTEXT"] == "1"


def test_cli_args_leave_env_alone_when_not_specified(monkeypatch):
    """If the CLI omits a flag, any pre-existing env-var must remain."""
    from crunch_uml.cli import _propagate_translate_args_to_env

    monkeypatch.setenv("CRUNCH_UML_TRANSLATE_BACKEND", "ollama")
    monkeypatch.setenv("CRUNCH_UML_OLLAMA_MODEL", "preset-model")
    monkeypatch.delenv("CRUNCH_UML_TRANSLATE_CONTEXT", raising=False)

    args = SimpleNamespace(
        translate_backend=None,
        ollama_model=None,
        ollama_url=None,
        ollama_timeout=None,
        translate_workers=None,
        translate_context=False,
    )
    _propagate_translate_args_to_env(args)

    import os as _os

    assert _os.environ["CRUNCH_UML_TRANSLATE_BACKEND"] == "ollama"
    assert _os.environ["CRUNCH_UML_OLLAMA_MODEL"] == "preset-model"
    # store_true=False (not passed) does NOT force the env var on.
    assert "CRUNCH_UML_TRANSLATE_CONTEXT" not in _os.environ
