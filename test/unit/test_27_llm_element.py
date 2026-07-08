"""
Tests for crunch_uml.translation.llm — per-element translation calls and the
deterministic quality checks.

All HTTP is mocked. Covered:

* the payload wiring: one /api/chat call per element, JSON-schema ``format``
  over exactly the element's fields, temperature 0 + configured seed,
  response-length cap;
* the prompt: compact context header, binding glossary, termbank candidates
  with definition/source/reliability, source fields as one JSON object;
* response handling: parsed JSON becomes the field dict, identifier casing
  is reconciled, malformed or incomplete responses degrade per field to the
  source value with a warning (never crash, never corrupt);
* ``names_agree`` — the two-workhorse vote normalisation;
* ``glossary_violations`` — the deterministic compliance check that decides
  escalation for definitions.
"""

from __future__ import annotations

import json
from typing import Dict, List

import requests

from crunch_uml.translation import llm
from crunch_uml.translation.config import TranslationConfig
from crunch_uml.translation.llm import Element, glossary_violations, names_agree
from crunch_uml.translation.termbank import Candidate

CONFIG = TranslationConfig(seed=42, ollama_url="http://localhost:11434", ollama_timeout=5)


class FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": self._content}}


def _capture_post(monkeypatch, content: Dict[str, str]):
    """Mock requests.post, returning ``content`` as the LLM answer and
    capturing every payload sent."""
    payloads: List[Dict] = []

    def fake_post(url, json=None, timeout=None):
        payloads.append({"url": url, "payload": json, "timeout": timeout})
        import json as _json

        return FakeResponse(_json.dumps(content))

    monkeypatch.setattr(requests, "post", fake_post)
    return payloads


def _element(**kwargs):
    defaults = dict(
        section="classes",
        key="EAID_1",
        fields={"name": "Bouwactiviteit", "definitie": "Het bouwen van een bouwwerk."},
        context={},
    )
    defaults.update(kwargs)
    return Element(**defaults)


# ---------------------------------------------------------------------------
# Payload wiring
# ---------------------------------------------------------------------------


def test_single_call_with_json_schema_temperature_zero_and_seed(monkeypatch):
    payloads = _capture_post(monkeypatch, {"name": "ConstructionActivity", "definitie": "The construction."})
    element = _element()

    result = llm.translate_element_once(element, "en", "nl", model="qwen2.5:14b", config=CONFIG)

    assert len(payloads) == 1
    sent = payloads[0]["payload"]
    assert payloads[0]["url"] == "http://localhost:11434/api/chat"
    assert sent["model"] == "qwen2.5:14b"
    assert sent["options"]["temperature"] == 0
    assert sent["options"]["seed"] == 42
    # Modellen blijven tussen passes warm (Ollama's 5m-default is te kort).
    assert sent["keep_alive"] == CONFIG.ollama_keep_alive
    assert sent["options"]["num_predict"] <= 4096
    # format = JSON-schema over precies de velden van het element.
    assert sent["format"]["required"] == ["name", "definitie"]
    assert sent["format"]["additionalProperties"] is False
    assert result == {"name": "ConstructionActivity", "definitie": "The construction."}


def test_prompt_contains_context_glossary_candidates_and_fields(monkeypatch):
    payloads = _capture_post(monkeypatch, {"name": "Party", "definitie": "A party."})
    element = _element(
        fields={"name": "Partij", "definitie": "Persoon die deelneemt aan een overeenkomst."},
        context={
            "model": "Gebouwde Omgeving",
            "model_definition": "Model voor de gebouwde omgeving.",
            "package": "Kern",
            "parent": "Overeenkomst",
            "parent_definition": "Afspraak tussen partijen.",
            "siblings": "Zaak, Besluit",
        },
        candidates=[
            Candidate(
                term="party",
                source_term="partij",
                uri="ex:partij-recht",
                source="eurovoc",
                priority=0,
                exact=True,
                definition="Persoon of rechtspersoon in een overeenkomst.",
                domains=["Recht"],
                reliability=3,
            )
        ],
    )

    llm.translate_element_once(element, "en", "nl", model="m", config=CONFIG, glossary={"vergunning": "permit"})

    user_msg = payloads[0]["payload"]["messages"][1]["content"]
    assert "Model: Gebouwde Omgeving — Model voor de gebouwde omgeving." in user_msg
    assert "Package: Kern" in user_msg
    assert "Belongs to: Overeenkomst — Afspraak tussen partijen." in user_msg
    assert "Sibling elements: Zaak, Besluit" in user_msg
    assert "GLOSSARY (binding):" in user_msg
    assert "- vergunning -> permit" in user_msg
    assert 'CANDIDATES for "Partij"' in user_msg
    assert (
        "1. party — Persoon of rechtspersoon in een overeenkomst. (source: eurovoc; domain: Recht; reliability: 3)"
        in user_msg
    )
    # De bronvelden gaan als één JSON-object mee.
    assert json.dumps(element.fields, ensure_ascii=False) in user_msg


