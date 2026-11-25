"""SunSpec model definitions, item addresses and register layout."""

import asyncio
import json

import pytest

from plugins.modbus import sunspec
from plugins.modbus.sunspec import GroupDef, PointDef, SunSpecError, load_catalog
from plugins.modbus.tests.sunspec_rig import image, model, reader

CATALOG = load_catalog()

UPSTREAM_MODEL = {
    'id': 64999,
    'group': {
        'name': 'demo',
        'label': 'Demo',
        'desc': 'dropped',
        'type': 'group',
        'points': [
            {'name': 'ID', 'type': 'uint16', 'size': 1, 'static': 'S', 'mandatory': 'M', 'value': 64999},
            {'name': 'L', 'type': 'uint16', 'size': 1, 'mandatory': 'M'},
            {'name': 'W', 'type': 'int16', 'size': 1, 'sf': 'W_SF', 'units': 'W', 'label': 'Watts', 'desc': 'x'},
            {'name': 'WMax', 'type': 'uint16', 'size': 1, 'access': 'RW', 'symbols': [{'name': 'A', 'value': 1}]},
            {'name': 'W_SF', 'type': 'sunssf', 'size': 1},
        ],
        'groups': [
            {'name': 'rep', 'type': 'group', 'count': 0, 'points': [{'name': 'V', 'type': 'uint16', 'size': 1}]}
        ],
    },
}


def test_shipped_catalog_has_the_common_inverter_models():
    assert {1, 101, 103, 160, 802} <= set(CATALOG.models)
    inverter = CATALOG.get(103)
    assert inverter.name == 'inverter_three_phase'
    assert [p.name for p in inverter.group.points[:3]] == ['ID', 'L', 'A']
    watts = next(p for p in inverter.group.points if p.name == 'W')
    assert (watts.type, watts.size, watts.sf, watts.units) == ('int16', 1, 'W_SF', 'W')
    assert CATALOG.get(160).group.groups[0].count == 0
    assert CATALOG.source.startswith('sunspec/models ')


def test_unknown_model_is_reported():
    with pytest.raises(SunSpecError, match='unknown SunSpec model 9999'):
        CATALOG.get(9999)


def test_convert_keeps_what_addressing_needs(tmp_path):
    source = tmp_path / 'json'
    source.mkdir()
    (source / 'model_64999.json').write_text(json.dumps(UPSTREAM_MODEL))
    (source / 'schema.json').write_text('{}')
    target = tmp_path / 'models.json'

    assert sunspec.convert(source, target, source='test 1') == 1
    catalog = load_catalog(target)

    assert catalog.source == 'test 1'
    assert catalog.get(64999).group == GroupDef(
        name='demo',
        label='Demo',
        points=(
            PointDef('ID', 'uint16', 1),
            PointDef('L', 'uint16', 1),
            PointDef('W', 'int16', 1, sf='W_SF', units='W', label='Watts'),
            PointDef('WMax', 'uint16', 1, writable=True),
            PointDef('W_SF', 'sunssf', 1),
        ),
        groups=(GroupDef('rep', points=(PointDef('V', 'uint16', 1),), count=0),),
    )


@pytest.mark.parametrize(
    'point,datatype',
    [
        (PointDef('a', 'acc32', 2), 'uint32'),
        (PointDef('a', 'sunssf', 1), 'int16'),
        (PointDef('a', 'enum16', 1), 'uint16'),
        (PointDef('a', 'string', 8), 'string16'),
        (PointDef('a', 'float32', 2), 'float32'),
        (PointDef('a', 'pad', 1), None),
        (PointDef('a', 'ipaddr', 2), 'ipv4'),
        (PointDef('a', 'eui48', 4), None),
    ],
)
def test_datatype_of_a_point(point, datatype):
    assert point.datatype == datatype


@pytest.mark.parametrize(
    'text,ref',
    [
        ('103.W', sunspec.PointRef(103, 1, ('W',))),
        ('103:2.W', sunspec.PointRef(103, 2, ('W',))),
        ('160.module.2.DCW', sunspec.PointRef(160, 1, ('module', 2, 'DCW'))),
        (' 103.W ', sunspec.PointRef(103, 1, ('W',))),
    ],
)
def test_item_address_syntax(text, ref):
    assert sunspec.PointRef.parse(text) == ref
    assert str(ref) == text.strip()


@pytest.mark.parametrize('text', ['103', 'W', 'abc.W', '103:0.W', '103:x.W', '103..W', '160.module.0.DCW'])
def test_malformed_item_addresses_are_rejected(text):
    with pytest.raises(SunSpecError, match='modBusSunSpec'):
        sunspec.PointRef.parse(text)


@pytest.mark.parametrize(
    'text,name', [('103.W', 'W'), ('160.module.2.DCW', 'DCW'), ('160.DCW_SF', 'DCW_SF'), ('705.Crv.1.Pt.3.V', 'V')]
)
def test_addresses_resolve_to_point_definitions(text, name):
    assert CATALOG.point(sunspec.PointRef.parse(text)).name == name


