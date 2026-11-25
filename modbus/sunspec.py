"""
SunSpec: items address points by name, the device tells where its models are.

A SunSpec device holds the marker ``SunS`` at a base address (40000, 50000 or 0), followed by a
chain of models: model id, length ``L`` (registers after the id and length) and the model's
registers, ended by id 0xFFFF. Point names, types, sizes and scale factors come from the model
definitions of the SunSpec Alliance, shipped as ``sunspec_models.json`` (converted from
https://github.com/sunspec/models, Apache-2.0, license in ``sunspec_models.LICENSE``).

Item address syntax (``modBusSunSpec``)::

    103.W                 point W of the first model 103
    103:2.W               point W of the second model 103 on the device
    160.module.2.DCW      point DCW of the second repetition of group ``module``

Command line, from the SmartHomeNG base directory: list the points of a device with their item
addresses and current values, or refresh the shipped definitions from a checkout of sunspec/models::

    python -m plugins.modbus.sunspec scan --host 192.168.0.50 [--port 502] [--unit 1]
    python -m plugins.modbus.sunspec convert <models checkout>/json --source "sunspec/models <commit>"
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import pathlib
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .codec import CodecRegistry, decode_available, default_registry, scale
from .model import Direction, RegisterKey, RegisterSpec, Table, Value
from .transport import UNIT_KWARG, TcpTransport, new_client

CATALOG_FILE = pathlib.Path(__file__).parent / 'sunspec_models.json'
MARKER = (0x5375, 0x6E53)
BASE_ADDRESSES = (40000, 50000, 0)
END_ID = 0xFFFF
HEADER = 2

_DATATYPES = {
    'int16': 'int16',
    'sunssf': 'int16',
    'uint16': 'uint16',
    'enum16': 'uint16',
    'bitfield16': 'uint16',
    'count': 'uint16',
    'acc16': 'uint16',
    'int32': 'int32',
    'uint32': 'uint32',
    'enum32': 'uint32',
    'bitfield32': 'uint32',
    'acc32': 'uint32',
    'int64': 'int64',
    'uint64': 'uint64',
    'acc64': 'uint64',
    'float32': 'float32',
    'ipaddr': 'ipv4',
}


class SunSpecError(ValueError):
    """A model definition, an item address or a device's model chain is not usable."""


# --- model definitions ---


@dataclass(frozen=True)
class PointDef:
    """
    One point of a model definition.

    :param type: SunSpec type, e.g. ``uint16``, ``acc32``, ``sunssf``, ``string``, ``pad``
    :param size: registers the point occupies
    :param sf: scale factor: name of a ``sunssf`` point of this or an enclosing group, or a constant exponent
    :param writable: the definition allows writing (access RW)
    """

    name: str
    type: str
    size: int
    sf: str | int | None = None
    units: str = ''
    label: str = ''
    writable: bool = False

    @property
    def datatype(self) -> str | None:
        """Codec datatype of the point; None for types the plugin does not decode (pad, addresses)."""
        if self.type == 'string':
            return f'string{self.size * 2}'
        return _DATATYPES.get(self.type)


@dataclass(frozen=True)
class GroupDef:
    """
    A group of points, possibly repeated.

    :param count: None = once; 0 = repeated until the model length is used up; a name = repeated
        as often as that ``count`` point (of this or an enclosing group) says
    """

    name: str
    points: tuple[PointDef, ...] = ()
    groups: tuple[GroupDef, ...] = ()
    count: int | str | None = None
    label: str = ''

    @property
    def size(self) -> int:
        """Registers of one repetition, if it contains no repeated groups."""
        if any(group.count is not None for group in self.groups):
            raise SunSpecError(f'{self.name}: size depends on device data')
        return sum(point.size for point in self.points) + sum(group.size for group in self.groups)


@dataclass(frozen=True)
class ModelDef:
    """A SunSpec model; ``group`` starts with the points ``ID`` and ``L``."""

    id: int
    group: GroupDef

    @property
    def name(self) -> str:
        return self.group.name


