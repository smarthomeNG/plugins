#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Unit tests for MatterBridgeSidecar: _build_args() (pure list-building logic,
no process spawned) and supervise()'s backoff escalation (fake process/clock,
no real subprocess or real wall-clock waiting - see TestSuperviseBackoff's
own docstring for why the clock has to be faked, not just asyncio.sleep).
Mirrors tests/test_sidecar.py's pattern for the server role's sidecar.
"""

import asyncio
import unittest
from unittest.mock import patch

from plugins.matter.bridge import sidecar as bridge_sidecar_module
from plugins.matter.bridge.sidecar import MatterBridgeSidecar


def _sidecar(**overrides) -> MatterBridgeSidecar:
    kwargs = dict(
        node_binary='node',
        entry_path='bridge.js',
        matter_port=5560,
        control_port=5561,
        storage_path='/tmp/matter-bridge-storage',
        passcode=20202021,
        discriminator=3840,
        vendor_id=65521,
    )
    kwargs.update(overrides)
    return MatterBridgeSidecar(**kwargs)


def test_matter_port_and_control_port_are_both_passed():
    args = _sidecar()._build_args()
    assert args[args.index('--matter-port') + 1] == '5560'
    assert args[args.index('--control-port') + 1] == '5561'


def test_storage_path_is_passed_as_single_token():
    """--storage-path=<value>, not two separate tokens - matter.js's own
    argv-to-env mapping (parseArgvStyle) only splits on "=", a bare
    "--storage-path" with the value as a following token is silently
    parsed as storage-path=true and the actual path is dropped."""
    args = _sidecar()._build_args()
    assert '--storage-path=/tmp/matter-bridge-storage' in args


def test_passcode_discriminator_vendor_id_are_configurable():
    args = _sidecar(passcode=1, discriminator=2, vendor_id=3)._build_args()
    assert args[args.index('--passcode') + 1] == '1'
    assert args[args.index('--discriminator') + 1] == '2'
    assert args[args.index('--vendor-id') + 1] == '3'


def test_primary_interface_omitted_by_default():
    args = _sidecar()._build_args()
    assert '--primary-interface' not in args


def test_primary_interface_passed_when_set():
    """Same multi-interface gotcha server/sidecar.py's own primary_interface
    exists for - the bridge role uses matter.js's own network stack too, so
    it needs the same escape hatch, not just the server role."""
    args = _sidecar(primary_interface='en0')._build_args()
    assert args[args.index('--primary-interface') + 1] == 'en0'


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
    advancing the fake clock by uptime_seconds - the process "ran" for that
    long, as far as supervise()'s own time.monotonic()-based check can tell."""

    def __init__(self, clock: _FakeClock, uptime_seconds: float):
        self._clock = clock
        self._uptime_seconds = uptime_seconds

    async def wait(self):
        self._clock.advance(self._uptime_seconds)
        return 1


class TestSuperviseBackoff(unittest.TestCase):
    """
    Regression tests for a real bug: supervise() used to reset its own
    `attempt` counter to 0 immediately after every start(), regardless of how
    long that new process then stayed up before crashing again - so
    RESTART_BACKOFF_SECONDS's escalation (1, 2, 5, 10, 30, 60) never actually
    kicked in for a genuine crash loop, every restart attempt saw the
    shortest (1s) delay (killing a bridge sidecar manually produced no
    visible restart activity, traced to this exact reset).

    Both time.monotonic() (via _FakeClock/_FakeProcess above) and
    asyncio.sleep() (patched per-test below) are faked, so these tests run in
    milliseconds despite exercising delays up to STABLE_RUN_SECONDS (60s) of
    simulated time.
    """

    def _run_supervise_capturing_delays(self, uptimes, stop_after):
        """Drives supervise() through len(uptimes) simulated crashes, recording
        each backoff delay it computes. Stops once *stop_after* delays have
        been recorded (supervise() is an infinite loop otherwise)."""
        delays = []
        clock = _FakeClock()
        sidecar = _sidecar()
        remaining_uptimes = iter(uptimes)

        async def fake_start():
            sidecar._process = _FakeProcess(clock, next(remaining_uptimes))

        real_sleep = asyncio.sleep  # captured before patching - see fake_sleep's own use below

        async def fake_sleep(delay):
            delays.append(delay)
            if len(delays) >= stop_after:
                sidecar._stopping = True
            await real_sleep(0)  # yield once, no real delay - NOT asyncio.sleep, patched to this same function below

        sidecar.start = fake_start

        async def run():
            with (
                patch.object(bridge_sidecar_module.time, 'monotonic', clock.monotonic),
                patch.object(bridge_sidecar_module.asyncio, 'sleep', fake_sleep),
            ):
                await sidecar.supervise()

        asyncio.run(run())
        return delays

    def test_repeated_immediate_crashes_escalate_the_backoff(self):
        delays = self._run_supervise_capturing_delays(uptimes=[0, 0, 0, 0], stop_after=4)
        self.assertEqual(delays, [1, 2, 5, 10])

    def test_a_stable_run_resets_the_backoff_for_the_next_crash(self):
        # crash, crash (escalating to 2s), then a run that lasts long enough to
        # count as "stable" (>= STABLE_RUN_SECONDS) before crashing again - that
        # third delay must be back to the shortest tier, not continuing to
        # escalate from the unrelated crash streak before it.
        stable_uptime = bridge_sidecar_module.STABLE_RUN_SECONDS + 1
        delays = self._run_supervise_capturing_delays(uptimes=[0, 0, stable_uptime], stop_after=3)
        self.assertEqual(delays, [1, 2, 1])

    def test_backoff_caps_at_the_last_tier(self):
        delays = self._run_supervise_capturing_delays(uptimes=[0] * 8, stop_after=8)
        self.assertEqual(delays, [1, 2, 5, 10, 30, 60, 60, 60])
