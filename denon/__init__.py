#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 <Onkel Andy>                    <onkelandy@hotmail.com>
#########################################################################
#  This file is part of SmartHomeNG
#
#  Denon AV plugin for SmartDevicePlugin class
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

from lib.model.sdp.globals import (PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_CONNECTION, PLUGIN_ATTR_SERIAL_PORT, PLUGIN_ATTR_CONN_TERMINATOR, CONN_NULL, CONN_NET_TCP_CLI, CONN_SER_ASYNC)
from lib.model.smartdeviceplugin import SmartDevicePlugin, Standalone

# from .webif import WebInterface

builtins.SDP_standalone = False

CUSTOM_INPUT_NAME_COMMAND = 'custom_inputnames'


class denon(SmartDevicePlugin):
    """ Device class for Denon AV. """

    PLUGIN_VERSION = '1.0.1'

    def on_connect(self, by=None):
        self.logger.debug("Checking for custom input names.")
        self.send_command('general.custom_inputnames')

    def _set_device_defaults(self):

        self._custom_inputnames = {}

        # set our own preferences concerning connections
        if PLUGIN_ATTR_NET_HOST in self._parameters and self._parameters[PLUGIN_ATTR_NET_HOST]:
            self._parameters[PLUGIN_ATTR_CONNECTION] = CONN_NET_TCP_CLI
        elif PLUGIN_ATTR_SERIAL_PORT in self._parameters and self._parameters[PLUGIN_ATTR_SERIAL_PORT]:
            self._parameters[PLUGIN_ATTR_CONNECTION] = CONN_SER_ASYNC
        else:
            self.logger.error('Neither host nor serialport set, connection not possible. Using dummy connection, plugin will not work')
            self._parameters[PLUGIN_ATTR_CONNECTION] = CONN_NULL

        b = self._parameters[PLUGIN_ATTR_CONN_TERMINATOR].encode()
        b = b.decode('unicode-escape').encode()
        self._parameters[PLUGIN_ATTR_CONN_TERMINATOR] = b

    # we need to receive data via callback, as the "reply" can be unrelated to
    # the sent command. Getting it as return value would assign it to the wrong
    # command and discard it... so break the "return result"-chain and don't
    # return anything
    def _send(self, data_dict):
        self._connection.send(data_dict)

    def _transform_send_data(self, data=None, **kwargs):
        if isinstance(data, dict):
            data['limit_response'] = self._parameters[PLUGIN_ATTR_CONN_TERMINATOR]
            data['payload'] = f'{data.get("payload", "")}{data["limit_response"].decode("unicode-escape")}'
        return data

    def on_data_received(self, by, data, command=None):

        commands = None
        if command is not None:
            self.logger.debug(f'received data "{data}" from {by} for command {command}')
            commands = [command]
        else:
            # command == None means that we got raw data from a callback and
            # don't know yet to which command this belongs to. So find out...
            self.logger.debug(f'received data "{data}" from {by} without command specification')

            # command can be a string (classic single command) or
            # - new - a list of strings if multiple commands are identified
            # in that case, work on all strings
            commands = self._commands.get_commands_from_reply(data)
            if not commands:
                if self._discard_unknown_command:
                    self.logger.debug(f'data "{data}" did not identify a known command, ignoring it')
                    return
                else:
                    self.logger.debug(f'data "{data}" did not identify a known command, forwarding it anyway for {self._unknown_command}')
                    self._dispatch_callback(self._unknown_command, data, by)

        # TODO: remove later?
        assert(isinstance(commands, list))

        # process all commands
        for command in commands:
            self._check_for_custominputs(command, data)
            custom = None
            if self.custom_commands:
                custom = self._get_custom_value(command, data)

            base_command = command
            value = None
            try:
                if CUSTOM_INPUT_NAME_COMMAND in command:
                    value = self._custom_inputnames
                else:
                    value = self._commands.get_shng_data(command, data)
            except OSError as e:
                self.logger.warning(f'received data "{data}" for command {command}, error {e} occurred while converting. Discarding data.')
            else:
                self.logger.debug(f'received data "{data}" for command {command} converted to value {value}')
                self._dispatch_callback(command, value, by)

            self._process_additional_data(base_command, data, value, custom, by)

    def _check_for_custominputs(self, command, data):
        if CUSTOM_INPUT_NAME_COMMAND in command and isinstance(data, str):
            tmp = data.split(' ', 1)
            src = tmp[0][5:]
            name = tmp[1]
            self._custom_inputnames[src] = name

if __name__ == '__main__':
    s = Standalone(lms, sys.argv[0])