@dataclass(frozen=True)
class Catalog:
    """All model definitions the plugin knows, by model id."""

    models: Mapping[int, ModelDef]
    source: str = ''

    def get(self, model_id: int) -> ModelDef:
        """Definition of ``model_id``; SunSpecError if unknown."""
        try:
            return self.models[model_id]
        except KeyError:
            raise SunSpecError(f'unknown SunSpec model {model_id}') from None

    def point(self, ref: PointRef) -> PointDef:
        """Definition of the point ``ref`` names; SunSpecError if the definitions have no such point."""
        group = self.get(ref.model).group
        where = str(ref.model)
        elements = list(ref.path)
        while elements:
            element = elements.pop(0)
            if isinstance(element, int):
                raise SunSpecError(f'{where}: group is not repeated, no index allowed')
            where = f'{where}.{element}'
            point = next((p for p in group.points if p.name == element), None)
            if point is not None:
                if elements:
                    raise SunSpecError(f'{where}: not a group')
                return point
            sub = next((g for g in group.groups if g.name == element), None)
            if sub is None:
                raise SunSpecError(f'{where.rpartition(".")[0]}: no point {element!r}')
            if sub.count is not None:
                if not elements or not isinstance(elements[0], int):
                    raise SunSpecError(f'{where}: repeated group needs an index')
                where = f'{where}.{elements.pop(0)}'
            group = sub
        raise SunSpecError(f'{where}: names a group, not a point')


# --- item addresses ---

PathElement = str | int
"""A group or point name, or the 1-based repetition index following a repeated group."""


@dataclass(frozen=True)
class PointRef:
    """
    The SunSpec point an item reads or writes.

    :param model: model id
    :param instance: which model of that id on the device, 1-based
    :param path: group names (each repeated group followed by its index) and the point name
    """

    model: int
    instance: int
    path: tuple[PathElement, ...]

    @classmethod
    def parse(cls, text: str) -> PointRef:
        """Reference from the ``modBusSunSpec`` syntax ``<model>[:<instance>].<group>[.<index>]...<point>``."""
        head, _, rest = text.strip().partition('.')
        model, _, instance = head.partition(':')
        tokens = rest.split('.') if rest else []
        if not model.isdigit() or (instance and not instance.isdigit()) or not tokens or '' in tokens:
            raise SunSpecError(f'modBusSunSpec {text!r}: expected <model>[:<instance>].<point>, e.g. 103.W')
        path = tuple(int(token) if token.isdigit() else token for token in tokens)
        if (instance and int(instance) < 1) or any(isinstance(e, int) and e < 1 for e in path):
            raise SunSpecError(f'modBusSunSpec {text!r}: instances and indices count from 1')
        return cls(int(model), int(instance or 1), path)

    def __str__(self) -> str:
        head = str(self.model) if self.instance == 1 else f'{self.model}:{self.instance}'
        return '.'.join([head, *map(str, self.path)])


# --- device scan ---

Reader = Callable[[int, int], Awaitable[Sequence[int] | None]]
"""Reads ``count`` holding registers from ``address`` of one unit; None on an error response."""

MAX_MODELS = 256
MAX_REQUEST = 125


@dataclass(frozen=True)
class ModelLocation:
    """
    One model on a device.

    :param instance: 1-based count of models with this id up to this one
    :param start: address of the model's ``ID`` register
    :param length: the model's ``L``, registers after ``ID`` and ``L``
    """

    model: int
    instance: int
    start: int
    length: int


async def scan(read: Reader) -> list[ModelLocation]:
    """
    The model chain of a device: marker at the first base address that has it, then id/length pairs.

    :raises SunSpecError: no marker, or the chain ends before the end marker
    """
    for base in BASE_ADDRESSES:
        if tuple(await read(base, 2) or ()) == MARKER:
            break
    else:
        raise SunSpecError(f'no SunSpec marker at {", ".join(map(str, BASE_ADDRESSES))}')

    locations: list[ModelLocation] = []
    seen: dict[int, int] = {}
    address = base + len(MARKER)
    for _ in range(MAX_MODELS):
        header = await read(address, HEADER)
        if header is None or len(header) < HEADER:
            raise SunSpecError(f'model chain unreadable at {address}')
        model_id, length = header[0], header[1]
        if model_id == END_ID:
            return locations
        seen[model_id] = seen.get(model_id, 0) + 1
        locations.append(ModelLocation(model_id, seen[model_id], address, length))
        address += HEADER + length
    raise SunSpecError(f'model chain longer than {MAX_MODELS} models')


