# Kwetsbaarheden & Technische Schuld

## Risicomatrix

| Risico | Kans | Impact | Score | Component | Mitigatie |
|---|:---:|:---:|:---:|---|---|
| XMI parsing fouten door brondiversiteit | Hoog | Hoog | **9** | XMI Parser, EA XMI Parser | Encoding detectie, recovery, error logging |
| Inconsistenties repository vs. werkelijk metaschema | Hoog | Hoog | **9** | Gecentraliseerde Repo (beoogd) | Schema-validatie, versie-tracking |
| Geheugenbelasting geïndexeerde gegevens | Hoog | Medium | **6** | Indexering (beoogd) | Lazy loading, paginatie, streaming |
| Concurrentieproblemen cache/validatie | Medium | Hoog | **6** | Caching Engine (beoogd) | Locking-strategie, versioned cache |
| Complexiteit mapping-configuratie | Medium | Medium | **4** | Mapping Layer (beoogd) | DSL, test-driven development |
| Singleton pattern bij concurrent gebruik | Laag | Medium | **3** | Database klasse | Connection pooling |
| Destructieve EA Repo operaties | Laag | Hoog | **3** | EA Repo Updater | Flags, dry-run modus |

---

## Hoog risico

### XMI Parsing — Foutgevoeligheid

Parsen van XMI-data is kwetsbaar door diversiteit in bronformaten en repositories. Elk bronsysteem heeft een eigen structuur, wat resulteert in error-gevoelige parsing. De twee-fasen aanpak (structuur → relaties) vermindert dit maar elimineert het niet.

**Impact**: Dataverlies, inconsistente modellen

**Huidige mitigatie**: Encoding detectie, recovery mechanismen, uitgebreide error logging

!!! danger "Kern van het probleem"
    Door beperkte ondersteuning van Python-bibliotheken voor XMI moeten alle XMI-bibliotheken in huis worden ontwikkeld. Dit leidt tot verminderde efficiëntie en verhoogde kans op onherleidbare fouten.

### Inconsistenties Metaschema

Het risico dat het repository-metaschema afwijkt van de werkelijk gebruikte metaschema's in bronsystemen.

**Impact**: Verkeerde interpretaties van datastructuren

**Huidige mitigatie**: Nog niet volledig geadresseerd — beoogde oplossing via gecentraliseerde repository met hiërarchie-documentatie.

---

## Medium risico

### Validatie Overhead

Herhaalde validaties bij onvolledige relaties vereisen aanzienlijke rekenkracht. Er is momenteel geen caching van validatieresultaten.

**Impact**: Onaanvaardbare vertragingen bij grote modellen

**Beoogde mitigatie**: Caching & Validatie Engine met:

- [ ] Cache-mechanisme voor opgeslagen validaties
- [ ] Controlemodule voor beheer van gecachte resultaten
- [ ] Concurrent-safe cache-invalidatie

### Inheritance Interpretatie-variaties

Diversiteit in hoe inheritance-relaties worden gemodelleerd en geïnterpreteerd bij vertaling naar fysieke databasemodellen.

**Impact**: Inconsistente output bij complexe modellen

**Beoogde mitigatie**: Universele Mapping Layer met standaard-strategieën

### Singleton Database Pattern { #singleton-database-pattern }

De Database-klasse gebruikt een singleton pattern dat problematisch kan zijn bij multi-threaded of concurrent gebruik. Er is geen connection pooling of thread-safety afhandeling.

**Impact**: Concurrentieproblemen, potentiële memory leaks

**Mogelijke mitigatie**:

- [ ] SQLAlchemy session-per-request pattern
- [ ] Connection pooling configuratie
- [ ] Thread-local sessions

---

## Laag risico

### EA Repo Updater — Destructieve Operaties

De EA Repo Updater kan via `--ea_allow_insert` en `--ea_allow_delete` records toevoegen en verwijderen in productie EA-repositories.

**Impact**: Potentieel onherstelbaar dataverlies

**Huidige mitigatie**: Flags achter CLI-argumenten, documentatie

**Aanvullende suggesties**:

- [ ] Dry-run modus (`--ea_dry_run`)
- [ ] Automatische backup voor wijzigingen
- [ ] Bevestigingsprompt bij destructieve operaties

### Translators Library — Externe Afhankelijkheid

De vertaalmodule (lang.py) is afhankelijk van de `translators` library. Externe diensten kunnen onbeschikbaar zijn of rate-limits opleggen.

**Impact**: Falende i18n-exports

**Huidige mitigatie**: Retry-logica, fallback translator

### Grote db.py (1200+ regels)

Het database-modelbestand combineert modeldefinities, business logica en hulpmethoden in één bestand.

**Impact**: Verhoogde onderhoudslast

**Suggestie**:

- [ ] Splits naar `models/package.py`, `models/clazz.py`, etc.
- [ ] Verplaats business logica naar service-laag
- [ ] Extraheer mixins naar apart bestand
