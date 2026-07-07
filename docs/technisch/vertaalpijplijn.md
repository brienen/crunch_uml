# Vertaalpijplijn — technisch ontwerp

Dit document is de definitieve specificatie van de gelaagde, deterministische
vertaalpijplijn (backend `pipeline`) die losse termen én korte definities uit
UML-informatiemodellen vertaalt. Officiële terminologie (IATE, EuroVoc, eigen
begrippenkaders als LOD) is de basis; de context uit het bronmodel bepaalt de
betekenis. Reproduceerbaarheid is een harde eis: dezelfde input plus dezelfde
bronnen plus hetzelfde (gelogde) model geeft altijd dezelfde output.

## Uitgangspunten en genomen besluiten

1. **Geen aparte cache (geen SQLite).** Het i18n-uitvoerbestand ís het
   vertaalgeheugen: bestaande vertalingen per `(sectie, GUID, veld)` worden
   hergebruikt en nooit opnieuw vertaald (`update_i18n=True`). Die sleutel is
   sterker dan een stringsleutel — de GUID identificeert het exacte
   modelelement, dus homoniemen kunnen elkaar niet besmetten. Het bestand is
   bovendien reviewbaar en versioneerbaar in git. Een tweede opslagplaats zou
   een tweede bron van waarheid zijn die kan verouderen en stilletjes
   verkeerde vertalingen serveert.
2. **Configuratie uitsluitend via omgevingsvariabelen** (patroon
   `CRUNCH_UML_*`, met CLI-args als override). Geen configbestanden: crunch
   wordt vanuit scripts aangeroepen.
3. **Vertalen per modelelement, niet per string.** Alle vertaalbare velden
   van één element (`name`, `alias`, `definitie`, `toelichting`, …) gaan in
   één gestructureerde JSON-call. De definitie disambigueert de term en de
   gekozen term wordt gegarandeerd consistent gebruikt in de vertaalde
   definitie.
4. **Hiërarchische volgorde met glossarium-doorgifte.** Eerst pakketten, dan
   klassen/enumeraties, dan attributen/enumeratiewaarden. Elke laag legt zijn
   naamvertalingen vast in het bindende glossarium van de laag eronder, zodat
   een attribuutdefinitie die "de bouwactiviteit" noemt dezelfde vertaling
   gebruikt als de klasse `Bouwactiviteit`.
5. **Twee werkpaarden en een zwaar model.** De werkpaarden vertalen
   onafhankelijk (zelfde glossarium); komen de namen na normalisatie overeen
   dan is het resultaat geaccepteerd. Onenigheid ís de definitie van een
   moeilijk geval en gaat naar het zware model, met beide kandidaten in de
   prompt. Voor definities werkt stemmen niet (twee LLM's formuleren nooit
   letterlijk gelijk); daar geldt het primaire werkpaard plus een
   *deterministische* glossarium-nalevingscheck, met escalatie bij schending.
   Met één geconfigureerd werkpaard gaat de stemlaag uit (waarschuwing) en
   escaleren alleen de deterministische checks.
6. **Passes, geen interleaving.** Ollama wisselt modellen in en uit het
   VRAM; om en om bevragen betekent swappen. Daarom per niveau: werkpaard A
   over de hele batch, dan werkpaard B, dan vergelijken, dan het zware model
   alleen over de meningsverschillen.
7. **Online diensten (Google/Bing via `translators`) zijn opt-in** en nooit
   default: ze zijn niet reproduceerbaar.

## Cascade

```
                    ┌──────────────────────────────────────────────┐
                    │ 0. Preflight (capability discovery)          │
                    └──────────────────┬───────────────────────────┘
                                       ▼
 i18n-bestand ──▶ 1. Hergebruik per (sectie, GUID, veld)   [bestaand gedrag]
                                       ▼ (alleen ontbrekende velden)
 termbanken  ──▶ 2. Kandidaten (exact, dan fuzzy) per naam
                                       ▼
                 3. Deterministische disambiguatie op brondefinitie + domein
                      │ eenduidig → naamvertaling ligt vast (met concept-URI)
                      ▼ meervoudig/geen
                 4. LLM per element (JSON, temp 0, glossarium bindend)
                      werkpaard A ─ werkpaard B ─ [onenigheid] → zwaar model
                                       ▼ (LLM niet beschikbaar)
                 5. NMT-vangnet (optionele dependency, bv. Opus-MT)
                                       ▼ (NMT niet beschikbaar)
                 6. Online (translators) — alleen als expliciet toegestaan
                                       ▼ (niets beschikbaar)
                    origineel behouden + waarschuwing
```

