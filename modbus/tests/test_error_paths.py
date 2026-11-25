"""Boundary cases, failures and lifecycle behaviour over real loopback TCP."""

import asyncio
import socket
import time

import pytest

from plugins.modbus.tests.test_async_io import Simulator, rig_for, wait_until


@pytest.fixture
def simulator():
    server = Simulator()
    try:
        yield server
    finally:
        server.close()


def test_odd_length_string_wire_read(tmp_path, simulator):
    simulator.registers.update({10: 0x4142, 11: 0x4300})
    rig = rig_for(
        tmp_path,
        simulator,
        items="""
dev:
    text:
        type: str
        modBusAddress: 10
        modBusDataType: string3
""",
    )
    try:
        rig.plugin.run()
        wait_until(lambda: rig.plugin.connected)
        rig.plugin._trigger_async_read()
        wait_until(lambda: rig.item('dev.text')() == 'ABC')
    finally:
        rig.plugin.stop()


def test_exception_response_does_not_hide_valid_register(tmp_path, simulator):
    rig = rig_for(
        tmp_path,
        simulator,
        items="""
dev:
    bad:
        type: num
        initial_value: 88
        modBusAddress: 100
    good:
        type: num
        modBusAddress: 0
""",
    )
    try:
        rig.plugin.run()
        wait_until(lambda: rig.plugin.connected)
        rig.plugin._trigger_async_read()
        wait_until(lambda: rig.item('dev.good')() == 1234)
        assert rig.item('dev.bad')() == 88
        assert rig.plugin.connected
        assert any('dev.bad' in x and 'illegal data address' in x for x in rig.logs.messages())
    finally:
        rig.plugin.stop()


def test_actual_pause_resume_and_no_writes_while_stopped(tmp_path, simulator):
    rig = rig_for(
        tmp_path,
        simulator,
        cycle=-1,
        pause_item='dev.pause',
        items="""
dev:
    pause:
        type: bool
    value:
        type: num
        modBusAddress: 0
        modBusDirection: read_write
""",
    )
    p = rig.plugin
    try:
        p.run()
        wait_until(lambda: rig.item('dev.value')() == 1234)
        rig.item('dev.pause')(True, 'test')
        assert not p.alive
        assert not p.pluginThread.is_alive()
        count = len(simulator.requests)
        rig.item('dev.value')(111, 'test')
        time.sleep(0.1)
        assert len(simulator.requests) == count
        rig.item('dev.pause')(False, 'test')
        wait_until(lambda: p.connected)
        wait_until(lambda: rig.item('dev.value')() == 1234)
        rig.item('dev.pause')(True, p.get_fullname())
        assert p.alive
        rig.item('dev.pause')(False, p.get_fullname())
    finally:
        if p.alive:
            p.stop()


def test_manual_poll_false_and_self_updates_are_ignored(tmp_path, simulator):
    rig = rig_for(tmp_path, simulator, cycle=0)
    p = rig.plugin
    try:
        p.run()
        wait_until(lambda: p.connected)
        p.update_item(rig.item('dev.poll'), caller='test')
        rig.item('dev.poll')(True, p.get_fullname())
        time.sleep(0.1)
        assert not simulator.requests
        rig.item('dev.poll')(False, 'test')
        rig.item('dev.poll')(True, 'test')
        wait_until(lambda: rig.item('dev.value')() == 123.4)
        wait_until(lambda: p._scheduled_read_task.done())
        assert len(simulator.requests) == 4
    finally:
        p.stop()


def test_per_item_unit_and_read_only_guard(tmp_path, simulator):
    rig = rig_for(
        tmp_path,
        simulator,
        items="""
dev:
    value:
        type: num
        modBusAddress: 0
        modBusUnit: 9
        modBusDirection: read
""",
    )
    p = rig.plugin
    try:
        p.run()
        wait_until(lambda: p.connected)
        p._trigger_async_read()
        wait_until(lambda: rig.item('dev.value')() == 1234)
        wait_until(lambda: p._scheduled_read_task.done())
        count = len(simulator.requests)
        rig.item('dev.value')(99, 'test')
        p.update_item(rig.item('dev.value'), caller='test')
        time.sleep(0.1)
        assert len(simulator.requests) == count
        assert all(unit == 9 for unit, _ in simulator.requests)
    finally:
        p.stop()


def test_write_validation_and_read_only_object_types(tmp_path, simulator):
    rig = rig_for(
        tmp_path,
        simulator,
        cycle=0,
        items="""
dev:
    input:
        type: num
        modBusAddress: 1
        modBusObjectType: InputRegister
        modBusDirection: read_write
    discrete:
        type: bool
        modBusAddress: 0
        modBusObjectType: DiscreteInput
        modBusDirection: read_write
    coil:
        type: num
        modBusAddress: 0
        modBusObjectType: Coil
        modBusDirection: read_write
    odd_type:
        type: num
        modBusAddress: 2
        modBusDataType: uint12
        modBusDirection: read_write
    small:
        type: num
        modBusAddress: 3
        modBusDirection: read_write
    zero_factor:
        type: num
        modBusAddress: 4
        modBusFactor: 0
        modBusDirection: read_write
""",
    )
    p = rig.plugin
    try:
        p.run()
        wait_until(lambda: p.connected)
        for path, value in [
            ('input', 10),
            ('discrete', True),
            ('coil', 1),
            ('odd_type', 10),
            ('small', 70000),
            ('zero_factor', 10),
        ]:
            rig.item(f'dev.{path}')(value, 'test')
        wait_until(lambda: any('cannot encode' in x for x in rig.logs.messages()))
        wait_until(lambda: any('factor' in x and 'zero' in x for x in rig.logs.messages()))
        wait_until(lambda: any('not boolean' in x for x in rig.logs.messages()))
        messages = rig.logs.messages()
        assert any('unknown datatype' in x for x in messages)
        assert sum('cannot be written' in x for x in messages) == 2
        assert not simulator.requests
        assert p.connected
        assert not any('Traceback' in x for x in messages)
    finally:
        p.stop()


def test_bounded_write_when_endpoint_is_unavailable(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]

        class Endpoint:
            server_address = ('127.0.0.1', port)

        rig = rig_for(tmp_path, Endpoint(), cycle=0)
        p = rig.plugin
        try:
            p.run()
            p._write_timeout = 0.2
            rig.item('dev.value')(10, 'test')
            wait_until(lambda: any('write skipped' in x for x in rig.logs.messages()), timeout=1)
            assert not p.connected
        finally:
            p.stop()


def test_signed_invalid_wire_value_is_not_written_to_item(tmp_path, simulator):
    simulator.registers[0] = 0x8000
    rig = rig_for(
        tmp_path,
        simulator,
        items="""
dev:
    value:
        type: num
        initial_value: 77
        modBusAddress: 0
        modBusDataType: int16
""",
    )
    p = rig.plugin
    try:
        p.run()
        wait_until(lambda: p.connected)
        p._trigger_async_read()
        wait_until(lambda: p._scheduled_read_task.done())
        assert rig.item('dev.value')() == 77
        simulator.registers[0] = 0xFF9C
        p._trigger_async_read()
        wait_until(lambda: rig.item('dev.value')() == -100)
    finally:
        p.stop()
