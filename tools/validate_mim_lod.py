#!/usr/bin/env python
"""Valideer een LOD-export van crunch_uml tegen de MIM 1.2-shapes.

Gebruik:
    python tools/validate_mim_lod.py export.ttl [--shapes PAD] [--ontologie PAD]
                                     [--max-voorbeelden N] [--json RAPPORT.json]

De shapes (mim-shapes.ttl) en het vocabulaire (mim.ttl) komen standaard uit
test/data/mim/ (kopie van https://docs.geostandaarden.nl/mim/mim/media/).
Het vocabulaire wordt in de datagraaf gemengd: de shapes controleren met
sh:class op mim:Datatype (met de subklassen mim:PrimitiefDatatype,
mim:Enumeratie, ...) en met sh:hasValue op skos:inScheme van de MIM-
waardelijsten (authenticiteit, aggregatietypen, informatiemodeltypen), en die
feiten staan in mim.ttl, niet in de export. pyshacl gebruikt een losse
ontologiegraaf alleen voor inferentie, dus mengen is nodig.

De uitvoer is een samenvatting per (shape, pad, constraint) met aantallen en
voorbeeld-focusnodes; de exitcode is 0 als de export conformeert, anders 1.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import RDF, SH

try:
    import pyshacl
except ImportError:  # pragma: no cover - alleen zonder dev-requirements
    sys.exit("pyshacl ontbreekt: pip install pyshacl (zie dev_requirements.txt)")

HIER = Path(__file__).resolve().parent.parent
STANDAARD_SHAPES = HIER / "test" / "data" / "mim" / "mim-shapes.ttl"
STANDAARD_ONTOLOGIE = HIER / "test" / "data" / "mim" / "mim.ttl"
MIM = Namespace("http://modellen.mim-standaard.nl/def/mim#")


def valideer(data_graph: Graph, shapes_path=STANDAARD_SHAPES, ontologie_path=STANDAARD_ONTOLOGIE, inference="none"):
    """Draai pyshacl op de export plus het MIM-vocabulaire en geef
    (conformeert, resultaatgraaf, tekst) terug."""
    shapes = Graph().parse(str(shapes_path), format="turtle")
    gemengd = Graph()
    gemengd += data_graph
    gemengd.parse(str(ontologie_path), format="turtle")
    return pyshacl.validate(
        gemengd,
        shacl_graph=shapes,
        inference=inference,
        advanced=True,
        allow_warnings=False,
    )


def kort(term, graph: Graph) -> str:
    try:
        return graph.namespace_manager.normalizeUri(term)
    except Exception:
        return str(term)


def rapport_resultaten(results: Graph):
    """De resultaten die het rapport zelf meldt (sh:result). De geneste
    details van sh:node/sh:xone (sh:detail) zijn ook sh:ValidationResult en
    zouden anders dubbel en met vertekende componenten meetellen. Meldingen
    over resources uit het MIM-vocabulaire zelf (mim:CharacterString e.d.,
    meegemengd voor de controles) gaan niet over de export en vallen weg."""
    for report in results.subjects(RDF.type, SH.ValidationReport):
        for result in results.objects(report, SH.result):
            focus = results.value(result, SH.focusNode)
            if focus is not None and str(focus).startswith(str(MIM)):
                continue
            yield result


def vat_samen(results: Graph, data_graph: Graph, max_voorbeelden=3):
    """Groepeer de validatieresultaten per (shape, pad, constraintcomponent)."""
    groepen = defaultdict(lambda: {"aantal": 0, "voorbeelden": [], "bericht": None, "ernst": None})
    for result in rapport_resultaten(results):
        shape = results.value(result, SH.sourceShape)
        pad = results.value(result, SH.resultPath)
        component = results.value(result, SH.sourceConstraintComponent)
        focus = results.value(result, SH.focusNode)
        sleutel = (
            kort(shape, results) if shape is not None else "-",
            kort(pad, data_graph) if pad is not None else "-",
            kort(component, results),
        )
        groep = groepen[sleutel]
        groep["aantal"] += 1
        if groep["bericht"] is None:
            bericht = results.value(result, SH.resultMessage)
            groep["bericht"] = str(bericht) if bericht is not None else ""
            ernst = results.value(result, SH.resultSeverity)
            groep["ernst"] = kort(ernst, results) if ernst is not None else "sh:Violation"
        if len(groep["voorbeelden"]) < max_voorbeelden and focus is not None:
            groep["voorbeelden"].append(str(focus))
    rijen = [
        {"shape": shape, "pad": pad, "constraint": component, **waarden}
        for (shape, pad, component), waarden in groepen.items()
    ]
    rijen.sort(key=lambda rij: (-rij["aantal"], rij["shape"], rij["pad"]))
    return rijen


def tel_focusnodes_per_type(data_graph: Graph):
    """Hoeveel getypeerde MIM-resources de export heeft, als noemer bij de aantallen."""
    telling = defaultdict(int)
    for subject, soort in data_graph.subject_objects(RDF.type):
        if str(soort).startswith(str(MIM)):
            telling[kort(soort, data_graph)] += 1
    return dict(sorted(telling.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("export", help="LOD-export (Turtle) van crunch_uml")
    parser.add_argument("--shapes", default=str(STANDAARD_SHAPES), help="MIM-shapes (mim-shapes.ttl)")
    parser.add_argument("--ontologie", default=str(STANDAARD_ONTOLOGIE), help="MIM-vocabulaire (mim.ttl)")
    parser.add_argument("--inference", default="none", choices=["none", "rdfs", "owlrl", "both"])
    parser.add_argument("--max-voorbeelden", type=int, default=3)
    parser.add_argument("--json", help="schrijf de samenvatting ook als JSON naar dit bestand")
    args = parser.parse_args(argv)

    data_graph = Graph().parse(args.export, format="turtle")
    conformeert, results, _ = valideer(data_graph, args.shapes, args.ontologie, args.inference)
    rijen = vat_samen(results, data_graph, args.max_voorbeelden)
    typen = tel_focusnodes_per_type(data_graph)

    print(f"Export: {args.export} ({len(data_graph)} triples)")
    print("MIM-getypeerde resources: " + ", ".join(f"{soort} {aantal}" for soort, aantal in typen.items()))
    print(
        f"Conformeert: {'ja' if conformeert else 'nee'}; {sum(rij['aantal'] for rij in rijen)} meldingen in {len(rijen)} groepen"
    )
    for rij in rijen:
        print(f"\n{rij['aantal']:6d}  {rij['shape']}  {rij['pad']}  {rij['constraint']}  [{rij['ernst']}]")
        print(f"        {rij['bericht']}")
        for voorbeeld in rij["voorbeelden"]:
            print(f"        bv. {voorbeeld}")
    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {"export": args.export, "conformeert": conformeert, "typen": typen, "groepen": rijen},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return 0 if conformeert else 1


if __name__ == "__main__":
    sys.exit(main())