NMT is bewust het vangnet *onder* de LLM en geen escalatiepad erboven:
dedicated vertaalmodellen kunnen geen glossarium volgen of disambigueren.

## Preflight

Elke laag controleert zijn eigen randvoorwaarden en degradeert netjes: een
ontbrekende of onleesbare resource geeft een `logging.warning` en het
overslaan van die laag — nooit stille verkeerde output of een crash. Bij de
start wordt een compact overzicht gelogd: actieve lagen, geladen bronnen met
versie, uitgeschakelde lagen met reden.

**Ollama**

- Bereikbaarheid via `GET /api/tags`; onbereikbaar → LLM-laag uit, waarschuwing.
- Serverversie via `GET /api/version`, vergeleken met
  `CRUNCH_UML_OLLAMA_MIN_VERSION` (waarschuwing indien lager).
- Modelresolutie per rol: een geconfigureerde waarde is een **prefix**.
  Exacte tag wint; anders de hoogste lokaal geïnstalleerde tag die met de
  prefix begint (natuurlijke versiesortering). De opgeloste tag, digest en
  lokale pull-datum worden gelogd, zodat elke run traceerbaar is. Ontbreekt
  een model → waarschuwing met de exacte instructie (`ollama pull <model>`).
  Eerlijkheid in de melding: Ollama kan niet bepalen of een tag upstream
  verouderd is; de check beperkt zich tot lokale aanwezigheid.
- Eén opgelost werkpaard → stemlaag uit (waarschuwing); nul → LLM-laag uit.

**Termbanken**

- Elk pad uit `CRUNCH_UML_TERMBANKS` wordt gecontroleerd (bestaat, leesbaar,
  parseerbaar); een directory wordt gescand op ondersteunde bestanden.
- Versie/datum wordt uit de data zelf gelezen (`owl:versionInfo`,
  `dcterms:modified`/`issued`, TBX-headerdatum) en gerapporteerd; ouder dan
  `CRUNCH_UML_TERMBANK_MAX_AGE_DAYS` → waarschuwing.
- Geen enkele termbank beschikbaar → nadrukkelijke waarschuwing dat termen
  zonder autoritatieve grounding vertaald worden.

## Termbanken: automatische LOD-detectie

Eén lijstvariabele, volgorde = prioriteit (eerste wint bij conflicten):

```bash
export CRUNCH_UML_TERMBANKS="resources/gemma_begrippen.ttl,resources/lod/,resources/IATE_export.tbx"
```

- Formaat wordt automatisch bepaald: rdflib leest alle gangbare
  LOD-serialisaties (Turtle, RDF/XML, N-Triples, JSON-LD, TriG, N-Quads) op
  extensie met inhouds-sniffing als vangnet; TBX (XML, herkenbaar aan het
  rootelement) heeft een eigen lader.
- De vocabulaire wordt generiek bevraagd, niet per bron gecodeerd:
  taalgelabelde labels via `skos:prefLabel` > `skos:altLabel` > `rdfs:label`
  > `dct:title`; definities uit `skos:definition`/`skos:scopeNote`; domein
  uit `skos:inScheme`/`dct:subject`; IATE-betrouwbaarheidscodes uit TBX.
  Daarmee werkt elke SKOS/RDFS/OWL-gebaseerde bron zonder nieuwe code.
- Lookup: eerst exact (genormaliseerd), dan fuzzy (deterministisch,
  `difflib`); kandidaten dragen doelterm, definitie, domein, bron,
  betrouwbaarheid en concept-URI.

## Disambiguatie (deterministisch, zonder model)

Uit de kandidaten wordt gekozen op basis van context die crunch al heeft:
het pakket/domein waarin de term staat en vooral de brondefinitie
(tokenoverlap tussen kandidaat-definitie en brondefinitie). Past precies één
kandidaat (unieke winnaar met marge) → die wordt deterministisch genomen,
zonder model. Meervoudig of geen → naar de LLM-laag, mét de kandidaten als
glossarium en de instructie de juiste betekenis te kiezen.

