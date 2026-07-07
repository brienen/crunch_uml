"""Context enrichment for element translation.

The i18n data structure is flat (section → GUID → translatable fields); the
hierarchy lives in the database. This module queries the schema once and
builds, per (section, GUID), the compact context header the LLM prompt
uses: the model (root package) name and definition, the package, the owning
class or enumeration for attributes/literals (with definition), and sibling
names. Deliberately compact — long prompts with irrelevant context make
local models worse, not better.

Any database problem degrades to an empty context map with a warning:
translation then simply runs with less context, it never crashes.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from crunch_uml import db

logger = logging.getLogger()

MAX_SIBLINGS = 15

ContextMap = Dict[Tuple[str, str], Dict[str, str]]


def build_context_map(schema) -> ContextMap:
    """Build the (section, GUID) → context dict map for one schema."""
    try:
        return _build(schema)
    except Exception as e:
        logger.warning(f"Contextverrijking uit het schema mislukt ({e}); er wordt zonder modelcontext vertaald.")
        return {}


def _build(schema) -> ContextMap:
    session = schema.get_session()

    def _all(model):
        return session.query(model).filter(model.schema_id == schema.schema_id).all()

    packages = {p.id: p for p in _all(db.Package)}
    classes = {c.id: c for c in _all(db.Class)}
    enums = {e.id: e for e in _all(db.Enumeratie)}
    attributes = _all(db.Attribute)
    literals = _all(db.EnumerationLiteral)

    def _root_of(package_id: Optional[str]):
        pkg = packages.get(package_id)
        seen = set()
        while pkg is not None and pkg.parent_package_id in packages and pkg.id not in seen:
            seen.add(pkg.id)
            pkg = packages[pkg.parent_package_id]
        return pkg

    def _package_context(package_id: Optional[str]) -> Dict[str, str]:
        ctx: Dict[str, str] = {}
        pkg = packages.get(package_id)
        if pkg is not None and pkg.name:
            ctx["package"] = pkg.name
        root = _root_of(package_id)
        if root is not None and root.name and (pkg is None or root.id != pkg.id):
            ctx["model"] = root.name
            if root.definitie:
                ctx["model_definition"] = root.definitie
        return ctx

    context_map: ContextMap = {}

    for pkg in packages.values():
        context_map[("packages", pkg.id)] = _package_context(pkg.parent_package_id)

    for section, objects in (("classes", classes.values()), ("enumerations", enums.values())):
        for obj in objects:
            context_map[(section, obj.id)] = _package_context(obj.package_id)

    # Siblings: names of the other attributes/literals of the same owner.
    siblings_by_owner: Dict[Tuple[str, str], list] = {}
    for attr in attributes:
        siblings_by_owner.setdefault(("attributes", attr.clazz_id), []).append(attr.name or "")
    for lit in literals:
        siblings_by_owner.setdefault(("enumerationliterals", lit.enumeratie_id), []).append(lit.name or "")

    def _member_context(section: str, obj, owner) -> Dict[str, str]:
        ctx = _package_context(owner.package_id) if owner is not None else {}
        if owner is not None and owner.name:
            ctx["parent"] = owner.name
            if owner.definitie:
                ctx["parent_definition"] = owner.definitie
        owner_id = obj.clazz_id if section == "attributes" else obj.enumeratie_id
        names = [n for n in siblings_by_owner.get((section, owner_id), []) if n and n != obj.name]
        if names:
            ctx["siblings"] = ", ".join(sorted(names)[:MAX_SIBLINGS])
        return ctx

    for attr in attributes:
        context_map[("attributes", attr.id)] = _member_context("attributes", attr, classes.get(attr.clazz_id))
    for lit in literals:
        context_map[("enumerationliterals", lit.id)] = _member_context(
            "enumerationliterals", lit, enums.get(lit.enumeratie_id)
        )

    return context_map
