# Graph Report - .  (2026-07-29)

## Corpus Check
- Large corpus: 183 files · ~781,258 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 1782 nodes · 3856 edges · 125 communities (93 shown, 32 thin omitted)
- Extraction: 89% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 401 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Component Architecture Diagram
- CLI Entrypoint & Database API
- Jinja2 & Markdown Renderers
- Ollama Translation Backend
- EA Repository Updater
- EA Geometry Conversions
- Renderer Dispatch & Pandas Exports
- Utility Helpers & EA GUIDs
- Schema Diff Markdown
- I18n & JSON Renderers
- Core Modules & Import Tests
- Linked Data Renderers
- LLM Translation & Casing
- Termbank Disambiguation
- Diagram ORM Entities
- Package Scoping & Copy
- Translation Pipeline & Elements
- UML Association & Attribute Model
- Translation Config & Preflight
- Termbank Loading Tests
- Termbank Loading & Parsing
- Table Text Formatting Tests
- UML Tag Mixins
- QEA GUID & Completeness Tests
- Registry & Transformers
- Pandas Tabular Renderers
- Preflight Capability Tests
- LLM Element Translation Tests
- Markdown Blockquote Tests
- QEA vs XMI Equivalence Tests
- CSV, JSON & I18n Parsers
- XMI Renderer
- EA XMI Parser
- QEA Parser Phases
- Parser & Renderer Catalog
- Run Marker & Versioning Tests
- Six-Layer Model (docs)
- Datamodel Versioning & Run Markers
- NMT Safety Net
- Translation Memory & Glossary
- Risk Matrix & Roadmap (docs)
- Diagram Geometry Phases
- Standard XMI Parser
- Transform Command Docs
- XMI Round-trip Acceptance Tests
- Schema Copy & UML Base
- ORM Entities & Mixin Pattern
- Diagram Geometry Components
- XMI Parsing Risks & Roadmap
- Debt Counseling Domain Model
- XMI Renderer EA Quirks
- CLI Argument Registration
- EA Repo Risks & Diagram Roadmap
- Translation Config Tests
- Live Ollama Smoke Tests
- Diagram Geometry Parser Tests
- Database Migration & Versioning
- SEO Metadata Overrides
- Import & Export Data Flows
- Config & Dependency Decisions
- Translation Cascade Design
- RDF & JSON-LD Renderers
- Persistence & Pipeline Layers
- Generic Format Geometry Tests
- Pipeline Translation Passes
- Caching Decision & XMI Phase 3
- Transform Layer Components
- Deployment Pipeline Examples
- Translation Env-Var Config
- Translation Fallback Chain
- GGM Complete EA Tests
- GGM Income EA Tests
- CI/CD Workflows
- Translation Context Map
- Termbank Lookup Index
- Test Fixtures & Isolation
- EA MIM Model Tests
- RSGB i18n Export Tests
- I18n Export Validation
- Registry & Decorator Patterns
- CSV Parser Renderer Tests
- XLSX Parser Renderer Tests
- DDAS Schuldhulp Test
- LOD Renderer Tests
- JSON Schema Renderer Tests
- Markdown Depth Tests
- Preflight Test Doubles
- Import Run Start
- Quality & Tooling Requirements
- QEA Cursor Fixtures
- Import Run Completion
- ORM Column Reflection
- Translation Package Init
- CLI Entry Point & Logging
- Living Situation Entities
- XLSX Round-trip Test
- JSON Relations Test
- Markdown Export Test
- Dash Bullet Table Test
- Star Bullet Table Test
- Numbered List Table Test
- Pipe Escaping Table Test
- Double Break Table Test
- Font Tag Stripping Test
- Complex Definition Table Test
- Single Line Markdown Test
- HTML Strip Markdown Test
- Multiline Markdown Test
- HTML List Blockquote Test
- Complex Definition Markdown Test
- GGM Schema Import Fixture
- Missing Column Migration Test
- Version Mismatch Recreate Test
- API Endpoint Parser (planned)
- GraphQL & OpenAPI Renderers (planned)
- Monitoring & Metrics (planned)
- GEMMA CSV Export Example
- Future Improvements Roadmap

## God Nodes (most connected - your core abstractions)
1. `Schema` - 133 edges
2. `CrunchException` - 120 edges
3. `Database` - 98 edges
4. `main()` - 74 edges
5. `Element` - 50 edges
6. `EARepoUpdater` - 44 edges
7. `Package` - 43 edges
8. `TranslationPipeline` - 40 edges
9. `RendererRegistry` - 37 edges
10. `load_termbanks()` - 32 edges

## Surprising Connections (you probably didn't know these)
- `mkdocs i18n-plugin (nl default, en met suffix-structuur)` --semantically_similar_to--> `Vertaalpijplijn backend `pipeline``  [INFERRED] [semantically similar]
  mkdocs.yml → docs/technisch/vertaalpijplijn.md
- `Gestandaardiseerd metaschema` --semantically_similar_to--> `Normalised SQLAlchemy storage of UML entities`  [INFERRED] [semantically similar]
  docs/index.md → README.md
- `Translations — i18n export with Ollama LLM (EN)` --conceptually_related_to--> `ollama translation backend (local Mistral LLM)`  [AMBIGUOUS]
  docs/handleiding/vertalingen.en.md → README.md
- `update_i18n — bestaande vertalingen hergebruiken` --semantically_similar_to--> `i18n file as translation memory`  [INFERRED] [semantically similar]
  docs/handleiding/vertalingen.md → README.md
- `Canoniek coördinatenstelsel (oorsprong linksboven, alles positief)` --semantically_similar_to--> `Universele Mapping Layer`  [INFERRED] [semantically similar]
  tasks/diagram-geometry-support.md → docs/technisch/roadmap.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Four-phase diagram geometry programme (model, parsers, renderer, all formats)** — changelog_diagram_geometry_phase1, changelog_diagram_geometry_phase2, changelog_diagram_geometry_phase3, changelog_diagram_geometry_phase4, changelog_ea_geometry_module, changelog_canonical_coordinate_system [EXTRACTED 1.00]
