"""Termbank loading and lookup for the translation pipeline.

Sources come from the single ``CRUNCH_UML_TERMBANKS`` env-var: a
comma-separated list of *paths* (files or directories) whose order defines
priority. Formats are detected automatically, never configured:

* **Linked Open Data** — every serialisation rdflib understands (Turtle,
  RDF/XML, N-Triples, JSON-LD, TriG, N-Quads, …), picked by extension via
  ``rdflib.util.guess_format`` with content sniffing as fallback. The
  vocabulary is queried generically — language-tagged labels through
  ``skos:prefLabel`` > ``skos:altLabel`` > ``rdfs:label`` > ``dct:title``,
  definitions through ``skos:definition``/``skos:scopeNote`` — so EuroVoc,
  the GEMMA-begrippenkader or any other SKOS/RDFS/OWL source loads without
  source-specific code.
* **TBX** (IATE) — XML with a ``martif``/``tbx`` root element; both the
  classic ``termEntry/langSet/tig`` and the TBX-core
  ``conceptEntry/langSec/termSec`` shapes are handled, including
  ``reliabilityCode`` and ``subjectField``.

Version/date information is read from the data itself (``owl:versionInfo``,
``dcterms:modified``/``issued``, the TBX header date) and reported by the
preflight; it is never configured per source.

A missing or unreadable source yields a ``logging.warning`` and is skipped —
never a crash, never silent wrong output.
"""

from __future__ import annotations

import difflib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from lxml import etree
from rdflib import Graph, URIRef
from rdflib.namespace import DC, DCTERMS, OWL, RDFS, SKOS
from rdflib.term import Literal
from rdflib.util import guess_format

logger = logging.getLogger()

# Extensions the directory scanner picks up. ``.xml`` is ambiguous (RDF/XML
# or TBX) and resolved by sniffing the root element.
LOD_EXTENSIONS = {".ttl", ".rdf", ".owl", ".nt", ".n3", ".jsonld", ".json-ld", ".trig", ".nq", ".nquads", ".xml"}
TBX_EXTENSIONS = {".tbx"}
SUPPORTED_EXTENSIONS = LOD_EXTENSIONS | TBX_EXTENSIONS

# Label properties in descending preference; the order also determines which
# label becomes the concept's preferred term per language.
_LABEL_PROPS = (SKOS.prefLabel, SKOS.altLabel, RDFS.label, DCTERMS.title, DC.title)
_DEFINITION_PROPS = (SKOS.definition, SKOS.scopeNote)
_DOMAIN_PROPS = (SKOS.inScheme, DCTERMS.subject, DC.subject)

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass
class Concept:
    """A single concept aggregated from one source: labels and definitions
    per language, plus provenance."""

    uri: str
    source: str
    priority: int  # position of the source in CRUNCH_UML_TERMBANKS (lower wins)
    labels: Dict[str, List[str]] = field(default_factory=dict)  # lang -> labels, preferred first
    definitions: Dict[str, str] = field(default_factory=dict)  # lang -> definition/scope note
    domains: List[str] = field(default_factory=list)
    reliability: Optional[int] = None  # IATE reliabilityCode (1-4), TBX only


@dataclass
class Candidate:
    """A lookup result: one possible translation of a source term."""

    term: str  # target-language term
    source_term: str  # the label that matched in the source language
    uri: str
    source: str
    priority: int
    exact: bool
    definition: Optional[str] = None  # target- or source-language definition, for disambiguation
    domains: List[str] = field(default_factory=list)
    reliability: Optional[int] = None


@dataclass
class SourceReport:
    """Preflight report for one configured source path."""

    name: str
    path: str
    loaded: bool
    concepts: int = 0
    version: Optional[str] = None
    date: Optional[str] = None
    error: Optional[str] = None


def _norm(term: str) -> str:
    """Normalise a term for index keys: casefold and collapse whitespace."""
    return " ".join(term.split()).casefold()


def _lang_of(lit: Literal) -> str:
    """Language tag of a literal, reduced to its primary subtag ('en-GB' →
    'en'). Untagged literals map to ''."""
    lang = (lit.language or "").lower()
    return lang.split("-")[0]


def _local_name(uri: str) -> str:
    """Last path/fragment segment of a URI, as a readable fallback label."""
    return re.split(r"[/#]", uri.rstrip("/#"))[-1]


# ---------------------------------------------------------------------------
# LOD loading (rdflib)
# ---------------------------------------------------------------------------

