#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022 <Onkel Andy>                    <onkelandy@hotmail.com>
#########################################################################
#  This file is part of SmartHomeNG
#
#  Logitech Mediaserver/Squeezebox plugin for SmartDevicePlugin class
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
#  along with SmartHomeNG  If not, see <http://www.gnu.org/licenses/>.
#########################################################################
from __future__ import annotations
from typing import Any, Tuple

import builtins
import os
import sys
import re

if __name__ == '__main__':
    builtins.SDP_standalone = True

    class SmartPlugin():
        pass

    class SmartPluginWebIf():
        pass

    BASE = os.path.sep.join(os.path.realpath(__file__).split(os.path.sep)[:-3])
    sys.path.insert(0, BASE)

else:
    builtins.SDP_standalone = False

from lib.model.sdp.globals import (CUSTOM_SEP, PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_RECURSIVE, PLUGIN_ATTR_CMD_CLASS,
                                   PLUGIN_ATTR_CONNECTION, PLUGIN_ATTR_CONN_TERMINATOR)
from lib.model.smartdeviceplugin import SmartDevicePlugin, Standalone
from lib.model.sdp.command import SDPCommandParseStr

import urllib.parse


class lms(SmartDevicePlugin):
    """ Device class for Logitech Mediaserver/Squeezebox function. """

    PLUGIN_VERSION = '2.0.0'

    def _set_device_defaults(self):
        self.custom_commands = 1
        self._token_pattern = '([0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2}'
        # for substitution in reply_pattern
        self._custom_patterns = {1: '(?:[0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2}', 2: '', 3: ''}
        self._use_callbacks = True
        self._parameters[PLUGIN_ATTR_RECURSIVE] = 1
        self._parameters[PLUGIN_ATTR_CMD_CLASS] = SDPCommandParseStr
        self._parameters[PLUGIN_ATTR_CONNECTION] = 'net_tcp_client'

        self._parameters['web_port'] = self.get_parameter_value('web_port')
        if self.get_parameter_value('web_host') == '':
            host = self._parameters.get(PLUGIN_ATTR_NET_HOST)
            if host.startswith('http'):
                self._parameters['web_host'] = host
            else:
                self._parameters['web_host'] = f'http://{host}'
        else:
            host = self.get_parameter_value('web_host')
            if host.startswith('http'):
                self._parameters['web_host'] = host
            else:
                self._parameters['web_host'] = f'http://{host}'
        self._parameters['CURRENT_LIST_ID'] = {}

    def on_connect(self, by=None):
        self.logger.debug(f"Activating listen mode after connection.")
        self.send_command('server.listenmode', True)
        self.logger.debug(f"Subscribing all players to playlist changes.")
        for player in self._custom_values.get(1):
            if player == '-':
                continue
            else:
                self.send_command('player.info.player.status_subscribe' + CUSTOM_SEP + player, True)

    def _transform_send_data(self, data=None, **kwargs):
        if isinstance(data, dict):
            data['limit_response'] = self._parameters[PLUGIN_ATTR_CONN_TERMINATOR]
            data['payload'] = f'{data.get("payload")}{data["limit_response"]}'
        return data

    def _transform_received_data(self, data):
        # fix weird representation of MAC address (%3A = :), etc.
        data_temp = data.replace("%20", "PPLACcCEHOLDERR")
        data = urllib.parse.unquote(data_temp)
        data = data.replace("PPLACcCEHOLDERR", "%20")
        return data

    def _process_additional_data(self, command: str, data: Any, value: Any, custom: int, by: str | None = None):

        def trigger_read(command):
            self.send_command(command + CUSTOM_SEP + custom)

        if command == f'server.newclient':
            self.logger.debug(f"Got new client connection {command}, re-reading players.")
            self.send_command('server.players')
            if value in self._custom_values.get(1):
                self.logger.debug(f"Subscribing to updates: {value}")
                self.send_command('player.info.player.status_subscribe' + CUSTOM_SEP + value, True)
                self.read_all_commands('player.info.currentsong' + CUSTOM_SEP + value)
                self.read_all_commands('player.control' + CUSTOM_SEP + value)

        if command == f'server.forgetclient':
            self.logger.debug(f"Got forget client connection {command}: {value}, re-reading players")
            self.send_command('server.players')

        if command == f'server.players':
            self.logger.debug(f"Got command players {command} data {data} value {value} by {by}")
            for player in self._custom_values.get(1):
                if player == '-':
                    continue
                elif player in value.keys():
                    self._dispatch_callback('player.info.player.modelname' + CUSTOM_SEP + player, value[player].get('modelname'), by)
                    self._dispatch_callback('player.info.player.firmware' + CUSTOM_SEP + player, value[player].get('firmware'), by)

        if command == f'database.rescan.running' and value is False:
            self.logger.debug(f"Got command rescan not running, {command} data {data} value {value} by {by}")
            self._dispatch_callback('database.rescan.progress', "", by)

        if command == f'server.playlists.delete':
            self.logger.debug(f"Got command delete playlist {command}, re-reading playlists")
            self.send_command('server.playlists.available')

        if command == f'server.syncgroups.members' and data:
            def find_player_index(target, mac_list):
                for index, item in enumerate(mac_list):
                    if re.search(rf'\b{re.escape(target)}\b', item):
                        return index  # Return the index where the match is found
                return -1

            self.logger.debug(f"Got command syncgroups {command} data {data} value {value} by {by}")
            for player in self._custom_values.get(1):
                idx = find_player_index(player, value)
                if idx >= 0:
                    synced = value[idx].split(",")
                    synced.remove(player)
                    self.logger.debug(f"Updating syncstatus of player {player} to {synced}")
                    self._dispatch_callback('player.control.sync_status' + CUSTOM_SEP + player, synced, by)
                else:
                    self._dispatch_callback('player.control.sync_status' + CUSTOM_SEP + player, [], by)
                    self._dispatch_callback('player.control.sync' + CUSTOM_SEP + player, '-', by)

        if not custom:
            return

        if command == f'player.info.player.connected{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got client (dis)connection {command}: {value}, re-reading players")
            self.send_command('server.players')

        if command == f'player.info.player.name{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got name {command}: {value}, re-reading players")
            self.send_command('server.players')

        if command == f'player.playlist.rename_current{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got command rename_current {command}, re-reading playlists")
            self.send_command('server.playlists.available')

        if command == f'player.playlist.delete_current{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got command delete_current {command}, re-reading playlists")
            self.send_command('server.playlists.available')

        if command == f'player.playlist.save{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got command save playlist {command}, re-reading playlists")
            self.send_command('server.playlists.available')

        if command == f'player.playlist.clear{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got command playlist clear {command}")
            trigger_read('player.info.player.status')

        if command == f'player.playlist.tracks{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got command playlist tracks, most likely because playlist was changed. Check modified {command}")
            trigger_read('player.playlist.modified')

        # set alarm
        if command == f'player.control.alarms{CUSTOM_SEP}{custom}':
            return
            # This does not really work currently. The created string is somehow correct.
            # However, much more logic has to be included to add/update/delete alarms, etc.
            try:
                for i in value.keys():
                    d = value.get(i)
                    alarm = f"id:{i} "
                    for k, v in d.items():
                        alarm += f"{k}:{v} "
                    alarm = f"add {alarm.strip()}"
                    self.logger.debug(f"Set alarm: {alarm}")
                    self.send_command('player.control.set_alarm' + CUSTOM_SEP + custom, alarm)
            except Exception as e:
                self.logger.error(f"Error setting alarm: {e}")

        # set album art URL
        if command == f'player.info.currentsong.album{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got command album {command} data {data} value {value} custom {custom} by {by}")
            host = self._parameters['web_host']
            port = self._parameters['web_port']
            if port == 0:
                url = f'{host}/music/current/cover.jpg?player={custom}'
            else:
                url = f'{host}:{port}/music/current/cover.jpg?player={custom}'
            self.logger.debug(f"Setting albumarturl to {url}")
            self._dispatch_callback('player.info.player.albumarturl' + CUSTOM_SEP + custom, url, by)

        # set playlist ID
        if command == f'player.playlist.load{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got command load {command} data {data} value {value} custom {custom} by {by}")
            trigger_read('player.playlist.current_id')
            trigger_read('player.control.playmode')

        if command == f'player.playlist.current_id{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got command id {command} data {data} value {value} custom {custom} by {by}")
            self._parameters['CURRENT_LIST_ID'][custom] = value
            trigger_read('player.playlist.current_name')
            trigger_read('player.playlist.current_url')

        if command == f'player.control.sync{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got command sync {command} data {data} value {value} custom {custom} by {by}")
            self.send_command('server.syncgroups.members')

        # update on new song
        if command == f'player.info.currentsong.title{CUSTOM_SEP}{custom}':
            # trigger_read('player.control.playmode')
            # trigger_read('player.playlist.index')
            trigger_read('player.info.currentsong.duration')
            trigger_read('player.info.currentsong.album')
            trigger_read('player.info.currentsong.artist')
            trigger_read('player.info.currentsong.genre')
            trigger_read('player.info.currentsong.file_path')

        # update on new song
        if command == f'player.control.playpause{CUSTOM_SEP}{custom}' and value:
            trigger_read('player.control.playmode')
            self.read_all_commands('player.info.currentsong' + CUSTOM_SEP + custom)

        # update on new song
        if command == f'player.playlist.index{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got command index {command} data {data} value {value} custom {custom} by {by}")
            trigger_read('player.control.playmode')
            self.read_all_commands('player.info.currentsong' + CUSTOM_SEP + custom)

        # update current time info
        if command in [f'player.control.forward{CUSTOM_SEP}{custom}', f'player.control.rewind{CUSTOM_SEP}{custom}']:
            self.logger.debug(f"Got command forward/rewind {command} data {data} value {value} custom {custom} by {by}")
            trigger_read('player.control.time')

        # update play and stop items based on playmode
        if command == f'player.control.playmode{CUSTOM_SEP}{custom}':
            self.logger.debug(f"Got command playmode {command} data {data} value {value} custom {custom} by {by}")
            mode = data.split("mode")[-1].strip()
            mode = mode.split("playlist")[-1].strip()
            self._dispatch_callback('player.control.playpause' + CUSTOM_SEP + custom,
                                    True if mode in ["play", "pause 0"] else False, by)
            self._dispatch_callback('player.control.stop' + CUSTOM_SEP + custom,
                                    True if mode == "stop" else False, by)
            trigger_read('player.control.time')

        # update play and stop items based on playmode
        if command == f'player.control.stop{CUSTOM_SEP}{custom}' or (command == f'player.control.playpause{CUSTOM_SEP}{custom}' and not value):
            self.logger.debug(f"Got command stop or pause {command} data {data} value {value} custom {custom} by {by}")
            trigger_read('player.control.playmode')


if __name__ == '__main__':
    s = Standalone(lms, sys.argv[0])
