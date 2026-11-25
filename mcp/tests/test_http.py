import asyncio
import logging
import os
import threading
import time

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from plugins.mcp.clients import ClientRegistry
from plugins.mcp.transport import GRACEFUL_SHUTDOWN_TIMEOUT, McpHttpServer
from plugins.mcp.logs import LogReader
from plugins.mcp.server import create_mcp_server
from plugins.mcp.types import Entitlement
from tests.mock.core import MockSmartHome

from .support import StaticSource

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'access_items.yaml')
TOKEN = 'test-token-0123456789'


@pytest.fixture
def http_server():
    sh = MockSmartHome()
    sh.with_items_from(FIXTURE)
    assert sh.items is not None
    registry = ClientRegistry.build(TOKEN, Entitlement('local', 'none', False, frozenset(), 30), {})
    mcp_server = create_mcp_server(sh.items, registry, StaticSource(), LogReader('/nonexistent'))
    server = McpHttpServer(mcp_server, registry, '127.0.0.1', 0)
    server.start()
    yield server
    server.stop()


def url_of(server):
    return f'http://127.0.0.1:{server.port}/mcp'


def test_request_without_token_is_unauthorized(http_server):
    assert httpx2.post(url_of(http_server), json={}).status_code == 401


def test_request_with_wrong_token_is_unauthorized(http_server):
    assert httpx2.post(url_of(http_server), json={}, headers={'Authorization': 'Bearer nope'}).status_code == 401


def test_client_with_token_can_list_tools(http_server):
    async def run():
        async with httpx2.AsyncClient(headers={'Authorization': f'Bearer {TOKEN}'}) as http_client:
            async with Client(streamable_http_client(url_of(http_server), http_client=http_client)) as client:
                return {tool.name for tool in (await client.list_tools()).tools}

    assert 'get_item' in asyncio.run(run())


def test_server_can_be_stopped_and_started_again(http_server):
    stopped_url = url_of(http_server)
    http_server.stop()
    with pytest.raises(httpx2.ConnectError):
        httpx2.post(stopped_url, json={}, timeout=2)
    http_server.start()
    assert httpx2.post(url_of(http_server), json={}).status_code == 401


def hold_open(server, request, release, connected):
    """Run in a thread: issue ``request`` against the server and keep its response open until ``release`` is set."""

    async def run():
        headers = {'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/json, text/event-stream'}
        async with httpx2.AsyncClient(headers=headers, timeout=60) as http_client:
            async with request(http_client, url_of(server)) as response:
                connected.set()
                async for _ in response.aiter_bytes():
                    if release.is_set():
                        break

    try:
        asyncio.run(run())
    except httpx2.HTTPError:
        pass  # the server cutting the request off when it stops is the expected end


def open_event_stream(http_client, url):
    return http_client.stream('GET', url)


def start_tool_call(http_client, url):
    body = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'tools/call',
        'params': {'name': 'wait_for_change', 'arguments': {'path': 'house.living.lamp', 'timeout': 30}},
    }
    return http_client.stream('POST', url, json=body)


@pytest.mark.parametrize('request_kind', [open_event_stream, start_tool_call], ids=['event-stream', 'running-call'])
def test_server_stops_quickly_and_quietly_while_a_client_request_is_still_open(
    http_server, monkeypatch, request_kind, capfd, caplog
):
    monkeypatch.setattr('plugins.mcp.transport.SHUTDOWN_TIMEOUT', 5.0)
    connected, release = threading.Event(), threading.Event()
    client = threading.Thread(target=hold_open, args=(http_server, request_kind, release, connected), daemon=True)
    client.start()
    try:
        assert connected.wait(10)
        started = time.monotonic()
        with caplog.at_level(logging.WARNING):
            http_server.stop()
        elapsed = time.monotonic() - started
    finally:
        release.set()
        client.join(10)
    assert elapsed < GRACEFUL_SHUTDOWN_TIMEOUT
    assert capfd.readouterr().err == ''
    assert [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR] == []
