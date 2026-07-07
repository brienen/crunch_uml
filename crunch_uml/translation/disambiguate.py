"""Deterministic disambiguation of termbank candidates — no model involved.

Given the candidates for a source term, pick the right one using context
crunch already has: the domain(s) the element lives in (package/model names)
and, decisively, the source definition. The rules, in order:

1. no candidates → nothing to choose;
2. exactly one candidate → take it;
3. domain filter: candidates whose domains overlap the context narrow the
   set; a unique survivor wins;
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
        return candidates[0]

    pool = candidates
    context_tokens: Set[str] = set()
    for term in context_terms or ():
        context_tokens |= _tokens(term)
    if context_tokens:
        domain_matched = [c for c in pool if _domain_matches(c, context_tokens)]
        if len(domain_matched) == 1:
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
