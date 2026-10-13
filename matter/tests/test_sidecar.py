#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for plugins/matter/sidecar.py (NodeSidecar) with real child
processes - a small Python script stands in for the Node.js entry file -
plus both concrete sidecars' command lines and the bridge identity.
"""

import asyncio
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

import psutil

from plugins.matter.bridge.sidecar import (
    DEFAULT_BRIDGE_UNIQUE_ID,
    MAX_BASIC_INFORMATION_STRING,
    BridgeSidecarSettings,
    MatterBridgeSidecar,
    bridge_unique_id,
)
from plugins.matter.role import Backoff
from plugins.matter.server.sidecar import MatterServerSidecar, ServerSidecarSettings
from plugins.matter.sidecar import NodeSidecar, SidecarStartError

SCRIPT = textwrap.dedent(
    """
    import sys, time
    mode = sys.argv[1]
    print('booting', flush=True)
    print('READY now', flush=True)
    if mode == 'crash':
        sys.exit(3)
    time.sleep(60)
    """
)


class ScriptSidecar(NodeSidecar):
    LABEL = 'test sidecar'
    LOG_PREFIX = '[test]'
    READY_MARKER = 'READY'
    PIDFILE_NAME = 'test.pid'
    MISSING_ENTRY_HINT = 'test hint.'

    def __init__(self, entry_path, storage_path, mode='run', node_binary=sys.executable):
        super().__init__(node_binary, entry_path, storage_path)
        self.mode = mode

    def _build_args(self):
        return [self.entry_path, self.mode]


class _SidecarTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.storage = os.path.join(tmp.name, 'storage')
        self.entry = os.path.join(tmp.name, 'entry.py')
        with open(self.entry, 'w') as f:
            f.write(SCRIPT)


class TestStartStop(_SidecarTest):
    async def test_start_waits_for_readiness_and_records_the_pid(self):
        sidecar = ScriptSidecar(self.entry, self.storage)
        await sidecar.start()
        self.addAsyncCleanup(sidecar.stop)

        self.assertTrue(sidecar.running)
        with open(sidecar.pidfile_path) as f:
            self.assertEqual(int(f.read()), sidecar._process.pid)

    async def test_stop_terminates_and_removes_the_pidfile(self):
        sidecar = ScriptSidecar(self.entry, self.storage)
        await sidecar.start()
        pid = sidecar._process.pid

        await sidecar.stop()

        self.assertFalse(sidecar.running)
        self.assertFalse(os.path.exists(sidecar.pidfile_path))
        self.assertFalse(psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE)

    async def test_missing_entry_file_is_a_start_error(self):
        sidecar = ScriptSidecar(self.entry + '.missing', self.storage)

        with self.assertRaises(SidecarStartError) as caught:
            await sidecar.start()

        self.assertIn('test hint.', str(caught.exception))

    async def test_missing_node_binary_is_a_start_error(self):
        sidecar = ScriptSidecar(self.entry, self.storage, node_binary='/nonexistent/node')

        with self.assertRaises(SidecarStartError):
            await sidecar.start()


class TestStaleProcess(_SidecarTest):
    async def test_leftover_process_of_this_entry_is_terminated_before_start(self):
        os.makedirs(self.storage)
        leftover = subprocess.Popen([sys.executable, self.entry, 'run'], stdout=subprocess.DEVNULL)
        self.addCleanup(leftover.kill)
        sidecar = ScriptSidecar(self.entry, self.storage)
        with open(sidecar.pidfile_path, 'w') as f:
            f.write(str(leftover.pid))

        await sidecar.start()
        self.addAsyncCleanup(sidecar.stop)

        self.assertIsNotNone(await asyncio.to_thread(leftover.wait, 15))
        self.assertNotEqual(sidecar._process.pid, leftover.pid)

    async def test_unrelated_process_in_pidfile_is_left_alone(self):
        os.makedirs(self.storage)
        sidecar = ScriptSidecar(self.entry, self.storage)
        with open(sidecar.pidfile_path, 'w') as f:
            f.write(str(os.getpid()))

        await sidecar.start()
        self.addAsyncCleanup(sidecar.stop)

        self.assertTrue(psutil.pid_exists(os.getpid()))


class TestSupervise(_SidecarTest):
    async def test_crashed_process_is_restarted(self):
        sidecar = ScriptSidecar(self.entry, self.storage, mode='crash')
        await sidecar.start()
        first_pid = sidecar._process.pid
        supervisor = asyncio.create_task(sidecar.supervise(Backoff(schedule=(0,))))

        restarted = False
        for _ in range(200):
            if sidecar._process is not None and sidecar._process.pid != first_pid:
                restarted = True
                break
            await asyncio.sleep(0.02)
        supervisor.cancel()
        await asyncio.gather(supervisor, return_exceptions=True)
        await sidecar.stop()

        self.assertTrue(restarted)

    async def test_failing_restart_keeps_supervising(self):
        sidecar = ScriptSidecar(self.entry, self.storage, mode='crash')
        await sidecar.start()
        os.rename(self.entry, self.entry + '.away')
        supervisor = asyncio.create_task(sidecar.supervise(Backoff(schedule=(0,))))

        await asyncio.sleep(0.5)
        self.assertFalse(supervisor.done())

        os.rename(self.entry + '.away', self.entry)
        sidecar.mode = 'run'
        for _ in range(200):
            if sidecar.running:
                break
            await asyncio.sleep(0.02)
        running = sidecar.running
        supervisor.cancel()
        await asyncio.gather(supervisor, return_exceptions=True)
        await sidecar.stop()

        self.assertTrue(running)


class TestCommandLines(unittest.TestCase):
    def test_server_args(self):
        sidecar = MatterServerSidecar(
            'node',
            '/p/MatterServer.js',
            '/s',
            ServerSidecarSettings(port=5580, primary_interface='eth0', bluetooth_adapter='0', enable_test_net_dcl=True),
        )

        args = sidecar._build_args()

        self.assertEqual(args[:5], ['/p/MatterServer.js', '--port', '5580', '--storage-path', '/s'])
        self.assertIn('--enable-test-net-dcl', args)
        self.assertEqual(args[args.index('--primary-interface') + 1], 'eth0')
        self.assertEqual(args[args.index('--bluetooth-adapter') + 1], '0')

    def test_bridge_args_carry_storage_as_key_value_and_the_unique_id(self):
        sidecar = MatterBridgeSidecar(
            'node',
            '/p/bridge.js',
            '/s',
            BridgeSidecarSettings(
                matter_port=5560, control_port=5561, passcode=1, discriminator=2, vendor_id=3, unique_id='shng-bridge-x'
            ),
        )

        args = sidecar._build_args()

        self.assertIn('--storage-path=/s', args)
        self.assertEqual(args[args.index('--unique-id') + 1], 'shng-bridge-x')
        self.assertNotIn('--primary-interface', args)


class TestBridgeUniqueId(unittest.TestCase):
    def test_default_instance_keeps_the_existing_identity(self):
        self.assertEqual(bridge_unique_id(''), DEFAULT_BRIDGE_UNIQUE_ID)

    def test_named_instance_is_readable(self):
        self.assertEqual(bridge_unique_id('garage'), 'shng-bridge-garage')

    def test_long_instance_names_fit_and_stay_distinct(self):
        first = bridge_unique_id('a_really_long_instance_name_one')
        second = bridge_unique_id('a_really_long_instance_name_two')

        self.assertLessEqual(len(first), MAX_BASIC_INFORMATION_STRING)
        self.assertLessEqual(len(second), MAX_BASIC_INFORMATION_STRING)
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith('shng-bridge-a_really'))


if __name__ == '__main__':
    unittest.main()
