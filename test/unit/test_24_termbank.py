"""
Tests for crunch_uml.translation.termbank — loading and lookup.

Covered behaviour:

* **Generic LOD loading** — a SKOS .ttl loads via rdflib without any
  source-specific code: prefLabel/altLabel per language, definitions,
  domains (via inScheme with a readable label), version (owl:versionInfo)
  and date (dcterms:modified) read from the data itself.
* **TBX loading** — an IATE-style martif file: terms per langSet,
  definitions, subjectField domains, reliability codes and the release
  date from the header.
* **Lookup** — exact match first (case-insensitive), deterministic fuzzy
  fallback, homonyms yield multiple candidates, concepts without a
  target-language term never appear, priority ordering across sources.
* **Graceful degradation** — a missing path warns and is skipped while the
  remaining sources still load; a directory is scanned automatically.
"""

from __future__ import annotations

import shutil

from crunch_uml.translation import termbank

TTL_FIXTURE = "./test/data/termbank_fixture.ttl"
TBX_FIXTURE = "./test/data/termbank_fixture.tbx"


# ---------------------------------------------------------------------------
# LOD loading
# ---------------------------------------------------------------------------


def test_load_skos_ttl_reads_labels_definitions_domains_and_version():
    index, reports = termbank.load_termbanks([TTL_FIXTURE])

    assert len(reports) == 1
    report = reports[0]
    assert report.loaded
    assert report.name == "termbank_fixture"
    # 4 skos:Concepts + the concept scheme (dct:title) + 2 domain resources
    # (rdfs:label): the loader is deliberately generic and indexes every
    # labelled resource. Harmless for lookup — candidates require a label in
    # the *target* language, which scheme/domain resources don't have.
    assert report.concepts == 7
    assert report.version == "4.22"
    assert report.date == "2020-01-15"


def test_lookup_exact_hit_returns_candidate_with_uri_and_definition():
    index, _ = termbank.load_termbanks([TTL_FIXTURE])
    candidates = index.lookup("vergunning", from_lang="nl", to_lang="en")

    assert len(candidates) == 1
    c = candidates[0]
    assert c.term == "permit"
    assert c.exact
    assert c.uri == "http://example.org/begrippen/vergunning"
    assert "permission" in (c.definition or "").lower() or "toestemming" in (c.definition or "").lower()
    assert c.domains == ["Recht"]


def test_lookup_is_case_insensitive_and_matches_altlabel():
    index, _ = termbank.load_termbanks([TTL_FIXTURE])
    assert index.lookup("Vergunning", from_lang="nl", to_lang="en")[0].term == "permit"
    # altLabel "toestemming" resolves to the same concept.
    assert index.lookup("toestemming", from_lang="nl", to_lang="en")[0].uri.endswith("vergunning")


def test_homonym_yields_multiple_candidates_in_deterministic_order():
    index, _ = termbank.load_termbanks([TTL_FIXTURE])
    candidates = index.lookup("partij", from_lang="nl", to_lang="en")

    assert [c.term for c in candidates] == ["political party", "party"]  # uri-sortering binnen zelfde bron
    assert all(c.exact for c in candidates)
    # Both carry their own definition so disambiguation has something to work with.
    assert all(c.definition for c in candidates)


def test_concept_without_target_language_term_is_never_a_candidate():
    index, _ = termbank.load_termbanks([TTL_FIXTURE])
    assert index.lookup("doorzonwoning", from_lang="nl", to_lang="en") == []


def test_fuzzy_lookup_finds_near_miss_deterministically():
    """A small typo still finds the concept, marked as non-exact."""
    index, _ = termbank.load_termbanks([TTL_FIXTURE])
    candidates = index.lookup("vergunningen", from_lang="nl", to_lang="en")
    assert candidates, "fuzzy match expected for 'vergunningen'"
    assert candidates[0].term == "permit"
    assert not candidates[0].exact


# ---------------------------------------------------------------------------
# TBX loading
# ---------------------------------------------------------------------------


