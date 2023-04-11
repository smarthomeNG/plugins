#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 <Onkel Andy>                    <onkelandy@hotmail.com>
#########################################################################
#  This file is part of SmartHomeNG
#
#  Oppo UHD Player plugin for SmartDevicePlugin class
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

from lib.model.sdp.globals import (PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_CONNECTION, PLUGIN_ATTR_SERIAL_PORT, PLUGIN_ATTR_CONN_TERMINATOR, CONN_NET_TCP_CLI, CONN_SER_ASYNC)
from lib.model.smartdeviceplugin import SmartDevicePlugin, Standalone

if not SDP_standalone:
    #from .webif import WebInterface
    pass

CUSTOM_INPUT_NAME_COMMAND = 'custom_inputnames'


class oppo(SmartDevicePlugin):
    """ Device class for Oppo.

    Most of the work is done by the base class, so we only set default parameters
    for the connection (to be overwritten by device attributes from the plugin
    configuration) and add a fixed terminator byte to outgoing datagrams.

    The know-how is in the commands.py (and some DT_ classes...)
    """

    PLUGIN_VERSION = '1.0.0'

    def _set_device_defaults(self):

        # set our own preferences concerning connections
        if PLUGIN_ATTR_NET_HOST in self._parameters and self._parameters[PLUGIN_ATTR_NET_HOST]:
            self._parameters[PLUGIN_ATTR_CONNECTION] = CONN_NET_TCP_CLI
        elif PLUGIN_ATTR_SERIAL_PORT in self._parameters and self._parameters[PLUGIN_ATTR_SERIAL_PORT]:
            self._parameters[PLUGIN_ATTR_CONNECTION] = CONN_SER_ASYNC
        if PLUGIN_ATTR_CONN_TERMINATOR in self._parameters:
            b = self._parameters[PLUGIN_ATTR_CONN_TERMINATOR].encode()
            b = b.decode('unicode-escape').encode()
            self._parameters[PLUGIN_ATTR_CONN_TERMINATOR] = b
        self._use_callbacks = True
        self._last_command = ''

    def on_connect(self, by=None):
        verbose = self.get_items_for_mapping('general.verbose')[0].property.value
        self.logger.debug(f"Activating verbose mode {verbose} after connection.")
        self.send_command('general.verbose', verbose)

    def _send(self, data_dict):
        self.logger.debug(f"Sending data_dict {data_dict}")
        self._connection.send(data_dict)
        return None

    def _transform_send_data(self, data=None, **kwargs):
        try:
            self._last_command = kwargs['cmd']
        except Exception:
            pass
        if data:
            try:
                data['limit_response'] = self._parameters.get(PLUGIN_ATTR_CONN_TERMINATOR, b'\r')
                data['payload'] = f'{data.get("payload")}\r'
            except Exception as e:
                self.logger.error(f'ERROR {e}')
        return data

    def _process_additional_data(self, command, data, value, custom, by):

        def _trigger_read(command, custom=None):
            if custom:
                command = command + CUSTOM_SEP + custom
            self.logger.debug(f"Sending read command for {command}")
            self.send_command(command)

        if value == "ER INVALID":
            self.logger.warning(f"Command {command} with data {data} and value {value} did not work, got error response. Last Command: {self._last_command}")
            try:
                last_item = self.get_items_for_mapping(self._last_command)[0]
                prev_val = last_item.property.prev_value
                self._dispatch_callback(self._last_command, prev_val)
                self.logger.debug(f"Item {last_item} set to previous value {prev_val}")
            except Exception as e:
                self.logger.debug(f"Last value could not be set")

        if command == 'info.status':
            self.logger.debug(f"Got status {command} data {data} value {value} custom {custom} by {by}")
            if value == 'PLAY':
                self._dispatch_callback('control.playpause', True)
                self._dispatch_callback('control.stop', False)
            elif value.startswith('PAUS'):
                self._dispatch_callback('control.playpause', False)
                self._dispatch_callback('control.stop', False)
            elif value == 'STOP':
                self._dispatch_callback('control.playpause', False)
                self._dispatch_callback('control.stop', True)
        if command == 'info.trackinfo':
            self.logger.debug(f"Got trackinfo {command} data {data} value {value} custom {custom} by {by}")
            val = value.split(" ")
            self._dispatch_callback('control.title', val[0])
            self._dispatch_callback('control.chapter', val[1])
            self._dispatch_callback('info.displaytype', val[2])
            if val[2] == 'E':
                self._dispatch_callback('info.time.totalelapsed', val[3])
            elif val[2] == 'R':
                self._dispatch_callback('info.time.totalremaining', val[3])
            elif val[2] == 'T' or val[2] == 'C':
                self._dispatch_callback('info.time.titleelapsed', val[3])
            elif val[2] == 'X' or val[2] == 'K':
                self._dispatch_callback('info.time.titleremaining', val[3])

if __name__ == '__main__':
    s = Standalone(oppo, sys.argv[0])
