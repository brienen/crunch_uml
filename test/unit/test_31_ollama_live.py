"""
Live smoke tests against a REAL local Ollama server — no mocks.

All other pipeline tests (test_23 … test_30) mock every HTTP call so they
are fast, deterministic and CI-safe. These tests are the opt-in
complement: they verify the assumptions the mocks encode against a real
server and a real model:

* the preflight resolves locally installed models with digest and pull date;
* a real element translation returns valid JSON with all fields;
* temperature 0 + seed actually yields reproducible output (the hard
  requirement of the pipeline) on this server/model combination;
* a real model follows the binding glossary.

They are marked ``slow`` (excluded from ``make test``) and skip cleanly
when no Ollama server is reachable or no chat-capable model is installed:

    .venv/bin/pytest -m slow test/unit/test_31_ollama_live.py -v

The model is picked automatically (preference: mistral-small*, otherwise
the smallest chat-capable model); override with
``CRUNCH_UML_TEST_OLLAMA_MODEL``.
"""

from __future__ import annotations

import os
from typing import Optional

import pytest
import requests

from crunch_uml.translation.config import TranslationConfig
from crunch_uml.translation.llm import (
    Element,
    glossary_violations,
    translate_element_once,
)
from crunch_uml.translation.preflight import run_preflight

OLLAMA_URL = os.environ.get("CRUNCH_UML_OLLAMA_URL", "http://localhost:11434").rstrip("/")
# Ruime timeout: de eerste call laadt het model in het (V)RAM.
LIVE_TIMEOUT = int(os.environ.get("CRUNCH_UML_TEST_OLLAMA_TIMEOUT", "300"))


def _pick_live_model() -> Optional[str]:
    """The model the live tests run against, or None when unavailable."""
    override = os.environ.get("CRUNCH_UML_TEST_OLLAMA_MODEL")
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        resp.raise_for_status()
        models = resp.json().get("models", [])
    except Exception:
        return None
    if override:
        return override
    chat_models = [
        m
        for m in models
        # Embedding-modellen (bge-m3, nomic-embed, ...) kunnen niet chatten.
        if "embedding" not in (m.get("capabilities") or ["completion"])
    ]
    if not chat_models:
        return None
    preferred = [m for m in chat_models if m["name"].startswith("mistral-small")]
    pool = preferred or chat_models
    return min(pool, key=lambda m: m.get("size", 0))["name"]


LIVE_MODEL = _pick_live_model()

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(LIVE_MODEL is None, reason=f"geen bereikbare Ollama met chat-model op {OLLAMA_URL}"),
]


def _config() -> TranslationConfig:
    assert LIVE_MODEL is not None  # afgedwongen door de skipif hierboven
    return TranslationConfig(
        workhorses=(LIVE_MODEL,),
        ollama_url=OLLAMA_URL,
        ollama_timeout=LIVE_TIMEOUT,
        workers=1,
        seed=42,
    )


def _element() -> Element:
    return Element(
        section="classes",
        key="EAID_LIVE_1",
        fields={
            "name": "Bouwactiviteit",
            "definitie": "Het bouwen van een bouwwerk waarvoor een vergunning vereist is.",
        },
        context={"model": "Gebouwde Omgeving", "package": "Kern"},
    )


def test_live_preflight_resolves_installed_model(caplog):
    with caplog.at_level("INFO"):
        result = run_preflight(_config())

    assert result.llm.enabled
    assert result.llm.workhorses[0].tag == LIVE_MODEL
    # Traceerbaarheid: digest en serverversie zijn echt aanwezig.
    assert result.llm.workhorses[0].digest
    assert result.llm.server_version
    summary = next(m for m in caplog.messages if m.startswith("Vertaalpijplijn preflight:"))
    assert LIVE_MODEL in summary


def test_live_element_translation_returns_all_fields():
    result = translate_element_once(_element(), "en", "nl", model=LIVE_MODEL, config=_config())

    assert set(result.keys()) == {"name", "definitie"}
    assert all(isinstance(v, str) and v.strip() for v in result.values())
    # De naam is een PascalCase-bron: reconcile_case moet de vorm bewaken.
    assert " " not in result["name"]
    # De definitie is echt vertaald (Engels): het Nederlandse lidwoord-patroon is weg.
    assert "waarvoor" not in result["definitie"].lower()


def test_live_translation_is_reproducible():
    """De harde eis van de pijplijn, gecontroleerd tegen de echte server:
    temperature 0 + vaste seed → tweemaal exact dezelfde output."""
    first = translate_element_once(_element(), "en", "nl", model=LIVE_MODEL, config=_config())
    second = translate_element_once(_element(), "en", "nl", model=LIVE_MODEL, config=_config())
    assert first == second


def test_live_model_follows_binding_glossary():
    """Het bindende glossarium is het kernmechanisme van de pijplijn: een
    echt model moet de voorgeschreven vertaling gebruiken. Faalt deze test,
    dan is het gekozen werkpaard ongeschikt voor terminologiegebonden werk
    — precies wat je wilt weten."""
    element = Element(
        section="attributes",
        key="EAID_LIVE_2",
        fields={"definitie": "Er is een vergunning vereist voor het plaatsen van een bouwwerk."},
    )
    glossary = {"vergunning": "permit", "bouwwerk": "structure"}

    result = translate_element_once(element, "en", "nl", model=LIVE_MODEL, config=_config(), glossary=glossary)

    assert glossary_violations(element.fields["definitie"], result["definitie"], glossary) == []