async def read_model(read: Reader, location: ModelLocation) -> list[int]:
    """All registers of one model, from its ``ID``, in requests of at most 125 registers."""
    registers: list[int] = []
    end = location.start + HEADER + location.length
    for address in range(location.start, end, MAX_REQUEST):
        chunk = await read(address, min(MAX_REQUEST, end - address))
        if chunk is None:
            raise SunSpecError(f'model {location.model} unreadable at {address}')
        registers.extend(chunk)
    return registers


# --- register layout ---


@dataclass(frozen=True)
class Located:
    """
    Where a point of one model lives on the device.

    :param offset: registers from the model's ``ID`` register
    :param sf_offset: offset of its scale factor point, if the scale factor is a point
    :param sf_constant: its scale factor exponent, if the definition fixes it
    """

    point: PointDef
    offset: int
    sf_offset: int | None = None
    sf_constant: int | None = None


def layout(model: ModelDef, registers: Sequence[int]) -> dict[tuple[PathElement, ...], Located]:
    """
    Positions of a model's points, by path as in :class:`PointRef`.

    Repeated groups are laid out as often as their count says: the value of the count point in
    ``registers``, or as often as they fit for count 0. Points beyond ``registers`` are left out.

    :param registers: the model as read from the device, starting at its ``ID`` register
    """
    located: dict[tuple[PathElement, ...], Located] = {}
    _lay_out(model.group, 0, (), {}, registers, located)
    return located


def _lay_out(
    group: GroupDef,
    offset: int,
    prefix: tuple[PathElement, ...],
    outer: Mapping[str, int],
    registers: Sequence[int],
    located: dict[tuple[PathElement, ...], Located],
) -> int:
    """Lay out one repetition of ``group`` at ``offset``; returns the offset after it."""
    scope = dict(outer)
    positions = []
    for point in group.points:
        scope[point.name] = offset
        positions.append((point, offset))
        offset += point.size
    for point, at in positions:
        if at + point.size > len(registers) or point.type == 'pad':
            continue
        sf_offset = scope.get(point.sf) if isinstance(point.sf, str) else None
        sf_constant = point.sf if isinstance(point.sf, int) else None
        located[(*prefix, point.name)] = Located(point, at, sf_offset, sf_constant)
    for sub in group.groups:
        if sub.count is None:
            offset = _lay_out(sub, offset, (*prefix, sub.name), scope, registers, located)
            continue
        if isinstance(sub.count, str):
            repetitions = registers[scope[sub.count]] if scope.get(sub.count, len(registers)) < len(registers) else 0
        else:
            repetitions = max(0, len(registers) - offset) // sub.size
        for index in range(1, repetitions + 1):
            offset = _lay_out(sub, offset, (*prefix, sub.name, index), scope, registers, located)
    return offset


# --- binding items ---


@dataclass(frozen=True)
class SunSpecItem:
    """
    An item's SunSpec configuration, before the device tells where its point is.

    :param invalid_value: item value for "not available", as ``modBusInvalidValue``
    """

    ref: PointRef
    unit: int
    direction: Direction = Direction.READ
    invalid_value: Value | None = None


@dataclass(frozen=True)
class Resolved:
    """
    A point found on the device.

    :param address: holding register address of the point
    :param sf_address: address of its scale factor point, if the scale factor is a point
    :param sf_constant: its scale factor exponent, if the definition fixes it
    """

    point: PointDef
    address: int
    sf_address: int | None = None
    sf_constant: int | None = None


