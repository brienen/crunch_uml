# Crunch_uml — volledige diagram-ondersteuning (membership + geometrie)

## Context en doel

Crunch_uml wordt de brug tussen Sparx Enterprise Architect (waarin het GGM wordt onderhouden) en de Semantic Toolkit. De toolkit gaat GGM-modellen inlezen **inclusief diagrammen mét layout**: posities en afmetingen van klassen/enumeraties op een diagram, en het verloop (waypoints) van associatie- en generalisatielijnen.

Crunch kent diagrammen nu alleen als membership-lijst (welke elementen staan op welk diagram). Deze upgrade voegt de **geometrie** toe, end-to-end:

1. Datamodel uitbreiden met geometrievelden.
2. Parsers (`eaxmi`, `qea`) lezen geometrie in.
3. Een **nieuwe XMI-renderer** schrijft modellen inclusief diagrammen + geometrie weg als EA-compatibele XMI.
4. Daarna moeten **alle** renderers en parsers met de uitgebreide diagrammen overweg kunnen (round-trip via json/csv/xlsx, write-back naar EA-repo, en expliciete n.v.t.-documentatie voor semantische renderers).

Werk in fasen, in deze volgorde. Elke fase eindigt groen (pytest, mypy, ruff) en wordt apart gecommit.

## Huidige staat (verifieer eerst zelf)

- `crunch_uml/db.py`: `Diagram` (UMLBase: id, schema_id, name, author, version, created, modified, definitie; plus package_id) met koppeltabellen `DiagramClass`, `DiagramEnumeration`, `DiagramAssociation`, `DiagramGeneralization`. Composite PK (diagram_id, schema_id, element_id). **Geen geometrie.**
- `crunch_uml/parsers/eaxmiparser.py` (~regel 230–310): leest `<diagram>`-elementen uit de EA-extension-sectie, koppelt membership via `subject`-idrefs, maar **negeert het `geometry`-attribuut** volledig. Een voorbeeld van de XML staat als docstring in de code.
- `crunch_uml/parsers/qeaparser.py`: leest t_package, t_object, t_attribute, t_connector en tagged values, maar **geen enkele diagram-tabel**. Diagram-membership ontbreekt dus volledig bij `.qea`-import.
- `crunch_uml/parsers/xmiparser.py` (strict XMI): kent geen diagrammen — strict XMI 2.1 bevat ze niet. Blijft zo.
- Renderers: er bestaat **geen XMI-renderer**. `earepo`/`eamimrepo` (`renderers/earepoupdater.py`, ~regel 1180) updaten alleen `t_diagram`-metadata (naam e.d.), geen diagramobjects/links.
- Generieke parsers/renderers (`json`, `csv`, `xlsx`, `i18n` in `parsers/multiple_parsers.py` en `renderers/pandasrenderer.py`) itereren over `db.getTables()` en pikken nieuwe kolommen dus grotendeels automatisch op — maar let op: de *indexed* variant slaat tabellen zonder `id`-kolom over, en de koppeltabellen hebben geen `id`. Controleer per formaat wat er nu al wel/niet doorheen komt en dek het af met tests.
- `Diagram.get_copy()` kopieert alleen class- en enum-membership (geen associations/generalizations — bestaande omissie) en straks dus ook nog geen geometrie.

## Fase 1 — datamodel

Breid de vier koppeltabellen uit. Alle nieuwe kolommen **nullable** (membership zonder bekende layout blijft geldig; bestaande fixtures/databases zonder geometrie moeten blijven werken).

Node-achtig (`DiagramClass`, `DiagramEnumeration`):

| Kolom | Type | Betekenis |
| --- | --- | --- |
| `x` | Float | linkerkant, canonieke coördinaten |
| `y` | Float | bovenkant, canonieke coördinaten |
| `width` | Float | breedte |
| `height` | Float | hoogte |
| `z_order` | Integer | stapelvolgorde (EA `seqno`/`Sequence`) |
| `ea_style` | Text | ruwe EA style-string, lossless bewaren voor round-trip |

Edge-achtig (`DiagramAssociation`, `DiagramGeneralization`):

| Kolom | Type | Betekenis |
| --- | --- | --- |
| `waypoints` | Text (JSON) | `[{"x": .., "y": ..}, ...]` in canonieke coördinaten; lege lijst/NULL = geen tussenpunten |
| `hidden` | Boolean | EA `Hidden`-vlag |
| `ea_geometry` | Text | ruwe EA geometry-string (SX/SY/EX/EY/EDGE/labelposities/Path) — lossless |
| `ea_style` | Text | ruwe EA style-string — lossless |

