#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for plugins/matter/rpc.py through both concrete clients
(MatterServerClient, MatterBridgeClient), against a real in-process
WebSocket peer.
"""

import asyncio
import time
import unittest

from plugins.matter.bridge.client import BridgeCommandError, MatterBridgeClient
from plugins.matter.rpc import TRANSIENT_ERRORS, describe_error
from plugins.matter.server.client import MatterCommandError, MatterServerClient
from plugins.matter.tests.support import WsPeer

SERVER_INFO = {'fabric_id': 1, 'thread_credentials_set': False}


class _Logger:
    def __init__(self):
        self.warnings = []
        self.exceptions = []

    def warning(self, msg, *args, **kwargs):
        self.warnings.append(msg)

    def exception(self, msg, *args, **kwargs):
        self.exceptions.append(msg)

    def debug(self, msg, *args, **kwargs):
        pass


class _ClientTest(unittest.IsolatedAsyncioTestCase):
    """Starts a WsPeer per test; subclasses pick the client flavor."""

    id_field = 'message_id'
    greeting = SERVER_INFO

    def respond(self, request):
        return {'result': {'echo': request['args']}}

    def setUp(self):
        self.peer = WsPeer(self.id_field, responder=lambda request: self.respond(request), greeting=self.greeting)
        self.peer.start()
        self.addCleanup(self.peer.stop)
        self.events = []
        self.logger = _Logger()

    def make_client(self):
        return MatterServerClient(self.peer.url + '/ws', on_event=self.events.append, logger=self.logger)

    async def connected_client(self):
        client = self.make_client()
        await client.connect()
        self.addAsyncCleanup(client.close)
        return client


class TestServerClient(_ClientTest):
    async def test_handshake_reads_server_info(self):
        client = await self.connected_client()

        self.assertEqual(client.server_info, SERVER_INFO)
        self.assertTrue(client.connected)

    async def test_command_round_trip(self):
        client = await self.connected_client()

        result = await client.send_command('get_nodes', {'only_available': False})

        self.assertEqual(result, {'echo': {'only_available': False}})

    async def test_error_code_raises_matter_command_error(self):
        self.respond = lambda request: {'error_code': 5, 'details': 'nope'}
        client = await self.connected_client()

        with self.assertRaises(MatterCommandError) as caught:
            await client.get_nodes()

        self.assertEqual(caught.exception.error_code, 5)
        self.assertIsInstance(caught.exception, TRANSIENT_ERRORS)

    async def test_unsolicited_event_reaches_on_event(self):
        client = await self.connected_client()
        event = {'event': 'attribute_updated', 'data': [1, '1/6/0', True]}

        await asyncio.to_thread(self.peer.push, event)
        await asyncio.sleep(0.1)

        self.assertEqual(self.events, [event])
        self.assertTrue(client.connected)

    async def test_late_answer_after_timeout_is_logged_not_treated_as_event(self):
        async def slow(request):
            await asyncio.sleep(0.3)
            return {'result': 'late'}

        self.respond = slow
        client = await self.connected_client()

        with self.assertRaises(asyncio.TimeoutError):
            await client.send_command('get_nodes', {}, timeout=0.05)
        await asyncio.sleep(0.5)

        self.assertEqual(self.events, [])
        self.assertTrue(any('late answer' in message for message in self.logger.warnings))

    async def test_pending_request_fails_fast_when_the_connection_drops(self):
        self.respond = lambda request: None
        client = await self.connected_client()

        started = time.monotonic()
        request = asyncio.create_task(client.send_command('get_nodes', {}, timeout=10))
        await asyncio.sleep(0.1)
        await asyncio.to_thread(self.peer.drop_connections)

        with self.assertRaises(ConnectionError):
            await request
        self.assertLess(time.monotonic() - started, 5)
        await asyncio.wait_for(client.closed.wait(), 5)
        self.assertFalse(client.connected)

    async def test_send_after_disconnect_raises_connection_error(self):
        client = await self.connected_client()
        await asyncio.to_thread(self.peer.drop_connections)
        await asyncio.wait_for(client.closed.wait(), 5)

        with self.assertRaises(ConnectionError):
            await client.get_nodes()

    async def test_close_fails_pending_requests_with_connection_error(self):
        self.respond = lambda request: None
        client = await self.connected_client()
        request = asyncio.create_task(client.send_command('get_nodes', {}, timeout=10))
        await asyncio.sleep(0.1)

        await client.close()

        with self.assertRaises(ConnectionError):
            await request
        self.assertTrue(client.closed.is_set())


class TestBridgeClient(_ClientTest):
    id_field = 'id'
    greeting = None

    def make_client(self):
        return MatterBridgeClient(self.peer.url, on_event=self.events.append, logger=self.logger)

    async def test_add_endpoint_returns_endpoint_id(self):
        self.respond = lambda request: {'result': {'endpoint_id': 7}}
        client = await self.connected_client()

        self.assertEqual(await client.add_endpoint('a.b', 'switch', 'a.b'), 7)
        self.assertEqual(
            self.peer.commands('add_endpoint')[0]['args'], {'item_path': 'a.b', 'expose_type': 'switch', 'name': 'a.b'}
        )

    async def test_error_field_raises_bridge_command_error(self):
        self.respond = lambda request: {'error': 'no endpoint 9'}
        client = await self.connected_client()

        with self.assertRaises(BridgeCommandError) as caught:
            await client.remove_endpoint(9)

        self.assertIn('no endpoint 9', str(caught.exception))


class TestDescribeError(unittest.TestCase):
    def test_timeouts_get_a_message(self):
        self.assertIn('timed out', describe_error(asyncio.TimeoutError()))
        self.assertIn('timed out', describe_error(TimeoutError()))

    def test_other_errors_stringify(self):
        self.assertEqual(describe_error(ConnectionError('gone')), 'gone')


if __name__ == '__main__':
    unittest.main()
