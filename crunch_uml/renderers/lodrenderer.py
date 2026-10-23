import logging
import os
import re
from typing import Optional, Tuple
from urllib.parse import urlunparse

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, SKOS, XSD

import crunch_uml.schema as sch
from crunch_uml import const
from crunch_uml.exceptions import CrunchException
from crunch_uml.renderers import mim
from crunch_uml.renderers.lod_mim import MimAnnotator
from crunch_uml.renderers.renderer import ModelRenderer, RendererRegistry

logger = logging.getLogger()

# GeoSPARQL: geometrische datatypes worden als WKT-literal gemodelleerd.
GEO = Namespace("http://www.opengis.net/ont/geosparql#")


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# Enterprise Architect-GUID's: EAID_ (elementen) of EAPK_ (pakketten) met
# alfanumerieke groepen; ook de synthetische id's van de parsers (EAID_dst...).
_EA_GUID_RE = re.compile(r"^EA(ID|PK)_[0-9A-Za-z]+(_[0-9A-Za-z]+)*$")

# Het losse woord 'Model' aan het begin of einde van een pakketnaam.
_MODEL_WORD_RE = re.compile(r"^\s*model\b\s*|\s*\bmodel\s*$", re.IGNORECASE)


def model_segment_name(name):
    """Naam van een modelpakket zonder het losse woord 'Model' voor- of achteraan.

    'Model Kern RGBZ' -> 'Kern RGBZ', 'RSGB Model' -> 'RSGB'; 'Gegevensmodel
    Wonen' blijft intact. Blijft er niets over (pakket 'Model'), dan is de
    volledige naam het segment, zodat de IRI nooit een leeg segment krijgt.
    """
    name = (name or "").strip()
    cleaned = _MODEL_WORD_RE.sub("", name).strip()
    return cleaned or name


# ---------------------------------------------------------------------------
# Datatype-mapping: GGM/EA-primitieven -> XSD (of GeoSPARQL)
# ---------------------------------------------------------------------------

# Alfanumeriek met maximumlengte (AN200, AN 40) en numeriek (N2, N6,2).
_AN_RE = re.compile(r"^an\s*(\d+)$")
_N_RE = re.compile(r"^n\s*(\d+)([.,]\d+)?$")

# Genormaliseerd (casefold, zonder randspaties) -> XSD-datatype. Dekt de
# spellingsvarianten die in de praktijk in GGM/EA-modellen voorkomen.
_XSD_TYPEMAP = {
    "string": XSD.string,
    "an": XSD.string,  # kaal 'AN' zonder lengte
    "blob": XSD.base64Binary,
    "text": XSD.string,
    "characterstring": XSD.string,
    "varchar": XSD.string,
    "char": XSD.string,
    "guid": XSD.string,
    "nen3610id": XSD.string,
    # Een onvolledige datum (alleen jaar, of jaar+maand bekend) past niet in
    # xsd:date; xsd:string behoudt de informatie zonder te liegen.
    "onvolledigedatum": XSD.string,
    "date": XSD.date,
    "datum": XSD.date,
    "datetime": XSD.dateTime,
    "datumtijd": XSD.dateTime,
    "timestamp": XSD.dateTime,
    "time": XSD.time,
    "tijd": XSD.time,
    "jaar": XSD.gYear,
    "year": XSD.gYear,
    "int": XSD.integer,
    "integer": XSD.integer,
    "aantal": XSD.integer,
    "count": XSD.integer,
    "bedrag": XSD.decimal,
    "geldbedrag": XSD.decimal,
    "decimal": XSD.decimal,
    "percentage": XSD.decimal,
    "double": XSD.double,
    "float": XSD.float,
    "real": XSD.double,
    "boolean": XSD.boolean,
    "bool": XSD.boolean,
    "indicatie": XSD.boolean,
}

# GML-/geometrietypen -> geo:wktLiteral (GeoSPARQL).
_GEOMETRY_TYPES = {
    "point",
    "multipoint",
    "curve",
    "multicurve",
    "line",
    "linestring",
    "multilinestring",
    "surface",
    "multisurface",
    "polygon",
    "multipolygon",
    "geometry",
    "geometrie",
    "geometriecollectie",
    "geometrycollection",
    "punt",
    "vlak",
    "lijn",
}


def map_datatype(primitive: Optional[str]) -> Tuple[Optional[URIRef], Optional[int]]:
    """Map een GGM/EA-primitief type naar (RDF-datatype, maximumlengte).

    * ``AN<n>`` -> (xsd:string, n) — alfanumeriek met maximumlengte;
    * ``N<n>``  -> (xsd:integer, None) — numeriek;
    * bekende namen (alle spellingsvarianten) -> bijbehorend XSD-type;
    * geometrie -> geo:wktLiteral (GeoSPARQL);
    * onbekend  -> (None, None): de aanroeper beslist (klasse-referentie of
      terugval op xsd:string met waarschuwing).
    """
    if not primitive:
        return None, None
    norm = primitive.strip().casefold()
    if m := _AN_RE.match(norm):
        return XSD.string, int(m.group(1))
    if _N_RE.match(norm):
        return XSD.integer, None
    if norm in _GEOMETRY_TYPES:
        return GEO.wktLiteral, None
    return _XSD_TYPEMAP.get(norm), None