_SNIFF_FORMATS = ("turtle", "xml", "json-ld", "nt", "trig")


def _parse_graph(path: str) -> Graph:
    """Parse ``path`` into an rdflib Graph. Extension-based format guessing
    first; on failure, sniff by trying the common serialisations."""
    graph = Graph()
    fmt = guess_format(path)
    if fmt:
        try:
            graph.parse(path, format=fmt)
            return graph
        except Exception:
            logger.debug(f"Parsen van {path} als {fmt} mislukt; probeer andere formaten...")
    for fmt in _SNIFF_FORMATS:
        try:
            graph = Graph()
            graph.parse(path, format=fmt)
            return graph
        except Exception:
            continue
    raise ValueError(f"geen ondersteund LOD-formaat herkend in {path}")


def _graph_version(graph: Graph) -> Tuple[Optional[str], Optional[str]]:
    """Best-effort (version, date) from the data itself: owl:versionInfo and
    dcterms:modified/issued/date on any subject (concept schemes and
    ontology headers carry these)."""
    version = None
    for _, _, obj in graph.triples((None, OWL.versionInfo, None)):
        version = str(obj)
        break
    date = None
    for prop in (DCTERMS.modified, DCTERMS.issued, DCTERMS.date, DC.date):
        for _, _, obj in graph.triples((None, prop, None)):
            m = _DATE_RE.search(str(obj))
            if m:
                date = m.group(0)
                break
        if date:
            break
    return version, date


def _load_lod(
    path: str, source_name: str, priority: int, languages: Optional[set] = None
) -> Tuple[List[Concept], Optional[str], Optional[str]]:
    """Load any RDF serialisation into Concepts by querying label properties
    generically. Returns (concepts, version, date). An optional ``languages``
    filter (primary subtags) limits which labels/definitions are stored —
    untagged literals always pass."""
    graph = _parse_graph(path)

    def _lang_ok(lit: Literal) -> bool:
        return languages is None or not lit.language or _lang_of(lit) in languages

    concepts: Dict[str, Concept] = {}
    for prop in _LABEL_PROPS:
        for subj, _, obj in graph.triples((None, prop, None)):
            if not isinstance(obj, Literal) or not _lang_ok(obj):
                continue
            uri = str(subj)
            concept = concepts.setdefault(uri, Concept(uri=uri, source=source_name, priority=priority))
            lang = _lang_of(obj)
            labels = concept.labels.setdefault(lang, [])
            label = str(obj).strip()
            # _LABEL_PROPS runs in preference order, so first-seen stays first.
            if label and label not in labels:
                labels.append(label)

    for uri, concept in concepts.items():
        subj = URIRef(uri)
        for prop in _DEFINITION_PROPS:
            for obj in graph.objects(subj, prop):
                if isinstance(obj, Literal) and _lang_ok(obj):
                    lang = _lang_of(obj)
                    concept.definitions.setdefault(lang, str(obj).strip())
        for prop in _DOMAIN_PROPS:
            for obj in graph.objects(subj, prop):
                # Prefer a label of the domain resource; fall back to the
                # last URI segment so EuroVoc scheme URIs stay readable.
                domain: Optional[str] = None
                for label_prop in _LABEL_PROPS:
                    for label_node in graph.objects(obj, label_prop):
                        if isinstance(label_node, Literal):
                            domain = str(label_node).strip()
                            break
                    if domain:
                        break
                domain = domain or _local_name(str(obj))
                if domain and domain not in concept.domains:
                    concept.domains.append(domain)

    result = list(concepts.values())
    if languages is not None:
        # Zonder bron- én doeltaal wordt een concept nooit een kandidaat;
        # wegsnoeien houdt grote bronnen (volledige EuroVoc) geheugen-begrensd.
        result = [c for c in result if len(c.labels) >= 2]

    version, date = _graph_version(graph)
    return result, version, date


# ---------------------------------------------------------------------------
# TBX loading (lxml)
# ---------------------------------------------------------------------------


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _xml_lang(elem) -> str:
    lang = elem.get("{http://www.w3.org/XML/1998/namespace}lang") or elem.get("lang") or ""
    return lang.lower().split("-")[0]


def is_tbx_file(path: str) -> bool:
    """Cheap root-element sniff: TBX roots are ``martif`` (TBX v2/IATE) or
    ``tbx`` (TBX core)."""
    try:
        for _, elem in etree.iterparse(path, events=("start",)):
            return _strip_ns(elem.tag).lower() in ("martif", "tbx")
    except Exception:
        return False
    return False


