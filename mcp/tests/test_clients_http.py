import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp_types import TextContent

from plugins.mcp.clients import ClientRegistry
from plugins.mcp.logs import LogReader
from plugins.mcp.server import create_mcp_server
from plugins.mcp.transport import McpHttpServer
from plugins.mcp.types import Entitlement
from tests.mock.core import MockSmartHome

from .support import StaticSource

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'access_items.yaml')
LOCAL_TOKEN = 'local-token-0123456789'
DESKTOP_TOKEN = 'desktop-token-0123456789'
LIMITED_TOKEN = 'limited-token-0123456789'
LOCAL = Entitlement('local', 'none', False, frozenset({'system'}), 1)
DESKTOP = {
    'token': DESKTOP_TOKEN,
    'default_access': 'ro',
    'expose': ['logs'],
    'max_access': 'rw',
    'write_rate_limit': 1,
}


@pytest.fixture
def server():
    sh = MockSmartHome()
    sh.with_items_from(FIXTURE)
    assert sh.items is not None
    registry = ClientRegistry.build(
        LOCAL_TOKEN,
        LOCAL,
        {
            'desktop': DESKTOP,
            'limited': {
                'token': LIMITED_TOKEN,
                'max_access': 'rw',
                'default_access': 'ro',
                'write_paths': ['house.garage'],
            },
        },
    )
    mcp_server = create_mcp_server(sh.items, registry, StaticSource(), LogReader('/nonexistent'))
    http = McpHttpServer(mcp_server, registry, '127.0.0.1', 0)
    http.start()
    yield http
    http.stop()


def call(server, token, tool, arguments=None):
    async def run():
        headers = {'Authorization': f'Bearer {token}'}
        async with httpx2.AsyncClient(headers=headers) as http_client:
            url = f'http://127.0.0.1:{server.port}/mcp'
            async with Client(streamable_http_client(url, http_client=http_client)) as client:
                return await client.call_tool(tool, arguments or {})

    return asyncio.run(run())


def payload(result):
    block = result.content[0]
    assert isinstance(block, TextContent)
    return json.loads(block.text.split(': ', 1)[1] if result.is_error else block.text)


def test_each_token_gets_the_access_of_its_own_client(server):
    local = payload(call(server, LOCAL_TOKEN, 'get_access_info'))
    desktop = payload(call(server, DESKTOP_TOKEN, 'get_access_info'))
    assert (local['token_id'], local['expose'], local['default_access']) == ('local', ['system'], 'none')
    assert (desktop['token_id'], desktop['expose'], desktop['default_access']) == ('desktop', ['logs'], 'ro')


def test_a_client_sees_items_by_its_own_default_access(server):
    local = payload(call(server, LOCAL_TOKEN, 'get_item', {'path': 'unmarked'}))
    desktop = payload(call(server, DESKTOP_TOKEN, 'get_item', {'path': 'unmarked'}))
    assert local['code'] == 'not_found'
    assert desktop['access'] == 'ro'


def test_an_unknown_token_is_unauthorized(server):
    url = f'http://127.0.0.1:{server.port}/mcp'
    assert httpx2.post(url, json={}, headers={'Authorization': 'Bearer nope'}).status_code == 401


def test_concurrent_calls_of_different_clients_keep_their_identity(server):
    tokens = [LOCAL_TOKEN, DESKTOP_TOKEN] * 10
    with ThreadPoolExecutor(8) as pool:
        ids = list(pool.map(lambda token: payload(call(server, token, 'get_access_info'))['token_id'], tokens))
    assert ids == ['local', 'desktop'] * 10


def test_every_client_has_its_own_write_budget(server):
    write = {'path': 'house.living.lamp', 'value': True}
    assert 'code' not in payload(call(server, LOCAL_TOKEN, 'set_item', write))
    assert payload(call(server, LOCAL_TOKEN, 'set_item', write))['code'] == 'rate_limited'
    assert 'code' not in payload(call(server, DESKTOP_TOKEN, 'set_item', write))


def test_write_paths_confine_the_writes_of_a_client(server):
    inside = payload(call(server, LIMITED_TOKEN, 'set_item', {'path': 'house.garage', 'value': True}))
    outside = payload(call(server, LIMITED_TOKEN, 'set_item', {'path': 'house.living.lamp', 'value': True}))
    assert 'code' not in inside
    assert outside == {'code': 'forbidden', 'message': 'item is not writable (access: ro)'}
