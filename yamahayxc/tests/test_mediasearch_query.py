"""Media search query grammar and ranking (pure functions, no I/O)."""

from plugins.yamahayxc.mediasearch.query import Candidate, HitKind, SearchTarget, parse_query, rank


def test_bare_words_are_separate_terms_searching_albums_and_tracks():
    query = parse_query('Foo  bar')

    assert query.target is SearchTarget.ANY
    assert query.terms == ('foo', 'bar')


def test_quoted_phrase_is_one_term():
    assert parse_query('"foo bar" baz').terms == ('foo bar', 'baz')


def test_unterminated_quote_takes_the_rest_as_phrase():
    assert parse_query('baz "foo bar').terms == ('baz', 'foo bar')


def test_leading_album_prefix_restricts_target():
    query = parse_query('album: Abbey Road')

    assert query.target is SearchTarget.ALBUM
    assert query.terms == ('abbey', 'road')


def test_leading_title_prefix_restricts_target_to_tracks():
    assert parse_query('title: Yesterday').target is SearchTarget.TRACK


def test_prefix_is_literal_unless_exact_lowercase_and_first():
    assert parse_query('Album: x').target is SearchTarget.ANY
    assert parse_query('x album: y').target is SearchTarget.ANY
    assert parse_query('album:x').terms == ('album:x',)
    assert parse_query('x album: y').terms == ('x', 'album:', 'y')


def test_query_without_terms_is_none():
    assert parse_query('') is None
    assert parse_query('   ') is None
    assert parse_query('album:') is None
    assert parse_query('""') is None


def track(title, album='Some Album', ref=''):
    return Candidate(HitKind.TRACK, title, album, ref)


def album(title, ref=''):
    return Candidate(HitKind.ALBUM, title, title, ref)


def test_rank_drops_candidates_missing_a_term_ignoring_case():
    query = parse_query('love me')

    ranked = rank(query, [track('LOVE ME do'), track('Love Song'), track('Me and Love')])

    assert [c.title for c in ranked] == ['LOVE ME do', 'Me and Love']


def test_rank_phrase_needs_contiguous_text():
    query = parse_query('"me do"')

    assert [c.title for c in rank(query, [track('do me'), track('Love me do')])] == ['Love me do']


def test_rank_exact_title_beats_server_order():
    query = parse_query('help')

    ranked = rank(query, [track('Help Me'), track('HELP')])

    assert [c.title for c in ranked] == ['HELP', 'Help Me']


def test_rank_album_beats_track_on_equal_exactness_then_server_order():
    query = parse_query('help')

    ranked = rank(query, [track('Help B'), track('Help A'), album('Help C')])

    assert [c.title for c in ranked] == ['Help C', 'Help B', 'Help A']


def test_rank_exact_track_beats_partial_album():
    query = parse_query('help')

    ranked = rank(query, [album('Help Me'), track('Help')])

    assert [c.title for c in ranked] == ['Help', 'Help Me']


def test_rank_honours_target():
    candidates = [album('Help'), track('Help')]

    assert [c.kind for c in rank(parse_query('album: help'), candidates)] == [HitKind.ALBUM]
    assert [c.kind for c in rank(parse_query('title: help'), candidates)] == [HitKind.TRACK]