def test_load_tbx_reads_terms_reliability_domain_and_release_date():
    index, reports = termbank.load_termbanks([TBX_FIXTURE])

    report = reports[0]
    assert report.loaded
    assert report.concepts == 2
    assert report.date == "2019-06-30"

    candidates = index.lookup("bouwwerk", from_lang="nl", to_lang="en")
    assert len(candidates) == 1
    c = candidates[0]
    assert c.term == "structure"
    assert c.reliability == 3
    assert c.domains == ["LAW"]
    assert "grond verbonden" in (c.definition or "")


def test_tbx_reliability_keeps_lowest_code():
    """IATE-1002 has reliability 4 (nl) and 2 (en): the concept must not be
    presented as more reliable than its weakest term."""
    index, _ = termbank.load_termbanks([TBX_FIXTURE])
    c = index.lookup("vergunning", from_lang="nl", to_lang="en")[0]
    assert c.term == "licence"
    assert c.reliability == 2


# ---------------------------------------------------------------------------
# Multiple sources, priority, degradation, directories
# ---------------------------------------------------------------------------


def test_source_order_defines_candidate_priority():
    """'vergunning' exists in both fixtures. The source listed first must
    come first in the candidate list (order = priority)."""
    index, _ = termbank.load_termbanks([TBX_FIXTURE, TTL_FIXTURE])
    candidates = index.lookup("vergunning", from_lang="nl", to_lang="en")
    assert [c.term for c in candidates] == ["licence", "permit"]

    index, _ = termbank.load_termbanks([TTL_FIXTURE, TBX_FIXTURE])
    candidates = index.lookup("vergunning", from_lang="nl", to_lang="en")
    assert [c.term for c in candidates] == ["permit", "licence"]


def test_missing_source_warns_and_remaining_sources_still_load(caplog):
    with caplog.at_level("WARNING"):
        index, reports = termbank.load_termbanks(["./does/not/exist.ttl", TTL_FIXTURE])

    assert len(reports) == 2
    assert not reports[0].loaded
    assert reports[1].loaded
    assert any("bestaat niet" in m for m in caplog.messages)
    # The good source is fully usable.
    assert index.lookup("vergunning", from_lang="nl", to_lang="en")


def test_unreadable_source_warns_and_is_skipped(tmp_path, caplog):
    bad = tmp_path / "kapot.ttl"
    bad.write_text("dit is geen turtle @@@ ;;;")
    with caplog.at_level("WARNING"):
        index, reports = termbank.load_termbanks([str(bad)])
    assert not reports[0].loaded
    assert reports[0].error
    assert any("kon niet worden gelezen" in m for m in caplog.messages)
    assert len(index) == 0


def test_directory_is_scanned_for_supported_files(tmp_path):
    lod_dir = tmp_path / "lod"
    lod_dir.mkdir()
    shutil.copy(TTL_FIXTURE, lod_dir / "begrippen.ttl")
    shutil.copy(TBX_FIXTURE, lod_dir / "iate.tbx")
    (lod_dir / "leesmij.txt").write_text("geen termbank")

    index, reports = termbank.load_termbanks([str(lod_dir)])

    assert len(reports) == 2  # .txt niet meegenomen
    assert all(r.loaded for r in reports)
    # Alphabetical order inside the directory: begrippen.ttl before iate.tbx.
    assert index.lookup("vergunning", from_lang="nl", to_lang="en")[0].term == "permit"


def test_xml_extension_is_sniffed_for_tbx_root(tmp_path):
    """A TBX file with a .xml extension must be routed to the TBX loader via
    root-element sniffing, not to rdflib."""
    xml_copy = tmp_path / "iate_export.xml"
    shutil.copy(TBX_FIXTURE, xml_copy)
    index, reports = termbank.load_termbanks([str(xml_copy)])
    assert reports[0].loaded
    assert index.lookup("bouwwerk", from_lang="nl", to_lang="en")[0].term == "structure"


def test_empty_term_lookup_returns_nothing():
    index, _ = termbank.load_termbanks([TTL_FIXTURE])
    assert index.lookup("", from_lang="nl", to_lang="en") == []
    assert index.lookup("   ", from_lang="nl", to_lang="en") == []
