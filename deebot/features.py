#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

"""
Registry of the item attribute values (features) the deebot plugin offers.

A feature maps one ``deebot: <name>`` item attribute value to

* the deebot-client event that delivers its value and how to read the value from that event, and/or
* the deebot-client command that is sent when the item is written.

Support for a further vacuum function means adding one ``Feature`` to ``FEATURES``; the plugin, the web interface
and the metadata check pick it up from there.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar

from deebot_client.capabilities import Capabilities, CapabilityExecuteTypes, CapabilitySetTypes
from deebot_client.command import Command
from deebot_client.commands import StationAction
from deebot_client.events import (
    AvailabilityEvent,
    BatteryEvent,
    CachedMapInfoEvent,
    ErrorEvent,
    Event,
    FanSpeedEvent,
    LifeSpan,
    LifeSpanEvent,
    MapChangedEvent,
    PositionsEvent,
    RoomsEvent,
    StateEvent,
    StatsEvent,
    StationEvent,
    TotalStatsEvent,
    water_info,
)
from deebot_client.models import CleanAction, CleanMode, State
from deebot_client.rs.map import PositionType


class _Skip:
    """Type of the ``SKIP`` sentinel."""

    def __repr__(self) -> str:
        return 'SKIP'


# returned by an extractor when the event carries no value for its feature
SKIP = _Skip()

E = TypeVar('E', bound=Event)
EnumT = TypeVar('EnumT', bound=Enum)
T = TypeVar('T')
V = TypeVar('V')

Extractor = Callable[[Event], object]
CommandBuilder = Callable[[Capabilities, object], Command | None]


@dataclass(frozen=True)
class Feature:
    """
    One value of the item attribute ``deebot``.

    :param name: attribute value, e.g. ``battery``
    :param item_type: shng item type the attribute is meant for
    :param event: event delivering the value, ``None`` for write-only features
    :param extract: reads the item value from ``event``, returns ``SKIP`` if the event holds no value for this feature;
        ``None`` if the plugin renders the value itself
    :param capability: returns the part of the device capabilities backing this feature, ``None`` if the device lacks it
    :param command: builds the command for an item write, ``None`` if the write needs no command; absent for read-only
        features
    :param reset_to: value the plugin writes back to the item after sending the command, ``SKIP`` to leave it
    """

    name: str
    item_type: str
    capability: Callable[[Capabilities], object | None]
    event: type[Event] | None = None
    extract: Extractor | None = None
    command: CommandBuilder | None = None
    reset_to: object = SKIP

    @property
    def writable(self) -> bool:
        """True if writing the item sends a command to the device."""
        return self.command is not None


def _on(event_type: type[E], read: Callable[[E], object]) -> Extractor:
    """Wrap ``read`` so it only handles events of ``event_type``."""

    def extract(event: Event) -> object:
        return read(event) if isinstance(event, event_type) else SKIP

    return extract


def _enum_name(value: Enum) -> str:
    return value.name.lower()


def _parse_enum(value: object, allowed: Sequence[EnumT]) -> EnumT:
    """Return the member of ``allowed`` whose lower-case name is ``value``, case-insensitive."""
    by_name = {_enum_name(member): member for member in allowed}
    try:
        return by_name[str(value).lower()]
    except KeyError:
        raise ValueError(f"'{value}' is not one of {sorted(by_name)}") from None


def _require(capability: T | None, what: str) -> T:
    if capability is None:
        raise ValueError(f'{what} is not supported by this device')
    return capability


def _trigger(build: Callable[[Capabilities], Command]) -> CommandBuilder:
    """Command builder for items that act when set to ``True`` and ignore ``False``."""

    def command(caps: Capabilities, value: object) -> Command | None:
        return build(caps) if value else None

    return command


def _water_amount(caps: Capabilities) -> CapabilitySetTypes | None:
    if caps.water is not None and isinstance(caps.water.amount, CapabilitySetTypes):
        return caps.water.amount
    return None


def _fan_speed_command(caps: Capabilities, value: object) -> Command:
    capability = _require(caps.fan_speed, 'fan_speed')
    return capability.set(_parse_enum(value, capability.types))


def _water_amount_command(caps: Capabilities, value: object) -> Command:
    capability = _require(_water_amount(caps), 'water_amount')
    return capability.set(_parse_enum(value, capability.types))


def _position(positions: PositionsEvent, position_type: PositionType) -> dict[str, int] | _Skip:
    for position in positions.positions:
        if position.type == position_type:
            return {'x': position.x, 'y': position.y, 'angle': position.a}
    return SKIP


def _skip_none(value: int | None) -> int | _Skip:
    return SKIP if value is None else value


def _active(state: StateEvent) -> bool:
    return state.state in (State.CLEANING, State.RETURNING)


def _lifespan_features() -> list[Feature]:
    def feature(life_span: LifeSpan) -> Feature:
        return Feature(
            f'lifespan_{life_span.name.lower()}',
            'num',
            capability=lambda caps: caps.life_span if life_span in caps.life_span.types else None,
            event=LifeSpanEvent,
            extract=_on(LifeSpanEvent, lambda e: e.percent if e.type == life_span else SKIP),
        )

    return [feature(life_span) for life_span in LifeSpan]


def _int(value: object, what: str) -> int:
    """``value`` as int, also from its text form."""
    try:
        return int(str(value))
    except ValueError:
        raise ValueError(f'{what} must be a number, got {value!r}') from None


def clean_rooms_command(caps: Capabilities, rooms: object, count: object) -> Command:
    """
    Build the command to clean the given rooms.

    :param caps: capabilities of the device
    :param rooms: list of room ids as reported by the ``rooms`` feature, numbers or their text form
    :param count: number of cleaning passes, a number or its text form
    :raises ValueError: if ``rooms`` is no list, empty or holds non-numbers, ``count`` is no number or below 1, or the
        device cannot clean single rooms
    """
    if not isinstance(rooms, (list, tuple)):
        raise ValueError(f'expected a list of room ids, got {rooms!r}')
    if not rooms:
        raise ValueError('at least one room id is required')
    room_ids: list[int | float] = [_int(room, 'room id') for room in rooms]
    passes = _int(count, 'count')
    if passes < 1:
        raise ValueError(f'count must be at least 1, got {count!r}')
    area = _require(caps.clean.action.area, 'cleaning single rooms')
    return area(CleanMode.SPOT_AREA, room_ids, passes)


def _clean_rooms_item_command(caps: Capabilities, value: object) -> Command | None:
    """Command for a write of room ids to the ``cmd_clean_rooms`` item; an empty list does nothing."""
    if isinstance(value, (list, tuple)) and not value:
        return None
    return clean_rooms_command(caps, value, 1)


@dataclass(frozen=True)
class RoomSetting(Generic[V]):
    """
    Values the configuration assigns to rooms.

    :param everywhere: value by room id, applies to the rooms of every map
    :param by_map: value by map id and room id, takes precedence over ``everywhere``
    """

    everywhere: Mapping[int, V] = field(default_factory=dict)
    by_map: Mapping[str, Mapping[int, V]] = field(default_factory=dict)

    def get(self, maps: Sequence[str], room_id: int, default: V) -> V:
        """
        Value of a room of a map.

        :param maps: id and name of the map of the room; the entry of the first one that configures the room wins
        :param default: returned if neither the map nor the general entries configure the room
        """
        for key in maps:
            if room_id in self.by_map.get(key, {}):
                return self.by_map[key][room_id]
        return self.everywhere.get(room_id, default)


_REQUIRED = object()


def _parse_room_entries(
    raw: Sequence[object], value_key: str, convert: Callable[[object], V], default: object
) -> RoomSetting[V]:
    """
    Entries ``{room: <id>, [map: <id>,] <value_key>: <value>}`` as ``RoomSetting``.

    Config keys must not start with a digit (the config loader drops them), so ids are values, not keys.
    """
    everywhere: dict[int, V] = {}
    by_map: dict[str, dict[int, V]] = {}
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise ValueError(f'expected an entry like {{room: 3, {value_key}: ...}}, got {entry!r}')
        unknown = set(entry) - {'room', 'map', value_key}
        if unknown:
            raise ValueError(f'unknown key {sorted(unknown)} in {dict(entry)!r}')
        if 'room' not in entry:
            raise ValueError(f"'room' missing in {dict(entry)!r}")
        if value_key not in entry and default is _REQUIRED:
            raise ValueError(f"'{value_key}' missing in {dict(entry)!r}")
        value = convert(entry.get(value_key, default))
        target = by_map.setdefault(str(entry['map']), {}) if 'map' in entry else everywhere
        target[_int(entry['room'], 'room')] = value
    return RoomSetting(everywhere, by_map)


def parse_room_names(raw: Sequence[object]) -> RoomSetting[str]:
    """
    Room names from the ``room_names`` parameter.

    :param raw: entries ``{room: 3, name: Küche}``; ``map: <id>`` limits an entry to one map, without it it applies to all
    :raises ValueError: if an entry is malformed or a room id is not a number
    """
    return _parse_room_entries(raw, 'name', str, _REQUIRED)


def parse_room_preselect(raw: Sequence[object]) -> RoomSetting[bool]:
    """
    Rooms to preselect from the ``room_preselect`` parameter.

    :param raw: entries ``{room: 3}``; ``map: <id>`` limits an entry to one map, ``select: false`` removes a preselection
    :raises ValueError: if an entry is malformed or a room id is not a number
    """
    return _parse_room_entries(raw, 'select', bool, True)


def apply_room_settings(
    rooms: Sequence[Mapping[str, int | str]],
    names: RoomSetting[str],
    preselect: RoomSetting[bool],
    map_names: Mapping[str, str],
) -> list[dict[str, int | str | bool]]:
    """
    Copy of ``rooms`` (``{'id', 'name', 'map'}`` entries) with the configured name and a ``preselect`` flag per room.

    A map is addressed in the configuration by its id or, once known, by its name; the id wins.

    :param rooms: rooms as published by the ``rooms`` feature
    :param names: configured names, they replace the names of the device
    :param preselect: rooms to preselect for cleaning, ``False`` for rooms not configured
    :param map_names: name of each known map by map id
    """
    result: list[dict[str, int | str | bool]] = []
    for room in rooms:
        map_id = str(room.get('map', ''))
        maps = [map_id, map_names[map_id]] if map_names.get(map_id) else [map_id]
        room_id = int(room['id'])
        result.append(
            {
                **room,
                'name': names.get(maps, room_id, str(room['name'])),
                'preselect': preselect.get(maps, room_id, False),
            }
        )
    return result


def _station_action(caps: Capabilities, action: StationAction) -> CapabilityExecuteTypes[StationAction] | None:
    """Return the station action capability if the base station offers ``action``."""
    if caps.station is not None and action in caps.station.action.types:
        return caps.station.action
    return None


def _trigger_feature(
    name: str, capability: Callable[[Capabilities], object | None], build: Callable[[Capabilities], Command]
) -> Feature:
    """Bool item that sends the command of ``build`` when set to ``True`` and resets itself to ``False``."""
    return Feature(name, 'bool', capability, command=_trigger(build), reset_to=False)


_FEATURE_LIST: list[Feature] = [
    Feature('state', 'str', lambda caps: caps.state, StateEvent, _on(StateEvent, lambda e: _enum_name(e.state))),
    Feature('active', 'bool', lambda caps: caps.state, StateEvent, _on(StateEvent, _active)),
    Feature('battery', 'num', lambda caps: caps.battery, BatteryEvent, _on(BatteryEvent, lambda e: e.value)),
    Feature(
        'available',
        'bool',
        lambda caps: caps.availability,
        AvailabilityEvent,
        _on(AvailabilityEvent, lambda e: e.available),
    ),
    Feature('error_code', 'num', lambda caps: caps.error, ErrorEvent, _on(ErrorEvent, lambda e: e.code)),
    Feature('error_text', 'str', lambda caps: caps.error, ErrorEvent, _on(ErrorEvent, lambda e: e.description or '')),
    Feature(
        'fan_speed',
        'str',
        lambda caps: caps.fan_speed,
        FanSpeedEvent,
        _on(FanSpeedEvent, lambda e: _enum_name(e.speed)),
        _fan_speed_command,
    ),
    Feature(
        'water_amount',
        'str',
        _water_amount,
        water_info.WaterAmountEvent,
        _on(water_info.WaterAmountEvent, lambda e: _enum_name(e.value)),
        _water_amount_command,
    ),
    Feature(
        'station_state',
        'str',
        lambda caps: caps.station.state if caps.station else None,
        StationEvent,
        _on(StationEvent, lambda e: _enum_name(e.state)),
    ),
    Feature(
        'clean_area', 'num', lambda caps: caps.stats.clean, StatsEvent, _on(StatsEvent, lambda e: _skip_none(e.area))
    ),
    Feature(
        'clean_time', 'num', lambda caps: caps.stats.clean, StatsEvent, _on(StatsEvent, lambda e: _skip_none(e.time))
    ),
    Feature(
        'total_area', 'num', lambda caps: caps.stats.total, TotalStatsEvent, _on(TotalStatsEvent, lambda e: e.area)
    ),
    Feature(
        'total_time', 'num', lambda caps: caps.stats.total, TotalStatsEvent, _on(TotalStatsEvent, lambda e: e.time)
    ),
    Feature(
        'total_cleanings',
        'num',
        lambda caps: caps.stats.total,
        TotalStatsEvent,
        _on(TotalStatsEvent, lambda e: e.cleanings),
    ),
    *_lifespan_features(),
    Feature(
        'position',
        'dict',
        lambda caps: caps.map.position if caps.map else None,
        PositionsEvent,
        _on(PositionsEvent, lambda e: _position(e, PositionType.DEEBOT)),
    ),
    Feature(
        'charger_position',
        'dict',
        lambda caps: caps.map.position if caps.map else None,
        PositionsEvent,
        _on(PositionsEvent, lambda e: _position(e, PositionType.CHARGER)),
    ),
    Feature(
        'rooms',
        'list',
        lambda caps: caps.map.rooms if caps.map else None,
        RoomsEvent,
        _on(RoomsEvent, lambda e: [{'id': room.id, 'name': room.name, 'map': e.map_id} for room in e.rooms]),
    ),
    Feature(
        'maps',
        'list',
        lambda caps: caps.map.cached_info if caps.map else None,
        CachedMapInfoEvent,
        _on(
            CachedMapInfoEvent,
            lambda e: [
                {'id': m.id, 'name': m.name, 'active': m.using, 'built': m.built}
                for m in sorted(e.maps, key=lambda m: m.id)
            ],
        ),
    ),
    Feature('map_svg', 'str', lambda caps: caps.map, MapChangedEvent),
    _trigger_feature('cmd_start', lambda caps: caps.clean, lambda caps: caps.clean.action.command(CleanAction.START)),
    _trigger_feature('cmd_pause', lambda caps: caps.clean, lambda caps: caps.clean.action.command(CleanAction.PAUSE)),
    _trigger_feature('cmd_resume', lambda caps: caps.clean, lambda caps: caps.clean.action.command(CleanAction.RESUME)),
    _trigger_feature('cmd_stop', lambda caps: caps.clean, lambda caps: caps.clean.action.command(CleanAction.STOP)),
    _trigger_feature('cmd_dock', lambda caps: caps.charge, lambda caps: caps.charge.execute()),
    _trigger_feature('cmd_locate', lambda caps: caps.play_sound, lambda caps: caps.play_sound.execute()),
    _trigger_feature(
        'cmd_empty_dustbin',
        lambda caps: _station_action(caps, StationAction.EMPTY_DUSTBIN),
        lambda caps: _require(_station_action(caps, StationAction.EMPTY_DUSTBIN), 'emptying the dustbin').execute(
            StationAction.EMPTY_DUSTBIN
        ),
    ),
    Feature(
        'cmd_clean_rooms', 'list', lambda caps: caps.clean.action.area, command=_clean_rooms_item_command, reset_to=[]
    ),
]


# all features by attribute value
FEATURES: dict[str, Feature] = {feature.name: feature for feature in _FEATURE_LIST}
