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
import time

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

from lib.model.sdp.globals import (PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_CONNECTION, PLUGIN_ATTR_SERIAL_PORT, PLUGIN_ATTR_CONN_TERMINATOR, PLUGIN_ATTR_CMD_CLASS, CONN_NULL, CONN_NET_TCP_CLI, CONN_SER_ASYNC)
from lib.model.smartdeviceplugin import SmartDevicePlugin, Standalone
from lib.model.sdp.command import SDPCommandParseStr

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
        self._use_callbacks = True
        self._custom_inputnames = {}

        # set our own preferences concerning connections
        if PLUGIN_ATTR_NET_HOST in self._parameters and self._parameters[PLUGIN_ATTR_NET_HOST]:
            self._parameters[PLUGIN_ATTR_CONNECTION] = CONN_NET_TCP_CLI
        elif PLUGIN_ATTR_SERIAL_PORT in self._parameters and self._parameters[PLUGIN_ATTR_SERIAL_PORT]:
            self._parameters[PLUGIN_ATTR_CONNECTION] = CONN_SER_ASYNC
        else:
            self.logger.error('Neither host nor serialport set, connection not possible. Using dummy connection, plugin will not work')
            self._parameters[PLUGIN_ATTR_CONNECTION] = CONN_NULL

        self._parameters[PLUGIN_ATTR_CMD_CLASS] = SDPCommandParseStr

        b = self._parameters[PLUGIN_ATTR_CONN_TERMINATOR].encode()
        b = b.decode('unicode-escape').encode()
        self._parameters[PLUGIN_ATTR_CONN_TERMINATOR] = b

    def _transform_send_data(self, data=None, **kwargs):
        if isinstance(data, dict):
            data['limit_response'] = self._parameters[PLUGIN_ATTR_CONN_TERMINATOR]
            data['payload'] = f'{data.get("payload", "")}{data["limit_response"].decode("unicode-escape")}'
        return data

    def _process_additional_data(self, command, data, value, custom, by):
        zone = 0
        if command == 'zone1.control.power':
            zone = 1
        elif command == 'zone2.control.power':
            zone = 2
        elif command == 'zone3.control.power':
            zone = 3
        if zone > 0 and value is True:
            self.logger.debug(f"Device is turned on by command {command}. Requesting current state of zone {zone}.")
            time.sleep(1)
            self.send_command(f'zone{zone}.control.mute')
            self.send_command(f'zone{zone}.control.sleep')
            self.send_command(f'zone{zone}.control.standby')
        if zone == 1 and value is True:
            self.send_command(f'zone{zone}.control.input')
            self.send_command(f'zone{zone}.control.volume')
            self.send_command(f'zone{zone}.control.listeningmode')


if __name__ == '__main__':
    s = Standalone(denon, sys.argv[0])
