import itertools
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Set

import pandas as pd
import sqlalchemy
from sqlalchemy.ext.hybrid import hybrid_property

import crunch_uml.schema as sch
from crunch_uml import const, db, lang, util
from crunch_uml.renderers.renderer import Renderer, RendererRegistry

logger = logging.getLogger()


def object_as_dict(obj, session):
    """
    Converteert een SQLAlchemy-modelobject naar een dictionary, inclusief hybride attributen en kolommen.
    :param obj: Het SQLAlchemy-object.
    :return: Dictionary met alle kolom- en hybride attributen.
    """
    # Haal kolom-attributen op
    col_attrs = {attr.key for attr in sqlalchemy.inspect(obj).mapper.column_attrs}
    hyb_attrs = {
        attr
        for attr in dir(obj.__class__)
        if hasattr(getattr(obj.__class__, attr), 'descriptor')
        and isinstance(getattr(obj.__class__, attr).descriptor, hybrid_property)
    }
    attrs = col_attrs | hyb_attrs

    dict_obj = {key: getattr(obj, key) for key in dir(obj) if key in attrs and hasattr(obj, key)}

    # Dirty hack, but only way: set package domain name to domain_iv3
    if const.COLUMN_DOMEIN_IV3 in attrs and (isinstance(obj, db.Class) or isinstance(obj, db.Enumeratie)):
        package = (
            session.query(db.Package)
            .filter(db.Package.id == obj.package_id, db.Package.schema_id == obj.schema_id)
            .one_or_none()
        )
        dict_obj[const.COLUMN_DOMEIN_IV3] = package.domain_name if package is not None else obj.domein_iv3
    dict_obj[const.COLUMN_DOMEIN_GGM_UML_TYPE] = obj.__class__.__name__
    dict_obj[const.COLUMN_DOMEIN_DATUM_TIJD_EXPORT] = util.current_time_export()

    return dict_obj


@RendererRegistry.register(
    "json",
    descr="Renders JSON document where each element corresponds to one of the tables in the datamodel.",
)
class JSONRenderer(Renderer):
    def get_record_type(self):
        return const.RECORD_TYPE_RECORD

    def get_all_data(self, args, schema: sch.Schema, empty_values=True):
        # Retrieve all models dynamically
        base = db.Base
        models = base.metadata.tables
        session = schema.get_session()
        all_data = {}

        # Define the list of column names to include in the output
        # If this list is empty, all columns will be included
        included_columns = self.get_included_columns(args)

        for table_name, table in models.items():
            # Model class associated with the table
            model = base.model_lookup_by_table_name(table_name)
            if (
                not model or self.get_record_type() == const.RECORD_TYPE_INDEXED and "id" not in model.__table__.columns
            ):  # In case of a junction table
                continue

            records = session.query(model).filter(model.schema_id == schema.schema_id).all()
            data = [object_as_dict(record, session) for record in records]

            # Filter columns based on included_columns, unless included_columns is empty
            filtered_data = []
            for record in data:
                if included_columns and len(included_columns) > 0:
                    filtered_record = {
                        key: value
                        for key, value in record.items()
                        if key in included_columns and (empty_values or value is not None)
                    }
                    filtered_record = util.reorder_dict(filtered_record, included_columns)
                else:
                    filtered_record = record  # Include all columns if included_columns is empty
                if len(filtered_record) > 0:
                    filtered_data.append(
                        filtered_record
                        if self.get_record_type() == const.RECORD_TYPE_RECORD
                        else {record["id"]: filtered_record}
                    )

            all_data[table_name] = filtered_data
        return all_data

    def rename_keys(self, input_dict, key_mapper):
        """
        Hernoem keys in een dictionary (inclusief geneste dictionaries) volgens een gegeven mapper.
        :param input_dict: De originele dictionary waarvan de keys moeten worden hernoemd.
        :param key_mapper: Een dictionary waarin oude keys worden gekoppeld aan nieuwe keys.
        :return: Een nieuwe dictionary met hernoemde keys.
        """
        if key_mapper is None or len(key_mapper) == 0:
            return input_dict

        renamed_dict = {}
        for k, v in input_dict.items():
            # Hernoem de key volgens de mapper
            new_key = key_mapper.get(k, k)

            # Controleer of de waarde een geneste dictionary is
            if isinstance(v, dict):
                # Roep de functie recursief aan voor de geneste dictionary
                renamed_dict[new_key] = self.rename_keys(v, key_mapper)
            elif isinstance(v, list):
                # Als de waarde een lijst is, controleer of elementen dictionaries zijn
                renamed_dict[new_key] = [
                    self.rename_keys(item, key_mapper) if isinstance(item, dict) else item for item in v
                ]
            else:
                # Anders gebruik de originele waarde
                renamed_dict[new_key] = v
        return renamed_dict

    def render(self, args, schema: sch.Schema):
        all_data = self.get_all_data(args, schema)
        all_data = self.rename_keys(all_data, json.loads(args.mapper))
        with open(args.outputfile, "w") as json_file:
            json.dump(all_data, json_file, default=str, indent=4, sort_keys=True)