@pytest.mark.parametrize(
    'text,message',
    [
        ('103.Watts', "103: no point 'Watts'"),
        ('9999.W', 'unknown SunSpec model 9999'),
        ('160.module.DCW', '160.module: repeated group needs an index'),
        ('160.DCW', "160: no point 'DCW'"),
        ('103.W.1', '103.W: not a group'),
        ('160.module.2', '160.module.2: names a group, not a point'),
    ],
)
def test_addresses_not_in_the_definitions_are_reported(text, message):
    with pytest.raises(SunSpecError, match=message):
        CATALOG.point(sunspec.PointRef.parse(text))


def model_registers(model_id: int, length: int) -> list[int]:
    return [model_id, length] + [0] * length


def test_layout_of_a_fixed_model():
    located = sunspec.layout(CATALOG.get(103), model_registers(103, 50))

    assert (located[('W',)].offset, located[('W',)].sf_offset) == (14, 15)
    assert located[('A',)].sf_offset == 6
    assert located[('W_SF',)].sf_offset is None


def test_layout_repeats_fill_groups_to_the_model_length():
    located = sunspec.layout(CATALOG.get(160), model_registers(160, 8 + 2 * 20))

    assert located[('module', 2, 'DCW')].offset == 10 + 20 + 11
    assert located[('module', 2, 'DCW')].sf_offset == 4
    assert ('module', 3, 'DCW') not in located


def test_layout_repeats_counted_groups_as_often_as_the_device_says():
    model = sunspec.ModelDef(
        64999,
        GroupDef(
            'demo',
            points=(PointDef('ID', 'uint16', 1), PointDef('L', 'uint16', 1), PointDef('N', 'count', 1)),
            groups=(
                GroupDef(
                    'rep',
                    count='N',
                    points=(PointDef('V', 'uint16', 1, sf='V_SF'), PointDef('V_SF', 'sunssf', 1)),
                    groups=(GroupDef('fixed', points=(PointDef('T', 'int16', 1, sf=-1),)),),
                ),
            ),
        ),
    )
    registers = [64999, 10, 3] + [0] * 9

    located = sunspec.layout(model, registers)

    assert located[('rep', 3, 'V')].offset == 3 + 2 * 3
    assert located[('rep', 3, 'V')].sf_offset == 3 + 2 * 3 + 1
    assert (located[('rep', 1, 'fixed', 'T')].offset, located[('rep', 1, 'fixed', 'T')].sf_constant) == (5, -1)
    assert ('rep', 4, 'V') not in located


def test_layout_skips_points_beyond_a_short_model():
    located = sunspec.layout(CATALOG.get(103), model_registers(103, 10))

    assert ('A',) in located
    assert ('W',) not in located


@pytest.mark.parametrize('model_id', sorted(CATALOG.models))
def test_every_shipped_model_lays_out(model_id):
    located = sunspec.layout(CATALOG.get(model_id), model_registers(model_id, 300))

    assert ('ID',) in located


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize('base', [40000, 50000, 0])
def test_scan_finds_the_model_chain_at_any_base_address(base):
    device = image(base, model(1, [0] * 66), model(103, [0] * 50), model(103, [0] * 50), model(160, [0] * 48))

    locations = run(sunspec.scan(reader(device)))

    assert [(m.model, m.instance, m.start, m.length) for m in locations] == [
        (1, 1, base + 2, 66),
        (103, 1, base + 70, 50),
        (103, 2, base + 122, 50),
        (160, 1, base + 174, 48),
    ]


def test_scan_without_marker_is_reported():
    with pytest.raises(SunSpecError, match='no SunSpec marker'):
        run(sunspec.scan(reader({40000: 1, 40001: 2})))


def test_scan_stops_at_an_unreadable_chain():
    device = image(40000, model(1, [0] * 66))
    del device[40002 + 68]

    with pytest.raises(SunSpecError, match='model chain unreadable at 40070'):
        run(sunspec.scan(reader(device)))


def test_read_model_respects_the_request_limit():
    device = image(40000, model(64, list(range(300))))
    requests = []
    location = sunspec.ModelLocation(64, 1, 40002, 300)

    registers = run(sunspec.read_model(reader(device, requests), location))

    assert registers == [64, 300, *range(300)]
    assert requests == [(40002, 125), (40127, 125), (40252, 52)]


def test_describe_lists_points_with_their_addresses_and_values():
    body = [0] * 50
    body[12], body[13] = 1234, 0xFFFF
    body[0], body[4] = 0xFFFF, 0xFFFF  # A not implemented, A_SF -1
    location = sunspec.ModelLocation(103, 2, 40070, 50)

    rows = {str(row.ref): row for row in sunspec.describe(location, CATALOG.get(103), model(103, body))}

    assert rows['103:2.W'].value == pytest.approx(123.4)
    assert rows['103:2.W'].point.units == 'W'
    assert rows['103:2.A'].value is None
    assert '103:2.ID' in rows


def test_scan_command_prints_the_points_of_a_device(modbus_server, capsys):
    body = [0] * 50
    body[12] = 1234
    registers = image(40000, model(1, [0x4163, 0x6D65] + [0] * 64), model(103, body))
    server = modbus_server(1, {40000: [registers[a] for a in sorted(registers)]})

    sunspec.main(['scan', '--host', server.host, '--port', str(server.port), '--unit', '1'])

    out = capsys.readouterr().out
    assert 'model 103 inverter_three_phase at 40070' in out
    assert any(line.split()[:2] == ['103.W', '1234'] for line in out.splitlines())
    assert any(line.split()[:2] == ['1.Mn', 'Acme'] for line in out.splitlines())
