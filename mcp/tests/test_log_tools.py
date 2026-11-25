import pytest
from tests import common

from plugins.mcp.logs import LogReader
from plugins.mcp.tools import LogTools, get_access_info
from plugins.mcp.types import Entitlement, ToolFailure

common.register_shng_log_levels()

LINES = ''.join(f'2026-11-10 10:00:{i:02d} INFO     x   entry {i}\n' for i in range(10))


def make(tmp_path, expose=('logs',), **kwargs):
    (tmp_path / 'shng.log').write_text(LINES)
    entitlement = Entitlement('local', 'none', False, frozenset(expose), 30)
    reader = LogReader(str(tmp_path))
    return LogTools(reader, entitlement, **kwargs), entitlement, reader


def test_logs_that_are_not_exposed_are_refused(tmp_path):
    tools, _, _ = make(tmp_path, expose=())
    with pytest.raises(ToolFailure) as failure:
        tools.get_logs('shng.log')
    assert failure.value.code == 'not_exposed'


def test_the_default_page_size_applies(tmp_path):
    tools, _, _ = make(tmp_path, default_page_size=3)
    page = tools.get_logs('shng.log')
    assert [e['message'] for e in page['entries']] == ['entry 9', 'entry 8', 'entry 7']
    assert page['cursor'] is not None


def test_the_limit_is_capped_by_the_maximum(tmp_path):
    tools, _, _ = make(tmp_path, default_page_size=3, max_page_size=4)
    assert len(tools.get_logs('shng.log', limit=100)['entries']) == 4


def test_a_non_positive_limit_is_a_bad_request(tmp_path):
    tools, _, _ = make(tmp_path)
    with pytest.raises(ToolFailure) as failure:
        tools.get_logs('shng.log', limit=0)
    assert failure.value.code == 'bad_request'


def test_filters_and_cursor_reach_the_reader(tmp_path):
    tools, _, _ = make(tmp_path, default_page_size=2)
    first = tools.get_logs('shng.log', contains='entry')
    second = tools.get_logs('shng.log', contains='entry', cursor=first['cursor'])
    assert [e['message'] for e in second['entries']] == ['entry 7', 'entry 6']


def test_access_info_lists_log_files_only_when_logs_are_exposed(tmp_path):
    _, entitlement, reader = make(tmp_path)
    assert get_access_info(entitlement, reader)['log_files'] == ['shng.log']
    hidden = Entitlement('local', 'none', False, frozenset(), 30)
    assert get_access_info(hidden, reader)['log_files'] == []
