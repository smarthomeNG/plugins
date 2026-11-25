"""A poll reads adjacent registers with one request and falls back to single reads on errors."""

import pytest

from plugins.modbus.tests.test_async_io import Simulator, rig_for, wait_until


@pytest.fixture
def simulator():
    server = Simulator()
    try:
        yield server
    finally:
        server.close()


def poll(rig) -> None:
    plugin = rig.plugin
    plugin._trigger_async_read()
    wait_until(lambda: plugin._scheduled_read_task is not None and plugin._scheduled_read_task.done())


def test_adjacent_registers_are_read_with_one_request(tmp_path, simulator):
    simulator.registers.update({10: 1, 11: 0x0001, 12: 0x0002, 13: 4})
    rig = rig_for(
        tmp_path,
        simulator,
        items="""
dev:
    a:
        type: num
        modBusAddress: 10
    b:
        type: num
        modBusAddress: 11
        modBusDataType: uint32
    c:
        type: num
        modBusAddress: 13
""",
    )
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        poll(rig)
    finally:
        plugin.stop()

    assert (rig.item('dev.a')(), rig.item('dev.b')(), rig.item('dev.c')()) == (1, 0x00010002, 4)
    assert simulator.requests == [(7, 3)]


def test_a_failing_block_is_read_point_by_point(tmp_path, simulator):
    simulator.registers.update({99: 42})
    rig = rig_for(
        tmp_path,
        simulator,
        items="""
dev:
    good:
        type: num
        modBusAddress: 99
    bad:
        type: num
        initial_value: 7
        modBusAddress: 100
""",
    )
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        poll(rig)
    finally:
        plugin.stop()

    assert rig.item('dev.good')() == 42
    assert rig.item('dev.bad')() == 7
    assert simulator.requests == [(7, 3), (7, 3), (7, 3)]


GOOD_AND_REJECTED = """
dev:
    good:
        type: num
        modBusAddress: 99
    bad:
        type: num
        modBusAddress: 100
"""


def test_a_point_the_device_rejects_is_no_longer_read(tmp_path, simulator):
    simulator.registers.update({99: 42})
    rig = rig_for(tmp_path, simulator, items=GOOD_AND_REJECTED)
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        poll(rig)
        simulator.requests.clear()
        simulator.registers[99] = 43
        poll(rig)
    finally:
        plugin.stop()

    assert rig.item('dev.good')() == 43
    assert simulator.requests == [(7, 3)]
    assert len([m for m in rig.logs.messages() if 'dev.bad' in m and 'illegal data address' in m]) == 1


def test_a_rejected_point_is_tried_again_after_a_reconnect(tmp_path, simulator):
    simulator.registers.update({99: 42})
    rig = rig_for(tmp_path, simulator, items=GOOD_AND_REJECTED)
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        poll(rig)
        simulator.drop_next = True
        poll(rig)
        wait_until(lambda: simulator.accepted == 2 and plugin.connected)
        simulator.requests.clear()
        poll(rig)
    finally:
        plugin.stop()

    assert simulator.requests == [(7, 3), (7, 3), (7, 3)]
