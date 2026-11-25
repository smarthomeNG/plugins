"""``invalidate_on_disconnect``: a lost connection opens a database gap for the items read from the device."""

import pytest

from plugins.modbus.tests.test_async_io import Simulator, rig_for, wait_until
from tests.gap_recorder import GapRecorder

ITEMS = """
dev:
    value:
        type: num
        modBusAddress: 0
    setpoint:
        type: num
        modBusAddress: 1
        modBusDirection: write
"""


@pytest.fixture
def simulator():
    server = Simulator()
    try:
        yield server
    finally:
        server.close()


def connected_rig(tmp_path, simulator, **params):
    rig = rig_for(tmp_path, simulator, cycle=0, items=ITEMS, **params)
    gaps = {path: GapRecorder(rig.item(path)) for path in ('dev.value', 'dev.setpoint')}
    rig.plugin.run()
    wait_until(lambda: rig.plugin.connected)
    return rig, gaps


def drop_connection(rig, simulator) -> None:
    plugin = rig.plugin
    simulator.drop_next = True
    plugin._trigger_async_read()
    wait_until(lambda: not simulator.drop_next)
    wait_until(lambda: plugin._scheduled_read_task.done())


def test_connection_loss_marks_read_items(tmp_path, simulator):
    rig, gaps = connected_rig(tmp_path, simulator, invalidate_on_disconnect=True)
    try:
        drop_connection(rig, simulator)
        wait_until(lambda: gaps['dev.value'].calls)
    finally:
        rig.plugin.stop()

    assert gaps['dev.value'].calls == [(rig.plugin.get_fullname(), 'connection_lost')]
    assert gaps['dev.setpoint'].calls == []


def test_disabled_by_default(tmp_path, simulator):
    rig, gaps = connected_rig(tmp_path, simulator)
    try:
        drop_connection(rig, simulator)
        wait_until(lambda: rig.plugin.connected)
    finally:
        rig.plugin.stop()

    assert gaps['dev.value'].calls == []


def test_stopping_the_plugin_is_no_connection_loss(tmp_path, simulator):
    rig, gaps = connected_rig(tmp_path, simulator, invalidate_on_disconnect=True)
    rig.plugin.stop()

    assert gaps['dev.value'].calls == []
