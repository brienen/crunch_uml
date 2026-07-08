"""Capability discovery for the translation pipeline.

Before anything is translated, preflight establishes what is actually
available. Ground rule: every layer checks its own preconditions and
degrades gracefully — a missing or unreadable resource yields a
``logging.warning`` and a disabled layer, never silent wrong output or a
crash. The result is logged as a compact overview: which layers are active,
which sources loaded (with version), and which are disabled and why.

**Ollama.** Reachability via ``GET /api/tags``; the server version via
``GET /api/version`` is compared against ``CRUNCH_UML_OLLAMA_MIN_VERSION``.
Configured model names are *prefixes*: an exact tag match wins, otherwise
the highest locally installed tag starting with the prefix is resolved
(natural version ordering) so minor model upgrades need no config change.
The resolved tag, digest and local pull date are logged — that makes every
run traceable ("this translation was produced by mistral-small3.1:24b,
digest sha256:..."). Honesty note: Ollama cannot tell whether a tag is
outdated *upstream*; the check is limited to local presence, and the local
pull date from the model list is reported for transparency.

**Voting.** With two resolved workhorses the name-voting layer is active;
with one it is disabled (warning: escalation then relies solely on the
deterministic checks); with zero the whole LLM layer is off.

**Termbanks.** Loaded via :mod:`crunch_uml.translation.termbank`; per-source
version/date is read from the data itself and compared against
``CRUNCH_UML_TERMBANK_MAX_AGE_DAYS`` when set. No termbank at all triggers
an emphatic warning that terms will be translated without authoritative
grounding.
"""

from __future__ import annotations

import datetime
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests

from crunch_uml.translation import nmt
from crunch_uml.translation.config import TranslationConfig
from crunch_uml.translation.termbank import SourceReport, TermbankIndex, load_termbanks

logger = logging.getLogger()


@dataclass
class ResolvedModel:
    requested: str  # the configured prefix
    tag: str  # the locally installed tag it resolved to
    digest: str = ""
    pulled_at: str = ""  # local pull date from /api/tags (modified_at)


@dataclass
class LLMStatus:
    enabled: bool = False
    server_version: Optional[str] = None
    workhorses: List[ResolvedModel] = field(default_factory=list)
    heavy: Optional[ResolvedModel] = None
    voting_enabled: bool = False


@dataclass
class PreflightResult:
    config: TranslationConfig
    llm: LLMStatus = field(default_factory=LLMStatus)
    termbank_index: TermbankIndex = field(default_factory=TermbankIndex)
    termbank_reports: List[SourceReport] = field(default_factory=list)
    nmt_enabled: bool = False
    online_enabled: bool = False


def _version_key(text: str) -> Tuple[int, ...]:
    """Natural version key: every number in the string, in order. Makes
    'mistral-small3.2:24b' sort above 'mistral-small3.1:24b'."""
    return tuple(int(n) for n in re.findall(r"\d+", text))


def compare_versions(found: str, minimum: str) -> int:
    """-1 / 0 / 1 for found < / == / > minimum, on numeric components."""
    a, b = _version_key(found), _version_key(minimum)
    return (a > b) - (a < b)


def resolve_model(requested: str, installed: List[Dict]) -> Optional[ResolvedModel]:
    """Resolve a configured model prefix against the locally installed tags.
    Exact tag match first; otherwise the highest tag that starts with the
    prefix. Returns None when nothing matches."""
    by_name = {m.get("name", ""): m for m in installed}
    if requested in by_name:
        m = by_name[requested]
        return ResolvedModel(
            requested=requested, tag=requested, digest=m.get("digest", ""), pulled_at=m.get("modified_at", "")
        )
    matches = sorted(
        (name for name in by_name if name.startswith(requested)),
        key=lambda name: (_version_key(name), name),
    )
    if not matches:
        return None
    tag = matches[-1]
    m = by_name[tag]
    return ResolvedModel(requested=requested, tag=tag, digest=m.get("digest", ""), pulled_at=m.get("modified_at", ""))


def _check_ollama(config: TranslationConfig) -> LLMStatus:
    status = LLMStatus()
    try:
        resp = requests.get(f"{config.ollama_url}/api/tags", timeout=10)
        resp.raise_for_status()
        installed = resp.json().get("models", [])
    except Exception as e:
        logger.warning(f"Ollama-server op {config.ollama_url} is niet bereikbaar ({e}); LLM-laag uitgeschakeld.")
        return status

    try:
        resp = requests.get(f"{config.ollama_url}/api/version", timeout=10)
        resp.raise_for_status()
        status.server_version = resp.json().get("version")
    except Exception:
        logger.warning("Ollama-serverversie kon niet worden bepaald (/api/version).")

    if status.server_version and config.ollama_min_version:
        if compare_versions(status.server_version, config.ollama_min_version) < 0:
            logger.warning(
                f"Ollama-serverversie {status.server_version} is lager dan de geconfigureerde minimumversie"
                f" {config.ollama_min_version}; overweeg een upgrade."
            )

    if not installed:
        logger.warning(
            f"Geen enkel model lokaal aanwezig op {config.ollama_url}; LLM-laag uitgeschakeld."
            f" Installeer een model met: ollama pull {config.workhorses[0]}"
        )
        return status

    for requested in config.workhorses:
        resolved = resolve_model(requested, installed)
        if resolved is None:
            logger.warning(
                f"Werkpaardmodel '{requested}' is niet lokaal aanwezig en wordt niet gebruikt."
                f" Installeer het met: ollama pull {requested}"
            )
            continue
        status.workhorses.append(resolved)

    if config.heavy_model:
        status.heavy = resolve_model(config.heavy_model, installed)
        if status.heavy is None:
            logger.warning(
                f"Zwaar model '{config.heavy_model}' is niet lokaal aanwezig; escalatie valt terug op het"
                f" primaire werkpaard. Installeer het met: ollama pull {config.heavy_model}"
            )

    if not status.workhorses:
        logger.warning("Geen van de geconfigureerde werkpaardmodellen is lokaal aanwezig; LLM-laag uitgeschakeld.")
        return status

    status.enabled = True
    status.voting_enabled = len(status.workhorses) >= 2
    if not status.voting_enabled:
        logger.warning(
            "Slechts één werkpaardmodel beschikbaar: de stemlaag is uitgeschakeld en escalatie naar het"
            " zware model gebeurt alleen nog op de deterministische controles (glossarium-naleving)."
        )
    return status