def _parse_tbx_entry(entry, source_name: str, priority: int, index: int, languages: Optional[set]) -> Optional[Concept]:
    """Parse one termEntry/conceptEntry element into a Concept.

    ``languages`` (primary subtags) restricts which langSets are stored;
    with a filter active, a concept needs labels in at least two of those
    languages to be a usable translation candidate — everything else is
    dropped to keep huge sources (the full IATE export) memory-bounded.
    """
    uri = entry.get("id") or f"{source_name}#{index}"
    concept = Concept(uri=uri, source=source_name, priority=priority)
    for descrip in entry.iter():
        if _strip_ns(descrip.tag) == "descrip" and (descrip.get("type") or "").lower() == "subjectfield":
            domain = (descrip.text or "").strip()
            if domain and domain not in concept.domains:
                concept.domains.append(domain)
    for lang_set in entry:
        if _strip_ns(lang_set.tag) not in ("langSet", "langSec"):
            continue
        lang = _xml_lang(lang_set)
        if languages is not None and lang not in languages:
            continue
        for descrip in lang_set.iter():
            tag = _strip_ns(descrip.tag)
            dtype = (descrip.get("type") or "").lower()
            if tag == "descrip" and dtype == "definition":
                text = (descrip.text or "").strip()
                if text:
                    concept.definitions.setdefault(lang, text)
            elif tag == "term":
                term = (descrip.text or "").strip()
                if term:
                    concept.labels.setdefault(lang, [])
                    if term not in concept.labels[lang]:
                        concept.labels[lang].append(term)
            elif tag == "termNote" and dtype == "reliabilitycode":
                try:
                    code = int((descrip.text or "").strip())
                except ValueError:
                    continue
                # Keep the lowest code seen so the concept is never
                # presented as more reliable than its weakest term.
                concept.reliability = code if concept.reliability is None else min(concept.reliability, code)
    if not concept.labels:
        return None
    if languages is not None and len(concept.labels) < 2:
        return None  # geen bron- én doeltaal → nooit een kandidaat
    return concept


def _load_tbx(
    path: str, source_name: str, priority: int, languages: Optional[set] = None
) -> Tuple[List[Concept], Optional[str], Optional[str]]:
    """Load a TBX file (classic martif or TBX-core element names).

    Streaming via ``iterparse``: the full IATE export is hundreds of MB and
    must never be materialised as one DOM. Each processed element is cleared
    and detached, so memory stays bounded by the surviving Concepts."""
    date = None
    concepts: List[Concept] = []
    for _, elem in etree.iterparse(path, events=("end",)):
        tag = _strip_ns(elem.tag)
        if tag.lower() in ("martifheader", "tbxheader") and date is None:
            header_text = " ".join(str(t) for t in elem.itertext())
            m = _DATE_RE.search(header_text)
            if m:
                date = m.group(0)
        elif tag in ("termEntry", "conceptEntry"):
            concept = _parse_tbx_entry(elem, source_name, priority, len(concepts), languages)
            if concept is not None:
                concepts.append(concept)
        else:
            continue
        # Release the processed subtree and everything before it.
        elem.clear()
        parent = elem.getparent()
        while parent is not None and elem.getprevious() is not None:
            del parent[0]

    return concepts, None, date


# ---------------------------------------------------------------------------
# Directory expansion + source loading
# ---------------------------------------------------------------------------


def expand_paths(paths) -> List[str]:
    """Expand the CRUNCH_UML_TERMBANKS entries: files stay, directories are
    scanned (recursively, sorted alphabetically for determinism) for
    supported extensions. Missing paths are returned as-is so the loader can
    warn about them individually."""
    expanded: List[str] = []
    for path in paths:
        if os.path.isdir(path):
            found = []
            for dirpath, dirnames, filenames in os.walk(path):
                dirnames.sort()
                for filename in sorted(filenames):
                    if os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS:
                        found.append(os.path.join(dirpath, filename))
            if not found:
                logger.warning(f"Termbank-directory '{path}' bevat geen ondersteunde bestanden; overgeslagen.")
            expanded.extend(found)
        else:
            expanded.append(path)
    return expanded


