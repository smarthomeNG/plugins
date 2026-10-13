"""Real TCP/asyncio regression tests against a loopback-only Modbus simulator."""

import asyncio
import socket
import socketserver
import struct
import threading
import time

import pytest

from plugins.modbus_tcp import modbus_tcp
from tests.sdp_harness import load_plugin


def wait_until(predicate, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    assert predicate(), 'timed out waiting for async operation'


class Simulator(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__(('127.0.0.1', 0), Handler)
        self.registers = {0: 1234, 1: 0x1234, 2: 0x5678}
        self.coils = {0: True}
        self.requests = []
        self.drop_next = False
        self.thread = threading.Thread(target=self.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
        self.thread.start()

    def close(self):
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=2)


class Handler(socketserver.BaseRequestHandler):
    def read_exact(self, count):
        data = b''
        while len(data) < count:
            chunk = self.request.recv(count - len(data))
            if not chunk:
                raise EOFError
            data += chunk
        return data

    def handle(self):
        try:
            while True:
                header = self.read_exact(7)
                tid, protocol, length, unit = struct.unpack('>HHHB', header)
                pdu = self.read_exact(length - 1)
                function = pdu[0]
                self.server.requests.append((unit, function))
                if self.server.drop_next:
                    self.server.drop_next = False
                    self.request.shutdown(socket.SHUT_RDWR)
                    return
                address, count = struct.unpack('>HH', pdu[1:5])
                if address >= 100:
                    reply = bytes([function | 0x80, 2])
                elif function in (3, 4):
                    values = [self.server.registers.get(address + offset, 0) for offset in range(count)]
                    reply = bytes([function, count * 2]) + struct.pack('>' + 'H' * count, *values)
                elif function in (1, 2):
                    packed = bytearray((count + 7) // 8)
                    for offset in range(count):
                        if self.server.coils.get(address + offset, False):
                            packed[offset // 8] |= 1 << (offset % 8)
                    reply = bytes([function, len(packed)]) + packed
                elif function == 5:
                    self.server.coils[address] = count == 0xff00
                    reply = pdu
                elif function == 16:
                    values = struct.unpack('>' + 'H' * count, pdu[6:])
                    for offset, value in enumerate(values):
                        self.server.registers[address + offset] = value
                    reply = pdu[:5]
                else:
                    reply = bytes([function | 0x80, 1])
                self.request.sendall(struct.pack('>HHHB', tid, protocol, len(reply) + 1, unit) + reply)
        except (EOFError, OSError):
            return


ITEMS = '''
dev:
    value:
        type: num
        modBusAddress: 0
        modBusFactor: 0.1
        modBusDirection: read_write
    coil:
        type: bool
        modBusAddress: 0
        modBusObjectType: Coil
        modBusDirection: read_write
    input:
        type: num
        modBusAddress: 1
        modBusObjectType: InputRegister
    discrete:
        type: bool
        modBusAddress: 0
        modBusObjectType: DiscreteInput
    poll:
        type: bool
        modbusPoll: true
'''


@pytest.fixture
def simulator():
    server = Simulator()
    try:
        yield server
    finally:
        server.close()


def rig_for(tmp_path, simulator, cycle=1, items=ITEMS, **params):
    return load_plugin(str(tmp_path), 'plugins.modbus_tcp', 'modbus_tcp', items,
                       params={'host': '127.0.0.1', 'port': simulator.server_address[1],
                               'cycle': cycle, 'slaveUnit': 7, **params})


@pytest.mark.parametrize('cycle', [1, 0, -1])
def test_reads_writes_and_clean_shutdown(tmp_path, simulator, cycle):
    rig = rig_for(tmp_path, simulator, cycle=cycle)
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        if cycle >= 0:
            time.sleep(0.1)
            assert simulator.requests == []
            if cycle == 0:
                rig.item('dev.poll')(True, 'test')
            else:
                rig.job(plugin._scheduler_name()).fire()
        wait_until(lambda: rig.item('dev.value')() == 123.4)
        assert rig.item('dev.coil')() is True
        wait_until(lambda: rig.item('dev.input')() == 0x1234)
        wait_until(lambda: rig.item('dev.discrete')() is True)
        assert all(unit == 7 for unit, _ in simulator.requests)
        # Freeze read acquisition to make external write assertions deterministic.
        plugin.run_asyncio_coro(cancel_reader(plugin))
        rig.item('dev.value')(43.2, 'test')
        wait_until(lambda: simulator.registers[0] == 432)
        rig.item('dev.coil')(False, 'test')
        wait_until(lambda: simulator.coils[0] is False)
        assert not any(function == 6 for _, function in simulator.requests)
    finally:
        plugin.stop()
    assert not plugin.pluginThread.is_alive()
    assert plugin._aclient is None
    assert not plugin._write_tasks
    assert not [msg for msg in rig.logs.messages() if 'exception' in msg.lower() or 'failed' in msg.lower()]


async def cancel_reader(plugin):
    if plugin._reader_task:
        plugin._reader_task.cancel()
        await asyncio.gather(plugin._reader_task, return_exceptions=True)


def test_disabled_reads_do_not_connect(tmp_path, simulator):
    rig = rig_for(tmp_path, simulator, cycle=0,
                  items='dev:\n    value:\n        type: num\n        modBusAddress: 0\n')
    try:
        rig.plugin.run()
        assert rig.plugin._connection_task is None
        assert rig.plugin._reader_task is None
        assert not rig.scheduler.jobs
        assert not rig.plugin.connected
        assert simulator.requests == []
    finally:
        rig.plugin.stop()


def test_reconnect_after_connection_drop(tmp_path, simulator):
    rig = rig_for(tmp_path, simulator)
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        plugin._trigger_async_read()
        wait_until(lambda: rig.item('dev.value')() == 123.4)
        wait_until(lambda: plugin._scheduled_read_task.done())
        simulator.drop_next = True
        plugin._trigger_async_read()
        wait_until(lambda: not simulator.drop_next)
        wait_until(lambda: plugin._scheduled_read_task.done())
        wait_until(lambda: plugin.connected and plugin._aclient is not None)
        simulator.registers[0] = 789
        plugin._trigger_async_read()
        wait_until(lambda: rig.item('dev.value')() == 78.9)
    finally:
        plugin.stop()


def test_crontab_and_restart(tmp_path, simulator):
    rig = rig_for(tmp_path, simulator, cycle=0, crontab='* * * *')
    plugin = rig.plugin
    for expected in (123.4, 56.7):
        simulator.registers[0] = round(expected * 10)
        try:
            plugin.run()
            wait_until(lambda: plugin.connected)
            assert rig.job(plugin._scheduler_name()) is not None
            rig.job(plugin._scheduler_name()).fire()
            wait_until(lambda: rig.item('dev.value')() == expected)
        finally:
            plugin.stop()
        assert not plugin.pluginThread.is_alive()
        assert not rig.scheduler.jobs


def test_write_only_mode_and_self_callback(tmp_path, simulator):
    rig = rig_for(tmp_path, simulator, cycle=0, items='''
dev:
    value:
        type: num
        modBusAddress: 0
        modBusDirection: write
''')
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        rig.item('dev.value')(999, plugin.get_fullname())
        time.sleep(0.1)
        assert simulator.requests == []
        rig.item('dev.value')(555, 'test')
        wait_until(lambda: simulator.registers[0] == 555)
        assert all(function == 16 for _, function in simulator.requests)
    finally:
        plugin.stop()


def test_overlapping_read_triggers_are_coalesced(tmp_path, simulator):
    rig = rig_for(tmp_path, simulator)
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        plugin._read_inter_request_delay = 0.1
        plugin._trigger_async_read()
        original = plugin._scheduled_read_task
        plugin._trigger_async_read()
        assert plugin._scheduled_read_task is original
        wait_until(lambda: original.done())
        assert len(simulator.requests) == 4
    finally:
        plugin.stop()


@pytest.mark.parametrize('datatype,bits,value', [
    ('uint', 16, 0x1234), ('uint', 32, 0x12345678), ('uint', 64, 0x123456789abcdef0),
    ('int', 16, -1234), ('int', 32, -123456), ('int', 64, -123456789),
    ('float', 32, 12.5), ('float', 64, -12.5),
])
@pytest.mark.parametrize('byteorder,wordorder', [('BIG', 'BIG'), ('BIG', 'LITTLE'),
                                             ('LITTLE', 'BIG'), ('LITTLE', 'LITTLE')])
def test_codec_round_trip(datatype, bits, value, byteorder, wordorder):
    registers = modbus_tcp._value_to_registers(value, datatype, bits, byteorder, wordorder)
    assert modbus_tcp._registers_to_value(registers, datatype, bits, byteorder, wordorder) == value


@pytest.mark.parametrize('byteorder,wordorder,expected', [
    ('BIG', 'BIG', [0x1234, 0x5678]), ('BIG', 'LITTLE', [0x5678, 0x1234]),
    ('LITTLE', 'BIG', [0x3412, 0x7856]), ('LITTLE', 'LITTLE', [0x7856, 0x3412]),
])
def test_known_wire_order(byteorder, wordorder, expected):
    assert modbus_tcp._value_to_registers(0x12345678, 'uint', 32, byteorder, wordorder) == expected


def test_string_and_register_bits():
    assert modbus_tcp._value_to_registers('AB', 'string', 2, 'BIG', 'BIG') == [0x4142]
    assert modbus_tcp._registers_to_value([0x4142, 0], 'string', 4, 'BIG', 'BIG') == 'AB'
    assert modbus_tcp._value_to_registers('1000000000000001', 'bit', 16, 'BIG', 'BIG') == [0x8001]
    assert modbus_tcp._registers_to_value([0x8001], 'bit', 16, 'BIG', 'BIG') == [True] + [False] * 14 + [True]
