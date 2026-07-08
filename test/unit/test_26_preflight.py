"""
Tests for crunch_uml.translation.preflight — capability discovery.

All network access is mocked; no Ollama server is contacted. Covered:

* unreachable Ollama → LLM layer disabled with a warning, pipeline continues;
* a missing workhorse model → warning with the exact ``ollama pull`` hint,
  remaining models still resolve;
* prefix resolution picks the highest locally installed tag and carries the
  digest + local pull date (traceability);
* a single workhorse disables the voting layer with a warning;
* a missing heavy model warns and falls back to the primary workhorse;
* server version below the configured minimum warns;
* a stale termbank (older than CRUNCH_UML_TERMBANK_MAX_AGE_DAYS) warns;
* no termbanks at all → emphatic "no authoritative grounding" warning;
* the compact start-of-run summary lists layers, sources and versions.
"""

from __future__ import annotations

from typing import Dict, List

import requests

from crunch_uml.translation import preflight
from crunch_uml.translation.config import TranslationConfig
from crunch_uml.translation.preflight import (
    compare_versions,
    resolve_model,
    run_preflight,
)

TTL_FIXTURE = "./test/data/termbank_fixture.ttl"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _mock_ollama(monkeypatch, models: List[Dict], version: str = "0.9.0"):
    def fake_get(url, timeout=10):
        if url.endswith("/api/tags"):
            return FakeResponse({"models": models})
        if url.endswith("/api/version"):
            return FakeResponse({"version": version})
        raise AssertionError(f"onverwachte GET {url}")

    monkeypatch.setattr(requests, "get", fake_get)


MODELS = [
    {"name": "mistral-small3.1:24b", "digest": "sha256:aaa111", "modified_at": "2026-06-01T10:00:00Z"},
    {"name": "mistral-small3.2:24b", "digest": "sha256:bbb222", "modified_at": "2026-07-01T10:00:00Z"},
    {"name": "qwen2.5:14b", "digest": "sha256:ccc333", "modified_at": "2026-05-15T10:00:00Z"},
]


def _config(**overrides):
    defaults = dict(
        termbank_paths=(),
        workhorses=("mistral-small3.1:24b", "qwen2.5:14b"),
        heavy_model=None,
        ollama_url="http://localhost:11434",
    )
    defaults.update(overrides)
    return TranslationConfig(**defaults)


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------


def test_resolve_model_exact_tag_wins():
    resolved = resolve_model("mistral-small3.1:24b", MODELS)
    assert resolved.tag == "mistral-small3.1:24b"
    assert resolved.digest == "sha256:aaa111"
    assert resolved.pulled_at.startswith("2026-06-01")


def test_resolve_model_prefix_picks_highest_version():
    """Configured as prefix 'mistral-small': the highest installed tag wins,
    so a minor upgrade (3.1 → 3.2) is picked up without config changes."""
    resolved = resolve_model("mistral-small", MODELS)
    assert resolved.tag == "mistral-small3.2:24b"
    assert resolved.digest == "sha256:bbb222"


def test_resolve_model_unknown_returns_none():
    assert resolve_model("llama3.1:70b", MODELS) is None


def test_compare_versions_numeric_components():
    assert compare_versions("0.9.0", "0.5.0") > 0
    assert compare_versions("0.5.0", "0.5.0") == 0
    assert compare_versions("0.4.9", "0.5.0") < 0


# ---------------------------------------------------------------------------
# Ollama preflight
# ---------------------------------------------------------------------------


def test_unreachable_ollama_disables_llm_with_warning(monkeypatch, caplog):
    def fail_get(url, timeout=10):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "get", fail_get)
    with caplog.at_level("WARNING"):
        result = run_preflight(_config())

    assert not result.llm.enabled
    assert any("niet bereikbaar" in m and "LLM-laag uitgeschakeld" in m for m in caplog.messages)


def test_missing_workhorse_warns_with_pull_instruction_and_continues(monkeypatch, caplog):
    _mock_ollama(monkeypatch, MODELS)
    with caplog.at_level("WARNING"):
        result = run_preflight(_config(workhorses=("niet-bestaand:7b", "qwen2.5:14b")))

    assert result.llm.enabled  # het tweede werkpaard is er wel
    assert [m.tag for m in result.llm.workhorses] == ["qwen2.5:14b"]
    assert any("ollama pull niet-bestaand:7b" in m for m in caplog.messages)


def test_single_workhorse_disables_voting_with_warning(monkeypatch, caplog):
    _mock_ollama(monkeypatch, MODELS)
    with caplog.at_level("WARNING"):
        result = run_preflight(_config(workhorses=("qwen2.5:14b",)))

    assert result.llm.enabled
    assert not result.llm.voting_enabled
    assert any("stemlaag is uitgeschakeld" in m for m in caplog.messages)


def test_two_workhorses_enable_voting(monkeypatch):
    _mock_ollama(monkeypatch, MODELS)
    result = run_preflight(_config())
    assert result.llm.voting_enabled


def test_missing_heavy_model_warns_and_falls_back(monkeypatch, caplog):
    _mock_ollama(monkeypatch, MODELS)
    with caplog.at_level("WARNING"):
        result = run_preflight(_config(heavy_model="qwen2.5:72b"))

    assert result.llm.enabled
    assert result.llm.heavy is None
    assert any("valt terug op het" in m and "ollama pull qwen2.5:72b" in m for m in caplog.messages)


