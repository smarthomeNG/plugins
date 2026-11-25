import pytest

from plugins.mcp.tools import DiagnosticsTools
from plugins.mcp.types import Entitlement, ToolFailure

from .support import SCHEDULER, SYSTEM, StaticSource


def tools(expose=(), source=None, **kwargs):
    entitlement = Entitlement('local', 'none', False, frozenset(expose), 30)
    return DiagnosticsTools(source or StaticSource(), entitlement, **kwargs)


CALLS = {
    'plugins': [lambda t: t.list_plugins(), lambda t: t.get_plugin_info('knx')],
    'scheduler': [lambda t: t.list_schedulers()],
    'logics': [lambda t: t.list_logics()],
    'threads': [lambda t: t.get_threads()],
    'system': [lambda t: t.get_system_info()],
}
ALL_CALLS = [(group, call) for group, calls in CALLS.items() for call in calls]


@pytest.mark.parametrize(('group', 'call'), ALL_CALLS)
def test_a_group_that_is_not_exposed_is_refused(group, call):
    with pytest.raises(ToolFailure) as failure:
        call(tools(expose=()))
    assert failure.value.code == 'not_exposed'
    assert group in failure.value.message


@pytest.mark.parametrize(('group', 'call'), ALL_CALLS)
def test_an_exposed_group_is_served(group, call):
    assert call(tools(expose=[group])) is not None


def test_exposing_one_group_does_not_expose_another():
    with pytest.raises(ToolFailure) as failure:
        tools(expose=['system']).list_logics()
    assert failure.value.code == 'not_exposed'


def test_system_info_and_scheduler_pass_through():
    assert tools(expose=['system']).get_system_info() == SYSTEM
    assert tools(expose=['scheduler']).list_schedulers() == SCHEDULER


def test_unknown_plugin_is_not_found():
    with pytest.raises(ToolFailure) as failure:
        tools(expose=['plugins']).get_plugin_info('nope')
    assert failure.value.code == 'not_found'


def test_lists_are_paged():
    diagnostics = tools(expose=['plugins'], source=StaticSource(plugin_count=5), default_page_size=2, max_page_size=3)
    first = diagnostics.list_plugins()
    assert [entry['config_name'] for entry in first['plugins']] == ['plugin000', 'plugin001']
    second = diagnostics.list_plugins(cursor=first['cursor'])
    assert [entry['config_name'] for entry in second['plugins']] == ['plugin002', 'plugin003']
    last = diagnostics.list_plugins(limit=50, cursor=second['cursor'])
    assert [entry['config_name'] for entry in last['plugins']] == ['plugin004']
    assert last['cursor'] is None
