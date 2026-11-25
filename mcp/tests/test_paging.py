import pytest

from plugins.mcp.paging import paginate
from plugins.mcp.types import ToolFailure

NAMES = ['delta', 'alpha', 'charlie', 'bravo', 'echo']


def pages(limit, **kwargs):
    collected = []
    cursor = None
    while True:
        page, cursor = paginate(NAMES, key=str, limit=limit, cursor=cursor, **kwargs)
        collected.append(page)
        if cursor is None:
            return collected


def test_entries_are_ordered_by_key_and_split_into_pages():
    assert pages(2, default=50, maximum=200) == [['alpha', 'bravo'], ['charlie', 'delta'], ['echo']]


def test_the_last_page_has_no_cursor():
    page, cursor = paginate(NAMES, key=str, limit=5, cursor=None, default=50, maximum=200)
    assert page == ['alpha', 'bravo', 'charlie', 'delta', 'echo']
    assert cursor is None


def test_default_and_maximum_page_size_apply():
    assert len(paginate(NAMES, key=str, limit=None, cursor=None, default=3, maximum=200)[0]) == 3
    assert len(paginate(NAMES, key=str, limit=50, cursor=None, default=3, maximum=2)[0]) == 2


def test_invalid_cursor_and_limit_are_rejected():
    with pytest.raises(ToolFailure):
        paginate(NAMES, key=str, limit=None, cursor='!!', default=3, maximum=5)
    with pytest.raises(ToolFailure):
        paginate(NAMES, key=str, limit=0, cursor=None, default=3, maximum=5)
