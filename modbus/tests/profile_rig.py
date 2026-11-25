"""Load the modbus plugin with items built from shipped or exported profile structs, and poll once."""

import contextlib
import json
import pathlib
import struct
from collections.abc import Iterator

import lib.config
from lib.shyaml import yaml_load
from tests.sdp_harness import PluginRig, load_plugin

from plugins.modbus import profiles
from plugins.modbus.tests.test_async_io import wait_until

PLUGIN_YAML = pathlib.Path(__file__).parent.parent / 'plugin.yaml'


def exported_structs(profile_id: str, tmp_path: pathlib.Path, writable: bool = False) -> dict:
    """Struct definitions of profile ``<vendor>.<device>`` as exported to a local structs directory."""
    path = profiles.export(profiles.PROFILE_DIR, profile_id, tmp_path / 'structs', writable)
    return {f'my.{path.stem}': yaml_load(str(path), ordered=True)}


def expand_structs(items_yaml: str, tmp_path: pathlib.Path, struct_dict: dict | None = None) -> str:
    """``items_yaml`` with its structs expanded by SmartHomeNG's config parser; default: ``modbus.*`` of plugin.yaml."""
    if struct_dict is None:
        structs = yaml_load(str(PLUGIN_YAML), ordered=True)['item_structs']
        struct_dict = {f'modbus.{name}': definition for name, definition in structs.items()}
    source = tmp_path / 'struct_items.yaml'
    source.write_text(items_yaml)
    return json.dumps(lib.config.parse(str(source), parseitems=True, struct_dict=struct_dict))


@contextlib.contextmanager
def running(tmp_path: pathlib.Path, server, items_yaml: str, struct_dict: dict | None = None) -> Iterator[PluginRig]:
    """Running plugin on ``server`` (a modbus_server handle) with the expanded items, after one complete read."""
    rig = load_plugin(
        str(tmp_path),
        'plugins.modbus',
        'Modbus',
        expand_structs(items_yaml, tmp_path, struct_dict),
        params={'host': server.host, 'port': server.port, 'cycle': 60, 'slaveUnit': server.unit},
    )
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        rig.job(plugin._scheduler_name()).fire()
        wait_until(lambda: plugin._scheduled_read_task is not None and plugin._scheduled_read_task.done())
        yield rig
    finally:
        plugin.stop()


def poll_once(tmp_path: pathlib.Path, server, items_yaml: str, struct_dict: dict | None = None) -> PluginRig:
    """Plugin on ``server`` (a modbus_server handle) with the expanded items, after one complete read; stopped."""
    with running(tmp_path, server, items_yaml, struct_dict) as rig:
        return rig


def text(value: str, count: int) -> list[int]:
    """``value`` as ``count`` registers, two ASCII characters each, NUL padded."""
    return list(struct.unpack(f'>{count}H', value.encode().ljust(count * 2, b'\0')))


def words(fmt: str, value, low_word_first: bool = False) -> list[int]:
    """Registers of ``value`` packed big-endian with struct format ``fmt`` (e.g. ``'>i'``)."""
    raw = struct.pack(fmt, value)
    registers = list(struct.unpack(f'>{len(raw) // 2}H', raw))
    return registers[::-1] if low_word_first else registers