## LLM-laag

- Eén `POST /api/chat` per element met `format` = JSON-schema (alle velden
  van het element), `temperature: 0`, configureerbare seed (default 42).
- Compacte contextkop — bewust géén hele modellen in de prompt: modelnaam +
  modeldefinitie (1–2 zinnen), pakketpad, bij attributen de eigen klasse met
  definitie, sibling-namen als één regel, en het bindende glossarium.
- Identifier-casing wordt na afloop deterministisch hersteld
  (`reconcile_case`, bestaand).
- Overeenstemming is bewijs van vertrouwen, geen bewijs van juistheid: de
  uiteindelijke waarheidscheck blijft menselijke review van het i18n-bestand.

## Configuratie (alle instellingen)

| Variabele | Betekenis | Default |
|---|---|---|
| `CRUNCH_UML_TRANSLATE_BACKEND` | `translators` \| `ollama` \| `pipeline` | `translators` |
| `CRUNCH_UML_TERMBANKS` | kommagescheiden paden (bestanden of directories) naar LOD/TBX-bronnen; volgorde = prioriteit | leeg |
| `CRUNCH_UML_TERMBANK_MAX_AGE_DAYS` | waarschuw als een bron ouder is | uit |
| `CRUNCH_UML_LLM_WORKHORSES` | kommagescheiden modelprefixen; 1e = primair (definities), 2e = tweede stem | `mistral-small3.1:24b` |
| `CRUNCH_UML_LLM_HEAVY` | modelprefix voor escalatie (het grootste dat de hardware trekt) | uit |
| `CRUNCH_UML_OLLAMA_URL` | Ollama-server | `http://localhost:11434` |
| `CRUNCH_UML_OLLAMA_TIMEOUT` | seconden per call | `120` |
| `CRUNCH_UML_OLLAMA_MIN_VERSION` | minimale serverversie (waarschuwing) | uit |
| `CRUNCH_UML_NMT_MODEL` | HF-modelnaam voor het NMT-vangnet, `{from}`/`{to}`-placeholders toegestaan (bv. `Helsinki-NLP/opus-mt-{from}-{to}`) | uit |
| `CRUNCH_UML_TRANSLATE_ALLOW_ONLINE` | `1` = translators-route als laatste vangnet toestaan | `0` |
| `CRUNCH_UML_TRANSLATE_WORKERS` | parallelle calls binnen één pass | `8` |
| `CRUNCH_UML_TRANSLATE_SEED` | seed voor LLM-calls | `42` |

De bestaande variabelen (`CRUNCH_UML_OLLAMA_MODEL`, `_URL`, `_TIMEOUT`,
`CRUNCH_UML_TRANSLATE_CONTEXT`) blijven werken voor de backends
`translators` en `ollama`; het gedrag daarvan is ongewijzigd.

## Modulestructuur

```
crunch_uml/translation/
├── __init__.py
├── config.py        # TranslationConfig.from_env()
├── termbank.py      # LOD/TBX-laders, directory-scan, lookup, versie-extractie
├── disambiguate.py  # deterministische keuze uit kandidaten
├── preflight.py     # capability discovery + startoverzicht
├── llm.py           # element-vertaling via Ollama, stemmen, glossarium-check
├── nmt.py           # optioneel NMT-vangnet (transformers, optionele dependency)
└── pipeline.py      # cascade-orkestratie: niveaus, passes, glossarium-doorgifte
```

Integratie: `I18nRenderer.translate_data` bouwt bij backend `pipeline`
elementen uit de i18n-data (alleen velden zonder bestaande vertaling),
verrijkt ze met context uit het schema (pakket-/klassenamen en -definities)
en schrijft de resultaten terug in de bestaande i18n-structuur. De
string-gebaseerde route voor `translators`/`ollama` blijft onaangeroerd.

## Wat bewust géén onderdeel is

- **Geen agent- of toolloop** — dit is een deterministische batchpijplijn.
- **Geen SQLite-vertaalgeheugen** — zie besluit 1.
- **Geen terugschrijven van concept-URI's naar het model** — het datamodel
  heeft daar nu geen veld voor; kan later als aparte feature.
- **Geen cloud-LLM-escalatie** — kan later als expliciete opt-in laag boven
  het zware model, met een deterministisch aan-criterium.
