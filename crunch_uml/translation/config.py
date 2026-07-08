"""Environment-variable configuration for the translation pipeline.

crunch_uml is typically driven from shell scripts, so every setting is an
env-var following the existing ``CRUNCH_UML_*`` pattern (CLI args override
them via ``cli._propagate_translate_args_to_env``). Lists are comma-separated
values inside a single variable — most notably ``CRUNCH_UML_TERMBANKS``,
whose entries are *paths* (files or directories) and whose order defines
source priority.

Model names in ``CRUNCH_UML_LLM_WORKHORSES`` / ``CRUNCH_UML_LLM_HEAVY`` are
**prefixes**: preflight resolves them against the locally installed Ollama
tags (exact match first, otherwise the highest matching version), so minor
model upgrades don't require config changes.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple

logger = logging.getLogger()

# Default workhorse matches the existing single-model Ollama backend so that
# switching CRUNCH_UML_TRANSLATE_BACKEND to "pipeline" works out of the box.
DEFAULT_WORKHORSES = ("mistral-small3.1:24b",)
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_TIMEOUT = 120
# Houd modellen ruim tussen de passes in het geheugen: Ollama's eigen
# default (5m) is korter dan één pass, waardoor het volgende niveau het
# werkpaard opnieuw zou laden. Ollama's scheduler mag altijd evicten als
# het geheugen elders nodig is, dus een lange keep-alive is veilig.
DEFAULT_OLLAMA_KEEP_ALIVE = "60m"
DEFAULT_WORKERS = 8
DEFAULT_SEED = 42

ENV_TERMBANKS = "CRUNCH_UML_TERMBANKS"
ENV_TERMBANK_MAX_AGE_DAYS = "CRUNCH_UML_TERMBANK_MAX_AGE_DAYS"
ENV_LLM_WORKHORSES = "CRUNCH_UML_LLM_WORKHORSES"
ENV_LLM_HEAVY = "CRUNCH_UML_LLM_HEAVY"
ENV_OLLAMA_URL = "CRUNCH_UML_OLLAMA_URL"
ENV_OLLAMA_TIMEOUT = "CRUNCH_UML_OLLAMA_TIMEOUT"
ENV_OLLAMA_MIN_VERSION = "CRUNCH_UML_OLLAMA_MIN_VERSION"
ENV_OLLAMA_KEEP_ALIVE = "CRUNCH_UML_OLLAMA_KEEP_ALIVE"
ENV_NMT_MODEL = "CRUNCH_UML_NMT_MODEL"
ENV_ALLOW_ONLINE = "CRUNCH_UML_TRANSLATE_ALLOW_ONLINE"
ENV_WORKERS = "CRUNCH_UML_TRANSLATE_WORKERS"
ENV_SEED = "CRUNCH_UML_TRANSLATE_SEED"


def _split_csv(raw: Optional[str]) -> Tuple[str, ...]:
    """Split a comma-separated env value into a tuple of stripped entries."""
    if not raw:
        return ()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _int_or_default(raw: Optional[str], default: int, env_name: str) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"Ongeldige waarde '{raw}' voor {env_name}; gebruik default {default}.")
        return default


def _optional_int(raw: Optional[str], env_name: str) -> Optional[int]:
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"Ongeldige waarde '{raw}' voor {env_name}; instelling genegeerd.")
        return None


@dataclass(frozen=True)
class TranslationConfig:
    """All pipeline settings, resolved from the environment."""

    termbank_paths: Tuple[str, ...] = ()
    termbank_max_age_days: Optional[int] = None
    workhorses: Tuple[str, ...] = field(default_factory=lambda: DEFAULT_WORKHORSES)
    heavy_model: Optional[str] = None
    ollama_url: str = DEFAULT_OLLAMA_URL
    ollama_timeout: int = DEFAULT_OLLAMA_TIMEOUT
    ollama_min_version: Optional[str] = None
    ollama_keep_alive: str = DEFAULT_OLLAMA_KEEP_ALIVE
    nmt_model: Optional[str] = None
    allow_online: bool = False
    workers: int = DEFAULT_WORKERS
    seed: int = DEFAULT_SEED

    @classmethod
    def from_env(cls) -> "TranslationConfig":
        workhorses = _split_csv(os.environ.get(ENV_LLM_WORKHORSES))
        if not workhorses:
            workhorses = DEFAULT_WORKHORSES
        heavy = os.environ.get(ENV_LLM_HEAVY, "").strip() or None
        nmt = os.environ.get(ENV_NMT_MODEL, "").strip() or None
        return cls(
            termbank_paths=_split_csv(os.environ.get(ENV_TERMBANKS)),
            termbank_max_age_days=_optional_int(os.environ.get(ENV_TERMBANK_MAX_AGE_DAYS), ENV_TERMBANK_MAX_AGE_DAYS),
            workhorses=workhorses,
            heavy_model=heavy,
            ollama_url=os.environ.get(ENV_OLLAMA_URL, DEFAULT_OLLAMA_URL).rstrip("/"),
            ollama_timeout=_int_or_default(
                os.environ.get(ENV_OLLAMA_TIMEOUT), DEFAULT_OLLAMA_TIMEOUT, ENV_OLLAMA_TIMEOUT
            ),
            ollama_min_version=os.environ.get(ENV_OLLAMA_MIN_VERSION, "").strip() or None,
            ollama_keep_alive=os.environ.get(ENV_OLLAMA_KEEP_ALIVE, "").strip() or DEFAULT_OLLAMA_KEEP_ALIVE,
            nmt_model=nmt,
            allow_online=os.environ.get(ENV_ALLOW_ONLINE, "0").strip() == "1",
            workers=max(1, _int_or_default(os.environ.get(ENV_WORKERS), DEFAULT_WORKERS, ENV_WORKERS)),
            seed=_int_or_default(os.environ.get(ENV_SEED), DEFAULT_SEED, ENV_SEED),
        )
