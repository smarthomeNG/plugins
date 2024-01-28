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

import builtins
import os
import sys

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

from lib.model.sdp.globals import (CUSTOM_SEP, PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_RECURSIVE, PLUGIN_ATTR_CONN_TERMINATOR)
from lib.model.smartdeviceplugin import SmartDevicePlugin, Standalone

import urllib.parse


class lms(SmartDevicePlugin):
    """ Device class for Logitech Mediaserver/Squeezebox function. """

    PLUGIN_VERSION = '1.5.2'

    def _set_device_defaults(self):
        self.custom_commands = 1
        self._token_pattern = '([0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2}'
        # for substitution in reply_pattern
        self._custom_patterns = {1: '(?:[0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2}', 2: '', 3: ''}
        self._use_callbacks = True
        self._parameters[PLUGIN_ATTR_RECURSIVE] = 1
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

    def on_connect(self, by=None):
        self.logger.debug("Activating listen mode after connection.")
        self.send_command('server.listenmode', True)

    def _transform_send_data(self, data=None, **kwargs):
        if isinstance(data, dict):
            data['limit_response'] = self._parameters[PLUGIN_ATTR_CONN_TERMINATOR]
            data['payload'] = f'{data.get("payload")}{data["limit_response"]}'
        return data

    def _transform_received_data(self, data):
        # fix weird representation of MAC address (%3A = :), etc.
        return urllib.parse.unquote_plus(data)

    def _process_additional_data(self, command, data, value, custom, by):

        def trigger_read(command):
            self.send_command(command + CUSTOM_SEP + custom)

        if not custom:
            return

        if command == 'player.info.playlists.names':
            self.logger.debug(f"Got command playlist names {command} data {data} value {value} custom {custom} by {by}")
            trigger_read('player.playlist.id')
            trigger_read('player.playlist.name')

        if command == 'playlist.rename':
            trigger_read('info.playlists.names')
        # set alarm
        if command == 'player.control.alarms':
            # This does not really work currently. The created string is somehow correct.
            # However, much more logic has to be included to add/update/delete alarms, etc.
            try:
                for i in value.keys():
                    d = value.get(i)
                    alarm = f"id:{i} "
                    for k, v in d.items():
                        alarm += f"{k}:{v} "
                    alarm = f"alarm add {alarm.strip()}"
                    self.logger.debug(f"Set alarm: {alarm}")
                    self.send_command('player.control.set_alarm' + CUSTOM_SEP + custom, alarm)
            except Exception as e:
                self.logger.error(f"Error setting alarm: {e}")

        # set album art URL
        if command == 'player.info.album':
            self.logger.debug(f"Got command album {command} data {data} value {value} custom {custom} by {by}")
            host = self._parameters['web_host']
            port = self._parameters['web_port']
            if port == 0:
                url = f'{host}/music/current/cover.jpg?player={custom}'
            else:
                url = f'{host}:{port}/music/current/cover.jpg?player={custom}'
            self.logger.debug(f"Setting albumarturl to {url}")
            self._dispatch_callback('player.info.albumarturl' + CUSTOM_SEP + custom, url, by)

        # set playlist ID
        if command == 'player.playlist.load':
            self.logger.debug(f"Got command load {command} data {data} value {value} custom {custom} by {by}")
            trigger_read('player.playlist.id')
            trigger_read('player.control.playmode')

        if command == 'player.playlist.id':
            self.logger.debug(f"Got command id {command} data {data} value {value} custom {custom} by {by}")
            trigger_read('player.playlist.name')

        # update on new song
        if command == 'player.info.title':
            # trigger_read('player.control.playmode')
            # trigger_read('player.playlist.index')
            trigger_read('player.info.duration')
            trigger_read('player.info.album')
            trigger_read('player.info.artist')
            trigger_read('player.info.genre')
            trigger_read('player.info.path')

        # update on new song
        if command == 'player.control.playpause' and value:
            trigger_read('player.control.playmode')
            trigger_read('player.info.duration')
            trigger_read('player.info.album')
            trigger_read('player.info.artist')
            trigger_read('player.info.genre')
            trigger_read('player.info.path')

        # update on new song
        if command == 'player.playlist.index':
            self.logger.debug(f"Got command index {command} data {data} value {value} custom {custom} by {by}")
            trigger_read('player.control.playmode')
            trigger_read('player.info.duration')
            trigger_read('player.info.album')
            trigger_read('player.info.artist')
            trigger_read('player.info.genre')
            trigger_read('player.info.path')
            trigger_read('player.info.title')

        # update current time info
        if command in ['player.control.forward', 'player.control.rewind']:
            self.logger.debug(f"Got command forward/rewind {command} data {data} value {value} custom {custom} by {by}")
            trigger_read('player.control.time')

        # update play and stop items based on playmode
        if command == 'player.control.playmode':
            self.logger.debug(f"Got command playmode {command} data {data} value {value} custom {custom} by {by}")
            mode = data.split("mode")[-1].strip()
            mode = mode.split("playlist")[-1].strip()
            self._dispatch_callback('player.control.playpause' + CUSTOM_SEP + custom,
                                    True if mode in ["play", "pause 0"] else False, by)
            self._dispatch_callback('player.control.stop' + CUSTOM_SEP + custom,
                                    True if mode == "stop" else False, by)
            trigger_read('player.control.time')

        # update play and stop items based on playmode
        if command == 'player.control.stop' or (command == 'player.control.playpause' and not value):
            self.logger.debug(f"Got command stop or pause {command} data {data} value {value} custom {custom} by {by}")
            trigger_read('player.control.playmode')


if __name__ == '__main__':
    s = Standalone(lms, sys.argv[0])
