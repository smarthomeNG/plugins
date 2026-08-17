#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Unit tests for MatterBridgeClient._receive_loop()'s ConnectionClosed handling -
mirrors tests/test_client.py's identical coverage for the server role's
MatterServerClient (same bug, same fix, in the sibling client class). See that
file's own TestReceiveLoopConnectionClosedHandling docstring for the full
reasoning.
"""

import asyncio
import unittest

from websockets.exceptions import ConnectionClosedError

from plugins.matter.bridge.client import MatterBridgeClient


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
    same as a real bridge sidecar process disappearing out from under an open socket."""

    def __init__(self, exception):
        self._exception = exception

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise self._exception


class TestReceiveLoopConnectionClosedHandling(unittest.TestCase):
    def test_connection_closed_logs_a_short_warning_not_a_full_exception(self):
        logger = _FakeLogger()
        client = MatterBridgeClient('ws://unused', on_event=lambda message: None, logger=logger)
        # Same constructor args, same resulting message ("no close frame received or
        # sent") as the traceback this fix was written against.
        client._ws = _RaisingWebSocket(ConnectionClosedError(None, None))

        asyncio.run(client._receive_loop())

        self.assertEqual(len(logger.warnings), 1)
        self.assertIn('connection closed', logger.warnings[0])
        self.assertEqual(logger.exceptions, [])

    def test_a_genuinely_unexpected_error_still_logs_the_full_exception(self):
        logger = _FakeLogger()
        client = MatterBridgeClient('ws://unused', on_event=lambda message: None, logger=logger)
        client._ws = _RaisingWebSocket(RuntimeError('something else broke'))

        asyncio.run(client._receive_loop())

        self.assertEqual(logger.warnings, [])
        self.assertEqual(len(logger.exceptions), 1)


if __name__ == '__main__':
    unittest.main()
