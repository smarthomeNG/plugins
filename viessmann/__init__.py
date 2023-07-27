#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Sebastian Helms           Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG
#
#  Viessmann heating plugin for SmartDevicePlugin class
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

from lib.model.sdp.globals import PLUGIN_ATTR_SERIAL_PORT, PLUGIN_ATTR_PROTOCOL
from lib.model.smartdeviceplugin import SmartDevicePlugin, Standalone
from .protocol import SDPProtocolViessmann


if not SDP_standalone:
    from .webif import WebInterface


class sdp_viessmann(SmartDevicePlugin):
    """ Device class for Viessmann heating systems.

    Standalone mode is automatic device type discovery
    """
    PLUGIN_VERSION = '1.3.0'

    def _set_device_defaults(self):

        if not SDP_standalone:
            self._webif = WebInterface

        self._parameters[PLUGIN_ATTR_PROTOCOL] = SDPProtocolViessmann

#
# methods for standalone mode
#

    def run_standalone(self):
        """
        try to identify device
        """
        print(f'dev_viessmann trying to identify device at {self._parameters.get("serialport", "unknown")}...')
        devs = self.get_lookup('devicetypes')
        if not devs:
            devs = {}

        for proto in ('P300', 'KW'):

            res = self.get_device_type(proto)

            if res is None:

                # None means no connection, no further tries
                print(f'Connection could not be established to {self._parameters[PLUGIN_ATTR_SERIAL_PORT]}. Please check connection.')
                break

            if res is False:

                # False means no comm init (only P300), go on
                print(f'Communication could not be established using protocol {proto}.')
            else:

                # anything else should be the devices answer, try to decode and quit
                print(f'Device ID is {res}, device type is {devs.get(res.upper(), "unknown")} supporting protocol {proto}')
                # break

    def read_addr(self, addr):
        """
        Tries to read a data point indepently of item config

        :param addr: data point addr (2 byte hex address)
        :type addr: str
        :return: Value if read is successful, None otherwise
        """
        addr = addr.lower()

        commandname = self._commands.get_command_from_reply(addr)
        if commandname is None:
            self.logger.debug(f'Address {addr} not defined in commandset, aborting')
            return None

        self.logger.debug(f'Attempting to read address {addr} for command {commandname}')

        return self.send_command(commandname)

    def read_temp_addr(self, addr, length=1, mult=0, signed=False):
        """
        Tries to read an arbitrary supplied data point indepently of device config

        :param addr: data point addr (2 byte hex address)
        :type addr: str
        :param len: Length (in byte) expected from address read
        :type len: num
        :param mult: value multiplicator
        :type mult: num
        :param signed: specifies signed or unsigned value
        :type signed: bool
        :return: Value if read is successful, None otherwise
        """
        # as we have no reference whatever concerning the supplied data, we do a few sanity checks...

        addr = addr.lower()
        if len(addr) != 4:              # addresses are 2 bytes
            self.logger.warning(f'temp address: address not 4 digits long: {addr}')
            return None

        for c in addr:                  # addresses are hex strings
            if c not in '0123456789abcdef':
                self.logger.warning(f'temp address: address digit "{c}" is not hex char')
                return None

        if length < 1 or length > 32:          # empiritistical choice
            self.logger.warning(f'temp address: len is not > 0 and < 33: {len}')
            return None

        # addr already known?
        cmd = self._commands.get_command_from_reply(addr)
        if cmd:
            self.logger.info(f'temp address {addr} already known for command {cmd}')
        else:
            # create temp commandset
            cmd = 'temp_cmd'
            cmdconf = {'read': True, 'write': False, 'opcode': addr, 'reply_token': addr, 'item_type': 'str', 'dev_datatype': 'H', 'params': ['value', 'mult', 'signed', 'len'], 'param_values': ['VAL', mult, signed, length]}
            self.logger.debug(f'Adding temporary command config {cmdconf} for command temp_cmd')
            self._commands._parse_commands(self.device_id, {cmd: cmdconf}, [cmd])

        try:
            res = self.read_addr(addr)
        except Exception as e:
            self.logger.error(f'Error on send: {e}')
            res = None

        try:
            del self._commands._commands['temp_cmd']
        except (KeyError, AttributeError):
            pass

        return res

    def write_addr(self, addr, value):
        """
        Tries to write a data point indepently of item config

        :param addr: data point addr (2 byte hex address)
        :type addr: str
        :param value: value to write
        :return: Value if read is successful, None otherwise
        """
        addr = addr.lower()

        commandname = self._commands.get_command_from_reply(addr)
        if commandname is None:
            self.logger.debug(f'Address {addr} not defined in commandset, aborting')
            return None

        self.logger.debug(f'Attempting to write address {addr} with value {value} for command {commandname}')

        return self.send_command(commandname, value)

    def get_device_type(self, protocol):

        serialport = self._parameters.get('serialport', None)

        # try to connect and read device type info from 0x00f8
        self.logger.info(f'Trying protocol {protocol} on device {serialport}')

        # first, initialize Viessmann object for use
        self.alive = True
        self._parameters['viess_proto'] = protocol
        self._parameters['protocol'] = 'viessmann'
        self._get_connection()
        self._dispatch_callback = self._cb_standalone

        err = None
        res = None
        try:
            res = self._connection.open()
        except Exception as e:
            err = e
        if not res:
            self.logger.info(f'Connection to {serialport} failed. Please check connection. {err if err else ""}')
            return None

        res = None
        try:
            res = self._connection._send_init_on_send()
        except Exception as e:
            err = e
        if not res:
            self.logger.info(f'Could not initialize communication using protocol {protocol}. {err if err else ""}')
            return False

        self._result = None
        try:
            self.read_temp_addr('00f8', 2, 0, False)
        except Exception as e:
            err = e

        if self._result is None:
            raise ValueError(f'Error on communicating with the device, no response received. {err if err else ""}')

        # let it go...
        self._connection.close()

        if self._result is not None:
            return self._result
        else:
            return None

    def _cb_standalone(self, command, value, by):
        self._result = value


if __name__ == '__main__':
    s = Standalone(sdp_viessmann, sys.argv[0])
