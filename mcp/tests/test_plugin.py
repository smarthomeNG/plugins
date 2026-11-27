import asyncio
import logging
import os
import unittest
from collections.abc import Iterator
from contextlib import contextmanager

import anyio
import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.subscriptions import ResourceUpdated
from mcp_types import TextContent

from plugins.mcp import Mcp
from tests.mock.core import MockSmartHome

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'access_items.yaml')
TOKEN = 'plugin-test-token-0123456789'

PARAMETERS = {
    'bind_address': '127.0.0.1',
    'port': 0,
    'token': TOKEN,
    'default_access': 'none',
    'inherit_rw_access': False,
    'expose': [],
    'write_rate_limit': 30,
    'max_page_size': 200,
    'wait_max_seconds': 30,
    'log_redact': [],
    'clients': {},
    'tls_certfile': '',
    'tls_keyfile': '',
    'allowed_hosts': [],
    'allowed_origins': [],
    'auth_failure_limit': 20,
    'history_plugin': '',
    'history_max_days': 7,
}


def make_plugin(vardir=None, **overrides):
    sh = MockSmartHome()
    sh.with_items_from(FIXTURE)
    if vardir is not None:
        sh.get_vardir = lambda: str(vardir)
    Mcp._parameters = {**PARAMETERS, **overrides}
    return Mcp(sh)


class _MessageCollector(logging.Handler):
    """Keep the message of every record it handles."""

    def __init__(self, level: int) -> None:
        super().__init__(level)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@contextmanager
def warnings_of(logger: logging.Logger) -> Iterator[list[str]]:
    """Collect the messages of WARNING or higher that *logger* emits inside the block; none is fine."""
    collector = _MessageCollector(logging.WARNING)
    level = logger.level
    logger.setLevel(logging.WARNING)
    logger.addHandler(collector)
    try:
        yield collector.messages
    finally:
        logger.removeHandler(collector)
        logger.setLevel(level)


@pytest.fixture
def plugin():
    plugin = make_plugin()
    yield plugin
    plugin.stop()


def call_tool(plugin, tool, arguments, token=TOKEN):
    async def run():
        url = f'http://127.0.0.1:{plugin.port}/mcp'
        async with httpx2.AsyncClient(headers={'Authorization': f'Bearer {token}'}) as http_client:
            async with Client(streamable_http_client(url, http_client=http_client)) as client:
                return await client.call_tool(tool, arguments)

    return asyncio.run(run())


def list_item_paths(plugin):
    return call_tool(plugin, 'list_items', {}).structured_content


def test_running_plugin_serves_the_items_it_may_expose(plugin):
    plugin.run()
    content = list_item_paths(plugin)
    assert content is not None
    paths = [entry['path'] for entry in content['items']]
    assert 'house' in paths
    assert 'unmarked' not in paths


def test_default_access_ro_exposes_unmarked_items():
    plugin = make_plugin(default_access='ro')
    try:
        plugin.run()
        content = list_item_paths(plugin)
        assert content is not None
        assert 'unmarked' in [entry['path'] for entry in content['items']]
    finally:
        plugin.stop()


def test_plugin_without_token_does_not_initialize():
    assert make_plugin(token='')._init_complete is False


def test_invalid_default_access_does_not_initialize():
    assert make_plugin(default_access='rw')._init_complete is False


def test_inherit_rw_access_warns_on_every_run():
    plugin = make_plugin(inherit_rw_access=True)
    with unittest.TestCase().assertLogs(plugin.logger, level='WARNING') as logs:
        plugin.run()
        plugin.stop()
        plugin.run()
    plugin.stop()
    assert sum('inherit_rw_access' in message for message in logs.output) == 2


def test_non_loopback_bind_warns():
    plugin = make_plugin(bind_address='0.0.0.0')
    with unittest.TestCase().assertLogs(plugin.logger, level='WARNING') as logs:
        plugin.run()
    plugin.stop()
    assert any('0.0.0.0' in message for message in logs.output)


def test_rw_item_can_be_written_through_the_running_plugin(plugin):
    plugin.run()
    result = call_tool(plugin, 'set_item', {'path': 'house.living.lamp', 'value': True})
    assert not result.is_error
    assert result.structured_content == {'previous': False, 'value': True, 'changed': True}


def test_wait_for_change_is_capped_by_the_plugin_parameter():
    plugin = make_plugin(wait_max_seconds=0.1)
    try:
        plugin.run()
        result = call_tool(plugin, 'wait_for_change', {'path': 'house.living.lamp', 'timeout': 600})
        assert result.structured_content is not None
        assert result.structured_content['timed_out'] is True
    finally:
        plugin.stop()


def test_exposed_diagnostics_are_served_through_the_running_plugin():
    plugin = make_plugin(expose=['plugins', 'system'])
    try:
        plugin.run()
        system = call_tool(plugin, 'get_system_info', {}).structured_content
        plugins = call_tool(plugin, 'list_plugins', {}).structured_content
    finally:
        plugin.stop()
    assert system is not None and plugins is not None
    assert system['version'] == plugin._smarthome.version
    assert 'wol' in [entry['config_name'] for entry in plugins['plugins']]


