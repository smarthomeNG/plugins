import asyncio
import os

import pytest

from plugins.mcp.tools import ItemTools
from plugins.mcp.types import Entitlement, ToolFailure
from tests.mock.core import MockSmartHome

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'write_items.yaml')


def make_tools(**kwargs):
    sh = MockSmartHome()
    sh.with_items_from(FIXTURE)
    assert sh.items is not None
    tools = ItemTools(sh.items, Entitlement('local', 'none', False, frozenset(), 0), poll_interval=0.01, **kwargs)
    return tools, sh.items


def write_later(items, path, value, delay):
    async def write():
        await asyncio.sleep(delay)
        item = items.return_item(path)
        assert item is not None
        item(value, caller='test')

    return asyncio.ensure_future(write())


class TestWaitForChange:
    def test_returns_the_new_value_once_the_item_changes(self):
        async def run():
            tools, items = make_tools()
            writer = write_later(items, 'rwnum', 5, 0.05)
            result = await tools.wait_for_change('rwnum', 2)
            await writer
            return result

        assert asyncio.run(run()) == {'changed': True, 'value': 5, 'previous': 1, 'timed_out': False}

    def test_times_out_without_a_change(self):
        async def run():
            tools, _ = make_tools()
            return await tools.wait_for_change('rwnum', 0.05)

        assert asyncio.run(run()) == {'changed': False, 'value': 1, 'previous': 1, 'timed_out': True}

    def test_an_update_to_the_same_value_is_not_a_change(self):
        async def run():
            tools, items = make_tools()
            writer = write_later(items, 'rwnum', 1, 0.02)
            result = await tools.wait_for_change('rwnum', 0.1)
            await writer
            return result

        assert asyncio.run(run())['changed'] is False

    def test_invisible_item_is_not_found(self):
        async def run():
            tools, _ = make_tools()
            await tools.wait_for_change('unmarked', 1)

        with pytest.raises(ToolFailure) as failure:
            asyncio.run(run())
        assert failure.value.code == 'not_found'

    @pytest.mark.parametrize('timeout', [0, -1])
    def test_non_positive_timeout_is_rejected(self, timeout):
        async def run():
            tools, _ = make_tools()
            await tools.wait_for_change('rwnum', timeout)

        with pytest.raises(ToolFailure) as failure:
            asyncio.run(run())
        assert failure.value.code == 'bad_request'

    def test_timeout_is_capped(self):
        async def run():
            tools, _ = make_tools(wait_max_seconds=0.05)
            return await tools.wait_for_change('rwnum', 3600)

        assert asyncio.run(run())['timed_out'] is True
