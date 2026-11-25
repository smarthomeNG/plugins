import asyncio
import json
import os

import anyio
import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from mcp.shared.subscriptions import ResourceUpdated
from mcp_types import TextResourceContents

from plugins.mcp.clients import ClientRegistry
from plugins.mcp.events import ItemEvents
from plugins.mcp.logs import LogReader
from plugins.mcp.server import create_mcp_server
from plugins.mcp.transport import McpHttpServer
from plugins.mcp.types import Entitlement
from tests.mock.core import MockSmartHome

from .support import StaticSource

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'access_items.yaml')
LOCAL_TOKEN = 'local-token-0123456789'
DESKTOP_TOKEN = 'desktop-token-0123456789'
LOCAL = Entitlement('local', 'ro', False, frozenset(), 30)
LAMP = 'shng://item/house.living.lamp'
UNMARKED = 'shng://item/unmarked'
ALARM = 'shng://item/house.alarm'
QUIET_SECONDS = 0.8


@pytest.fixture
def items():
    sh = MockSmartHome()
    sh.with_items_from(FIXTURE)
    assert sh.items is not None
    return sh.items


@pytest.fixture
def server(items):
    registry = ClientRegistry.build(LOCAL_TOKEN, LOCAL, {'desktop': {'token': DESKTOP_TOKEN}})
    events = ItemEvents(items, registry, coalesce_seconds=0.1)
    for item in items.return_items():
        item.add_method_trigger(lambda changed, caller, source, dest: events.item_changed(changed.property.path))
    mcp_server = create_mcp_server(items, registry, StaticSource(), LogReader('/nonexistent'), subscriptions=events)
    http = McpHttpServer(mcp_server, registry, '127.0.0.1', 0)
    http.start()
    yield http
    http.stop()


def watch(server, uris, act, token=LOCAL_TOKEN, wait=QUIET_SECONDS):
    """Listen to the URIs, run ``act`` once the stream is acknowledged, and return the uris of the events that arrive."""

    async def run():
        headers = {'Authorization': f'Bearer {token}'}
        async with httpx2.AsyncClient(headers=headers, timeout=30) as http_client:
            url = f'http://127.0.0.1:{server.port}/mcp'
            async with Client(streamable_http_client(url, http_client=http_client)) as client:
                async with client.listen(resource_subscriptions=uris) as subscription:
                    await anyio.to_thread.run_sync(act)
                    seen: list[str] = []
                    with anyio.move_on_after(wait):
                        async for event in subscription:
                            if isinstance(event, ResourceUpdated):
                                seen.append(event.uri)
                    return seen

    return asyncio.run(run())


class TestEvents:
    def test_a_change_of_a_subscribed_item_is_announced(self, server, items):
        lamp = items.return_item('house.living.lamp')
        assert watch(server, [LAMP], lambda: lamp(True)) == [LAMP]

    def test_a_change_of_another_item_is_not(self, server, items):
        garage = items.return_item('house.garage.door')
        assert watch(server, [LAMP], lambda: garage(True)) == []

    def test_an_update_that_keeps_the_value_is_not_a_change(self, server, items):
        lamp = items.return_item('house.living.lamp')
        assert watch(server, [LAMP], lambda: lamp(False)) == []

    def test_a_burst_of_changes_is_announced_once(self, server, items):
        lamp = items.return_item('house.living.lamp')

        def flip():
            for value in (True, False, True, False, True):
                lamp(value)

        assert watch(server, [LAMP], flip) == [LAMP]

    def test_every_listener_gets_the_event(self, server, items):
        lamp = items.return_item('house.living.lamp')
        assert watch(server, [LAMP], lambda: lamp(True), token=DESKTOP_TOKEN) == [LAMP]


class TestVisibility:
    def test_a_client_is_not_told_about_items_it_cannot_see(self, server, items):
        alarm = items.return_item('house.alarm')
        alarm_door = items.return_item('house.alarm.siren')
        assert watch(server, [ALARM], lambda: alarm_door(True)) == []
        assert watch(server, [ALARM], lambda: alarm(True)) == []

    def test_a_client_is_told_only_about_what_its_own_access_shows(self, server, items):
        unmarked = items.return_item('unmarked')
        assert watch(server, [UNMARKED], lambda: unmarked(1), token=LOCAL_TOKEN) == [UNMARKED]
        assert watch(server, [UNMARKED], lambda: unmarked(2), token=DESKTOP_TOKEN) == []


def read(server, uri, token=LOCAL_TOKEN):
    async def run():
        headers = {'Authorization': f'Bearer {token}'}
        async with httpx2.AsyncClient(headers=headers) as http_client:
            url = f'http://127.0.0.1:{server.port}/mcp'
            async with Client(streamable_http_client(url, http_client=http_client)) as client:
                try:
                    return await client.read_resource(uri)
                except MCPError as error:
                    return error

    return asyncio.run(run())


class TestResource:
    def test_an_item_is_read_as_a_resource(self, server):
        result = read(server, LAMP)
        assert not isinstance(result, MCPError)
        content = result.contents[0]
        assert isinstance(content, TextResourceContents)
        assert json.loads(content.text)['path'] == 'house.living.lamp'

    def test_an_invisible_item_cannot_be_read(self, server):
        result = read(server, ALARM)
        assert isinstance(result, MCPError)
        assert 'not_found' in str(result)
