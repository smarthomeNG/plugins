"""The optional TROVIS 557x profile, exported and used per point, reads a simulated controller over real Modbus TCP."""

from plugins.modbus.tests.profile_rig import exported_structs, poll_once, running
from plugins.modbus.tests.test_async_io import wait_until

ITEMS = """
heizung:
    aussen:
        struct: my.modbus_samson.trovis557x.AussentempAF1
    aussen2:
        struct: my.modbus_samson.trovis557x.AussentempAF2
        modBusInvalidValue: 0
    anlage:
        struct: my.modbus_samson.trovis557x.Anlage
    firmware:
        struct: my.modbus_samson.trovis557x.Firmware_Version
    uhrzeit:
        struct: my.modbus_samson.trovis557x.Uhrzeit
    datum:
        struct: my.modbus_samson.trovis557x.Datum
    schalter:
        struct: my.modbus_samson.trovis557x.Schalteroben
"""


def test_points_read_as_with_the_trovis557x_plugin(tmp_path, modbus_server):
    server = modbus_server(247, {1: [10, 219], 9: [(-55) & 0xFFFF, 32767], 99: [905, 1503], 102: [3]})

    rig = poll_once(tmp_path, server, ITEMS, exported_structs('samson.trovis557x', tmp_path))

    def value(path: str):
        return rig.item(f'heizung.{path}')()

    assert value('aussen') == -5.5
    assert value('aussen2') == 0
    assert (value('anlage'), value('firmware')) == ('1.0', '2.19')
    assert (value('uhrzeit'), value('datum')) == ('09:05', '15.03.')
    assert (value('schalter'), value('schalter.text')) == (3, 'Hand')


SETPOINTS = """
heizung:
    sommer:
        struct: my.modbus_samson.trovis557x.SommerAT_Wert
    betriebsart:
        struct: my.modbus_samson.trovis557x.BetriebsArtRk1
    uhrzeit:
        struct: my.modbus_samson.trovis557x.Uhrzeit
"""


def test_writable_export_writes_setpoints(tmp_path, modbus_server):
    server = modbus_server(247, {99: [905], 105: [1], 116: [150]})

    with running(tmp_path, server, SETPOINTS, exported_structs('samson.trovis557x', tmp_path, writable=True)) as rig:
        rig.item('heizung.sommer')(18.5, 'test')
        rig.item('heizung.betriebsart.text')('Hand', 'test')
        rig.item('heizung.uhrzeit')('07:30', 'test')

        wait_until(lambda: (server.holding(116), server.holding(105), server.holding(99)) == ([185], [3], [730]))


def test_default_export_reads_setpoints_only(tmp_path):
    point = exported_structs('samson.trovis557x', tmp_path)['my.modbus_samson']['trovis557x']['SommerAT_Wert']

    assert point['modBusDirection@instance'] == 'read'
    assert point['remark'] == 'writable (modBusDirection: read_write)'


def test_an_item_enables_writing_in_a_read_only_export(tmp_path, modbus_server):
    server = modbus_server(247, {105: [1], 116: [150]})
    items = """
heizung:
    sommer:
        struct: my.modbus_samson.trovis557x.SommerAT_Wert
        modBusDirection: read_write
    betriebsart:
        struct: my.modbus_samson.trovis557x.BetriebsArtRk1
        text:
            modBusDirection: read_write
"""

    with running(tmp_path, server, items, exported_structs('samson.trovis557x', tmp_path)) as rig:
        rig.item('heizung.sommer')(18.5, 'test')
        rig.item('heizung.betriebsart.text')('Hand', 'test')

        wait_until(lambda: (server.holding(116), server.holding(105)) == ([185], [3]))
