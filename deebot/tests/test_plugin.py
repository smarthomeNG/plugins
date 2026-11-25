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
Item handling of the Deebot plugin: attribute parsing, publishing device values to items and sending item writes
as commands.

The Ecovacs cloud is not involved: commands go to a deebot-client ``Device`` whose command executor records instead
of sending.
"""

import asyncio
import os

import aiohttp
import pytest
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.command import Command
from deebot_client.commands.json.charge import Charge
from deebot_client.commands.json.clean import CleanAreaV2, CleanV2
from deebot_client.commands.json.fan_speed import SetFanSpeed
from deebot_client.device import Device
from deebot_client.events import FanSpeedLevel
from deebot_client.hardware import get_static_device_info
from deebot_client.models import CleanAction, CleanMode, DeviceInfo

import tests.common as common
from plugins.deebot.credentials import CredentialStore
from plugins.deebot.session import DeebotSession
from .helpers import FIXTURES_DIR, item, make_plugin, write

common.register_shng_log_levels()


class RecordingDevice(Device):
    """Real deebot-client device that records commands instead of sending them to the cloud."""

    def __init__(self, info: DeviceInfo, authenticator: Authenticator) -> None:
        super().__init__(info, authenticator)
        self.sent: list[Command] = []

    async def execute_command(self, command: Command) -> dict:
        self.sent.append(command)
        return {}


class TestParseItem:
    def test_known_features_are_registered(self, plugin, sh):
        assert plugin.get_item_mapping(item(sh, 'battery')) == 'battery'
        assert plugin.get_item_mapping(item(sh, 'start')) == 'cmd_start'

    def test_only_writable_features_ask_for_updates(self, sh):
        plugin = make_plugin(sh)

        assert plugin.parse_item(item(sh, 'battery')) is None
        assert plugin.parse_item(item(sh, 'start')) == plugin.update_item

    def test_unknown_feature_is_not_registered(self, plugin, sh):
        assert item(sh, 'unknown_feature') not in plugin.get_item_list()

    def test_items_without_attribute_are_ignored(self, plugin, sh):
        assert item(sh, 'unrelated') not in plugin.get_item_list()


class TestPublish:
    def test_value_reaches_items_of_the_feature(self, plugin, sh):
        plugin._publish('battery', 77)

        assert item(sh, 'battery')() == 77
        assert plugin.values['battery'] == 77

    def test_value_without_item_is_kept_for_the_web_interface(self, plugin, sh):
        plugin._publish('error_code', 105)

        assert plugin.values['error_code'] == 105


class TestRoomSettings:
    rooms = [{'id': 3, 'name': 'Default', 'map': '10'}, {'id': 3, 'name': 'Default', 'map': '20'}]

    def test_names_and_preselection_of_the_map_reach_the_rooms_item(self, sh):
        plugin = make_plugin(
            sh,
            room_names=[{'map': '10', 'room': 3, 'name': 'Küche'}, {'map': '20', 'room': 3, 'name': 'Bad'}],
            room_preselect=[{'map': '20', 'room': 3}],
        )
        plugin.parse_item(item(sh, 'rooms'))

        plugin._publish('rooms', self.rooms[:1])
        assert item(sh, 'rooms')() == [{'id': 3, 'name': 'Küche', 'map': '10', 'preselect': False}]

        plugin._publish('rooms', self.rooms[1:])
        assert item(sh, 'rooms')() == [{'id': 3, 'name': 'Bad', 'map': '20', 'preselect': True}]
        assert plugin.values['rooms'] == item(sh, 'rooms')()

    maps = [
        {'id': '10', 'name': 'EG', 'active': True, 'built': True},
        {'id': '20', 'name': 'OG', 'active': False, 'built': True},
    ]

    def by_map_name(self, sh):
        plugin = make_plugin(sh, room_names=[{'map': 'EG', 'room': 3, 'name': 'Küche'}])
        plugin.parse_item(item(sh, 'rooms'))
        return plugin

    def test_map_names_known_before_the_rooms_apply(self, sh):
        plugin = self.by_map_name(sh)

        plugin._publish('maps', self.maps)
        plugin._publish('rooms', self.rooms[:1])

        assert item(sh, 'rooms')()[0]['name'] == 'Küche'

    def test_rooms_published_before_the_map_names_are_updated_when_they_arrive(self, sh):
        plugin = self.by_map_name(sh)

        plugin._publish('rooms', self.rooms[:1])
        assert item(sh, 'rooms')()[0]['name'] == 'Default'

        plugin._publish('maps', self.maps)
        assert item(sh, 'rooms')()[0]['name'] == 'Küche'
        assert plugin.values['rooms'] == item(sh, 'rooms')()

    def test_other_values_are_not_touched(self, sh):
        plugin = make_plugin(sh, room_names=[{'room': 3, 'name': 'Küche'}])
        plugin.parse_item(item(sh, 'battery'))

        plugin._publish('battery', 55)

        assert item(sh, 'battery')() == 55


class TestItemWrites:
    @pytest.fixture
    def running(self, plugin):
        """Plugin with a live asyncio loop and a connected recording device."""
        store = CredentialStore(plugin._store._path)
        plugin.session = DeebotSession(store, 'a', 'b', 'DE', '', plugin._publish, True)
        plugin.start_asyncio(plugin.wait_for_asyncio_termination())
        while plugin.asyncio_state() != 'running':
            pass
        plugin.alive = True

        async def attach():
            info = await get_static_device_info('qhe2o2')
            assert info is not None
            async with aiohttp.ClientSession() as http:
                auth = Authenticator(create_rest_config(http, device_id='x', alpha_2_country='DE'), 'a', 'b')
                plugin.session._device = RecordingDevice(
                    DeviceInfo(
                        {'class': 'qhe2o2', 'company': 'eco-ng', 'did': 'd', 'name': 'n', 'resource': 'r'}, info
                    ),
                    auth,
                )

        plugin.run_asyncio_coro(attach())
        self.sent(plugin).clear()
        yield plugin
        plugin.stop_asyncio()

    def sent(self, plugin) -> list[Command]:
        async def settle():
            await asyncio.sleep(0.1)

        plugin.run_asyncio_coro(settle())
        return plugin.session._device.sent

    def test_item_write_sends_command(self, running, sh):
        write(running, sh, 'fan_speed', 'max')

        assert self.sent(running) == [SetFanSpeed(FanSpeedLevel.MAX)]

    def test_trigger_item_sends_command_and_resets(self, running, sh):
        write(running, sh, 'start', True)

        assert self.sent(running) == [CleanV2(CleanAction.START)]
        assert item(sh, 'start')() is False

    def test_room_list_item_sends_area_command_and_resets(self, running, sh):
        write(running, sh, 'clean_rooms', [3, 4])

        assert self.sent(running) == [CleanAreaV2(CleanMode.SPOT_AREA, [3, 4], 1)]
        assert item(sh, 'clean_rooms')() == []

    def test_invalid_value_sends_nothing(self, running, sh):
        write(running, sh, 'fan_speed', 'turbo')

        assert self.sent(running) == []

    def test_rejected_value_is_replaced_by_the_device_value(self, running, sh):
        running._publish('fan_speed', 'max')

        write(running, sh, 'fan_speed', 'turbo')
        self.sent(running)

        assert item(sh, 'fan_speed')() == 'max'

    def test_value_not_sent_to_disconnected_device_is_replaced_by_the_device_value(self, running, sh):
        running._publish('fan_speed', 'max')
        running.session._device = None

        write(running, sh, 'fan_speed', 'quiet')
        running.run_asyncio_coro(asyncio.sleep(0.1))

        assert item(sh, 'fan_speed')() == 'max'

    def test_update_by_plugin_itself_sends_nothing(self, running, sh):
        running._publish('fan_speed', 'max')
        running.update_item(item(sh, 'fan_speed'), running.get_fullname())

        assert self.sent(running) == []

    def test_clean_rooms_sends_area_command(self, running):
        assert running.clean_rooms([3, 4], 2) is True

        assert self.sent(running) == [CleanAreaV2(CleanMode.SPOT_AREA, [3, 4], 2)]

    def test_clean_rooms_with_invalid_arguments_sends_nothing(self, running):
        running.clean_rooms([], 1)

        assert self.sent(running) == []


class TestNotRunning:
    def test_item_write_is_ignored(self, plugin, sh):
        write(plugin, sh, 'start', True)

        assert item(sh, 'start')() is True

    def test_clean_rooms_reports_failure(self, plugin):
        assert plugin.clean_rooms([3], 1) is False

    def test_stop_forgets_the_device_values(self, plugin, sh):
        plugin._publish('battery', 77)

        plugin.stop()

        assert plugin.values == {}
        assert item(sh, 'battery')() == 77


class TestMapSvg:
    with open(os.path.join(FIXTURES_DIR, 'map.svg')) as file:
        svg = file.read()

    def published(self, sh, **parameters):
        plugin = make_plugin(sh, **parameters)
        plugin.parse_item(item(sh, 'map_svg'))
        plugin._publish('map_svg', self.svg)
        return plugin, item(sh, 'map_svg')()

    def test_svg_is_published_unchanged_by_default(self, sh):
        plugin, value = self.published(sh)

        assert value == self.svg
        assert plugin.values['map_svg'] == self.svg

    def test_configured_css_and_trace_option_apply(self, sh):
        plugin, value = self.published(sh, map_css='.u{fill: none}', map_trace=False)

        assert value.endswith('.u{fill: none}</style></svg>')
        assert 'stroke="#fff" stroke-linejoin' not in value
        assert plugin.values['map_svg'] == value


def test_unwritable_var_dir_fails_initialisation(sh, tmp_path):
    blocker = tmp_path / 'not_a_dir'
    blocker.write_text('')
    sh._var_dir = str(blocker)

    plugin = make_plugin(sh)

    assert plugin._init_complete is False
