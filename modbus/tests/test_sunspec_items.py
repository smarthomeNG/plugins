"""Items with ``modBusSunSpec`` read and write SunSpec points of a real Modbus TCP server."""

import pytest

from plugins.modbus.tests.sunspec_rig import image, model
from plugins.modbus.tests.test_async_io import wait_until
from tests.sdp_harness import load_plugin

COMMON = model(1, [0x4163, 0x6D65] + [0] * 64)  # Mn = 'Acme'


def inverter(watts: int, scale: int) -> list[int]:
    body = [0] * 50
    body[12], body[13] = watts, scale & 0xFFFF
    return model(103, body)


def controls(limit: int, scale: int) -> list[int]:
    body = [0] * 24
    body[3], body[21] = limit, scale & 0xFFFF
    return model(123, body)


def mppt(module_watts: list[int], scale: int) -> list[int]:
    head = [0, 0, scale & 0xFFFF, 0, 0, 0, len(module_watts), 0]
    modules = []
    for watts in module_watts:
        module = [0] * 20
        module[11] = watts
        modules += module
    return model(160, head + modules)


def holding(*models: list[int]) -> dict[int, list[int]]:
    registers = image(40000, *models)
    return {40000: [registers[a] for a in sorted(registers)]}


@pytest.fixture
def sunspec_rig(tmp_path, modbus_server):
    rigs = []

    def start(items: str, *models: list[int], cycle: int = 60):
        server = modbus_server(1, holding(*models))
        rig = load_plugin(
            str(tmp_path),
            'plugins.modbus',
            'Modbus',
            items,
            params={'host': server.host, 'port': server.port, 'cycle': cycle, 'slaveUnit': 1},
        )
        rig.server = server
        rigs.append(rig)
        rig.plugin.run()
        wait_until(lambda: rig.plugin.connected)
        return rig

    yield start
    for rig in rigs:
        rig.plugin.stop()


def poll(rig) -> None:
    plugin = rig.plugin
    rig.job(plugin._scheduler_name()).fire()
    wait_until(lambda: plugin._scheduled_read_task is not None and plugin._scheduled_read_task.done())


def test_points_are_read_by_name_and_scaled(sunspec_rig):
    rig = sunspec_rig(
        """
inv:
    maker:
        type: str
        modBusSunSpec: 1.Mn
    power:
        type: num
        modBusSunSpec: 103.W
    module2:
        type: num
        modBusSunSpec: 160.module.2.DCW
""",
        COMMON,
        inverter(1234, -1),
        mppt([700, 500], 1),
    )
    poll(rig)

    assert rig.item('inv.maker')() == 'Acme'
    assert rig.item('inv.power')() == pytest.approx(123.4)
    assert rig.item('inv.module2')() == 5000


def test_writes_divide_by_the_scale_factor(sunspec_rig):
    rig = sunspec_rig(
        """
inv:
    limit:
        type: num
        modBusSunSpec: 123.WMaxLimPct
        modBusDirection: read_write
""",
        COMMON,
        controls(1000, -1),
    )
    poll(rig)
    assert rig.item('inv.limit')() == 100

    rig.item('inv.limit')(55.5, 'test')

    wait_until(lambda: rig.server.holding(40070 + 5) == [555])


def test_unusable_addresses_are_dropped_with_a_warning(sunspec_rig):
    rig = sunspec_rig(
        """
inv:
    second:
        type: num
        initial_value: 7
        modBusSunSpec: 103:2.W
    unknown:
        type: num
        modBusSunSpec: 103.Watts
    power:
        type: num
        modBusSunSpec: 103.W
""",
        COMMON,
        inverter(1234, 0),
    )
    poll(rig)
    poll(rig)

    assert rig.item('inv.power')() == 1234
    assert rig.item('inv.second')() == 7
    warnings = [m for m in rig.logs.messages() if 'inv.' in m]
    assert sum('103.Watts' in m for m in warnings) == 1
    assert sum('103:2.W' in m and 'not on the device' in m for m in warnings) == 1


def test_scale_factor_without_value_leaves_the_item_unchanged(sunspec_rig):
    rig = sunspec_rig(
        """
inv:
    power:
        type: num
        initial_value: 7
        modBusSunSpec: 103.W
""",
        COMMON,
        inverter(1234, -0x8000),
    )
    poll(rig)

    assert rig.item('inv.power')() == 7


def test_a_new_connection_scans_again(sunspec_rig):
    rig = sunspec_rig(
        """
inv:
    power:
        type: num
        modBusSunSpec: 103.W
""",
        COMMON,
        inverter(1234, 0),
    )
    poll(rig)
    assert rig.item('inv.power')() == 1234

    rig.server.set_holding(40000, holding(COMMON, controls(0, 0), inverter(4321, 0))[40000])

    async def drop():
        rig.plugin._close_client()

    rig.plugin.run_asyncio_coro(drop(), timeout=1)
    wait_until(lambda: rig.plugin.connected and rig.plugin._connections == 2)
    poll(rig)

    assert rig.item('inv.power')() == 4321


def test_write_only_items_bind_and_scale_without_polling(sunspec_rig):
    rig = sunspec_rig(
        """
inv:
    limit:
        type: num
        modBusSunSpec: 123.WMaxLimPct
        modBusDirection: write
""",
        COMMON,
        controls(0, -1),
        cycle=0,
    )
    rig.item('inv.limit')(55.5, 'test')

    wait_until(lambda: rig.server.holding(40070 + 5) == [555])
