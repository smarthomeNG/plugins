#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Sebastian Helms             Morg @ knx-user-forum
#########################################################################
#  This file aims to become part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  MD_Device for MultiDevice plugin
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
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import logging
import time
import sys
import re
from lib.shyaml import yaml_load
import importlib

if MD_standalone:
    from MD_Globals import (CONNECTION_TYPES, CONN_NULL, CONN_NET_TCP_REQ, CONN_SER_DIR, CUSTOM_SEP, PLUGIN_ATTRS, PLUGIN_ATTR_CB_ON_CONNECT, PLUGIN_ATTR_CB_ON_DISCONNECT, PLUGIN_ATTR_CMD_CLASS, PLUGIN_ATTR_CONNECTION, PLUGIN_ATTR_ENABLED, PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_PROTOCOL, PLUGIN_ATTR_RECURSIVE, PLUGIN_ATTR_SERIAL_PORT, PROTOCOL_TYPES, PROTO_NULL)
    from MD_Commands import MD_Commands
    from MD_Command import MD_Command
    from MD_Connection import MD_Connection
    from MD_Protocol import MD_Protocol
else:
    from .MD_Globals import (CONNECTION_TYPES, CONN_NULL, CONN_NET_TCP_REQ, CONN_SER_DIR, CUSTOM_SEP, PLUGIN_ATTRS, PLUGIN_ATTR_CB_ON_CONNECT, PLUGIN_ATTR_CB_ON_DISCONNECT, PLUGIN_ATTR_CMD_CLASS, PLUGIN_ATTR_CONNECTION, PLUGIN_ATTR_ENABLED, PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_PROTOCOL, PLUGIN_ATTR_RECURSIVE, PLUGIN_ATTR_SERIAL_PORT, PROTOCOL_TYPES, PROTO_NULL)
    from .MD_Commands import MD_Commands
    from .MD_Command import MD_Command
    from .MD_Connection import MD_Connection
    from .MD_Protocol import MD_Protocol


#############################################################################################################################################################################################################################################
#
# class MD_Device
#
#############################################################################################################################################################################################################################################

