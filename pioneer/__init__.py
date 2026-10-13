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

from __future__ import annotations
import builtins
import os
import sys
import time
from typing import Any

if __name__ == '__main__':
    builtins.SDP_standalone = True

    class SmartPlugin:
        pass

    class SmartPluginWebIf:
        pass

    BASE = os.path.sep.join(os.path.realpath(__file__).split(os.path.sep)[:-3])
    sys.path.insert(0, BASE)

else:
    # importing commands.py re-imports this module under its package name, also in standalone mode
    if not hasattr(builtins, 'SDP_standalone'):
        builtins.SDP_standalone = False

from lib.model.sdp.declarations import TransportRule
from lib.model.sdp.globals import PLUGIN_ATTR_MODEL, CONN_NET_TCP_CLI, CONN_SER_ASYNC
from lib.model.smartdeviceplugin import SmartDevicePlugin, Standalone
from lib.model.sdp.command import SDPCommandParseStr

# from .webif import WebInterface


class pioneer(SmartDevicePlugin):
    """Device class for Pioneer AV function."""

    PLUGIN_VERSION = '1.0.3'

    TRANSPORTS = (
        TransportRule(CONN_NET_TCP_CLI, requires='host'),
        TransportRule(CONN_SER_ASYNC, requires='serialport'),
    )
    COMMAND_CLASS = SDPCommandParseStr
    LINE_TERMINATED = True

    def _process_additional_data(self, command: str, data: Any, value: Any, custom: int, by: str | None = None):
        def read_group(cmd):
            if self._parameters[PLUGIN_ATTR_MODEL] == '':
                self.read_all_commands(f'ALL.{cmd}')
            else:
                self.read_all_commands(f'{self._parameters[PLUGIN_ATTR_MODEL]}.{cmd}')

        if command in ['zone1.control.power', 'zone2.control.power', 'zone3.control.power'] and value:
            self.logger.debug(f'Device is turned on by command {command}. Requesting settings.')
            time.sleep(1)
            read_group('general.settings')

        if command in ['zone1.control.input', 'zone2.control.input', 'zone3.control.input']:
            if value == 'INTERNET RADIO':
                self.logger.debug('Zone is set to internet radio, checking tuner info.')
                time.sleep(1)
                read_group('tuner')
            if value == 'TUNER':
                self.logger.debug('Zone is set to tuner, checking tuner preset.')
                time.sleep(1)
                self.send_command('tuner.tunerpreset')


if __name__ == '__main__':
    s = Standalone(pioneer, sys.argv[0])
