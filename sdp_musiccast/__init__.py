#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Sebastian Helms           Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG
#
#  Yamaha MusicCast AV plugin for SmartDevicePlugin class
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

from lib.model.sdp.globals import (COMMAND_SEP, CUSTOM_SEP, PLUGIN_ATTR_RECURSIVE)
from lib.model.smartdeviceplugin import SmartDevicePlugin, Standalone

if not SDP_standalone:
    from .webif import WebInterface

from lib.network import Network
import json


class sdp_musiccast(SmartDevicePlugin):
    """
    Device class for Yamaha MusicCast devices.
    """
    _hosts = {}  # {'ip': 'custom_param'}
    _trigger_commands = {'netusb.play_info_updated': 'netusb.playinfo'}

    PLUGIN_VERSION = '1.1.0'

    def _set_device_defaults(self):
        self._discard_unknown_command = False
        self._use_callbacks = True

        if 'host' not in self._parameters or not self._parameters['host']:
            self.custom_commands = 1
            self._parameters[PLUGIN_ATTR_RECURSIVE] = 1

    def set_custom_item(self, item, command, index, value):
        super().set_custom_item(item, command, index, value)

        if value not in self._hosts.values():
            (ip, _, _) = Network.validate_inet_addr(value, 0)
            if ip:
                self.logger.debug(f'added host {value} with ip {ip} to host list')
                self._hosts[ip] = value
            else:
                self.logger.debug(f'couldn\'t get ip for host {value}, skipping')

    def on_connect(self, by=None):
        # redirect send_command() output to on_data_received
        self.logger.debug('redirecting callbacks')
        self._plugin_callback = self._dispatch_callback
        self._dispatch_callback = self.data_callback

    def _transform_send_data(self, data_dict, **kwargs):
        if self.custom_commands and 'custom' in kwargs:
            host = kwargs['custom'][self.custom_commands]
        else:
            host = self._parameters['host']

        # complete url in payload from command in payload
        url = f'http://{host}/YamahaExtendedControl/{data_dict["payload"]}'
        headers = {
            'X-AppName': 'MusicCast/0.42',
            'X-AppPort': f'{self._parameters["port"]}'
        }
        data_dict['payload'] = url
        data_dict['headers'] = headers

        if data_dict['data'] is not None:
            data_dict['request_method'] = 'post'
        else:
            data_dict['request_method'] = 'get'

        return data_dict

    def data_callback(self, command, data, by=None):

        def _dispatch(command, value, custom=None):
            # send command via callback to plugin
            if custom:
                command = command + CUSTOM_SEP + custom
            if self._plugin_callback:
                self._plugin_callback(command, value, by)

        def _check_value(token, value, custom):
            # test if current token designates valid command and process it
            res = self._commands.get_command_from_reply(token)
            if res:
                self.logger.debug(f'found reply component {token} for command {res}, assigning value {value}')
                try:
                    value = self._commands.get_shng_data(res, value, custom={1: custom, 2: None, 3: None})
                except ValueError:
                    pass
                _dispatch(res, value, custom)

                # handle special case
                if res == 'info.inputs_raw':
                    _dispatch('info.inputs_sys', [el['id'] for el in value], custom)
                    _dispatch('info.inputs_user', [el['text'] for el in value], custom)

            else:
                if token in self._trigger_commands:
                    cmd = self._trigger_commands[token]
                    if custom:
                        cmd = cmd + CUSTOM_SEP + custom
                    self.logger.debug(f'found trigger command {token}, issuing command {cmd}')
                    self.send_command(cmd)

        # start method
        self.logger.debug(f'called musiccast on_data_received with command={command} and data={data} from {by}')

        if command == self._unknown_command:
            data = json.loads(data)

        # find possible custom item = host
        custom = None
        if self.custom_commands and by:
            if by in self._hosts:
                custom = self._hosts[by]
            else:
                custom = by
            self.logger.debug(f'found host {custom}')

        # handle returning information.
        if not isinstance(data, dict):
            self.logger.info(f'got unknown reply: {data}, ignoring.')
            return

        if data == {'response_code': 0}:
            # ok, no error, no answer
            self.logger.debug(f'command {command} executed without error.')
            return

        if 'response_code' in data and data['response_code']:
            # error, response_code != 0
            lu = self._commands._get_cmd_lookup('info.error')
            if lu:
                result = self._commands._lookup(data['response_code'], lu)
                _dispatch('info.error', result, custom)

        # check all keys in reply, test for valid reply tokens
        for l1 in list(data.keys()):
            if isinstance(data[l1], dict):
                for l2 in list(data[l1].keys()):
                    if isinstance(data[l1][l2], dict):
                        for l3 in list(data[l1][l2].keys()):
                            _check_value(l1 + COMMAND_SEP + l2 + COMMAND_SEP + l3, data[l1][l2][l3], custom)
                    else:
                        _check_value(l1 + COMMAND_SEP + l2, data[l1][l2], custom)
            else:
                _check_value(l1, data[l1], custom)


if __name__ == '__main__':
    s = Standalone(sdp_musiccast, sys.argv[0])