class MD_Device(object):
    """ MD_Device class to handle device instances in MultiDevice plugin

    This class is the base class for a simple device class. It can process
    commands by sending values to the device and collect data by parsing data
    received from the device.

    Configuration is done via ``dev_<device_type>/commands.py``
    (for documentation of the format see ``dev_example/commands.py``)

    :param device_type: device type as used in derived class names
    :param device_id: device id for use in item configuration and logs
    :type device_type: str
    :type device_id: str
    """
    ADDITIONAL_DEVICE_ATTRS = ('viess_proto',)

    def __init__(self, device_type, device_id, **kwargs):
        """
        This initializes the class object.

        As additional device classes are expected to be implemented as
        subclasses, most initialization steps are modularized as methods which
        can be overwritten as needed.

        As all pre-implemented methods are called in hopefully-logical sequence,
        this __init__ probably doesn't need to be changed.
        """
        # get MultiDevice.device logger (if not already defined by derived class calling us via super().__init__())
        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger('.'.join(__name__.split('.')[:-1]) + f'.{device_id}')
        if MD_standalone:
            self.logger = logging.getLogger('__main__')

        self.logger.info(f'initializing from device module {str(self.__class__).split(".")[-3]} with arguments {kwargs}')

        #
        # the following can be set in _set_device_defaults to customize device behaviour
        #

        # None for normal operations, 1..3 for combined custom commands (<command>#<customx>)
        self.custom_commands = None

        # for extraction of custom token from reply
        self._token_pattern = ''

        # for detection of custom tokens in reply_pattern
        self._custom_patterns = {1: '', 2: '', 3: ''}

        # set to True to use on_connect and on_disconnect callbacks
        self._use_callbacks = False

        #
        #
        #

        # set class properties
        self._connection = None                             # connection instance
        self._commands = None                               # commands instance
        self._custom_values = {1: [], 2: [], 3: []}         # keep custom123 values

        self.device_type = device_type
        self.device_id = device_id
        self.alive = False
        self.disabled = True
        self._discard_unknown_command = True                # by default, discard data not assignable to known command
        self._unknown_command = '.notify.'                  # if not discarding data, set this command instead
        self._runtime_data_set = False
        self._initial_values_read = False
        self._cyclic_update_active = False

        self._data_received_callback = None
        self._commands_read = {}
        self._commands_read_grp = {}
        self._commands_initial = []
        self._commands_cyclic = {}
        self._triggers_initial = []
        self._triggers_cyclic = {}

        # read device.yaml and set default attributes for device / connection
        try:
            self._set_default_params()
        except Exception as e:
            self.logger.error(f'couldn\'t load device defaults, disabling device. Error was: {e}')
            return

        self._params.update(kwargs)
        self._plugin = self._params.get('plugin', None)

        # possibly initialize additional (overwrite _set_device_defaults)
        self._set_device_defaults()

        # save modified value for passing to MD_Commands
        self._params['custom_patterns'] = self._custom_patterns

        # check if manually disabled
        if PLUGIN_ATTR_ENABLED in self._params and not self._params[PLUGIN_ATTR_ENABLED]:
            self.logger.info('device attribute "enabled" set to False, not loading device')
            return

        # this is only viable for the base class. All derived classes from
        # MD_Device will probably be created towards a specific command class
        # but, just in case, be well-behaved...
        self._command_class = self._params.get(PLUGIN_ATTR_CMD_CLASS, MD_Command)

        # try to read configuration files
        try:
            if not self._read_configuration():
                self.logger.error('configuration could not be read, device disabled')
                return
        except Exception as e:
            self.logger.error(f'configuration could not be read, device disabled. Original error: {e}')
            return

        # instantiate connection object
        self._connection = self._get_connection()
        if not self._connection:
            self.logger.error(f'could not setup connection with {kwargs}, device disabled')
            return

        # the following code should only be run if not called from subclass via super()
        if self.__class__ is MD_Device:
            self.logger.debug(f'device initialized from {self.__class__.__name__}')

        self.disabled = False

        # call method for possible custom work (overwrite _post_init)
        self._post_init()

    def start(self):
        if self.alive:
            return
        if self.disabled:
            self.logger.error('start method called, but device is disabled')
            return
        if self._runtime_data_set:
            self.logger.debug('start method called')
        else:
            self.logger.error('start method called, but runtime data not set, device (still) disabled')
            return

        self.alive = True
        self._connection.open()

        if self._connection.connected():
            self._read_initial_values()
            if not MD_standalone:
                self._create_cyclic_scheduler()

    def stop(self):
        self.logger.debug('stop method called')
        self.alive = False
        if self._plugin and self._plugin.scheduler_get(self.device_id + '_cyclic'):
            self._plugin.scheduler_remove(self.device_id + '_cyclic')
        self._connection.close()

    # def run_standalone(self):
    #     """
    #     If you want to provide a standalone function, you'll have to implement
    #     this function with the appropriate code. You can use all functions from
    #     the MultiDevice class (plugin), the devices, connections and commands.
    #     You do not have an sh object, items or web interfaces.
    #
    #     As the base class should not have this method, it is commented out.
    #     """
    #     pass

    def send_command(self, command, value=None, **kwargs):
        """
        Sends the specified command to the device providing <value> as data
        Not providing data will issue a read command, trying to read the value
        from the device and writing it to the associated item.

        :param command: the command to send
        :param value: the data to send, if applicable
        :type command: str
        :return: True if send was successful, False otherwise
        :rtype: bool
        """
        if not self.alive:
            self.logger.warning(f'trying to send command {command} with value {value}, but device is not active.')
            return False

        if not self._connection:
            self.logger.warning(f'trying to send command {command} with value {value}, but connection is None. This shouldn\'t happen...')
            return False

        kwargs.update(self._params)
        if self.custom_commands:
            try:
                command, custom_value = command.split(CUSTOM_SEP)
                if 'custom' not in kwargs:
                    kwargs['custom'] = {1: None, 2: None, 3: None}
                kwargs['custom'][self.custom_commands] = custom_value
            except ValueError:
                self.logger.debug(f'extracting custom token failed, maybe not present in command {command}')

        if not self._connection.connected():
            self._connection.open()
            if not self._connection.connected():
                self.logger.warning(f'trying to send command {command} with value {value}, but connection could not be established.')
                return False

        try:
            data_dict = self._commands.get_send_data(command, value, **kwargs)
        except Exception as e:
            self.logger.warning(f'command {command} with value {value} produced error on converting value, aborting. Error was: {e}')
            return False

        if data_dict['payload'] is None or data_dict['payload'] == '':
            self.logger.warning(f'command {command} with value {value} yielded empty command payload, aborting')
            return False

        data_dict = self._transform_send_data(data_dict, **kwargs)
        self.logger.debug(f'command {command} with value {value} yielded send data_dict {data_dict}')

        # if an error occurs on sending, an exception is thrown
        result = None
        try:
            result = self._send(data_dict)
        except OSError as e:  # Exception as e:
            self.logger.debug(f'error on sending command {command}, error was {e}')
            return False

        if result:
            self.logger.debug(f'command {command} received result {result}')
            try:
                value = self._commands.get_shng_data(command, result, **kwargs)
            except Exception as e:
                self.logger.info(f'command {command} received result {result}, error {e} occurred while converting. Discarding result.')
            else:
                self.logger.debug(f'command {command} received result {result}, converted to value {value}')
                if self._data_received_callback:
                    by = None
                    if self.custom_commands:
                        by = kwargs['custom'][self.custom_commands]
                        if custom_value:
                            command = command + CUSTOM_SEP + custom_value
                    self._data_received_callback(self.device_id, command, value, by)
                else:
                    self.logger.warning(f'command {command} received result {result}, but _data_received_callback is not set. Discarding result.')
        return True

    def on_data_received(self, by, data, command=None):
        """
        Callback function for received data e.g. from an event loop
        Processes data and dispatches value to plugin class

        :param command: the command in reply to which data was received
        :param data: received data in 'raw' connection format
        :param by: client object / name / identifier
        :type command: str
        """
        data = self._transform_received_data(data)
        if command is not None:
            self.logger.debug(f'received data "{data}" from {by} for command {command}')
        else:
            # command == None means that we got raw data from a callback and don't know yet to
            # which command this belongs to. So find out...
            self.logger.debug(f'received data "{data}" from {by} without command specification')
            command = self._commands.get_command_from_reply(data)
            if not command:
                if self._discard_unknown_command:
                    self.logger.debug(f'data "{data}" did not identify a known command, ignoring it')
                    return
                elif self._data_received_callback:
                    self.logger.debug(f'data "{data}" did not identify a known command, forwarding it anyway for {self._unknown_command}')
                    self._data_received_callback(self.device_id, self._unknown_command, data, by)

        custom = None
        if self.custom_commands:
            custom = self._get_custom_value(command, data)

        base_command = command
        value = None
        try:
            value = self._commands.get_shng_data(command, data)
            if custom:
                command = command + CUSTOM_SEP + custom
        except OSError as e:  # Exception as e:
            self.logger.info(f'received data "{data}" for command {command}, error {e} occurred while converting. Discarding data.')
        else:
            self.logger.debug(f'received data "{data}" for command {command} converted to value {value}')
            if self._data_received_callback:
                self._data_received_callback(self.device_id, command, value, by)
            else:
                self.logger.warning(f'command {command} yielded value {value}, but _data_received_callback is not set. Discarding data.')

        self._process_additional_data(base_command, data, value, custom, by)

    def read_all_commands(self, group=''):
        """
        Triggers all configured read commands or all configured commands of given group
        """
        if not group:
            for cmd in self._commands_read:
                self.send_command(cmd)
        else:
            if group in self._commands_read_grp:
                for cmd in self._commands_read_grp[group]:
                    self.send_command(cmd)

    def is_valid_command(self, command, read=None):
        """
        Validate if 'command' is a valid command for this device
        Possible to check only for reading or writing

        :param command: the command to test
        :type command: str
        :param read: check for read (True) or write (False), or both (None)
        :type read: bool | NoneType
        :return: True if command is valid, False otherwise
        :rtype: bool
        """
        if self.custom_commands:
            try:
                command, custom_value = command.split(CUSTOM_SEP)
                if custom_value not in self._custom_values[self.custom_commands]:
                    self.logger.debug(f'custom value {custom_value} not in known custom values {self._custom_values[self.custom_commands]}')
                    return None
            except ValueError:
                pass

        if self._commands:
            return self._commands.is_valid_command(command, read)
        else:
            return False

    def set_runtime_data(self, **kwargs):
        """
        Sets runtime data received from the plugin class

        data_received_callback takes one argument 'data'
        """
        try:
            self._commands_read = kwargs.get('read_commands', [])
            self._commands_read_grp = kwargs.get('read_commands_grp', [])
            self._commands_cyclic = kwargs.get('cycle_commands', [])
            self._commands_initial = kwargs.get('initial_commands', [])
            self._triggers_cyclic = kwargs.get('cycle_triggers', [])
            self._triggers_initial = kwargs.get('initial_triggers', [])
            self._data_received_callback = kwargs.get('callback', None)
            self._runtime_data_set = True
        except Exception as e:
            self.logger.error(f'error in runtime data: {e}.')

    def update_device_params(self, **kwargs):
        """
        Updates / changes configuration parametes for device. Needs device to not be running

        overwrite as needed.
        """
        if self.alive:
            self.logger.warning(f'tried to update params with {kwargs}, but device is still running. Ignoring request')
            return

        if not kwargs:
            self.logger.warning('update_device_params called without new parameters. Don\'t know what to update.')
            return

        # merge new params with self._params, overwrite old values if necessary
        self._params.update(kwargs)

        # update = recreate the connection with new parameters
        self._connection = self._get_connection()

    def get_lookup(self, lookup, mode='fwd'):
        """ returns the lookup table for name <lookup>, None on error """
        if self._commands:
            return self._commands.get_lookup(lookup, mode)
        else:
            return None

    def has_recursive_custom_attribute(self, index=1):
        rec = self._params.get(PLUGIN_ATTR_RECURSIVE, [])
        if isinstance(rec, list):
            return index in rec
        else:
            return rec == index

    def set_custom_item(self, item, command, index, value):
        """ this is called by parse_items if md_custom[123] is found. """
        self._custom_values[index].append(value)
        self._custom_values[index] = list(set(self._custom_values[index]))

    #
    #
    # check if overwriting needed
    #
    #

    def _set_device_defaults(self):
        """ Set custom class properties. Overwrite as needed... """

        # if you want to enable callbacks, overwrite this method and set
        # self._use_callbacks = True
        pass

    def _post_init(self):
        """ do something after default initializing is done. Overwrite if needed.

        If for some reason you find compelling argument to stop loading the
        device instance, set self._disabled to true.
        """
        pass

    def _transform_send_data(self, data_dict, **kwargs):
        """
        This method provides a way to adjust, modify or transform all data before
        it is sent to the device.
        This might be to add general parameters, include custom attributes,
        add/change line endings or add your favourite pet's name...
        By default, nothing happens here.
        """
        return data_dict

    def _transform_received_data(self, data):
        """
        This method provides a way to adjust, modify or transform all data as soon
        as it is received from the device.
        This might be useful to clean or parse data.
        By default, nothing happens here.
        """
        return data

    def _send(self, data_dict):
        """
        This method acts as a overwritable intermediate between the handling
        logic of send_command() and the connection layer.
        If you need any special arrangements for or reaction to events on sending,
        you can implement this method in your derived MD_Device-class in the
        dev_foo/device.py device file.

        By default, this just forwards the data_dict to the connection instance
        and return the result.
        """
        return self._connection.send(data_dict)

    def on_connect(self, by=None):
        """ callback if connection is made. """
        pass

    def on_disconnect(self, by=None):
        """ callback if connection is broken. """
        pass

    def _get_custom_value(self, command, data):
        """ extract custom value from data. At least PATTERN Needs to be overwritten """
        if not self.custom_commands:
            return None
        if not isinstance(data, str):
            return None
        res = re.search(self._token_pattern, data)
        if not res:
            self.logger.debug(f'custom token not found in {data}, ignoring')
            return None
        elif res[0] in self._custom_values[self.custom_commands]:
            return res[0]
        else:
            self.logger.debug(f'received custom token {res[0]}, not in list of known tokens {self._custom_values[self.custom_commands]}')
            return None

    def _process_additional_data(self, command, data, value, custom, by):
        """ do additional processing of received data

        Here you can do additional data examinating, filtering and possibly
        triggering additional commands or setting additional items.
        Overwrite as needed.
        """
        pass

    #
    #
    # utility methods
    #
    #

    def _set_default_params(self):
        """ load default params from device.yaml """
        if MD_standalone:
            info_file = 'plugins/multidevice/dev_' + self.device_type + '/device.yaml'
        else:
            info_file = '/'.join(__name__.split('.')[:-1]) + '/dev_' + self.device_type + '/device.yaml'
        self._device_config = yaml = yaml_load(info_file, ordered=False, ignore_notfound=True)

        # if derived class sets defaults before calling us, they must not be
        # overwritten
        if not hasattr(self, '_params'):
            self._params = {}

        p = yaml.get('parameters', {})
        self._params.update({k: v.get('default', None) for k, v in p.items() if k in (PLUGIN_ATTRS + self.ADDITIONAL_DEVICE_ATTRS)})

    def _get_connection(self):
        """
        return connection object. Try to identify the wanted connection  and return
        the proper subclass instead. If no decision is possible, just return an
        instance of MD_Connection.

        If the PLUGIN_ATTR_PROTOCOL parameter is set, we need to change something.
        In this case, the protocol instance takes the place of the connection
        object and instantiates the connection object itself. Instead of the name
        of the connection class, we pass the class itself, so instantiating it
        poses no further challenge.

        If you need to use other connection types for your device, implement it
        and preselect with PLUGIN_ATTR_CONNECTION in /etc/plugin.yaml, so this
        class will never be used.
        """
        if self._use_callbacks:
            self.logger.debug('setting callbacks')
            self._params[PLUGIN_ATTR_CB_ON_CONNECT] = self.on_connect
            self._params[PLUGIN_ATTR_CB_ON_DISCONNECT] = self.on_disconnect

        conn_type = None
        conn_classname = None
        conn_cls = None
        proto_type = None
        proto_classname = None
        proto_cls = None

        mod_str = 'MD_Connection'
        if not MD_standalone:
            mod_str = '.'.join(self.__module__.split('.')[:-2]) + '.' + mod_str
        conn_module = sys.modules.get(mod_str, '')
        if not conn_module:
            self.logger.error('unable to get object handle of MD_Connection module')
            return None

        # try to find out what kind of connection is wanted
        if PLUGIN_ATTR_CONNECTION in self._params:
            if isinstance(self._params[PLUGIN_ATTR_CONNECTION], type) and issubclass(self._params[PLUGIN_ATTR_CONNECTION], MD_Connection):
                conn_cls = self._params[PLUGIN_ATTR_CONNECTION]
                conn_classname = conn_cls.__name__
            elif self._params[PLUGIN_ATTR_CONNECTION] in CONNECTION_TYPES:
                conn_type = self._params[PLUGIN_ATTR_CONNECTION]
                if conn_type == CONN_NULL:
                    conn_classname = 'MD_Connection'
                    conn_cls = MD_Connection
            else:
                conn_classname = self._params[PLUGIN_ATTR_CONNECTION]

        if not conn_type and not conn_cls and not conn_classname:
            if PLUGIN_ATTR_NET_HOST in self._params and self._params[PLUGIN_ATTR_NET_HOST]:

                # no further information on network specifics, use basic HTTP TCP client
                conn_type = CONN_NET_TCP_REQ

            elif PLUGIN_ATTR_SERIAL_PORT in self._params and self._params[PLUGIN_ATTR_SERIAL_PORT]:

                # this seems to be a serial killer application
                conn_type = CONN_SER_DIR

            if not conn_type:
                # if not preset and not identified, use "empty" connection, e.g. for testing
                # when physical device is not present
                conn_classname = 'MD_Connection'

        if not conn_classname:
            conn_classname = 'MD_Connection_' + '_'.join([tok.capitalize() for tok in conn_type.split('_')])
        self.logger.debug(f'wanting connection class named {conn_classname}')

        if not conn_cls:
            conn_cls = getattr(conn_module, conn_classname, getattr(conn_module, 'MD_Connection'))

        self.logger.debug(f'using connection class {conn_cls}')

        # if protocol is specified, find second class
        if PLUGIN_ATTR_PROTOCOL in self._params:
            mod_str = 'MD_Protocol'
            if not MD_standalone:
                mod_str = '.'.join(self.__module__.split('.')[:-2]) + '.' + mod_str
            proto_module = sys.modules.get(mod_str, '')
            if not proto_module:
                self.logger.error('unable to get object handle of MD_Protocol module')
                return None

            if isinstance(self._params[PLUGIN_ATTR_PROTOCOL], type) and issubclass(self._params[PLUGIN_ATTR_PROTOCOL], MD_Connection):
                proto_cls = self._params[PLUGIN_ATTR_PROTOCOL]
            elif self._params[PLUGIN_ATTR_PROTOCOL] in PROTOCOL_TYPES:
                proto_type = self._params[PLUGIN_ATTR_PROTOCOL]
            else:
                proto_classname = self._params[PLUGIN_ATTR_PROTOCOL]

            if proto_type is None and not proto_cls and not proto_classname:
                # class not known and not provided
                self.logger.error(f'protocol {self._params[PLUGIN_ATTR_PROTOCOL]} specified, but unknown and not class type or class name')
                return None

            if proto_type == PROTO_NULL:
                proto_cls = MD_Protocol
            elif proto_type:
                proto_classname = 'MD_Protocol_' + '_'.join([tok.capitalize() for tok in proto_type.split('_')])

            if not proto_cls:
                proto_cls = getattr(proto_module, proto_classname, None)
                if not proto_cls:
                    self.logger.error(f'protocol {self._params[PLUGIN_ATTR_PROTOCOL]} specified, but not loadable')
                    return None

            self.logger.debug(f'using protocol class {proto_cls}')

            # set connection class in _params dict for protocol class to use
            self._params[PLUGIN_ATTR_CONNECTION] = conn_cls

            # return protocol instance as connection instance
            return proto_cls(self.device_type, self.device_id, self.on_data_received, **self._params)

        return conn_cls(self.device_type, self.device_id, self.on_data_received, **self._params)

    def _create_cyclic_scheduler(self):
        """
        Setup the scheduler to handle cyclic read commands and find the proper time for the cycle.
        """
        if not self.alive:
            return

        # did we get the plugin instance?
        if not self._plugin:
            return

        # find shortest cycle
        shortestcycle = -1
        for cmd in self._commands_cyclic:
            cycle = self._commands_cyclic[cmd]['cycle']
            if shortestcycle == -1 or cycle < shortestcycle:
                shortestcycle = cycle
        for grp in self._triggers_cyclic:
            cycle = self._triggers_cyclic[grp]['cycle']
            if shortestcycle == -1 or cycle < shortestcycle:
                shortestcycle = cycle

        # Start the worker thread
        if shortestcycle != -1:

            # Balance unnecessary calls and precision
            workercycle = int(shortestcycle / 2)

            # just in case it already exists...
            if self._plugin.scheduler_get(self.device_id + '_cyclic'):
                self._plugin.scheduler_remove(self.device_id + '_cyclic')
            self._plugin.scheduler_add(self.device_id + '_cyclic', self._read_cyclic_values, cycle=workercycle, prio=5, offset=0)
            self.logger.info(f'Added cyclic worker thread {self.device_id}_cyclic with {workercycle} s cycle. Shortest item update cycle found was {shortestcycle} s')

    def _read_initial_values(self):
        """
        Read all values configured to be read/triggered at startup / after reconnect
        """
        if self._initial_values_read:
            self.logger.debug('_read_initial_values() called, but inital values were already read. Ignoring')
        else:
            if self._commands_initial:  # also read after reconnect and not self._initial_values_read:
                self.logger.info('Starting initial read commands')
                for cmd in self._commands_initial:
                    self.logger.debug(f'Sending initial command {cmd}')
                    self.send_command(cmd)
                self._initial_values_read = True
                self.logger.info('Initial read commands sent')
            if self._triggers_initial:  # also read after reconnect and not self._initial_values_read:
                self.logger.info('Starting initial read group triggers')
                for grp in self._triggers_initial:
                    self.logger.debug(f'Triggering initial read group {grp}')
                    self.read_all_commands(grp)
                self.logger.info('Initial read group triggers sent')

    def _read_cyclic_values(self):
        """
        Recall function for cyclic scheduler. Reads all values configured to be read cyclically.
        """
        # check if another cyclic cmd run is still active
        if self._cyclic_update_active:
            self.logger.warning('Triggered cyclic command read, but previous cyclic run is still active. Check device and cyclic configuration (too much/too short?)')
            return
        else:
            self.logger.info('Triggering cyclic command read')

        # set lock
        self._cyclic_update_active = True
        currenttime = time.time()
        read_cmds = 0
        todo = []
        for cmd in self._commands_cyclic:

            # Is the command already due?
            if self._commands_cyclic[cmd]['next'] <= currenttime:
                todo.append(cmd)

        for cmd in todo:
            # as this loop can take considerable time, repeatedly check if shng wants to stop
            if not self.alive:
                self.logger.info('Stop command issued, cancelling cyclic read')
                return

            # also leave early on disconnect
            if not self._connection.connected():
                self.logger.info('Disconnect detected, cancelling cyclic read')
                return

            self.logger.debug(f'Triggering cyclic read of command {cmd}')
            self.send_command(cmd)
            self._commands_cyclic[cmd]['next'] = currenttime + self._commands_cyclic[cmd]['cycle']
            read_cmds += 1

        if read_cmds:
            self.logger.debug(f'Cyclic command read took {(time.time() - currenttime):.1f} seconds for {read_cmds} items')

        currenttime = time.time()
        read_grps = 0
        todo = []
        for grp in self._triggers_cyclic:

            # Is the trigger already due?
            if self._triggers_cyclic[grp]['next'] <= currenttime:
                todo.append(grp)

        for grp in todo:
            # as this loop can take considerable time, repeatedly check if shng wants to stop
            if not self.alive:
                self.logger.info('Stop command issued, cancelling cyclic trigger')
                return

            # also leave early on disconnect
            if not self._connection.connected():
                self.logger.info('Disconnect detected, cancelling cyclic trigger')
                return

            self.logger.debug(f'Triggering cyclic read of group {grp}')
            self.read_all_commands(grp)
            self._triggers_cyclic[grp]['next'] = currenttime + self._triggers_cyclic[grp]['cycle']
            read_grps += 1

        if read_grps:
            self.logger.debug(f'Cyclic triggers took {(time.time() - currenttime):.1f} seconds for {read_grps} groups')

        self._cyclic_update_active = False

    def _read_configuration(self):
        """
        This initiates reading of configuration.
        Basically, this calls the MD_Commands object to fill itselt; but if needed,
        this can be overwritten to do something else.
        """
        cls = None
        if isinstance(self._command_class, type):
            cls = self._command_class
        elif isinstance(self._command_class, str):

            mod_str = 'MD_Command'
            if not MD_standalone:
                mod_str = '..' + mod_str

            try:
                # get module
                cmd_module = importlib.import_module(mod_str, __name__)
            except Exception as e:
                raise ImportError(f'importing module {mod_str} failed. Error was: "{e}"')

            cls = getattr(cmd_module, self._command_class, None)

        if cls is None:
            cls = MD_Command
        self._commands = MD_Commands(self.device_type, self.device_id, cls, **self._params)
        return True
