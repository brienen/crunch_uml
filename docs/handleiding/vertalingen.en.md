---
title: Translations — i18n export with Ollama LLM
description: >-
  Translate UML models automatically via the external translators API or
  via a locally running LLM (Mistral on Ollama). Preserves camelCase,
  PascalCase and snake_case identifiers, and honours domain acronyms like
  BAG, BRP and GEMMA.
tags:
  - i18n
  - translation
  - ollama
  - mistral
  - llm
  - export
keywords:
  - crunch_uml translations
  - i18n export
  - ollama mistral dutch
  - UML model translation
  - GEMMA terminology
  - local LLM translation
---

# Translations

The `i18n` export format can automatically translate model fields (names,
definitions, notes, GEMMA tags) into a target language. Two backends are
available:

| Backend | When to use |
| --- | --- |
| `translators` (default) | Fast exports with zero setup. Uses Google/Bing endpoints. |
| `ollama` | Higher quality, offline, context-aware. Runs a local LLM (Mistral) via Ollama. |

!!! tip "Casing is preserved automatically"
    A common pitfall with auto-translation: Google turns `aanvangAanwezigheid`
    into "start attendance" and breaks the identifier. crunch_uml detects
    the original casing style and deterministically re-cases the result —
    camelCase, PascalCase, snake_case or kebab-case is kept intact:
    `aanvangAanwezigheid` → `startAttendance`.

## The easy path — external API

```bash
crunch_uml -sch my_model export -t i18n \
    -f my_model.i18n.json \
    --language en --translate True --from_language nl
```

No extra setup. Translations go through Google/Bing and are parallelised
(8 worker threads) with deduplication of identical strings — a GGM-sized
model typically completes within 1-2 minutes.

## The local path — Ollama + Mistral

No rate limits, no outbound traffic, and better quality on domain jargon
(`objecttype`, `attribuutsoort`, `BAG`, `RSGB`, …).

### 1. Install and pull the model

```bash
# Install Ollama — see https://ollama.com
ollama pull mistral-small3.1:24b   # ~14 GB Q4_K_M — recommended default
ollama serve                       # if the daemon is not running yet
```

### 2. Activate the backend

```bash
crunch_uml -sch my_model export -t i18n \
    -f my_model.i18n.json \
    --language en --translate True --from_language nl \
    --translate_backend ollama
```

Or, as an environment variable that holds for the whole session:

```bash
export CRUNCH_UML_TRANSLATE_BACKEND=ollama
crunch_uml -sch my_model export -t i18n -f my_model.i18n.json \
    --language en --translate True --from_language nl
```

If Ollama is unreachable (server down, model not pulled), the renderer
transparently falls back to the external API. A missing Ollama never
breaks an existing pipeline.

## All knobs

Every setting is configurable as a CLI flag **and** as an environment
variable. **CLI wins over env var, env var wins over the default.**

| Setting | CLI flag | Env var | Default |
| --- | --- | --- | --- |
| Backend | `--translate_backend {translators,ollama}` | `CRUNCH_UML_TRANSLATE_BACKEND` | `translators` |
| Model | `--ollama_model TAG` | `CRUNCH_UML_OLLAMA_MODEL` | `mistral-small3.1:24b` |
| Server URL | `--ollama_url URL` | `CRUNCH_UML_OLLAMA_URL` | `http://localhost:11434` |
| Timeout | `--ollama_timeout SEC` | `CRUNCH_UML_OLLAMA_TIMEOUT` | `120` |
| Workers | `--translate_workers N` | `CRUNCH_UML_TRANSLATE_WORKERS` | `8` |
| Context prompt | `--translate_context` | `CRUNCH_UML_TRANSLATE_CONTEXT=1` | off |

### One-liner with CLI only

```bash
crunch_uml -sch my_model export -t i18n -f out.json \
    --language en --translate True --from_language nl \
    --translate_backend ollama \
    --ollama_model mistral-small3.1:24b \
    --translate_workers 8 \
    --translate_context
```

## Which Mistral model?

