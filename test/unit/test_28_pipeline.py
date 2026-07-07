"""
Tests for crunch_uml.translation.pipeline — the cascade orchestration.

All model calls are mocked (no Ollama, no network). Covered:

* an exact, unambiguous termbank hit fixes the name deterministically —
  the LLM is never called for a name-only element;
* a homonym is disambiguated on the source definition before any model
  runs;
* hierarchy: the package translation from level 1 appears in the binding
  glossary of a class translated in level 2 (glossary propagation);
* voting: agreeing workhorses → accepted without escalation; disagreeing
  names → the heavy model arbitrates and its answer wins;
* a glossary violation in a definition escalates deterministically;
* degradation: no LLM → NMT; no NMT → online only when explicitly allowed;
  nothing available → source values kept plus a warning.
"""

from __future__ import annotations

from typing import Dict, List

import pytest

import crunch_uml.translation.pipeline as pipeline_mod
from crunch_uml.translation import termbank
from crunch_uml.translation.config import TranslationConfig
from crunch_uml.translation.llm import Element
from crunch_uml.translation.pipeline import TranslationPipeline
from crunch_uml.translation.preflight import LLMStatus, PreflightResult, ResolvedModel

TTL_FIXTURE = "./test/data/termbank_fixture.ttl"


def _preflight(
    llm_enabled=True,
    voting=True,
    heavy=True,
    termbanks=(TTL_FIXTURE,),
    nmt_enabled=False,
    online_enabled=False,
):
    config = TranslationConfig(workers=1, nmt_model="nmt-model" if nmt_enabled else None)
    result = PreflightResult(config=config)
    if llm_enabled:
        horses = [ResolvedModel(requested="wp1", tag="wp1")]
        if voting:
            horses.append(ResolvedModel(requested="wp2", tag="wp2"))
        result.llm = LLMStatus(
            enabled=True,
            workhorses=horses,
            heavy=ResolvedModel(requested="heavy", tag="heavy") if heavy else None,
            voting_enabled=voting,
        )
    if termbanks:
        result.termbank_index, result.termbank_reports = termbank.load_termbanks(list(termbanks))
    result.nmt_enabled = nmt_enabled
    result.online_enabled = online_enabled
    return result


class FakeLLM:
    """Deterministic stand-in for llm.translate_element_once: answers come
    from a (element-key, model) table and every call is recorded."""

    def __init__(self, answers: Dict):
        self.answers = answers
        self.calls: List[Dict] = []

    def __call__(self, element, to_language, from_language, model, config, glossary=None):
        self.calls.append(
            {"key": element.key, "model": model, "fields": dict(element.fields), "glossary": dict(glossary or {})}
        )
        answer = self.answers.get((element.key, model)) or self.answers.get(element.key) or {}
        return {f: answer.get(f, f"<{model}:{v}>") for f, v in element.fields.items()}


def _install(monkeypatch, fake: FakeLLM):
    monkeypatch.setattr(pipeline_mod, "translate_element_once", fake)


# ---------------------------------------------------------------------------
# Termbank layer
# ---------------------------------------------------------------------------


def test_exact_termbank_hit_skips_llm_for_name_only_element(monkeypatch, caplog):
    fake = FakeLLM({})
    _install(monkeypatch, fake)
    pipe = TranslationPipeline(_preflight())
    element = Element(section="classes", key="E1", fields={"name": "Vergunning"})

    with caplog.at_level("INFO"):
        results = pipe.translate_elements([element], "en", "nl")

    assert results[("classes", "E1")]["name"] == "Permit"  # reconcile_case: PascalCase bron
    assert fake.calls == [], "geen LLM-call verwacht bij een eenduidige termbanktreffer"
    assert any("deterministisch vertaald" in m and "vergunning" in m for m in caplog.messages)


def test_homonym_is_disambiguated_on_definition_before_any_model(monkeypatch):
    fake = FakeLLM({})
    _install(monkeypatch, fake)
    pipe = TranslationPipeline(_preflight())
    element = Element(
        section="classes",
        key="E1",
        fields={
            "name": "Partij",
            "definitie": "Persoon of rechtspersoon die deelneemt aan een overeenkomst met de gemeente.",
        },
    )

    results = pipe.translate_elements([element], "en", "nl")

    # Naam ligt deterministisch vast op het juridische concept...
    assert results[("classes", "E1")]["name"] == "Party"
    # ...en alleen de definitie ging nog door de LLM, mét de naam in het glossarium.
    assert len(fake.calls) >= 1
    assert all("name" not in c["fields"] for c in fake.calls)
    assert fake.calls[0]["glossary"].get("Partij") == "Party"