class LodRenderer(ModelRenderer):
    """
    Renders all model packages as a Linked Data ontology.
    A model package is a package with at least 1 class inside.

    Naast de klassen en properties bevat de output:

    * **echte datatypes**: attributen krijgen een ``rdfs:range`` (en SHACL
      ``sh:datatype``) op basis van :func:`map_datatype`; ``AN<n>``-types
      krijgen bovendien ``sh:maxLength``. Attributen waarvan het type de
      naam van een modelklasse is, worden ``owl:ObjectProperty`` met die
      klasse als range (``sh:class`` in de shape);
    * **de domeinhiërarchie**: elk pakket wordt een ``owl:Ontology`` — het
      wortelpakket als ``mim:Informatiemodel`` op de basis-URI, de overige
      (model- en domein)pakketten als ``mim:Domein`` — waar zijn klassen met
      ``rdfs:isDefinedBy`` naar verwijzen, met ``dcterms:isPartOf`` naar het
      bovenliggende pakket en ``owl:imports`` van ouder naar kind (MIM 6.4.9.40);
    * **enumeraties**: elke enumeratie wordt een ``owl:Class`` én
      ``skos:ConceptScheme``; de waarden worden ``skos:Concept``-en (met
      ``skos:inScheme``/``skos:topConceptOf`` en de enumeratie als klasse).
      Attributen die een enumeratie als type hebben — via de directe
      koppeling in het model of via de typenaam — worden
      ``owl:ObjectProperty`` met de enumeratie als range; hun SHACL-shape
      somt de toegestane concepten op met ``sh:in``;
    * **MIM 1.2** (bijlage 6.4): elke resource draagt naast de OWL/SHACL-
      typering de MIM-metaklasse (``mim:Objecttype``, ``mim:Attribuutsoort``,
      ``mim:Relatiesoort``, ``mim:Gegevensgroeptype``,
      ``mim:GestructureerdDatatype``, ...) en de MIM-metagegevens uit het
      model (herkomst, datum opname, kardinaliteit met ``sh:minCount``/
      ``sh:maxCount``, lengte, patroon, authentiek, ...); relaties worden ook
      ``sh:property`` van de NodeShape van de bronklasse. Zie
      :mod:`crunch_uml.renderers.lod_mim`.
    """

    default_exclude_package_names = const.LOD_EXCLUDE_PACKAGE_NAMES

    # Taaltag voor labels, definities en toelichtingen (--lod_language);
    # None geeft literals zonder taaltag.
    _lang: Optional[str] = "nl"

    def writeToFile(self, graph, args):
        pass

    def lit(self, text):
        """Tekstliteral in de taal van de export (MIM 6.4.9.2: rdfs:label met
        de taal van het model), of zonder taaltag als die leeg is."""
        return mim.lang_literal(text, self._lang)

    def addIdentifier(self, g, uri, obj_id, what):
        """Voeg dcterms:identifier toe en meld lege of afwijkende identifiers.

        De GGM-export had één lege identifier en één zonder EAID_-prefix; zo'n
        element is in Enterprise Architect niet terug te vinden. Een lege
        identifier wordt niet als lege literal geschreven; identifiers die niet
        op een EA-GUID lijken worden verzameld en aan het eind van de export in
        één waarschuwing gemeld.
        """
        if obj_id is None or not str(obj_id).strip():
            logger.warning(f"Lege identifier voor {what} <{uri}>; dcterms:identifier weggelaten")
            return
        obj_id = str(obj_id)
        if not _EA_GUID_RE.match(obj_id):
            self._odd_identifiers.setdefault(obj_id, f"{what} <{uri}>")
        g.add((uri, DCTERMS.identifier, Literal(obj_id)))

    def reportOddIdentifiers(self):
        if self._odd_identifiers:
            voorbeelden = ", ".join(f"'{k}' ({v})" for k, v in list(self._odd_identifiers.items())[:10])
            logger.warning(
                f"{len(self._odd_identifiers)} identifiers wijken af van het EA-GUID-patroon (EAID_.../EAPK_...):"
                f" {voorbeelden}" + (" ..." if len(self._odd_identifiers) > 10 else "")
            )

    @staticmethod
    def isRenderableClass(cls):
        """Klassen zonder stereotype zijn in EA-modellen technische elementen
        (ProxyConnector, diagram- en view-hulpklassen) en horen niet in de
        ontologie; datatype-klassen hebben van nature geen Objecttype-stereotype
        en blijven."""
        return bool((cls.stereotype or "").strip()) or bool(cls.is_datatype)

    @staticmethod
    def uniqueSlugs(packages, name_of, soort):
        """Slug per package-id, uniek over de hele verzameling.

        Pakketten met dezelfde slug (acht keer 'Diagram', twee keer
        'Groepattribuutsoort' in het GGM) deelden één namespace, zodat hun
        klassen door elkaar liepen en de ontologie twee identifiers kreeg.
        Botsende pakketten krijgen de slug van het bovenliggende pakket als
        voorvoegsel en, als dat niet volstaat, een volgnummer (deterministisch
        op id). Er wordt gewaarschuwd, want het model zelf is dan dubbelzinnig.
        """
        groups: dict = {}
        for pkg in packages:
            slug = slugify(name_of(pkg) or "") or slugify(pkg.id or "") or "pakket"
            groups.setdefault(slug, []).append(pkg)
        result: dict = {}
        taken = set(groups)
        for slug in sorted(groups):
            group = groups[slug]
            if len(group) == 1:
                result[group[0].id] = slug
                continue
            namen = ", ".join(sorted(f"{p.name} ({p.id})" for p in group))
            logger.warning(
                f"{len(group)} {soort} delen de naam '{slug}': {namen}; ze krijgen de naam van het"
                " bovenliggende pakket als voorvoegsel"
            )
            for pkg in sorted(group, key=lambda p: p.id or ""):
                parent = pkg.parent_package
                parent_slug = slugify(name_of(parent) or "") if parent is not None else ""
                candidate = f"{parent_slug}-{slug}" if parent_slug else slug
                unique, n = candidate, 2
                while unique in taken:
                    unique = f"{candidate}-{n}"
                    n += 1
                taken.add(unique)
                result[pkg.id] = unique
        return result

    def addPackageHierarchy(self, g, models, domain_ns, model_ns, args):
        """Voeg de pakkethiërarchie toe als owl:Ontology-entiteiten.

        Het wortelpakket is het informatiemodel (``mim:Informatiemodel``, op de
        basis-URI, met versie- en MIM-metadata uit de ``--lod_*``-opties); elk
        ander pakket in de hiërarchie is een ``mim:Domein`` (MIM 6.4.7.1).
        Kinderen verwijzen met ``dcterms:isPartOf`` omhoog, ouders importeren
        hun kinderen met ``owl:imports`` (6.4.9.40).
        """
        seen = {}

        # Alle bovenliggende (domein)pakketten vooraf verzamelen, zodat
        # gelijknamige domeinen ('Archief' en 'archief') unieke URI's krijgen.
        domains: dict = {}
        for model in models:
            parent = model.parent_package
            while parent is not None and parent.name and parent.id not in domains:
                if parent.id not in model_ns:
                    domains[parent.id] = parent
                parent = parent.parent_package
        domain_slugs = self.uniqueSlugs(domains.values(), lambda p: p.name, "domeinpakketten")

        def is_root(pkg):
            return pkg.parent_package is None or not pkg.parent_package.name

        def entity_uri(pkg):
            # Een bovenliggend pakket kan zelf ook een model zijn: dan is de
            # ontologie-URI van dat model het ankerpunt, geen domein-URI.
            if pkg.id in model_ns:
                return URIRef(str(model_ns[pkg.id][1]))
            if is_root(pkg):
                # Het informatiemodel zelf: de basis-URI van de export.
                return URIRef(self.annotator.base)
            return domain_ns[domain_slugs.get(pkg.id) or slugify(pkg.name)]

        def add_package(pkg):
            if pkg.id in seen:
                return seen[pkg.id]
            uri = entity_uri(pkg)
            seen[pkg.id] = uri
            if is_root(pkg):
                self.annotator.annotate_informatiemodel(
                    uri,
                    pkg,
                    versie=getattr(args, "lod_version", None),
                    titel=getattr(args, "lod_title", None),
                    uitgever=getattr(args, "lod_publisher", None),
                    licentie=getattr(args, "lod_license", None),
                    informatiedomein=getattr(args, "lod_informatiedomein", None),
                    informatiemodeltype=getattr(args, "lod_informatiemodeltype", None) or "logisch",
                )
            else:
                namespace = str(model_ns[pkg.id][1]) if pkg.id in model_ns else str(uri)
                self.annotator.annotate_domein(uri, pkg, namespace)
            g.add((uri, RDFS.label, self.lit(pkg.name)))
            self.addIdentifier(g, uri, pkg.id, "pakket")
            if pkg.definitie:
                g.add((uri, RDFS.comment, self.lit(pkg.definitie)))
            parent = pkg.parent_package
            if parent is not None and parent.name:
                parent_uri = add_package(parent)
                g.add((uri, DCTERMS.isPartOf, parent_uri))
                self.annotator.imports(parent_uri, uri)
            return uri

        for model in models:
            add_package(model)

    @staticmethod
    def enumConceptUri(enum_uri, literal):
        return URIRef(f"{enum_uri}/{slugify(literal.name) if literal.name else slugify(literal.id)}")

    def addEnumeration(self, g, enum, enum_uri, model_uri, shape_uri):
        """Render één enumeratie als owl:Class + skos:ConceptScheme (en
        mim:Enumeratie, rdfs:subClassOf skos:Concept, met een NodeShape op
        ``shape_uri``; MIM 6.4.5.12) met haar waarden als skos:Concept-en en
        mim:Enumeratiewaarde. Retourneert de concept-URI's (voor
        sh:in-constraints)."""
        g.add((enum_uri, RDF.type, OWL.Class))
        g.add((enum_uri, RDF.type, SKOS.ConceptScheme))
        g.add((enum_uri, RDFS.label, self.lit(enum.name)))
        self.addIdentifier(g, enum_uri, enum.id, "enumeratie")
        if enum.definitie:
            g.add((enum_uri, RDFS.comment, self.lit(enum.definitie)))
        if model_uri is not None:
            g.add((enum_uri, RDFS.isDefinedBy, model_uri))
        self.annotator.annotate_enumeration(enum_uri, enum, shape_uri)

        concepts = []
        for literal in enum.literals:
            concept_uri = self.enumConceptUri(enum_uri, literal)
            concepts.append(concept_uri)
            g.add((concept_uri, RDF.type, SKOS.Concept))
            # Het concept is óók instantie van de enumeratieklasse, zodat de
            # rdfs:range van attributen OWL-semantisch klopt.
            g.add((concept_uri, RDF.type, enum_uri))
            g.add((concept_uri, SKOS.inScheme, enum_uri))
            g.add((concept_uri, SKOS.topConceptOf, enum_uri))
            if literal.name:
                g.add((concept_uri, SKOS.prefLabel, self.lit(literal.name)))
            self.addIdentifier(g, concept_uri, literal.id, "enumeratiewaarde")
            if literal.definitie:
                g.add((concept_uri, SKOS.definition, self.lit(literal.definitie)))
            self.annotator.annotate_enum_literal(concept_uri, literal, enum_uri)
        return concepts

    @staticmethod
    def rendered_attributes(cls):
        """De attributen die een property worden: met een naam en met een type."""
        return [
            attribute
            for attribute in cls.attributes
            if attribute.name is not None
            and (
                attribute.primitive is not None or attribute.enumeration is not None or attribute.type_class is not None
            )
        ]

    @staticmethod
    def rangeSlug(range_uri):
        """Kort achtervoegsel voor een range: 'string', 'wktliteral', 'pand'."""
        text = str(range_uri).rstrip("/")
        return slugify(text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]) or "type"

    def propertyUris(self, cls, ns, class_dict, resolve_range, notes):
        """Unieke, deterministische URI's voor alle properties van een klasse.

        Attributen en uitgaande associaties delen de ruimte ``{model}/{klasse}/``.
        Zonder botsing is de URI simpelweg ``{klasse}/{naam}``. Bij botsing:

        * gelijknamige attributen krijgen het datatype of de doelklasse als
          achtervoegsel (``objectidentificatie-string``, ``objectidentificatie-pand``);
        * gelijknamige associaties, of een associatie met de naam van een
          attribuut, krijgen de doelklasse als achtervoegsel (``heeft-projectlocatie``);
        * naamloze associaties heten naar hun rol of 'relatie', plus doelklasse
          (``relatie-locatie``);
        * blijft er dan nog een botsing over, dan volgt een volgnummer.

        Gelijknamige associaties vielen voorheen samen tot één owl:ObjectProperty
        met meerdere rdfs:range (OWL leest dat als doorsnede). Retourneert
        (attribuut-id -> URI, associatie-id -> URI); botsingen worden in ``notes``
        verzameld voor één samenvattende waarschuwing.
        """
        prefix = slugify(cls.name) + "/"
        taken: set = set()
        attr_uris: dict = {}
        assoc_uris: dict = {}

        def claim(slug):
            candidate, n = slug, 2
            while candidate in taken:
                candidate = f"{slug}-{n}"
                n += 1
            taken.add(candidate)
            return ns[prefix + candidate]

        attr_groups: dict = {}
        for attribute in self.rendered_attributes(cls):
            slug = slugify(attribute.name) if attribute.name else slugify(attribute.id)
            attr_groups.setdefault(slug, []).append(attribute)
        for slug in sorted(attr_groups):
            group = attr_groups[slug]
            if len(group) == 1:
                attr_uris[group[0].id] = claim(slug)
                continue
            notes["attributen"].append(f"{cls.name}.{group[0].name} ({len(group)}x)")
            for attribute in sorted(group, key=lambda a: a.id or ""):
                _, range_uri, _ = resolve_range(attribute)
                attr_uris[attribute.id] = claim(f"{slug}-{self.rangeSlug(range_uri)}")

        assocs = [a for a in cls.uitgaande_associaties if a.dst_class is not None and a.dst_class.id in class_dict]
        assoc_groups: dict = {}
        for assoc in assocs:
            if assoc.name:
                assoc_groups.setdefault(slugify(assoc.name), []).append(assoc)
        for assoc in sorted(assocs, key=lambda a: a.id or ""):
            target = slugify(assoc.dst_class.name) if assoc.dst_class.name else slugify(assoc.dst_class.id)
            if assoc.name:
                slug = slugify(assoc.name)
                if len(assoc_groups[slug]) > 1 or slug in taken:
                    if slug not in notes["_gemeld"]:
                        notes["_gemeld"].add(slug)
                        notes["associaties"].append(f"{cls.name}.{assoc.name} ({len(assoc_groups[slug])}x)")
                    slug = f"{slug}-{target}"
            else:
                rol = slugify(assoc.src_role) if assoc.src_role else "relatie"
                slug = f"{rol}-{target}"
            assoc_uris[assoc.id] = claim(slug)
        return attr_uris, assoc_uris

    def render(self, args, zchema: sch.Schema):
        self._odd_identifiers: dict = {}
        try:
            if args.linked_data_namespace is None:
                logger.warning(
                    f'No namespace provided via parameter "linked_data_namespace", using default {const.DEFAULT_LOD_NS}'
                )
                args.linked_data_namespace = const.DEFAULT_LOD_NS
            elif not isinstance(args.linked_data_namespace, str):
                args.linked_data_namespace = urlunparse(args.linked_data_namespace)

            base = args.linked_data_namespace + ("" if args.linked_data_namespace.endswith("/") else "/")

            # Create graph
            g = Graph()
            # Taal van labels en definities (standaard nl); MIM 1.2-laag: typering en
            # metagegevens op de resources hieronder.
            self._lang = getattr(args, "lod_language", "nl") or None
            self.annotator = MimAnnotator(g, base, self._lang)

            # Namespaces en bindings
            shape_ns = Namespace(base + "shapes/")
            domain_ns = Namespace(base + "domein/")
            g.bind("sh", SH)
            g.bind("shape", shape_ns)
            g.bind("domein", domain_ns)
            g.bind("geo", GEO)
            g.bind("dcterms", DCTERMS)

            # Get list of packages that are to be rendered
            models = self.getModels(args, zchema)
            if not models:
                msg = "Geen modellen gevonden om te renderen. Controleer of het schema pakketten met klassen bevat."
                logger.error(msg)
                raise CrunchException(msg)

            # Voorbereiding over ALLE modellen: namespaces en klasse-indexen,
            # zodat attribuut- en associatie-ranges ook klassen uit andere
            # modellen kunnen aanwijzen.
            model_ns: dict = {}  # package id -> (modelslug, Namespace)
            class_dict: dict = {}  # class guid -> uri
            class_by_name: dict = {}  # klassenaam (casefold) -> uri
            soorten: dict = {}  # class guid -> MIM-soort (mim.mim_soort)
            soort_by_uri: dict = {}  # class uri -> MIM-soort, voor de doelzijde van attributen
            shape_uris: dict = {}  # class guid -> NodeShape-URI, voor de relatie-shapes
            enum_uris: dict = {}  # enum guid -> uri
            enum_by_name: dict = {}  # enumnaam (casefold) -> enum
            enum_by_uri: dict = {}  # enum uri -> enum (voor sh:in)
            skipped_classes: list = []
            # Het modelsegment krijgt dezelfde slug-vorm als klassen en
            # attributen (geen %20 of %28 in IRI's) en is uniek per model. De
            # namespace wordt achter de basis geplakt: urljoin(base, "/slug/")
            # gooide een eventueel pad in de basis-URI weg.
            model_slugs = self.uniqueSlugs(models, lambda p: model_segment_name(p.name), "modelpakketten")
            for model in models:
                modelname = model_slugs[model.id]
                ns = Namespace(base + modelname + "/")
                model_ns[model.id] = (modelname, ns)
                for cls in model.classes:
                    if not cls.name:
                        logger.warning(f"Klasse zonder naam overgeslagen: {cls.id}")
                        continue
                    if not self.isRenderableClass(cls):
                        skipped_classes.append(f"{model.name}/{cls.name}")
                        continue
                    class_uri = ns[slugify(cls.name)]
                    class_dict[cls.id] = class_uri
                    class_by_name.setdefault(cls.name.strip().casefold(), class_uri)
                    soorten[cls.id] = mim.mim_soort(cls)
                    soort_by_uri[class_uri] = soorten[cls.id]
                for enum in model.enumerations:
                    if not enum.name:
                        continue
                    enum_uris[enum.id] = ns[slugify(enum.name)]
                    enum_by_uri[enum_uris[enum.id]] = enum
                    enum_by_name.setdefault(enum.name.strip().casefold(), enum)

            if skipped_classes:
                logger.warning(
                    f"{len(skipped_classes)} klassen zonder stereotype overgeslagen: "
                    + ", ".join(sorted(skipped_classes))
                )

            # Modellen waarvan alle klassen technisch zijn en die geen enumeraties
            # hebben, leveren geen ontologie op.
            leeg = [m for m in models if not any(c.id in class_dict for c in m.classes) and not m.enumerations]
            if leeg:
                logger.info("Modelpakketten zonder te renderen inhoud overgeslagen: " + ", ".join(m.name for m in leeg))
                models = [m for m in models if m not in leeg]
                if not models:
                    msg = "Geen modellen met te renderen klassen of enumeraties gevonden."
                    logger.error(msg)
                    raise CrunchException(msg)

            # Enumeraties die buiten de modelpakketten leven maar wel als
            # attribuuttype voorkomen, krijgen een URI onder /enumeraties/.
            orphan_enum_ns = Namespace(base + "enumeraties/")
            orphan_enums: dict = {}  # enum guid -> enum, na afloop renderen

            def enum_uri_for(enum):
                if enum.id not in enum_uris:
                    enum_uris[enum.id] = orphan_enum_ns[slugify(enum.name)]
                    enum_by_uri[enum_uris[enum.id]] = enum
                    orphan_enums[enum.id] = enum
                return enum_uris[enum.id]

            unmapped_types = set()

            def resolve_range(attribute):
                """Bepaal de range van een attribuut: ('datatype'|'object'|
                'enum', range-URI, maximumlengte). De directe koppelingen uit
                het model (enumeration/type_class) zijn leidend; daarna de
                datatype-mapping op de typenaam en tenslotte naam-matching."""
                if attribute.enumeration is not None and attribute.enumeration.name:
                    return "enum", enum_uri_for(attribute.enumeration), None
                if attribute.type_class is not None and attribute.type_class.id in class_dict:
                    return "object", class_dict[attribute.type_class.id], None
                dtype, max_length = map_datatype(attribute.primitive)
                if dtype is not None:
                    return "datatype", dtype, max_length
                if not attribute.primitive:
                    return "datatype", XSD.string, None
                norm = attribute.primitive.strip().casefold()
                if class_uri := class_by_name.get(norm):
                    return "object", class_uri, None
                if enum := enum_by_name.get(norm):
                    return "enum", enum_uri_for(enum), None
                unmapped_types.add(attribute.primitive)
                return "datatype", XSD.string, None

            # Pakkethiërarchie: wortel als mim:Informatiemodel, overige pakketten
            # als mim:Domein (allemaal owl:Ontology), met dcterms:isPartOf omhoog
            # en owl:imports omlaag.
            self.addPackageHierarchy(g, models, domain_ns, model_ns, args)

            # Property-URI's per klasse (attributen én associaties), uniek binnen
            # de klasse; ook de SHACL-shapes en het relatieblok gebruiken deze.
            prop_uris: dict = {}  # class guid -> (attribuut-id -> uri, associatie-id -> uri)
            uri_notes: dict = {"attributen": [], "associaties": [], "_gemeld": set()}

            # First add all classes
            try:
                for model in models:
                    modelname, ns = model_ns[model.id]
                    model_uri = URIRef(str(ns))
                    verwerkt_voor = len(prop_uris)

                    for cls in model.classes:
                        if cls.id not in class_dict:
                            continue
                        class_uri = class_dict[cls.id]
                        uri_notes["_gemeld"] = set()
                        prop_uris[cls.id] = self.propertyUris(cls, ns, class_dict, resolve_range, uri_notes)
                        attr_uris, _ = prop_uris[cls.id]

                        # Voeg de klasse toe. Een gestructureerd datatype is in MIM
                        # alleen een sh:NodeShape (6.4.6.3), geen owl:Class.
                        soort = soorten[cls.id]
                        if soort == mim.GESTRUCTUREERD_DATATYPE:
                            g.add((class_uri, RDF.type, SH.NodeShape))
                        else:
                            g.add((class_uri, RDF.type, OWL.Class))
                        g.add((class_uri, RDFS.label, self.lit(cls.name)))
                        self.addIdentifier(g, class_uri, cls.id, "klasse")
                        g.add((class_uri, RDFS.isDefinedBy, model_uri))
                        if cls.definitie is not None:
                            g.add((class_uri, RDFS.comment, self.lit(cls.definitie)))
                        self.annotator.annotate_class(class_uri, cls, soort)

                        for attribute in self.rendered_attributes(cls):
                            attr_uri = attr_uris[attribute.id]
                            kind, range_uri, _ = resolve_range(attribute)
                            prop_type = OWL.DatatypeProperty if kind == "datatype" else OWL.ObjectProperty
                            g.add((attr_uri, RDF.type, prop_type))
                            g.add((attr_uri, RDFS.domain, class_uri))
                            g.add((attr_uri, RDFS.label, self.lit(attribute.name)))
                            g.add((attr_uri, RDFS.range, range_uri))
                            g.add((attr_uri, RDFS.isDefinedBy, model_uri))
                            self.addIdentifier(g, attr_uri, attribute.id, "attribuut")
                            if attribute.definitie is not None:
                                g.add((attr_uri, RDFS.comment, self.lit(attribute.definitie)))

                    # Enumeraties van dit model als ConceptScheme + concepten.
                    for enum in model.enumerations:
                        if not enum.name:
                            logger.warning(f"Enumeratie zonder naam overgeslagen: {enum.id}")
                            continue
                        self.addEnumeration(
                            g, enum, enum_uris[enum.id], model_uri, shape_ns[modelname + "/" + slugify(enum.name)]
                        )

                    # Add SHACL NodeShapes for each class
                    for cls in model.classes:
                        if cls.id not in class_dict:
                            continue
                        class_uri = class_dict[cls.id]
                        attr_uris, _ = prop_uris[cls.id]
                        soort = soorten[cls.id]
                        if soort == mim.GESTRUCTUREERD_DATATYPE:
                            # De structuur hangt direct aan het datatype, dat zelf de
                            # NodeShape is (6.4.6.3/6.4.6.4).
                            shape_uri = class_uri
                        else:
                            shape_uri = shape_ns[modelname + "/" + slugify(cls.name)]
                            g.add((shape_uri, RDF.type, SH.NodeShape))
                            g.add((shape_uri, SH.targetClass, class_uri))
                            g.add((shape_uri, RDFS.label, self.lit(cls.name)))
                            self.addIdentifier(g, shape_uri, cls.id, "SHACL-shape van klasse")
                        shape_uris[cls.id] = shape_uri

                        for attribute in self.rendered_attributes(cls):
                            prop_bnode = BNode()
                            attr_uri = attr_uris[attribute.id]
                            g.add((shape_uri, SH.property, prop_bnode))
                            g.add((prop_bnode, SH.path, attr_uri))
                            kind, range_uri, max_length = resolve_range(attribute)
                            doel_soort = soort_by_uri.get(range_uri)
                            if kind == "datatype":
                                g.add((prop_bnode, SH.datatype, range_uri))
                                if max_length is not None:
                                    g.add((prop_bnode, SH.maxLength, Literal(max_length)))
                            elif doel_soort == mim.GESTRUCTUREERD_DATATYPE:
                                # Een gestructureerd datatype heeft geen klasse: de waarde
                                # moet aan de structuur (NodeShape) voldoen.
                                g.add((prop_bnode, SH.node, range_uri))
                                g.add((prop_bnode, SH.nodeKind, SH.BlankNodeOrIRI))
                            elif doel_soort == mim.GEGEVENSGROEPTYPE:
                                g.add((prop_bnode, getattr(SH, "class"), range_uri))
                                g.add((prop_bnode, SH.nodeKind, SH.BlankNodeOrIRI))
                            else:
                                g.add((prop_bnode, getattr(SH, "class"), range_uri))
                                g.add((prop_bnode, SH.nodeKind, SH.IRI))
                            if kind == "enum":
                                # Toegestane waarden expliciet opsommen.
                                enum = enum_by_uri.get(range_uri)
                                if enum is not None and enum.literals:
                                    list_node = BNode()
                                    Collection(
                                        g,
                                        list_node,
                                        [self.enumConceptUri(range_uri, lit) for lit in enum.literals],
                                    )
                                    g.add((prop_bnode, SH["in"], list_node))
                            g.add((prop_bnode, SH.name, self.lit(attribute.name)))
                            if attribute.definitie:
                                g.add((prop_bnode, SH.description, self.lit(attribute.definitie)))
                            # MIM-typering en -metagegevens; zet ook sh:minCount/sh:maxCount
                            # uit de kardinaliteit (6.4.9.15/18) en de lengte-, patroon- en
                            # waardebereik-constraints op de shape.
                            self.annotator.annotate_attribute(
                                attr_uri,
                                prop_bnode,
                                attribute,
                                eigenaar_uri=class_uri,
                                eigenaar_soort=soort,
                                kind=kind,
                                range_uri=range_uri,
                                doel_soort=doel_soort,
                                max_length=max_length,
                            )
                    logger.info(f"Aantal klassen verwerkt in model '{modelname}': {len(prop_uris) - verwerkt_voor}")
            except Exception as e:
                logger.exception("Fout tijdens het renderen van modellen:")
                raise CrunchException(f"Renderproces mislukt: {e}") from e

            # Then add all relations
            for model in models:
                modelname, ns = model_ns[model.id]
                for cls in model.classes:
                    if cls.id not in class_dict:
                        continue
                    # First set inheritance. cls.superclasses levert Generalization-
                    # objecten waarin cls de subklasse is en .superclass de ouder.
                    sub_cls = class_dict.get(cls.id)
                    for gener in cls.superclasses:
                        if gener.superclass is None or sub_cls is None:
                            continue
                        if gener.superclass.id == cls.id:
                            logger.warning(
                                f"Generalisatie van klasse '{cls.name}' naar zichzelf overgeslagen: {gener.id}"
                            )
                            continue
                        super_cls = class_dict.get(gener.superclass.id)
                        if super_cls is not None:
                            g.add((sub_cls, RDFS.subClassOf, super_cls))

                    # Then set associations
                    if cls.id not in prop_uris:
                        continue
                    _, assoc_uris = prop_uris[cls.id]
                    for assoc in cls.uitgaande_associaties:
                        from_cls = class_dict.get(cls.id)
                        to_cls = class_dict.get(getattr(assoc.dst_class, "id", None))
                        if to_cls is None:
                            logger.warning(f"Doelklasse onbekend voor associatie {assoc.name or assoc.id}")
                            continue

                        if from_cls is not None and to_cls is not None:
                            assoc_uri = assoc_uris[assoc.id]
                            label = assoc.name or assoc.src_role or f"relatie naar {assoc.dst_class.name}"
                            g.add((assoc_uri, RDF.type, OWL.ObjectProperty))
                            g.add((assoc_uri, RDFS.domain, from_cls))
                            g.add((assoc_uri, RDFS.range, to_cls))
                            g.add((assoc_uri, RDFS.label, self.lit(label)))
                            g.add((assoc_uri, RDFS.isDefinedBy, URIRef(str(ns))))
                            self.addIdentifier(g, assoc_uri, assoc.id, "associatie")
                            if assoc.definitie is not None:
                                g.add((assoc_uri, RDFS.comment, self.lit(assoc.definitie)))
                            # De relatie als sh:property van de NodeShape van de
                            # bronklasse (6.4.5.6, 6.4.9.31/32), met kardinaliteit.
                            prop_bnode = BNode()
                            g.add((shape_uris[cls.id], SH.property, prop_bnode))
                            g.add((prop_bnode, SH.path, assoc_uri))
                            g.add((prop_bnode, getattr(SH, "class"), to_cls))
                            g.add((prop_bnode, SH.nodeKind, SH.IRI))
                            g.add((prop_bnode, SH.name, self.lit(label)))
                            if assoc.definitie:
                                g.add((prop_bnode, SH.description, self.lit(assoc.definitie)))
                            self.annotator.annotate_association(
                                assoc_uri, prop_bnode, assoc, from_cls, to_cls, naam=label
                            )

            # Enumeraties die buiten de modelpakketten leven maar wel als
            # attribuuttype zijn aangetroffen.
            for enum in orphan_enums.values():
                self.addEnumeration(g, enum, enum_uris[enum.id], None, shape_ns["enumeraties/" + slugify(enum.name)])

            for soort, voorbeelden in (
                ("attributen", uri_notes["attributen"]),
                ("associaties", uri_notes["associaties"]),
            ):
                if voorbeelden:
                    logger.warning(
                        f"{len(voorbeelden)} klassen hebben gelijknamige {soort}; hun URI's kregen het type of de"
                        f" doelklasse als achtervoegsel: {', '.join(voorbeelden[:10])}"
                        + (" ..." if len(voorbeelden) > 10 else "")
                    )

            if unmapped_types:
                overview = ", ".join(sorted(unmapped_types))
                logger.warning(
                    f"Onbekende datatypes teruggevallen op xsd:string (geen mapping, geen modelklasse of"
                    f" -enumeratie): {overview}"
                )

            self.reportOddIdentifiers()
            logger.info(self.annotator.samenvatting())
            self.writeToFile(g, args)
        except CrunchException:
            raise  # Laat eigen excepties door
        except Exception as e:
            logger.exception("Onverwachte fout in LodRenderer:")
            raise CrunchException(f"Interne fout tijdens renderen: {e}") from e


