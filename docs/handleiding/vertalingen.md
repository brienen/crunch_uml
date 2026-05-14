---
title: Vertalingen — i18n export met Ollama LLM
description: >-
  Vertaal UML-modellen automatisch via de externe translators-API of via een
  lokaal draaiend LLM (Mistral via Ollama). Behoudt camelCase, PascalCase en
  snake_case identifiers, en respecteert domeintermen als BAG, BRP en GEMMA.
tags:
  - i18n
  - vertaling
  - ollama
  - mistral
  - llm
  - export
keywords:
  - crunch_uml vertalingen
  - i18n export
  - ollama mistral nederlands
  - UML-model vertalen
  - GEMMA terminologie
  - lokale LLM vertaling
---

# Vertalingen

Het `i18n`-export-formaat kan modelvelden (namen, definities, toelichtingen,
GEMMA-tags) automatisch naar een doeltaal vertalen. Er zijn twee backends:

| Backend | Wanneer kiezen |
| --- | --- |
| `translators` (standaard) | Snelle exports zonder extra setup. Gebruikt Google/Bing endpoints. |
| `ollama` | Hogere kwaliteit, offline, context-bewust. Draait een lokaal LLM (Mistral) via Ollama. |

!!! tip "Casing wordt automatisch behouden"
    Een veel-voorkomende valkuil bij automatisch vertalen: `aanvangAanwezigheid`
    wordt door Google als "start attendance" teruggegeven en breekt zo de
    identifier. Crunch_uml herkent het oorspronkelijke casing-patroon en zet
    het resultaat deterministisch terug in camelCase, PascalCase, snake_case
    of kebab-case. `aanvangAanwezigheid` → `startAttendance`.

## Het simpele pad — externe API

```bash
crunch_uml -sch mijn_model export -t i18n \
    -f mijn_model.i18n.json \
    --language en --translate True --from_language nl
```

Geen extra setup nodig. De vertalingen lopen via Google/Bing en zijn
geparalleliseerd (8 worker threads tegelijk) met deduplicatie van identieke
strings — een GGM-grootte model is doorgaans binnen 1-2 minuten klaar.

## Het lokale pad — Ollama + Mistral

Geen rate-limits, geen netwerkverkeer naar buiten, en betere kwaliteit op
domeinjargon (`objecttype`, `attribuutsoort`, `BAG`, `RSGB`, …).

### 1. Installeer en pull het model

```bash
# Installeer Ollama — zie https://ollama.com
ollama pull mistral-small3.1:24b   # ~14 GB Q4_K_M — aanbevolen default
ollama serve                       # als de daemon nog niet draait
```

### 2. Activeer de backend

```bash
crunch_uml -sch mijn_model export -t i18n \
    -f mijn_model.i18n.json \
    --language en --translate True --from_language nl \
    --translate_backend ollama
```

Of, als environment variable die voor de hele sessie geldt:

```bash
export CRUNCH_UML_TRANSLATE_BACKEND=ollama
crunch_uml -sch mijn_model export -t i18n -f mijn_model.i18n.json \
    --language en --translate True --from_language nl
```

Als Ollama onverhoopt onbereikbaar is (server uit, model niet gepulld), valt
de renderer transparant terug op de externe API. Een ontbrekende Ollama
breekt nooit een bestaande pijplijn.

## Alle knoppen op een rij

Elke instelling kan zowel als CLI-flag als als environment variable. **CLI
heeft voorrang op env-var, env-var op de default.**

| Instelling | CLI-flag | Env-var | Default |
| --- | --- | --- | --- |
| Backend | `--translate_backend {translators,ollama}` | `CRUNCH_UML_TRANSLATE_BACKEND` | `translators` |
| Model | `--ollama_model TAG` | `CRUNCH_UML_OLLAMA_MODEL` | `mistral-small3.1:24b` |
| Server URL | `--ollama_url URL` | `CRUNCH_UML_OLLAMA_URL` | `http://localhost:11434` |
| Timeout | `--ollama_timeout SEC` | `CRUNCH_UML_OLLAMA_TIMEOUT` | `120` |
| Workers | `--translate_workers N` | `CRUNCH_UML_TRANSLATE_WORKERS` | `8` |
| Context-prompt | `--translate_context` | `CRUNCH_UML_TRANSLATE_CONTEXT=1` | uit |

### One-liner met alleen CLI

