import fnmatch
import logging
import os
import re
from typing import Optional, Tuple
from urllib.parse import urlunparse

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, SKOS, XSD

import crunch_uml.db as db
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
# Een volgnummer waarmee EA-pakketten en -diagrammen op volgorde worden gezet:
# '3 Economie', '99 Kern', '0 Bestuur, Politiek en Ondersteuning'.
_ORDER_PREFIX_RE = re.compile(r"^\s*\d+[\s._-]+(?=\S)")


def strip_order_prefix(name):
    """Naam zonder het volgnummer vooraan: '99 Kern' -> 'Kern', '3 Economie' ->
    'Economie'. Het nummer ordent de pakketten in EA en is geen betekenis, dus
    hoort niet in een IRI. Een naam die alleen uit een nummer bestaat blijft."""
    name = (name or "").strip()
    return _ORDER_PREFIX_RE.sub("", name).strip() or name


def model_segment_name(name):
    """Naam van een modelpakket zonder volgnummer en zonder het losse woord
    'Model' voor- of achteraan.

    'Model Kern RGBZ' -> 'Kern RGBZ', 'RSGB Model' -> 'RSGB', '3 Economie' ->
    'Economie'; 'Gegevensmodel Wonen' blijft intact. Blijft er niets over
    (pakket 'Model'), dan is de volledige naam het segment, zodat de IRI nooit
    een leeg segment krijgt.
    """
    name = strip_order_prefix(name)
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
    "uri": XSD.anyURI,
    "anyuri": XSD.anyURI,
    "url": XSD.anyURI,
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
    # ISO 19107 / GML3-datatypen zoals het GGM ze als DataType-elementen kent.
    "gm_object",
    "gm_primitive",
    "gm_aggregate",
    "gm_point",
    "gm_multipoint",
    "gm_curve",
    "gm_multicurve",
    "gm_linestring",
    "gm_surface",
    "gm_multisurface",
    "gm_polygon",
    "gm_multipolygon",
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

    # Serialisatie van de subklassen: rdflib-formaat en bestandsextensie.
    rdf_format = "turtle"
    extension = ".ttl"

    # Taaltag voor labels, definities en toelichtingen (--lod_language);
    # None geeft literals zonder taaltag.
    _lang: Optional[str] = "nl"
    # Slug van het wortelpakket; een naamgenoot eronder levert geen padsegment.
    _root_slug: Optional[str] = None

    # ------------------------------------------------------------------
    # Uitvoer: ontologie, SHACL-shapes en views
    # ------------------------------------------------------------------

    def writeGraph(self, path, graph, header=None):
        """Serialiseer een graaf naar ``path``; ``header`` (een Turtle-
        commentaarregel zoals ``# graph: <...>``) alleen in Turtle."""
        data = graph.serialize(format=self.rdf_format)
        with open(path, "w", encoding="utf-8") as file:
            if header and self.rdf_format == "turtle":
                file.write(header + "\n\n")
            file.write(data)

    def outputPath(self, outputfile):
        """Het uitvoerpad met de extensie van dit formaat."""
        base_name, _ = os.path.splitext(outputfile)
        return base_name + self.extension

    def writeToFile(self, graph, args):
        self.writeGraph(self.outputPath(args.outputfile), graph)

    def writeOutput(self, g, args, zchema, shape_ns, context):
        """Schrijf de export: het uitvoerbestand, en op verzoek de SHACL-shapes
        apart (``--lod_shapes_file``) en de views per diagram (``--lod_views_dir``).

        De views zijn altijd deelgrafen van de ontologie zonder SHACL, ook als
        het uitvoerbestand zelf ontologie en shapes samen bevat.
        """
        shapes_file = getattr(args, "lod_shapes_file", None)
        views_dir = getattr(args, "lod_views_dir", None)
        ontology = g
        if shapes_file or views_dir:
            ontology, shapes = self.splitShapes(g, shape_ns)
        if shapes_file:
            shapes_path = self.outputPath(shapes_file)
            self.addShapesHeader(ontology, shapes, shape_ns, args)
            self.writeToFile(ontology, args)
            self.writeGraph(shapes_path, shapes)
            logger.info(
                f"Ontologie ({len(ontology)} triples) geschreven naar {self.outputPath(args.outputfile)};"
                f" SHACL-shapes ({len(shapes)} triples) naar {shapes_path}"
            )
        else:
            self.writeToFile(g, args)
        if views_dir:
            self.writeViews(ontology, args, zchema, context)

    @staticmethod
    def splitShapes(g, shape_ns):
        """Verdeel de graaf in (ontologie, shapes).

        Naar de shapes gaat elke triple met SHACL-vocabulaire: de NodeShapes
        onder ``{basis}shapes/`` met alles wat erover gezegd wordt, elke triple
        met een ``sh:``-predicaat, de typering ``a sh:NodeShape`` (ook van
        gestructureerde en eigen primitieve datatypen, die in MIM 6.4.6 zelf
        de NodeShape zijn) en alle blank nodes (PropertyShapes en de
        ``sh:in``-lijsten; de ontologie zelf bevat er geen). De rest — klassen,
        properties, enumeraties, pakketten en hun MIM-metagegevens — is de
        ontologie. Beide grafen houden de prefix-bindingen van de export.
        """
        ontology, shapes = Graph(), Graph()
        for prefix, namespace in g.namespaces():
            ontology.bind(prefix, namespace)
            shapes.bind(prefix, namespace)
        shape_prefix = str(shape_ns)
        sh_prefix = str(SH)
        for s, p, o in g:
            is_shape = (
                isinstance(s, BNode)
                or (isinstance(s, URIRef) and str(s).startswith(shape_prefix))
                or str(p).startswith(sh_prefix)
                or (p == RDF.type and o in (SH.NodeShape, SH.PropertyShape))
            )
            (shapes if is_shape else ontology).add((s, p, o))
        return ontology, shapes

    def addShapesHeader(self, ontology, shapes, shape_ns, args):
        """De shapes-graaf als eigen owl:Ontology op ``{basis}shapes/`` die de
        ontologie importeert; de ontologie verwijst ernaar met rdfs:seeAlso."""
        shapes_iri = URIRef(str(shape_ns))
        base_iri = URIRef(self.annotator.base)
        titel = next(ontology.objects(base_iri, DCTERMS.title), None)
        shapes.add((shapes_iri, RDF.type, OWL.Ontology))
        shapes.add((shapes_iri, RDFS.label, self.lit(f"{titel or 'Ontologie'} (SHACL)")))
        shapes.add((shapes_iri, OWL.imports, base_iri))
        versie = mim.clean_value(getattr(args, "lod_version", None))
        if versie:
            shapes.add((shapes_iri, OWL.versionInfo, Literal(versie)))
        ontology.add((base_iri, RDFS.seeAlso, shapes_iri))

    @staticmethod
    def viewExcludePatterns(args):
        """De patronen uit --lod_views_exclude, of de standaardlijst."""
        value = getattr(args, "lod_views_exclude", None)
        if value is None:
            value = const.LOD_VIEWS_EXCLUDE_NAMES
        if not value:
            return []
        return [pattern.strip().casefold() for pattern in value.split(",") if pattern.strip()]

    def isExcludedView(self, diagram, patterns):
        """Waar als de diagramnaam of een package erboven een patroon matcht."""
        if not patterns:
            return False
        name = (diagram.name or "").casefold()
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns):
            return True
        return self.isExcludedByName(diagram.package, patterns)

    def viewSegments(self, diagram):
        """De padsegmenten van een view: het pakketpad van het diagram
        (:meth:`packagePath`, dezelfde segmenten als de term-IRI's) gevolgd
        door de slug van de diagramnaam zonder volgnummer."""
        segments = list(self.packagePath(diagram.package))
        segments.append(slugify(strip_order_prefix(diagram.name)) or slugify(diagram.id or "") or "diagram")
        return segments

    def viewGraph(self, ontology, diagram, context):
        """De deelgraaf van één diagram, of None als er niets op staat dat in
        de ontologie zit.

        Inhoud: de klassen en enumeraties op het diagram met alles wat de
        ontologie erover zegt, al hun attributen en enumeratiewaarden, de
        enumeraties die het type van zo'n attribuut zijn (met hun waarden, ook
        als ze niet getekend zijn), de associaties waarvan bron en doel op het
        diagram staan en de generalisaties tussen diagramelementen. De view
        volgt de elementen op het diagram, niet de tekenwijze: een connector
        die in EA op het diagram verborgen is ('Hidden') telt mee. Een
        rdfs:subClassOf naar een klasse buiten het diagram blijft weg; andere
        verwijzingen naar elementen buiten het diagram (rdfs:range, mim:type)
        blijven staan, want het zijn dezelfde IRI's als in de ontologie.
        """
        class_dict = context["class_dict"]
        enum_uris = context["enum_uris"]
        enum_by_uri = context["enum_by_uri"]
        prop_uris = context["prop_uris"]
        model_class_uris = context["model_class_uris"]

        on_classes = [cls for cls in diagram.classes if cls.id in class_dict]
        on_enums = [enum for enum in diagram.enumerations if enum.id in enum_uris]
        if not on_classes and not on_enums:
            return None
        on_ids = {cls.id for cls in on_classes}

        subjects = set()
        enums = {enum_uris[enum.id]: enum for enum in on_enums}
        supers: dict = {}  # klasse-URI -> toegestane superklasse-URI's
        for cls in on_classes:
            class_uri = class_dict[cls.id]
            subjects.add(class_uri)
            attr_uris, assoc_uris = prop_uris.get(cls.id, ({}, {}))
            subjects.update(attr_uris.values())
            for attr_uri in attr_uris.values():
                for range_uri in ontology.objects(attr_uri, RDFS.range):
                    if range_uri in enum_by_uri:
                        enums.setdefault(range_uri, enum_by_uri[range_uri])
            for assoc in cls.uitgaande_associaties:
                dst_id = getattr(assoc.dst_class, "id", None)
                if dst_id in on_ids and assoc.id in assoc_uris:
                    subjects.add(assoc_uris[assoc.id])
            supers[class_uri] = {
                class_dict[gener.superclass.id]
                for gener in cls.superclasses
                if gener.superclass is not None and gener.superclass.id in on_ids
            }
        for enum_uri, enum in enums.items():
            subjects.add(enum_uri)
            subjects.update(self.conceptUris(enum_uri, enum).values())

        view = Graph()
        for prefix, namespace in ontology.namespaces():
            view.bind(prefix, namespace)
        for subject in subjects:
            for pred, obj in ontology.predicate_objects(subject):
                if pred == RDFS.subClassOf and obj in model_class_uris and obj not in supers.get(subject, ()):
                    continue
                view.add((subject, pred, obj))
        return view

    def writeViews(self, ontology, args, zchema, context):
        """Schrijf per diagram een view naar ``--lod_views_dir``.

        Bestand: ``{map}/{segmenten}.{ext}``; graph-IRI ``{basis}[{versie}/]{segmenten}``
        (de versie uit ``--lod_version`` als segment, zodat de view-IRI's nooit
        met term-IRI's botsen en onder de owl:versionIRI vallen), in Turtle als
        kopregel ``# graph: <...>``. De view beschrijft zichzelf als
        owl:Ontology met label, EA-identifier, dcterms:isPartOf het
        informatiemodel en owl:versionInfo.
        """
        views_dir = args.lod_views_dir
        patterns = self.viewExcludePatterns(args)
        versie = mim.clean_value(getattr(args, "lod_version", None))
        version_segment = mim.version_segment(versie) if versie else None
        base = self.annotator.base
        base_iri = URIRef(base)

        diagrams = zchema.get_session().query(db.Diagram).filter(db.Diagram.schema_id == zchema.schema_id).all()
        diagrams.sort(key=lambda d: (d.name or "", d.id or ""))
        written: list = []
        excluded: list = []
        empty: list = []
        duplicates: list = []
        seen_paths: dict = {}
        for diagram in diagrams:
            label = f"{diagram.name} ({diagram.id})"
            if self.isExcludedView(diagram, patterns):
                excluded.append(label)
                continue
            view = self.viewGraph(ontology, diagram, context)
            if view is None:
                empty.append(label)
                continue
            segments = self.viewSegments(diagram)
            pad = "/".join(segments)
            if pad in seen_paths:
                duplicates.append(f"{label} krijgt hetzelfde pad '{pad}' als {seen_paths[pad]}")
                continue
            seen_paths[pad] = label
            view_iri = URIRef(base + (f"{version_segment}/" if version_segment else "") + pad)
            if (view_iri, None, None) in ontology:
                logger.warning(
                    f"View-IRI <{view_iri}> van diagram {label} is al een term in de ontologie; de view krijgt"
                    " geen eigen beschrijving. Geef --lod_version op om de views onder een versiesegment te zetten."
                )
            else:
                view.add((view_iri, RDF.type, OWL.Ontology))
                view.add((view_iri, RDFS.label, self.lit(diagram.name or pad)))
                if diagram.definitie:
                    view.add((view_iri, RDFS.comment, self.lit(diagram.definitie)))
                self.addIdentifier(view, view_iri, diagram.id, "diagram")
                view.add((view_iri, DCTERMS.isPartOf, base_iri))
                if versie:
                    view.add((view_iri, OWL.versionInfo, Literal(versie)))
            path = os.path.join(views_dir, *segments) + self.extension
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.writeGraph(path, view, header=f"# graph: <{view_iri}>")
            written.append(pad)

        logger.info(
            f"{len(written)} views geschreven naar {views_dir}"
            + (f"; {len(excluded)} diagrammen op naam uitgesloten" if excluded else "")
            + (f"; {len(empty)} diagrammen zonder inhoud in de ontologie overgeslagen" if empty else "")
        )
        if empty:
            logger.debug("Diagrammen zonder inhoud in de ontologie: " + ", ".join(empty))
        if duplicates:
            logger.warning(
                f"{len(duplicates)} diagrammen overgeslagen omdat hun pad al bezet is (gelijknamige diagrammen"
                " in hetzelfde pakket): " + "; ".join(duplicates[:10]) + (" ..." if len(duplicates) > 10 else "")
            )
        if not written:
            logger.warning("Geen views geschreven: geen diagram met klassen of enumeraties uit de ontologie.")

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
        """Is deze klasse een modelklasse, of een technisch EA-element?

        Als de bron het EA-objecttype meegeeft (``object_type``, sinds 0.7.0:
        'class', 'datatype', 'boundary', 'proxyconnector', 'text', en
        'enumeration' voor de plaatsvervanger van een associatie-uiteinde op een
        enumeratie) beslist dat: alleen klassen en datatypen horen in de
        ontologie. Een klasse die de modelleur geen stereotype gaf (Aantal,
        Rol) blijft dan gewoon een klasse. Zonder objecttype (oudere databases,
        generieke formaten) geldt de oude regel: klassen zonder stereotype zijn
        technische elementen (ProxyConnector, diagramhulpklassen), tenzij het
        datatype-klassen zijn."""
        kind = (getattr(cls, "object_type", None) or "").strip().casefold()
        if kind:
            return kind in ("class", "datatype")
        return bool((cls.stereotype or "").strip()) or bool(cls.is_datatype)

    @staticmethod
    def isRootPackage(pkg):
        """Het wortelpakket: zonder (benoemde) ouder. Dat is het informatiemodel
        op de basis-URI."""
        return pkg.parent_package is None or not pkg.parent_package.name

    def packagePath(self, pkg):
        """Het pad van een pakket als lijst segmenten, van wortel naar pakket:
        de basis van alle IRI's van zijn klassen (``{basis}kern/bag/pand``),
        van zijn eigen ontologie-IRI (``{basis}kern/bag/``) en van de views.

        Elk pakket levert zijn naam als slug zonder volgnummer en zonder het
        losse woord 'Model' ('99 Kern' -> kern, 'Model BAG' -> bag, 'RSGB
        Model' -> rsgb). Geen segment leveren: het wortelpakket
        (de basis-URI), een pakket met dezelfde naam als het wortelpakket (in
        EA is de modelknoop vaak een naamgenoot van het informatiemodelpakket
        eronder) en een package 'Diagram' (de EA-map met diagrammen naast
        het model). Een pakket met dezelfde naam als zijn ouder zonder
        klassen (de EA-conventies 'BAG' > 'Model BAG' en 'Omgevingswet' >
        'Model Omgevingswet' > 'Model Omgevingswet') gaat in die ouder op:
        één segment 'bag', en het diepste pakket vertegenwoordigt de ouder in
        de hiërarchie. Omdat het pad de boom
        volgt, zijn gelijknamige pakketten op verschillende plaatsen vanzelf
        uniek; alleen gelijknamige pakketten onder dezelfde ouder krijgen een
        volgnummer, met een waarschuwing. Eén keer berekend per pakket
        (deterministisch: wie het eerst komt houdt het kale pad, en de
        aanroeper loopt de modellen op id af).
        """
        if pkg is None:
            return []
        cache = self.__dict__.setdefault("_package_paths", {})
        if pkg.id in cache:
            return cache[pkg.id]
        if self.isRootPackage(pkg):
            self._root_slug = slugify(strip_order_prefix(pkg.name))
            path: list = []
        else:
            parent_path = self.packagePath(pkg.parent_package)
            plain = slugify(strip_order_prefix(pkg.name))
            if not plain or plain == getattr(self, "_root_slug", None) or plain == "diagram":
                path = list(parent_path)
            else:
                slug = slugify(model_segment_name(pkg.name)) or plain
                owners = self.__dict__.setdefault("_path_owners", {})
                merged = self.__dict__.setdefault("_merged", {})
                parent = pkg.parent_package
                if (
                    parent_path
                    and parent_path[-1] == slug
                    and not self.isRootPackage(parent)
                    and not parent.classes
                    and parent.id not in merged
                ):
                    # 'BAG' > 'Model BAG': het pakket gaat op in zijn ouder.
                    merged[parent.id] = pkg.id
                    cache[pkg.id] = list(parent_path)
                    return cache[pkg.id]
                candidate, n = tuple(parent_path) + (slug,), 2
                while candidate in owners and owners[candidate] != pkg.id:
                    if n == 2:
                        logger.warning(
                            f"Pakket '{pkg.name}' ({pkg.id}) heeft dezelfde naam als een ander pakket onder"
                            f" dezelfde ouder ({owners[candidate]}); het krijgt een volgnummer in zijn pad"
                        )
                    candidate, n = tuple(parent_path) + (f"{slug}-{n}",), n + 1
                owners[candidate] = pkg.id
                path = list(candidate)
        cache[pkg.id] = path
        return path

    @staticmethod
    def schemaPackage(parent, pkg_id):
        """Het subpakket van ``parent`` met dit id (het model dat in de ouder opgaat)."""
        for sub in parent.subpackages:
            if sub.id == pkg_id:
                return sub
        raise CrunchException(f"Subpakket {pkg_id} van {parent.name} niet gevonden")

    def packageUri(self, pkg):
        """De ontologie-IRI van een pakket: de basis-URI plus zijn pad, met
        afsluitende slash; het wortelpakket is de basis-URI zelf."""
        path = self.packagePath(pkg)
        return URIRef(self.annotator.base + ("/".join(path) + "/" if path else ""))

    def addPackageHierarchy(self, g, models, args):
        """Voeg de pakkethiërarchie toe als owl:Ontology-entiteiten.

        Het wortelpakket is het informatiemodel (``mim:Informatiemodel``, op de
        basis-URI, met versie- en MIM-metadata uit de ``--lod_*``-opties); elk
        ander pakket in de hiërarchie is een ``mim:Domein`` (MIM 6.4.7.1) op
        ``{basis}{pad}/``, of de ontologie van het model als het pakket
        klassen heeft. Kinderen verwijzen met ``dcterms:isPartOf`` omhoog,
        ouders importeren hun kinderen met ``owl:imports`` (6.4.9.40).
        Pakketten zonder eigen segment (naamgenoot van de wortel, 'Diagram')
        worden overgeslagen: hun kinderen hangen aan de eerstvolgende ouder.
        """
        seen = {}
        is_root = self.isRootPackage
        merged = self.__dict__.setdefault("_merged", {})  # ouder-id -> id van het model dat erin opgaat

        def visible_parent(pkg):
            """De eerste ouder met een eigen IRI; een ouder waarin dit model
            opgaat wordt overgeslagen, een ouder die door zijn model wordt
            vertegenwoordigd levert (via add_package) dat model."""
            parent = pkg.parent_package
            while parent is not None and parent.name and not is_root(parent):
                if merged.get(parent.id) == pkg.id:
                    pkg, parent = parent, parent.parent_package
                    continue
                if parent.id in merged or self.packagePath(parent) != self.packagePath(parent.parent_package):
                    return parent
                parent = parent.parent_package
            return parent

        def add_package(pkg):
            if pkg.id in seen:
                return seen[pkg.id]
            if pkg.id in merged:
                # Dit pakket wordt vertegenwoordigd door het model dat erin opgaat.
                seen[pkg.id] = add_package(self.schemaPackage(pkg, merged[pkg.id]))
                return seen[pkg.id]
            if (
                not is_root(pkg)
                and self.packagePath(pkg) == self.packagePath(pkg.parent_package)
                and merged.get(getattr(pkg.parent_package, "id", None)) != pkg.id
            ):
                # Transparant pakket: geen eigen IRI, de ouder is het ankerpunt.
                seen[pkg.id] = add_package(visible_parent(pkg) or pkg.parent_package)
                return seen[pkg.id]
            uri = self.packageUri(pkg)
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
                self.annotator.annotate_domein(uri, pkg, str(uri))
            g.add((uri, RDFS.label, self.lit(pkg.name)))
            self.addIdentifier(g, uri, pkg.id, "pakket")
            if pkg.definitie:
                g.add((uri, RDFS.comment, self.lit(pkg.definitie)))
            parent = visible_parent(pkg)
            if parent is not None and parent.name:
                parent_uri = add_package(parent)
                g.add((uri, DCTERMS.isPartOf, parent_uri))
                self.annotator.imports(parent_uri, uri)
            return uri

        for model in models:
            add_package(model)

    def conceptUris(self, enum_uri, enum):
        """IRI per enumeratiewaarde (literal-id -> IRI), uniek binnen de
        enumeratie: ``{enumeratie}/{slug van de naam}``. Waarden met dezelfde
        slug (A, A+ en A++ van een energielabel worden alle drie 'a') krijgen
        in alfabetische volgorde een volgnummer: a, a-2, a-3. Eén keer berekend
        per enumeratie, zodat ontologie, sh:in-lijsten en views dezelfde IRI's
        gebruiken."""
        cache = self.__dict__.setdefault("_concept_uris", {})
        if enum.id in cache:
            return cache[enum.id]
        groups: dict = {}
        for literal in enum.literals:
            slug = slugify(literal.name) if literal.name else slugify(literal.id or "")
            groups.setdefault(slug or "waarde", []).append(literal)
        uris: dict = {}
        taken = set(groups)
        for slug, group in groups.items():
            if len(group) == 1:
                uris[group[0].id] = URIRef(f"{enum_uri}/{slug}")
                continue
            namen = ", ".join(f"'{lit.name}'" for lit in group)
            logger.warning(
                f"{len(group)} waarden van enumeratie '{enum.name}' delen de IRI-slug '{slug}' ({namen});"
                " ze krijgen een volgnummer"
            )
            for n, literal in enumerate(sorted(group, key=lambda lit: (lit.name or "", lit.id or "")), start=1):
                candidate = slug if n == 1 else f"{slug}-{n}"
                while n > 1 and candidate in taken:
                    n += 1
                    candidate = f"{slug}-{n}"
                taken.add(candidate)
                uris[literal.id] = URIRef(f"{enum_uri}/{candidate}")
        cache[enum.id] = uris
        return uris

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
        concept_uris = self.conceptUris(enum_uri, enum)
        for literal in enum.literals:
            concept_uri = concept_uris[literal.id]
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
        self._concept_uris: dict = {}
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
            g.bind("sh", SH)
            g.bind("shape", shape_ns)
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
            # De namespace van een model is de basis plus zijn pakketpad
            # (packagePath: 'kern/bag' voor 99 Kern > Model BAG), met dezelfde
            # slug-vorm als klassen en attributen (geen %20 of %28 in IRI's).
            # De namespace wordt achter de basis geplakt: urljoin(base, "/slug/")
            # gooide een eventueel pad in de basis-URI weg. De modellen worden
            # op id afgelopen, zodat gelijknamige pakketten onder één ouder
            # altijd hetzelfde volgnummer krijgen.
            self._package_paths: dict = {}
            self._path_owners: dict = {}
            self._root_slug = None
            for model in sorted(models, key=lambda m: m.id or ""):
                self.packagePath(model)
            for model in models:
                modelname = "/".join(self.packagePath(model))
                ns = Namespace(str(self.packageUri(model)))
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
                if attribute.type_class is not None:
                    # Een typeklasse met de naam van een primitief datatype is een
                    # datatype, geen objecttype: in EA zijn de MIM11-primitieven
                    # (CharacterString, Date, Integer, Boolean, ...) en datatypen
                    # als Bedrag of GUID DataType-elementen waar attributen via hun
                    # classifier naar verwijzen. De XSD-mapping wint dan; anders
                    # zou elk zo getypeerd attribuut een owl:ObjectProperty met
                    # een gestructureerd datatype als range worden.
                    dtype, max_length = map_datatype(attribute.type_class.name)
                    if dtype is not None:
                        return "datatype", dtype, max_length
                    if attribute.type_class.id in class_dict:
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
            self.addPackageHierarchy(g, models, args)

            # Property-URI's per klasse (attributen én associaties), uniek binnen
            # de klasse; ook de SHACL-shapes en het relatieblok gebruiken deze.
            prop_uris: dict = {}  # class guid -> (attribuut-id -> uri, associatie-id -> uri)
            uri_notes: dict = {"attributen": [], "associaties": [], "_gemeld": set()}

            # First add all classes
            try:
                for model in models:
                    modelname, ns = model_ns[model.id]
                    model_uri = URIRef(str(ns))
                    shape_prefix = modelname + "/" if modelname else ""
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
                            g, enum, enum_uris[enum.id], model_uri, shape_ns[shape_prefix + slugify(enum.name)]
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
                            shape_uri = shape_ns[shape_prefix + slugify(cls.name)]
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
                                    concept_uris = self.conceptUris(range_uri, enum)
                                    Collection(g, list_node, [concept_uris[lit.id] for lit in enum.literals])
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

            logger.info(self.annotator.samenvatting())
            context = {
                "class_dict": class_dict,
                "enum_uris": enum_uris,
                "enum_by_uri": enum_by_uri,
                "prop_uris": prop_uris,
                "model_class_uris": set(class_dict.values()),
            }
            self.writeOutput(g, args, zchema, shape_ns, context)
            self.reportOddIdentifiers()
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
    """Linked Data-ontologie in Turtle."""

    rdf_format = "turtle"
    extension = ".ttl"


@RendererRegistry.register(
    "rdf",
    descr="Renderer that renders Linked Data ontology in RDF from the supplied models, "
    + "where a model is a package that includes at least one Class. "
    + ' Needs parameter "output_lod_url".',
)
class RDFRenderer(LodRenderer):
    """Linked Data-ontologie in RDF/XML."""

    rdf_format = "xml"
    extension = ".rdf"


@RendererRegistry.register(
    "json-ld",
    descr="Renderer that renders Linked Data ontology in JSON-LD from the supplied models, "
    + "where a model is a package that includes at least one Class. "
    + ' Needs parameter "output_lod_url".',
)
class JSONLDRenderer(LodRenderer):
    """Linked Data-ontologie in JSON-LD."""

    rdf_format = "json-ld"
    extension = ".jsonld"
