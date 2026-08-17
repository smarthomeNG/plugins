#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Unit tests for MatterServerClient's request/response correlation, in
particular the late-response path added after a real incident: a
commission_with_code call took ~3 minutes end to end while send_command()'s
default 30s timeout had already given up on it, and matter-server's real
final answer was silently dropped as "unsolicited" (see
dev/matter/matter-integration-plan.md's matching section). Exercises the
real MatterServerClient/_receive_loop/send_command code (asyncio.run, same
convention as test_bridge.py's TestBridgeErrorHandling), against a small
fake websocket - not a mock of MatterServerClient itself.
"""

import asyncio
import inspect
import json
import unittest

from websockets.exceptions import ConnectionClosedError

from plugins.matter.server.client import MatterServerClient


class _FakeWebSocket:
    """Async-iterable stand-in for a websockets connection - real send()/__anext__ shape, no network."""

    def __init__(self):
        self.sent: list[str] = []
        self._queue: asyncio.Queue = asyncio.Queue()

    async def send(self, raw: str) -> None:
        self.sent.append(raw)

    async def push(self, message: dict) -> None:
        await self._queue.put(json.dumps(message))

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self._queue.get()


def _make_client(on_late_result=None) -> tuple[MatterServerClient, _FakeWebSocket]:
    client = MatterServerClient('ws://unused', on_event=lambda message: None, on_late_result=on_late_result)
    ws = _FakeWebSocket()
    client._ws = ws
    return client, ws


class TestCommissionTimeoutDefault(unittest.TestCase):
    def test_commission_with_code_default_timeout_is_300s_not_send_commands_30s(self):
        # A commission_with_code call was observed taking ~3 minutes end to
        # end - send_command()'s general 30s default is fine for every other command
        # exercised in this plugin, but not this one. See commission_with_code's own
        # docstring for the source citation this value comes from.
        default = inspect.signature(MatterServerClient.commission_with_code).parameters['timeout'].default
        self.assertEqual(default, 300.0)


class TestLateResponseHandling(unittest.TestCase):
    def test_late_response_after_timeout_reaches_on_late_result_not_dropped(self):
        late_calls = []
        client, ws = _make_client(on_late_result=lambda command, message: late_calls.append((command, message)))

        async def scenario():
            receive_task = asyncio.create_task(client._receive_loop())
            try:
                with self.assertRaises(asyncio.TimeoutError):
                    await client.send_command('commission_with_code', {'code': 'x'}, timeout=0.05)
                # send_command's own timeout has fired - the caller (e.g. the webif) already
                # got its TimeoutError back. matter-server answers a moment later, for real.
                self.assertIn('1', client._timed_out)
                await ws.push({'message_id': '1', 'result': {'node_id': 42}})
                await asyncio.sleep(0.05)
            finally:
                receive_task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await receive_task

        asyncio.run(scenario())

        self.assertEqual(late_calls, [('commission_with_code', {'message_id': '1', 'result': {'node_id': 42}})])
        self.assertNotIn('1', client._timed_out)  # consumed, not left to leak/re-fire

    def test_genuinely_unmatched_message_does_not_call_on_late_result(self):
        late_calls = []
        client, ws = _make_client(on_late_result=lambda command, message: late_calls.append((command, message)))

        async def scenario():
            receive_task = asyncio.create_task(client._receive_loop())
            try:
                # No send_command was ever issued for this message_id, and it never
                # timed out either - a message like this from matter-server (if it ever
                # happened) is genuinely unexplained, not a late answer to anything.
                await ws.push({'message_id': '999', 'result': {}})
                await asyncio.sleep(0.05)
            finally:
                receive_task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await receive_task

        asyncio.run(scenario())
        self.assertEqual(late_calls, [])

    def test_normal_in_time_response_still_resolves_send_command_not_on_late_result(self):
        late_calls = []
        client, ws = _make_client(on_late_result=lambda command, message: late_calls.append((command, message)))

        async def scenario():
            receive_task = asyncio.create_task(client._receive_loop())
            try:
                send_task = asyncio.create_task(client.send_command('get_nodes', {}, timeout=5.0))
                await asyncio.sleep(0.01)  # let send_command register message_id 1 in _pending
                await ws.push({'message_id': '1', 'result': [{'node_id': 1}]})
                result = await send_task
                self.assertEqual(result, [{'node_id': 1}])
            finally:
                receive_task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await receive_task

        asyncio.run(scenario())
        self.assertEqual(late_calls, [])
        self.assertEqual(client._timed_out, {})

    def test_event_dispatch_still_works_alongside_the_late_result_path(self):
        events = []
        client = MatterServerClient('ws://unused', on_event=lambda message: events.append(message))
        ws = _FakeWebSocket()
        client._ws = ws

        async def scenario():
            receive_task = asyncio.create_task(client._receive_loop())
            try:
                await ws.push({'event': 'attribute_updated', 'data': [1, '1/6/0', True]})
                await asyncio.sleep(0.05)
            finally:
                receive_task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await receive_task

        asyncio.run(scenario())
        self.assertEqual(events, [{'event': 'attribute_updated', 'data': [1, '1/6/0', True]}])


class _FakeLogger:
    def __init__(self):
        self.warnings: list[str] = []
        self.exceptions: list[str] = []

    def warning(self, msg):
        self.warnings.append(msg)

    def exception(self, msg):
        self.exceptions.append(msg)

    def debug(self, msg):
        pass


class _RaisingWebSocket:
    """__anext__ raises immediately - simulates the connection dying mid-receive,
    same as a real sidecar process disappearing out from under an open socket."""

    def __init__(self, exception):
        self._exception = exception

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise self._exception


class TestReceiveLoopConnectionClosedHandling(unittest.TestCase):
    """
    Regression tests: a ConnectionClosed from the underlying websocket - the
    sidecar process died, whether killed deliberately, crashed, or restarted
    by supervise() (all now routine occurrences) - used to log a full
    traceback via logger.exception(), identically to any other genuinely
    unexpected error, drowning real errors in routine-restart noise.
    """

    def test_connection_closed_logs_a_short_warning_not_a_full_exception(self):
        logger = _FakeLogger()
        client = MatterServerClient('ws://unused', on_event=lambda message: None, logger=logger)
        # Same constructor args, same resulting message ("no close frame received or
        # sent") as the traceback this fix was written against.
        client._ws = _RaisingWebSocket(ConnectionClosedError(None, None))

        asyncio.run(client._receive_loop())

        self.assertEqual(len(logger.warnings), 1)
        self.assertIn('connection closed', logger.warnings[0])
        self.assertEqual(logger.exceptions, [])

    def test_a_genuinely_unexpected_error_still_logs_the_full_exception(self):
        logger = _FakeLogger()
        client = MatterServerClient('ws://unused', on_event=lambda message: None, logger=logger)
        client._ws = _RaisingWebSocket(RuntimeError('something else broke'))

        asyncio.run(client._receive_loop())

        self.assertEqual(logger.warnings, [])
        self.assertEqual(len(logger.exceptions), 1)


if __name__ == '__main__':
    unittest.main()
