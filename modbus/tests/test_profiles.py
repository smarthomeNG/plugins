"""Profiles: loading and validation, struct generation, plugin.yaml block, local export."""

import pathlib
import textwrap

import pytest
from ruamel.yaml import YAML

from plugins.modbus import profiles
from plugins.modbus.profiles import ProfileError

PLUGIN_YAML = textwrap.dedent(
    """\
    plugin:
        classname: Modbus   # keep me

    item_structs:
        handmade:
            value:
                type: num
                modBusAddress@instance: 1

    plugin_functions: NONE
    """
)

PROFILE = textwrap.dedent(
    """\
    vendor: acme
    device: meter
    title: ACME meter
    tier: shipped
    defaults:
        word_order: little
    groups:
        power:
            description: Power values
            active:
                address: 100
                datatype: int32
                type: num
                description: Active power W
            total:
                address: 102
                datatype: uint64
                type: num
                factor: 0.1
                word_order: big
                table: InputRegister
            phases:
                l1:
                    address: 110
                    type: num
        mode:
            type: str
            attributes:
                cache: true
                on_change: .register = sh..reverse(key=value)
            reverse:
                type: dict
                attributes:
                    initial_value: "{'off': 0, 'on': 1}"
            register:
                address: 120
                type: num
                direction: read_write
                attributes:
                    on_change: .. = 'on' if value else 'off'
        settings:
            limit:
                address: 200
                datatype: uint16
                type: num
                direction: read_write
    """
)