All three fit comfortably on a Mac with 32 GB+ unified memory; on an M4
with 128 GB even `mistral-large` is fine.

| Tag | Size | Speed on M4 | When |
| --- | --- | --- | --- |
| `mistral-small3.1:24b` ⭐ | ~14 GB | 30-40 tok/s | **Default.** Best balance. |
| `mistral-nemo:12b` | ~7 GB | 50-70 tok/s | Iteration / dev loop. Strong on Dutch thanks to the Tekken tokenizer. |
| `mistral-large:123b` | ~70 GB | 10-15 tok/s | Publication quality. |

Switching takes one env var or CLI flag:

```bash
crunch_uml … --ollama_model mistral-large:123b
```

## Casing is preserved

Many UML model fields are identifiers, not prose. The Ollama backend
instructs the model in its system prompt and applies a deterministic
post-processing step (`reconcile_case`) afterwards.

| Source (NL) | Output (EN) |
| --- | --- |
| `aanvangAanwezigheid` | `startAttendance` |
| `redenWijzigingAdres` | `reasonAddressChange` |
| `Bouwactiviteit` | `ConstructionActivity` |
| `BeschermdeStatus` | `ProtectedStatus` |
| `MigratieIngeschrevenNatuurlijkPersoon` | `MigrationRegisteredNaturalPerson` |
| `datum_opname` | `recording_date` |
| `indicatie_in_onderzoek` | `under_investigation_indication` |
| `gemma-type` | `gemma-type` |
| `BAG`, `BRP`, `RSGB` | unchanged |
| `Het bouwen van een bouwwerk.` | `The construction of a building.` |

Acronyms like BAG, BRP and RSGB are kept unchanged through both the prompt
instructions and the ALL_CAPS detection in the safety net.

## Opaque tokens are protected

Some values have no meaningful translation and previously caused LLM
hallucinations (e.g. "expand `<memo>`" → fictional content). The Ollama
backend short-circuits these patterns entirely — no model call, source
returned verbatim:

* XML/HTML-like single tags: `<memo>`, `<typing>`, `</br>`, `<UML:Class>`
* EA identifiers: `EAID_…`, `EAPK_…`, `EAID_attr_…`
* URLs: `http://…`, `https://…`, `www.…`
* ISO dates and timestamps: `2024-05-13`, `2024-05-13T10:30:00Z`
* Pure punctuation or numbers

## Context-aware translation

With `--translate_context` (or `CRUNCH_UML_TRANSLATE_CONTEXT=1`) the LLM
receives extra hints per call about *where* the string comes from —
e.g. "the 'definitie' field of a classes entry". That improves
consistency on ambiguous terms (e.g. "code" as an attribute name vs. as
an enum value).

Trade-off: with context on, the dedup key becomes
`(value, section, field)` instead of just `value`. Identical strings in
different contexts will be translated separately — smaller dedup, more
API calls.

## `update_i18n` — reuse existing translations

By default (`--update_i18n True`) the renderer reuses translations from a
previous run's i18n file. Only missing fields are translated again. Works
on both backends.

```bash
# First run: translates everything.
crunch_uml … export -t i18n -f mine.i18n.json --language en --translate True

# Second run: reuses existing EN translations, only translates new or
# changed fields.
crunch_uml … export -t i18n -f mine.i18n.json --language en --translate True --update_i18n True
```

## Performance — what to expect

On a Mac M4 with `mistral-small3.1:24b`:

* Short identifier (≤ 5 words): ~0.3 s
* Full definition sentence: ~0.5-1 s
* Spot check on 19 GGM strings: 6.6 s total, 0.35 s per call on average
* `test_16_export_i18n.py` (Monumenten + RSGBPlus): 78 s for the full
  pipeline including i18n export, EA repo update and validations

The external `translators` API is usually slightly faster on short
strings (~0.1 s of network latency), but quality on identifiers and
domain terms is clearly lower.

## Further reading

* [Export command](export.md) — full options for the `export` subcommand.
* [Renderers technical](../technisch/componenten/renderers.md) — how the
  i18n renderer works internally (deduplication, parallel pool, fallback).