async def resolve(
    read: Reader, refs: Iterable[PointRef], catalog: Catalog
) -> tuple[dict[PointRef, Resolved], dict[PointRef, str]]:
    """
    Scan one unit and find ``refs`` on it; models are read only if a ref needs them.

    :returns: the points found, and for the others why not
    :raises SunSpecError: the device has no readable model chain
    """
    locations = {(location.model, location.instance): location for location in await scan(read)}
    layouts: dict[tuple[int, int], dict[tuple[PathElement, ...], Located]] = {}
    found: dict[PointRef, Resolved] = {}
    missing: dict[PointRef, str] = {}
    for ref in refs:
        key = (ref.model, ref.instance)
        location = locations.get(key)
        if location is None:
            missing[ref] = f'model {ref.model} instance {ref.instance} not on the device'
            continue
        if key not in layouts:
            layouts[key] = layout(catalog.get(ref.model), await read_model(read, location))
        located = layouts[key].get(ref.path)
        if located is None:
            missing[ref] = 'point not on the device'
            continue
        found[ref] = Resolved(
            located.point,
            location.start + located.offset,
            None if located.sf_offset is None else location.start + located.sf_offset,
            located.sf_constant,
        )
    return found, missing


# --- listing ---


@dataclass(frozen=True)
class Row:
    """One point of a device: its item address, register address and current value (None: not available)."""

    ref: PointRef
    point: PointDef
    address: int
    value: Value | None


def describe(
    location: ModelLocation, model: ModelDef, registers: Sequence[int], codecs: CodecRegistry | None = None
) -> list[Row]:
    """The points of one model on a device, in definition order, scaled like the plugin scales them."""
    codecs = codecs or default_registry()
    return [
        Row(
            PointRef(location.model, location.instance, path),
            located.point,
            location.start + located.offset,
            _value(located, registers, codecs),
        )
        for path, located in layout(model, registers).items()
    ]


def _value(located: Located, registers: Sequence[int], codecs: CodecRegistry) -> Value | None:
    datatype = located.point.datatype
    if datatype is None:
        return None
    try:
        value = decode_available(
            codecs, _spec(datatype), registers[located.offset : located.offset + located.point.size]
        )
        exponent = located.sf_constant
        if located.sf_offset is not None:
            exponent = decode_available(codecs, _spec('int16'), registers[located.sf_offset : located.sf_offset + 1])
            if exponent is None:
                return None
    except (TypeError, ValueError):
        return None
    if value is None or exponent is None or not isinstance(value, (int, float)) or isinstance(value, bool):
        return value
    return scale(value, int(exponent))


def _spec(datatype: str) -> RegisterSpec:
    return RegisterSpec(RegisterKey(0, Table.HOLDING_REGISTER, 0), datatype=datatype)


@dataclass(frozen=True)
class ModelListing:
    """One model found on a device; ``definition`` None if the catalog doesn't know it (no rows then)."""

    location: ModelLocation
    definition: ModelDef | None
    rows: tuple[Row, ...] = ()


@dataclass(frozen=True)
class DeviceListing:
    """Result of listing a device: its models, or why it couldn't be listed."""

    unit: int
    scanned: datetime
    models: tuple[ModelListing, ...] = ()
    error: str = ''


async def list_device(read: Reader, catalog: Catalog, codecs: CodecRegistry | None = None) -> list[ModelListing]:
    """
    Every model and point of a device, with item address and current value.

    :raises SunSpecError: no SunSpec marker, or the model chain is unreadable
    """
    listings = []
    for location in await scan(read):
        definition = catalog.models.get(location.model)
        rows: tuple[Row, ...] = ()
        if definition is not None:
            rows = tuple(describe(location, definition, await read_model(read, location), codecs))
        listings.append(ModelListing(location, definition, rows))
    return listings


async def print_device(host: str, port: int, unit: int, catalog: Catalog) -> None:
    """Print every model and point of a Modbus TCP device with item address, value, unit and label."""
    client = new_client(TcpTransport(host, port))
    if not await client.connect():
        raise SunSpecError(f'cannot connect to {host}:{port}')
    try:

        async def read(address: int, count: int) -> list[int] | None:
            result = await client.read_holding_registers(address, count=count, **{UNIT_KWARG: unit})
            return None if result.isError() else list(result.registers)

        print(f'SunSpec device {host}:{port} unit {unit}, definitions: {catalog.source}')
        for listing in await list_device(read, catalog):
            location, definition = listing.location, listing.definition
            if definition is None:
                print(f'model {location.model} at {location.start} ({location.length} registers): no definition')
                continue
            instance = '' if location.instance == 1 else f' instance {location.instance}'
            print(
                f'model {location.model} {definition.name}{instance} at {location.start} ({location.length} registers)'
            )
            for row in listing.rows:
                value = 'n/a' if row.value is None else row.value
                print(f'  {str(row.ref):<32} {value} {row.point.units}  {row.point.label}'.rstrip())
    finally:
        client.close()