**Canoniek coördinatenstelsel**: oorsprong linksboven, x naar rechts, y naar beneden, alles positief. Alle parser-/renderer-conversies van en naar EA-conventies gebeuren aan de rand; de database bevat alleen canonieke waarden. Leg dit vast in een module-docstring of `docs/technisch/datamodel.md`.

Verder in deze fase:

- `Diagram.get_copy()`: kopieer de nieuwe geometrievelden mee. Fix daarbij ook de bestaande omissie dat association-/generalization-membership niet gekopieerd wordt (of, als dat bewust is, documenteer het expliciet bij de methode).
- Unit-tests voor het datamodel (aanmaken, kopiëren, cascade delete van diagram incl. geometrierijen).

## Fase 2 — parsers

### 2a. `eaxmi` (eaxmiparser.py)

Parse het `geometry`-attribuut per `<element>` in `<diagram><elements>`:

- **Nodes**: `geometry="Left=90;Top=30;Right=210;Bottom=90;"` → `x=90, y=30, width=120, height=60`. Hier zijn Top/Bottom al positief (schermcoördinaten). `seqno` → `z_order`, `style` → `ea_style`.
- **Edges**: geometry bevat `SX/SY/EX/EY/EDGE`, labelposities (`$LLB`, `LLT`, `LMT`, `LMB`, `LRT`, `LRB`) en `Path=226:-205$256:-205$...` — x:y-paren gescheiden door `$`, **y is hier negatief** (EA-conventie). Converteer Path naar canonieke waypoints (y-teken flippen); bewaar de volledige string in `ea_geometry` en de style in `ea_style`, zet `hidden` op basis van `Hidden=1` in de style-string.

Onbekende elementtypen (Notes, Constraints, referenties buiten het model) blijven zoals nu: debug-log en overslaan.

### 2b. `qea` (qeaparser.py)

Nieuw: lees de diagram-tabellen. Dit voegt voor `.qea` óók de nu ontbrekende membership toe:

- `t_diagram`: Diagram_ID, ea_guid (→ id, zelfde GUID-naar-EAID-conversie als elders in de parser), Name, Package_ID, Author, Version, CreatedDate, ModifiedDate, Notes (→ definitie).
- `t_diagramobjects`: Diagram_ID, Object_ID (join op t_object voor ea_guid), RectLeft, RectTop, RectRight, RectBottom, Sequence, ObjectStyle. **Let op: RectTop/RectBottom zijn negatief** in de qea-database: `y = -RectTop`, `height = RectTop - RectBottom` (controleer met een echt bestand). Object kan class of enumeratie zijn — route naar de juiste koppeltabel.
- `t_diagramlinks`: DiagramID, ConnectorID (join op t_connector voor ea_guid), Geometry, Style, Hidden, Path. Zelfde Path-parsing en y-flip als bij 2a. Connector kan association of generalization zijn.

### 2c. Tests fase 2

- Gebruik bestaande fixtures: `test/data/GGM_Monumenten_EA2.1.xml` en `test/data/Monumenten.qea`. Assert voor minimaal één diagram concrete verwachte posities/afmetingen van een paar klassen en de waypoints van minimaal één relatie (lees de verwachte waarden uit de fixture zelf).
- Cross-check: hetzelfde model via `eaxmi` en via `qea` ingelezen moet (bij benadering) dezelfde geometrie opleveren voor dezelfde elementen.
- Bestaande tests (o.a. `test_01c_import_schuldhulpverlening.py`, `test_17_qea_parser.py`) blijven groen; membership-counts van qea-import wijzigen doordat diagrammen er nu bij komen — pas die tests bewust aan.

## Fase 3 — nieuwe XMI-renderer

Registreer een renderer `xmi` (in een nieuw bestand `renderers/xmirenderer.py`) die het complete model wegschrijft als **XMI 2.1 met EA-extension-sectie**, het spiegelbeeld van wat `eaxmiparser` leest:

- Strikte deel: `uml:Model` met packagedElements (packages, classes incl. attributen, enumeraties incl. literals, associaties incl. ends/cardinaliteiten/rollen, generalisaties). Gebruik de bestaande ids als `xmi:id`.
- Extension-deel: per diagram een `<diagram>` met properties/project-metadata en `<elements>` met per element het `geometry`-attribuut in EA-formaat — de exacte omkering van de fase-2-conversies (incl. y-flip voor Path). Gebruik `ea_geometry`/`ea_style` als die gevuld zijn; genereer anders minimale geldige strings uit de canonieke velden.
- Doel-compatibiliteit: het bestand moet door de eigen `eaxmi`-parser gelezen kunnen worden **en** door Sparx EA importeerbaar zijn. Waar de XMI-spec en EA botsen wint EA; documenteer elke afwijking met een korte notitie in `renderers/EA_QUIRKS.md`.

