"""Every profile struct, shipped or exported, creates all of its items in SmartHomeNG."""

import pytest

from tests.sdp_harness import load_plugin

from plugins.modbus import profiles
from plugins.modbus.tests.profile_rig import expand_structs, exported_structs

PROFILES = profiles.load_all()


def item_paths(tree: dict, prefix: str) -> list[str]:
    paths = []
    for key, value in tree.items():
        if isinstance(value, dict):
            paths.append(f'{prefix}.{key}')
            paths += item_paths(value, f'{prefix}.{key}')
    return paths


@pytest.mark.parametrize('profile', PROFILES, ids=[p.id for p in PROFILES])
def test_struct_creates_every_item(tmp_path, profile):
    if profile.tier == 'shipped':
        items, structs = f'dev:\n    struct: modbus.{profile.id}\n', None
    else:
        items = f'dev:\n    struct: my.modbus_{profile.vendor}.{profile.device}\n'
        structs = exported_structs(profile.id, tmp_path)
    rig = load_plugin(
        str(tmp_path),
        'plugins.modbus',
        'Modbus',
        expand_structs(items, tmp_path, structs),
        params={'host': '127.0.0.1', 'port': 1, 'cycle': 0},
    )

    missing = [path for path in item_paths(profiles.to_struct(profile), 'dev') if rig.item(path) is None]

    assert not missing
    assert not [message for message in rig.logs.messages() if 'ignored' in message or 'invalid' in message]
