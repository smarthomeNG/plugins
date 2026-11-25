"""``modBusInvalidValue``: the item value for "no value" reports of the device, not for errors."""

import pytest

from plugins.modbus.tests.test_async_io import Simulator, rig_for, wait_until


@pytest.fixture
def simulator():
    server = Simulator()
    try:
        yield server
    finally:
        server.close()


def poll(plugin) -> None:
    plugin._trigger_async_read()
    wait_until(lambda: plugin._scheduled_read_task is not None and plugin._scheduled_read_task.done())


def test_no_value_report_sets_the_invalid_value_as_is(tmp_path, simulator):
    simulator.registers.update({10: 0x8000, 11: 0x0000})
    rig = rig_for(
        tmp_path,
        simulator,
        items="""
dev:
    power:
        type: num
        initial_value: 3000
        modBusAddress: 10
        modBusDataType: int32
        modBusFactor: 0.1
        modBusInvalidValue: 5
""",
    )
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        poll(plugin)
        assert rig.item('dev.power')() == 5

        simulator.registers.update({10: 0x0000, 11: 0x0064})
        poll(plugin)
        assert rig.item('dev.power')() == 10
    finally:
        plugin.stop()


def test_read_errors_leave_the_item_unchanged(tmp_path, simulator):
    rig = rig_for(
        tmp_path,
        simulator,
        items="""
dev:
    power:
        type: num
        initial_value: 3000
        modBusAddress: 100
        modBusInvalidValue: 0
""",
    )
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        poll(plugin)
        assert rig.item('dev.power')() == 3000
    finally:
        plugin.stop()


def test_device_specific_no_value_reports(tmp_path, simulator):
    simulator.registers.update({20: 32767, 21: 32767})
    rig = rig_for(
        tmp_path,
        simulator,
        items="""
dev:
    zeroed:
        type: num
        modBusAddress: 20
        modBusDataType: int16
        modBusFactor: 0.1
        modBusInvalid: [32767]
        modBusInvalidValue: 0
    kept:
        type: num
        initial_value: 21.5
        modBusAddress: 21
        modBusDataType: int16
        modBusFactor: 0.1
        modBusInvalid: [32767]
""",
    )
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        poll(plugin)
    finally:
        plugin.stop()

    assert rig.item('dev.zeroed')() == 0
    assert rig.item('dev.kept')() == 21.5
