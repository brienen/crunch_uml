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


def _candidate(term, uri, definition=None, domains=None, priority=0, source_term="partij", exact=True):
    return Candidate(
        term=term,
        source_term=source_term,
        uri=uri,
        source="test",
        priority=priority,
        exact=exact,
        definition=definition,
        domains=domains or [],
    )


def test_no_candidates_returns_none():
    assert disambiguate([]) is None


def test_single_exact_candidate_is_chosen_without_further_evidence():
    only = _candidate("permit", "ex:vergunning", source_term="vergunning")
    assert disambiguate([only]) is only


def test_single_fuzzy_candidate_needs_definition_support():
    """Regressie uit de GGM-proefrun: 'eindRegistratie' fuzzy-matchte één
    willekeurig IATE-concept ('lineTrace') en werd zonder bewijs gekozen.
    Een enkele fuzzy kandidaat mag alleen winnen met definitie-overlap."""
    guess = _candidate(
        "line trace",
        "iate:1592918",
        source_term="eindRegistratie",
        exact=False,
        definition="Trace of a surveyed line in geodesy.",
    )
    assert disambiguate([guess]) is None
    assert disambiguate([guess], source_definition="Datum waarop de registratie is beëindigd.") is None

    supported = _candidate(
        "end of registration",
        "iate:x",
        source_term="eindRegistratie",
        exact=False,
        definition="Datum waarop de registratie eindigt of is beëindigd.",
    )
    chosen = disambiguate([supported], source_definition="Datum waarop de registratie is beëindigd.")
    assert chosen is supported


def test_short_terms_are_never_autopicked():
    """Regressie uit de GGM-proefrun: 'Nee' matchte exact op een
    luchtvaartconcept ('negative') en 'Leeg' fuzzy op 'leegmassa'
    ('kerb mass'). Korte termen gaan altijd naar de LLM."""
    nee = _candidate("negative", "iate:1566471", source_term="Nee", exact=True)
    assert disambiguate([nee]) is None
    leeg = _candidate("kerb mass", "iate:63105", source_term="Leeg", exact=False)
    assert disambiguate([leeg]) is None


def test_unique_domain_winner_needs_same_credentials():
    """Een unieke domeintreffer die fuzzy is, wint niet zonder
    definitie-bewijs; met bewijs wel."""
    a = _candidate("guess", "ex:a", exact=False, domains=["Recht"], definition="Iets juridisch onduidelijks.")
    b = _candidate("other", "ex:b", exact=False, domains=["Landbouw"])
    assert disambiguate([a, b], context_terms=["Recht"]) is None

    a_supported = _candidate(
        "party",
        "ex:a",
        exact=False,
        domains=["Recht"],
        definition="Persoon of rechtspersoon die deelneemt aan een overeenkomst.",
    )
    chosen = disambiguate(
        [a_supported, b],
        source_definition="Rechtspersoon die deelneemt aan een overeenkomst.",
        context_terms=["Recht"],
    )
    assert chosen is a_supported


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
