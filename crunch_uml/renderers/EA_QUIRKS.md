# EA quirks — XMI renderer

The `xmi` renderer (`xmirenderer.py`) writes XMI 2.1 with the Enterprise
Architect extension section. Where the XMI specification and EA behaviour
conflict, EA wins. This file documents every deliberate deviation and
EA-specific choice, so future changes do not "fix" them by accident.

## Header and namespaces

- The `xmi:Documentation` element claims `exporter="Enterprise Architect"
  exporterVersion="6.5"`. EA is picky about importing XMI it does not
  recognize as its own export; declaring another exporter makes EA fall back
  to a much more limited import path.
- The namespace URIs are EA's (`http://schema.omg.org/spec/XMI/2.1`,
  `http://schema.omg.org/spec/UML/2.1`), **not** the OMG-standard
  `http://www.omg.org/spec/...` URIs. EA exports and expects the
  `schema.omg.org` variants for XMI 2.1.

## Strict part

- **Association ends.** EA exports navigable association ends as
  `ownedAttribute` elements on the class (with ids like `EAID_dst...`) and
  only non-navigable ends as `ownedEnd` under the association. The renderer
  always writes both ends as `ownedEnd` under the association and *skips*
  attribute rows whose id starts with `EAID_src`/`EAID_dst` (artifacts of a
  previous eaxmi import). Re-importing with the eaxmi parser therefore does
  not recreate those attribute rows; roles and cardinalities live on the
  Association entity and are unaffected.
- End ids follow EA's derivation: `EAID_333AC8C9_...` →
  `EAID_src3AC8C9_...` / `EAID_dst3AC8C9_...` (first three hex characters of
  the first id block replaced).
- `lowerValue` is always written as `uml:LiteralInteger` and `upperValue` as
  `uml:LiteralUnlimitedNatural`, matching EA, regardless of the actual value
  (`*` and `-1` both occur in EA exports for "unlimited").
- **Orphan placeholders** (`<Orphan Class>` rows created by the parsers for
  elements outside the model) are *not* rendered as `packagedElement`. The
  associations that reference them keep their dangling `type` idrefs on
  purpose: the eaxmi parser recreates the placeholder with the same id on
  import, so the round-trip is stable. Associations whose *source* class is
  an orphan are placed in the first root package (EA nests associations in
  the package of their source class; an orphan has none).
- Primitive attribute types are written as `EAJava_<type>` idrefs; the eaxmi
  parser strips the `EA...._` prefix again. The original prefix from the
  imported file (e.g. `EAnone_`, profile-specific prefixes) is not stored in
  the model, so `EAJava_` is used for all primitives.

## Extension part

- Tagged values are written for every string-valued column that has no
  dedicated XML attribute (see `_NON_TAG_COLUMNS`). Tag names equal the
  column names (snake_case); the eaxmi parser maps them back via `fixtag`,
  for which snake_case is a fixed point. EA shows them as regular tagged
  values; the original EA tag spellings (e.g. `domein-iv3`) are not
  preserved.
- `<element>` entries are written with `xmi:type="uml:DataType"` for
  datatypes, matching EA. The eaxmi parser was extended (phase 3) to read
  documentation/tags for `uml:DataType` extension elements as well.
- Generalization connectors *are* written to the extension section
  (`ea_type="Generalization"`), because generalization names, definitions
  and stereotypes have no place in the strict part (EA does not put them
  there either). Like EA, the connector name is carried in the middle-top
  label (`<labels mt="..."/>`); the eaxmi parser was extended to read
  these connectors. Connector *stereotypes* (associations and
  generalizations) are carried as a tagged value named `stereotype`, which
  the eaxmi parser maps back onto the stereotype column — EA shows it as a
  regular tagged value.
- Classes and enumerations whose `package_id` is NULL or dangling (possible
  through json/xlsx imports; SQLite does not enforce the foreign keys) are
  placed in the first root package with a warning instead of being dropped.
  On re-import they belong to that package.
- Characters that are invalid in XML 1.0 (control characters like `\\x0b`,
  which can enter the database through json/xlsx imports) are removed from
  attribute values with a warning; lxml would otherwise refuse to serialize.
- The `<attribute>` extension entries always contain a `<documentation>`
  child (possibly empty): the eaxmi parser indexes `[0]` into that node
  unconditionally.

## Diagrams and geometry

- Node geometry is regenerated from the canonical columns as
  `Left=..;Top=..;Right=..;Bottom=..;` with **positive** Top/Bottom
  (EA screen convention in XMI exports).
- Edge geometry is reassembled as `<ea_geometry>Path=<waypoints>;` where the
  waypoints get their y sign flipped back to EA's negative-y convention and
  are joined with `$`. When no raw geometry was preserved, a minimal valid
  string (`SX=0;...;ILHS=;`) is generated because EA expects the label
  placeholders to be present.
- Edge style is reassembled as `<ea_style>Hidden=<0|1>;`. If the stored
  style string already contains a `Hidden=` component it is written as-is.
  If EA ever produced a style with `Hidden=` in the middle of the string,
  the reassembled string would have it at the end instead — EA parses these
  strings as key/value lists, so the order does not matter.
- Diagram type is always written as `type="Logical"`: crunch_uml only
  supports class diagrams and does not store the diagram type.
- Label geometry (`LMT=CX=..`) is passed through untouched inside the raw
  geometry string; it is never interpreted.

## Verification status

- Round-trip via the own eaxmi parser is covered by
  `test/unit/test_35_xmi_renderer_roundtrip.py` (Monumenten from XMI,
  Monumenten from QEA, Schuldhulpverlening from XMI, InkomenMIM from QEA —
  the latter with 30 datatypes and 30 named/stereotyped generalizations):
  schema B equals schema A on all entities, diagram membership and geometry
  (exact, no 1px tolerance needed).
- **Manual import into Sparx Enterprise Architect: not yet performed.**
  This requires a Windows machine with EA; the result should be recorded
  here once done.
