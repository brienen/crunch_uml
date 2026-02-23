import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

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

    def translate_data(self, data, to_language, from_language="auto", update_i18n=True, original_i18n={}):
        logger.info(
            f"Starting Translating data to language '{to_language}'. This may take a while:"
            f" {util.count_dict_elements(data)} entries..."
        )
        translated_data = {}
        for section, entries in data.items():
            logger.info(f"Translating section {section}...")
            translated_data[section] = []
            original_i18n_section = original_i18n.get(to_language, {}).get(section, [])
            for entry in entries:
                translated_record = {}
                for key, record in entry.items():
                    original_record = [record for record in original_i18n_section if key in record]
                    original_record = original_record[0] if len(original_record) > 0 else {}
                    original_record = original_record.get(key, {})
                    for field, value in record.items():
                        if not isinstance(value, str):
                            next
                        if not (util.is_empty_or_none(value)):
                            if update_i18n:
                                # Check if the field is already translated
                                translated_value = original_record.get(field, None)
                                if translated_value is None:
                                    # Translate the value
                                    translated_value = lang.translate(
                                        value,
                                        to_language=to_language,
                                        from_language=from_language,
                                        max_retries=1,
                                    )
                                translated_record[field] = translated_value
                            else:
                                translated_record[field] = lang.translate(  #
                                    value,
                                    to_language=to_language,
                                    from_language=from_language,
                                    max_retries=1,
                                )
                translated_data[section].append({key: translated_record})

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
                all_data, args.language, from_language=args.from_language, update_i18n=True, original_i18n=i18n_data
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


def _norm(v: Any) -> Any:
    if v is None:
        return ""
    return v


def _safe_get(obj: Any, field: str) -> Any:
    return getattr(obj, field) if obj is not None and hasattr(obj, field) else None


def _diff_fields(
    a: Any,
    b: Any,
    fields: Iterable[str],
    labels: Optional[Dict[str, str]] = None,
    formatters: Optional[Dict[str, Any]] = None,
) -> List[str]:
    out: List[str] = []
    for f in fields:
        av = _norm(_safe_get(a, f))
        bv = _norm(_safe_get(b, f))
        if av != bv:
            label = labels.get(f, f) if labels else f
            if formatters and f in formatters:
                out.append(formatters[f](label, av, bv))
            else:
                out.append(f"- **{label}**: `{av}` → `{bv}`")
    return out


def _md_list(items: List[str], indent: int = 0) -> str:
    if not items:
        return ""
    pad = " " * indent
    return "\n".join(pad + it for it in items)


def _md_escape(s: str) -> str:
    return str(s).replace("\n", " ").strip()