def test_old_server_version_warns(monkeypatch, caplog):
    _mock_ollama(monkeypatch, MODELS, version="0.4.0")
    with caplog.at_level("WARNING"):
        result = run_preflight(_config(ollama_min_version="0.5.0"))
    assert result.llm.server_version == "0.4.0"
    assert any("lager dan de geconfigureerde minimumversie" in m for m in caplog.messages)


def test_no_models_installed_disables_llm(monkeypatch, caplog):
    _mock_ollama(monkeypatch, [])
    with caplog.at_level("WARNING"):
        result = run_preflight(_config())
    assert not result.llm.enabled
    assert any("Geen enkel model lokaal aanwezig" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# Termbank preflight
# ---------------------------------------------------------------------------


def test_missing_termbank_warns_and_pipeline_continues(monkeypatch, caplog):
    _mock_ollama(monkeypatch, MODELS)
    with caplog.at_level("WARNING"):
        result = run_preflight(_config(termbank_paths=("./bestaat/niet.ttl", TTL_FIXTURE)))

    # De ontbrekende bron is gemeld, de goede bron is geladen.
    assert any("bestaat niet" in m for m in caplog.messages)
    assert len(result.termbank_index) > 0
    assert [r.loaded for r in result.termbank_reports] == [False, True]


def test_stale_termbank_warns(monkeypatch, caplog):
    """The .ttl fixture carries dcterms:modified 2020-01-15 — far older than
    the 365-day threshold."""
    _mock_ollama(monkeypatch, MODELS)
    with caplog.at_level("WARNING"):
        run_preflight(_config(termbank_paths=(TTL_FIXTURE,), termbank_max_age_days=365))
    assert any("dagen oud" in m and "termbank_fixture" in m for m in caplog.messages)


def test_termbank_without_embedded_date_falls_back_to_file_mtime(monkeypatch, caplog, tmp_path):
    """The IATE dca export carries no date in its header: the age check must
    fall back to the file's modification time (the download moment)."""
    import os
    import shutil

    old_file = tmp_path / "iate_zonder_datum.tbx"
    shutil.copy("./test/data/termbank_fixture.tbx", old_file)
    # Strip de datum uit de header zodat alleen de bestandsdatum overblijft.
    content = old_file.read_text().replace("2019-06-30", "eergisteren")
    old_file.write_text(content)
    two_years_ago = 2 * 365 * 24 * 3600
    os.utime(old_file, (os.path.getmtime(old_file) - two_years_ago,) * 2)

    _mock_ollama(monkeypatch, MODELS)
    with caplog.at_level("WARNING"):
        run_preflight(_config(termbank_paths=(str(old_file),), termbank_max_age_days=365))
    assert any("bestandsdatum" in m and "dagen oud" in m for m in caplog.messages)


def test_fresh_enough_termbank_does_not_warn_about_age(monkeypatch, caplog):
    _mock_ollama(monkeypatch, MODELS)
    with caplog.at_level("WARNING"):
        run_preflight(_config(termbank_paths=(TTL_FIXTURE,), termbank_max_age_days=100000))
    assert not any("dagen oud" in m for m in caplog.messages)


def test_no_termbanks_at_all_warns_about_grounding(monkeypatch, caplog):
    _mock_ollama(monkeypatch, MODELS)
    with caplog.at_level("WARNING"):
        run_preflight(_config(termbank_paths=()))
    assert any("zonder autoritatieve grounding" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# NMT + summary
# ---------------------------------------------------------------------------


def test_nmt_configured_but_not_installed_warns(monkeypatch, caplog):
    _mock_ollama(monkeypatch, MODELS)
    monkeypatch.setattr(preflight.nmt, "available", lambda: False)
    with caplog.at_level("WARNING"):
        result = run_preflight(_config(nmt_model="Helsinki-NLP/opus-mt-{from}-{to}"))
    assert not result.nmt_enabled
    assert any("transformers" in m and "uitgeschakeld" in m for m in caplog.messages)


def test_nothing_available_warns_emphatically(monkeypatch, caplog):
    def fail_get(url, timeout=10):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests, "get", fail_get)
    with caplog.at_level("WARNING"):
        run_preflight(_config(allow_online=False))
    assert any("Geen enkele vertaallaag met generatiecapaciteit" in m for m in caplog.messages)


def test_summary_reports_layers_sources_and_versions(monkeypatch, caplog):
    _mock_ollama(monkeypatch, MODELS)
    with caplog.at_level("INFO"):
        run_preflight(_config(termbank_paths=(TTL_FIXTURE,), heavy_model="mistral-small"))

    summary = next(m for m in caplog.messages if m.startswith("Vertaalpijplijn preflight:"))
    assert "werkpaarden: mistral-small3.1:24b" in summary
    assert "qwen2.5:14b" in summary
    assert "sha256:aaa11" in summary  # digest (afgekort) voor traceerbaarheid
    assert "Zwaar model: mistral-small3.2:24b" in summary  # prefix → hoogste tag
    assert "Stemlaag: actief" in summary
    assert "termbank_fixture: 7 concepten geladen (4.22)" in summary
    assert "Online vangnet (translators): uit" in summary
