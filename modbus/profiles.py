"""
Device profiles: register maps as data, turned into item structs.

A profile is ``profiles/<vendor>/<device>.yaml``: a tree of nodes below ``groups``. A node with
``address`` reads or writes a register (``bit``, ``round``, ``invalid`` and the value list ``values``
refine it);
``type``, ``description`` and ``attributes`` shape the item; every other mapping-valued key is a
child node (also one named like a node key). Top-level
groups become sub-structs; a point is read-only unless its ``direction`` says otherwise, and a point
with a write direction gets a ``remark`` naming it. Two targets:

- shipped profiles are generated into plugin.yaml, between the marker comments inside
  ``item_structs`` -> ``struct: modbus.<vendor>.<device>[.<group>]``
- ``export`` writes one profile to ``<conf>/structs/modbus_<vendor>.yaml``
  -> ``struct: my.modbus_<vendor>.<device>[.<group>]``, read-only unless ``--writable``

Command line, from the SmartHomeNG base directory::

    python -m plugins.modbus.profiles generate
    python -m plugins.modbus.profiles check
    python -m plugins.modbus.profiles export e3dc.s10 --structs-dir etc/../structs [--writable]
    python -m plugins.modbus.profiles import-struct huawei [--source <plugin.yaml>] [--profile-dir <dir>]

``import-struct`` writes the ``item_structs`` of a vendor in a plugin.yaml (default: modbus_tcp's) as
profiles, see ``import_structs``; run ``generate`` afterwards for shipped ones.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from ruamel.yaml import YAML, YAMLError

import lib.constants

from . import attributes
from .codec import default_registry, word_ordered
from .model import Direction, Endian, Table

PLUGIN_DIR = pathlib.Path(__file__).parent
PROFILE_DIR = PLUGIN_DIR / 'profiles'
PLUGIN_YAML = PLUGIN_DIR / 'plugin.yaml'
MODBUS_TCP_YAML = PLUGIN_DIR.parent / 'modbus_tcp' / 'plugin.yaml'

BEGIN = '    # >>> generated from profiles/ by `python -m plugins.modbus.profiles generate` - do not edit'
END = '    # <<< end of generated profiles'

StructTree = dict[str, Any]
"""An item struct as nested dicts, ready to dump as YAML."""


class ProfileError(ValueError):
    """A profile file is malformed; the message starts with its location."""


@dataclass(frozen=True)
class PointDef:
    """
    The register binding of a node.

    The unit id is not part of a point: it comes from the plugin instance (``slaveUnit``).
    """

    address: int
    datatype: str = 'uint16'
    table: Table = Table.HOLDING_REGISTER
    factor: float = 1.0
    byte_order: Endian | None = None
    word_order: Endian | None = None
    direction: Direction | None = None
    bit: int | None = None
    values: tuple[tuple[Any, Any], ...] = ()
    decimals: int | None = None
    invalid: tuple[int | float, ...] = ()


@dataclass(frozen=True)
class NodeDef:
    """
    One item of a profile tree.

    :param point: register binding; None for containers and helper items
    :param item_type: shng item type; required for points
    :param description: becomes the item's ``name``
    :param attributes: further item attributes, copied verbatim (``on_change``, ``cache``, ...)
    :param children: child items
    """

    name: str
    point: PointDef | None = None
    item_type: str | None = None
    description: str = ''
    attributes: tuple[tuple[str, Any], ...] = ()
    children: tuple[NodeDef, ...] = ()


@dataclass(frozen=True)
class ProfileDef:
    """
    A device type.

    :param tier: ``shipped`` = generated into plugin.yaml, ``optional`` = export only
    :param groups: top-level nodes of the device
    :param tested_with: models confirmed on real hardware
    :param byte_order, word_order: defaults for points that don't set their own
    """

    vendor: str
    device: str
    title: str
    tier: Literal['shipped', 'optional']
    groups: tuple[NodeDef, ...]
    tested_with: tuple[str, ...] = ()
    byte_order: Endian = Endian.BIG
    word_order: Endian = Endian.BIG

    @property
    def id(self) -> str:
        """``<vendor>.<device>``."""
        return f'{self.vendor}.{self.device}'


# --- loading ---

_PROFILE_KEYS = {'vendor', 'device', 'title', 'tier', 'tested_with', 'defaults', 'groups'}
_POINT_KEYS = {
    'address',
    'datatype',
    'table',
    'factor',
    'byte_order',
    'word_order',
    'direction',
    'bit',
    'values',
    'round',
    'invalid',
}
_NODE_KEYS = _POINT_KEYS | {'type', 'description', 'attributes'}
_MAPPING_KEYS = {'attributes', 'values'}
"""Node keys with mapping values; all other mapping-valued keys are children."""
_POINT_TYPES = ('num', 'bool', 'str', 'foo', 'datetime', 'timestamp')
_RESERVED_NAMES = {
    value for name, value in vars(lib.constants).items() if name.startswith('KEY_') and isinstance(value, str)
}


def load_all(profile_dir: pathlib.Path = PROFILE_DIR) -> list[ProfileDef]:
    """All profiles below ``profile_dir``, sorted by id; raises ProfileError on the first malformed one."""
    return sorted(
        (load(path, path.relative_to(profile_dir).as_posix()) for path in profile_dir.glob('*/*.yaml')),
        key=lambda p: p.id,
    )


def load(path: pathlib.Path, location: str) -> ProfileDef:
    """Profile from ``path``; ``location`` prefixes error messages."""
    try:
        raw = YAML(typ='safe').load(path.read_text())
    except YAMLError as e:
        raise ProfileError(f'{location}: {e}') from None
    if not isinstance(raw, dict):
        raise ProfileError(f'{location}: not a mapping')
    _no_unknown_keys(raw, _PROFILE_KEYS, location)

    tier = raw.get('tier', 'optional')
    if tier not in ('shipped', 'optional'):
        raise ProfileError(f'{location}: tier must be shipped or optional, not {tier!r}')
    defaults = raw.get('defaults') or {}
    _no_unknown_keys(defaults, {'byte_order', 'word_order'}, f'{location}: defaults')
    profile_orders = {
        name: _endian(defaults.get(name), Endian.BIG, f'{location}: defaults: {name}')
        for name in ('byte_order', 'word_order')
    }

    groups = raw.get('groups')
    if not isinstance(groups, dict) or not groups:
        raise ProfileError(f'{location}: groups missing')
    return ProfileDef(
        vendor=_required_str(raw, 'vendor', location),
        device=_required_str(raw, 'device', location),
        title=_required_str(raw, 'title', location),
        tier=tier,
        groups=tuple(_node(name, body, location, name) for name, body in groups.items()),
        tested_with=tuple(str(model) for model in raw.get('tested_with') or ()),
        **profile_orders,
    )


def _node(name: str, raw: Any, location: str, path: str) -> NodeDef:
    """Node from ``raw``; every mapping-valued key except ``attributes`` and ``values`` is a child, even ``factor``."""
    where = f'{location}: {path}'
    if not isinstance(raw, dict):
        raise ProfileError(f'{where}: not a mapping')
    children = {key: value for key, value in raw.items() if isinstance(value, dict) and key not in _MAPPING_KEYS}
    reserved = sorted(set(children) & _RESERVED_NAMES)
    if reserved:
        raise ProfileError(f'{location}: {path}.{reserved[0]}: reserved item attribute name, not usable as child')
    raw = {key: value for key, value in raw.items() if key not in children}
    _no_unknown_keys(raw, _NODE_KEYS, where)
    extra = raw.get('attributes') or {}
    if not isinstance(extra, dict):
        raise ProfileError(f'{where}: attributes must be a mapping')

    point = None
    item_type = raw.get('type')
    if 'address' in raw:
        point = _point(raw, where)
        if item_type not in _POINT_TYPES:
            raise ProfileError(f'{where}: type must be one of {", ".join(_POINT_TYPES)}, not {item_type!r}')
    elif set(raw) & (_POINT_KEYS - {'address'}):
        raise ProfileError(f'{where}: register keys without address')

    return NodeDef(
        name=name,
        point=point,
        item_type=None if item_type is None else str(item_type),
        description=str(raw.get('description', '')),
        attributes=tuple(extra.items()),
        children=tuple(_node(child, body, location, f'{path}.{child}') for child, body in children.items()),
    )


def _point(raw: dict, where: str) -> PointDef:
    if not isinstance(raw['address'], int):
        raise ProfileError(f'{where}: address must be an integer')
    datatype = str(raw.get('datatype', 'uint16'))
    try:
        codec = default_registry().resolve(datatype)
    except KeyError:
        raise ProfileError(f'{where}: unknown datatype {datatype!r}') from None
    bit = raw.get('bit')
    if bit is not None and (not isinstance(bit, int) or not 0 <= bit < 16 * codec.register_count(datatype)):
        raise ProfileError(f'{where}: bit {bit} is outside {datatype}')
    values = raw.get('values', {})
    if not isinstance(values, dict):
        raise ProfileError(f'{where}: values must be a mapping')
    decimals = raw.get('round')
    if decimals is not None and (not isinstance(decimals, int) or decimals < 0):
        raise ProfileError(f'{where}: round must be a number of decimals')
    try:
        attributes.parse_invalid(raw.get('invalid'))
    except ValueError:
        raise ProfileError(f'{where}: invalid must be a list of numbers') from None
    try:
        table = Table(raw.get('table', Table.HOLDING_REGISTER.value))
        factor = float(raw.get('factor', 1.0))
        direction = None if raw.get('direction') is None else Direction(raw['direction'])
    except ValueError as e:
        key = 'direction' if 'Direction' in str(e) else 'table/factor'
        raise ProfileError(f'{where}: {key}: {e}') from None
    return PointDef(
        address=raw['address'],
        datatype=datatype,
        table=table,
        factor=factor,
        byte_order=_endian(raw.get('byte_order'), None, f'{where}: byte_order'),
        word_order=_endian(raw.get('word_order'), None, f'{where}: word_order'),
        direction=direction,
        bit=bit,
        values=tuple(values.items()),
        decimals=decimals,
        invalid=tuple(raw.get('invalid') or ()),
    )


def _endian(raw: Any, default: Any, location: str) -> Any:
    if raw is None:
        return default
    try:
        return Endian.parse(raw)
    except ValueError as e:
        raise ProfileError(f'{location}: {e}') from None


def _required_str(raw: dict, key: str, location: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ProfileError(f'{location}: {key} missing')
    return value


def _no_unknown_keys(raw: Mapping, allowed: set[str], location: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ProfileError(f'{location}: unknown key(s) {", ".join(unknown)}')


# --- struct generation ---


def to_struct(profile: ProfileDef, writable: bool = True) -> StructTree:
    """
    Struct tree of one device: one sub-struct per group.

    With ``writable`` False every point reads only: a ``read_write`` point becomes ``read``, a
    ``write`` point loses its register attributes (the item stays, unbound). The ``remark`` naming
    the profile's write direction stays either way.
    """
    return {group.name: _item(profile, group, writable) for group in profile.groups}


def _item(profile: ProfileDef, node: NodeDef, writable: bool) -> StructTree:
    item: StructTree = {}
    if node.item_type:
        item['type'] = node.item_type
    if node.description:
        item['name'] = node.description
    point = node.point
    if point:
        direction = point.direction or Direction.READ
        if not writable:
            direction = Direction.READ if direction.reads else None
        if direction:
            attrs = _register_attributes(profile, point, direction)
            item.update({f'{name}@instance': value for name, value in attrs})
        if point.direction and point.direction.writes:
            item['remark'] = f'writable ({attributes.DIRECTION}: {point.direction.value})'
    item.update(node.attributes)
    item.update({child.name: _item(profile, child, writable) for child in node.children})
    return item


def _register_attributes(profile: ProfileDef, point: PointDef, direction: Direction) -> list[tuple[str, Any]]:
    attrs: list[tuple[str, Any]] = [(attributes.ADDRESS, point.address), (attributes.DATATYPE, point.datatype)]
    if point.table is not Table.HOLDING_REGISTER:
        attrs.append((attributes.TABLE, point.table.value))
    if point.factor != 1:
        attrs.append((attributes.FACTOR, point.factor))
    orders = [(attributes.BYTE_ORDER, point.byte_order or profile.byte_order)]
    if word_ordered(default_registry(), point.datatype):
        orders.append((attributes.WORD_ORDER, point.word_order or profile.word_order))
    attrs += [(name, f'Endian.{order.name}') for name, order in orders if order is not Endian.BIG]
    if point.bit is not None:
        attrs.append((attributes.BIT, point.bit))
    if point.values:
        attrs.append((attributes.LOOKUP, repr(dict(point.values))))
    if point.decimals is not None:
        attrs.append((attributes.ROUND, point.decimals))
    if point.invalid:
        attrs.append((attributes.INVALID, list(point.invalid)))
    attrs.append((attributes.DIRECTION, direction.value))
    return attrs


def vendor_trees(profiles: list[ProfileDef]) -> dict[str, StructTree]:
    """Vendor -> device -> struct tree, for the given profiles."""
    trees: dict[str, StructTree] = {}
    for profile in profiles:
        trees.setdefault(profile.vendor, {})[profile.device] = to_struct(profile)
    return trees


def _dump(data: Mapping[str, Any]) -> str:
    yaml = YAML()
    yaml.indent(mapping=4, sequence=4, offset=0)
    yaml.width = 4096
    stream = io.StringIO()
    yaml.dump(dict(data), stream)
    return stream.getvalue()


# --- plugin.yaml target ---


def _block(trees: Mapping[str, StructTree]) -> str:
    body = ''.join(f'    {line}\n' if line else '\n' for line in _dump(trees).splitlines()) if trees else ''
    return f'{BEGIN}\n{body}{END}\n'


def _split(text: str, plugin_yaml: pathlib.Path) -> tuple[str, str, str]:
    """plugin.yaml text before, inside and after the generated block (inside empty if absent)."""
    if BEGIN in text:
        start = text.index(BEGIN)
        end = text.index(END, start) + len(END) + 1
        return text[:start], text[start:end], text[end:]
    marker = '\nitem_structs:'
    if marker not in text:
        raise ProfileError(f'{plugin_yaml}: no item_structs section')
    position = text.index('\n', text.index(marker) + 1) + 1
    return text[:position], '', text[position:]


def generate(profile_dir: pathlib.Path = PROFILE_DIR, plugin_yaml: pathlib.Path = PLUGIN_YAML) -> None:
    """Write all shipped profiles into the generated block of ``plugin_yaml``."""
    shipped = [p for p in load_all(profile_dir) if p.tier == 'shipped']
    before, _, after = _split(plugin_yaml.read_text(), plugin_yaml)
    plugin_yaml.write_text(before + _block(vendor_trees(shipped)) + after)


def check(profile_dir: pathlib.Path = PROFILE_DIR, plugin_yaml: pathlib.Path = PLUGIN_YAML) -> list[str]:
    """Vendors whose generated structs in ``plugin_yaml`` differ from the shipped profiles."""
    shipped = vendor_trees([p for p in load_all(profile_dir) if p.tier == 'shipped'])
    _, block, _ = _split(plugin_yaml.read_text(), plugin_yaml)
    stored = YAML(typ='safe').load('\n'.join(line[4:] for line in block.splitlines()[1:-1])) or {} if block else {}
    return sorted(vendor for vendor in set(shipped) | set(stored) if shipped.get(vendor) != stored.get(vendor))


# --- modbus_tcp struct import ---

_STRUCT_POINT_KEYS = {
    f'{attributes.ADDRESS}@instance': 'address',
    f'{attributes.DATATYPE}@instance': 'datatype',
    f'{attributes.FACTOR}@instance': 'factor',
    f'{attributes.DIRECTION}@instance': 'direction',
}
_STRUCT_DEFAULTS = {'factor': 1, 'direction': Direction.READ.value}


def modbus_tcp_structs(vendor: str, source: pathlib.Path = MODBUS_TCP_YAML) -> dict[str, StructTree]:
    """Device -> struct tree below ``item_structs: <vendor>`` of a plugin.yaml (default: modbus_tcp's)."""
    try:
        structs = (YAML(typ='safe').load(source.read_text()) or {}).get('item_structs') or {}
    except (OSError, YAMLError) as e:
        raise ProfileError(f'{source}: {e}') from None
    devices = structs.get(vendor)
    if not isinstance(devices, dict) or not devices:
        raise ProfileError(f'{source}: no item_structs for vendor {vendor!r}')
    return devices


def import_structs(devices: Mapping[str, StructTree], vendor: str, profile_dir: pathlib.Path) -> list[pathlib.Path]:
    """
    Write modbus_tcp item structs (device -> struct tree) as profiles ``profile_dir/<vendor>/<device>.yaml``.

    The inverse of ``to_struct`` for the attributes modbus_tcp structs use: the register attributes
    ``modBusAddress``, ``modBusDataType``, ``modBusFactor`` and ``modBusDirection`` (``@instance``) become
    point keys, a factor of 1 and the direction ``read`` are left out; ``type`` stays, ``name`` becomes
    ``description``, every other scalar attribute goes to ``attributes``, mappings are child nodes. A
    child named like a reserved item attribute (e.g. ``type``) is renamed to ``<parent>_<name>``.

    An existing profile file keeps everything above ``groups:`` (comments, title, tier, ...); a new
    one gets tier ``optional``. Returns the written files.

    :raises ProfileError: a struct uses a register attribute the import does not translate
    """
    written = []
    for device, tree in devices.items():
        path = profile_dir / vendor / f'{device}.yaml'
        if path.exists():
            text = path.read_text()
            head = text[: text.index('\ngroups:\n') + 1]
        else:
            head = _dump(
                {
                    'vendor': vendor,
                    'device': device,
                    'title': f'{vendor} {device}',
                    'tier': 'optional',
                    'tested_with': [],
                }
            )
            head = '# Imported from modbus_tcp item structs.\n' + head
        groups = _struct_children(tree, device, f'{vendor}.{device}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(head + _dump({'groups': groups}))
        written.append(path)
    return written


def _struct_children(tree: StructTree, parent: str, where: str) -> dict[str, Any]:
    children = {}
    for name, body in tree.items():
        if isinstance(body, dict):
            child = f'{parent}_{name}' if name in _RESERVED_NAMES else name
            children[child] = _struct_node(body, child, f'{where}.{name}')
    return children


def _struct_node(tree: StructTree, name: str, where: str) -> dict[str, Any]:
    """Profile node of one struct item: type, description, point keys, attributes, then children."""
    unknown = sorted(key for key in tree if key.startswith('modBus') and key not in _STRUCT_POINT_KEYS)
    if unknown:
        raise ProfileError(f'{where}: register attribute {unknown[0]} is not translated by the import')
    node: dict[str, Any] = {}
    if 'type' in tree and not isinstance(tree['type'], dict):
        node['type'] = tree['type']
    if 'name' in tree and not isinstance(tree['name'], dict):
        node['description'] = tree['name']
    for struct_key, key in _STRUCT_POINT_KEYS.items():
        if struct_key in tree and tree[struct_key] != _STRUCT_DEFAULTS.get(key):
            node[key] = tree[struct_key]
    extra = {
        key: value
        for key, value in tree.items()
        if not isinstance(value, dict) and key not in ('type', 'name') and key not in _STRUCT_POINT_KEYS
    }
    if extra:
        node['attributes'] = extra
    node.update(_struct_children(tree, name, where))
    return node


# --- local export ---


def export(
    profile_dir: pathlib.Path, profile_id: str, structs_dir: pathlib.Path, writable: bool = False
) -> pathlib.Path:
    """
    Write profile ``<vendor>.<device>`` into ``structs_dir/modbus_<vendor>.yaml``, keeping other devices.

    Read-only unless ``writable`` (see ``to_struct``).
    """
    profile = next((p for p in load_all(profile_dir) if p.id == profile_id), None)
    if profile is None:
        raise ProfileError(f'{profile_id}: no such profile')
    path = structs_dir / f'modbus_{profile.vendor}.yaml'
    existing = YAML(typ='safe').load(path.read_text()) if path.exists() else None
    content = dict(existing or {})
    content[profile.device] = to_struct(profile, writable)
    structs_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump(content))
    return path


def main(argv: list[str] | None = None) -> int:
    """Command line entry point; returns the exit code."""
    parser = argparse.ArgumentParser(prog='python -m plugins.modbus.profiles', description=__doc__.split('\n\n')[0])
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('generate', help='write the shipped profiles into plugin.yaml')
    commands.add_parser('check', help='exit 1 if plugin.yaml is not up to date')
    export_cmd = commands.add_parser('export', help='write one profile to a local structs directory')
    export_cmd.add_argument('profile', help='<vendor>.<device>, e.g. e3dc.s10')
    export_cmd.add_argument('--structs-dir', type=pathlib.Path, required=True)
    export_cmd.add_argument('--writable', action='store_true', help='keep the write directions of the profile')
    import_cmd = commands.add_parser('import-struct', help="write a vendor's modbus_tcp item structs as profiles")
    import_cmd.add_argument('vendor', help='key below item_structs, e.g. huawei')
    import_cmd.add_argument(
        '--source', type=pathlib.Path, default=MODBUS_TCP_YAML, help='default: modbus_tcp plugin.yaml'
    )
    import_cmd.add_argument('--profile-dir', type=pathlib.Path, default=PROFILE_DIR)
    args = parser.parse_args(argv)
    try:
        if args.command == 'generate':
            generate()
        elif args.command == 'check':
            stale = check()
            if stale:
                print(f'plugin.yaml is out of date for: {", ".join(stale)}; run generate', file=sys.stderr)
                return 1
        elif args.command == 'import-struct':
            for path in import_structs(modbus_tcp_structs(args.vendor, args.source), args.vendor, args.profile_dir):
                print(path)
        else:
            print(export(PROFILE_DIR, args.profile, args.structs_dir, args.writable))
    except ProfileError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