- **Shared-database safety contract (run markers, version policy, postgres staging)** — changelog_import_run_markers, changelog_on_version_mismatch_policy, changelog_datamodel_version_marker, changelog_postgres_extra, docs_handleiding_import_shared_db_staging [EXTRACTED 1.00]
- **Deterministic translation cascade (memory → termbanks → LLM voting → NMT → online)** — readme_i18n_translation_memory, readme_termbanks, readme_llm_voting, readme_hierarchical_glossary, readme_preflight, readme_pipeline_backend [EXTRACTED 1.00]
- **Registry pattern: registries en de @register decorator** — docs_technisch_architectuur_lagen_registry, docs_technisch_architectuur_lagen_parserregistry, docs_technisch_architectuur_lagen_rendererregistry, docs_technisch_architectuur_lagen_transformerregistry, docs_technisch_architectuur_design_patterns_registry_pattern, docs_technisch_architectuur_design_patterns_decorator_pattern [EXTRACTED 1.00]
- **Vertaalpijplijn met Ollama-beschermingslagen en fallback** — docs_technisch_componenten_renderers_i18nrenderer, docs_technisch_componenten_renderers_translate_data_pipeline, docs_technisch_componenten_renderers_ollama_backend, docs_technisch_componenten_renderers_opaque_token_preserve_filter, docs_technisch_componenten_renderers_reconcile_case, docs_technisch_componenten_renderers_fallback_keten [EXTRACTED 1.00]
- **Diagram-geometrie round-trip via canoniek coordinatenstelsel** — docs_technisch_componenten_parsers_eaxmiparser, docs_technisch_componenten_parsers_qeaparser, docs_technisch_componenten_parsers_ea_geometry, docs_technisch_componenten_renderers_xmirenderer, docs_technisch_componenten_renderers_earepoupdater, docs_technisch_datamodel_canoniek_coordinatenstelsel, docs_technisch_componenten_persistentie_junction_tables [EXTRACTED 1.00]
- **Lagen van de deterministische vertaalcascade** — docs_technisch_vertaalpijplijn_preflight, docs_technisch_vertaalpijplijn_termbank_lod_detectie, docs_technisch_vertaalpijplijn_deterministische_disambiguatie, docs_technisch_vertaalpijplijn_llm_laag, docs_technisch_vertaalpijplijn_nmt_vangnet, docs_technisch_vertaalpijplijn_online_opt_in [EXTRACTED 1.00]
- **GGM deployment-pipeline stappen** — docs_voorbeelden_import_deelmodel_extractie, docs_voorbeelden_xlsx_export, docs_voorbeelden_meertalig_model, docs_voorbeelden_ttl_export, docs_voorbeelden_schema_diff, docs_voorbeelden_deployment_pipeline, docs_voorbeelden_schema_strategie [EXTRACTED 1.00]
- **Vier fasen van de diagram-geometrie-upgrade** — tasks_diagram_geometry_support_fase1_datamodel, tasks_diagram_geometry_support_fase2_parsers, tasks_diagram_geometry_support_fase3_xmi_renderer, tasks_diagram_geometry_support_fase4_overige, tasks_diagram_geometry_support_canoniek_coordinatenstelsel, docs_technisch_roadmap_volledige_diagram_ondersteuning [EXTRACTED 1.00]
- **Parsers geregistreerd in ParserRegistry** — docs_image_01_architectuur_drawio_parserregistry, docs_image_01_architectuur_drawio_xmi_parser, docs_image_01_architectuur_drawio_ea_xmi_parser, docs_image_01_architectuur_drawio_qea_parser, docs_image_01_architectuur_drawio_json_parser, docs_image_01_architectuur_drawio_xlsx_parser, docs_image_01_architectuur_drawio_csv_parser, docs_image_01_architectuur_drawio_i18n_parser [EXTRACTED 1.00]
- **Renderers geregistreerd in RendererRegistry (11 renderers)** — docs_image_01_architectuur_drawio_rendererregistry, docs_image_01_architectuur_drawio_json_renderer, docs_image_01_architectuur_drawio_csv_renderer, docs_image_01_architectuur_drawio_xlsx_renderer, docs_image_01_architectuur_drawio_jinja2_renderer, docs_image_01_architectuur_drawio_ggm_markdown_renderer, docs_image_01_architectuur_drawio_json_schema_renderer, docs_image_01_architectuur_drawio_ttl_rdf_jsonld_renderer, docs_image_01_architectuur_drawio_sqlalchemy_generator, docs_image_01_architectuur_drawio_ea_repo_updater, docs_image_01_architectuur_drawio_schema_diff_md_renderer [EXTRACTED 1.00]
- **Import -> Transform -> Persistentie (hub) -> Export -> Externe opslag pijplijn** — docs_image_01_architectuur_drawio_importlaag, docs_image_01_architectuur_drawio_transformatielaag, docs_image_01_architectuur_drawio_persistentielaag, docs_image_01_architectuur_drawio_exportlaag, docs_image_01_architectuur_drawio_externe_systemen, docs_image_01_architectuur_drawio_gestandaardiseerd_metaschema [EXTRACTED 1.00]

## Communities (125 total, 32 thin omitted)

### Community 0 - "Component Architecture Diagram"
Cohesion: 0.06
Nodes (66): API Endpoint Parser (beoogd), AzureDB (beoogd), Bestandssysteem (XMI, JSON, CSV, XLSX), Caching & Validatie Engine (in ontwikkeling), cli.py (ArgumentParser, main() entrypoint), crunch_uml Componentenarchitectuur v0.4.8 (diagram), Configuratiemodule (in ontwikkeling), const.py (Constanten & Namespaces) (+58 more)