def test_ambiguous_name_goes_to_llm_with_candidates(monkeypatch):
    """No definition, no domain context: the homonym stays ambiguous and the
    LLM decides — with the candidates attached to the element."""
    fake = FakeLLM({("E1", "wp1"): {"name": "Party"}, ("E1", "wp2"): {"name": "Party"}})
    _install(monkeypatch, fake)
    pipe = TranslationPipeline(_preflight())
    element = Element(section="classes", key="E1", fields={"name": "Partij"})

    results = pipe.translate_elements([element], "en", "nl")

    assert results[("classes", "E1")]["name"] == "Party"
    assert len(fake.calls) == 2  # beide werkpaarden, geen escalatie
    assert len(element.candidates) == 2  # kandidaten uit de termbank hingen aan het element


# ---------------------------------------------------------------------------
# Hierarchy + glossary propagation
# ---------------------------------------------------------------------------


def test_package_translation_propagates_into_class_glossary(monkeypatch):
    """Level 1 translates the package; level 2 must see that translation in
    its binding glossary when the term occurs in its source text."""
    fake = FakeLLM(
        {
            ("PKG", "wp1"): {"name": "Permits"},
            ("PKG", "wp2"): {"name": "Permits"},
            ("CLS", "wp1"): {"name": "Application", "definitie": "An application within Permits."},
            ("CLS", "wp2"): {"name": "Application"},
        }
    )
    _install(monkeypatch, fake)
    pipe = TranslationPipeline(_preflight(termbanks=()))

    elements = [
        Element(section="classes", key="CLS", fields={"name": "Aanvraag", "definitie": "Een aanvraag binnen Vergunningen."}),
        Element(section="packages", key="PKG", fields={"name": "Vergunningen"}),
    ]
    results = pipe.translate_elements(elements, "en", "nl")

    assert results[("packages", "PKG")]["name"] == "Permits"
    # De klasse-call kreeg het pakketglossarium mee.
    class_calls = [c for c in fake.calls if c["key"] == "CLS"]
    assert class_calls, "klasse moet door de LLM zijn gegaan"
    assert all(c["glossary"].get("Vergunningen") == "Permits" for c in class_calls)
    # En packages zijn vóór classes vertaald (niveau-volgorde).
    assert fake.calls[0]["key"] == "PKG"


# ---------------------------------------------------------------------------
# Voting + escalation
# ---------------------------------------------------------------------------


def test_agreeing_workhorses_accept_without_heavy_model(monkeypatch):
    fake = FakeLLM(
        {
            ("E1", "wp1"): {"name": "ConstructionActivity", "definitie": "d"},
            ("E1", "wp2"): {"name": "construction_activity", "definitie": "iets anders"},
        }
    )
    _install(monkeypatch, fake)
    pipe = TranslationPipeline(_preflight(termbanks=()))
    element = Element(section="classes", key="E1", fields={"name": "Bouwactiviteit", "definitie": "Het bouwen."})

    results = pipe.translate_elements([element], "en", "nl")

    # Genormaliseerd gelijk → geaccepteerd; het zware model is nooit aangeroepen.
    assert results[("classes", "E1")]["name"] == "ConstructionActivity"
    assert [c["model"] for c in fake.calls] == ["wp1", "wp2"]


def test_disagreeing_workhorses_escalate_to_heavy_model(monkeypatch, caplog):
    fake = FakeLLM(
        {
            ("E1", "wp1"): {"name": "Case"},
            ("E1", "wp2"): {"name": "Matter"},
            ("E1", "heavy"): {"name": "LegalCase"},
        }
    )
    _install(monkeypatch, fake)
    pipe = TranslationPipeline(_preflight(termbanks=()))
    element = Element(section="classes", key="E1", fields={"name": "Zaak"})

    with caplog.at_level("INFO"):
        results = pipe.translate_elements([element], "en", "nl")

    assert [c["model"] for c in fake.calls] == ["wp1", "wp2", "heavy"]
    assert results[("classes", "E1")]["name"] == "LegalCase"
    assert any("oneens over naam" in m for m in caplog.messages)


def test_disagreement_without_heavy_model_keeps_primary_and_warns(monkeypatch, caplog):
    fake = FakeLLM({("E1", "wp1"): {"name": "Case"}, ("E1", "wp2"): {"name": "Matter"}})
    _install(monkeypatch, fake)
    pipe = TranslationPipeline(_preflight(termbanks=(), heavy=False))
    element = Element(section="classes", key="E1", fields={"name": "Zaak"})

    with caplog.at_level("WARNING"):
        results = pipe.translate_elements([element], "en", "nl")

    assert results[("classes", "E1")]["name"] == "Case"  # primaire werkpaard
    assert any("geen zwaar model beschikbaar" in m for m in caplog.messages)


