"""Cascade orchestration for the translation pipeline.

The pipeline translates *model elements* (not loose strings), level by
level, root to leaves:

1. **packages** — few elements, full treatment;
2. **classes / enumerations** — their glossary includes the package and
   model translations fixed in level 1;
3. **attributes / enumeration literals / everything else** — their glossary
   additionally includes the class names fixed in level 2.

Every level feeds the binding glossary of the level below, so an attribute
definition mentioning "de bouwactiviteit" uses the same translation as the
class ``Bouwactiviteit``. Within a level the work runs in *passes* — one
model over the whole batch before the next model starts — because Ollama
swaps models in and out of VRAM: interleaving two models per element would
thrash.

Per element the cascade is:

* termbank candidates for the name, deterministically disambiguated on the
  source definition and domain context → an unambiguous hit fixes the name
  translation without any model (the concept URI is logged);
* the LLM translates the remaining fields in one JSON call (workhorse A),
  with workhorse B as an independent second vote on the *name*; the two
  agreeing → accepted, disagreeing → the heavy model arbitrates with both
  candidates in the prompt. Definitions are checked deterministically
  against the glossary instead (voting cannot work there) and escalate on
  violation;
* no LLM → the optional NMT safety net; no NMT → online services, **only**
  when explicitly allowed; otherwise the source value is kept and counted
  in a warning.

Determinism: same input + same sources + same (logged) model digests →
same output. There is no agent loop; this is a batch pipeline.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

from crunch_uml.ollama_translator import reconcile_case
from crunch_uml.translation.disambiguate import disambiguate
from crunch_uml.translation.llm import (
    NAME_FIELDS,
    Element,
    _term_in_text,
    glossary_violations,
    names_agree,
    translate_element_once,
)
from crunch_uml.translation.preflight import PreflightResult

logger = logging.getLogger()

# Hierarchy levels: sections not listed run in the last level.
LEVELS: Tuple[Tuple[str, ...], ...] = (
    ("packages",),
    ("classes", "enumerations"),
)

# Definition-like fields get the deterministic glossary-compliance check.
DEFINITION_FIELDS = ("definitie", "toelichting", "src_documentation", "dst_documentation")

# Cap the per-element glossary so prompts stay compact; entries are chosen
# deterministically (only terms that occur in the element's source text,
# sorted alphabetically).
MAX_GLOSSARY_ENTRIES = 30

ResultKey = Tuple[str, str]  # (section, key)

# Transport errors (timeouts, refused connections) get retries with backoff:
# a busy Ollama server recovers, and a silently failed element would end up
# with its Dutch source text stamped into the i18n file as "translation".
LLM_ATTEMPTS = 3
LLM_RETRY_BACKOFF_SECONDS = 10


def _level_of(section: str) -> int:
    for i, sections in enumerate(LEVELS):
        if section in sections:
            return i
    return len(LEVELS)


class TranslationPipeline:
    """Batch translation of Elements according to the preflight capabilities."""

    def __init__(self, preflight: PreflightResult):
        self.preflight = preflight
        self.config = preflight.config
        # Accumulated name translations from higher levels: src name -> tgt.
        self.global_glossary: Dict[str, str] = {}

    # -- glossary ----------------------------------------------------------

    def _element_glossary(self, element: Element, fixed: Dict[str, str]) -> Dict[str, str]:
        """The binding glossary for one element: accumulated translations
        whose source term actually occurs in the element's source text, plus
        the element's own deterministically fixed name."""
        source_text = " ".join(element.fields.values())
        entries = {src: tgt for src, tgt in self.global_glossary.items() if _term_in_text(src, source_text)}
        if len(entries) > MAX_GLOSSARY_ENTRIES:
            entries = dict(sorted(entries.items())[:MAX_GLOSSARY_ENTRIES])
        name = element.fields.get("name")
        if name and "name" in fixed:
            entries[name] = fixed["name"]
        return entries

    # -- deterministic term layer ------------------------------------------

    def _fix_names_via_termbank(self, element: Element, to_language: str, from_language: str) -> Dict[str, str]:
        """Termbank lookup + deterministic disambiguation for the element
        name. Returns the fields that are hereby fixed (no model involved)."""
        fixed: Dict[str, str] = {}
        name = element.fields.get("name")
        if not name or len(self.preflight.termbank_index) == 0:
            return fixed
        candidates = self.preflight.termbank_index.lookup(name, from_lang=from_language, to_lang=to_language)
        element.candidates = candidates
        if not candidates:
            return fixed
        context_terms = [v for k, v in element.context.items() if k in ("model", "package", "parent") and v]
        chosen = disambiguate(
            candidates,
            source_definition=element.fields.get("definitie"),
            context_terms=context_terms,
        )
        if chosen is not None:
            fixed["name"] = reconcile_case(name, chosen.term)
            logger.info(
                f"Term '{name}' deterministisch vertaald als '{fixed['name']}' via {chosen.source}" f" ({chosen.uri})"
            )
        return fixed

    # -- LLM passes ----------------------------------------------------------

    def _llm_pass(
        self,
        elements: List[Element],
        pending: Dict[ResultKey, Dict[str, str]],
        glossaries: Dict[ResultKey, Dict[str, str]],
        model_tag: str,
        to_language: str,
        from_language: str,
        label: str,
    ) -> Dict[ResultKey, Dict[str, str]]:
        """One model over the whole batch (see module docstring on passes)."""
        total = len(elements)
        logger.info(f"LLM-pass '{label}' ({model_tag}): {total} elementen...")

        def _one(indexed: Tuple[int, Element]) -> Dict[str, str]:
            i, element = indexed
            key = (element.section, element.key)
            sub_element = Element(
                section=element.section,
                key=element.key,
                fields=pending[key],
                context=element.context,
                candidates=element.candidates,
            )
            result: Dict[str, str] = dict(pending[key])  # fallback: bronwaarden
            for attempt in range(1, LLM_ATTEMPTS + 1):
                try:
                    result = translate_element_once(
                        sub_element,
                        to_language,
                        from_language,
                        model=model_tag,
                        config=self.config,
                        glossary=glossaries[key],
                    )
                    break
                except Exception as e:
                    if attempt < LLM_ATTEMPTS:
                        wait = LLM_RETRY_BACKOFF_SECONDS * attempt
                        logger.warning(
                            f"LLM-call ({label}) voor {element.section}/{element.key} mislukt bij poging"
                            f" {attempt}/{LLM_ATTEMPTS} ({e}); nieuwe poging over {wait}s..."
                        )
                        time.sleep(wait)
                    else:
                        logger.warning(
                            f"LLM-call ({label}) voor {element.section}/{element.key} definitief mislukt na"
                            f" {LLM_ATTEMPTS} pogingen ({e}); bronwaarden behouden."
                        )
            logger.info(f"[{i + 1}/{total}] ({label}) {element.section}/{element.key} vertaald")
            return result

        with ThreadPoolExecutor(max_workers=self.config.workers) as pool:
            results = list(pool.map(_one, enumerate(elements)))
        return {(e.section, e.key): r for e, r in zip(elements, results)}

    def _translate_level_with_llm(
        self,
        elements: List[Element],
        pending: Dict[ResultKey, Dict[str, str]],
        glossaries: Dict[ResultKey, Dict[str, str]],
        to_language: str,
        from_language: str,
    ) -> Dict[ResultKey, Dict[str, str]]:
        llm_status = self.preflight.llm
        primary = llm_status.workhorses[0].tag
        results = self._llm_pass(
            elements, pending, glossaries, primary, to_language, from_language, label="werkpaard-1"
        )

        # Independent second vote on names.
        escalate: Dict[ResultKey, str] = {}  # key -> reden
        if llm_status.voting_enabled:
            second = llm_status.workhorses[1].tag
            vote_elements = [e for e in elements if "name" in pending[(e.section, e.key)]]
            if vote_elements:
                second_results = self._llm_pass(
                    vote_elements, pending, glossaries, second, to_language, from_language, label="werkpaard-2"
                )
                for element in vote_elements:
                    key = (element.section, element.key)
                    if not names_agree(results[key].get("name"), second_results[key].get("name")):
                        escalate[key] = (
                            f"werkpaarden oneens over naam: '{results[key].get('name')}' vs"
                            f" '{second_results[key].get('name')}'"
                        )

        # Deterministic glossary compliance on definition-like fields.
        for element in elements:
            key = (element.section, element.key)
            if key in escalate:
                continue
            for field_name in DEFINITION_FIELDS:
                if field_name not in pending[key]:
                    continue
                violations = glossary_violations(
                    pending[key][field_name], results[key].get(field_name, ""), glossaries[key]
                )
                if violations:
                    escalate[key] = f"glossarium geschonden in '{field_name}': {violations}"
                    break

        if escalate:
            by_key = {(e.section, e.key): e for e in elements}
            hard_cases = [by_key[k] for k in escalate]
            for key, reason in escalate.items():
                logger.info(f"Escalatie {key[0]}/{key[1]}: {reason}")
            if llm_status.heavy is not None:
                heavy_results = self._llm_pass(
                    hard_cases,
                    pending,
                    glossaries,
                    llm_status.heavy.tag,
                    to_language,
                    from_language,
                    label="zwaar-model",
                )
                results.update(heavy_results)
            else:
                logger.warning(
                    f"{len(escalate)} moeilijke gevallen gedetecteerd maar geen zwaar model beschikbaar;"
                    " resultaat van het primaire werkpaard wordt gebruikt."
                )
        return results

    # -- fallbacks -----------------------------------------------------------

    def _translate_level_with_nmt(
        self, pending: Dict[ResultKey, Dict[str, str]], to_language: str, from_language: str
    ) -> Dict[ResultKey, Dict[str, str]]:
        from crunch_uml.translation import nmt

        flat: List[Tuple[ResultKey, str, str]] = [
            (key, field_name, value) for key, fields in pending.items() for field_name, value in fields.items()
        ]
        try:
            translated = nmt.translate_texts(
                [value for _, _, value in flat], to_language, from_language, self.config.nmt_model or ""
            )
        except Exception as e:
            logger.warning(f"NMT-vertaling mislukt ({e}); bronwaarden behouden.")
            return {key: dict(fields) for key, fields in pending.items()}
        results: Dict[ResultKey, Dict[str, str]] = {key: {} for key in pending}
        for (key, field_name, source_value), value in zip(flat, translated):
            if field_name in NAME_FIELDS:
                value = reconcile_case(source_value, value)
            results[key][field_name] = value
        return results

    def _translate_level_online(
        self, pending: Dict[ResultKey, Dict[str, str]], to_language: str, from_language: str
    ) -> Dict[ResultKey, Dict[str, str]]:
        from crunch_uml import lang

        results: Dict[ResultKey, Dict[str, str]] = {}
        for key, fields in pending.items():
            results[key] = {
                field_name: lang.translate(value, to_language, from_language, max_retries=1)
                for field_name, value in fields.items()
            }
        return results

    # -- main entry ----------------------------------------------------------

    def translate_elements(
        self, elements: List[Element], to_language: str, from_language: str
    ) -> Dict[ResultKey, Dict[str, str]]:
        """Translate all elements, level by level. Returns the translated
        fields per (section, key)."""
        all_results: Dict[ResultKey, Dict[str, str]] = {}
        untranslated = 0

        level_count = len(LEVELS) + 1
        for level in range(level_count):
            level_elements = [e for e in elements if _level_of(e.section) == level]
            if not level_elements:
                continue
            sections = sorted({e.section for e in level_elements})
            logger.info(
                f"Vertaalniveau {level + 1}/{level_count} ({', '.join(sections)}): {len(level_elements)} elementen"
            )

            fixed_per_element: Dict[ResultKey, Dict[str, str]] = {}
            pending: Dict[ResultKey, Dict[str, str]] = {}
            glossaries: Dict[ResultKey, Dict[str, str]] = {}
            for element in level_elements:
                key = (element.section, element.key)
                fixed = self._fix_names_via_termbank(element, to_language, from_language)
                fixed_per_element[key] = fixed
                glossaries[key] = self._element_glossary(element, fixed)
                pending[key] = {f: v for f, v in element.fields.items() if f not in fixed}

            with_pending = [e for e in level_elements if pending[(e.section, e.key)]]
            pending_only = {k: v for k, v in pending.items() if v}

            if with_pending:
                if self.preflight.llm.enabled:
                    llm_results = self._translate_level_with_llm(
                        with_pending, pending_only, glossaries, to_language, from_language
                    )
                elif self.preflight.nmt_enabled:
                    llm_results = self._translate_level_with_nmt(pending_only, to_language, from_language)
                elif self.preflight.online_enabled:
                    llm_results = self._translate_level_online(pending_only, to_language, from_language)
                else:
                    llm_results = {key: dict(fields) for key, fields in pending_only.items()}
                    untranslated += sum(len(fields) for fields in pending_only.values())
            else:
                llm_results = {}

            for element in level_elements:
                key = (element.section, element.key)
                merged = dict(element.fields)
                merged.update(llm_results.get(key, {}))
                merged.update(fixed_per_element[key])
                all_results[key] = merged
                # Fixed and generated names feed the glossary of deeper levels.
                src_name = element.fields.get("name")
                tgt_name = merged.get("name")
                if src_name and tgt_name and src_name != tgt_name:
                    self.global_glossary.setdefault(src_name, tgt_name)

        if untranslated:
            logger.warning(
                f"{untranslated} velden konden niet vertaald worden (geen LLM, NMT of online vangnet"
                " beschikbaar) en behouden hun oorspronkelijke waarde."
            )
        return all_results