@RendererRegistry.register(
    "diff_md",
    descr="Top-down Markdown diff between two schema versions (Package → Class/Datatype/Enum → Attribute/Literal).",
)
class SchemaDiffMarkdownRenderer(Renderer):
    def _get_other_schema(self, schema: sch.Schema, args) -> sch.Schema:
        other_name = getattr(args, "compare_schema_name", None)
        if not other_name:
            raise ValueError("diff_md requires --compare_schema_name <schema_id/schema_name>.")
        return sch.Schema(schema.database, schema_name=other_name)

    def _index_by_id(self, items: Iterable[Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for it in items:
            if getattr(it, "id", None) is not None:
                out[str(it.id)] = it
        return out

    def render(self, args, schema: sch.Schema):
        other = self._get_other_schema(schema, args)
        title = getattr(args, "compare_title", None) or f"Diff: {schema.schema_id} → {other.schema_id}"

        # Load entities
        a_pkgs = schema.get_all_packages()
        b_pkgs = other.get_all_packages()
        a_classes = schema.get_all_classes() + schema.get_all_datatypes()
        b_classes = other.get_all_classes() + other.get_all_datatypes()
        a_enums = schema.get_all_enumerations()
        b_enums = other.get_all_enumerations()
        a_attrs = schema.get_all_attributes()
        b_attrs = other.get_all_attributes()
        a_literals = schema.get_all_literals()
        b_literals = other.get_all_literals()

        A_pkg = self._index_by_id(a_pkgs)
        B_pkg = self._index_by_id(b_pkgs)
        A_cls = self._index_by_id(a_classes)
        B_cls = self._index_by_id(b_classes)
        A_enum = self._index_by_id(a_enums)
        B_enum = self._index_by_id(b_enums)
        A_attr = self._index_by_id(a_attrs)
        B_attr = self._index_by_id(b_attrs)

        # Human-readable ID lookups
        enum_name_by_id: Dict[str, str] = {}
        for _eid, _e in {**A_enum, **B_enum}.items():
            enum_name_by_id[_eid] = str(getattr(_e, "name", _eid))

        class_name_by_id: Dict[str, str] = {}
        for _cid, _c in {**A_cls, **B_cls}.items():
            class_name_by_id[_cid] = str(getattr(_c, "name", _cid))

        def _fmt_enum(label: str, old: Any, new: Any) -> str:
            o = str(old) if old not in (None, "") else ""
            n = str(new) if new not in (None, "") else ""
            o_txt = f"Enumeratie: {enum_name_by_id.get(o, o)}" if o else ""
            n_txt = f"Enumeratie: {enum_name_by_id.get(n, n)}" if n else ""
            return f"- **{label}**: `{o_txt}` → `{n_txt}`"

        def _fmt_class(label: str, old: Any, new: Any) -> str:
            o = str(old) if old not in (None, "") else ""
            n = str(new) if new not in (None, "") else ""
            o_txt = f"Objecttype: {class_name_by_id.get(o, o)}" if o else ""
            n_txt = f"Objecttype: {class_name_by_id.get(n, n)}" if n else ""
            return f"- **{label}**: `{o_txt}` → `{n_txt}`"

        attr_formatters: Dict[str, Any] = {
            "enumeration_id": _fmt_enum,
            "type_class_id": _fmt_class,
        }

        # Sets
        cls_added = sorted(set(B_cls) - set(A_cls))
        cls_removed = sorted(set(A_cls) - set(B_cls))
        cls_common = sorted(set(A_cls) & set(B_cls))

        enum_added = sorted(set(B_enum) - set(A_enum))
        enum_removed = sorted(set(A_enum) - set(B_enum))
        enum_common = sorted(set(A_enum) & set(B_enum))

        attr_added = sorted(set(B_attr) - set(A_attr))
        attr_removed = sorted(set(A_attr) - set(B_attr))
        attr_common = sorted(set(A_attr) & set(B_attr))

        # Field-level diffs
        labels = {"notes": "notes/toelichting", "definition": "definition/definitie"}
        class_fields = ["name", "stereotype", "alias", "uri", "notes", "definition", "package_id"]
        enum_fields = ["name", "stereotype", "alias", "uri", "notes", "definition", "package_id"]
        attr_fields = [
            "name",
            "stereotype",
            "alias",
            "uri",
            "notes",
            "definition",
            "clazz_id",
            "primitive",
            "enumeration_id",
            "type_class_id",
            "verplicht",
        ]

        class_changes: List[_DiffItem] = []
        enum_changes: List[_DiffItem] = []
        attr_changes: List[_DiffItem] = []

        for cid in cls_common:
            field_changes = _diff_fields(A_cls[cid], B_cls[cid], class_fields, labels=labels)
            if field_changes:
                class_changes.append(
                    _DiffItem(
                        key=cid,
                        title=str(_safe_get(B_cls[cid], "name") or cid),
                        changes=field_changes,
                    )
                )

        for eid in enum_common:
            field_changes = _diff_fields(A_enum[eid], B_enum[eid], enum_fields, labels=labels)
            if field_changes:
                enum_changes.append(
                    _DiffItem(
                        key=eid,
                        title=str(_safe_get(B_enum[eid], "name") or eid),
                        changes=field_changes,
                    )
                )

        for aid in attr_common:
            field_changes = _diff_fields(
                A_attr[aid],
                B_attr[aid],
                attr_fields,
                labels=labels,
                formatters=attr_formatters,
            )
            if field_changes:
                nm = str(_safe_get(B_attr[aid], "name") or aid)
                clsid = str(_safe_get(B_attr[aid], "clazz_id") or "")
                attr_changes.append(
                    _DiffItem(
                        key=aid,
                        title=f"{nm} (class={clsid})",
                        changes=field_changes,
                    )
                )

        changed_class_ids: Set[str] = {d.key for d in class_changes}
        changed_enum_ids: Set[str] = {d.key for d in enum_changes}
        changed_attr_ids: Set[str] = {d.key for d in attr_changes}

        # Fast lookups (and avoids mypy issues with next(..., None))
        class_changes_by_id: Dict[str, _DiffItem] = {d.key: d for d in class_changes}
        enum_changes_by_id: Dict[str, _DiffItem] = {d.key: d for d in enum_changes}
        attr_changes_by_id: Dict[str, _DiffItem] = {d.key: d for d in attr_changes}

        # Literals diff per enum
        lit_changes: Dict[str, Dict[str, List[str]]] = {}
        for eid in set(A_enum) | set(B_enum):
            a_lits = [lol for lol in a_literals if str(getattr(lol, "enumeratie_id", "")) == str(eid)]
            b_lits = [lol for lol in b_literals if str(getattr(lol, "enumeratie_id", "")) == str(eid)]
            a_names = {str(getattr(lol, "name", "")) for lol in a_lits if getattr(lol, "name", None)}
            b_names = {str(getattr(lol, "name", "")) for lol in b_lits if getattr(lol, "name", None)}
            added = sorted(b_names - a_names)
            removed = sorted(a_names - b_names)
            if added or removed:
                lit_changes[str(eid)] = {"added": added, "removed": removed}

        changed_enum_ids |= set(lit_changes.keys())

        # Helpers
        def pkg_name(pid: str) -> str:
            p = B_pkg.get(pid) or A_pkg.get(pid)
            return str(getattr(p, "name", pid))

        def cls_pkg_id(cid: str) -> str:
            c = B_cls.get(cid) or A_cls.get(cid)
            return str(getattr(c, "package_id", "") or "")

        def enum_pkg_id(eid: str) -> str:
            e = B_enum.get(eid) or A_enum.get(eid)
            return str(getattr(e, "package_id", "") or "")

        def is_datatype(cid: str) -> bool:
            c = B_cls.get(cid) or A_cls.get(cid)
            return isinstance(c, db.Datatype)

        # Markdown
        lines: List[str] = []
        lines.append(f"# {title}\n")

        lit_added_total = sum(len(v.get("added", [])) for v in lit_changes.values())
        lit_removed_total = sum(len(v.get("removed", [])) for v in lit_changes.values())

        cls_added_dt = [cid for cid in cls_added if is_datatype(cid)]
        cls_added_cl = [cid for cid in cls_added if not is_datatype(cid)]
        cls_removed_dt = [cid for cid in cls_removed if is_datatype(cid)]
        cls_removed_cl = [cid for cid in cls_removed if not is_datatype(cid)]
        cls_changed_dt = [cid for cid in changed_class_ids if is_datatype(cid)]
        cls_changed_cl = [cid for cid in changed_class_ids if not is_datatype(cid)]

        lines.append("## Summary\n")
        lines.append(
            "\n".join(
                [
                    f"- **Classes**: +{len(cls_added_cl)} / -{len(cls_removed_cl)} / ~{len(cls_changed_cl)}",
                    f"- **Datatypes**: +{len(cls_added_dt)} / -{len(cls_removed_dt)} / ~{len(cls_changed_dt)}",
                    f"- **Enumerations**: +{len(enum_added)} / -{len(enum_removed)} / ~{len(changed_enum_ids)}",
                    f"- **Attributes**: +{len(attr_added)} / -{len(attr_removed)} / ~{len(changed_attr_ids)}",
                    f"- **Literals**: +{lit_added_total} / -{lit_removed_total}",
                ]
            )
        )
        lines.append("")

        # Overview
        touched: Set[str] = set()
        for cid in set(cls_added) | set(cls_removed) | changed_class_ids:
            pid = cls_pkg_id(cid)
            if pid:
                touched.add(pid)
        for eid in set(enum_added) | set(enum_removed) | changed_enum_ids:
            pid = enum_pkg_id(eid)
            if pid:
                touched.add(pid)
        for aid in set(attr_added) | set(attr_removed) | changed_attr_ids:
            a = B_attr.get(aid) or A_attr.get(aid)
            parent = str(getattr(a, "clazz_id", "") or "")
            pid = cls_pkg_id(parent) if parent else ""
            if pid:
                touched.add(pid)

        lines.append("## Overview\n")
        lines.append(
            "**Packages touched:** "
            + ", ".join(f"`{_md_escape(pkg_name(pid))}`" for pid in sorted(touched, key=pkg_name))
        )
        lines.append("\n")

        # Top-down
        lines.append("## Top-down changes\n")

        def status(i: str, added: Set[str], removed: Set[str], changed: Set[str]) -> str:
            if i in added:
                return "Added"
            if i in removed:
                return "Removed"
            if i in changed:
                return "Changed"
            return "Unchanged"

        set_cls_added, set_cls_removed = set(cls_added), set(cls_removed)
        set_enum_added, set_enum_removed = set(enum_added), set(enum_removed)
        set_attr_added, set_attr_removed = set(attr_added), set(attr_removed)

        pkg_classes: Dict[str, Set[str]] = {}
        pkg_enums: Dict[str, Set[str]] = {}

        def bucket_class(cid: str):
            pid = cls_pkg_id(cid)
            if pid:
                pkg_classes.setdefault(pid, set()).add(cid)

        def bucket_enum(eid: str):
            pid = enum_pkg_id(eid)
            if pid:
                pkg_enums.setdefault(pid, set()).add(eid)

        for cid in set_cls_added | set_cls_removed | changed_class_ids:
            bucket_class(cid)
        for eid in set_enum_added | set_enum_removed | changed_enum_ids:
            bucket_enum(eid)

        attrs_by_class: Dict[str, Set[str]] = {}
        for aid in set_attr_added | set_attr_removed | changed_attr_ids:
            a = B_attr.get(aid) or A_attr.get(aid)
            parent = str(getattr(a, "clazz_id", "") or "")
            if parent:
                attrs_by_class.setdefault(parent, set()).add(aid)
                bucket_class(parent)

        def sort_by_name(ids: Iterable[str], lookup: Dict[str, Any]) -> List[str]:
            return sorted(ids, key=lambda x: _md_escape(str(_safe_get(lookup.get(x), "name") or x)))

        for pid in sorted(set(pkg_classes) | set(pkg_enums), key=pkg_name):
            lines.append(f"## Package: {_md_escape(pkg_name(pid))}\n")

            all_cls_ids = pkg_classes.get(pid, set())
            class_ids = sort_by_name([cid for cid in all_cls_ids if not is_datatype(cid)], {**A_cls, **B_cls})
            dtype_ids = sort_by_name([cid for cid in all_cls_ids if is_datatype(cid)], {**A_cls, **B_cls})

            if class_ids:
                lines.append("### Classes\n")
                for cid in class_ids:
                    c = B_cls.get(cid) or A_cls.get(cid)
                    cname = _md_escape(getattr(c, "name", "(no name)"))
                    lines.append(
                        f"#### {cname} — **{status(cid, set_cls_added, set_cls_removed, changed_class_ids)}**\n"
                    )
                    class_diff = class_changes_by_id.get(cid)
                    if class_diff:
                        lines.append(_md_list(class_diff.changes) + "\n")
                    a_ids = sort_by_name(attrs_by_class.get(cid, set()), {**A_attr, **B_attr})
                    if a_ids:
                        lines.append("##### Attributes\n")
                        for aid in a_ids:
                            aobj = B_attr.get(aid) or A_attr.get(aid)
                            raw_name = getattr(aobj, "name", None) if aobj is not None else None
                            if raw_name is None or str(raw_name).strip() == "":
                                # Skip unnamed/None attributes (these are usually incomplete rows)
                                continue
                            an = _md_escape(str(raw_name))
                            lines.append(
                                f"- {an} — **{status(aid, set_attr_added, set_attr_removed, changed_attr_ids)}**"
                            )
                            ach = attr_changes_by_id.get(aid)
                            if ach:
                                lines.append(_md_list(ach.changes, indent=2))
                        lines.append("")
            else:
                lines.append("_No class changes in this package._\n")

            if dtype_ids:
                lines.append("### Datatypes\n")
                for cid in dtype_ids:
                    c = B_cls.get(cid) or A_cls.get(cid)
                    cname = _md_escape(getattr(c, "name", "(no name)"))
                    lines.append(
                        f"#### {cname} — **{status(cid, set_cls_added, set_cls_removed, changed_class_ids)}**\n"
                    )
                    class_diff = class_changes_by_id.get(cid)
                    if class_diff:
                        lines.append(_md_list(class_diff.changes) + "\n")
                    a_ids = sort_by_name(attrs_by_class.get(cid, set()), {**A_attr, **B_attr})
                    if a_ids:
                        lines.append("##### Attributes\n")
                        for aid in a_ids:
                            aobj = B_attr.get(aid) or A_attr.get(aid)
                            raw_name = getattr(aobj, "name", None) if aobj is not None else None
                            if raw_name is None or str(raw_name).strip() == "":
                                # Skip unnamed/None attributes (these are usually incomplete rows)
                                continue
                            an = _md_escape(str(raw_name))
                            lines.append(
                                f"- {an} — **{status(aid, set_attr_added, set_attr_removed, changed_attr_ids)}**"
                            )
                            ach = attr_changes_by_id.get(aid)
                            if ach:
                                lines.append(_md_list(ach.changes, indent=2))
                        lines.append("")
            else:
                lines.append("_No datatype changes in this package._\n")

            enum_ids = sort_by_name(pkg_enums.get(pid, set()), {**A_enum, **B_enum})
            if enum_ids:
                lines.append("### Enumerations\n")
                for eid in enum_ids:
                    e = B_enum.get(eid) or A_enum.get(eid)
                    en = _md_escape(getattr(e, "name", "(no name)"))
                    lines.append(f"#### {en} — **{status(eid, set_enum_added, set_enum_removed, changed_enum_ids)}**\n")
                    enum_diff = enum_changes_by_id.get(eid)
                    if enum_diff:
                        lines.append(_md_list(enum_diff.changes) + "\n")
                    lc = lit_changes.get(eid)
                    if lc:
                        lines.append("##### Literals\n")
                        for n in lc.get("added", []):
                            lines.append(f"- `{_md_escape(n)}` — **Added**")
                        for n in lc.get("removed", []):
                            lines.append(f"- `{_md_escape(n)}` — **Removed**")
                        lines.append("")
            else:
                lines.append("_No enumeration changes in this package._\n")

        with open(args.outputfile, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip() + "\n")