def test_glossary_violation_in_definition_escalates(monkeypatch):
    """The primary workhorse ignores the binding term 'permit' in the
    definition: deterministic compliance check must escalate to heavy."""
    fake = FakeLLM(
        {
            ("PKG", "wp1"): {"name": "Permit"},
            ("PKG", "wp2"): {"name": "Permit"},
            ("E1", "wp1"): {"definitie": "A licence is required."},
            ("E1", "heavy"): {"definitie": "A permit is required."},
        }
    )
    _install(monkeypatch, fake)
    pipe = TranslationPipeline(_preflight(termbanks=()))

    elements = [
        Element(section="packages", key="PKG", fields={"name": "Vergunning"}),
        Element(section="attributes", key="E1", fields={"definitie": "Er is een vergunning vereist."}),
    ]
    results = pipe.translate_elements(elements, "en", "nl")

    assert results[("attributes", "E1")]["definitie"] == "A permit is required."
    heavy_calls = [c for c in fake.calls if c["model"] == "heavy"]
    assert [c["key"] for c in heavy_calls] == ["E1"]


def test_single_workhorse_never_runs_second_pass(monkeypatch):
    """Voting disabled (one workhorse): exactly one pass, no second vote."""
    fake = FakeLLM({("E1", "wp1"): {"name": "Case"}})
    _install(monkeypatch, fake)
    pipe = TranslationPipeline(_preflight(termbanks=(), voting=False, heavy=False))
    element = Element(section="classes", key="E1", fields={"name": "Zaak"})

    results = pipe.translate_elements([element], "en", "nl")

    assert [c["model"] for c in fake.calls] == ["wp1"]
    assert results[("classes", "E1")]["name"] == "Case"


# ---------------------------------------------------------------------------
# Degradation below the LLM
# ---------------------------------------------------------------------------


def test_without_llm_the_nmt_safety_net_translates(monkeypatch):
    def fake_nmt(texts, to_lang, from_lang, template):
        assert template == "nmt-model"
        return [f"NMT:{t}" for t in texts]

    from crunch_uml.translation import nmt

    monkeypatch.setattr(nmt, "translate_texts", fake_nmt)
    pipe = TranslationPipeline(_preflight(llm_enabled=False, termbanks=(), nmt_enabled=True))
    element = Element(section="classes", key="E1", fields={"definitie": "Het bouwen."})

    results = pipe.translate_elements([element], "en", "nl")
    assert results[("classes", "E1")]["definitie"] == "NMT:Het bouwen."


def test_without_llm_and_nmt_online_runs_only_when_allowed(monkeypatch):
    calls = []

    def fake_online(value, to_language, from_language, **kwargs):
        calls.append(value)
        return f"ONLINE:{value}"

    import crunch_uml.lang as lang

    monkeypatch.setattr(lang, "translate", fake_online)

    pipe = TranslationPipeline(_preflight(llm_enabled=False, termbanks=(), online_enabled=True))
    element = Element(section="classes", key="E1", fields={"name": "Zaak"})
    results = pipe.translate_elements([element], "en", "nl")
    assert results[("classes", "E1")]["name"] == "ONLINE:Zaak"
    assert calls == ["Zaak"]


def test_nothing_available_keeps_source_values_with_warning(monkeypatch, caplog):
    pipe = TranslationPipeline(_preflight(llm_enabled=False, termbanks=()))
    element = Element(section="classes", key="E1", fields={"name": "Zaak", "definitie": "Een zaak."})

    with caplog.at_level("WARNING"):
        results = pipe.translate_elements([element], "en", "nl")

    assert results[("classes", "E1")] == {"name": "Zaak", "definitie": "Een zaak."}
    assert any("konden niet vertaald worden" in m for m in caplog.messages)


def test_termbank_layer_still_works_without_any_generation_layer(monkeypatch, caplog):
    """Only the termbank is available: exact hits still translate, the rest
    keeps its source value."""
    pipe = TranslationPipeline(_preflight(llm_enabled=False))
    elements = [
        Element(section="classes", key="E1", fields={"name": "Vergunning"}),
        Element(section="classes", key="E2", fields={"name": "Onvindbaar"}),
    ]
    with caplog.at_level("WARNING"):
        results = pipe.translate_elements(elements, "en", "nl")

    assert results[("classes", "E1")]["name"] == "Permit"
    assert results[("classes", "E2")]["name"] == "Onvindbaar"
