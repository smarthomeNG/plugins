#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022 <Onkel Andy>                    <onkelandy@hotmail.com>
#########################################################################
#  This file is part of SmartHomeNG
#
#  Pioneer AV plugin for SmartDevicePlugin class
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

    class SmartPlugin():
        pass

    class SmartPluginWebIf():
        pass

    BASE = os.path.sep.join(os.path.realpath(__file__).split(os.path.sep)[:-3])
    sys.path.insert(0, BASE)

from lib.model.sdp.globals import (PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_CONNECTION, PLUGIN_ATTR_CMD_CLASS,
                                   PLUGIN_ATTR_SERIAL_PORT, PLUGIN_ATTR_CONN_TERMINATOR,
                                   PLUGIN_ATTR_MODEL, CONN_NET_TCP_CLI, CONN_SER_ASYNC, CONN_NULL)
from lib.model.smartdeviceplugin import SmartDevicePlugin, Standalone
from lib.model.sdp.command import SDPCommandParseStr

# from .webif import WebInterface

builtins.SDP_standalone = False


class pioneer(SmartDevicePlugin):
    """ Device class for Pioneer AV function. """

    PLUGIN_VERSION = '1.0.3'

    def _set_device_defaults(self):
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
        cond1 = command == 'zone1.control.power' or command == 'zone2.control.power' or command == 'zone3.control.power'
        if cond1 and value:
            self.logger.debug(f"Device is turned on by command {command}. Requesting settings.")
            time.sleep(1)
            if self._parameters[PLUGIN_ATTR_MODEL] == '':
                self.read_all_commands('ALL.general.settings')
            else:
                self.read_all_commands(f'{self._parameters[PLUGIN_ATTR_MODEL]}.general.settings')
            #self.send_command('general.settings.language')
            #self.send_command('general.settings.speakersystem')
            #self.send_command('general.settings.surroundposition')
            #self.send_command('general.settings.xover')
            #self.send_command('general.settings.xcurve')
            #self.send_command('general.settings.hdmi.control')
            #self.send_command('general.settings.hdmi.controlmode')
            #self.send_command('general.settings.hdmi.arc')
            #self.send_command('general.settings.hdmi.standbythrough')


if __name__ == '__main__':
    s = Standalone(pioneer, sys.argv[0])