@functools.cache
def default_catalog() -> Catalog:
    """The shipped catalog, loaded once."""
    return load_catalog()


def load_catalog(path: pathlib.Path = CATALOG_FILE) -> Catalog:
    """Catalog from a compact definitions file as written by :func:`convert`."""
    raw = json.loads(path.read_text())
    models = {model['id']: ModelDef(model['id'], _group(model['group'])) for model in raw['models']}
    return Catalog(models, raw.get('source', ''))


def _group(raw: Mapping[str, Any]) -> GroupDef:
    return GroupDef(
        name=raw['name'],
        points=tuple(
            PointDef(
                name=p['name'],
                type=p['type'],
                size=p['size'],
                sf=p.get('sf'),
                units=p.get('units', ''),
                label=p.get('label', ''),
                writable=p.get('rw', False),
            )
            for p in raw.get('points', ())
        ),
        groups=tuple(_group(g) for g in raw.get('groups', ())),
        count=raw.get('count'),
        label=raw.get('label', ''),
    )


def convert(source_dir: pathlib.Path, target: pathlib.Path = CATALOG_FILE, source: str = '') -> int:
    """
    Write the compact definitions file from the ``model_*.json`` files of sunspec/models.

    Keeps what addressing and presentation need (names, types, sizes, scale factors, counts,
    units, labels, write access); drops descriptions, symbols and standards references.

    :returns: number of models written
    """
    models = []
    for path in sorted(source_dir.glob('model_*.json'), key=lambda p: int(p.stem.removeprefix('model_'))):
        raw = json.loads(path.read_text())
        models.append({'id': raw['id'], 'group': _compact_group(raw['group'])})
    lines = ',\n'.join(json.dumps(model, separators=(',', ':'), ensure_ascii=False) for model in models)
    target.write_text(f'{{"source":{json.dumps(source)},"models":[\n{lines}\n]}}\n')
    return len(models)


def _compact_group(raw: Mapping[str, Any]) -> dict[str, Any]:
    group: dict[str, Any] = {'name': raw['name']}
    if raw.get('label'):
        group['label'] = raw['label']
    if 'count' in raw:
        group['count'] = raw['count']
    group['points'] = [_compact_point(p) for p in raw.get('points', ())]
    if raw.get('groups'):
        group['groups'] = [_compact_group(g) for g in raw['groups']]
    return group


def _compact_point(raw: Mapping[str, Any]) -> dict[str, Any]:
    point: dict[str, Any] = {'name': raw['name'], 'type': raw['type'], 'size': raw['size']}
    for key in ('sf', 'units', 'label'):
        if raw.get(key) is not None and raw.get(key) != '':
            point[key] = raw[key]
    if raw.get('access') == 'RW':
        point['rw'] = True
    return point


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog='python -m plugins.modbus.sunspec', description=__doc__.split('\n\n')[0])
    commands = parser.add_subparsers(dest='command', required=True)
    conv = commands.add_parser('convert', help='refresh sunspec_models.json from sunspec/models json files')
    conv.add_argument('source_dir', type=pathlib.Path)
    conv.add_argument('--source', default='', help='provenance note, e.g. "sunspec/models <commit>"')
    device = commands.add_parser('scan', help='list the points of a Modbus TCP device with their values')
    device.add_argument('--host', required=True)
    device.add_argument('--port', type=int, default=502)
    device.add_argument('--unit', type=int, default=1)
    args = parser.parse_args(argv)
    if args.command == 'convert':
        print(f'{convert(args.source_dir, source=args.source)} models written to {CATALOG_FILE}')
    else:
        asyncio.run(print_device(args.host, args.port, args.unit, default_catalog()))


if __name__ == '__main__':
    main()