@RendererRegistry.register(
    "ttl",
    descr="Renderer that renders Linked Data ontology in turtle from the supplied models, "
    + "where a model is a package that includes at least one Class. "
    + 'Needs parameter "output_lod_url".',
)
class TTLRenderer(LodRenderer):
    """
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    """

    def writeToFile(self, graph, args):
        # get filename
        base_name, ext = os.path.splitext(args.outputfile)
        outputfile = f"{base_name}.ttl"

        with open(outputfile, "w") as file:
            file.write(graph.serialize(format="turtle"))


@RendererRegistry.register(
    "rdf",
    descr="Renderer that renders Linked Data ontology in RDF from the supplied models, "
    + "where a model is a package that includes at least one Class. "
    + ' Needs parameter "output_lod_url".',
)
class RDFRenderer(LodRenderer):
    """
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    """

    def writeToFile(self, graph, args):
        # get filename
        base_name, ext = os.path.splitext(args.outputfile)
        outputfile = f"{base_name}.rdf"

        with open(outputfile, "w") as file:
            file.write(graph.serialize(format="xml"))


@RendererRegistry.register(
    "json-ld",
    descr="Renderer that renders Linked Data ontology in JSON-LD from the supplied models, "
    + "where a model is a package that includes at least one Class. "
    + ' Needs parameter "output_lod_url".',
)
class JSONLDRenderer(LodRenderer):
    """
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    """

    def writeToFile(self, graph, args):
        # get filename
        base_name, ext = os.path.splitext(args.outputfile)
        outputfile = f"{base_name}.jsonld"

        with open(outputfile, "w") as file:
            file.write(graph.serialize(format="json-ld"))