**Acceptatietest (de kern van deze hele upgrade)** — round-trip:

```
GGM_Monumenten_EA2.1.xml → [eaxmi parse] → schema A → [xmi render] → out.xml
out.xml → [eaxmi parse] → schema B
```

Schema B is semantisch gelijk aan schema A: zelfde packages/classes/attributen/enums/associaties/generalisaties, zelfde diagram-membership, en **zelfde geometrie** (posities exact of binnen 1px, waypoints gelijk). Zelfde test ook met `Monumenten.qea` als startpunt. Handmatige EA-importcheck van `out.xml` hoort bij de definition-of-done van deze fase (noteer het resultaat in de PR/commit-message).

## Fase 4 — alle overige renderers en parsers

- **`json`, `csv`, `xlsx`, `i18n`** (renderers én parsers): de vier koppeltabellen inclusief nieuwe kolommen moeten volledig round-trippen: `parse eaxmi → render json → nieuwe db → parse json → render json` levert identieke geometrie. Onderzoek de bestaande junction-table-behandeling (indexed variant slaat tabellen zonder `id` over) en fix waar nodig. Backwards-compat: bestaande bestanden zónder geometriekolommen (bv. `test/data/Monumenten.json`) blijven importeerbaar.
- **`earepo` / `eamimrepo`** (earepoupdater.py): schrijf geometrie terug naar `t_diagramobjects` en `t_diagramlinks` (update bestaande rijen; insert voor elementen die nieuw op een diagram staan; verwijder rijen waarvan de membership vervallen is). Zelfde coördinaatconversies als de qea-parser, omgekeerd. Test tegen een kopie van `Monumenten.qea` naar het patroon van `test_15_updateEAModel.py`.
- **`sqla`**: controleer dat de nieuwe kolommen meekomen (vermoedelijk automatisch via ORM-metadata); test dekt het af.
- **Semantische renderers** (`jinja2`, `ggm_md`, `json_schema`, `plain_html`, `model_overview_md`, `er_diagram`, `openapi`, `ttl`, `rdf`, `json-ld`, `shex`, `profile`, `uml_mmd`, `model_stats_md`, `diff_md`): geometrie is daar niet van toepassing. Niets bouwen, wél vastleggen: voeg in `docs/technisch/datamodel.md` een dekkings-matrix toe (parser/renderer × diagram-membership × geometrie: leest / schrijft / n.v.t.).
- `renderers/lodrenderer copy.py` is dood bestand — negeren (of opruimen als losse commit).

## EA-quirks — let op

- XMI-extension node-geometrie heeft **positieve** Top/Bottom; `t_diagramobjects` heeft **negatieve** RectTop/RectBottom; `Path=`-coördinaten zijn in **beide** bronnen negatief in y. Verifieer elk van deze drie tegen echte bestanden voordat je de conversies vastlegt, en documenteer ze bij de conversiefuncties.
- Label-geometrie (`LMT=CX=28:CY=14:...`) niet interpreteren — ruw bewaren in `ea_geometry` zodat de round-trip hem terug kan schrijven.
- EA staat (zelden) hetzelfde element twee keer op één diagram toe; onze composite PK kan dat niet. Bekende beperking: eerste instantie wint, log een warning. Niet oplossen.
- Zelfde element-GUID kan in `t_diagramobjects` naar een package of note verwijzen — alleen classes/enums/associations/generalizations verwerken, rest debug-loggen.

## Kwaliteitseisen (elke fase)

- `pytest` volledig groen; nieuwe functionaliteit heeft eigen tests (happy path + minimaal één failure/edge case).
- `mypy` en `ruff check` schoon; formatteren met de bestaande project-setup.
- CHANGELOG.md: één alinea per fase.
- `docs/technisch/datamodel.md` (en `.en.md`) bijwerken bij fase 1 en fase 4.
- Versiebump (minor) bij afronding van fase 4.
- Conventional Commits; code/comments/docstrings in het Engels.

## Out of scope

- Notes/comments, constraints en andere niet-ondersteunde elementtypen op diagrammen.
- Diagram-typen anders dan klassendiagrammen ("Logical").
- Interpretatie van EA-stylestrings (kleuren, fonts) — alleen lossless doorgeven.
- Auto-layout voor ontbrekende geometrie — consumenten (zoals de Semantic Toolkit) lossen dat zelf op.
- Wijzigingen aan de strict-`xmi`-parser.