def _check_termbanks(
    config: TranslationConfig, languages: Optional[set] = None
) -> Tuple[TermbankIndex, List[SourceReport]]:
    index, reports = load_termbanks(config.termbank_paths, languages)

    if config.termbank_max_age_days is not None:
        today = datetime.date.today()
        for report in reports:
            if not report.loaded:
                continue
            source_date = None
            date_source = "datum uit de data"
            if report.date:
                try:
                    source_date = datetime.date.fromisoformat(report.date)
                except ValueError:
                    source_date = None
            if source_date is None and os.path.isfile(report.path):
                # Sommige exports (IATE dca) dragen geen datum in de data;
                # de bestandsdatum (downloadmoment) is dan de beste maat.
                source_date = datetime.date.fromtimestamp(os.path.getmtime(report.path))
                date_source = "bestandsdatum"
            if source_date is None:
                continue
            age = (today - source_date).days
            if age > config.termbank_max_age_days:
                logger.warning(
                    f"Termbank '{report.name}' is {age} dagen oud ({date_source} {source_date}, drempel"
                    f" {config.termbank_max_age_days} dagen); overweeg een nieuwere release."
                )

    if config.termbank_paths and len(index) == 0:
        logger.warning(
            "Geen enkele geconfigureerde termbank kon worden geladen: termen worden vertaald ZONDER"
            " autoritatieve grounding; de pijplijn valt terug op alleen generatie of NMT."
        )
    elif not config.termbank_paths:
        logger.warning(
            "Geen termbanken geconfigureerd (CRUNCH_UML_TERMBANKS is leeg): termen worden vertaald"
            " zonder autoritatieve grounding."
        )
    return index, reports


def _log_summary(result: PreflightResult) -> None:
    """Compact start-of-run overview: active layers, loaded sources with
    version, disabled layers with reason."""
    lines = ["Vertaalpijplijn preflight:"]
    llm = result.llm
    if llm.enabled:
        horses = ", ".join(
            f"{m.tag} (digest {m.digest[:12] or 'onbekend'}, gepulld {m.pulled_at[:10] or 'onbekend'})"
            for m in llm.workhorses
        )
        lines.append(f"  LLM: actief via Ollama {llm.server_version or '?'} — werkpaarden: {horses}")
        if llm.heavy:
            lines.append(f"  Zwaar model: {llm.heavy.tag} (digest {llm.heavy.digest[:12] or 'onbekend'})")
        else:
            lines.append("  Zwaar model: niet beschikbaar — escalatie valt terug op het primaire werkpaard")
        lines.append(f"  Stemlaag: {'actief' if llm.voting_enabled else 'UIT (één werkpaard)'}")
    else:
        lines.append("  LLM: UIT (Ollama onbereikbaar of geen modellen)")
    for report in result.termbank_reports:
        if report.loaded:
            version = report.version or report.date or "versie onbekend"
            lines.append(f"  Termbank {report.name}: {report.concepts} concepten geladen ({version})")
        else:
            lines.append(f"  Termbank {report.name}: UIT ({report.error})")
    if not result.termbank_reports:
        lines.append("  Termbanken: geen geconfigureerd")
    lines.append(f"  NMT-vangnet: {'actief' if result.nmt_enabled else 'uit'}")
    lines.append(f"  Online vangnet (translators): {'toegestaan' if result.online_enabled else 'uit'}")
    logger.info("\n".join(lines))


def run_preflight(config: Optional[TranslationConfig] = None, languages: Optional[set] = None) -> PreflightResult:
    """Run all capability checks and log the overview.

    ``languages`` (bron- plus doeltaal van de run) begrenst welke langSets
    van grote termbanken worden ingeladen; zonder filter wordt alles
    geladen."""
    config = config or TranslationConfig.from_env()
    result = PreflightResult(config=config)

    result.llm = _check_ollama(config)
    result.termbank_index, result.termbank_reports = _check_termbanks(config, languages)

    if config.nmt_model:
        result.nmt_enabled = nmt.available()
        if not result.nmt_enabled:
            logger.warning(
                f"NMT-model '{config.nmt_model}' is geconfigureerd maar de optionele dependency"
                " 'transformers' (met 'sentencepiece' en 'torch') is niet geïnstalleerd; NMT-vangnet uitgeschakeld."
            )
    result.online_enabled = config.allow_online

    if not result.llm.enabled and not result.nmt_enabled and not result.online_enabled:
        logger.warning(
            "Geen enkele vertaallaag met generatiecapaciteit beschikbaar (LLM uit, NMT uit, online uit):"
            " alleen exacte termbanktreffers worden vertaald; overige teksten behouden het origineel."
        )

    _log_summary(result)
    return result