def write(path: pathlib.Path, text: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def load_yaml(path: pathlib.Path):
    return YAML(typ='safe').load(path.read_text())


@pytest.fixture
def profile_dir(tmp_path):
    write(tmp_path / 'profiles' / 'acme' / 'meter.yaml', PROFILE)
    return tmp_path / 'profiles'


def test_struct_tree_of_a_profile(profile_dir):
    (profile,) = profiles.load_all(profile_dir)
    tree = profiles.to_struct(profile)

    assert tree['power']['active'] == {
        'type': 'num',
        'name': 'Active power W',
        'modBusAddress@instance': 100,
        'modBusDataType@instance': 'int32',
        'modBusWordOrder@instance': 'Endian.LITTLE',
        'modBusDirection@instance': 'read',
    }
    assert tree['power']['total'] == {
        'type': 'num',
        'modBusAddress@instance': 102,
        'modBusDataType@instance': 'uint64',
        'modBusObjectType@instance': 'InputRegister',
        'modBusFactor@instance': 0.1,
        'modBusDirection@instance': 'read',
    }
    assert tree['power']['phases']['l1'] == {
        'type': 'num',
        'modBusAddress@instance': 110,
        'modBusDataType@instance': 'uint16',
        'modBusDirection@instance': 'read',
    }
    assert tree['mode'] == {
        'type': 'str',
        'cache': True,
        'on_change': '.register = sh..reverse(key=value)',
        'reverse': {'type': 'dict', 'initial_value': "{'off': 0, 'on': 1}"},
        'register': {
            'type': 'num',
            'modBusAddress@instance': 120,
            'modBusDataType@instance': 'uint16',
            'modBusDirection@instance': 'read_write',
            'remark': 'writable (modBusDirection: read_write)',
            'on_change': ".. = 'on' if value else 'off'",
        },
    }
    assert tree['settings']['limit'] == {
        'type': 'num',
        'modBusAddress@instance': 200,
        'modBusDataType@instance': 'uint16',
        'modBusDirection@instance': 'read_write',
        'remark': 'writable (modBusDirection: read_write)',
    }


def test_generate_writes_shipped_profiles_into_plugin_yaml(tmp_path, profile_dir):
    plugin_yaml = write(tmp_path / 'plugin.yaml', PLUGIN_YAML)

    assert profiles.check(profile_dir, plugin_yaml) == ['acme']
    profiles.generate(profile_dir, plugin_yaml)

    text = plugin_yaml.read_text()
    assert '# keep me' in text
    meta = load_yaml(plugin_yaml)
    assert meta['item_structs']['handmade']['value']['modBusAddress@instance'] == 1
    assert meta['item_structs']['acme']['meter']['power']['active']['modBusAddress@instance'] == 100
    assert meta['plugin_functions'] == 'NONE'
    assert profiles.check(profile_dir, plugin_yaml) == []

    profiles.generate(profile_dir, plugin_yaml)
    assert plugin_yaml.read_text() == text


def test_check_reports_a_hand_edited_block(tmp_path, profile_dir):
    plugin_yaml = write(tmp_path / 'plugin.yaml', PLUGIN_YAML)
    profiles.generate(profile_dir, plugin_yaml)
    plugin_yaml.write_text(
        plugin_yaml.read_text().replace('modBusAddress@instance: 100', 'modBusAddress@instance: 101')
    )

    assert profiles.check(profile_dir, plugin_yaml) == ['acme']


def test_optional_profiles_stay_out_of_plugin_yaml(tmp_path, profile_dir):
    write(profile_dir / 'acme' / 'meter.yaml', PROFILE.replace('tier: shipped', 'tier: optional'))
    plugin_yaml = write(tmp_path / 'plugin.yaml', PLUGIN_YAML)

    profiles.generate(profile_dir, plugin_yaml)

    assert 'acme' not in load_yaml(plugin_yaml)['item_structs']


def test_export_writes_a_local_struct_file(tmp_path, profile_dir):
    structs = tmp_path / 'structs'
    write(structs / 'modbus_acme.yaml', 'other_device:\n    x:\n        type: num\n')

    path = profiles.export(profile_dir, 'acme.meter', structs)

    assert path == structs / 'modbus_acme.yaml'
    exported = load_yaml(path)
    assert exported['meter']['power']['active']['modBusAddress@instance'] == 100
    assert exported['other_device'] == {'x': {'type': 'num'}}


def test_export_is_read_only_unless_writable(tmp_path, profile_dir):
    structs = tmp_path / 'structs'

    read_only = load_yaml(profiles.export(profile_dir, 'acme.meter', structs))['meter']
    writable = load_yaml(profiles.export(profile_dir, 'acme.meter', structs, writable=True))['meter']

    assert read_only['settings']['limit']['modBusDirection@instance'] == 'read'
    assert read_only['settings']['limit']['remark'] == 'writable (modBusDirection: read_write)'
    assert writable['settings']['limit']['modBusDirection@instance'] == 'read_write'
    assert writable['power']['active']['modBusDirection@instance'] == 'read'


def test_read_only_export_leaves_write_only_points_unbound(tmp_path, profile_dir, monkeypatch):
    monkeypatch.setattr(profiles, 'PROFILE_DIR', profile_dir)
    reset = '        reset:\n            address: 201\n            type: bool\n            direction: write\n'
    write(profile_dir / 'acme' / 'meter.yaml', PROFILE + reset)
    structs = tmp_path / 'structs'

    profiles.main(['export', 'acme.meter', '--structs-dir', str(structs)])
    read_only = load_yaml(structs / 'modbus_acme.yaml')['meter']['settings']['reset']
    profiles.main(['export', 'acme.meter', '--structs-dir', str(structs), '--writable'])
    writable = load_yaml(structs / 'modbus_acme.yaml')['meter']['settings']['reset']

    assert read_only == {'type': 'bool', 'remark': 'writable (modBusDirection: write)'}
    assert writable['modBusDirection@instance'] == 'write'


@pytest.mark.parametrize(
    'change,message',
    [
        (('datatype: int32', 'datatype: int33'), 'acme/meter.yaml: power.active: unknown datatype'),
        (('            address: 100\n', '            adress: 100\n'), 'acme/meter.yaml: power.active: unknown key'),
        (('type: num\n            description', 'type: nmu\n            description'), 'power.active: type'),
        (('factor: 0.1', 'factr: 0.1'), 'power.total: unknown key'),
        (('tier: shipped', 'tier: maybe'), 'acme/meter.yaml: tier'),
        (('word_order: big', 'word_order: middle'), 'power.total: word_order'),
        (('direction: read_write', 'direction: both'), 'mode.register: direction'),
        (('address: 110\n                type: num', 'address: 110'), 'power.phases.l1: type'),
        (('    settings:\n', '    settings:\n        writable: true\n'), 'settings: unknown key'),
        (
            ('        phases:\n', '        type:\n            address: 130\n            type: num\n        phases:\n'),
            'power.type: reserved',
        ),
        (('address: 200\n', 'address: 200\n            bit: 16\n'), 'settings.limit: bit 16 is outside uint16'),
        (('address: 200\n', 'address: 200\n            values: [1, 2]\n'), 'settings.limit: values'),
        (('address: 200\n', 'address: 200\n            invalid: 32767\n'), 'settings.limit: invalid'),
    ],
)
def test_invalid_profiles_are_reported_with_location(profile_dir, change, message):
    write(profile_dir / 'acme' / 'meter.yaml', PROFILE.replace(*change))

    with pytest.raises(ProfileError, match=message.replace('.', r'\.')):
        profiles.load_all(profile_dir)


def test_shipped_profiles_are_in_sync_with_plugin_yaml():
    plugin_dir = pathlib.Path(profiles.__file__).parent
    assert profiles.check(plugin_dir / 'profiles', plugin_dir / 'plugin.yaml') == []


FLAGS = textwrap.dedent(
    """\
    vendor: acme
    device: vent
    title: ACME ventilation
    defaults:
        word_order: little
    groups:
        state:
            address: 10
            type: num
            away:
                address: 10
                bit: 4
                type: bool
                direction: read_write
            text:
                address: 10
                type: str
                values:
                    0: Standby
                    1: Manual
        since:
            address: 20
            datatype: datetime32
            type: datetime
        temp:
            address: 40
            datatype: float32
            round: 1
            type: num
        sensor:
            address: 50
            datatype: int16
            invalid: [32767]
            type: num
        ip:
            address: 30
            datatype: ipv4
            type: str
    """
)


def test_bits_value_lists_and_word_ordered_datatypes(tmp_path):
    write(tmp_path / 'profiles' / 'acme' / 'vent.yaml', FLAGS)
    (profile,) = profiles.load_all(tmp_path / 'profiles')
    tree = profiles.to_struct(profile)

    assert tree['state']['away']['modBusBit@instance'] == 4
    assert tree['state']['text']['modBusLookup@instance'] == "{0: 'Standby', 1: 'Manual'}"
    assert 'values' not in tree['state']['text']
    assert tree['since']['type'] == 'datetime'
    assert tree['since']['modBusWordOrder@instance'] == 'Endian.LITTLE'
    assert tree['ip']['modBusWordOrder@instance'] == 'Endian.LITTLE'
    assert tree['temp']['modBusRound@instance'] == 1
    assert tree['sensor']['modBusInvalid@instance'] == [32767]