def test_candidate_list_in_prompt_is_capped(monkeypatch):
    """IATE can yield dozens of near-duplicate candidates for common terms;
    only the strongest MAX_PROMPT_CANDIDATES reach the prompt."""
    payloads = _capture_post(monkeypatch, {"name": "Municipality"})
    candidates = [
        Candidate(term=f"variant{i}", source_term="gemeente", uri=f"ex:c{i:02d}", source="iate", priority=0, exact=True)
        for i in range(20)
    ]
    element = _element(fields={"name": "Gemeente"}, candidates=candidates)

    llm.translate_element_once(element, "en", "nl", model="m", config=CONFIG)

    user_msg = payloads[0]["payload"]["messages"][1]["content"]
    assert f"{llm.MAX_PROMPT_CANDIDATES}. variant{llm.MAX_PROMPT_CANDIDATES - 1}" in user_msg
    assert f"variant{llm.MAX_PROMPT_CANDIDATES}" not in user_msg


def test_identifier_casing_is_reconciled_on_name_fields(monkeypatch):
    """The LLM answers with spaces; the source name is PascalCase, so the
    result must be re-cased deterministically."""
    _capture_post(monkeypatch, {"name": "construction activity", "definitie": "x"})
    result = llm.translate_element_once(_element(), "en", "nl", model="m", config=CONFIG)
    assert result["name"] == "ConstructionActivity"


# ---------------------------------------------------------------------------
# Degradation on bad responses
# ---------------------------------------------------------------------------


def test_malformed_json_response_keeps_source_values_with_warning(monkeypatch, caplog):
    def fake_post(url, json=None, timeout=None):
        return FakeResponse("dit is geen json")

    monkeypatch.setattr(requests, "post", fake_post)
    element = _element()
    with caplog.at_level("WARNING"):
        result = llm.translate_element_once(element, "en", "nl", model="m", config=CONFIG)
    assert result == element.fields
    assert any("geen geldige JSON" in m for m in caplog.messages)


def test_missing_field_in_response_keeps_that_source_value(monkeypatch, caplog):
    _capture_post(monkeypatch, {"name": "ConstructionActivity"})  # definitie ontbreekt
    element = _element()
    with caplog.at_level("WARNING"):
        result = llm.translate_element_once(element, "en", "nl", model="m", config=CONFIG)
    assert result["name"] == "ConstructionActivity"
    assert result["definitie"] == element.fields["definitie"]
    assert any("mist veld 'definitie'" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# Voting + glossary compliance
# ---------------------------------------------------------------------------


def test_names_agree_normalises_casing_and_separators():
    assert names_agree("StartAttendance", "start_attendance")
    assert names_agree("start attendance", "startAttendance")
    assert not names_agree("StartAttendance", "BeginPresence")
    assert not names_agree(None, "x")
    assert not names_agree("", "")


def test_glossary_violations_flags_missing_binding_terms():
    glossary = {"vergunning": "permit", "bouwwerk": "structure"}
    source = "De vergunning voor een bouwwerk."
    ok = "The permit for a structure."
    bad = "The licence for a structure."

    assert glossary_violations(source, ok, glossary) == []
    assert glossary_violations(source, bad, glossary) == [("vergunning", "permit")]


def test_glossary_violations_ignores_terms_absent_from_source():
    glossary = {"vergunning": "permit"}
    assert glossary_violations("Iets heel anders.", "Something else.", glossary) == []


def test_glossary_violations_is_word_bounded_and_case_insensitive():
    glossary = {"partij": "party"}
    # 'partijdig' bevat 'partij' als substring maar is een ander woord.
    assert glossary_violations("Een partijdig besluit.", "A biased decision.", glossary) == []
    assert glossary_violations("De Partij tekent.", "The PARTY signs.", glossary) == []
