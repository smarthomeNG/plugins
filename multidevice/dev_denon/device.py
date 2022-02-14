#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

if MD_standalone:
    from MD_Globals import (PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_CONNECTION, PLUGIN_ATTR_SERIAL_PORT, PLUGIN_ATTR_CONN_TERMINATOR, CONN_NET_TCP_CLI, CONN_SER_ASYNC)
    from MD_Device import MD_Device
else:
    from ..MD_Globals import (PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_CONNECTION, PLUGIN_ATTR_SERIAL_PORT, PLUGIN_ATTR_CONN_TERMINATOR, CONN_NET_TCP_CLI, CONN_SER_ASYNC)
    from ..MD_Device import MD_Device


CUSTOM_INPUT_NAME_COMMAND = 'custom_inputnames'


class MD_Device(MD_Device):
    """ Device class for Denon AV.

    Most of the work is done by the base class, so we only set default parameters
    for the connection (to be overwritten by device attributes from the plugin
    configuration) and add a fixed terminator byte to outgoing datagrams.

    The know-how is in the commands.py (and some DT_ classes...)
    """

    def _set_device_defaults(self):

        self._custom_inputnames = {}

        # set our own preferences concerning connections
        if PLUGIN_ATTR_NET_HOST in self._params and self._params[PLUGIN_ATTR_NET_HOST]:
            self._params[PLUGIN_ATTR_CONNECTION] = CONN_NET_TCP_CLI
        elif PLUGIN_ATTR_SERIAL_PORT in self._params and self._params[PLUGIN_ATTR_SERIAL_PORT]:
            self._params[PLUGIN_ATTR_CONNECTION] = CONN_SER_ASYNC
        if PLUGIN_ATTR_CONN_TERMINATOR in self._params:
            b = self._params[PLUGIN_ATTR_CONN_TERMINATOR].encode()
            b = b.decode('unicode-escape').encode()
            self._params[PLUGIN_ATTR_CONN_TERMINATOR] = b

    # we need to receive data via callback, as the "reply" can be unrelated to
    # the sent command. Getting it as return value would assign it to the wrong
    # command and discard it... so break the "return result"-chain
    def _send(self, data_dict):
        self._connection.send(data_dict)
        return None

    def _transform_send_data(self, data=None, **kwargs):
        if data:
            try:
                data['limit_response'] = self._params.get(PLUGIN_ATTR_CONN_TERMINATOR, b'\r')
                data['payload'] = f'{data.get("payload")}\r'
            except Exception as e:
                self.logger.error(f'ERROR {e}')
        return data

    def on_data_received(self, by, data, command=None):

        if command is not None:
            self.logger.debug(f'received data "{data}" for command {command}')
        else:
            # command == None means that we got raw data from a callback and don't know yet to
            # which command this belongs to. So find out...
            self.logger.debug(f'received data "{data}" without command specification')
            command = self._commands.get_command_from_reply(data)
            if not command:
                self.logger.debug(f'data "{data}" did not identify a known command, ignoring it')
                return

        self._check_for_custominputs(command, data)

        try:
            if CUSTOM_INPUT_NAME_COMMAND in command:
                value = self._custom_inputnames
            else:
                value = self._commands.get_shng_data(command, data)
        except Exception as e:
            self.logger.info(f'received data "{data}" for command {command}, error {e} occurred while converting. Discarding data.')
        else:
            self.logger.debug(f'received data "{data}" for command {command} converted to value {value}')
            if self._data_received_callback:
                self._data_received_callback(self.device_id, command, value)
            else:
                self.logger.warning(f'command {command} yielded value {value}, but _data_received_callback is not set. Discarding data.')

    def _check_for_custominputs(self, command, data):
        if CUSTOM_INPUT_NAME_COMMAND in command and isinstance(data, str):
            tmp = data.split(' ', 1)
            src = tmp[0][5:]
            name = tmp[1]
            self._custom_inputnames[src] = name
