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
Feature registry contract tests, run against the real N20 Pro Plus capabilities of deebot-client.
"""

import asyncio

import pytest
from deebot_client.capabilities import Capabilities
from deebot_client.commands import StationAction
from deebot_client.commands.json.charge import Charge
from deebot_client.commands.json.clean import CleanAreaV2, CleanV2
from deebot_client.commands.json.fan_speed import SetFanSpeed
from deebot_client.commands.json.play_sound import PlaySound
from deebot_client.commands.json.station_action import StationAction as StationActionCommand
from deebot_client.commands.json.water_info import SetWaterInfo
from deebot_client.events import (
    AvailabilityEvent,
    BatteryEvent,
    CachedMapInfoEvent,
    ErrorEvent,
    FanSpeedEvent,
    FanSpeedLevel,
    LifeSpan,
    LifeSpanEvent,
    Position,
    PositionsEvent,
    RoomsEvent,
    StateEvent,
    StatsEvent,
    StationEvent,
    TotalStatsEvent,
    station,
    water_info,
)
from deebot_client.hardware import get_static_device_info
from deebot_client.models import CleanAction, CleanMode, Room, State
from deebot_client.rs.map import PositionType, RotationAngle
from deebot_client.events.map import Map

from plugins.deebot.features import (
    FEATURES,
    SKIP,
    apply_room_settings,
    clean_rooms_command,
    parse_room_names,
    parse_room_preselect,
)


@pytest.fixture(scope='module')
def caps() -> Capabilities:
    info = asyncio.run(get_static_device_info('qhe2o2'))
    assert info is not None
    return info.capabilities


def extract(name, event):
    extractor = FEATURES[name].extract
    assert extractor is not None
    return extractor(event)


class TestRegistry:
    def test_names_match_keys(self):
        assert all(name == feature.name for name, feature in FEATURES.items())

    def test_every_lifespan_type_has_a_feature(self):
        for life_span in LifeSpan:
            assert f'lifespan_{life_span.name.lower()}' in FEATURES

    def test_item_types_are_shng_types(self):
        assert {f.item_type for f in FEATURES.values()} <= {'bool', 'num', 'str', 'dict', 'list'}

    def test_event_features_have_extractor_except_rendered_ones(self):
        no_extract = {name for name, f in FEATURES.items() if f.event is not None and f.extract is None}
        assert no_extract == {'map_svg'}


class TestExtract:
    def test_state_is_lowercase_enum_name(self):
        assert extract('state', StateEvent(State.RETURNING)) == 'returning'

    @pytest.mark.parametrize(
        ('state', 'active'),
        [
            (State.CLEANING, True),
            (State.RETURNING, True),
            (State.DOCKED, False),
            (State.IDLE, False),
            (State.PAUSED, False),
            (State.ERROR, False),
        ],
    )
    def test_active_means_robot_is_moving(self, state, active):
        assert extract('active', StateEvent(state)) is active

    def test_battery(self):
        assert extract('battery', BatteryEvent(87)) == 87

    def test_available(self):
        assert extract('available', AvailabilityEvent(available=True)) is True

    def test_error(self):
        event = ErrorEvent(105, 'Stuck')
        assert extract('error_code', event) == 105
        assert extract('error_text', event) == 'Stuck'

    def test_error_without_description_is_empty_text(self):
        assert extract('error_text', ErrorEvent(0, None)) == ''

    def test_fan_speed(self):
        assert extract('fan_speed', FanSpeedEvent(FanSpeedLevel.MAX_PLUS)) == 'max_plus'

    def test_water_amount(self):
        assert extract('water_amount', water_info.WaterAmountEvent(water_info.WaterAmount.HIGH)) == 'high'

    def test_station_state(self):
        assert extract('station_state', StationEvent(station.State.WASHING_MOP)) == 'washing_mop'

    def test_stats(self):
        event = StatsEvent(area=12, time=340, type='auto')
        assert extract('clean_area', event) == 12
        assert extract('clean_time', event) == 340

    def test_stats_missing_values_are_skipped(self):
        event = StatsEvent(area=None, time=None, type=None)
        assert extract('clean_area', event) is SKIP
        assert extract('clean_time', event) is SKIP

    def test_total_stats(self):
        event = TotalStatsEvent(area=900, time=7200, cleanings=31)
        assert extract('total_area', event) == 900
        assert extract('total_time', event) == 7200
        assert extract('total_cleanings', event) == 31

    def test_lifespan_only_matches_its_own_type(self):
        event = LifeSpanEvent(LifeSpan.SIDE_BRUSH, 55.5, 4000)
        assert extract('lifespan_side_brush', event) == 55.5
        assert extract('lifespan_brush', event) is SKIP

    def test_position_and_charger(self):
        event = PositionsEvent([Position(PositionType.DEEBOT, 10, 20, 90), Position(PositionType.CHARGER, 1, 2, 0)])
        assert extract('position', event) == {'x': 10, 'y': 20, 'angle': 90}
        assert extract('charger_position', event) == {'x': 1, 'y': 2, 'angle': 0}

    def test_position_absent_is_skipped(self):
        event = PositionsEvent([Position(PositionType.CHARGER, 1, 2, 0)])
        assert extract('position', event) is SKIP

    def test_rooms(self):
        event = RoomsEvent('1', [Room('Kitchen', 3, '1,2'), Room('Hall', 4, '3,4')])
        assert extract('rooms', event) == [
            {'id': 3, 'name': 'Kitchen', 'map': '1'},
            {'id': 4, 'name': 'Hall', 'map': '1'},
        ]

    def test_maps_are_listed_by_id_with_the_active_one_flagged(self):
        event = CachedMapInfoEvent(
            {
                Map('20', 'Obergeschoss', using=False, built=True, angle=RotationAngle.DEG_0),
                Map('10', 'Erdgeschoss', using=True, built=True, angle=RotationAngle.DEG_0),
            }
        )

        assert extract('maps', event) == [
            {'id': '10', 'name': 'Erdgeschoss', 'active': True, 'built': True},
            {'id': '20', 'name': 'Obergeschoss', 'active': False, 'built': True},
        ]


class TestSupport:
    def test_supported_when_device_has_capability(self, caps):
        assert FEATURES['battery'].capability(caps) is not None
        assert FEATURES['lifespan_side_brush'].capability(caps) is not None
        assert FEATURES['station_state'].capability(caps) is not None
        assert FEATURES['map_svg'].capability(caps) is not None

    def test_unsupported_when_device_lacks_capability(self, caps):
        assert FEATURES['lifespan_dust_bag'].capability(caps) is None


class TestCommands:
    def command(self, caps, name, value):
        builder = FEATURES[name].command
        assert builder is not None
        return builder(caps, value)

    def test_event_only_features_are_read_only(self):
        assert FEATURES['battery'].command is None
        assert not FEATURES['battery'].writable

    @pytest.mark.parametrize(
        ('name', 'expected'),
        [
            ('cmd_start', CleanV2(CleanAction.START)),
            ('cmd_pause', CleanV2(CleanAction.PAUSE)),
            ('cmd_resume', CleanV2(CleanAction.RESUME)),
            ('cmd_stop', CleanV2(CleanAction.STOP)),
            ('cmd_dock', Charge()),
            ('cmd_locate', PlaySound()),
            ('cmd_empty_dustbin', StationActionCommand(StationAction.EMPTY_DUSTBIN)),
        ],
    )
    def test_trigger_items_issue_command_on_true(self, caps, name, expected):
        assert self.command(caps, name, True) == expected

    @pytest.mark.parametrize('name', ['cmd_start', 'cmd_dock', 'cmd_locate', 'cmd_empty_dustbin'])
    def test_trigger_items_ignore_false(self, caps, name):
        assert self.command(caps, name, False) is None

    def test_fan_speed(self, caps):
        assert self.command(caps, 'fan_speed', 'max') == SetFanSpeed(FanSpeedLevel.MAX)

    def test_fan_speed_is_case_insensitive(self, caps):
        assert self.command(caps, 'fan_speed', 'MAX_PLUS') == SetFanSpeed(FanSpeedLevel.MAX_PLUS)

    def test_fan_speed_unknown_value_rejected(self, caps):
        with pytest.raises(ValueError, match='turbo'):
            self.command(caps, 'fan_speed', 'turbo')

    def test_water_amount(self, caps):
        assert self.command(caps, 'water_amount', 'low') == SetWaterInfo(amount=water_info.WaterAmount.LOW)

    def test_water_amount_not_offered_by_device_rejected(self, caps):
        with pytest.raises(ValueError, match='ultrahigh'):
            self.command(caps, 'water_amount', 'ultrahigh')


class TestCleanRooms:
    def test_cleans_given_rooms(self, caps):
        assert clean_rooms_command(caps, [3, 4], 2) == CleanAreaV2(CleanMode.SPOT_AREA, [3, 4], 2)

    def test_empty_room_list_rejected(self, caps):
        with pytest.raises(ValueError, match='room'):
            clean_rooms_command(caps, [], 1)

    def test_count_must_be_positive(self, caps):
        with pytest.raises(ValueError, match='count'):
            clean_rooms_command(caps, [3], 0)

    def test_ids_and_count_given_as_text_are_accepted(self, caps):
        assert clean_rooms_command(caps, ['3', '4'], '2') == CleanAreaV2(CleanMode.SPOT_AREA, [3, 4], 2)

    def test_non_numeric_id_rejected(self, caps):
        with pytest.raises(ValueError, match='kitchen'):
            clean_rooms_command(caps, ['kitchen'], 1)

    def test_non_numeric_count_rejected(self, caps):
        with pytest.raises(ValueError, match='count'):
            clean_rooms_command(caps, [3], 'twice')

    def test_room_ids_not_in_a_list_rejected(self, caps):
        with pytest.raises(ValueError, match='list'):
            clean_rooms_command(caps, 3, 1)


class TestCleanRoomsItem:
    def command(self, caps, value):
        builder = FEATURES['cmd_clean_rooms'].command
        assert builder is not None
        return builder(caps, value)

    def test_is_a_list_item_with_support_check(self, caps):
        assert FEATURES['cmd_clean_rooms'].item_type == 'list'
        assert FEATURES['cmd_clean_rooms'].capability(caps) is not None

    def test_room_ids_start_one_cleaning_pass(self, caps):
        assert self.command(caps, [3, 4]) == CleanAreaV2(CleanMode.SPOT_AREA, [3, 4], 1)

    def test_ids_given_as_text_are_accepted(self, caps):
        assert self.command(caps, ['3', '4']) == CleanAreaV2(CleanMode.SPOT_AREA, [3, 4], 1)

    def test_empty_list_does_nothing(self, caps):
        assert self.command(caps, []) is None

    def test_non_numeric_id_rejected(self, caps):
        with pytest.raises(ValueError, match='kitchen'):
            self.command(caps, ['kitchen'])

    def test_non_list_rejected(self, caps):
        with pytest.raises(ValueError, match='list'):
            self.command(caps, 3)


class TestReset:
    def test_trigger_items_reset_to_their_idle_value(self):
        assert FEATURES['cmd_start'].reset_to is False
        assert FEATURES['cmd_clean_rooms'].reset_to == []

    def test_other_items_do_not_reset(self):
        assert FEATURES['fan_speed'].reset_to is SKIP
        assert FEATURES['battery'].reset_to is SKIP


class TestRoomSettings:
    rooms = [
        {'id': 3, 'name': 'Default', 'map': '10'},
        {'id': 5, 'name': 'Default', 'map': '10'},
        {'id': 3, 'name': 'Default', 'map': '20'},
    ]

    def apply(self, names=(), preselect=(), map_names=None):
        return apply_room_settings(
            self.rooms, parse_room_names(names), parse_room_preselect(preselect), map_names or {}
        )

    def test_a_map_may_be_given_by_its_name(self):
        result = self.apply([{'map': 'EG', 'room': 3, 'name': 'Küche'}], map_names={'10': 'EG', '20': 'OG'})

        assert [room['name'] for room in result] == ['Küche', 'Default', 'Default']

    def test_the_name_of_the_other_map_does_not_match(self):
        result = self.apply([{'map': 'OG', 'room': 3, 'name': 'Bad'}], map_names={'10': 'EG', '20': 'OG'})

        assert [room['name'] for room in result] == ['Default', 'Default', 'Bad']

    def test_preselection_by_map_name(self):
        result = self.apply(preselect=[{'map': 'EG', 'room': 5}], map_names={'10': 'EG'})

        assert [room['preselect'] for room in result] == [False, True, False]

    def test_map_name_is_ignored_while_the_names_are_unknown(self):
        result = self.apply([{'map': 'EG', 'room': 3, 'name': 'Küche'}])

        assert [room['name'] for room in result] == ['Default'] * 3

    def test_the_id_of_a_map_wins_over_its_name(self):
        result = self.apply(
            [{'map': 'EG', 'room': 3, 'name': 'nach Name'}, {'map': '10', 'room': 3, 'name': 'nach Id'}],
            map_names={'10': 'EG'},
        )

        assert result[0]['name'] == 'nach Id'

    def test_names_of_a_map_apply_to_its_rooms_only(self):
        result = self.apply([{'map': '10', 'room': 3, 'name': 'Küche'}])

        assert [room['name'] for room in result] == ['Küche', 'Default', 'Default']

    def test_two_maps_may_reuse_a_room_id(self):
        result = self.apply([{'map': '10', 'room': 3, 'name': 'Küche'}, {'map': '20', 'room': 3, 'name': 'Bad'}])

        assert [room['name'] for room in result] == ['Küche', 'Default', 'Bad']

    def test_entries_without_map_apply_to_every_map(self):
        result = self.apply([{'room': 3, 'name': 'Küche'}])

        assert [room['name'] for room in result] == ['Küche', 'Default', 'Küche']

    def test_the_entry_of_a_map_wins_over_the_general_one(self):
        result = self.apply([{'room': 3, 'name': 'Küche'}, {'map': '20', 'room': 3, 'name': 'Bad'}])

        assert [room['name'] for room in result] == ['Küche', 'Default', 'Bad']

    def test_rooms_are_not_preselected_by_default(self):
        assert [room['preselect'] for room in self.apply()] == [False, False, False]

    def test_listed_rooms_are_preselected(self):
        result = self.apply(preselect=[{'map': '10', 'room': 3}, {'room': 5}])

        assert [room['preselect'] for room in result] == [True, True, False]

    def test_select_false_overrides_a_general_preselection(self):
        result = self.apply(preselect=[{'room': 3}, {'map': '20', 'room': 3, 'select': False}])

        assert [room['preselect'] for room in result] == [True, False, False]

    def test_input_is_not_modified(self):
        self.apply([{'room': 3, 'name': 'Küche'}], [{'room': 3}])

        assert self.rooms[0] == {'id': 3, 'name': 'Default', 'map': '10'}

    def test_ids_may_be_text_and_map_ids_numbers(self):
        result = self.apply([{'map': 10, 'room': '3', 'name': 'Küche'}])

        assert result[0]['name'] == 'Küche'

    def test_names_are_converted_to_text(self):
        assert self.apply([{'room': 3, 'name': 2024}])[0]['name'] == '2024'

    def test_empty_config_changes_no_name(self):
        assert [room['name'] for room in self.apply()] == ['Default'] * 3

    def test_non_numeric_room_id_rejected(self):
        with pytest.raises(ValueError, match='kitchen'):
            parse_room_names([{'room': 'kitchen', 'name': 'Küche'}])

    def test_entry_without_room_rejected(self):
        with pytest.raises(ValueError, match="'room'"):
            parse_room_names([{'name': 'Küche'}])

    def test_entry_without_name_rejected(self):
        with pytest.raises(ValueError, match="'name'"):
            parse_room_names([{'room': 3}])

    def test_unknown_key_rejected(self):
        with pytest.raises(ValueError, match='nme'):
            parse_room_names([{'room': 3, 'nme': 'Küche'}])

    def test_entry_that_is_not_a_mapping_rejected(self):
        with pytest.raises(ValueError, match='Küche'):
            parse_room_preselect(['Küche'])
