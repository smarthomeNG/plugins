"""
Media search query grammar and ranking. Pure functions, no I/O.

Grammar of the raw query string:
- bare words are separate terms; all of them must be contained in the title
- a double-quoted run is one term, matched as contiguous text
- an unterminated quote takes the rest of the string as one term
- the exact lowercase first token ``album:`` / ``title:`` restricts the search to
  albums / tracks; anywhere else, or in any other spelling, it is a literal term

Matching is case-insensitive (casefold).
"""

from enum import StrEnum
from typing import NamedTuple


class SearchTarget(StrEnum):
    """What a query looks for"""

    ANY = 'any'
    ALBUM = 'album'
    TRACK = 'track'


class HitKind(StrEnum):
    """What a search result is"""

    ALBUM = 'album'
    TRACK = 'track'


class SearchQuery(NamedTuple):
    """A parsed query: casefolded terms, all of which must be contained in a title"""

    target: SearchTarget
    terms: tuple[str, ...]

    @property
    def text(self) -> str:
        """the terms joined by single spaces - what an exactly matching title looks like"""
        return ' '.join(self.terms)


class Candidate(NamedTuple):
    """One raw search result; ref is opaque to this module (the media server's object id)"""

    kind: HitKind
    title: str
    album: str
    ref: str


_TARGET_PREFIXES = {'album:': SearchTarget.ALBUM, 'title:': SearchTarget.TRACK}


def _tokenize(raw: str) -> list[str]:
    """split raw into whitespace-separated words and double-quoted phrases"""
    tokens: list[str] = []
    rest = raw
    while True:
        rest = rest.lstrip()
        if not rest:
            return tokens
        if rest[0] == '"':
            phrase, _, rest = rest[1:].partition('"')
            tokens.append(' '.join(phrase.split()))
        else:
            word, _, rest = rest.partition(' ')
            tokens.append(word)


def parse_query(raw: str) -> SearchQuery | None:
    """return the parsed query, or None if raw holds no search term"""
    words = raw.split(None, 1)
    target = _TARGET_PREFIXES.get(words[0]) if words else None
    tokens = _tokenize(words[1] if target and len(words) > 1 else '' if target else raw)
    terms = tuple(token.casefold() for token in tokens if token)
    if not terms:
        return None
    return SearchQuery(target or SearchTarget.ANY, terms)


def rank(query: SearchQuery, candidates: list[Candidate]) -> list[Candidate]:
    """
    return the candidates matching query, best first

    Candidates of the wrong kind or missing a term are dropped (the server's own
    matching is not trusted). Order: exact title equality, then album before
    track, then the server's order.
    """
    wanted = {SearchTarget.ALBUM: HitKind.ALBUM, SearchTarget.TRACK: HitKind.TRACK}.get(query.target)
    matching = [
        candidate
        for candidate in candidates
        if wanted in (None, candidate.kind) and all(term in candidate.title.casefold() for term in query.terms)
    ]
    return sorted(
        matching, key=lambda candidate: (candidate.title.casefold() != query.text, candidate.kind is not HitKind.ALBUM)
    )
