"""
Tests for crunch_uml.translation.nmt — the optional NMT safety net.

The 'transformers' dependency is optional and not installed in CI: the
module must import cleanly without it, report unavailability, and work
against a mocked transformers pipeline when it is present.
"""

from __future__ import annotations

import sys
import types

from crunch_uml.translation import nmt


def test_module_imports_without_transformers():
    """Importing crunch_uml.translation.nmt must never require transformers
    — merely reaching this test proves the import is safe."""
    assert hasattr(nmt, "available")


def test_available_reflects_importability(monkeypatch):
    if "transformers" not in sys.modules:
        # Niet geïnstalleerd: available() moet False zijn, geen exception.
        assert nmt.available() is False
    fake = types.ModuleType("transformers")
    monkeypatch.setitem(sys.modules, "transformers", fake)
    assert nmt.available() is True


def test_resolve_model_name_substitutes_placeholders():
    assert nmt.resolve_model_name("Helsinki-NLP/opus-mt-{from}-{to}", "nl", "en") == "Helsinki-NLP/opus-mt-nl-en"
    # Een vaste modelnaam gaat ongewijzigd door (bv. NLLB voor brede dekking).
    assert nmt.resolve_model_name("facebook/nllb-200", "nl", "en") == "facebook/nllb-200"


def test_translate_texts_uses_pipeline_and_caches_per_model(monkeypatch):
    created = []

    def fake_pipeline(task, model):
        assert task == "translation"
        created.append(model)

        def run(texts):
            return [{"translation_text": f"VERTAALD:{t}"} for t in texts]

        return run

    fake = types.ModuleType("transformers")
    fake.pipeline = fake_pipeline
    monkeypatch.setitem(sys.modules, "transformers", fake)
    monkeypatch.setattr(nmt, "_pipelines", {})

    out = nmt.translate_texts(["hallo", "wereld"], "en", "nl", "Helsinki-NLP/opus-mt-{from}-{to}")
    assert out == ["VERTAALD:hallo", "VERTAALD:wereld"]

    # Tweede batch met hetzelfde taalpaar: het model wordt niet opnieuw geladen.
    nmt.translate_texts(["nogmaals"], "en", "nl", "Helsinki-NLP/opus-mt-{from}-{to}")
    assert created == ["Helsinki-NLP/opus-mt-nl-en"]
