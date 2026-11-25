import asyncio
import json
import os

from mcp.client.client import Client
from mcp_types import CallToolResult, TextContent

from plugins.mcp.logs import LogReader
from plugins.mcp.server import create_mcp_server
from plugins.mcp.types import Entitlement
from tests.mock.core import MockSmartHome

from .support import StaticSource

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'access_items.yaml')
ENTITLEMENT = Entitlement('local', 'none', False, frozenset(), 30)


def make_server():
    sh = MockSmartHome()
    sh.with_items_from(FIXTURE)
    assert sh.items is not None
    return create_mcp_server(sh.items, ENTITLEMENT, StaticSource(), LogReader('/nonexistent'))


def call(tool, arguments):
    async def run():
        async with Client(make_server()) as client:
            return await client.call_tool(tool, arguments)

    return asyncio.run(run())


def test_lists_the_item_tools():
    async def run():
        async with Client(make_server()) as client:
            return {tool.name for tool in (await client.list_tools()).tools}

    assert asyncio.run(run()) == {
        'get_access_info',
        'list_items',
        'get_item',
        'set_item',
        'wait_for_change',
        'list_plugins',
        'get_plugin_info',
        'list_schedulers',
        'list_logics',
        'get_threads',
        'get_system_info',
        'get_logs',
    }


def test_get_item_returns_the_summary():
    result = call('get_item', {'path': 'house.living.temp'})
    assert not result.is_error
    assert json.loads(text_of(result)) == {'path': 'house.living.temp', 'type': 'num', 'value': 21.5, 'access': 'ro'}


def text_of(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def failure_payload(result: CallToolResult):
    """Parse the JSON the SDK appends after its 'Error executing tool <name>: ' prefix."""
    return json.loads(text_of(result).split(': ', 1)[1])


def test_failure_carries_a_machine_readable_code():
    result = call('get_item', {'path': 'unmarked'})
    assert result.is_error
    assert failure_payload(result) == {'code': 'not_found', 'message': 'item not found'}


WRITE_FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'write_items.yaml')


def make_write_server(write_rate_limit=30):
    sh = MockSmartHome()
    sh.with_items_from(WRITE_FIXTURE)
    assert sh.items is not None
    return create_mcp_server(
        sh.items,
        Entitlement('local', 'none', False, frozenset(), write_rate_limit),
        StaticSource(),
        LogReader('/nonexistent'),
    )


def call_on(server, tool, arguments):
    async def run():
        async with Client(server) as client:
            return await client.call_tool(tool, arguments)

    return asyncio.run(run())


def test_set_item_writes_and_reports_the_read_back():
    result = call_on(make_write_server(), 'set_item', {'path': 'rwnum', 'value': 8})
    assert not result.is_error
    assert json.loads(text_of(result)) == {'previous': 1, 'value': 8, 'changed': True}


def test_set_item_failure_carries_the_retry_time_when_rate_limited():
    server = make_write_server(write_rate_limit=1)
    call_on(server, 'set_item', {'path': 'rwnum', 'value': 2})
    result = call_on(server, 'set_item', {'path': 'rwnum', 'value': 3})
    assert result.is_error
    payload = failure_payload(result)
    assert payload['code'] == 'rate_limited'
    assert 0 < payload['retry_after'] <= 60


def test_wait_for_change_times_out_through_the_protocol():
    result = call_on(make_write_server(), 'wait_for_change', {'path': 'rwnum', 'timeout': 0.1})
    assert not result.is_error
    assert json.loads(text_of(result)) == {'changed': False, 'value': 1, 'previous': 1, 'timed_out': True}


def test_wait_for_change_failure_is_a_tool_error():
    result = call_on(make_write_server(), 'wait_for_change', {'path': 'unmarked', 'timeout': 0.1})
    assert result.is_error
    assert failure_payload(result)['code'] == 'not_found'


def test_a_diagnostic_group_that_is_not_exposed_is_a_tool_error():
    result = call_on(make_write_server(), 'get_system_info', {})
    assert result.is_error
    assert failure_payload(result)['code'] == 'not_exposed'