def load_source(
    path: str, priority: int, languages: Optional[set] = None
) -> Tuple[Optional[List[Concept]], SourceReport]:
    """Load one termbank file, auto-detecting TBX vs LOD."""
    name = os.path.splitext(os.path.basename(path))[0]
    if not os.path.isfile(path):
        logger.warning(f"Termbank '{path}' bestaat niet of is geen bestand; bron overgeslagen.")
        return None, SourceReport(name=name, path=path, loaded=False, error="bestand niet gevonden")
    try:
        ext = os.path.splitext(path)[1].lower()
        if ext in TBX_EXTENSIONS or (ext == ".xml" and is_tbx_file(path)):
            concepts, version, date = _load_tbx(path, name, priority, languages)
        else:
            concepts, version, date = _load_lod(path, name, priority, languages)
    except Exception as e:
        logger.warning(f"Termbank '{path}' kon niet worden gelezen ({e}); bron overgeslagen.")
        return None, SourceReport(name=name, path=path, loaded=False, error=str(e))

    report = SourceReport(name=name, path=path, loaded=True, concepts=len(concepts), version=version, date=date)
    return concepts, report


# ---------------------------------------------------------------------------
# Index + lookup
# ---------------------------------------------------------------------------

FUZZY_CUTOFF = 0.85


class TermbankIndex:
    """All loaded concepts, indexed by (normalised label, language)."""

    def __init__(self) -> None:
        self.concepts: List[Concept] = []
        self._by_label: Dict[Tuple[str, str], List[Concept]] = {}

    def add_concepts(self, concepts: List[Concept]) -> None:
        for concept in concepts:
            self.concepts.append(concept)
            for lang, labels in concept.labels.items():
                for label in labels:
                    key = (_norm(label), lang)
                    bucket = self._by_label.setdefault(key, [])
                    if concept not in bucket:
                        bucket.append(concept)

    def __len__(self) -> int:
        return len(self.concepts)

    def _candidates_for(self, concepts: List[Concept], source_term: str, to_lang: str, exact: bool) -> List[Candidate]:
        candidates = []
        for concept in concepts:
            target_labels = concept.labels.get(to_lang) or []
            if not target_labels:
                continue  # concept has no term in the target language
            definition = concept.definitions.get(to_lang) or next(iter(concept.definitions.values()), None)
            candidates.append(
                Candidate(
                    term=target_labels[0],
                    source_term=source_term,
                    uri=concept.uri,
                    source=concept.source,
                    priority=concept.priority,
                    exact=exact,
                    definition=definition,
                    domains=list(concept.domains),
                    reliability=concept.reliability,
                )
            )
        return candidates

    def lookup(self, term: str, from_lang: str, to_lang: str) -> List[Candidate]:
        """Find translation candidates: exact match on the normalised source
        label first, otherwise deterministic fuzzy matching (difflib). The
        result is sorted by (source priority, reliability desc, uri) so equal
        inputs always yield the same candidate order."""
        if not term or not term.strip():
            return []
        key = (_norm(term), from_lang)
        exact_concepts = self._by_label.get(key, [])
        candidates = self._candidates_for(exact_concepts, term, to_lang, exact=True)

        if not candidates:
            same_lang_keys = [label for (label, lang) in self._by_label.keys() if lang == from_lang]
            for match in difflib.get_close_matches(_norm(term), same_lang_keys, n=5, cutoff=FUZZY_CUTOFF):
                concepts = self._by_label.get((match, from_lang), [])
                candidates.extend(self._candidates_for(concepts, term, to_lang, exact=False))

        candidates.sort(key=lambda c: (c.priority, -(c.reliability or 0), c.uri))
        return candidates


def load_termbanks(paths, languages: Optional[set] = None) -> Tuple[TermbankIndex, List[SourceReport]]:
    """Load every source from the (already expanded or raw) path list into a
    single index. Sources that fail to load are reported and skipped.

    ``languages`` is the set of primary language subtags the current run
    actually needs (source + target). Passing it keeps huge sources like the
    full IATE export memory-bounded: only the relevant langSets are stored
    and concepts without at least two of those languages are dropped."""
    if languages is not None:
        languages = {lang.lower().split("-")[0] for lang in languages}
    index = TermbankIndex()
    reports: List[SourceReport] = []
    for priority, path in enumerate(expand_paths(paths)):
        started = time.time()
        concepts, report = load_source(path, priority, languages)
        reports.append(report)
        if concepts:
            index.add_concepts(concepts)
            logger.info(
                f"Termbank '{report.name}': {report.concepts} concepten geladen in {time.time() - started:.1f}s"
            )
    return index, reports
