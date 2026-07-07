"""
Tests for crunch_uml.translation.disambiguate — deterministic concept choice.

The core scenario is the homonym: "partij" as contract party vs political
party. Given the source definition from the model, the right concept must be
chosen without any LLM; when the evidence is thin or contradictory the
function must return None so the (non-deterministic) choice escalates to the
LLM layer instead of being guessed.
"""

from __future__ import annotations

from crunch_uml.translation import termbank
from crunch_uml.translation.disambiguate import definition_overlap, disambiguate
from crunch_uml.translation.termbank import Candidate

TTL_FIXTURE = "./test/data/termbank_fixture.ttl"


def _candidate(term, uri, definition=None, domains=None, priority=0):
    return Candidate(
        term=term,
        source_term="partij",
        uri=uri,
        source="test",
        priority=priority,
        exact=True,
        definition=definition,
        domains=domains or [],
    )


def test_no_candidates_returns_none():
    assert disambiguate([]) is None


def test_single_candidate_is_chosen_without_further_evidence():
    only = _candidate("permit", "ex:vergunning")
    assert disambiguate([only]) is only


def test_homonym_resolved_by_source_definition():
    """The model's own definition mentions 'overeenkomst' (contract), which
    overlaps the legal-party concept definition — not the political one."""
    index, _ = termbank.load_termbanks([TTL_FIXTURE])
    candidates = index.lookup("partij", from_lang="nl", to_lang="en")
    assert len(candidates) == 2

    chosen = disambiguate(
        candidates,
        source_definition="Persoon of rechtspersoon die deelneemt aan een overeenkomst met de gemeente.",
    )
    assert chosen is not None
    assert chosen.term == "party"
    assert chosen.uri.endswith("partij-recht")

    chosen = disambiguate(
        candidates,
        source_definition="Politieke organisatie die kandidaten stelt bij gemeenteraadsverkiezingen.",
    )
    assert chosen is not None
    assert chosen.term == "political party"


def test_homonym_resolved_by_domain_context():
    """Without a definition, an unambiguous domain match (package/model
    context vs candidate domains) decides."""
    index, _ = termbank.load_termbanks([TTL_FIXTURE])
    candidates = index.lookup("partij", from_lang="nl", to_lang="en")

    chosen = disambiguate(candidates, context_terms=["Politiek"])
    assert chosen is not None
    assert chosen.term == "political party"


def test_ambiguous_without_evidence_returns_none():
    """Two candidates, no definition, no domain context → the choice belongs
    to the LLM layer, not to a coin flip."""
    index, _ = termbank.load_termbanks([TTL_FIXTURE])
    candidates = index.lookup("partij", from_lang="nl", to_lang="en")
    assert disambiguate(candidates) is None


def test_unrelated_definition_returns_none():
    """A source definition that matches neither candidate must not force a
    choice (both scores stay below the minimum)."""
    index, _ = termbank.load_termbanks([TTL_FIXTURE])
    candidates = index.lookup("partij", from_lang="nl", to_lang="en")
    chosen = disambiguate(candidates, source_definition="Hoeveelheid goederen die in één zending wordt geleverd.")
    assert chosen is None


def test_near_tie_returns_none():
    """Two candidates whose definitions overlap the source almost equally:
    the margin requirement must block a fragile pick."""
    a = _candidate("party", "ex:a", definition="rechtspersoon neemt deel aan overeenkomst")
    b = _candidate("political party", "ex:b", definition="rechtspersoon neemt deel aan verkiezingen")
    chosen = disambiguate([a, b], source_definition="Rechtspersoon die deelneemt aan iets.")
    assert chosen is None


def test_deterministic_repeated_calls_same_answer():
    index, _ = termbank.load_termbanks([TTL_FIXTURE])
    candidates = index.lookup("partij", from_lang="nl", to_lang="en")
    definition = "Persoon die deelneemt aan een overeenkomst of rechtszaak."
    answers = {disambiguate(candidates, source_definition=definition).uri for _ in range(10)}
    assert len(answers) == 1


def test_definition_overlap_edge_cases():
    assert definition_overlap(None, "iets") == 0.0
    assert definition_overlap("iets", None) == 0.0
    assert definition_overlap("de het een", "van tot bij") == 0.0  # alleen stopwoorden
    assert definition_overlap("vergunning bouwwerk", "vergunning voor een bouwwerk") > 0.5
