"""Deterministic disambiguation of termbank candidates — no model involved.

Given the candidates for a source term, pick the right one using context
crunch already has: the domain(s) the element lives in (package/model names)
and, decisively, the source definition. The rules, in order:

1. no candidates → nothing to choose;
2. exactly one candidate → take it, but only with credentials: an exact
   match on a term of reasonable length, or definition support. A single
   *fuzzy* hit or a short term ("Nee", "Leeg") is a guess, not a match —
   the GGM pilot showed IATE mapping those to arbitrary concepts
   ('Leeg' → 'kerb mass');
3. domain filter: candidates whose domains overlap the context narrow the
   set; a unique survivor wins under the same credentials as rule 2;
4. definition scoring: token overlap between each candidate's definition and
   the source definition; a unique winner with a minimum score *and* a
   minimum margin over the runner-up wins;
5. otherwise → ``None``: the choice is genuinely ambiguous and is left to
   the LLM layer, which receives all candidates as glossary input.

Everything here is pure string arithmetic: same inputs, same answer, every
run.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set

from crunch_uml.translation.termbank import Candidate

# Minimal Dutch/English stopword set: enough to stop function words from
# dominating the overlap score, small enough to stay predictable.
_STOPWORDS = {
    "de", "het", "een", "en", "of", "van", "in", "op", "aan", "met", "voor", "door", "bij", "tot",
    "die", "dat", "deze", "dit", "is", "zijn", "wordt", "worden", "als", "om", "te", "uit", "over",
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "with", "for", "by", "to", "that",
    "this", "is", "are", "be", "as", "from",
}  # fmt: skip

# A candidate definition must reach this overlap with the source definition
# to win, and beat the runner-up by at least the margin. Values are
# intentionally conservative: when in doubt, defer to the LLM.
MIN_SCORE = 0.15
MIN_MARGIN = 0.05

# Short source terms ("Ja", "Nee", "Leeg") are too ambiguous for an
# autonomous termbank pick, whatever the match quality: IATE matches them to
# arbitrary specialised concepts ("Nee" → aviation "negative"). Below this
# length the candidates only travel along to the LLM as suggestions.
MIN_AUTOPICK_CHARS = 5


def _tokens(text: Optional[str]) -> Set[str]:
    if not text:
        return set()
    words = re.findall(r"[a-zà-ÿ0-9]+", text.casefold())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def definition_overlap(candidate_definition: Optional[str], source_definition: Optional[str]) -> float:
    """Jaccard-like overlap between two definitions, seen from the source
    side: |intersection| / |source tokens|. Returns 0.0 when either side has
    no usable tokens."""
    src = _tokens(source_definition)
    cand = _tokens(candidate_definition)
    if not src or not cand:
        return 0.0
    return len(src & cand) / len(src)


def _domain_matches(candidate: Candidate, context_terms: Set[str]) -> bool:
    for domain in candidate.domains:
        domain_tokens = _tokens(domain)
        if domain_tokens & context_terms:
            return True
    return False


def _autopick_allowed(candidate: Candidate) -> bool:
    """May this candidate be taken WITHOUT definition evidence?

    Only an exact label match on a term of reasonable length qualifies. A
    fuzzy match is a guess ('eindregistratie' ~ 'lijnregistratie'), and
    short terms hit arbitrary specialised concepts — both must prove
    themselves against the source definition or defer to the LLM.
    """
    return candidate.exact and len(candidate.source_term.strip()) >= MIN_AUTOPICK_CHARS


def _definition_supported(candidate: Candidate, source_definition: Optional[str]) -> bool:
    return bool(source_definition) and definition_overlap(candidate.definition, source_definition) >= MIN_SCORE


def disambiguate(
    candidates: List[Candidate],
    source_definition: Optional[str] = None,
    context_terms: Optional[Iterable[str]] = None,
) -> Optional[Candidate]:
    """Pick the single right candidate, or ``None`` when ambiguous.

    ``context_terms`` are free-form context strings (package name, model
    name, domain hints); they are tokenised and matched against candidate
    domains.
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        only = candidates[0]
        if _autopick_allowed(only) or _definition_supported(only, source_definition):
            return only
        return None

    pool = candidates
    context_tokens: Set[str] = set()
    for term in context_terms or ():
        context_tokens |= _tokens(term)
    if context_tokens:
        domain_matched = [c for c in pool if _domain_matches(c, context_tokens)]
        if len(domain_matched) == 1 and (
            _autopick_allowed(domain_matched[0]) or _definition_supported(domain_matched[0], source_definition)
        ):
            return domain_matched[0]
        if domain_matched:
            pool = domain_matched  # narrowed, definition decides below

    if not source_definition:
        return None

    scored = sorted(
        ((definition_overlap(c.definition, source_definition), c) for c in pool),
        key=lambda pair: (-pair[0], pair[1].priority, pair[1].uri),
    )
    best_score, best = scored[0]
    runner_up_score = scored[1][0] if len(scored) > 1 else 0.0
    if best_score >= MIN_SCORE and best_score - runner_up_score >= MIN_MARGIN:
        return best
    return None