### Community 1 - "CLI Entrypoint & Database API"
Cohesion: 0.05
Nodes (38): main(), The main entrypoint for this script used in the setup.py file., Database, test_import_monumenten(), test_import_monumenten(), test_import_schuldhulpverlening(), test_modelafhandeling(), test_modelafhandeling() (+30 more)

### Community 2 - "Jinja2 & Markdown Renderers"
Cohesion: 0.07
Nodes (45): ERDiagramRenderer, fix_and_format_text(), fix_mojibake(), getJSONDatatype(), getVerplichteAttributen(), GGM_MDRenderer, _html_to_markdown_lines(), Jinja2Renderer (+37 more)

### Community 3 - "Ollama Translation Backend"
Cohesion: 0.05
Nodes (52): _propagate_translate_args_to_env(), Push any explicitly-set translation CLI args into ``os.environ`` so deeper…, Probeert een vertaling uit te voeren en bij een fout probeert het opnieuw, met…, translate(), _build_messages(), detect_case(), _env_model(), _env_timeout() (+44 more)

### Community 4 - "EA Repository Updater"
Cohesion: 0.07
Nodes (19): EARepoUpdater, Delete t_object records of the given object_type whose ea_guid is NOT in…, Delete Package records from both t_package and t_object whose ea_guid is NOT in…, Past de veldnamen in data_dict aan op basis van de field_mapper., Delete t_attribute rows whose ea_guid is NOT in known_attr_guids. If…, Delete t_connector records of the given connector_type whose ea_guid is NOT in…, Batched UPDATE — one prepared statement, many parameter sets., Batched INSERT — one sequence-allocation for the whole batch, followed by a… (+11 more)

### Community 5 - "EA Geometry Conversions"
Cohesion: 0.06
Nodes (46): compose_xmi_edge_geometry(), compose_xmi_edge_style(), format_num(), format_path(), format_qea_rect(), format_xmi_node_geometry(), parse_path(), parse_qea_rect() (+38 more)

### Community 6 - "Renderer Dispatch & Pandas Exports"
Cohesion: 0.04
Nodes (5): Schema, Same datamodel version: reconnecting must not touch existing data., test_compatible_database_keeps_data_between_connects(), QEA import now also yields the previously missing diagram membership., test_qea_diagram_membership_and_metadata()

### Community 7 - "Utility Helpers & EA GUIDs"
Cohesion: 0.06
Nodes (33): fromEAGuid(), is_empty_or_none(), lremove_substring(), map_field_name_from_EARepo(), map_field_name_to_EARepo(), nested_get(), parse_date(), parse_string_to_list() (+25 more)

### Community 8 - "Schema Diff Markdown"
Cohesion: 0.10
Nodes (23): _clean_name(), _fmt_value(), _match_by_key_or_id(), _md_anchor(), _md_escape(), _norm(), Any, _qualified_pkg_path() (+15 more)

### Community 9 - "I18n & JSON Renderers"
Cohesion: 0.08
Nodes (31): I18nRenderer, JSONRenderer, Hernoem keys in een dictionary (inclusief geneste dictionaries) volgens een…, Index existing translations once: section -> key -> {field: value}. This is the…, Translate every string field of ``data`` into ``to_language``. Backend…, _make_data(), Fast mock-based tests for I18nRenderer.translate_data. These tests exercise the…, update_i18n=False must translate every string, ignoring original_i18n. (+23 more)

### Community 10 - "Core Modules & Import Tests"
Cohesion: 0.17
Nodes (5): are_json_files_equal(), Vergelijk twee JSON-bestanden en negeer specifieke velden tijdens de…, copy_test_files(), fixture, Test 20: Integratie-test voor SchuldenXMI.xml met ggm_md Markdown output.…

### Community 11 - "Linked Data Renderers"
Cohesion: 0.06
Nodes (31): LodRenderer, map_datatype(), Renders all model packages as a Linked Data ontology. A model package is a…, Voeg de pakkethiërarchie toe als Linked Data-entiteiten., Render één enumeratie als owl:Class + skos:ConceptScheme met haar waarden als…, Map een GGM/EA-primitief type naar (RDF-datatype, maximumlengte). * ``AN<n>``…, slugify(), monumenten_graph() (+23 more)

### Community 12 - "LLM Translation & Casing"
Cohesion: 0.08
Nodes (32): Counter, Make the translation match the source's identifier style. No-op when the source…, reconcile_case(), build_messages(), _context_lines(), glossary_violations(), names_agree(), _normalize_name() (+24 more)

### Community 13 - "Termbank Disambiguation"
Cohesion: 0.11
Nodes (34): _autopick_allowed(), definition_overlap(), _definition_supported(), disambiguate(), _domain_matches(), Deterministic disambiguation of termbank candidates — no model involved. Given…, Pick the single right candidate, or ``None`` when ambiguous. ``context_terms``…, Jaccard-like overlap between two definitions, seen from the source side:… (+26 more)

### Community 14 - "Diagram ORM Entities"
Cohesion: 0.12
Nodes (32): Base, Class, Diagram, DiagramAssociation, DiagramClass, DiagramEdgeGeometry, DiagramEnumeration, DiagramGeneralization (+24 more)

### Community 15 - "Package Scoping & Copy"
Cohesion: 0.10
Nodes (8): Package, Verwijder getallen aan het begin van een string en trim leidende en afsluitende…, Get class by name from the model, Get enumeration by name from the model, Get diagram by name from the model, Associations whose both endpoint classes are in scope of this package., Generalizations whose both endpoint classes are in scope of this package., hybrid_property