def test_diagnostics_that_are_not_exposed_are_refused_through_the_running_plugin(plugin):
    plugin.run()
    result = call_tool(plugin, 'list_logics', {})
    assert result.is_error
    block = result.content[0]
    assert isinstance(block, TextContent)
    assert '"not_exposed"' in block.text


def test_exposed_logs_are_read_from_the_var_directory_with_configured_redaction(tmp_path):
    (tmp_path / 'log').mkdir()
    (tmp_path / 'log' / 'shng.log').write_text('2026-11-10 10:00:00 INFO     x   serial SN-12345 seen\n')
    plugin = make_plugin(vardir=tmp_path, expose=['logs'], log_redact=[r'SN-\d+'])
    try:
        plugin.run()
        files = call_tool(plugin, 'get_access_info', {}).structured_content
        page = call_tool(plugin, 'get_logs', {'file': 'shng.log'}).structured_content
    finally:
        plugin.stop()
    assert files is not None and page is not None
    assert files['log_files'] == ['shng.log']
    assert [entry['message'] for entry in page['entries']] == ['serial *** seen']


def test_an_invalid_log_redact_pattern_stops_the_plugin_from_starting():
    plugin = make_plugin(log_redact=['('])
    assert plugin._init_complete is False


def test_a_configured_client_is_served_with_its_own_access():
    client_token = 'second-client-token-0123456789'
    plugin = make_plugin(clients={'desktop': {'token': client_token, 'default_access': 'ro', 'expose': ['system']}})
    try:
        plugin.run()
        info = call_tool(plugin, 'get_access_info', {}, token=client_token).structured_content
        assert info is not None
        assert (info['token_id'], info['default_access'], info['max_access'], info['expose']) == (
            'desktop',
            'ro',
            'ro',
            ['system'],
        )
        local = call_tool(plugin, 'get_access_info', {}).structured_content
        assert local is not None
        assert local['token_id'] == 'local'
    finally:
        plugin.stop()


@pytest.mark.parametrize(
    'clients', [{'desktop': {'token': 'short'}}, {'desktop': {'token': TOKEN}}, {'local': {'token': 'x' * 20}}]
)
def test_an_invalid_client_definition_stops_the_plugin_from_starting(clients):
    assert make_plugin(clients=clients)._init_complete is False


def test_a_network_bind_warns_about_missing_tls_and_allowed_hosts():
    plugin = make_plugin(bind_address='0.0.0.0')
    with unittest.TestCase().assertLogs(plugin.logger, level='WARNING') as logs:
        plugin.run()
    plugin.stop()
    text = ' '.join(logs.output)
    assert 'no TLS configured' in text
    assert 'allowed_hosts is empty' in text


def test_a_loopback_bind_does_not_warn_about_tls():
    plugin = make_plugin()
    try:
        with warnings_of(plugin.logger) as warnings:
            plugin.run()
    finally:
        plugin.stop()
    text = ' '.join(warnings)
    assert 'TLS' not in text
    assert 'allowed_hosts' not in text


def test_configured_allowed_hosts_are_applied_by_the_running_plugin():
    plugin = make_plugin(allowed_hosts=['shng.example:*'])
    try:
        plugin.run()
        headers = {'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/json, text/event-stream'}
        url = f'http://127.0.0.1:{plugin.port}/mcp'
        ping = {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}
        assert httpx2.post(url, json=ping, headers={**headers, 'Host': 'shng.example:8765'}).status_code == 200
        assert httpx2.post(url, json=ping, headers={**headers, 'Host': 'evil.example:8765'}).status_code == 421
    finally:
        plugin.stop()


@pytest.mark.parametrize(
    'settings',
    [
        {'tls_certfile': '/nonexistent/cert.pem'},
        {'tls_certfile': '/nonexistent/c.pem', 'tls_keyfile': '/nonexistent/k.pem'},
    ],
)
def test_incomplete_or_unreadable_tls_files_stop_the_plugin_from_starting(settings):
    assert make_plugin(**settings)._init_complete is False


def test_a_change_of_a_bound_item_reaches_a_listening_client():
    plugin = make_plugin()
    try:
        plugin.run()
        lamp = plugin._smarthome.items.return_item('house.living.lamp')
        for item in plugin._smarthome.items.return_items():
            update = plugin.parse_item(item)
            if update:
                item.add_method_trigger(update)

        async def listen():
            headers = {'Authorization': f'Bearer {TOKEN}'}
            async with httpx2.AsyncClient(headers=headers, timeout=30) as http_client:
                url = f'http://127.0.0.1:{plugin.port}/mcp'
                async with Client(streamable_http_client(url, http_client=http_client)) as client:
                    async with client.listen(resource_subscriptions=['shng://item/house.living.lamp']) as subscription:
                        await asyncio.to_thread(lambda: lamp(True))
                        with anyio.fail_after(5):
                            async for event in subscription:
                                if isinstance(event, ResourceUpdated):
                                    return event.uri

        assert asyncio.run(listen()) == 'shng://item/house.living.lamp'
    finally:
        plugin.stop()
