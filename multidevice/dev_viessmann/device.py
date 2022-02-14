#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab


if MD_standalone:
    from MD_Globals import PLUGIN_ATTR_SERIAL_PORT
    from MD_Device import MD_Device
else:
    from ..MD_Globals import PLUGIN_ATTR_SERIAL_PORT
    from ..MD_Device import MD_Device


class MD_Device(MD_Device):
    """ Device class for Viessmann heating systems.

    Standalone mode is automatic device type discovery
    """

#
# methods for standalone mode
#

    def run_standalone(self):
        """
        try to identify device
        """
        print(f'dev_viessmann trying to identify device at {self._params.get("serialport", "unknown")}...')
        devs = self.get_lookup('devicetypes')
        if not devs:
            devs = {}

        for proto in ('P300', 'KW'):

            res = self.get_device_type(proto)

            if res is None:

                # None means no connection, no further tries
                print(f'Connection could not be established to {self._params[PLUGIN_ATTR_SERIAL_PORT]}. Please check connection.')
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

        serialport = self._params.get('serialport', None)

        # try to connect and read device type info from 0x00f8
        self.logger.info(f'Trying protocol {protocol} on device {serialport}')

        # first, initialize Viessmann object for use
        self.alive = True
        self._params['viess_proto'] = protocol
        self._get_connection()
        self.set_runtime_data(callback=self._cb_standalone)

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

    def _cb_standalone(self, device_id, command, value):
        self._result = value
