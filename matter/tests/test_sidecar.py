#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Unit tests for MatterServerSidecar: _build_args() (pure list-building logic, no
process spawned) and supervise()'s backoff escalation (fake process/clock, no
real subprocess or real wall-clock waiting - mirrors
tests/test_bridge_sidecar.py's TestSuperviseBackoff, see that class's own
docstring for the full reasoning; both roles' supervise() share the same
requirement).
"""

import asyncio
import unittest
from unittest.mock import patch

from plugins.matter.server import sidecar as server_sidecar_module
from plugins.matter.server.sidecar import MatterServerSidecar


def _sidecar(**overrides) -> MatterServerSidecar:
    kwargs = dict(
        node_binary='node',
        entry_path='entry.js',
        port=5580,
        storage_path='/tmp/matter-storage',
        enable_test_net_dcl=False,
    )
    kwargs.update(overrides)
    return MatterServerSidecar(**kwargs)


def test_default_fabric_vendor_id_is_matter_spec_test_range():
    args = _sidecar()._build_args()
    assert args[args.index('--vendorid') + 1] == '65521'


def test_default_fabric_label_is_smarthomeng():
    args = _sidecar()._build_args()
    assert args[args.index('--default-fabric-label') + 1] == 'SmartHomeNG'


def test_fabric_vendor_id_is_configurable():
    args = _sidecar(fabric_vendor_id=42)._build_args()
    assert args[args.index('--vendorid') + 1] == '42'


def test_fabric_label_is_configurable():
    args = _sidecar(fabric_label='My Home')._build_args()
    assert args[args.index('--default-fabric-label') + 1] == 'My Home'


class _FakeClock:
    """Stands in for time.monotonic() - advanced explicitly by _FakeProcess.wait()
    below to simulate "this much time passed while the process was running",
    without actually consuming any real wall-clock time in the test."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class _FakeProcess:
    """Stands in for asyncio.subprocess.Process - supervise() only ever calls
    .wait() on it. Resolves on the next event loop tick (no real sleep), after
    advancing the fake clock by uptime_seconds."""

    def __init__(self, clock: _FakeClock, uptime_seconds: float):
        self._clock = clock
        self._uptime_seconds = uptime_seconds

    async def wait(self):
        self._clock.advance(self._uptime_seconds)
        return 1


class TestSuperviseBackoff(unittest.TestCase):
    """Regression tests for the same real bug test_bridge_sidecar.py's own
    TestSuperviseBackoff documents in full - server/sidecar.py's supervise()
    had the identical reset-attempt-too-early bug, same fix applied here."""

    def _run_supervise_capturing_delays(self, uptimes, stop_after):
        delays = []
        clock = _FakeClock()
        sidecar = _sidecar()
        remaining_uptimes = iter(uptimes)

        async def fake_start():
            sidecar._process = _FakeProcess(clock, next(remaining_uptimes))

        real_sleep = asyncio.sleep

        async def fake_sleep(delay):
            delays.append(delay)
            if len(delays) >= stop_after:
                sidecar._stopping = True
            await real_sleep(0)

        sidecar.start = fake_start

        async def run():
            with (
                patch.object(server_sidecar_module.time, 'monotonic', clock.monotonic),
                patch.object(server_sidecar_module.asyncio, 'sleep', fake_sleep),
            ):
                await sidecar.supervise()

        asyncio.run(run())
        return delays

    def test_repeated_immediate_crashes_escalate_the_backoff(self):
        delays = self._run_supervise_capturing_delays(uptimes=[0, 0, 0, 0], stop_after=4)
        self.assertEqual(delays, [1, 2, 5, 10])

    def test_a_stable_run_resets_the_backoff_for_the_next_crash(self):
        stable_uptime = server_sidecar_module.STABLE_RUN_SECONDS + 1
        delays = self._run_supervise_capturing_delays(uptimes=[0, 0, stable_uptime], stop_after=3)
        self.assertEqual(delays, [1, 2, 1])

    def test_backoff_caps_at_the_last_tier(self):
        delays = self._run_supervise_capturing_delays(uptimes=[0] * 8, stop_after=8)
        self.assertEqual(delays, [1, 2, 5, 10, 30, 60, 60, 60])