### Community 16 - "Translation Pipeline & Elements"
Cohesion: 0.17
Nodes (31): Element-based translation via the layered pipeline (backend ``pipeline``, see…, Element, One translatable model element: its source fields plus the compact context the…, Batch translation of Elements according to the preflight capabilities., TranslationPipeline, FakeLLM, _install(), _preflight() (+23 more)

### Community 17 - "UML Association & Attribute Model"
Cohesion: 0.14
Nodes (11): Association, Attribute, BaseModel, CrunchException, Plugin, ABC, Exception, DDASPlugin (+3 more)

### Community 18 - "Translation Config & Preflight"
Cohesion: 0.12
Nodes (25): All pipeline settings, resolved from the environment., TranslationConfig, _check_ollama(), _check_termbanks(), compare_versions(), LLMStatus, _log_summary(), PreflightResult (+17 more)

### Community 19 - "Termbank Loading Tests"
Cohesion: 0.11
Nodes (27): load_termbanks(), Load every source from the (already expanded or raw) path list into a single…, Tests for crunch_uml.translation.termbank — loading and lookup. Covered…, IATE-1002 has reliability 4 (nl) and 2 (en): the concept must not be presented…, vergunning' exists in both fixtures. The source listed first must come first in…, A TBX file with a .xml extension must be routed to the TBX loader via root-…, With a language filter, concepts lacking labels in at least two of the…, A TBX loaded for nl→en only: entries keep working, but requesting a language… (+19 more)

### Community 20 - "Termbank Loading & Parsing"
Cohesion: 0.12
Nodes (26): Concept, expand_paths(), _graph_version(), is_tbx_file(), _lang_of(), _load_lod(), load_source(), _load_tbx() (+18 more)

### Community 21 - "Table Text Formatting Tests"
Cohesion: 0.14
Nodes (24): Tests voor fix_and_format_text in mode="table" en mode="markdown". Dekt alle…, markdownify gebruikt * voor <ul>; na normalisatie moet dat - worden., + bullets moeten worden genormaliseerd naar -., Ingesprongen * bullets (bijv. geneste lijsten) correct afhandelen., Een enkelvoudige tekst zonder structure mag geen <br> bevatten., Verkorte aanroep voor mode='table'., table(), test_table_empty_string() (+16 more)

### Community 22 - "UML Tag Mixins"
Cohesion: 0.14
Nodes (17): UMLTags, UMLTagsAttribute, UMLTagsCommon, UMLTagsDomain, UMLTagsGEMMA, UMLTagsGeneralization, UMLTagsHistory, UMLTagsLiteral (+9 more)

### Community 23 - "QEA GUID & Completeness Tests"
Cohesion: 0.14
Nodes (23): guid_to_eaid(), Convert EA GUID {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX} to EAID_ format. Returns…, slow, End-to-end completeness check on a GGM-sized .qea import. We import…, Phase 4 of the QEA parser only keeps connectors whose endpoints are…, Class.definitie is filled from t_object.Note in phase 2 (not from tagged…, Attribute.definitie is filled from t_attribute.Notes (phase 3)., Tagged values that *do* live in t_objectproperties (herkomst, gemma-type,… (+15 more)

### Community 24 - "Registry & Transformers"
Cohesion: 0.14
Nodes (8): Registry, CopyTransformer, register, PluginTransformer, register, ABC, Transformer, TransformerRegistry

### Community 25 - "Pandas Tabular Renderers"
Cohesion: 0.19
Nodes (17): CSVRenderer, DataProfilerRenderer, _DiffItem, ModelStatisticsMarkdownRenderer, object_as_dict(), register, Converteert een SQLAlchemy-modelobject naar een dictionary, inclusief hybride…, Render de Shape Expressions (ShEx) van het model naar een .shex bestand. Args:… (+9 more)

### Community 26 - "Preflight Capability Tests"
Cohesion: 0.26
Nodes (22): Run all capability checks and log the overview. ``languages`` (bron- plus…, run_preflight(), _config(), _mock_ollama(), Tests for crunch_uml.translation.preflight — capability discovery. All network…, The .ttl fixture carries dcterms:modified 2020-01-15 — far older than the…, The IATE dca export carries no date in its header: the age check must fall back…, test_fresh_enough_termbank_does_not_warn_about_age() (+14 more)

### Community 27 - "LLM Element Translation Tests"
Cohesion: 0.16
Nodes (18): _json_schema_for(), One deterministic Ollama call translating all fields of one element. Raises on…, JSON schema forcing the response to contain exactly the element's fields, all…, translate_element_once(), _capture_post(), _element(), FakeResponse, Tests for crunch_uml.translation.llm — per-element translation calls and the… (+10 more)

### Community 28 - "Markdown Blockquote Tests"
Cohesion: 0.09
Nodes (22): md0(), Verkorte aanroep voor mode='markdown', depth=0 (template-mode)., depth=0 geeft GEEN leading newline terug (template staat al op positie)., ■ bullets worden herkend als lijstitems., ■ bullets in blockquote: vervolg-regels hebben '> ' prefix., ■-teken zelf mag niet meer in de output staan (omgezet naar list item)., Geen letterlijke \\1 backreference in output., ■ bullets zonder intro-tekst worden ook correct verwerkt. (+14 more)

### Community 29 - "QEA vs XMI Equivalence Tests"
Cohesion: 0.14
Nodes (20): get_schemas(), Test dat MonumentenMIM.qea en MonumentenMIM.xml na inlezen gelijke data…, Alle enumeraties hebben in beide schema's dezelfde IDs., Alle associaties hebben in beide schema's dezelfde IDs, namen, source- en…, Classes hebben in beide schema's dezelfde naam., Als beide schema's een definitie hebben voor dezelfde class, moeten deze gelijk…, Tagged values (gemma_type, gemma_url, definitie) zijn gelijk voor classes., Packages, classes, datatypes, enumeraties, literals, associaties en… (+12 more)

### Community 30 - "CSV, JSON & I18n Parsers"
Cohesion: 0.21
Nodes (10): clean_value(), CSVParser, I18nParser, JSONParser, register, Pandas represents empty spreadsheet cells as NaN; the database expects NULL.…, Hernoem kolomnamen in het record volgens de opgegeven mapper. :param record:…, TransformableParser (+2 more)

### Community 31 - "XMI Renderer"
Cohesion: 0.23
Nodes (9): _add_tags(), _association_end_id(), is_association_end_attribute(), register, Write the remaining string-valued columns of ``obj`` as tagged values. The…, Attributes with an EAID_src/EAID_dst id are artifacts of navigable association…, _set_attrs(), XMIRenderer (+1 more)

### Community 32 - "EA XMI Parser"
Cohesion: 0.16
Nodes (14): EAXMIParser, get_sorted_tags(), register, Sorteert tags op basis van vermoedelijke ouderdom aan de hand van de eerste…, third and last phase of parsing XMI-documents. Parsing extra propriatary data:…, copy_values(), fixtag(), Parser (+6 more)

### Community 33 - "QEA Parser Phases"
Cohesion: 0.18
Nodes (11): normalize_newlines(), register, QEAParser, Parse t_object into Class and Enumeratie objects., Parse t_attribute into Attribute and EnumerationLiteral objects., Parse t_connector into Association and Generalization objects., Apply tagged values from t_objectproperties, t_attributetag, t_connectortag.…, Parse t_diagram, t_diagramobjects and t_diagramlinks into Diagram objects with… (+3 more)

### Community 34 - "Parser & Renderer Catalog"
Cohesion: 0.12
Nodes (18): Template Method Pattern, CSVParser (csv), I18nParser (i18n), JSONParser (json), TransformableParser, XLSXParser (xlsx), CSVRenderer (csv), GGM_MDRenderer (ggm_md) (+10 more)

### Community 35 - "Run Marker & Versioning Tests"
Cohesion: 0.26
Nodes (17): _count_classes(), _db_url(), _dispose_singleton(), _fetch_runs(), fixture, The Database singleton survives across tests (export-only CLI runs never close…, _read_version(), _reset_database_singleton() (+9 more)

### Community 36 - "Six-Layer Model (docs)"
Cohesion: 0.24
Nodes (17): Zeslagenmodel, const.py — Constanten & Namespaces, Layer Details (EN), Lagendetail, Laag 1: Presentatielaag, Componenten (overzichtspagina), Components (EN), Parsers (Import Layer, EN) (+9 more)

### Community 37 - "Datamodel Versioning & Run Markers"
Cohesion: 0.17
Nodes (16): Additive on-connect migration, Datamodel version marker (crunch_uml_meta table), Import-run markers (crunch_uml_runs table), -on_version_mismatch {auto,fail,recreate} policy, PostgreSQL extra (crunch_uml[postgres]), CLI-referentie (NL), Database backends (SQLite, PostgreSQL, MySQL, MariaDB), CLI Reference (EN) (+8 more)

### Community 38 - "NMT Safety Net"
Cohesion: 0.17
Nodes (14): available(), _get_pipeline(), Optional NMT safety net (dedicated translation models, no Ollama). This is the…, True when the optional 'transformers' dependency is importable., Substitute {from}/{to} placeholders; a fixed name passes through., Translate ``texts`` with the configured NMT model. Raises when the optional…, resolve_model_name(), translate_texts() (+6 more)

### Community 39 - "Translation Memory & Glossary"
Cohesion: 0.17
Nodes (16): Context-bewust vertalen: dedup-sleutel trade-off, Translations — i18n export with Ollama LLM (EN), Modelnamen als prefix (hoogste lokaal geïnstalleerde tag), update_i18n — bestaande vertalingen hergebruiken, Vertalingen — i18n export met Ollama LLM (NL), Hierarchical glossary (packages → classes → attributes), i18n file as translation memory, Two-workhorse LLM voting with heavy-model escalation (+8 more)

### Community 40 - "Risk Matrix & Roadmap (docs)"
Cohesion: 0.15
Nodes (16): Risk Matrix (EN), Singleton Database Pattern (EN), Inconsistenties repository-metaschema vs bronsystemen, Risicomatrix (kans x impact scoring), Singleton Database Pattern (concurrency-risico), Development Roadmap Overview (EN), Gecentraliseerde Repository (metaschema), Schema Diff & Merge Engine (+8 more)

### Community 41 - "Diagram Geometry Phases"
Cohesion: 0.15
Nodes (15): Canonical coordinate system (origin top-left, y downwards, positive), Phase 1 — diagram geometry in the data model, Phase 2 — parsers read diagram geometry, Phase 4 — all formats carry diagram geometry, crunch_uml.ea_geometry conversion module, i18n format deliberately skips diagram junction tables, Edge geometry Path= reassembly with y-sign flip, Node geometry regenerated with positive Top/Bottom (+7 more)

### Community 42 - "Standard XMI Parser"
Cohesion: 0.21
Nodes (9): extract_declared_encoding(), load_xmi(), register, second phase of parsing XMI-documents. Parsing and connecting: - Assosiations -…, third and last phase of parsing XMI-documents. Parsing extra propriatary data:…, First phase of parsing XMI-documents. Parsing recursively: - Packages - Classes…, remove_EADatatype(), XMIParser (+1 more)

### Community 43 - "Transform Command Docs"
Cohesion: 0.15
Nodes (15): Afwijkingen README (ontbrekende flags en renderer-types), Copy transformer (deep copy van package-hiërarchie), transform command (EN), Materialiseren van generalisaties (inheritance afvlakken), Plugin transformer (crunch_uml.transformers.plugin.Plugin), transform-commando (NL), crunch_uml — universele UML model converter (docs home NL), crunch_uml — universal UML model converter (docs home EN) (+7 more)

### Community 44 - "XMI Round-trip Acceptance Tests"
Cohesion: 0.23
Nodes (14): assert_semantically_equal(), is_association_end(), normalize(), Acceptance test for the XMI renderer (phase 3): the round-trip fixture ->…, Same acceptance test starting from the QEA repository file., Larger model with generalizations on diagrams, waypoint paths and orphan…, MIM model with named/stereotyped generalizations, datatypes with definitions…, The rendered file has the structural markers EA needs on import. (+6 more)

### Community 46 - "ORM Entities & Mixin Pattern"
Cohesion: 0.22
Nodes (13): Mixin Pattern (UML_Generic / UMLBase / UMLTags*), Association (ORM-entiteit), Attribute (ORM-entiteit), Class (ORM-entiteit), Enumeratie (ORM-entiteit), EnumerationLiteral (ORM-entiteit), Generalization (ORM-entiteit), Package (ORM-entiteit) (+5 more)

### Community 47 - "Diagram Geometry Components"
Cohesion: 0.33
Nodes (13): crunch_uml/ea_geometry.py (geometrieconversies), EAXMIParser (eaxmi), Parser (abstracte basisklasse), QEAParser (qea), Diagram junction tables (membership + layout), EARepoUpdater (ea_repo), XMIRenderer (xmi), Canoniek coordinatenstelsel (+5 more)

### Community 48 - "XMI Parsing Risks & Roadmap"
Cohesion: 0.15
Nodes (13): In-huis ontwikkelde XMI-bibliotheken, XMI Parsing Error Sensitivity (EN), Inheritance-interpretatievariaties bij DB-mapping, XMI Parsing foutgevoeligheid (hoog risico), Cloud Database Connectors (Snowflake, Azure SQL), Generalization Materializer v2, REST API Interface (FastAPI), Streaming / Chunked Parser (+5 more)

### Community 49 - "Debt Counseling Domain Model"
Cohesion: 0.19
Nodes (13): Aanmelding, Crisisinterventie, Intake, Moratorium, Nazorg, Oplossing, Schuld, Schuldeiser (+5 more)

### Community 50 - "XMI Renderer EA Quirks"
Cohesion: 0.18
Nodes (12): Phase 3 — new XMI renderer, parse → render → parse round-trip acceptance test, Association ends written as ownedEnd, Diagram type always written as Logical, Generalization connectors in the EA extension section, EA exporter header and schema.omg.org namespaces, Orphan class placeholders and dangling type idrefs, Tagged values from snake_case columns (+4 more)

### Community 51 - "CLI Argument Registration"
Cohesion: 0.18
Nodes (12): add_args(), getTables(), add_args(), add_args(), Argparse-type for real booleans. ``type=bool`` is a classic trap: bool("False")…, str2bool(), add_args(), add_args() (+4 more)

### Community 52 - "EA Repo Risks & Diagram Roadmap"
Cohesion: 0.17
Nodes (12): EA Repo Updater destructieve operaties, Grote db.py (1200+ regels) technische schuld, Datamodel-versionering via crunch_uml_meta, Full diagram support v0.5.0 (EN), Volledige diagram-ondersteuning v0.5.0 (membership + geometrie), Voorbeeld 9: EA Repository bijwerken met MIM-tags, Gemeentelijk Gegevensmodel (GGM) als referentiecase, Doel: crunch_uml als brug EA → Semantic Toolkit met diagramlayout (+4 more)

### Community 53 - "Translation Config Tests"
Cohesion: 0.27
Nodes (11): _clean_env(), Tests for crunch_uml.translation.config — env-var based pipeline settings.…, CRUNCH_UML_TERMBANKS holds the paths themselves, comma-separated; order is…, Broken numeric values must not crash a batch run: fall back to the default (or…, test_defaults_when_no_env_set(), test_empty_workhorses_falls_back_to_default(), test_invalid_numbers_degrade_with_warning(), test_llm_roles_workhorses_and_heavy() (+3 more)

### Community 54 - "Live Ollama Smoke Tests"
Cohesion: 0.26
Nodes (11): _config(), _element(), _pick_live_model(), Live smoke tests against a REAL local Ollama server — no mocks. All other…, De harde eis van de pijplijn, gecontroleerd tegen de echte server: temperature…, Het bindende glossarium is het kernmechanisme van de pijplijn: een echt model…, The model the live tests run against, or None when unavailable., test_live_element_translation_returns_all_fields() (+3 more)

### Community 55 - "Diagram Geometry Parser Tests"
Cohesion: 0.35
Nodes (11): get_session(), junction_rows(), Integration tests for diagram geometry parsing (phase 2). Expected values are…, The same model read through eaxmi and qea yields identical geometry for every…, setup_module(), test_cross_check_eaxmi_vs_qea_geometry_identical(), test_eaxmi_edge_geometry_without_waypoints(), test_eaxmi_node_geometry() (+3 more)

### Community 56 - "Database Migration & Versioning"
Cohesion: 0.22
Nodes (3): Effective mismatch policy: an explicit CLI choice wins; 'auto' recreates only…, Version marker stored in the database, or None when the database predates the…, Lightweight additive migration for existing database files. Database files…

### Community 57 - "SEO Metadata Overrides"
Cohesion: 0.24
Nodes (11): Canonical URL Link, Open Graph and Twitter Card Metadata, MkDocs SEO Metadata Override (main.html), Schema.org SoftwareApplication JSON-LD, Schema.org TechArticle JSON-LD, Architectuuroverzicht, Beoogde componenten (gestreepte legenda), Architecture Overview (EN) (+3 more)

### Community 58 - "Import & Export Data Flows"
Cohesion: 0.24
Nodes (11): Dataflows (pagina), Data Flows (EN), Export Flow, Import Flow, Two-Phase Parsing, cli.py — Command Line Interface, Laag 2: Orchestratielaag, ParserRegistry (7 parsers) (+3 more)

### Community 59 - "Config & Dependency Decisions"
Cohesion: 0.18
Nodes (11): Externe afhankelijkheid translators-library (lang.py), Configuratiemodule (pipeline-configuratie, audit logging), Runtime dependencies (SQLAlchemy, lxml, pandas, rdflib, ...), CRUNCH_UML_* configuratievariabelen vertaalpijplijn, Besluit: configuratie uitsluitend via CRUNCH_UML_* env-vars, Besluit: online vertaaldiensten zijn opt-in, nooit default, Preflight capability discovery met graceful degradation, Reproduceerbaarheid als harde eis (+3 more)

### Community 60 - "Translation Cascade Design"
Cohesion: 0.22
Nodes (11): Indexeringstechnieken (full-text, fuzzy, embeddings), Vertaalcascade (hergebruik → termbank → disambiguatie → LLM → NMT → online), Deterministische disambiguatie zonder model, Hiërarchische volgorde met glossarium-doorgifte, LLM-laag (Ollama /api/chat, JSON-schema, temp 0, seed), Modulestructuur crunch_uml/translation/, NMT-vangnet (optionele dependency, Opus-MT), Besluit: passes per model, geen interleaving (VRAM-swapping) (+3 more)

### Community 61 - "RDF & JSON-LD Renderers"
Cohesion: 0.24
Nodes (7): JSONLDRenderer, register, Renders all model packages using jinja2 and a template. A model package is a…, Renders all model packages using jinja2 and a template. A model package is a…, Renders all model packages using jinja2 and a template. A model package is a…, RDFRenderer, TTLRenderer

### Community 62 - "Persistence & Pipeline Layers"
Cohesion: 0.24
Nodes (10): Volledige Pipeline (import → transform → multi-export), Singleton Pattern (Database._instance), Kernprincipe: Multi-schema isolatie, Kernprincipe: Pipeline-architectuur, Laag 5: Externe Systemen, Database klasse (db.py), Datamodelversie en migratie (crunch_uml_meta), Schema klasse (schema.py) (+2 more)

### Community 63 - "Generic Format Geometry Tests"
Cohesion: 0.31
Nodes (9): assert_junction_rows_equal(), get_session(), Round-trip tests for diagram membership + geometry through the generic formats…, Files written before diagram membership/geometry existed (like the…, setup_module(), test_csv_roundtrip_includes_diagram_geometry(), test_json_roundtrip_includes_diagram_geometry(), test_old_json_without_geometry_still_imports() (+1 more)

### Community 64 - "Pipeline Translation Passes"
Cohesion: 0.33
Nodes (4): _level_of(), One model over the whole batch (see module docstring on passes).…, Translate all elements, level by level. Returns the translated fields per…, ResultKey

### Community 65 - "Caching Decision & XMI Phase 3"
Cohesion: 0.25
Nodes (9): Validatie-overhead zonder caching, Caching & Validatie Engine, Besluit: geen aparte cache — i18n-bestand is het vertaalgeheugen, Bewust buiten scope (geen agentloop, geen SQLite-geheugen, geen cloud-LLM), Example 9a: export model including diagrams as EA XMI (EN), Voorbeeld 9a: model inclusief diagrammen exporteren als EA XMI, Fase 3: nieuwe XMI-renderer (renderers/xmirenderer.py), Lossless bewaren van ruwe EA geometry/style-strings (+1 more)

### Community 66 - "Transform Layer Components"
Cohesion: 0.36
Nodes (8): Transform Flow, Plugin Framework, TransformerRegistry (2+ transformers), CopyTransformer (copy), Materialize Generalizations, Plugin (abstracte basisklasse), PluginTransformer (plugin), Transformer (abstracte basisklasse)

### Community 67 - "Deployment Pipeline Examples"
Cohesion: 0.25
Nodes (8): Integratie via I18nRenderer.translate_data, Vertaalpijplijn backend `pipeline`, Voorbeeld 10: volledige deployment-pipeline (Taskfile), Voorbeeld 7: i18n-vertalingen genereren, Voorbeeld 6: meertalig model genereren en terugschrijven naar EA, Voorbeeld 2: Excel-specificatie genereren, SEO / JSON-LD structured data via overrides/main.html, MkDocs Material site-configuratie

### Community 68 - "Translation Env-Var Config"
Cohesion: 0.38
Nodes (5): _int_or_default(), _optional_int(), Environment-variable configuration for the translation pipeline. crunch_uml is…, Split a comma-separated env value into a tuple of stripped entries., _split_csv()

### Community 69 - "Translation Fallback Chain"
Cohesion: 0.38
Nodes (7): Laag 6: Hulpmodules (util, lang, exceptions, templates), Vertaal-fallbackketen, I18nRenderer (i18n), Ollama vertaal-backend, Opaque-token preserve-filter, reconcile_case safety net, translate_data — drie-passes vertaalpijplijn

### Community 70 - "GGM Complete EA Tests"
Cohesion: 0.29
Nodes (4): copy_test_files(), fixture, slow, test_import_monumenten()

### Community 71 - "GGM Income EA Tests"
Cohesion: 0.29
Nodes (4): copy_test_files(), fixture, slow, test_import_monumenten()

### Community 72 - "CI/CD Workflows"
Cohesion: 0.33
Nodes (6): Coveralls coverage upload (main only), build.yml lint job, build.yml test job (Python 3.10-3.13 matrix), Publish to PyPI on tag push, release.yml release job, Development toolchain (black, flake8, isort, mypy, pytest, bandit, build, twine)

### Community 73 - "Translation Context Map"
Cohesion: 0.47
Nodes (5): ContextMap, _build(), build_context_map(), Context enrichment for element translation. The i18n data structure is flat…, Build the (section, GUID) → context dict map for one schema.

### Community 74 - "Termbank Lookup Index"
Cohesion: 0.33
Nodes (3): _norm(), Normalise a term for index keys: casefold and collapse whitespace., Find translation candidates: exact match on the normalised source label first,…

### Community 75 - "Test Fixtures & Isolation"
Cohesion: 0.47
Nodes (5): isolated_test_database(), mock_function(), fixture, Run the whole suite against a database file outside the repository. The…, test_setup_output_directory()

### Community 76 - "EA MIM Model Tests"
Cohesion: 0.40
Nodes (4): copy_test_files(), getRecordFromEARepository(), fixture, test_import_monumenten()

### Community 77 - "RSGB i18n Export Tests"
Cohesion: 0.33
Nodes (4): copy_test_files(), fixture, slow, test_import_monumenten()

### Community 78 - "I18n Export Validation"
Cohesion: 0.50
Nodes (5): is_valid_i18n_file(), getRecordFromEARepository(), slow, test_import_monumenten(), test_import_monumenten_met_update()

### Community 79 - "Registry & Decorator Patterns"
Cohesion: 0.70
Nodes (5): Decorator Pattern (@register), Design Patterns (pagina), Design Patterns (EN), Registry Pattern, Kernprincipe: Registry-driven uitbreidbaarheid

### Community 80 - "CSV Parser Renderer Tests"
Cohesion: 0.40
Nodes (5): are_csv_files_equal(), check_value_in_csv(), Vergelijk twee CSV-bestanden efficiënt met Pandas. :param file1: Pad naar het…, Controleer of een rij in een CSV-bestand waar 'GGM_guid' gelijk is aan een…, test_csv_parser_renderer()

### Community 81 - "XLSX Parser Renderer Tests"
Cohesion: 0.40
Nodes (5): are_xlsx_files_equal(), check_value_in_xlsx(), Vergelijk twee Excel-bestanden efficiënt met Pandas. :param file1: Pad naar het…, Controleer of een rij in een CSV-bestand waar 'GGM_guid' gelijk is aan een…, test_csv_parser_renderer()

### Community 82 - "DDAS Schuldhulp Test"
Cohesion: 0.67
Nodes (3): slow, test_importAndTransform_schuldhulp(), validate_json_schema()

### Community 83 - "LOD Renderer Tests"
Cohesion: 0.50
Nodes (4): count_occurences(), is_valid_ttl_file(), Test of een bestand een geldig Turtle-bestand is. Args: - filename (str): Pad…, test_lod_renderer()

### Community 85 - "Markdown Depth Tests"
Cohesion: 0.50
Nodes (4): md1(), depth=1: alle regels krijgen '> ' prefix, leading newline aanwezig., Verkorte aanroep voor mode='markdown', depth=1 (standaard)., test_markdown_depth1_multiline()

### Community 88 - "Quality & Tooling Requirements"
Cohesion: 0.67
Nodes (3): Doorlopende activiteiten (quality, testing, CI/CD, packaging), Development tooling (pytest, black, isort, mypy, flake8, bandit), Kwaliteitseisen per fase (pytest, mypy, ruff, CHANGELOG, versiebump)

### Community 89 - "QEA Cursor Fixtures"
Cohesion: 0.67
Nodes (3): fixture, A cursor on the raw .qea SQLite file., src_cursor()

## Ambiguous Edges - Review These
- `-on_version_mismatch {auto,fail,recreate} policy` → `CLI-referentie (NL)`  [AMBIGUOUS]
  docs/handleiding/cli-referentie.md · relation: conceptually_related_to
- `ollama translation backend (local Mistral LLM)` → `Translations — i18n export with Ollama LLM (EN)`  [AMBIGUOUS]
  docs/handleiding/vertalingen.en.md · relation: conceptually_related_to
- `Singleton Pattern (Database._instance)` → `Schema klasse (schema.py)`  [AMBIGUOUS]
  docs/technisch/architectuur/design-patterns.md · relation: conceptually_related_to
- `Beoogde componenten (gestreepte legenda)` → `Dekkingsmatrix diagrammen`  [AMBIGUOUS]
  docs/technisch/datamodel.md · relation: conceptually_related_to
- `Configuratiemodule (pipeline-configuratie, audit logging)` → `Besluit: configuratie uitsluitend via CRUNCH_UML_* env-vars`  [AMBIGUOUS]
  docs/technisch/roadmap.md · relation: semantically_similar_to
- `GGM Markdown Renderer` → `TTL / RDF / JSON-LD Renderer (Linked Data)`  [AMBIGUOUS]
  docs/image/01_architectuur.drawio.svg · relation: semantically_similar_to

## Knowledge Gaps
- **56 isolated node(s):** `build.yml lint job`, `Coveralls coverage upload (main only)`, `Publish to PyPI on tag push`, `Pipeline approach (import / transform / export)`, `translators translation backend (Google/Bing)` (+51 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **32 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `-on_version_mismatch {auto,fail,recreate} policy` and `CLI-referentie (NL)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `ollama translation backend (local Mistral LLM)` and `Translations — i18n export with Ollama LLM (EN)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Singleton Pattern (Database._instance)` and `Schema klasse (schema.py)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Beoogde componenten (gestreepte legenda)` and `Dekkingsmatrix diagrammen`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Configuratiemodule (pipeline-configuratie, audit logging)` and `Besluit: configuratie uitsluitend via CRUNCH_UML_* env-vars`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **What is the exact relationship between `GGM Markdown Renderer` and `TTL / RDF / JSON-LD Renderer (Linked Data)`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **Why does `Schema` connect `Renderer Dispatch & Pandas Exports` to `CLI Entrypoint & Database API`, `Jinja2 & Markdown Renderers`, `EA Repository Updater`, `EA Geometry Conversions`, `Utility Helpers & EA GUIDs`, `Schema Diff Markdown`, `I18n & JSON Renderers`, `Core Modules & Import Tests`, `Linked Data Renderers`, `Diagram ORM Entities`, `UML Association & Attribute Model`, `UML Tag Mixins`, `Pandas Tabular Renderers`, `QEA vs XMI Equivalence Tests`, `CSV, JSON & I18n Parsers`, `XMI Renderer`, `EA XMI Parser`, `QEA Parser Phases`, `Standard XMI Parser`, `XMI Round-trip Acceptance Tests`, `Generic Format Geometry Tests`, `I18n Export Validation`, `CSV Parser Renderer Tests`, `XLSX Parser Renderer Tests`, `LOD Renderer Tests`, `XLSX Round-trip Test`, `GGM Schema Import Fixture`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._