```bash
crunch_uml -sch mijn_model export -t i18n -f out.json \
    --language en --translate True --from_language nl \
    --translate_backend ollama \
    --ollama_model mistral-small3.1:24b \
    --translate_workers 8 \
    --translate_context
```

## Welk Mistral-model?

Alle drie passen ruim in een Mac met 32 GB+ unified memory; voor een M4 met
128 GB is `mistral-large` ook prima.

| Tag | Grootte | Snelheid op M4 | Wanneer kiezen |
| --- | --- | --- | --- |
| `mistral-small3.1:24b` ⭐ | ~14 GB | 30-40 tok/s | **Default.** Beste balans. |
| `mistral-nemo:12b` | ~7 GB | 50-70 tok/s | Iteratie / dev-loop. Sterk in NL via de Tekken-tokenizer. |
| `mistral-large:123b` | ~70 GB | 10-15 tok/s | Publicatie-kwaliteit. |

Schakelen kost één environment-variable of CLI-flag:

```bash
crunch_uml … --ollama_model mistral-large:123b
```

## Casing wordt behouden

Veel velden in een UML-model zijn identifiers, geen prozaregels. De
Ollama-backend instrueert het model expliciet in zijn system prompt én
herstelt achteraf deterministisch met `reconcile_case`.

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
| `BAG`, `BRP`, `RSGB` | ongewijzigd |
| `Het bouwen van een bouwwerk.` | `The construction of a building.` |

Acroniemen als BAG, BRP en RSGB blijven onveranderd door zowel de prompt-
instructies als de ALL_CAPS-detectie in het vangnet.

## Opake tokens zijn beschermd

Bepaalde waarden hebben geen zinvolle vertaling en zorgden voorheen voor
LLM-hallucinatie (b.v. "expand `<memo>`" → fictieve inhoud). De Ollama-
backend skipt deze patronen volledig — geen model-call, brontekst
verbatim terug:

* XML/HTML-achtige enkelvoudige tags: `<memo>`, `<typing>`, `</br>`, `<UML:Class>`
* EA-identifiers: `EAID_…`, `EAPK_…`, `EAID_attr_…`
* URLs: `http://…`, `https://…`, `www.…`
* ISO-datums en -timestamps: `2024-05-13`, `2024-05-13T10:30:00Z`
* Pure leestekens of cijfers

## Context-bewust vertalen

Met `--translate_context` (of `CRUNCH_UML_TRANSLATE_CONTEXT=1`) krijgt het
LLM per call extra hints over wáár de string vandaan komt — bijvoorbeeld
"the 'definitie' field of a classes entry". Dat verbetert consistentie op
ambigue termen (b.v. "code" als attribuutnaam vs. als enum-waarde).

Belangrijke trade-off: met context aan wordt de dedup-sleutel
`(value, section, field)` in plaats van alleen `value`. Identieke strings
in verschillende contexten worden dus apart vertaald — kleinere dedup,
meer API-calls.

## `update_i18n` — bestaande vertalingen hergebruiken

Standaard (`--update_i18n True`) hergebruikt de renderer al-bestaande
vertalingen uit een vorig run i18n-bestand. Alleen ontbrekende velden
worden opnieuw vertaald. Dit werkt voor beide backends.

```bash
# Eerste run: vertaalt alles.
crunch_uml … export -t i18n -f mijn.i18n.json --language en --translate True

# Tweede run: hergebruikt bestaande EN-vertalingen, vertaalt alleen nieuwe
# of gewijzigde velden.
crunch_uml … export -t i18n -f mijn.i18n.json --language en --translate True --update_i18n True
```

## Prestaties — wat te verwachten

Op een Mac M4 met `mistral-small3.1:24b`:

* Korte identifier (≤ 5 woorden): ~0.3 s
* Volledige definitie-zin: ~0.5-1 s
* Spotcheck op 19 GGM-strings: 6.6 s totaal, gemiddeld 0.35 s per call
* `test_16_export_i18n.py` (Monumenten + RSGBPlus): 78 s totaal voor de hele
  pipeline inclusief i18n-export, EA-repo update en validaties

Met de externe `translators`-API zijn korte strings doorgaans iets sneller
(~0.1 s netwerklatentie), maar de kwaliteit op identifiers en domeintermen
is duidelijk lager.

## Verder lezen

* [Export-commando](export.md) — volledige opties van het `export`-subcommando.
* [Renderers technisch](../technisch/componenten/renderers.md) — hoe de
  i18n-renderer intern werkt (deduplicatie, parallel pool, fallback).
