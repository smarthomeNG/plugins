"""Importing modbus_tcp item structs as profiles."""

import pathlib

import pytest

from plugins.modbus import profiles
from plugins.modbus.profiles import ProfileError

DEVICES = {
    'meter': {
        'power': {
            'type': 'num',
            'modBusAddress@instance': 100,
            'modBusDataType@instance': 'int32',
            'modBusFactor@instance': 0.001,
            'modBusDirection@instance': 'read',
            'description': 'kW',
            'phase_a': {
                'type': 'num',
                'modBusAddress@instance': 102,
                'modBusDataType@instance': 'uint16',
                'modBusFactor@instance': 1,
                'modBusDirection@instance': 'read',
            },
        },
        'limit': {
            'type': 'num',
            'name': 'Feed-in limit',
            'modBusAddress@instance': 200,
            'modBusDataType@instance': 'uint16',
            'modBusFactor@instance': 1,
            'modBusDirection@instance': 'read_write',
            'cache': True,
        },
    }
}


def imported(tmp_path: pathlib.Path, devices: dict = DEVICES) -> list[profiles.ProfileDef]:
    profiles.import_structs(devices, 'acme', tmp_path)
    return profiles.load_all(tmp_path)


def test_an_imported_device_generates_its_struct_again(tmp_path):
    (profile,) = imported(tmp_path)
    assert profile.id == 'acme.meter'
    assert profiles.to_struct(profile) == {
        'power': {
            'type': 'num',
            'modBusAddress@instance': 100,
            'modBusDataType@instance': 'int32',
            'modBusFactor@instance': 0.001,
            'modBusDirection@instance': 'read',
            'description': 'kW',
            'phase_a': {
                'type': 'num',
                'modBusAddress@instance': 102,
                'modBusDataType@instance': 'uint16',
                'modBusDirection@instance': 'read',
            },
        },
        'limit': {
            'type': 'num',
            'name': 'Feed-in limit',
            'modBusAddress@instance': 200,
            'modBusDataType@instance': 'uint16',
            'modBusDirection@instance': 'read_write',
            'remark': 'writable (modBusDirection: read_write)',
            'cache': True,
        },
    }


def test_a_new_profile_is_optional_and_an_existing_one_keeps_its_head(tmp_path):
    (new,) = imported(tmp_path)
    assert new.tier == 'optional'
    path = tmp_path / 'acme' / 'meter.yaml'
    head = '# hand written\nvendor: acme\ndevice: meter\ntitle: ACME meter\ntier: shipped\n'
    path.write_text(head + 'groups:\n    old:\n        type: num\n        address: 1\n')
    (kept,) = imported(tmp_path)
    assert path.read_text().startswith(head + 'groups:\n    power:\n')
    assert (kept.title, kept.tier, [group.name for group in kept.groups]) == (
        'ACME meter',
        'shipped',
        ['power', 'limit'],
    )


def test_a_child_named_like_a_reserved_attribute_is_prefixed_with_its_parent(tmp_path):
    devices = {'meter': {'type': {'code': {'type': 'num', 'modBusAddress@instance': 1}}}}
    (profile,) = imported(tmp_path, devices)
    assert list(profiles.to_struct(profile)) == ['meter_type']


def test_an_untranslated_register_attribute_is_an_error(tmp_path):
    devices = {'meter': {'power': {'type': 'num', 'modBusAddress@instance': 1, 'modBusUnit@instance': 3}}}
    with pytest.raises(ProfileError, match=r'acme\.meter\.power: register attribute modBusUnit@instance'):
        profiles.import_structs(devices, 'acme', tmp_path)


def test_import_struct_command_reads_the_vendor_structs_of_a_plugin_yaml(tmp_path, capsys):
    source = tmp_path / 'plugin.yaml'
    source.write_text(
        'item_structs:\n    acme:\n        meter:\n            power:\n                type: num\n                modBusAddress@instance: 1\n'
    )
    profile_dir = tmp_path / 'profiles'
    assert profiles.main(['import-struct', 'acme', '--source', str(source), '--profile-dir', str(profile_dir)]) == 0
    assert capsys.readouterr().out.split() == [str(profile_dir / 'acme' / 'meter.yaml')]
    assert profiles.main(['import-struct', 'other', '--source', str(source), '--profile-dir', str(profile_dir)]) == 1
    assert "no item_structs for vendor 'other'" in capsys.readouterr().err
