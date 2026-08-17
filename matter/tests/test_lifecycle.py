#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Regression tests for server.cleanup()/bridge.cleanup()'s supervisor-task
cancellation: the sidecar's own crash-recovery loop (sidecar.supervise())
runs as a free-standing asyncio task, never part of the {stop_task,
server_task, bridge_task} set Matter._plugin_coro() awaits. Without
explicitly cancelling it first, supervise() only stops restarting once it
observes sidecar._stopping, which sidecar.stop() is what sets - a sidecar
process dying at exactly the wrong moment during shutdown could get
restarted by the *old* supervise() loop in the window before cleanup() gets
around to calling stop(), spawning a fresh process cleanup() never accounted
for (observed once: a shutdown log showed a fresh sidecar pid starting up
mid-shutdown, moments before the whole process exited).
"""

import asyncio
import unittest

from plugins.matter import Matter, bridge, server


class _FakeSidecar:
    def __init__(self, calls, label):
        self._calls = calls
        self._label = label

    async def stop(self):
        self._calls.append(f'{self._label}.stop')


class _FakeClient:
    def __init__(self, calls, label):
        self._calls = calls
        self._label = label

    async def close(self):
        self._calls.append(f'{self._label}.close')


async def _supervisor(calls):
    try:
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        calls.append('supervisor.cancelled')
        raise


class TestServerCleanupCancelsSupervisorTaskFirst(unittest.TestCase):
    def test_supervisor_task_is_cancelled_before_client_close_and_sidecar_stop(self):
        async def run():
            calls = []
            plugin = Matter.__new__(Matter)
            plugin.server_client = _FakeClient(calls, 'client')
            plugin.server_sidecar = _FakeSidecar(calls, 'sidecar')
            plugin.server_sidecar_supervisor_task = asyncio.create_task(_supervisor(calls))
            await asyncio.sleep(0)  # let the supervisor task actually start running

            await server.cleanup(plugin)

            self.assertEqual(calls, ['supervisor.cancelled', 'client.close', 'sidecar.stop'])
            self.assertIsNone(plugin.server_sidecar_supervisor_task)

        asyncio.run(run())

    def test_no_supervisor_task_is_a_safe_no_op(self):
        """run_forever() returns before creating the task if the sidecar failed to
        start at all (SidecarStartError) - cleanup() must not choke on that."""

        async def run():
            calls = []
            plugin = Matter.__new__(Matter)
            plugin.server_client = _FakeClient(calls, 'client')
            plugin.server_sidecar = _FakeSidecar(calls, 'sidecar')
            plugin.server_sidecar_supervisor_task = None

            await server.cleanup(plugin)

            self.assertEqual(calls, ['client.close', 'sidecar.stop'])

        asyncio.run(run())


class TestBridgeCleanupCancelsSupervisorTaskFirst(unittest.TestCase):
    def test_supervisor_task_is_cancelled_before_client_close_and_sidecar_stop(self):
        async def run():
            calls = []
            plugin = Matter.__new__(Matter)
            plugin.bridge_client = _FakeClient(calls, 'client')
            plugin.bridge_sidecar = _FakeSidecar(calls, 'sidecar')
            plugin.bridge_sidecar_supervisor_task = asyncio.create_task(_supervisor(calls))
            await asyncio.sleep(0)

            await bridge.cleanup(plugin)

            self.assertEqual(calls, ['supervisor.cancelled', 'client.close', 'sidecar.stop'])
            self.assertIsNone(plugin.bridge_sidecar_supervisor_task)

        asyncio.run(run())

    def test_no_supervisor_task_is_a_safe_no_op(self):
        async def run():
            calls = []
            plugin = Matter.__new__(Matter)
            plugin.bridge_client = _FakeClient(calls, 'client')
            plugin.bridge_sidecar = _FakeSidecar(calls, 'sidecar')
            plugin.bridge_sidecar_supervisor_task = None

            await bridge.cleanup(plugin)

            self.assertEqual(calls, ['client.close', 'sidecar.stop'])

        asyncio.run(run())
