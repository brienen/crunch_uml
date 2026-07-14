"""
Integration tests for the pipeline backend inside I18nRenderer.translate_data.

No network, no Ollama: requests.get is forced to fail (LLM layer disables
itself with a warning) and the termbank fixture drives the deterministic
layer. Covered:

* backend selection via CRUNCH_UML_TRANSLATE_BACKEND=pipeline;
* the i18n file acts as translation memory: existing (section, GUID, field)
  translations are reused and their elements never reach the pipeline;
* an exact termbank hit translates a name without any generation layer;
* untranslatable fields keep their source value (plus warning);
* the output structure is identical to the string-based flow;
* the existing string-based backends are untouched by the new argument.
"""

from __future__ import annotations

import requests

from crunch_uml.renderers.pandasrenderer import I18nRenderer


def _no_ollama(monkeypatch):
    def fail_get(url, timeout=10):
        raise requests.ConnectionError("geen ollama in tests")

    monkeypatch.setattr(requests, "get", fail_get)


def _enable_pipeline(monkeypatch, termbanks="./test/data/termbank_fixture.ttl"):
    monkeypatch.setenv("CRUNCH_UML_TRANSLATE_BACKEND", "pipeline")
    monkeypatch.setenv("CRUNCH_UML_TERMBANKS", termbanks)
    monkeypatch.delenv("CRUNCH_UML_TRANSLATE_ALLOW_ONLINE", raising=False)
    monkeypatch.delenv("CRUNCH_UML_NMT_MODEL", raising=False)
    _no_ollama(monkeypatch)


def test_pipeline_backend_translates_termbank_hits_and_keeps_the_rest(monkeypatch, caplog):
    _enable_pipeline(monkeypatch)
    data = {
        "classes": [
            {"id_1": {"name": "Vergunning"}},
            {"id_2": {"name": "Onbekend Begrip"}},
        ]
    }

    with caplog.at_level("WARNING"):
        out = I18nRenderer().translate_data(data, to_language="en", from_language="nl")

    # Structuur identiek aan de string-gebaseerde flow.
    assert set(out.keys()) == {"classes"}
    assert [list(e.keys()) for e in out["classes"]] == [["id_1"], ["id_2"]]
    # Exacte termbanktreffer deterministisch vertaald, zonder LLM/NMT/online.
    assert out["classes"][0]["id_1"]["name"] == "Permit"
    # Geen generatielaag beschikbaar → origineel behouden + waarschuwing.
    assert out["classes"][1]["id_2"]["name"] == "Onbekend Begrip"
    assert any("konden niet vertaald worden" in m for m in caplog.messages)
    # De preflight meldde de uitgevallen LLM-laag.
    assert any("niet bereikbaar" in m for m in caplog.messages)


def test_pipeline_reuses_existing_i18n_translations(monkeypatch):
    """update_i18n=True: fields already translated in the i18n file are the
    translation memory — they are reused verbatim and the element is not
    offered to the pipeline again."""
    _enable_pipeline(monkeypatch)
    data = {
        "classes": [
            {"id_1": {"name": "Vergunning", "definitie": "Toestemming van de gemeente."}},
        ]
    }
    original_i18n = {
        "en": {
            "classes": [
                {"id_1": {"name": "Authorization", "definitie": "Already reviewed translation."}},
            ]
        }
    }

    out = I18nRenderer().translate_data(
        data, to_language="en", from_language="nl", update_i18n=True, original_i18n=original_i18n
    )

    # De handmatig gereviewde vertaling wint van de termbank ('Permit').
    assert out["classes"][0]["id_1"] == {
        "name": "Authorization",
        "definitie": "Already reviewed translation.",
    }


def test_pipeline_overwrites_when_update_i18n_false(monkeypatch):
    _enable_pipeline(monkeypatch)
    data = {"classes": [{"id_1": {"name": "Vergunning"}}]}
    original_i18n = {"en": {"classes": [{"id_1": {"name": "Authorization"}}]}}

    out = I18nRenderer().translate_data(
        data, to_language="en", from_language="nl", update_i18n=False, original_i18n=original_i18n
    )
    assert out["classes"][0]["id_1"]["name"] == "Permit"


def test_pipeline_assumes_default_source_language_for_auto(monkeypatch, caplog):
    _enable_pipeline(monkeypatch)
    data = {"classes": [{"id_1": {"name": "Vergunning"}}]}

    with caplog.at_level("INFO"):
        out = I18nRenderer().translate_data(data, to_language="en", from_language="auto")

    assert out["classes"][0]["id_1"]["name"] == "Permit"
    assert any("brontaal 'nl' aangenomen" in m.lower() for m in caplog.messages)


def test_str2bool_parses_real_booleans():
    """type=bool was a silent trap: bool("False") is True, so
    '--update_i18n False' meant True and full re-translation was
    impossible via the CLI."""
    import pytest

    from crunch_uml.renderers.renderer import str2bool

    assert str2bool("True") is True and str2bool("true") is True and str2bool("1") is True
    assert str2bool("False") is False and str2bool("no") is False and str2bool("0") is False
    assert str2bool(True) is True and str2bool(False) is False
    with pytest.raises(ValueError):
        str2bool("misschien")


def test_cli_parses_update_i18n_false():
    """The flag must reach args as a real False so render() can trigger a
    full re-translation of one language."""
    import argparse

    from crunch_uml import const, db
    from crunch_uml import schema as sch
    from crunch_uml.parsers import parser as parsers
    from crunch_uml.renderers import renderer as renderers
    from crunch_uml.transformers import transformer as transformers

    p = argparse.ArgumentParser()
    subparsers = p.add_subparsers(dest="command")
    subparser_dict = {
        cmd: subparsers.add_parser(cmd) for cmd in (const.CMD_IMPORT, const.CMD_TRANSFORM, const.CMD_EXPORT)
    }
    db.add_args(p, subparser_dict)
    sch.add_args(p, subparser_dict)
    parsers.add_args(p, subparser_dict)
    renderers.add_args(p, subparser_dict)
    transformers.add_args(p, subparser_dict)

    args = p.parse_args(["export", "-f", "out.json", "-t", "i18n", "--translate", "True", "--update_i18n", "False"])
    assert args.translate is True
    assert args.update_i18n is False


def test_string_backend_still_works_with_schema_argument(monkeypatch):
    """The new schema parameter must not disturb the existing flow."""
    monkeypatch.setenv("CRUNCH_UML_TRANSLATE_BACKEND", "translators")
    import crunch_uml.lang as lang

    monkeypatch.setattr(lang, "translate", lambda value, to_language, from_language="auto", **kw: f"<{value}>")
    data = {"classes": [{"id_1": {"name": "Aap"}}]}

    out = I18nRenderer().translate_data(data, to_language="en", from_language="nl", schema=None)
    assert out["classes"][0]["id_1"]["name"] == "<Aap>"