@RendererRegistry.register(
    "i18n",
    descr=(
        "Renders a i18n file containing all tables with keys to the translatable fields"
        f" ({const.LANGUAGE_TRANSLATE_FIELDS}) Also translates to a specified language."
    ),
)
class I18nRenderer(JSONRenderer):
    def get_included_columns(self, args):
        # Define the list of column names to include in the output
        # If this list is empty, all columns will be included
        return const.LANGUAGE_TRANSLATE_FIELDS

    def get_record_type(self):
        return const.RECORD_TYPE_INDEXED

    @staticmethod
    def _index_existing_i18n(original_i18n, to_language) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Index existing translations once: section -> key -> {field: value}.
        This is the translation memory of the pipeline: whatever is already
        in the i18n file is reused and never re-translated."""
        existing_index: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for section, entries in original_i18n.get(to_language, {}).items():
            sec_idx: Dict[str, Dict[str, Any]] = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for key, fields in entry.items():
                    if isinstance(fields, dict):
                        sec_idx[key] = fields
            existing_index[section] = sec_idx
        return existing_index

    def translate_data(self, data, to_language, from_language="auto", update_i18n=True, original_i18n={}, schema=None):
        """Translate every string field of ``data`` into ``to_language``.

        Backend selection via ``CRUNCH_UML_TRANSLATE_BACKEND``: the value
        ``pipeline`` routes to the element-based translation pipeline (see
        :mod:`crunch_uml.translation`); any other value keeps the original
        string-based flow below.

        Two optimisations over the original per-string loop:

        * **Dedup** — many strings repeat across the model (codelijst-namen,
          shared phrases like "Datum begin geldigheid"). We collect the
          unique values that still need translating and call the translator
          once per value.
        * **Parallel** — the ``translators`` library does one synchronous
          HTTP request per call; running them on a small ThreadPool reduces
          the total wall time roughly linearly with the worker count, up to
          the free translator API's rate limit. The pool size is
          configurable via ``CRUNCH_UML_TRANSLATE_WORKERS`` (default 8).

        Behaviour-preserving: when ``update_i18n=True`` and a previous
        translation for a (section, key, field) exists in ``original_i18n``,
        that value is reused unchanged, just like the old code.
        """
        logger.info(
            f"Starting Translating data to language '{to_language}'. This may take a while:"
            f" {util.count_dict_elements(data)} entries..."
        )

        backend = os.environ.get("CRUNCH_UML_TRANSLATE_BACKEND", "translators").lower()
        if backend == "pipeline":
            return self._translate_data_pipeline(data, to_language, from_language, update_i18n, original_i18n, schema)

        existing_index = self._index_existing_i18n(original_i18n, to_language)

        def _existing(section: str, key: str, field: str):
            if not update_i18n:
                return None
            return existing_index.get(section, {}).get(key, {}).get(field)

        # Per-call context support. When CRUNCH_UML_TRANSLATE_CONTEXT=1, the
        # dedup cache is keyed by (value, section, field) and each call to
        # lang.translate gets a context dict — improves consistency on
        # domain terminology when the Ollama backend is active. With the env
        # var unset (default) the behaviour is identical to before: dedup on
        # value alone, no context passed.
        context_enabled = os.environ.get("CRUNCH_UML_TRANSLATE_CONTEXT", "0") == "1"

        # Pass 1 — collect the unique cache keys that need a live
        # translation. Strings that already have an entry in original_i18n
        # are skipped (their cached value is reused in pass 3).
        # Cache key shape:
        #   context disabled: just the source string
        #   context enabled:  (value, section, field) — context-aware
        to_translate: Set[Any] = set()
        for section, entries in data.items():
            for entry in entries:
                for key, record in entry.items():
                    for field, value in record.items():
                        if not isinstance(value, str) or util.is_empty_or_none(value):
                            continue
                        if _existing(section, key, field) is not None:
                            continue
                        cache_key = (value, section, field) if context_enabled else value
                        to_translate.add(cache_key)

        # Pass 2 — translate the unique entries on a ThreadPool. Each call
        # is independent and synchronous; the GIL is released during the
        # underlying HTTP request, so this scales near-linearly. We also
        # log every completed translation at INFO level so users running a
        # long batch (especially via Ollama) can watch progress in real
        # time. ``itertools.count`` is GIL-atomic so it works across the
        # worker threads without an explicit lock.
        translations: Dict[Any, str] = {}
        if to_translate:
            workers = max(1, int(os.environ.get("CRUNCH_UML_TRANSLATE_WORKERS", "8")))
            total = len(to_translate)
            logger.info(f"Translating {total} unique strings using {workers} worker(s)...")

            progress = itertools.count(1)
            # Width for the [n/total] counter, padded so logs align visually.
            width = len(str(total))

            def _trim(text: Any, limit: int = 80) -> str:
                s = str(text).replace("\n", "\\n").replace("\r", "")
                return s if len(s) <= limit else s[: limit - 1] + "…"

            def _do_translate(item: Any) -> str:
                if context_enabled:
                    v, section, field = item
                    ctx = {"section": section, "field": field}
                else:
                    v = item
                    ctx = None
                result = lang.translate(
                    v,
                    to_language=to_language,
                    from_language=from_language,
                    context=ctx,
                    max_retries=1,
                )
                idx = next(progress)
                logger.info(f"[{idx:{width}d}/{total}] {_trim(v)} → {_trim(result)}")
                return result

            unique_list = list(to_translate)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(_do_translate, unique_list))
            translations = dict(zip(unique_list, results))

        # Pass 3 — rebuild the output structure, preserving the exact shape
        # and ordering of the original implementation (one entry per input
        # entry, keyed by the entry's last key).
        translated_data: Dict[str, List[Dict[str, Any]]] = {}
        for section, entries in data.items():
            logger.info(f"Translating section {section}...")
            out_entries: List[Dict[str, Any]] = []
            for entry in entries:
                translated_record: Dict[str, Any] = {}
                last_key = None
                for key, record in entry.items():
                    last_key = key
                    for field, value in record.items():
                        if not isinstance(value, str) or util.is_empty_or_none(value):
                            continue
                        pre = _existing(section, key, field)
                        if pre is not None:
                            translated_record[field] = pre
                        else:
                            cache_key = (value, section, field) if context_enabled else value
                            translated_record[field] = translations.get(cache_key, value)
                if last_key is not None:
                    out_entries.append({last_key: translated_record})
            translated_data[section] = out_entries

        logger.info(f"Finished translating data to language '{to_language}'.")
        return translated_data

    def _translate_data_pipeline(self, data, to_language, from_language, update_i18n, original_i18n, schema):
        """Element-based translation via the layered pipeline (backend
        ``pipeline``, see :mod:`crunch_uml.translation`).

        The i18n file is the translation memory: fields with an existing
        translation per (section, GUID, field) are excluded up front, so an
        element only reaches the pipeline with its actually missing fields.
        Elements are enriched with model/package/class context from the
        schema before translation.
        """
        from crunch_uml.translation.context import build_context_map
        from crunch_uml.translation.llm import Element
        from crunch_uml.translation.pipeline import TranslationPipeline
        from crunch_uml.translation.preflight import run_preflight

        # The pipeline needs a concrete source language (termbank lookup and
        # prompts): 'auto' falls back to the model's default language.
        from_lang = from_language if from_language and from_language != "auto" else const.DEFAULT_LANGUAGE
        if from_lang != from_language:
            logger.info(f"Brontaal 'auto' wordt door de pijplijn niet ondersteund; brontaal '{from_lang}' aangenomen.")

        existing_index = self._index_existing_i18n(original_i18n, to_language) if update_i18n else {}

        def _existing(section: str, key: str, field: str):
            return existing_index.get(section, {}).get(key, {}).get(field)

        context_map = build_context_map(schema) if schema is not None else {}

        elements = []
        for section, entries in data.items():
            for entry in entries:
                for key, record in entry.items():
                    pending = {
                        field: value
                        for field, value in record.items()
                        if isinstance(value, str)
                        and not util.is_empty_or_none(value)
                        and _existing(section, key, field) is None
                    }
                    if pending:
                        elements.append(
                            Element(
                                section=section, key=key, fields=pending, context=context_map.get((section, key), {})
                            )
                        )

        results: Dict[Any, Dict[str, str]] = {}
        if elements:
            logger.info(f"Vertaalpijplijn: {len(elements)} elementen met ontbrekende vertalingen...")
            # Alleen de taal-paren van deze run laden: dat houdt grote
            # termbanken (volledige IATE-export) geheugen-begrensd.
            pipeline = TranslationPipeline(run_preflight(languages={from_lang, to_language}))
            results = pipeline.translate_elements(elements, to_language, from_lang)

        # Rebuild the output structure, preserving the exact shape and
        # ordering of the string-based flow.
        translated_data: Dict[str, List[Dict[str, Any]]] = {}
        for section, entries in data.items():
            out_entries: List[Dict[str, Any]] = []
            for entry in entries:
                translated_record: Dict[str, Any] = {}
                last_key = None
                for key, record in entry.items():
                    last_key = key
                    for field, value in record.items():
                        if not isinstance(value, str) or util.is_empty_or_none(value):
                            continue
                        pre = _existing(section, key, field)
                        if pre is not None:
                            translated_record[field] = pre
                        else:
                            translated_record[field] = results.get((section, key), {}).get(field, value)
                if last_key is not None:
                    out_entries.append({last_key: translated_record})
            translated_data[section] = out_entries

        logger.info(f"Finished translating data to language '{to_language}'.")
        return translated_data

    def render(self, args, schema: sch.Schema):

        logger.info(f"Starting rendering i18n file {args.outputfile}...")

        # Initialize the i18n structure
        i18n_data = {}
        if os.path.exists(args.outputfile):
            # If the file exists, check if it's a valid JSON (i18n) file and load it
            with open(args.outputfile, "r", encoding="utf-8") as json_file:
                try:
                    i18n_data = json.load(json_file)
                except json.JSONDecodeError:
                    raise ValueError(f"The file {args.outputfile} is not a valid JSON file.")

            if not isinstance(i18n_data, dict):
                raise ValueError(f"The file {args.outputfile} does not contain a valid i18n structure.")

        # Retrieve all data
        all_data = self.get_all_data(args, schema, empty_values=False)
        if args.translate:
            all_data = self.translate_data(
                all_data,
                args.language,
                from_language=args.from_language,
                update_i18n=True,
                original_i18n=i18n_data,
                schema=schema,
            )

        # Update the i18n data with the new language entry
        i18n_data[args.language] = all_data

        # Map fields
        i18n_data = self.rename_keys(i18n_data, json.loads(args.mapper))

        # Controleer of het bestand al bestaat
        if not os.path.exists(args.outputfile):
            logger.info(f"Vertaalbestand {args.outputfile} bestaat niet, maak een nieuw bestand aan...")

        # Write the updated i18n data back to the file
        with open(args.outputfile, "w", encoding="utf-8") as json_file:
            json.dump(i18n_data, json_file, ensure_ascii=False, indent=4, default=str)

        logger.info(f"Rendering i18n file {args.outputfile} success")


@RendererRegistry.register(
    "csv",
    descr="Renders multiple CSV files where each file corresponds to one of the tables in the datamodel.",
)
class CSVRenderer(Renderer):
    def render(self, args, schema: sch.Schema):
        # Retrieve all models dynamically
        base = db.Base
        models = base.metadata.tables
        session = schema.get_session()
        entity_name = args.entity_name

        for table_name, table in models.items():
            # Model class associated with the table
            model = base.model_lookup_by_table_name(table_name)
            if not model:  # In geval van koppeltabel
                continue

            # check of entity_name is gegeven en niet gelijk is aan table_name
            if entity_name is not None and entity_name != table_name:
                continue

            # Retrieve data
            records = session.query(model).filter(model.schema_id == schema.schema_id).all()
            df = pd.DataFrame([object_as_dict(record, session) for record in records])

            # Map columns
            mapper = json.loads(args.mapper)
            if mapper is not None and len(mapper) > 0:
                df = df.rename(columns=mapper)

            df.to_csv(f"{args.outputfile}_{table_name}.csv", index=False)


@RendererRegistry.register(
    "shex",
    descr="Renderer that generates Shape Expressions (ShEx) schema from the model.",
)
class SHexRenderer(Renderer):
    """
    Render de Shape Expressions (ShEx) van het model naar een .shex bestand.

    Args:
        args: Argumenten waaronder de bestandsnaam (zonder extensie).
        schema (sch.Schema): Het informatiemodel met alle pakketten en klassen.

    Output:
        Een ShEx-bestand (.shex) dat de klassen en attributen beschrijft.
    """

    def render(self, args, schema: sch.Schema):
        filename, _ = os.path.splitext(args.outputfile)
        with open(f"{filename}.shex", "w") as f:
            for pkg in schema.get_all_packages():
                for clazz in pkg.classes:
                    # Start de beschrijving van een ShEx shape voor elke klasse
                    f.write(f"<{clazz.name}> {{\n")
                    for attr in clazz.attributes:
                        # Voeg een propertyregel toe voor elk attribuut met naam en datatype
                        f.write(f"  {attr.name} xsd:{attr.datatype} ;\n")
                    f.write("}\n\n")


@RendererRegistry.register(
    "profile",
    descr="Renderer that generates a simple data profile (per class) from the database.",
)
class DataProfilerRenderer(Renderer):
    def render(self, args, schema: sch.Schema):
        session = schema.get_session()
        base = db.Base
        models = base.metadata.tables
        with open(args.outputfile, "w") as out:
            for table_name in models:
                model = base.model_lookup_by_table_name(table_name)
                if not model:
                    continue
                count = session.query(model).filter(model.schema_id == schema.schema_id).count()
                out.write(f"{table_name}: {count} records\n")


@RendererRegistry.register(
    "uml_mmd",
    descr="Renderer that generates UML-style class diagram using Mermaid.js syntax.",
)
class UMLClassDiagramRenderer(Renderer):
    def render(self, args, schema: sch.Schema):
        filename, _ = os.path.splitext(args.outputfile)
        with open(f"{filename}.mmd", "w") as f:
            f.write("classDiagram\n")
            for pkg in schema.get_all_packages():
                for clazz in pkg.classes:
                    f.write(f"  class {clazz.name} {{\n")
                    for attr in clazz.attributes:
                        f.write(f"    +{attr.name}: {attr.datatype}\n")
                    f.write("  }\n")
                for clazz in pkg.classes:
                    for assoc in getattr(clazz, "uitgaande_associaties", []):
                        if getattr(assoc, "dst_class", None):
                            f.write(f"  {clazz.name} --> {assoc.dst_class.name}\n")


@RendererRegistry.register(
    "model_stats_md",
    descr="Renderer that outputs extended model statistics in Markdown format.",
)
class ModelStatisticsMarkdownRenderer(Renderer):
    def render(self, args, schema: sch.Schema):
        total_packages = len(schema.get_all_packages())
        total_classes = sum(len(pkg.classes) for pkg in schema.get_all_packages())
        total_attributes = sum(len(clazz.attributes) for pkg in schema.get_all_packages() for clazz in pkg.classes)
        total_associations = sum(
            len(getattr(clazz, "uitgaande_associaties", []))
            for pkg in schema.get_all_packages()
            for clazz in pkg.classes
        )
        total_enumerations = sum(len(pkg.enumerations) for pkg in schema.get_all_packages())
        total_enum_values = sum(len(enum.values) for pkg in schema.get_all_packages() for enum in pkg.enumerations)

        avg_attributes_per_class = total_attributes / total_classes if total_classes else 0
        avg_associations_per_class = total_associations / total_classes if total_classes else 0

        with open(args.outputfile, "w") as f:
            f.write("# Model Statistics\n\n")
            f.write(f"- **Packages**: {total_packages}\n")
            f.write(f"- **Classes**: {total_classes}\n")
            f.write(f"- **Attributes**: {total_attributes}\n")
            f.write(f"- **Associations**: {total_associations}\n")
            f.write(f"- **Enumerations**: {total_enumerations}\n")
            f.write(f"- **Enumeration values**: {total_enum_values}\n")
            f.write(f"- **Avg. attributes per class**: {avg_attributes_per_class:.2f}\n")
            f.write(f"- **Avg. associations per class**: {avg_associations_per_class:.2f}\n")

            # Laatste gewijzigde packages
            recent_packages = sorted(
                schema.get_all_packages(),
                key=lambda p: (
                    getattr(p, "modified", float('-inf'))
                    if hasattr(p, "modified")
                    else getattr(p, "created", float('-inf'))
                ),
                reverse=True,
            )[:5]

            f.write("\n## Recently Modified Packages\n\n")
            for pkg in recent_packages:
                f.write(f"- **{pkg.name}** ")
                if hasattr(pkg, "modified") and pkg.updated_at:
                    f.write(f"(last updated: {pkg.updated_at})\n")
                elif hasattr(pkg, "created") and pkg.created_at:
                    f.write(f"(created: {pkg.created_at})\n")
                else:
                    f.write("(no timestamp available)\n")


@dataclass
class _DiffItem:
    key: str
    title: str
    changes: List[str]


# ---------------------------------------------------------------------------
# Helpers shared by the diff renderer.
# ---------------------------------------------------------------------------


# Field labels (Dutch where the model uses Dutch column names).
_FIELD_LABELS: Dict[str, str] = {
    "name": "naam",
    "alias": "alias",
    "definitie": "definitie",
    "toelichting": "toelichting",
    "bron": "bron",
    "stereotype": "stereotype",
    "status": "status",
    "version": "versie",
    "phase": "fase",
    "author": "auteur",
    "uri": "uri",
    "visibility": "zichtbaarheid",
    "is_datatype": "is_datatype",
    "verplicht": "verplicht",
    "primitive": "primitieve type",
    "enumeration_id": "enumeratie",
    "type_class_id": "type (class)",
    "package_id": "package",
    "clazz_id": "class",
    "src_class_id": "src class",
    "dst_class_id": "dst class",
    "src_mult_start": "src mult. start",
    "src_mult_end": "src mult. end",
    "src_role": "src role",
    "src_documentation": "src documentatie",
    "dst_mult_start": "dst mult. start",
    "dst_mult_end": "dst mult. end",
    "dst_role": "dst role",
    "dst_documentation": "dst documentatie",
    "superclass_id": "superclass",
    "subclass_id": "subclass",
    # Tagged-value groups
    "herkomst": "herkomst",
    "herkomst_definitie": "herkomst definitie",
    "begrip": "begrip",
    "datum_opname": "datum opname",
    "gemma_naam": "gemma_naam",
    "gemma_type": "gemma_type",
    "gemma_url": "gemma_url",
    "gemma_definitie": "gemma_definitie",
    "gemma_toelichting": "gemma_toelichting",
    "domein_dcat": "domein_dcat",
    "domein_iv3": "domein_iv3",
    "heeft_tijdlijn_geldigheid": "tijdlijn geldigheid",
    "heeft_tijdlijn_registratie": "tijdlijn registratie",
    "indicatie_formele_historie": "formele historie",
    "indicatie_materiele_historie": "materiele historie",
    "indicatie_in_onderzoek": "in onderzoek",
    "minimumwaarde_inclusief": "min. inclusief",
    "minimumwaarde_exclusief": "min. exclusief",
    "maximumwaarde_inclusief": "max. inclusief",
    "maximumwaarde_exclusief": "max. exclusief",
    "eenheid": "eenheid",
    "populatie": "populatie",
    "kwaliteit": "kwaliteit",
    "synoniemen": "synoniemen",
    "authentiek": "authentiek",
    "lengte": "lengte",
    "patroon": "patroon",
    "formeel_patroon": "formeel patroon",
    "indicatie_classificerend": "classificerend",
    "mogelijk_geen_waarde": "mogelijk geen waarde",
    "nullable": "nullable",
    "modelnaam_kort": "modelnaam (kort)",
    "afkorting": "afkorting",
    "release": "release",
}


# Fields per entity type. Timestamp/identity fields are skipped to avoid noise.
_PACKAGE_FIELDS = [
    "name",
    "alias",
    "stereotype",
    "status",
    "version",
    "phase",
    "author",
    "uri",
    "visibility",
    "definitie",
    "toelichting",
    "bron",
    "afkorting",
    "release",
    "modelnaam_kort",
    "parent_package_id",
    "herkomst",
    "herkomst_definitie",
    "begrip",
    "datum_opname",
    "gemma_naam",
    "gemma_type",
    "gemma_url",
    "gemma_definitie",
    "gemma_toelichting",
    "domein_dcat",
    "domein_iv3",
]

_CLASS_FIELDS = [
    "name",
    "alias",
    "stereotype",
    "status",
    "version",
    "phase",
    "author",
    "uri",
    "visibility",
    "definitie",
    "toelichting",
    "bron",
    "is_datatype",
    "package_id",
    "indicatie_formele_historie",
    "authentiek",
    "nullable",
    "herkomst",
    "herkomst_definitie",
    "begrip",
    "datum_opname",
    "gemma_naam",
    "gemma_type",
    "gemma_url",
    "gemma_definitie",
    "gemma_toelichting",
    "domein_dcat",
    "domein_iv3",
    "populatie",
    "kwaliteit",
    "synoniemen",
]

_ENUM_FIELDS = [
    "name",
    "alias",
    "stereotype",
    "status",
    "version",
    "phase",
    "author",
    "uri",
    "visibility",
    "definitie",
    "toelichting",
    "bron",
    "package_id",
    "herkomst",
    "herkomst_definitie",
    "begrip",
    "datum_opname",
    "gemma_naam",
    "gemma_type",
    "gemma_url",
    "gemma_definitie",
    "gemma_toelichting",
    "domein_dcat",
    "domein_iv3",
]

_ATTR_FIELDS = [
    "name",
    "stereotype",
    "definitie",
    "toelichting",
    "bron",
    "primitive",
    "enumeration_id",
    "type_class_id",
    "verplicht",
    "clazz_id",
    "lengte",
    "patroon",
    "formeel_patroon",
    "indicatie_classificerend",
    "mogelijk_geen_waarde",
    "heeft_tijdlijn_geldigheid",
    "heeft_tijdlijn_registratie",
    "indicatie_formele_historie",
    "indicatie_materiele_historie",
    "indicatie_in_onderzoek",
    "minimumwaarde_inclusief",
    "minimumwaarde_exclusief",
    "maximumwaarde_inclusief",
    "maximumwaarde_exclusief",
    "eenheid",
    "populatie",
    "kwaliteit",
    "synoniemen",
    "authentiek",
    "herkomst",
    "herkomst_definitie",
    "begrip",
    "datum_opname",
]

_ASSOC_FIELDS = [
    "name",
    "stereotype",
    "definitie",
    "toelichting",
    "bron",
    "src_class_id",
    "src_mult_start",
    "src_mult_end",
    "src_role",
    "src_documentation",
    "dst_class_id",
    "dst_mult_start",
    "dst_mult_end",
    "dst_role",
    "dst_documentation",
    "herkomst",
    "herkomst_definitie",
    "begrip",
    "datum_opname",
    "heeft_tijdlijn_geldigheid",
    "heeft_tijdlijn_registratie",
    "indicatie_formele_historie",
    "indicatie_materiele_historie",
    "indicatie_in_onderzoek",
]

_GEN_FIELDS = [
    "name",
    "stereotype",
    "definitie",
    "toelichting",
    "bron",
    "subclass_id",
    "superclass_id",
]


# A change in a *structural* field impacts the model itself: identifiers,
# typing, multiplicity, mandatory-ness, links. A change in a descriptive field
# only updates metadata / documentation (definitie, toelichting, gemma tags,
# release/version/auteur, etc.) without altering the model structure.
_STRUCTURAL_FIELDS: Set[str] = {
    # Identity & containment
    "name",
    "stereotype",
    "is_datatype",
    "package_id",
    "parent_package_id",
    "clazz_id",
    # Attribute typing
    "primitive",
    "enumeration_id",
    "type_class_id",
    "verplicht",
    "lengte",
    "patroon",
    "formeel_patroon",
    "indicatie_classificerend",
    "mogelijk_geen_waarde",
    "nullable",
    "authentiek",
    # Value-range constraints
    "minimumwaarde_inclusief",
    "minimumwaarde_exclusief",
    "maximumwaarde_inclusief",
    "maximumwaarde_exclusief",
    "eenheid",
    # Historiek-flags affect storage shape
    "indicatie_formele_historie",
    "indicatie_materiele_historie",
    "heeft_tijdlijn_geldigheid",
    "heeft_tijdlijn_registratie",
    "indicatie_in_onderzoek",
    # Associations
    "src_class_id",
    "dst_class_id",
    "src_mult_start",
    "src_mult_end",
    "dst_mult_start",
    "dst_mult_end",
    "src_role",
    "dst_role",
    # Generalisaties
    "subclass_id",
    "superclass_id",
}


def _split_changes(
    by_key: Dict[str, List[Dict[str, str]]],
) -> "tuple[Dict[str, List[Dict[str, str]]], Dict[str, List[Dict[str, str]]]]":
    """Split each field-change list into (structural, descriptive) dicts."""
    s: Dict[str, List[Dict[str, str]]] = {}
    d: Dict[str, List[Dict[str, str]]] = {}
    for key, changes in by_key.items():
        sc = [c for c in changes if c["field"] in _STRUCTURAL_FIELDS]
        dc = [c for c in changes if c["field"] not in _STRUCTURAL_FIELDS]
        if sc:
            s[key] = sc
        if dc:
            d[key] = dc
    return s, d


def _norm(v: Any) -> Any:
    """Normalise field values so '' and None compare equal.

    Also collapses leading/trailing whitespace and the literal string ``"nan"``
    (which the XMI parser occasionally produces for empty cells) to ``""`` so
    that they don't show up as fake changes.
    """
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        # Normalise line endings — EA on Windows writes CRLF, other sources LF.
        # Without this every multi-line definition appears as "changed".
        s = v.replace("\r\n", "\n").replace("\r", "\n").strip()
        if s.lower() == "nan":
            return ""
        return s
    return v


def _safe_get(obj: Any, field: str) -> Any:
    return getattr(obj, field) if obj is not None and hasattr(obj, field) else None


def _md_escape(s: Any) -> str:
    return str(s).replace("\n", " ").strip()


def _md_anchor(s: str) -> str:
    """GitHub-style anchor: lowercase, spaces to dashes, drop punctuation."""
    out = []
    for ch in s.lower():
        if ch.isalnum() or ch == "-":
            out.append(ch)
        elif ch in (" ", "_"):
            out.append("-")
    return "".join(out)


def _clean_name(v: Any) -> str:
    """Strip whitespace and treat 'nan' as empty so cosmetic differences in
    names don't ripple into every child's qualified key."""
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() == "nan":
        return ""
    return s


def _qualified_pkg_path(pkg: Any, max_depth: int = 32) -> str:
    """Walk parent_package chain and return 'Top/Sub/Leaf'."""
    if pkg is None:
        return ""
    parts: List[str] = []
    seen: Set[int] = set()
    node = pkg
    for _ in range(max_depth):
        if node is None or id(node) in seen:
            break
        seen.add(id(node))
        parts.append(_clean_name(getattr(node, "name", None)))
        node = getattr(node, "parent_package", None)
    return "/".join(reversed(parts))


def _stable_key(obj: Any, kind: str) -> str:
    """Build a name-based key that survives ea_guid regeneration."""
    if obj is None:
        return ""
    if kind == "package":
        return _qualified_pkg_path(obj)
    if kind in ("class", "enum"):
        pkg_path = _qualified_pkg_path(getattr(obj, "package", None))
        return f"{pkg_path}::{_clean_name(getattr(obj, 'name', None))}"
    if kind == "attribute":
        cls_key = _stable_key(getattr(obj, "clazz", None), "class")
        return f"{cls_key}#{_clean_name(getattr(obj, 'name', None))}"
    if kind == "literal":
        enum_key = _stable_key(getattr(obj, "enumeratie", None), "enum")
        return f"{enum_key}={_clean_name(getattr(obj, 'name', None))}"
    if kind == "association":
        src = _stable_key(getattr(obj, "src_class", None), "class")
        dst = _stable_key(getattr(obj, "dst_class", None), "class")
        return f"{src} --[{_clean_name(getattr(obj, 'name', None))}]--> {dst}"
    if kind == "generalization":
        sub = _stable_key(getattr(obj, "subclass", None), "class")
        sup = _stable_key(getattr(obj, "superclass", None), "class")
        return f"{sub} --> {sup}"
    return getattr(obj, "id", "") or ""


def _match_by_key_or_id(
    a_items: Iterable[Any],
    b_items: Iterable[Any],
    kind: str,
) -> Dict[str, Any]:
    """Match entities from schema A to schema B.

    Strategy: first match by id (zero-change case), then by qualified name
    (catches re-imported entities where ea_guid was regenerated).

    Returns a dict with keys: ``pairs`` (list of (a, b)), ``added`` (B-only),
    ``removed`` (A-only).
    """
    a_list = list(a_items)
    b_list = list(b_items)
    a_by_id: Dict[str, Any] = {str(getattr(a, "id", "")): a for a in a_list if getattr(a, "id", None)}
    b_by_id: Dict[str, Any] = {str(getattr(b, "id", "")): b for b in b_list if getattr(b, "id", None)}
    a_by_key: Dict[str, Any] = {}
    for a in a_list:
        k = _stable_key(a, kind)
        if k and k not in a_by_key:
            a_by_key[k] = a
    b_by_key: Dict[str, Any] = {}
    for b in b_list:
        k = _stable_key(b, kind)
        if k and k not in b_by_key:
            b_by_key[k] = b

    matched_a: Set[int] = set()
    matched_b: Set[int] = set()
    pairs: List[Any] = []

    # Pass 1: identical ids.
    for aid, a in a_by_id.items():
        b = b_by_id.get(aid)
        if b is not None:
            pairs.append((a, b))
            matched_a.add(id(a))
            matched_b.add(id(b))

    # Pass 2: qualified-name fallback on leftovers.
    for key, a in a_by_key.items():
        if id(a) in matched_a:
            continue
        b = b_by_key.get(key)
        if b is None or id(b) in matched_b:
            continue
        pairs.append((a, b))
        matched_a.add(id(a))
        matched_b.add(id(b))

    added = [b for b in b_list if id(b) not in matched_b]
    removed = [a for a in a_list if id(a) not in matched_a]
    return {"pairs": pairs, "added": added, "removed": removed}


def _fmt_value(v: Any) -> str:
    s = _md_escape(v) if v not in (None, "") else ""
    if not s:
        return "_(leeg)_"
    if len(s) > 240:
        s = s[:237] + "…"
    return f"`{s}`"


@RendererRegistry.register(
    "diff_md",
    descr="Top-down Markdown diff between two schema versions (Package → Class/Datatype/Enum → Attribute/Literal).",
)
class SchemaDiffMarkdownRenderer(Renderer):
    """Markdown diff between two schemas.

    Entities are matched first by id, then by qualified-name fallback so that a
    re-import (which can regenerate ea_guid) is recognised as the same logical
    entity instead of being reported as a remove + add pair. Foreign-key fields
    (``enumeration_id``, ``type_class_id``, etc.) are resolved to their target
    entity in each schema and compared by qualified name, which removes the
    misleading ``Enumeratie: X → Enumeratie: X`` noise that the previous
    id-only comparison produced.
    """

    def _get_other_schema(self, schema: sch.Schema, args) -> sch.Schema:
        other_name = getattr(args, "compare_schema_name", None)
        if not other_name:
            raise ValueError("diff_md requires --compare_schema_name <schema_id/schema_name>.")
        return sch.Schema(schema.database, schema_name=other_name)

    # ------------------------------------------------------------------
    # FK resolution
    # ------------------------------------------------------------------

    def _resolve_target(
        self,
        field: str,
        value: Any,
        side_a: bool,
        ctx: Dict[str, Any],
    ) -> str:
        """Return a human-readable qualified key for an FK column value.

        Resolves the id within the *correct* schema (A or B) so that two
        different ea_guids that point to the same logical target collapse to
        the same string and produce no false-positive diff.
        """
        v = str(value or "")
        if not v:
            return ""
        side = "a" if side_a else "b"
        if field == "enumeration_id":
            obj = ctx["enums_by_id"][side].get(v)
            return f"Enumeratie: {_stable_key(obj, 'enum')}" if obj else f"Enumeratie: <onbekend:{v}>"
        if field in ("type_class_id", "clazz_id", "src_class_id", "dst_class_id", "subclass_id", "superclass_id"):
            obj = ctx["classes_by_id"][side].get(v)
            kind = "Datatype" if obj is not None and getattr(obj, "is_datatype", False) else "Class"
            return f"{kind}: {_stable_key(obj, 'class')}" if obj else f"Class: <onbekend:{v}>"
        if field in ("package_id", "parent_package_id"):
            obj = ctx["packages_by_id"][side].get(v)
            return f"Package: {_stable_key(obj, 'package')}" if obj else f"Package: <onbekend:{v}>"
        return v

    def _value_for_diff(self, field: str, raw: Any, side_a: bool, ctx: Dict[str, Any]) -> str:
        """Normalise a field value to a comparable string (with FK resolution)."""
        if field.endswith("_id") and field != "ea_guid":
            return self._resolve_target(field, raw, side_a, ctx)
        return str(_norm(raw))

    def _diff_entity_fields(
        self,
        a: Any,
        b: Any,
        fields: List[str],
        ctx: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Compare field-by-field. Returns list of {field, label, old, new}."""
        out: List[Dict[str, str]] = []
        for f in fields:
            av = self._value_for_diff(f, _safe_get(a, f), side_a=True, ctx=ctx)
            bv = self._value_for_diff(f, _safe_get(b, f), side_a=False, ctx=ctx)
            if av != bv:
                out.append(
                    {
                        "field": f,
                        "label": _FIELD_LABELS.get(f, f),
                        "old": av,
                        "new": bv,
                    }
                )
        return out

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_field_changes(self, changes: List[Dict[str, str]], indent: int = 2) -> List[str]:
        pad = " " * indent
        out: List[str] = []
        for c in changes:
            old = _fmt_value(c["old"])
            new = _fmt_value(c["new"])
            out.append(f"{pad}- **{c['label']}**: {old} → {new}")
        return out

    def _pkg_of_class(self, obj: Any) -> Any:
        return getattr(obj, "package", None)

    def _pkg_of_enum(self, obj: Any) -> Any:
        return getattr(obj, "package", None)

    def _pkg_of_attr(self, obj: Any) -> Any:
        cls = getattr(obj, "clazz", None)
        return getattr(cls, "package", None) if cls is not None else None

    def _pkg_of_assoc(self, obj: Any) -> Any:
        src = getattr(obj, "src_class", None)
        return getattr(src, "package", None) if src is not None else None

    def _pkg_of_gen(self, obj: Any) -> Any:
        sub = getattr(obj, "subclass", None)
        return getattr(sub, "package", None) if sub is not None else None

    def render(self, args, schema: sch.Schema):
        other = self._get_other_schema(schema, args)
        a_name = getattr(other, "schema_id", None) or "old"
        b_name = getattr(schema, "schema_id", None) or "new"
        title = getattr(args, "compare_title", None) or f"Changes from {a_name} to {b_name}"

        # Load entities. NB: A = old (compare schema), B = new (current schema).
        a_pkgs = list(other.get_all_packages())
        b_pkgs = list(schema.get_all_packages())
        a_classes = list(other.get_all_classes())  # includes datatypes
        b_classes = list(schema.get_all_classes())
        a_enums = list(other.get_all_enumerations())
        b_enums = list(schema.get_all_enumerations())
        a_attrs = list(other.get_all_attributes())
        b_attrs = list(schema.get_all_attributes())
        a_literals = list(other.get_all_literals())
        b_literals = list(schema.get_all_literals())
        try:
            a_assocs = list(other.get_all_associations())
            b_assocs = list(schema.get_all_associations())
        except Exception:
            a_assocs, b_assocs = [], []
        try:
            a_gens = list(other.get_all_generalizations())
            b_gens = list(schema.get_all_generalizations())
        except Exception:
            a_gens, b_gens = [], []

        # Indexes used by FK resolution.
        ctx: Dict[str, Any] = {
            "packages_by_id": {
                "a": {str(p.id): p for p in a_pkgs if getattr(p, "id", None)},
                "b": {str(p.id): p for p in b_pkgs if getattr(p, "id", None)},
            },
            "classes_by_id": {
                "a": {str(c.id): c for c in a_classes if getattr(c, "id", None)},
                "b": {str(c.id): c for c in b_classes if getattr(c, "id", None)},
            },
            "enums_by_id": {
                "a": {str(e.id): e for e in a_enums if getattr(e, "id", None)},
                "b": {str(e.id): e for e in b_enums if getattr(e, "id", None)},
            },
        }

        # Match by id, then by qualified key.
        m_pkg = _match_by_key_or_id(a_pkgs, b_pkgs, "package")
        m_cls = _match_by_key_or_id(a_classes, b_classes, "class")
        m_enum = _match_by_key_or_id(a_enums, b_enums, "enum")
        m_attr = _match_by_key_or_id(a_attrs, b_attrs, "attribute")
        m_assoc = _match_by_key_or_id(a_assocs, b_assocs, "association")
        m_gen = _match_by_key_or_id(a_gens, b_gens, "generalization")

        # Compute field-level diffs on common pairs.
        pkg_changes: Dict[str, List[Dict[str, str]]] = {}
        for a, b in m_pkg["pairs"]:
            ch = self._diff_entity_fields(a, b, _PACKAGE_FIELDS, ctx)
            if ch:
                pkg_changes[_stable_key(b, "package")] = ch

        class_changes: Dict[str, List[Dict[str, str]]] = {}
        for a, b in m_cls["pairs"]:
            ch = self._diff_entity_fields(a, b, _CLASS_FIELDS, ctx)
            if ch:
                class_changes[_stable_key(b, "class")] = ch

        enum_changes: Dict[str, List[Dict[str, str]]] = {}
        for a, b in m_enum["pairs"]:
            ch = self._diff_entity_fields(a, b, _ENUM_FIELDS, ctx)
            if ch:
                enum_changes[_stable_key(b, "enum")] = ch

        attr_changes: Dict[str, List[Dict[str, str]]] = {}
        for a, b in m_attr["pairs"]:
            ch = self._diff_entity_fields(a, b, _ATTR_FIELDS, ctx)
            if ch:
                attr_changes[_stable_key(b, "attribute")] = ch

        assoc_changes: Dict[str, List[Dict[str, str]]] = {}
        for a, b in m_assoc["pairs"]:
            ch = self._diff_entity_fields(a, b, _ASSOC_FIELDS, ctx)
            if ch:
                assoc_changes[_stable_key(b, "association")] = ch

        gen_changes: Dict[str, List[Dict[str, str]]] = {}
        for a, b in m_gen["pairs"]:
            ch = self._diff_entity_fields(a, b, _GEN_FIELDS, ctx)
            if ch:
                gen_changes[_stable_key(b, "generalization")] = ch

        # Literals are diffed by name within each enum (using the matched pairs).
        lit_changes: Dict[str, Dict[str, List[str]]] = {}  # enum_stable_key -> {added, removed}

        def _names_for_enum(lits: Iterable[Any], enum: Any) -> Set[str]:
            eid = str(getattr(enum, "id", "") or "")
            return {
                str(getattr(lol, "name", "") or "").strip()
                for lol in lits
                if str(getattr(lol, "enumeratie_id", "") or "") == eid and getattr(lol, "name", None)
            }

        for a, b in m_enum["pairs"]:
            a_names = _names_for_enum(a_literals, a)
            b_names = _names_for_enum(b_literals, b)
            added = sorted(b_names - a_names)
            removed = sorted(a_names - b_names)
            if added or removed:
                lit_changes[_stable_key(b, "enum")] = {"added": added, "removed": removed}
        # Literals for newly added enumerations: everything counts as added.
        for e in m_enum["added"]:
            names = sorted(_names_for_enum(b_literals, e))
            if names:
                lit_changes[_stable_key(e, "enum")] = {"added": names, "removed": []}
        # Literals for removed enumerations: everything counts as removed.
        for e in m_enum["removed"]:
            names = sorted(_names_for_enum(a_literals, e))
            if names:
                lit_changes[_stable_key(e, "enum")] = {"added": [], "removed": names}

        # Split each field-level diff into structural and descriptive parts.
        pkg_s, pkg_d = _split_changes(pkg_changes)
        class_s, class_d = _split_changes(class_changes)
        enum_s, enum_d = _split_changes(enum_changes)
        attr_s, attr_d = _split_changes(attr_changes)
        assoc_s, assoc_d = _split_changes(assoc_changes)
        gen_s, gen_d = _split_changes(gen_changes)

        # Build buckets per category. Structural also carries added/removed and
        # literal diffs; descriptive only has field updates on common entities.
        struct_buckets = self._build_buckets(
            pkg_changes=pkg_s,
            class_changes=class_s,
            enum_changes=enum_s,
            attr_changes=attr_s,
            assoc_changes=assoc_s,
            gen_changes=gen_s,
            lit_changes=lit_changes,
            m_cls=m_cls,
            m_enum=m_enum,
            m_attr=m_attr,
            m_assoc=m_assoc,
            m_gen=m_gen,
            include_added_removed=True,
        )
        descr_buckets = self._build_buckets(
            pkg_changes=pkg_d,
            class_changes=class_d,
            enum_changes=enum_d,
            attr_changes=attr_d,
            assoc_changes=assoc_d,
            gen_changes=gen_d,
            lit_changes={},
            m_cls=m_cls,
            m_enum=m_enum,
            m_attr=m_attr,
            m_assoc=m_assoc,
            m_gen=m_gen,
            include_added_removed=False,
        )

        s_counts = self._count_section(struct_buckets)
        d_counts = self._count_section(descr_buckets)
        lit_added_total = sum(len(v.get("added", [])) for v in lit_changes.values())
        lit_removed_total = sum(len(v.get("removed", [])) for v in lit_changes.values())

        # ------------------------------------------------------------------
        # Compose Markdown.
        # ------------------------------------------------------------------
        lines: List[str] = []
        lines.append(f"# {title}")
        lines.append("")
        lines.append(
            "Entiteiten worden vergeleken op naam (gekwalificeerd met pakketpad), zodat een nieuwe "
            "`ea_guid` voor hetzelfde logische element niet als _Removed + Added_ verschijnt. "
            "Verwijzingen naar andere entiteiten (FK-velden zoals `enumeration_id`) worden vergeleken "
            "op de naam van het doel — niet op de interne sleutel."
        )
        lines.append("")
        lines.append(
            "**Structurele wijzigingen** raken het model zelf: toegevoegde of verwijderde elementen, "
            "naamswijzigingen, type/verplicht/multipliciteit/lengte/patroon en links tussen elementen. "
            "**Beschrijvende wijzigingen** updaten alleen metadata of documentatie (definitie, "
            "toelichting, gemma-tags, versie, auteur, herkomst, …) zonder de structuur van het model "
            "te veranderen."
        )
        lines.append("")

        # Summary table — both categories side by side.
        lines.append("## Samenvatting")
        lines.append("")
        lines.append("| Element | + (struct.) | − (struct.) | ~ (struct.) | ~ (beschr.) |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for key, label in [
            ("classes", "Classes"),
            ("datatypes", "Datatypes"),
            ("enums", "Enumeraties"),
            ("attrs", "Attributen"),
            ("assocs", "Associaties"),
            ("gens", "Generalisaties"),
        ]:
            sa = s_counts[key]["added"]
            sr = s_counts[key]["removed"]
            sc = s_counts[key]["changed"]
            dc = d_counts[key]["changed"]
            lines.append(f"| {label} | {sa} | {sr} | {sc} | {dc} |")
        lines.append(f"| Enum-literals | {lit_added_total} | {lit_removed_total} | — | — |")
        # Packages alleen op metadata vergeleken — toon onder de tabel.
        s_pkg_changed = len(pkg_s)
        d_pkg_changed = len(pkg_d)
        lines.append(f"| Pakketten (metadata) | 0 | 0 | {s_pkg_changed} | {d_pkg_changed} |")
        lines.append("")

        # TOC.
        s_paths = sorted(p for p in struct_buckets if p)
        d_paths = sorted(p for p in descr_buckets if p)
        all_paths = sorted(set(s_paths) | set(d_paths))
        if all_paths:
            lines.append("## Geraakte packages")
            lines.append("")
            for path in all_paths:
                markers = []
                if path in struct_buckets:
                    markers.append(f"[structureel](#structureel-{_md_anchor(path)})")
                if path in descr_buckets:
                    markers.append(f"[beschrijvend](#beschrijvend-{_md_anchor(path)})")
                lines.append(f"- **{path}** — {' · '.join(markers)}")
            lines.append("")

        # Structural section.
        lines.append("## Structurele wijzigingen")
        lines.append("")
        if not s_paths:
            lines.append("_Geen structurele wijzigingen._")
            lines.append("")
        else:
            for path in s_paths:
                self._render_package(
                    lines,
                    path,
                    bucket=struct_buckets[path],
                    pkg_changes=pkg_s,
                    class_changes=class_s,
                    enum_changes=enum_s,
                    attr_changes=attr_s,
                    assoc_changes=assoc_s,
                    gen_changes=gen_s,
                    lit_changes=lit_changes,
                    anchor_prefix="structureel",
                )

        # Descriptive section.
        lines.append("## Beschrijvende wijzigingen")
        lines.append("")
        if not d_paths:
            lines.append("_Geen beschrijvende wijzigingen._")
            lines.append("")
        else:
            for path in d_paths:
                self._render_package(
                    lines,
                    path,
                    bucket=descr_buckets[path],
                    pkg_changes=pkg_d,
                    class_changes=class_d,
                    enum_changes=enum_d,
                    attr_changes=attr_d,
                    assoc_changes=assoc_d,
                    gen_changes=gen_d,
                    lit_changes={},
                    anchor_prefix="beschrijvend",
                )

        with open(args.outputfile, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip() + "\n")

    # ------------------------------------------------------------------
    # Bucket building / summary / per-package rendering
    # ------------------------------------------------------------------

    def _build_buckets(
        self,
        *,
        pkg_changes: Dict[str, List[Dict[str, str]]],
        class_changes: Dict[str, List[Dict[str, str]]],
        enum_changes: Dict[str, List[Dict[str, str]]],
        attr_changes: Dict[str, List[Dict[str, str]]],
        assoc_changes: Dict[str, List[Dict[str, str]]],
        gen_changes: Dict[str, List[Dict[str, str]]],
        lit_changes: Dict[str, Dict[str, List[str]]],
        m_cls: Dict[str, Any],
        m_enum: Dict[str, Any],
        m_attr: Dict[str, Any],
        m_assoc: Dict[str, Any],
        m_gen: Dict[str, Any],
        include_added_removed: bool,
    ) -> Dict[str, Dict[str, Any]]:
        buckets: Dict[str, Dict[str, Any]] = {}

        def _bucket(path: str) -> Dict[str, Any]:
            return buckets.setdefault(
                path,
                {
                    "classes_changed": [],
                    "classes_added": [],
                    "classes_removed": [],
                    "datatypes_changed": [],
                    "datatypes_added": [],
                    "datatypes_removed": [],
                    "enums_changed": [],
                    "enums_added": [],
                    "enums_removed": [],
                    "attrs_changed": [],
                    "attrs_added": [],
                    "attrs_removed": [],
                    "assocs_changed": [],
                    "assocs_added": [],
                    "assocs_removed": [],
                    "gens_changed": [],
                    "gens_added": [],
                    "gens_removed": [],
                    "pkg_changes_key": None,
                },
            )

        def _path(obj: Any, getter) -> str:
            return _qualified_pkg_path(getter(obj)) if obj is not None else ""

        def _push_class(obj: Any, bucket_field: str):
            b = _bucket(_path(obj, self._pkg_of_class))
            prefix = "datatypes" if bool(getattr(obj, "is_datatype", False)) else "classes"
            b[f"{prefix}_{bucket_field}"].append(obj)

        for key in pkg_changes:
            _bucket(key)["pkg_changes_key"] = key

        if include_added_removed:
            for c in m_cls["added"]:
                _push_class(c, "added")
            for c in m_cls["removed"]:
                _push_class(c, "removed")
            for e in m_enum["added"]:
                _bucket(_path(e, self._pkg_of_enum))["enums_added"].append(e)
            for e in m_enum["removed"]:
                _bucket(_path(e, self._pkg_of_enum))["enums_removed"].append(e)
            for a in m_attr["added"]:
                _bucket(_path(a, self._pkg_of_attr))["attrs_added"].append(a)
            for a in m_attr["removed"]:
                _bucket(_path(a, self._pkg_of_attr))["attrs_removed"].append(a)
            for assoc in m_assoc["added"]:
                _bucket(_path(assoc, self._pkg_of_assoc))["assocs_added"].append(assoc)
            for assoc in m_assoc["removed"]:
                _bucket(_path(assoc, self._pkg_of_assoc))["assocs_removed"].append(assoc)
            for g in m_gen["added"]:
                _bucket(_path(g, self._pkg_of_gen))["gens_added"].append(g)
            for g in m_gen["removed"]:
                _bucket(_path(g, self._pkg_of_gen))["gens_removed"].append(g)

        for _, b in m_cls["pairs"]:
            if _stable_key(b, "class") in class_changes:
                _push_class(b, "changed")
        for _, b in m_enum["pairs"]:
            key = _stable_key(b, "enum")
            if key in enum_changes or key in lit_changes:
                _bucket(_path(b, self._pkg_of_enum))["enums_changed"].append(b)
        for _, b in m_attr["pairs"]:
            if _stable_key(b, "attribute") in attr_changes:
                _bucket(_path(b, self._pkg_of_attr))["attrs_changed"].append(b)
        for _, b in m_assoc["pairs"]:
            if _stable_key(b, "association") in assoc_changes:
                _bucket(_path(b, self._pkg_of_assoc))["assocs_changed"].append(b)
        for _, b in m_gen["pairs"]:
            if _stable_key(b, "generalization") in gen_changes:
                _bucket(_path(b, self._pkg_of_gen))["gens_changed"].append(b)

        return buckets

    def _count_section(self, buckets: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for kind in ("classes", "datatypes", "enums", "attrs", "assocs", "gens"):
            added = removed = changed = 0
            for b in buckets.values():
                added += len(b.get(f"{kind}_added", []))
                removed += len(b.get(f"{kind}_removed", []))
                changed += len(b.get(f"{kind}_changed", []))
            out[kind] = {"added": added, "removed": removed, "changed": changed}
        return out

    def _render_package(
        self,
        lines: List[str],
        path: str,
        *,
        bucket: Dict[str, Any],
        pkg_changes: Dict[str, List[Dict[str, str]]],
        class_changes: Dict[str, List[Dict[str, str]]],
        enum_changes: Dict[str, List[Dict[str, str]]],
        attr_changes: Dict[str, List[Dict[str, str]]],
        assoc_changes: Dict[str, List[Dict[str, str]]],
        gen_changes: Dict[str, List[Dict[str, str]]],
        lit_changes: Dict[str, Dict[str, List[str]]],
        anchor_prefix: str,
    ) -> None:
        # Use an explicit anchor so the same package can appear in both the
        # structural and descriptive section without colliding heading slugs.
        anchor = f"{anchor_prefix}-{_md_anchor(path)}"
        lines.append(f'<a id="{anchor}"></a>')
        lines.append(f"### Package: {_md_escape(path)}")
        lines.append("")

        pkey = bucket.get("pkg_changes_key")
        if pkey and pkg_changes.get(pkey):
            lines.append("**Pakket-metadata gewijzigd:**")
            lines.append("")
            lines.extend(self._render_field_changes(pkg_changes[pkey], indent=0))
            lines.append("")

        self._render_class_group(
            lines,
            heading="Classes",
            added=bucket["classes_added"],
            removed=bucket["classes_removed"],
            changed=bucket["classes_changed"],
            field_changes_by_key=class_changes,
            attrs_added=bucket["attrs_added"],
            attrs_removed=bucket["attrs_removed"],
            attrs_changed=bucket["attrs_changed"],
            attr_changes_by_key=attr_changes,
            stable_key_kind="class",
        )
        self._render_class_group(
            lines,
            heading="Datatypes",
            added=bucket["datatypes_added"],
            removed=bucket["datatypes_removed"],
            changed=bucket["datatypes_changed"],
            field_changes_by_key=class_changes,
            attrs_added=bucket["attrs_added"],
            attrs_removed=bucket["attrs_removed"],
            attrs_changed=bucket["attrs_changed"],
            attr_changes_by_key=attr_changes,
            stable_key_kind="class",
        )
        self._render_enum_group(
            lines,
            added=bucket["enums_added"],
            removed=bucket["enums_removed"],
            changed=bucket["enums_changed"],
            field_changes_by_key=enum_changes,
            lit_changes_by_key=lit_changes,
        )
        self._render_relation_group(
            lines,
            heading="Associaties",
            added=bucket["assocs_added"],
            removed=bucket["assocs_removed"],
            changed=bucket["assocs_changed"],
            field_changes_by_key=assoc_changes,
            stable_key_kind="association",
            title_fn=self._assoc_title,
        )
        self._render_relation_group(
            lines,
            heading="Generalisaties",
            added=bucket["gens_added"],
            removed=bucket["gens_removed"],
            changed=bucket["gens_changed"],
            field_changes_by_key=gen_changes,
            stable_key_kind="generalization",
            title_fn=self._gen_title,
        )

    # ------------------------------------------------------------------
    # Section renderers
    # ------------------------------------------------------------------

    def _attrs_for_class(
        self,
        cls: Any,
        attrs: List[Any],
    ) -> List[Any]:
        cid = str(getattr(cls, "id", "") or "")
        cls_key = _stable_key(cls, "class")
        out = []
        for a in attrs:
            # Match either by direct id link or by qualified class key (in case
            # the same logical class has a different ea_guid between sides).
            if str(getattr(a, "clazz_id", "") or "") == cid:
                out.append(a)
                continue
            parent_cls = getattr(a, "clazz", None)
            if parent_cls is not None and _stable_key(parent_cls, "class") == cls_key:
                out.append(a)
        return out

    def _render_class_group(
        self,
        lines: List[str],
        heading: str,
        added: List[Any],
        removed: List[Any],
        changed: List[Any],
        field_changes_by_key: Dict[str, List[Dict[str, str]]],
        attrs_added: List[Any],
        attrs_removed: List[Any],
        attrs_changed: List[Any],
        attr_changes_by_key: Dict[str, List[Dict[str, str]]],
        stable_key_kind: str,
    ) -> None:
        attrs_added_orphans: List[Any] = []
        attrs_removed_orphans: List[Any] = []
        attrs_changed_orphans: List[Any] = []

        # Build a quick lookup: which classes are themselves in this section?
        in_section_keys = {_stable_key(c, stable_key_kind) for c in added + removed + changed}

        # Attributes whose parent class is not in the section (because the
        # class itself didn't change). Group them under their parent below.
        attrs_added_keyed: Dict[str, List[Any]] = {}
        attrs_removed_keyed: Dict[str, List[Any]] = {}
        attrs_changed_keyed: Dict[str, List[Any]] = {}

        def _parent_key(a: Any) -> str:
            return _stable_key(getattr(a, "clazz", None), stable_key_kind)

        for a in attrs_added:
            k = _parent_key(a)
            if k in in_section_keys:
                attrs_added_keyed.setdefault(k, []).append(a)
            else:
                attrs_added_orphans.append(a)
        for a in attrs_removed:
            k = _parent_key(a)
            if k in in_section_keys:
                attrs_removed_keyed.setdefault(k, []).append(a)
            else:
                attrs_removed_orphans.append(a)
        for a in attrs_changed:
            k = _parent_key(a)
            if k in in_section_keys:
                attrs_changed_keyed.setdefault(k, []).append(a)
            else:
                attrs_changed_orphans.append(a)

        # Build a set of class keys that have orphan attribute changes — these
        # need a stub class entry too so the attributes are reported.
        orphan_class_keys: Dict[str, Any] = {}
        for a in attrs_added_orphans + attrs_removed_orphans + attrs_changed_orphans:
            cls = getattr(a, "clazz", None)
            if cls is None:
                continue
            k = _stable_key(cls, stable_key_kind)
            # We can only place datatypes vs classes correctly using the
            # caller's heading — orphans of the *other* kind will silently be
            # filtered out by the caller (they end up in the matching group).
            if heading == "Datatypes" and not bool(getattr(cls, "is_datatype", False)):
                continue
            if heading == "Classes" and bool(getattr(cls, "is_datatype", False)):
                continue
            orphan_class_keys.setdefault(k, cls)

        has_section_content = bool(added or removed or changed or orphan_class_keys)
        if not has_section_content:
            return

        lines.append(f"#### {heading}")
        lines.append("")

        def _emit_class(cls: Any, status: str):
            name = _md_escape(getattr(cls, "name", "(no name)"))
            key = _stable_key(cls, stable_key_kind)
            badge = {"Added": "🟢 Toegevoegd", "Removed": "🔴 Verwijderd", "Changed": "🟡 Gewijzigd"}.get(
                status, status
            )
            lines.append(f"##### `{name}` — {badge}")
            lines.append("")
            field_changes = field_changes_by_key.get(key)
            if status == "Changed" and field_changes:
                lines.extend(self._render_field_changes(field_changes, indent=0))
                lines.append("")
            self._emit_attrs_for_class(
                lines,
                cls,
                attrs_added_keyed.get(key, []),
                attrs_removed_keyed.get(key, []),
                attrs_changed_keyed.get(key, []),
                attr_changes_by_key,
            )

        for cls in sorted(added, key=lambda c: (getattr(c, "name", "") or "").lower()):
            _emit_class(cls, "Added")
        for cls in sorted(removed, key=lambda c: (getattr(c, "name", "") or "").lower()):
            _emit_class(cls, "Removed")
        for cls in sorted(changed, key=lambda c: (getattr(c, "name", "") or "").lower()):
            _emit_class(cls, "Changed")

        # Orphan parents: the class itself didn't change, but attributes did.
        already_emitted = {_stable_key(c, stable_key_kind) for c in added + removed + changed}
        for k, cls in sorted(orphan_class_keys.items()):
            if k in already_emitted:
                continue
            name = _md_escape(getattr(cls, "name", "(no name)"))
            lines.append(f"##### `{name}` — 🟡 Attributen gewijzigd")
            lines.append("")
            self._emit_attrs_for_class(
                lines,
                cls,
                [a for a in attrs_added_orphans if _stable_key(getattr(a, "clazz", None), stable_key_kind) == k],
                [a for a in attrs_removed_orphans if _stable_key(getattr(a, "clazz", None), stable_key_kind) == k],
                [a for a in attrs_changed_orphans if _stable_key(getattr(a, "clazz", None), stable_key_kind) == k],
                attr_changes_by_key,
            )

    def _emit_attrs_for_class(
        self,
        lines: List[str],
        cls: Any,
        attrs_added: List[Any],
        attrs_removed: List[Any],
        attrs_changed: List[Any],
        attr_changes_by_key: Dict[str, List[Dict[str, str]]],
    ) -> None:
        def _named(a):
            n = getattr(a, "name", None)
            return n is not None and str(n).strip() != ""

        attrs_added = [a for a in attrs_added if _named(a)]
        attrs_removed = [a for a in attrs_removed if _named(a)]
        attrs_changed = [a for a in attrs_changed if _named(a)]
        if not (attrs_added or attrs_removed or attrs_changed):
            return

        lines.append("**Attributen:**")
        lines.append("")
        for a in sorted(attrs_added, key=lambda x: (getattr(x, "name", "") or "").lower()):
            lines.append(f"- 🟢 `{_md_escape(getattr(a, 'name', ''))}` — Toegevoegd")
        for a in sorted(attrs_removed, key=lambda x: (getattr(x, "name", "") or "").lower()):
            lines.append(f"- 🔴 `{_md_escape(getattr(a, 'name', ''))}` — Verwijderd")
        for a in sorted(attrs_changed, key=lambda x: (getattr(x, "name", "") or "").lower()):
            name = _md_escape(getattr(a, "name", ""))
            lines.append(f"- 🟡 `{name}` — Gewijzigd")
            ch = attr_changes_by_key.get(_stable_key(a, "attribute"))
            if ch:
                lines.extend(self._render_field_changes(ch, indent=4))
        lines.append("")

    def _render_enum_group(
        self,
        lines: List[str],
        added: List[Any],
        removed: List[Any],
        changed: List[Any],
        field_changes_by_key: Dict[str, List[Dict[str, str]]],
        lit_changes_by_key: Dict[str, Dict[str, List[str]]],
    ) -> None:
        if not (added or removed or changed):
            return
        lines.append("#### Enumeraties")
        lines.append("")

        def _emit(e: Any, status: str):
            name = _md_escape(getattr(e, "name", "(no name)"))
            key = _stable_key(e, "enum")
            badge = {"Added": "🟢 Toegevoegd", "Removed": "🔴 Verwijderd", "Changed": "🟡 Gewijzigd"}.get(
                status, status
            )
            lines.append(f"##### `{name}` — {badge}")
            lines.append("")
            field_changes = field_changes_by_key.get(key)
            if status == "Changed" and field_changes:
                lines.extend(self._render_field_changes(field_changes, indent=0))
                lines.append("")
            lc = lit_changes_by_key.get(key)
            if lc:
                lines.append("**Literals:**")
                lines.append("")
                for n in lc.get("added", []):
                    lines.append(f"- 🟢 `{_md_escape(n)}` — Toegevoegd")
                for n in lc.get("removed", []):
                    lines.append(f"- 🔴 `{_md_escape(n)}` — Verwijderd")
                lines.append("")

        for e in sorted(added, key=lambda x: (getattr(x, "name", "") or "").lower()):
            _emit(e, "Added")
        for e in sorted(removed, key=lambda x: (getattr(x, "name", "") or "").lower()):
            _emit(e, "Removed")
        for e in sorted(changed, key=lambda x: (getattr(x, "name", "") or "").lower()):
            _emit(e, "Changed")

    def _assoc_title(self, a: Any) -> str:
        src = getattr(getattr(a, "src_class", None), "name", "?") or "?"
        dst = getattr(getattr(a, "dst_class", None), "name", "?") or "?"
        nm = (getattr(a, "name", "") or "").strip()
        label = f" «{nm}»" if nm else ""
        return f"`{src}`{label} → `{dst}`"

    def _gen_title(self, g: Any) -> str:
        sub = getattr(getattr(g, "subclass", None), "name", "?") or "?"
        sup = getattr(getattr(g, "superclass", None), "name", "?") or "?"
        return f"`{sub}` ⟶ `{sup}`"

    def _render_relation_group(
        self,
        lines: List[str],
        heading: str,
        added: List[Any],
        removed: List[Any],
        changed: List[Any],
        field_changes_by_key: Dict[str, List[Dict[str, str]]],
        stable_key_kind: str,
        title_fn,
    ) -> None:
        if not (added or removed or changed):
            return
        lines.append(f"#### {heading}")
        lines.append("")

        def _emit(item: Any, status: str):
            badge = {"Added": "🟢 Toegevoegd", "Removed": "🔴 Verwijderd", "Changed": "🟡 Gewijzigd"}.get(
                status, status
            )
            lines.append(f"- {badge}: {title_fn(item)}")
            if status == "Changed":
                ch = field_changes_by_key.get(_stable_key(item, stable_key_kind))
                if ch:
                    lines.extend(self._render_field_changes(ch, indent=2))

        for it in sorted(added, key=lambda x: title_fn(x).lower()):
            _emit(it, "Added")
        for it in sorted(removed, key=lambda x: title_fn(x).lower()):
            _emit(it, "Removed")
        for it in sorted(changed, key=lambda x: title_fn(x).lower()):
            _emit(it, "Changed")
        lines.append("")
