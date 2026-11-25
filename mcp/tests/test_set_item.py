import os

import pytest

from plugins.mcp.tools import ItemTools
from plugins.mcp.types import Entitlement, ToolFailure
from tests.mock.core import MockSmartHome

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'write_items.yaml')


def item_of(items, path):
    item = items.return_item(path)
    assert item is not None
    return item


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_tools(write_rate_limit=0, clock=None):
    sh = MockSmartHome()
    sh.with_items_from(FIXTURE)
    assert sh.items is not None
    entitlement = Entitlement('local', 'none', False, frozenset(), write_rate_limit)
    kwargs = {'clock': clock} if clock is not None else {}
    return ItemTools(sh.items, entitlement, **kwargs), sh.items


class TestSetItem:
    def test_rw_item_is_written_and_read_back(self):
        tools, items = make_tools()
        result = tools.set_item('rwnum', 5)
        assert result == {'previous': 1, 'value': 5, 'changed': True}
        assert item_of(items, 'rwnum')() == 5

    def test_write_of_the_same_value_reports_no_change(self):
        tools, _ = make_tools()
        assert tools.set_item('rwnum', 1) == {'previous': 1, 'value': 1, 'changed': False}

    def test_write_is_attributed_to_mcp_and_the_token(self):
        tools, items = make_tools()
        tools.set_item('rwnum', 5)
        assert item_of(items, 'rwnum').property.last_change_by == 'mcp:local'

    def test_ro_item_is_forbidden(self):
        tools, items = make_tools()
        with pytest.raises(ToolFailure) as failure:
            tools.set_item('rwnum.child', 1)
        assert failure.value.code == 'forbidden'
        assert item_of(items, 'rwnum.child')() == 7

    def test_invisible_item_is_not_found(self):
        tools, _ = make_tools()
        with pytest.raises(ToolFailure) as failure:
            tools.set_item('unmarked', 1)
        assert failure.value.code == 'not_found'

    def test_null_cannot_be_written(self):
        tools, items = make_tools()
        with pytest.raises(ToolFailure) as failure:
            tools.set_item('rwnum', None)
        assert failure.value.code == 'invalid_value'
        assert item_of(items, 'rwnum')() == 1

    def test_value_of_the_wrong_type_is_rejected_and_nothing_is_written(self):
        tools, items = make_tools()
        with pytest.raises(ToolFailure) as failure:
            tools.set_item('rwnum', 'not a number')
        assert failure.value.code == 'invalid_value'
        assert item_of(items, 'rwnum')() == 1


class TestWriteRateLimit:
    def test_writes_beyond_the_global_limit_are_refused_and_not_applied(self):
        tools, items = make_tools(write_rate_limit=2, clock=FakeClock())
        tools.set_item('rwnum', 2)
        tools.set_item('rwbool', True)
        with pytest.raises(ToolFailure) as failure:
            tools.set_item('rwnum', 3)
        assert failure.value.code == 'rate_limited'
        assert failure.value.retry_after == 60.0
        assert item_of(items, 'rwnum')() == 2

    def test_writes_are_allowed_again_when_the_window_has_passed(self):
        clock = FakeClock()
        tools, _ = make_tools(write_rate_limit=1, clock=clock)
        tools.set_item('rwnum', 2)
        clock.now += 60
        assert tools.set_item('rwnum', 3)['value'] == 3

    def test_a_global_limit_of_zero_disables_limiting(self):
        tools, _ = make_tools(write_rate_limit=0, clock=FakeClock())
        for value in range(50):
            tools.set_item('rwnum', value)

    def test_an_item_limit_applies_to_that_item_regardless_of_the_global_limit(self):
        tools, _ = make_tools(write_rate_limit=30, clock=FakeClock())
        tools.set_item('rwlimited', 1)
        with pytest.raises(ToolFailure) as failure:
            tools.set_item('rwlimited', 2)
        assert failure.value.code == 'rate_limited'

    def test_an_item_limit_of_zero_exempts_the_item_and_spares_the_global_budget(self):
        tools, _ = make_tools(write_rate_limit=1, clock=FakeClock())
        for value in range(10):
            tools.set_item('rwfree', value)
        assert tools.set_item('rwnum', 9)['value'] == 9

    def test_a_refused_type_cast_does_not_use_up_the_budget(self):
        tools, _ = make_tools(write_rate_limit=1, clock=FakeClock())
        with pytest.raises(ToolFailure):
            tools.set_item('rwnum', 'nope')
        assert tools.set_item('rwnum', 9)['value'] == 9
