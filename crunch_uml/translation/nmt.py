"""Optional NMT safety net (dedicated translation models, no Ollama).

This is the layer *below* the LLM in the cascade: a dedicated neural
translation model (Opus-MT per language pair, or NLLB for broad coverage)
translates fluently in bulk but cannot follow a glossary or disambiguate —
so it only handles what the termbank and LLM layers could not.

The dependency is optional on purpose: ``transformers`` (plus ``torch`` and
``sentencepiece``) is heavy and many installations never need this layer.
When it is missing, :func:`available` returns False and preflight disables
the layer with a warning — nothing here may crash an import.

Configure via ``CRUNCH_UML_NMT_MODEL``; ``{from}``/``{to}`` placeholders are
substituted with the language codes, e.g.::

    export CRUNCH_UML_NMT_MODEL="Helsinki-NLP/opus-mt-{from}-{to}"
"""

from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger()

# Loaded pipelines per resolved model name; a model load is expensive and
# every batch reuses the same language pair.
_pipelines: Dict[str, object] = {}


def available() -> bool:
    """True when the optional 'transformers' dependency is importable."""
    try:
        import transformers  # type: ignore[import-not-found, import-untyped]  # noqa: F401

        return True
    except ImportError:
        return False


def resolve_model_name(template: str, from_lang: str, to_lang: str) -> str:
    """Substitute {from}/{to} placeholders; a fixed name passes through."""
    return template.replace("{from}", from_lang).replace("{to}", to_lang)


def _get_pipeline(model_name: str):
    if model_name not in _pipelines:
        from transformers import (  # type: ignore[import-not-found, import-untyped]
            pipeline,
        )

        logger.info(f"NMT-model '{model_name}' wordt geladen (eenmalig per taalpaar)...")
        _pipelines[model_name] = pipeline("translation", model=model_name)
    return _pipelines[model_name]


def translate_texts(texts: List[str], to_lang: str, from_lang: str, model_template: str) -> List[str]:
    """Translate ``texts`` with the configured NMT model. Raises when the
    optional dependency or the model itself is unavailable; the pipeline
    catches this and degrades."""
    model_name = resolve_model_name(model_template, from_lang, to_lang)
    translator = _get_pipeline(model_name)
    results = translator(texts)  # type: ignore[operator]
    return [r["translation_text"] for r in results]
