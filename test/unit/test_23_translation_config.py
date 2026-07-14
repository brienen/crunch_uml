"""
Tests for crunch_uml.translation.config — env-var based pipeline settings.

Every setting must be resolvable from ``CRUNCH_UML_*`` variables alone (no
config files); unset variables fall back to documented defaults, and invalid
numeric values degrade to the default with a warning instead of crashing.
"""

from __future__ import annotations

from crunch_uml.translation import config as cfg


def _clean_env(monkeypatch):
    for var in (
        cfg.ENV_TERMBANKS,
        cfg.ENV_TERMBANK_MAX_AGE_DAYS,
        cfg.ENV_LLM_WORKHORSES,
        cfg.ENV_LLM_HEAVY,
        cfg.ENV_OLLAMA_URL,
        cfg.ENV_OLLAMA_TIMEOUT,
        cfg.ENV_OLLAMA_MIN_VERSION,
        cfg.ENV_NMT_MODEL,
        cfg.ENV_ALLOW_ONLINE,
        cfg.ENV_WORKERS,
        cfg.ENV_SEED,
    ):
        monkeypatch.delenv(var, raising=False)


def test_defaults_when_no_env_set(monkeypatch):
    _clean_env(monkeypatch)
    c = cfg.TranslationConfig.from_env()

    assert c.termbank_paths == ()
    assert c.termbank_max_age_days is None
    assert c.workhorses == cfg.DEFAULT_WORKHORSES
    assert c.heavy_model is None
    assert c.ollama_url == cfg.DEFAULT_OLLAMA_URL
    assert c.ollama_timeout == cfg.DEFAULT_OLLAMA_TIMEOUT
    assert c.ollama_min_version is None
    assert c.nmt_model is None
    assert c.allow_online is False
    assert c.workers == cfg.DEFAULT_WORKERS
    assert c.seed == cfg.DEFAULT_SEED


def test_termbanks_is_a_single_list_of_paths(monkeypatch):
    """CRUNCH_UML_TERMBANKS holds the paths themselves, comma-separated;
    order is preserved because order = priority. Whitespace is stripped and
    empty entries are dropped."""
    _clean_env(monkeypatch)
    monkeypatch.setenv(cfg.ENV_TERMBANKS, " a/gemma.ttl , b/lod/ ,, c/iate.tbx ")
    c = cfg.TranslationConfig.from_env()
    assert c.termbank_paths == ("a/gemma.ttl", "b/lod/", "c/iate.tbx")


def test_llm_roles_workhorses_and_heavy(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv(cfg.ENV_LLM_WORKHORSES, "qwen2.5:14b, mistral-small")
    monkeypatch.setenv(cfg.ENV_LLM_HEAVY, "qwen2.5:32b")
    c = cfg.TranslationConfig.from_env()
    assert c.workhorses == ("qwen2.5:14b", "mistral-small")
    assert c.heavy_model == "qwen2.5:32b"


def test_empty_workhorses_falls_back_to_default(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv(cfg.ENV_LLM_WORKHORSES, "  ,  ")
    c = cfg.TranslationConfig.from_env()
    assert c.workhorses == cfg.DEFAULT_WORKHORSES


def test_numeric_settings_and_online_flag(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv(cfg.ENV_TERMBANK_MAX_AGE_DAYS, "365")
    monkeypatch.setenv(cfg.ENV_OLLAMA_TIMEOUT, "30")
    monkeypatch.setenv(cfg.ENV_WORKERS, "4")
    monkeypatch.setenv(cfg.ENV_SEED, "7")
    monkeypatch.setenv(cfg.ENV_ALLOW_ONLINE, "1")
    c = cfg.TranslationConfig.from_env()
    assert c.termbank_max_age_days == 365
    assert c.ollama_timeout == 30
    assert c.workers == 4
    assert c.seed == 7
    assert c.allow_online is True


def test_invalid_numbers_degrade_with_warning(monkeypatch, caplog):
    """Broken numeric values must not crash a batch run: fall back to the
    default (or drop the optional setting) and warn."""
    _clean_env(monkeypatch)
    monkeypatch.setenv(cfg.ENV_OLLAMA_TIMEOUT, "not-a-number")
    monkeypatch.setenv(cfg.ENV_TERMBANK_MAX_AGE_DAYS, "soon")
    with caplog.at_level("WARNING"):
        c = cfg.TranslationConfig.from_env()
    assert c.ollama_timeout == cfg.DEFAULT_OLLAMA_TIMEOUT
    assert c.termbank_max_age_days is None
    assert sum("Ongeldige waarde" in m for m in caplog.messages) == 2


def test_ollama_url_trailing_slash_is_stripped(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv(cfg.ENV_OLLAMA_URL, "http://gpu-box:11434/")
    c = cfg.TranslationConfig.from_env()
    assert c.ollama_url == "http://gpu-box:11434"
