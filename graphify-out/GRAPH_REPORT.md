# Graph Report - crunch_uml  (2026-09-17)

## Corpus Check
- 195 files · ~823,951 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2083 nodes · 4374 edges · 146 communities (121 shown, 25 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 405 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ed2bd809`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Exportlaag
- Database
- RendererRegistry
- translate
- EARepoUpdater
- ea_geometry.py
- Schema
- util.py
- SchemaDiffMarkdownRenderer
- I18nRenderer
- db.py
- test_09a_lod_datatypes_domeinen.py
- llm.py
- disambiguate
- test_32_diagram_geometry_model.py
- Package
- Element
- Class
- TranslationConfig
- load_termbanks
- termbank.py
- test_19_fix_and_format_table.py
- CrunchException
- test_19_qea_ggm_completeness.py
- renderer.py
- pandasrenderer.py
- run_preflight
- test_27_llm_element.py
- md0
- test_18_qea_xmi_vergelijking.py
- parser.py
- XMIRenderer
- eaxmiparser.py
- qeaparser.py
- Renderer (abstracte basisklasse)
- test_30_run_marker_and_versioning.py
- Zeslagenmodel
- Handleiding — driestapswerkwijze (NL)
- nmt.py
- Vertalingen — i18n export met Ollama LLM (NL)
- Risicomatrix (kans x impact scoring)
- export-commando (NL)
- xmiparser.py
- Crunch_UML — universal UML model converter
- test_35_xmi_renderer_roundtrip.py
- UML_Generic
- Class (ORM-entiteit)
- EAXMIParser (eaxmi)
- XMI Parsing foutgevoeligheid (hoog risico)
- Schuldhulptraject (central objecttype)
- xmi renderer EA quirks (xmirenderer.py)
- main
- Fase 1: datamodel-uitbreiding koppeltabellen met geometrie
- test_23_translation_config.py
- test_31_ollama_live.py
- test_34_diagram_geometry_parsers.py
- detect
- MkDocs SEO Metadata Override (main.html)
- Registry (base class, registry.py)
- Runtime dependencies (SQLAlchemy, lxml, pandas, rdflib, ...)
- Vertaalcascade (hergebruik → termbank → disambiguatie → LLM → NMT → online)
- lodrenderer.py
- Import Flow
- test_41_mini_m4_fixture.py
- .translate_elements
- Besluit: geen aparte cache — i18n-bestand is het vertaalgeheugen
- Transform Flow
- Voorbeeld 10: volledige deployment-pipeline (Taskfile)
- config.py
- I18nRenderer (i18n)
- test_15b_updateEAMIMModel_GGM_Complete.py
- test_15c_updateEAMIMModel_GGM_Inkomen.py
- build.yml test job (Python 3.10-3.13 matrix)
- build_context_map
- TermbankIndex
- conftest.py
- test_15a_updateEAMIMModel.py
- test_16a_export_i18n_rsgb.py
- test_16_export_i18n.py
- Design Patterns (pagina)
- test_05b_csv_parser_renderer_mapper.py
- test_06d_xlsx_parser_renderer_mapper.py
- test_importAndTransform_schuldhulp
- test_45_pack.py
- test_13_json_schema.py
- fix_and_format_text
- FakeResponse
- test_40_qea_xmi_pariteit.py
- Development tooling (pytest, black, isort, mypy, flake8, bandit)
- src_cursor
- test_42_invoer_hardening.py
- pack.py
- translation/__init__.py
- CLI entry point crunch_uml.cli:main
- Leefsituatie
- test_06_xlsx_parser_renderer.py
- load_xmi
- test_15_updateEAModel.py
- artifact.py
- test_43_versie.py
- test_table_markdown_numbered_list
- test_table_pipe_escaped
- test_table_no_double_br
- test_table_html_font_tag
- .render
- test_20_i18n_translate_dedup.py
- test_39_herimport_diagrammen.py
- test_22_ollama_translator.py
- .get_copy
- test_markdown_complex_definition
- ea_ids.py
- EAMIMRepoUpdater
- xmlsafe.py
- API Endpoint Parser
- GraphQL / OpenAPI Renderers (beoogd)
- Monitoring & Metrics
- Voorbeeld 8: CSV-export voor GEMMA met kolom-mapper
- Future improvements roadmap
- make_mini_m4_fixture.py
- synthetic_id
- reconcile_case
- Fase 3: nieuwe XMI-renderer (renderers/xmirenderer.py)
- JSONRenderer
- Onderwijs_42c2c682.md
- lang.py
- _LazyModule
- ._diff_entity_fields
- _propagate_translate_args_to_env
- test_17_qea_parser.py
- _FakeResponse
- test_05a_json_parser_renderer_mapper.py
- test_translate_preserves_opaque_tokens_without_llm
- Onderwijs_changes_670c81ce.md
- expand_paths
- GEMMA_Bedrijfsobjecten_element_1aa4897c.md
- OntbrekendeDefinitiesGGM_519b98c4.md
- test_markdown_square_bullets_no_backref
- test_markdown_square_bullets_only_no_intro
- test_markdown_numbered_list_plain

## God Nodes (most connected - your core abstractions)
1. `Schema` - 134 edges
2. `CrunchException` - 122 edges
3. `Database` - 104 edges
4. `main()` - 86 edges
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
- `EA-quirks (y-tekenconventies, labelgeometrie, dubbele elementen)` --conceptually_related_to--> `XMI Parsing foutgevoeligheid (hoog risico)`  [INFERRED]
  tasks/diagram-geometry-support.md → docs/technisch/kwetsbaarheden.md

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

## Communities (146 total, 25 thin omitted)

### Community 0 - "Exportlaag"
Cohesion: 0.06
Nodes (66): API Endpoint Parser (beoogd), AzureDB (beoogd), Bestandssysteem (XMI, JSON, CSV, XLSX), Caching & Validatie Engine (in ontwikkeling), cli.py (ArgumentParser, main() entrypoint), crunch_uml Componentenarchitectuur v0.4.8 (diagram), Configuratiemodule (in ontwikkeling), const.py (Constanten & Namespaces) (+58 more)

### Community 1 - "Database"
Cohesion: 0.06
Nodes (10): _crunch_version(), Database, Effective mismatch policy: an explicit CLI choice wins; 'auto' recreates only…, Insert an import-run row (completed_at NULL) and return its run_id. Uses its…, Stamp completed_at on the run row. Call as the FINAL step, after the import…, Version marker stored in the database, or None when the database predates the…, Lightweight additive migration for existing database files. Database files…, Had the table behind ``mapper`` no rows *of this schema* when this session… (+2 more)

### Community 2 - "RendererRegistry"
Cohesion: 0.30
Nodes (18): ERDiagramRenderer, GGM_MDRenderer, Jinja2Renderer, JSON_SchemaRenderer, ModelOverviewMarkdownRenderer, OpenAPIRenderer, PlainHTMLRenderer, register (+10 more)

### Community 3 - "translate"
Cohesion: 0.21
Nodes (13): _build_messages(), _env_model(), _env_timeout(), _env_url(), Any, Ollama-based translation backend for crunch_uml. Activate via the env-var…, Return True if ``value`` should be returned verbatim, skipping the LLM., Translate ``value`` via the Ollama ``/api/chat`` endpoint. Raises… (+5 more)

### Community 4 - "EARepoUpdater"
Cohesion: 0.07
Nodes (19): EARepoUpdater, Delete t_object records of the given object_type whose ea_guid is NOT in…, Delete Package records from both t_package and t_object whose ea_guid is NOT in…, Past de veldnamen in data_dict aan op basis van de field_mapper., Delete t_attribute rows whose ea_guid is NOT in known_attr_guids. If…, Delete t_connector records of the given connector_type whose ea_guid is NOT in…, Batched UPDATE — one prepared statement, many parameter sets., Batched INSERT — one sequence-allocation for the whole batch, followed by a… (+11 more)

### Community 5 - "ea_geometry.py"
Cohesion: 0.06
Nodes (51): compose_xmi_edge_geometry(), compose_xmi_edge_style(), _flag(), format_num(), format_path(), format_qea_rect(), format_xmi_node_geometry(), parse_diagram_hide_flags() (+43 more)

### Community 6 - "Schema"
Cohesion: 0.05
Nodes (5): Schema, Diagram.get_instances references get_associations_inscope and…, Same datamodel version: reconnecting must not touch existing data., test_compatible_database_keeps_data_between_connects(), test_diagram_get_instances_supports_all_types()

### Community 7 - "util.py"
Cohesion: 0.06
Nodes (31): getFilename(), getPackageImports(), getPackageLst(), getSQLADatatype(), koppeltabelname(), namePascalCase(), nameSnakeCase(), packagename() (+23 more)

### Community 8 - "SchemaDiffMarkdownRenderer"
Cohesion: 0.16
Nodes (10): _fmt_value(), _match_by_key_or_id(), _md_escape(), Any, Match entities from schema A to schema B. Strategy: first match by id (zero-…, Markdown diff between two schemas. Entities are matched first by id, then by…, Return a human-readable qualified key for an FK column value. Resolves the id…, Build a name-based key that survives ea_guid regeneration. (+2 more)

### Community 9 - "I18nRenderer"
Cohesion: 0.17
Nodes (16): I18nRenderer, Index existing translations once: section -> key -> {field: value}. This is the…, Translate every string field of ``data`` into ``to_language``. Backend…, Element-based translation via the layered pipeline (backend ``pipeline``, see…, _enable_pipeline(), _no_ollama(), Integration tests for the pipeline backend inside I18nRenderer.translate_data.…, type=bool was a silent trap: bool("False") is True, so '--update_i18n False'… (+8 more)

### Community 10 - "db.py"
Cohesion: 0.08
Nodes (29): BaseModel, getColumnNames(), Geeft een lijst met kolomnamen terug voor een gegeven tabelnaam., register, XLSXRenderer, test_import_monumenten(), test_import_monumenten(), test_import_schuldhulpverlening() (+21 more)

### Community 11 - "test_09a_lod_datatypes_domeinen.py"
Cohesion: 0.08
Nodes (25): map_datatype(), Map een GGM/EA-primitief type naar (RDF-datatype, maximumlengte). * ``AN<n>``…, monumenten_graph(), fixture, parametrize, Tests voor de verbeterde LOD-rendering: echte datatypes en de domeinhiërarchie.…, Niet langer alles xsd:string: het Monumenten-model heeft int- en…, AN200-attributen krijgen sh:datatype xsd:string mét sh:maxLength 200. (+17 more)

### Community 12 - "llm.py"
Cohesion: 0.09
Nodes (31): Counter, build_messages(), _context_lines(), glossary_violations(), _json_schema_for(), names_agree(), _normalize_name(), Per-element LLM translation via Ollama, plus the deterministic checks that… (+23 more)

### Community 13 - "disambiguate"
Cohesion: 0.11
Nodes (34): _autopick_allowed(), definition_overlap(), _definition_supported(), disambiguate(), _domain_matches(), Deterministic disambiguation of termbank candidates — no model involved. Given…, Pick the single right candidate, or ``None`` when ambiguous. ``context_terms``…, Jaccard-like overlap between two definitions, seen from the source side:… (+26 more)

### Community 14 - "test_32_diagram_geometry_model.py"
Cohesion: 0.13
Nodes (27): Base, Diagram, DiagramAssociation, DiagramClass, DiagramEdgeGeometry, DiagramEnumeration, DiagramGeneralization, DiagramNodeGeometry (+19 more)

### Community 15 - "Package"
Cohesion: 0.15
Nodes (6): Package, Verwijder getallen aan het begin van een string en trim leidende en afsluitende…, Get class by name from the model, Get enumeration by name from the model, Get diagram by name from the model, hybrid_property

### Community 16 - "Element"
Cohesion: 0.17
Nodes (32): _DiffItem, Element, One translatable model element: its source fields plus the compact context the…, Batch translation of Elements according to the preflight capabilities., TranslationPipeline, PreflightResult, FakeLLM, _install() (+24 more)

### Community 17 - "Class"
Cohesion: 0.14
Nodes (11): Association, Attribute, Class, Get attribute by name from the class, Plugin, ABC, DDASPlugin, DDASPluginUitwisselmodel (+3 more)

### Community 18 - "TranslationConfig"
Cohesion: 0.14
Nodes (22): All pipeline settings, resolved from the environment., TranslationConfig, _check_ollama(), _check_termbanks(), compare_versions(), LLMStatus, _log_summary(), Capability discovery for the translation pipeline. Before anything is… (+14 more)

### Community 19 - "load_termbanks"
Cohesion: 0.11
Nodes (27): load_termbanks(), Load every source from the (already expanded or raw) path list into a single…, Tests for crunch_uml.translation.termbank — loading and lookup. Covered…, IATE-1002 has reliability 4 (nl) and 2 (en): the concept must not be presented…, vergunning' exists in both fixtures. The source listed first must come first in…, A TBX file with a .xml extension must be routed to the TBX loader via root-…, With a language filter, concepts lacking labels in at least two of the…, A TBX loaded for nl→en only: entries keep working, but requesting a language… (+19 more)

### Community 20 - "termbank.py"
Cohesion: 0.12
Nodes (26): Concept, _graph_version(), is_tbx_file(), _lang_of(), _load_lod(), load_source(), _load_tbx(), _local_name() (+18 more)

### Community 21 - "test_19_fix_and_format_table.py"
Cohesion: 0.11
Nodes (30): Tests voor fix_and_format_text in mode="table" en mode="markdown". Dekt alle…, markdownify gebruikt * voor <ul>; na normalisatie moet dat - worden., - bullets zijn al correct en mogen niet worden gewijzigd., * bullets moeten worden genormaliseerd naar -., + bullets moeten worden genormaliseerd naar -., Ingesprongen * bullets (bijv. geneste lijsten) correct afhandelen., Een enkelvoudige tekst zonder structure mag geen <br> bevatten., Verkorte aanroep voor mode='table'. (+22 more)

### Community 22 - "CrunchException"
Cohesion: 0.24
Nodes (14): UMLTags, UMLTagsAttribute, UMLTagsCommon, UMLTagsDomain, UMLTagsGEMMA, UMLTagsGeneralization, UMLTagsHistory, UMLTagsLiteral (+6 more)

### Community 23 - "test_19_qea_ggm_completeness.py"
Cohesion: 0.14
Nodes (23): guid_to_eaid(), Convert EA GUID {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX} to EAID_ format. Returns…, slow, End-to-end completeness check on a GGM-sized .qea import. We import…, Phase 4 of the QEA parser only keeps connectors whose endpoints are…, Class.definitie is filled from t_object.Note in phase 2 (not from tagged…, Attribute.definitie is filled from t_attribute.Notes (phase 3)., Tagged values that *do* live in t_objectproperties (herkomst, gemma-type,… (+15 more)

### Community 24 - "renderer.py"
Cohesion: 0.11
Nodes (11): Registry, ABC, Renderer, Renderer that writes the model as XMI 2.1 with the Enterprise Architect…, CopyTransformer, register, PluginTransformer, register (+3 more)

### Community 25 - "pandasrenderer.py"
Cohesion: 0.13
Nodes (18): _clean_name(), CSVRenderer, DataProfilerRenderer, _md_anchor(), ModelStatisticsMarkdownRenderer, object_as_dict(), register, _qualified_pkg_path() (+10 more)

### Community 26 - "run_preflight"
Cohesion: 0.26
Nodes (22): Run all capability checks and log the overview. ``languages`` (bron- plus…, run_preflight(), _config(), _mock_ollama(), Tests for crunch_uml.translation.preflight — capability discovery. All network…, The .ttl fixture carries dcterms:modified 2020-01-15 — far older than the…, The IATE dca export carries no date in its header: the age check must fall back…, test_fresh_enough_termbank_does_not_warn_about_age() (+14 more)

### Community 27 - "test_27_llm_element.py"
Cohesion: 0.20
Nodes (15): One deterministic Ollama call translating all fields of one element. Raises on…, translate_element_once(), _capture_post(), _element(), FakeResponse, Tests for crunch_uml.translation.llm — per-element translation calls and the…, IATE can yield dozens of near-duplicate candidates for common terms; only the…, The LLM answers with spaces; the source name is PascalCase, so the result must… (+7 more)

### Community 28 - "md0"
Cohesion: 0.08
Nodes (24): md0(), Verkorte aanroep voor mode='markdown', depth=0 (template-mode)., Enkele regel: geen blockquote-prefix, geen leading newline., Enkele regel met HTML-tag: tag gestript, tekst terug., Meerdere regels plain tekst: eerste regel zonder prefix, rest met '> '., depth=0 geeft GEEN leading newline terug (template staat al op positie)., ■ bullets worden herkend als lijstitems., ■ bullets in blockquote: vervolg-regels hebben '> ' prefix. (+16 more)

### Community 29 - "test_18_qea_xmi_vergelijking.py"
Cohesion: 0.11
Nodes (25): get_schemas(), Test dat MonumentenMIM.qea en MonumentenMIM.xml na inlezen gelijke data…, Alle enumeraties hebben in beide schema's dezelfde IDs., Alle associaties hebben in beide schema's dezelfde IDs, namen, source- en…, Classes hebben in beide schema's dezelfde naam., Als beide schema's een definitie hebben voor dezelfde class, moeten deze gelijk…, Tagged values (gemma_type, gemma_url, definitie) zijn gelijk voor classes., Package-stereotypen (zoals «Domein») zijn in beide formaten gelijk. De QEA… (+17 more)

### Community 30 - "parser.py"
Cohesion: 0.18
Nodes (12): clean_value(), CSVParser, I18nParser, JSONParser, register, Pandas represents empty spreadsheet cells as NaN; the database expects NULL.…, Hernoem kolomnamen in het record volgens de opgegeven mapper. :param record:…, TransformableParser (+4 more)

### Community 31 - "XMIRenderer"
Cohesion: 0.23
Nodes (9): _add_tags(), _association_end_id(), is_association_end_attribute(), register, Write the remaining string-valued columns of ``obj`` as tagged values. The…, Attributes with an EAID_src/EAID_dst id are artifacts of navigable association…, _set_attrs(), XMIRenderer (+1 more)

### Community 32 - "eaxmiparser.py"
Cohesion: 0.29
Nodes (8): EAXMIParser, get_sorted_tags(), register, Sorteert tags op basis van vermoedelijke ouderdom aan de hand van de eerste…, third and last phase of parsing XMI-documents. Parsing extra propriatary data:…, copy_values(), fixtag(), Copies all values from attributes of node to obj, if obj has an attribute with…

### Community 33 - "qeaparser.py"
Cohesion: 0.14
Nodes (16): guid_to_eapk(), normalize_newlines(), open_readonly_engine(), register, QEAParser, Parse t_package into Package objects. Stereotype, author, status, alias and…, Parse t_object into Class and Enumeratie objects., Parse t_attribute into Attribute and EnumerationLiteral objects. (+8 more)

### Community 34 - "Renderer (abstracte basisklasse)"
Cohesion: 0.12
Nodes (17): Template Method Pattern, CSVParser (csv), JSONParser (json), TransformableParser, XLSXParser (xlsx), CSVRenderer (csv), GGM_MDRenderer (ggm_md), Jinja2Renderer (jinja2) (+9 more)

### Community 35 - "test_30_run_marker_and_versioning.py"
Cohesion: 0.26
Nodes (17): _count_classes(), _db_url(), _dispose_singleton(), _fetch_runs(), fixture, The Database singleton survives across tests (export-only CLI runs never close…, _read_version(), _reset_database_singleton() (+9 more)

### Community 36 - "Zeslagenmodel"
Cohesion: 0.19
Nodes (22): Canonical URL Link, Architectuuroverzicht, Beoogde componenten (gestreepte legenda), Architecture Overview (EN), Zeslagenmodel, Layer Details (EN), Lagendetail, Componenten (overzichtspagina) (+14 more)

### Community 37 - "Handleiding — driestapswerkwijze (NL)"
Cohesion: 0.17
Nodes (16): Additive on-connect migration, Datamodel version marker (crunch_uml_meta table), Import-run markers (crunch_uml_runs table), -on_version_mismatch {auto,fail,recreate} policy, PostgreSQL extra (crunch_uml[postgres]), CLI-referentie (NL), Database backends (SQLite, PostgreSQL, MySQL, MariaDB), CLI Reference (EN) (+8 more)

### Community 38 - "nmt.py"
Cohesion: 0.17
Nodes (14): available(), _get_pipeline(), Optional NMT safety net (dedicated translation models, no Ollama). This is the…, True when the optional 'transformers' dependency is importable., Substitute {from}/{to} placeholders; a fixed name passes through., Translate ``texts`` with the configured NMT model. Raises when the optional…, resolve_model_name(), translate_texts() (+6 more)

### Community 39 - "Vertalingen — i18n export met Ollama LLM (NL)"
Cohesion: 0.14
Nodes (18): Ondersteunde uitvoerformaten (23 renderers), Ondersteunde invoerformaten (xmi, eaxmi, qea, json, xlsx, csv, i18n), Context-bewust vertalen: dedup-sleutel trade-off, Translations — i18n export with Ollama LLM (EN), Modelnamen als prefix (hoogste lokaal geïnstalleerde tag), update_i18n — bestaande vertalingen hergebruiken, Vertalingen — i18n export met Ollama LLM (NL), Hierarchical glossary (packages → classes → attributes) (+10 more)

### Community 40 - "Risicomatrix (kans x impact scoring)"
Cohesion: 0.14
Nodes (17): Risk Matrix (EN), Singleton Database Pattern (EN), Inconsistenties repository-metaschema vs bronsystemen, Risicomatrix (kans x impact scoring), Singleton Database Pattern (concurrency-risico), Development Roadmap Overview (EN), Gecentraliseerde Repository (metaschema), Indexeringstechnieken (full-text, fuzzy, embeddings) (+9 more)

### Community 41 - "export-commando (NL)"
Cohesion: 0.29
Nodes (7): Phase 1 — diagram geometry in the data model, Phase 4 — all formats carry diagram geometry, i18n format deliberately skips diagram junction tables, Ondersteunde tabellen incl. vier diagram-koppeltabellen, earepo-renderer schrijft diagramlayout terug, export command (EN), export-commando (NL)

### Community 42 - "xmiparser.py"
Cohesion: 0.15
Nodes (13): detect_encoding(), get_end_value(), mint_missing_ids(), register, Give every row element exported with ``xmi:id=""`` a deterministic synthetic…, Waarde van het eerste kindelement ``tag`` van een association-end. Eén XPath-…, First phase of parsing XMI-documents. Parsing recursively: - Packages - Classes…, second phase of parsing XMI-documents. Parsing and connecting: - Assosiations -… (+5 more)

### Community 43 - "Crunch_UML — universal UML model converter"
Cohesion: 0.15
Nodes (15): Afwijkingen README (ontbrekende flags en renderer-types), Copy transformer (deep copy van package-hiërarchie), transform command (EN), Materialiseren van generalisaties (inheritance afvlakken), Plugin transformer (crunch_uml.transformers.plugin.Plugin), transform-commando (NL), crunch_uml — universele UML model converter (docs home NL), crunch_uml — universal UML model converter (docs home EN) (+7 more)

### Community 44 - "test_35_xmi_renderer_roundtrip.py"
Cohesion: 0.23
Nodes (14): assert_semantically_equal(), is_association_end(), normalize(), Acceptance test for the XMI renderer (phase 3): the round-trip fixture ->…, Same acceptance test starting from the QEA repository file., Larger model with generalizations on diagrams, waypoint paths and orphan…, MIM model with named/stereotyped generalizations, datatypes with definitions…, The rendered file has the structural markers EA needs on import. (+6 more)

### Community 45 - "UML_Generic"
Cohesion: 0.14
Nodes (5): Enumeratie, EnumerationLiteral, Generalization, UML_Generic, UMLBase

### Community 46 - "Class (ORM-entiteit)"
Cohesion: 0.22
Nodes (13): Mixin Pattern (UML_Generic / UMLBase / UMLTags*), Association (ORM-entiteit), Attribute (ORM-entiteit), Class (ORM-entiteit), Enumeratie (ORM-entiteit), EnumerationLiteral (ORM-entiteit), Generalization (ORM-entiteit), Package (ORM-entiteit) (+5 more)

### Community 47 - "EAXMIParser (eaxmi)"
Cohesion: 0.29
Nodes (15): Two-Phase Parsing, crunch_uml/ea_geometry.py (geometrieconversies), EAXMIParser (eaxmi), Parser (abstracte basisklasse), QEAParser (qea), XMIParser (xmi), Diagram junction tables (membership + layout), EARepoUpdater (ea_repo) (+7 more)

### Community 48 - "XMI Parsing foutgevoeligheid (hoog risico)"
Cohesion: 0.29
Nodes (7): In-huis ontwikkelde XMI-bibliotheken, XMI Parsing Error Sensitivity (EN), XMI Parsing foutgevoeligheid (hoog risico), Cloud Database Connectors (Snowflake, Azure SQL), REST API Interface (FastAPI), Streaming / Chunked Parser, Beoogde dependency-toevoegingen (Alembic, FastAPI, ijson, uvicorn)

### Community 49 - "Schuldhulptraject (central objecttype)"
Cohesion: 0.19
Nodes (13): Aanmelding, Crisisinterventie, Intake, Moratorium, Nazorg, Oplossing, Schuld, Schuldeiser (+5 more)

### Community 50 - "xmi renderer EA quirks (xmirenderer.py)"
Cohesion: 0.13
Nodes (18): Canonical coordinate system (origin top-left, y downwards, positive), Phase 2 — parsers read diagram geometry, Phase 3 — new XMI renderer, crunch_uml.ea_geometry conversion module, parse → render → parse round-trip acceptance test, Association ends written as ownedEnd, Diagram type always written as Logical, Edge geometry Path= reassembly with y-sign flip (+10 more)

### Community 51 - "main"
Cohesion: 0.07
Nodes (36): main(), The main entrypoint for this script used in the setup.py file., add_args(), getTables(), add_args(), add_args(), Argparse-type for real booleans. ``type=bool`` is a classic trap: bool("False")…, str2bool() (+28 more)

### Community 52 - "Fase 1: datamodel-uitbreiding koppeltabellen met geometrie"
Cohesion: 0.17
Nodes (12): Grote db.py (1200+ regels) technische schuld, Inheritance-interpretatievariaties bij DB-mapping, Datamodel-versionering via crunch_uml_meta, Full diagram support v0.5.0 (EN), Generalization Materializer v2, Universele Mapping Layer, Volledige diagram-ondersteuning v0.5.0 (membership + geometrie), Gemeentelijk Gegevensmodel (GGM) als referentiecase (+4 more)

### Community 53 - "test_23_translation_config.py"
Cohesion: 0.27
Nodes (11): _clean_env(), Tests for crunch_uml.translation.config — env-var based pipeline settings.…, CRUNCH_UML_TERMBANKS holds the paths themselves, comma-separated; order is…, Broken numeric values must not crash a batch run: fall back to the default (or…, test_defaults_when_no_env_set(), test_empty_workhorses_falls_back_to_default(), test_invalid_numbers_degrade_with_warning(), test_llm_roles_workhorses_and_heavy() (+3 more)

### Community 54 - "test_31_ollama_live.py"
Cohesion: 0.26
Nodes (11): _config(), _element(), _pick_live_model(), Live smoke tests against a REAL local Ollama server — no mocks. All other…, De harde eis van de pijplijn, gecontroleerd tegen de echte server: temperature…, Het bindende glossarium is het kernmechanisme van de pijplijn: een echt model…, The model the live tests run against, or None when unavailable., test_live_element_translation_returns_all_fields() (+3 more)

### Community 55 - "test_34_diagram_geometry_parsers.py"
Cohesion: 0.27
Nodes (13): get_session(), junction_rows(), Integration tests for diagram geometry parsing (phase 2). Expected values are…, QEA import now also yields the previously missing diagram membership., The same model read through eaxmi and qea yields identical geometry for every…, setup_module(), test_cross_check_eaxmi_vs_qea_geometry_identical(), test_eaxmi_edge_geometry_without_waypoints() (+5 more)

### Community 56 - "detect"
Cohesion: 0.12
Nodes (29): _attr(), detect(), _detect_gzip(), detect_json(), _detect_sqlite(), _detect_xml(), Content-based file type detection for model uploads (``crunch_uml detect``).…, A crunch_uml artifact is gzip-JSON whose first key is ``"format"``. (+21 more)

### Community 57 - "MkDocs SEO Metadata Override (main.html)"
Cohesion: 0.67
Nodes (4): Open Graph and Twitter Card Metadata, MkDocs SEO Metadata Override (main.html), Schema.org SoftwareApplication JSON-LD, Schema.org TechArticle JSON-LD

### Community 58 - "Registry (base class, registry.py)"
Cohesion: 0.29
Nodes (7): cli.py — Command Line Interface, const.py — Constanten & Namespaces, Laag 2: Orchestratielaag, ParserRegistry (7 parsers), Laag 1: Presentatielaag, Registry (base class, registry.py), RendererRegistry (11 renderers)

### Community 59 - "Runtime dependencies (SQLAlchemy, lxml, pandas, rdflib, ...)"
Cohesion: 0.18
Nodes (11): Externe afhankelijkheid translators-library (lang.py), Configuratiemodule (pipeline-configuratie, audit logging), Runtime dependencies (SQLAlchemy, lxml, pandas, rdflib, ...), CRUNCH_UML_* configuratievariabelen vertaalpijplijn, Besluit: configuratie uitsluitend via CRUNCH_UML_* env-vars, Besluit: online vertaaldiensten zijn opt-in, nooit default, Preflight capability discovery met graceful degradation, Reproduceerbaarheid als harde eis (+3 more)

### Community 60 - "Vertaalcascade (hergebruik → termbank → disambiguatie → LLM → NMT → online)"
Cohesion: 0.24
Nodes (10): Vertaalcascade (hergebruik → termbank → disambiguatie → LLM → NMT → online), Deterministische disambiguatie zonder model, Hiërarchische volgorde met glossarium-doorgifte, LLM-laag (Ollama /api/chat, JSON-schema, temp 0, seed), Modulestructuur crunch_uml/translation/, NMT-vangnet (optionele dependency, Opus-MT), Besluit: passes per model, geen interleaving (VRAM-swapping), Termbanken met automatische LOD-formaatdetectie (+2 more)

### Community 61 - "lodrenderer.py"
Cohesion: 0.15
Nodes (13): JSONLDRenderer, LodRenderer, register, Renders all model packages as a Linked Data ontology. A model package is a…, Voeg de pakkethiërarchie toe als Linked Data-entiteiten., Render één enumeratie als owl:Class + skos:ConceptScheme met haar waarden als…, Renders all model packages using jinja2 and a template. A model package is a…, Renders all model packages using jinja2 and a template. A model package is a… (+5 more)

### Community 62 - "Import Flow"
Cohesion: 0.20
Nodes (14): Dataflows (pagina), Data Flows (EN), Export Flow, Import Flow, Volledige Pipeline (import → transform → multi-export), Singleton Pattern (Database._instance), Kernprincipe: Multi-schema isolatie, Kernprincipe: Pipeline-architectuur (+6 more)

### Community 63 - "test_41_mini_m4_fixture.py"
Cohesion: 0.12
Nodes (18): normalize_braced_ids(), Rewrite quoted ``"EAID_{X}"``/``"EAID_{{X}}"`` values to ``"EAID_X"`` in UTF-8…, connect(), _dispose_singleton(), mini(), pair(), parse_into(), fixture (+10 more)

### Community 64 - ".translate_elements"
Cohesion: 0.21
Nodes (6): _level_of(), The binding glossary for one element: accumulated translations whose source…, Termbank lookup + deterministic disambiguation for the element name. Returns…, One model over the whole batch (see module docstring on passes).…, Translate all elements, level by level. Returns the translated fields per…, ResultKey

### Community 65 - "Besluit: geen aparte cache — i18n-bestand is het vertaalgeheugen"
Cohesion: 0.33
Nodes (6): Validatie-overhead zonder caching, Caching & Validatie Engine, Besluit: geen aparte cache — i18n-bestand is het vertaalgeheugen, Integratie via I18nRenderer.translate_data, Bewust buiten scope (geen agentloop, geen SQLite-geheugen, geen cloud-LLM), Lossless bewaren van ruwe EA geometry/style-strings

### Community 66 - "Transform Flow"
Cohesion: 0.36
Nodes (8): Transform Flow, Plugin Framework, TransformerRegistry (2+ transformers), CopyTransformer (copy), Materialize Generalizations, Plugin (abstracte basisklasse), PluginTransformer (plugin), Transformer (abstracte basisklasse)

### Community 67 - "Voorbeeld 10: volledige deployment-pipeline (Taskfile)"
Cohesion: 0.29
Nodes (7): Vertaalpijplijn backend `pipeline`, Voorbeeld 10: volledige deployment-pipeline (Taskfile), Voorbeeld 7: i18n-vertalingen genereren, Voorbeeld 6: meertalig model genereren en terugschrijven naar EA, Voorbeeld 2: Excel-specificatie genereren, SEO / JSON-LD structured data via overrides/main.html, MkDocs Material site-configuratie

### Community 68 - "config.py"
Cohesion: 0.38
Nodes (5): _int_or_default(), _optional_int(), Environment-variable configuration for the translation pipeline. crunch_uml is…, Split a comma-separated env value into a tuple of stripped entries., _split_csv()

### Community 69 - "I18nRenderer (i18n)"
Cohesion: 0.32
Nodes (8): Laag 6: Hulpmodules (util, lang, exceptions, templates), I18nParser (i18n), Vertaal-fallbackketen, I18nRenderer (i18n), Ollama vertaal-backend, Opaque-token preserve-filter, reconcile_case safety net, translate_data — drie-passes vertaalpijplijn

### Community 70 - "test_15b_updateEAMIMModel_GGM_Complete.py"
Cohesion: 0.29
Nodes (4): copy_test_files(), fixture, slow, test_import_monumenten()

### Community 71 - "test_15c_updateEAMIMModel_GGM_Inkomen.py"
Cohesion: 0.29
Nodes (4): copy_test_files(), fixture, slow, test_import_monumenten()

### Community 72 - "build.yml test job (Python 3.10-3.13 matrix)"
Cohesion: 0.33
Nodes (6): Coveralls coverage upload (main only), build.yml lint job, build.yml test job (Python 3.10-3.13 matrix), Publish to PyPI on tag push, release.yml release job, Development toolchain (black, flake8, isort, mypy, pytest, bandit, build, twine)

### Community 73 - "build_context_map"
Cohesion: 0.47
Nodes (5): ContextMap, _build(), build_context_map(), Context enrichment for element translation. The i18n data structure is flat…, Build the (section, GUID) → context dict map for one schema.

### Community 74 - "TermbankIndex"
Cohesion: 0.24
Nodes (5): _norm(), Normalise a term for index keys: casefold and collapse whitespace., All loaded concepts, indexed by (normalised label, language)., Find translation candidates: exact match on the normalised source label first,…, TermbankIndex

### Community 75 - "conftest.py"
Cohesion: 0.47
Nodes (5): isolated_test_database(), mock_function(), fixture, Run the whole suite against a database file outside the repository. The…, test_setup_output_directory()

### Community 76 - "test_15a_updateEAMIMModel.py"
Cohesion: 0.40
Nodes (4): copy_test_files(), getRecordFromEARepository(), fixture, test_import_monumenten()

### Community 77 - "test_16a_export_i18n_rsgb.py"
Cohesion: 0.33
Nodes (4): copy_test_files(), fixture, slow, test_import_monumenten()

### Community 78 - "test_16_export_i18n.py"
Cohesion: 0.36
Nodes (7): is_valid_i18n_file(), copy_test_files(), getRecordFromEARepository(), fixture, slow, test_import_monumenten(), test_import_monumenten_met_update()

### Community 79 - "Design Patterns (pagina)"
Cohesion: 0.70
Nodes (5): Decorator Pattern (@register), Design Patterns (pagina), Design Patterns (EN), Registry Pattern, Kernprincipe: Registry-driven uitbreidbaarheid

### Community 80 - "test_05b_csv_parser_renderer_mapper.py"
Cohesion: 0.47
Nodes (5): are_csv_files_equal(), check_value_in_csv(), Vergelijk twee CSV-bestanden efficiënt met Pandas. :param file1: Pad naar het…, Controleer of een rij in een CSV-bestand waar 'GGM_guid' gelijk is aan een…, test_csv_parser_renderer()

### Community 81 - "test_06d_xlsx_parser_renderer_mapper.py"
Cohesion: 0.47
Nodes (5): are_xlsx_files_equal(), check_value_in_xlsx(), Vergelijk twee Excel-bestanden efficiënt met Pandas. :param file1: Pad naar het…, Controleer of een rij in een CSV-bestand waar 'GGM_guid' gelijk is aan een…, test_csv_parser_renderer()

### Community 82 - "test_importAndTransform_schuldhulp"
Cohesion: 0.67
Nodes (3): slow, test_importAndTransform_schuldhulp(), validate_json_schema()

### Community 83 - "test_45_pack.py"
Cohesion: 0.12
Nodes (20): _dispose_singleton(), packed(), parse_to_sqlite(), fixture, parametrize, slow, `crunch_uml pack`: EA model file -> row artifact (.cua.gz). The artifact is…, Well-formed head and tail, broken middle: the parser refuses it (no recover). (+12 more)

### Community 84 - "test_13_json_schema.py"
Cohesion: 0.40
Nodes (3): Regression test for the 'primitive shadows enumeration' bug. An attribute typed…, test_enum_attributes_render_as_ref(), test_import_schuldhulp()

### Community 85 - "fix_and_format_text"
Cohesion: 0.17
Nodes (12): fix_and_format_text(), fix_mojibake(), _html_to_markdown_lines(), _preprocess_plain_lists(), Helper: - HTML → Markdown (incl. lijsten) via markdownify - HTML-entities…, Formatteert en escapt tekst afhankelijk van het doel: - mode="markdown": *…, Preprocess tekst vóór markdownify: converteer plain-text opsommingstekens (■,…, md1() (+4 more)

### Community 87 - "test_40_qea_xmi_pariteit.py"
Cohesion: 0.13
Nodes (23): assert_no_empty_ids(), _dispose_singleton(), ggm240(), ids(), inkomen(), parse_into(), fixture, slow (+15 more)

### Community 88 - "Development tooling (pytest, black, isort, mypy, flake8, bandit)"
Cohesion: 0.67
Nodes (3): Doorlopende activiteiten (quality, testing, CI/CD, packaging), Development tooling (pytest, black, isort, mypy, flake8, bandit), Kwaliteitseisen per fase (pytest, mypy, ruff, CHANGELOG, versiebump)

### Community 89 - "src_cursor"
Cohesion: 0.67
Nodes (3): fixture, A cursor on the raw .qea SQLite file., src_cursor()

### Community 90 - "test_42_invoer_hardening.py"
Cohesion: 0.11
Nodes (22): _clean_env(), _dispose_singleton(), _import_counting_statements(), fixture, parametrize, Hardening for untrusted input (0.7.0). * ``translators`` is imported lazily: it…, The prolog scan reads 64 KiB; a DOCTYPE behind a longer comment is caught on…, recover=False: a truncated export fails loudly instead of importing half a… (+14 more)

### Community 91 - "pack.py"
Cohesion: 0.13
Nodes (15): add_args(), _IsolatedDatabase, pack(), PackError, _parse(), Exception, ``crunch_uml pack``: turn an EA model file into a row artifact (``.cua.gz``).…, Parse ``source`` into the SQLite file; returns the class count. (+7 more)

### Community 96 - "test_06_xlsx_parser_renderer.py"
Cohesion: 0.67
Nodes (3): are_excel_files_equal(), test_xlsx_parser_and_changes(), test_xlsx_parser_renderer()

### Community 97 - "load_xmi"
Cohesion: 0.19
Nodes (16): extract_declared_encoding(), load_xmi(), count_detect(), fixture, Encoding-afhandeling van de XMI-loader. ``chardet.detect()`` leest het…, Vervang chardet.detect door een teller die de echte detectie doet., Het hete pad: encoding staat in de header, dus geen detectie., Niet-UTF8 met declaratie: nog steeds geen detectie, wel juiste tekens. (+8 more)

### Community 98 - "test_15_updateEAModel.py"
Cohesion: 0.18
Nodes (16): parse_date(), copy_test_files(), countAttributesOfObject(), countConnectorsByType(), countObjectsByType(), countTagsOfObject(), getRecordFromEARepository(), fixture (+8 more)

### Community 99 - "artifact.py"
Cohesion: 0.23
Nodes (12): ArtifactError, _Cleaner, _dumps(), Exception, Writer of the crunch_uml row artifact (``.cua.gz``), standard library only. The…, Write the artifact for ``tables`` of the SQLite file ``sqlite_path`` to…, The SQLite database cannot be written as an artifact., Converts SQLite values to JSON values and counts what had to be changed. (+4 more)

### Community 100 - "test_43_versie.py"
Cohesion: 0.17
Nodes (11): _common_dir(), producer_build(), Single source of the crunch_uml version. ``setup.py`` reads ``__version__``…, The git commit this code runs from, or ``'pypi'`` for an installed release.…, The shared git directory of a worktree (its ``commondir`` file), else ``git``…, _dispose_singleton(), parametrize, Version metadata (0.7.0): one source, reported truthfully. 0.6.0 run markers… (+3 more)

### Community 105 - ".render"
Cohesion: 0.26
Nodes (6): getJSONDatatype(), getVerplichteAttributen(), Render the model packages into simple HTML files., Render a single markdown file containing an overview of all models., Render ER diagrams in DOT format for each model package. The output can then be…, Render the OpenAPI YAML file for the model schema.

### Community 106 - "test_20_i18n_translate_dedup.py"
Cohesion: 0.19
Nodes (14): _make_data(), Fast mock-based tests for I18nRenderer.translate_data. These tests exercise the…, update_i18n=False must translate every string, ignoring original_i18n., Every completed translation must be logged at INFO level with an ``[n/total]``…, Empty/whitespace strings and non-string values are never translated., Build a small data dict with controlled (key, value) repetition. Each entry has…, 100 entries × 2 fields = 200 fields, but only 5 unique values per field (10…, When original_i18n already contains a translation for (section, key, field),… (+6 more)

### Community 107 - "test_39_herimport_diagrammen.py"
Cohesion: 0.21
Nodes (14): _counts(), _db_url(), _dispose_singleton(), _import(), fixture, Herimport van een model in een database die het al kent. Diagrammen werden met…, Dezelfde garantie voor de QEA-parser, die zijn diagrammen langs een ander pad…, De Database-singleton overleeft tests; dispose ervoor en erna zodat een… (+6 more)

### Community 108 - "test_22_ollama_translator.py"
Cohesion: 0.21
Nodes (13): Remove surrounding quotes / fences that the LLM sometimes adds., _strip_response(), _capture(), Tests for the Ollama translation backend. All tests are mock-based — no real…, Replace ``requests.post`` with a stub and capture each call's args., End-to-end: LLM returns whitespace for a camelCase source — the final returned…, test_strip_response_handles_plain_text(), test_strip_response_removes_code_fences() (+5 more)

### Community 111 - "ea_ids.py"
Cohesion: 0.18
Nodes (11): guid_to_ea_id(), normalize_ea_id(), placeholder_class_id(), Identifier rules shared by the ``qea`` and ``eaxmi`` parsers. Both parsers must…, Convert an EA GUID (``{X-Y-...}`` or ``{{X-Y-...}}``) to ``<prefix>_X_Y_...``.…, Normalize an XMI id such as ``EAID_{X_Y}`` or ``EAID_{{X_Y}}`` to ``EAID_X_Y``.…, Deterministic id for a placeholder class of a dangling association end., parametrize (+3 more)

### Community 112 - "EAMIMRepoUpdater"
Cohesion: 0.23
Nodes (6): EAMIMRepoUpdater, register, Connects to an Enterprise Architect repository by treating it as a database…, Set the stereotype for the recordtype., Infer datatype based on the value., Haalt objecten op uit t_object waar: - Object_Type = 'Datatype', of -…

### Community 113 - "xmlsafe.py"
Cohesion: 0.24
Nodes (10): make_parser(), parse_bytes(), One hardened lxml configuration for XML read from files crunch_uml does not…, The XML document contains constructs that are refused for safety., An ``etree.XMLParser`` with the hardened options (plus overrides such as…, Raise :class:`XMLForbiddenError` when a document type declaration is present.…, Parse XML bytes with the hardened parser and refuse DOCTYPEs., reject_doctype() (+2 more)

### Community 125 - "make_mini_m4_fixture.py"
Cohesion: 0.25
Nodes (9): a(), eaid(), end_id(), guid(), Generate the MiniM4 fixture pair: test/data/MiniM4.qea and…, XML attribute string in keyword order; '__' in a key becomes ':' (xmi__type ->…, EA derives association end ids by overwriting the first two hex digits:…, Deterministic EA-style GUID number n: {4D4E0000-0000-4000-8000-0000000000nn}. (+1 more)

### Community 126 - "synthetic_id"
Cohesion: 0.22
Nodes (8): Deterministic id for an element without a source GUID. ``dup_index`` is the…, Mints :func:`synthetic_id` values, tracking the duplicate index per owner and…, synthetic_id(), SyntheticIdMinter, test_attributen_zonder_guid_krijgen_synthetische_ids(), test_enumeratiewaarden_zonder_isliteral_zijn_waarden(), test_minter_telt_duplicaten_per_eigenaar_en_naam(), test_synthetic_id_is_stabiel_en_onderscheidend()

### Community 127 - "reconcile_case"
Cohesion: 0.20
Nodes (10): detect_case(), force_case(), Rejoin ``words`` in the given identifier style., Best-effort split of a translation string into words. Handles spaces,…, Make the translation match the source's identifier style. No-op when the source…, Classify the identifier-casing style of ``s``. Returns one of the ``_CASE_*``…, reconcile_case(), _split_words() (+2 more)

### Community 128 - "Fase 3: nieuwe XMI-renderer (renderers/xmirenderer.py)"
Cohesion: 0.22
Nodes (10): EA Repo Updater destructieve operaties, Voorbeeld 9: EA Repository bijwerken met MIM-tags, Example 9a: export model including diagrams as EA XMI (EN), Voorbeeld 9a: model inclusief diagrammen exporteren als EA XMI, EA-quirks (y-tekenconventies, labelgeometrie, dubbele elementen), Fase 2: eaxmi- en qea-parsers lezen geometrie, Fase 3: nieuwe XMI-renderer (renderers/xmirenderer.py), Fase 4: overige parsers/renderers + dekkingsmatrix (+2 more)

### Community 130 - "Onderwijs_42c2c682.md"
Cohesion: 0.25
Nodes (7): Sheet: associaties, Sheet: attributes, Sheet: classes, Sheet: enumeratieliterals, Sheet: enumeraties, Sheet: generalizations, Sheet: packages

### Community 131 - "lang.py"
Cohesion: 0.29
Nodes (6): Probeert een vertaling uit te voeren en bij een fout probeert het opnieuw, met…, translate(), Without the env-var set, lang.translate must NOT touch ollama_translator., test_lang_translate_default_backend_skips_ollama(), test_lang_translate_falls_back_to_translators_when_ollama_raises(), test_lang_translate_routes_to_ollama_when_backend_env_set()

### Community 133 - "._diff_entity_fields"
Cohesion: 0.29
Nodes (5): _norm(), Normalise a field value to a comparable string (with FK resolution)., Compare field-by-field. Returns list of {field, label, old, new}., Normalise field values so '' and None compare equal. Also collapses…, _safe_get()

### Community 134 - "_propagate_translate_args_to_env"
Cohesion: 0.33
Nodes (6): _propagate_translate_args_to_env(), Push any explicitly-set translation CLI args into ``os.environ`` so deeper…, ``--translate_backend``, ``--ollama_model`` etc. on the CLI must end up in…, If the CLI omits a flag, any pre-existing env-var must remain., test_cli_args_leave_env_alone_when_not_specified(), test_cli_args_propagate_to_env()

### Community 135 - "test_17_qea_parser.py"
Cohesion: 0.40
Nodes (4): EA leaves t_attribute.ea_guid NULL for some literals/attributes. The parser…, Test importing from an Enterprise Architect .qea repository file., test_import_monumenten_qea(), test_import_qea_with_null_ea_guid_attributes()

### Community 137 - "test_05a_json_parser_renderer_mapper.py"
Cohesion: 0.50
Nodes (3): are_json_files_equal(), Vergelijk twee JSON-bestanden en negeer specifieke velden tijdens de…, test_json_parser_renderer()

### Community 138 - "test_translate_preserves_opaque_tokens_without_llm"
Cohesion: 0.50
Nodes (4): parametrize, For tokens that have no meaningful translation, return the source verbatim.…, test_reconcile_case_examples(), test_translate_preserves_opaque_tokens_without_llm()

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
- **67 isolated node(s):** `Sheet: classes`, `Sheet: packages`, `Sheet: classes`, `Sheet: attributes`, `Sheet: enumeraties` (+62 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **25 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

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
- **Why does `CrunchException` connect `CrunchException` to `Database`, `RendererRegistry`, `EARepoUpdater`, `Schema`, `.render`, `db.py`, `xmiparser.py`, `UML_Generic`, `.get_copy`, `test_32_diagram_geometry_model.py`, `Package`, `Class`, `EAMIMRepoUpdater`, `xmlsafe.py`, `renderer.py`, `lodrenderer.py`, `parser.py`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._