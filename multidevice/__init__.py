#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Sebastian Helms             Morg @ knx-user-forum
#########################################################################
#  This file aims to become part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  MultiDevice plugin for handling arbitrary devices via network or serial
#  connection.
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

"""MultiDevice-Plugin to interface different devices

The MultiDevice-Plugin (MD)
===========================

This plugin aims to support a wide range of devices which work by sending
commands to a device and reading data from it. By abstracting devices and
connections, most devices will be able to be interfaced by this plugin.

General description
===================

The whole MultiDevice-plugin is organized and abstracted into multiple levels
of (reference) base classes and derived classes handling special
implementations.


The plugin manages item association and updates. For each device it handles, it
creates an object based on ``MD_Device`` or derived classes.

The device object handles starting and stopping the device and its
configuration as well as connecting the different layers.

Possible commands are bundled by the ``MD_Commands`` class which handles
loading, validating and calling the separate ``MD_Command`` or derived
objects.

Each ``MD_Command`` object handles one command and is responsible for creating
command tokens/strings to/from the real device.

Each command is assigned a data type, which is represented by a ``Datatype``-
derived class and transforms values between the real device and the command
object respectively the final SmartHomeNG item data type.

To actually talk to the real device, that is, send commands/values and receive
replies, it uses a standardized interface via one of the ``MD_Connection`` or
derived classes.

Thus, the plugin, devices and commands are ignorant of physical connection
details, the connection implementation is transparent regarding actual data
structures or content, and only the datatype classes need to concern itself
with validity of data sent or received.

.. note::
    Using the ``MD_Command_Str`` or especially the ``MD_Command_ParseStr`` classes,
    the need for specialized datatype classes **can** possibly be sidestepped.

    Be aware that while creating complex commands indeed can be fun, string
    parsing will not be able to detect or cope with some data type conversions.

    You have been warned 😉


(New) devices each reside in their respective subfolder of the plugin folder,
providing a derived device class, a device description file, a command definition
and - if applicable - additional necessary datatypes. These are automatically
loaded by the plugin if the respective device has a configuration entry in
``/etc/plugin.yaml``.


This concept is meant to

* minimize the amount of (repeating) code needed to implement a new device,
* make it easy to adjust functionality by deriving base classes, overriding
  methods without needing to adjust the remaining code,
* reduce implementing a new device (mostly) to properly defining the
  command API and datatypes,
* keeping individual devices separated and independent as each is loaded into
  its own module / namespace.

This comes at the cost of needing to understand the architecture of the plugin
to be able to decide what to change/extend and what to keep.


My hope is that with proper documentation and examples, this last part is
easier to achieve than having to rewrite the whole handling code for items,
network, serial interfaces and commands every time.

Thanks to OnkelAndy for kicking my backside repeatedly; otherwise the
development of this plugin might have stalled before being able to run ;)



Base Classes
============

MultiDevice
-----------

The ``MultiDevice``-class is derived from the ``SmartPlugin``-class and provides
the framework for handling item associations to the plugin, for storing
item-command associations, for forwarding commands and the associated data
to the device classes and receiving data from the device classes to update
item values.

This class will usually not need to be adjusted, but runs as the plugin itself.


Standalone mode
~~~~~~~~~~~~~~~

In addition, the plugin has a - limited - capability to run as a standalone
program. The main goal is running device-supplied functions, for example to
initiate a device discovery or diagnostic functions. To this end, it must be
run from the SmartHomeNG folder by issuing

``python3 plugins/multidevice/__init__.py <devicename> [<params>] [-v]``

Be advised that any functionality any device shall provide in this mode must
absolutely by implemented by you :) (that is, the device developer).


struct.yaml generation
~~~~~~~~~~~~~~~~~~~~~~

The second goal of standalone usage is creating ``struct.yaml`` template files
from device command configuration. To this end, run the plugin with the ``-s``
or the ``-S`` argument:

``python3 plugins/multidevice/__init__.py <devicename> -s``

The ``-s`` argument prints the struct file contents to screen, ``-S`` causes the
plugin to write the ``struct.yaml`` directly to the devices folder. Beware that
existing files _will_ be overwritten.

The additional argument ``-a`` instructs the generator to add ``visu_acl:`` item
attributes, setting the value to ``ro`` or ``rw`` depending on the write property
of the respective command.


When starting, MultiDevice will create a struct ``multidevice.<device_id>.MODEL``
for each device. If a model is configured, this struct will contain the model-
specific struct; if a model is not configured, this struct will contain the
generic struct ('ALL').


MD_Device
---------

The ``MD_Device``-class provides a framework for receiving (item) data values
from the plugin and forwarding them to the connection class and vice versa.
A basic framework for managing the device, i.e. (re-)configuring, starting
and stopping the device is already implemented and can be used via by device
configuration without the need for code changes.


``MD_Device(device_type, device_id, **kwargs)``


Public methods:

* ``start()``
* ``stop()``
* ``send_command(command, value=None, **kwargs)``
* ``read_all_commands(group=0)``
* ``is_valid_command(command, read=None)``
* ``set_runtime_data(**kwargs)``
* ``update_device_params(**kwargs)``
* ``get_lookup(lookup, mode='fwd')``
* ``has_recursive_custom_attribute(index=1)``
* ``set_custom_item(item, command, index, value)``


Public callback methods:

* ``on_data_received(by, data, command=None)``
* ``on_connect(by=None)``
* ``on_disconnect(by=None)``


Methods possibly needed to overwrite for inherited classes:

* ``_set_device_defaults()``
* ``_post_init()``
* ``_transform_send_data(data_dict, **kwargs)``
* ``_transform_received_data(data_dict)``
* ``_send(data_dict)``
* ``_get_custom_value(command, data)``
* ``_process_additional_data(command, data, custom)``
* ``run_standalone()``


MD_Connection
-------------

This class and the derived classes provide frameworks for sending and receiving
data to and from devices via serial or network connections. For both hardware
layers implementation of query-response-connections and listening servers with
asynchronous push-to-callback are already available. If more complex
communication setup is needed, this can be implemented on top of the existing
classes.


Data is exchanged with ``MD_Device`` in a special dict format:

.. code:: python

    data_dict = {
        'payload': raw data as needed by the connection,
        'data': data if not included in payload,
        'kw1': additional 'keyword' args or data specific to the connection type,
        'kw2': additional 'keyword' args or data specific to the connection type,
        '...': additional 'keyword' args or data specific to the connection type,
    }


``MD_Connection(device_type, device_id, data_received_callback, **kwargs)``


Public methods:

* ``open()``
* ``close()``
* ``send(data_dict)``
* ``connected()``


Public callback methods:

* ``on_data_received(by, data)``
* ``on_connect(by=None)``
* ``on_disconnect(by=None)``


Methods necessary to overwrite for derived classes:

* ``_open()``
* ``_close()``
* ``_send(data_dict)``


Methods possible to overwrite for derived classes:

* ``_send_init_on_open()``
* ``_send_init_on_send()``


This class has subclasses defined for the following types of connection:

* ``MD_Connection_Net_Tcp_Request`` for query-reply TCP connections
* ``MD_Connection_Net_Tcp_Client``  for persistent TCP connections with async replies
* ``MD_Connection_Net_Udp_Request`` for UDP listening server with async callback
* ``MD_Connection_Serial``          for query-reply serial connections
* ``MD_Connection_Serial_Async``    for event-loop serial connection with async callback

For detailed information and necessary configuration parameters, see the
respective class definition docstring.


MD_Protocol
-----------

For some device communication, the need arises to add another layer of protocol
handling - either for special handshake, initialization or general
communication and data handling, e.g. send queues or command tracking.

In these cases, instead of misusing the (physical) connection class or the
(command-oriented) device class, an additional protocol layer can be inserted
to handle this.


The ``MD_Protocol`` class is a subclass of ``MD_Connection`` and used by the
device instead of the actual connection class. The protocol class creates the
connection class instance itself and functions as a proxy.

To activate the protocol layer, configure the device with the ``protocol``
option, giving the name of an existing protocol class or the empty string for
the ``MD_Protocol`` base class, which has no additional function and can be
used for testing.

.. warning::

    Supplying the ``protocol`` attribute as a kind of 'empty default' is
    bound to break devices relying on protocol support.


The methods are the same as for the ``MD_Connection`` class.


This class has subclasses defined for the following types of protocols:

* ``MD_Protocol_Jsonrpc`` for JSON-RPC 2.0 protocol data exchange
* ``MD_Protocol_Viessmann`` for P300- and KW-protocol serial communication


MD_Commands
-----------

This class is a 'dict on steroids' of ``MD_Command``-objects with error checking
as added value. In addition, it also loads command and lookup definitions from
the file ``commands.py`` in the device folder and datatype sets and handles
datatype association.

No need to find out if ``command`` is defined, just call the method and the
class will handle failure cases. Beware of NoneType-return values, though.


``MD_Commands(device_type, device_id, command_obj_class=MD_Command, **kwargs)``


Public methods:

* ``is_valid_command(command, read=None)``
* ``get_send_data(command, data=None, **kwargs)``
* ``get_shng_data(command, data, **kwargs)``
* ``get_command_from_reply(data)``
* ``get_lookup(lookup, type='fwd')``


Options and syntax of commands configuration are detailed in the ``commands.py``
file in the ``dev_example`` folder:

.. literalinclude:: dev_example/commands.py
    :language: python


MD_Command
----------

This class contains information concerning the command name, the opcode or
URL needed to issue the command, and information about datatypes expected by
SmartHomeNG items and the device itself.

Its contents will be initialized by the ``MD_Commands``-class while reading the
command configuration.


``MD_Command(device_id, command, dt_class, **kwargs)``


Public methods:

* ``get_send_data(data, **kwargs)``
* ``get_shng_data(data, **kwargs)``
* ``get_lookup()``


Methods possible to overwrite:

* ``get_send_data(data, **kwargs)``
* ``get_shng_data(data, **kwargs)``
* ``_check_value(data)``


This class has subclasses defined for the following types of commands:

* ``MD_Command_Str``        for string-based communication with device
* ``MD_Command_ParseStr``   ditto with attribute parsing and regexes
* ``MD_Command_JSON``       for JSON-RPC 2.0 commands with multiple arguments
* ``MD_Command_Viessmann``  for the binary Viessmann heating protocols

The classes ``MD_Command_Str`` and ``MD_Command_ParseStr`` are examples for
defining own command classes according to your needs. These examples utilize
strings and dicts to build request URLs as payload data e.g. for the
``MD_Connection_Net_TCP_Request`` or ``MD_Connection_Net_Tcp_Client`` classes.
They also demonstrate parameter substitution in command definitions on
different levels of complexity.


Datatype
--------

This class contains information about the data type and format needed by
a device and methods to convert its value from selected Python data types
used in items to the (possibly) special data formats required by devices
and vice versa.

Datatypes are specified in subclasses of Datatype with a nomenclature
convention of ``DT_<device data type of format>``.

All default datatype classes are imported from ``datatypes.py`` into the 'DT' module.


New devices can ship their own needed datatype classes in a file called
``datatypes.py`` in the devices' folder.

For details concerning API and implementation, refer to the reference classes as
examples.


``Datatype(fail_silent=True)``


Public methods:

* ``get_send_data(data, **kwargs)``
* ``get_shng_data(data, type=None, **kwargs)``


Methods necessary to overwrite:

* ``get_send_data(data, **kwargs)``
* ``get_shng_data(data, type=None, **kwargs)``


Configuration
=============

The plugin class is capable of handling an arbitrary number of devices
independently. Necessary configuration include the chosen devices respectively
the device names and possibly device parameter in ``etc/plugin.yaml``.


Every device is identified by its type (which corresponds to the device folder
dev_<type>) and its id, which is the internal SmartHomeNG handle and the name
used in item configuration. If only one device of the same type is used, type
and id can be the same. The ``devices:``-attribute in ``plugin.yaml`` contains
a dict of all configured devices where the id is the key and the configuration
for the specific device is provided as 'dict in value' format, if needed.
The configuration can include the attribute ``device_type`` to specify the type
of the device (if different from the id) and - optionally - the attribute
``model``, if a device offers multiple model configurations.


The item configuration is supplemented by the attributes ``md_device`` and
``md_command``, which designate the device id from plugin configuration and
the command name from the device configuration, respectively.


The device class needs comprehensive configuration concerning available commands,
the associated sent and received data formats, which will be supplied by way
of configuration files in python format. Furthermore, the device-dependent
type and configuration of connection can be set in ``etc/plugin.yaml`` for
each device used, if the provided defaults are not sufficient.

For some device classes, it is possible to choose from different models. In
this case, the attribute ``model: <modelname>`` should be present. In any
other case, the ``model`` key should not be present.


The connection classes will be chosen and configured by the device classes.
They should not need further configuration, as all data transformation is done
by the device classes and the connection-specific attributes are provided
from plugin configuration.


If the additional protocol layer is necessary, usually the device class will
provide for proper loading (it loads the protocol in place of the connection
class). If for some reason the protocol layer should be selected and loaded
manually, it can be forced by providing the ``protocol: <protocolname>``
attribute. As with the model, this attribute should normally not be present
in the configuration.


When starting, MultiDevice will create a struct ``multidevice.<device_id>.MODEL``
for each device. If a model is configured, this struct will contain the model-
specific struct; if a model is not configured, this struct will contain the
generic struct ('ALL').

So the easiest way to configure items is using the struct generator and including
the `MODEL`-struct for each device.


Three custom item attributes exist, aptly named ``md_custom1`` through
``md_custom3``. These can be used by the device for arbitrary functions.
Unlike other item attributes, these can be configured to be used recursively,
meaning that it only needs to be set for one item and is used for all sub-items.
To effect this behaviour, the device configuration takes the parameter
``recursive_custom: <foo>``, where <foo> can be a number from 1 to 3 or a list
of any combination of the three.

A list and short description of all currently supported attributes is found in
the ``MD_Globals.py`` file next to their respective identifiers.


Example for ``etc/plugin.yaml`` configuration:

.. code:: yaml

    multidevice:
        plugin_name: multidevice
        devices:
            - <type>                    # id = <type>, type = <type>, folder = dev_<type>
                - param1: <value1>      #   optional
            - <id>:                     # id = <id>, type = <type>, folder = dev_<type>
                - device_type: <type>
                - param1: <value1>      #   optional
                - param2: <value2>      #   optional
            - dev1                      # id = dev1, type = dev1, folder = dev_dev1
            - mydev: dev2               # id = mydev, type = dev2, folder = dev_dev2
            - my2dev:                   # id = my2dev, type = dev3, folder = dev_dev3
                - device_type: dev3
                - device_model: foo     #   optional
                - host: somehost        #   optional
            - dev4:                     # id = dev4, type = dev4, folder = dev_dev4
                - host: someotherhost   #   optional


New devices
===========

A new device_type ``gadget`` can be implemented by providing the following:

* a device folder ``dev_gadget``
* a device description file defining configuration attributes ``dev_gadget/device.yaml``
* a device configuration file defining commands ``dev_gadget/commands.py``
* a device class file with a derived class ``dev_gadget/device.py`` (this can be
  an "empty" class containing only a ``pass`` statement)
* only if needed:

  * additional methods in the device class to handle special commands which
    do more than assign transformed item data to a single item or which need
    more complex item transformation
  * a data formats file defining data types ``dev_gadget/datatypes.py`` and
    additional data types in the datatype file
  * definition of lookup tables in ``dev_gadget/commands.py``

For examples on how to implement this, take a look at the dev_example folder
which contains simple examples as well as the reference documentation for the
commands.py file structure.

Also, take a look into the different existing device classes to get a feeling
for the needed effort to implement a new device. Both "simple" (all work is done
in the ``commands.py`` file) as well as more complex (extensive handling is added
in the ``device.py``file) devices are already provided and serve as examples.

Depending on the device protocol and command complexity, implementing a new
device can be a quick and easy job (e.g. for simple string or byte exchanges)
or requiring a more complex approach, e.g. if it is not practical to store all
information in items immediately, or if multiple data points are transmitted
at once, which requires splitting data or other means of data management.
"""

import importlib
import builtins
import logging
import re
import os
import sys
from copy import deepcopy
from ast import literal_eval
from collections import OrderedDict

__pdoc__ = {'multidevice.tools': False, 'multidevice.webif': False}

if __name__ == '__main__':
    # just needed for standalone mode
    builtins.MD_standalone = True

    class SmartPlugin():
        pass

    class SmartPluginWebIf():
        pass

    BASE = os.path.sep.join(os.path.realpath(__file__).split(os.path.sep)[:-3])
    sys.path.insert(0, BASE)

    from MD_Globals import (sanitize_param, update, CMD_ATTR_CMD_SETTINGS, CMD_ATTR_ITEM_ATTRS, CMD_ATTR_ITEM_TYPE, CMD_ATTR_LOOKUP, CMD_ATTR_OPCODE, CMD_ATTR_PARAMS, CMD_ATTR_READ, CMD_ATTR_READ_CMD, CMD_ATTR_WRITE, CMD_IATTR_ATTRIBUTES, CMD_IATTR_CYCLE, CMD_IATTR_ENFORCE, CMD_IATTR_INITIAL, CMD_IATTR_LOOKUP_ITEM, CMD_IATTR_READ_GROUPS, CMD_IATTR_RG_LEVELS, CMD_IATTR_TEMPLATE, COMMAND_READ, COMMAND_SEP, COMMAND_WRITE, CUSTOM_SEP, INDEX_GENERIC, INDEX_MODEL, ITEM_ATTR_COMMAND, ITEM_ATTR_CUSTOM_PREFIX, ITEM_ATTR_CYCLE, ITEM_ATTR_DEVICE, ITEM_ATTR_GROUP, ITEM_ATTR_LOOKUP, ITEM_ATTR_READ, ITEM_ATTR_READ_GRP, ITEM_ATTR_READ_INIT, ITEM_ATTR_WRITE, PLUGIN_ATTR_CLEAN_STRUCTS)
    from MD_Commands import MD_Commands

else:
    builtins.MD_standalone = False

    from lib.model.smartplugin import SmartPlugin
    import lib.shyaml as shyaml

    from .MD_Globals import (sanitize_param, update, CMD_ATTR_CMD_SETTINGS, CMD_ATTR_ITEM_ATTRS, CMD_ATTR_ITEM_TYPE, CMD_ATTR_LOOKUP, CMD_ATTR_OPCODE, CMD_ATTR_PARAMS, CMD_ATTR_READ, CMD_ATTR_READ_CMD, CMD_ATTR_WRITE, CMD_IATTR_ATTRIBUTES, CMD_IATTR_CYCLE, CMD_IATTR_ENFORCE, CMD_IATTR_INITIAL, CMD_IATTR_LOOKUP_ITEM, CMD_IATTR_READ_GROUPS, CMD_IATTR_RG_LEVELS, CMD_IATTR_TEMPLATE, COMMAND_READ, COMMAND_SEP, COMMAND_WRITE, CUSTOM_SEP, INDEX_GENERIC, INDEX_MODEL, ITEM_ATTR_COMMAND, ITEM_ATTR_CUSTOM_PREFIX, ITEM_ATTR_CYCLE, ITEM_ATTR_DEVICE, ITEM_ATTR_GROUP, ITEM_ATTR_LOOKUP, ITEM_ATTR_READ, ITEM_ATTR_READ_GRP, ITEM_ATTR_READ_INIT, ITEM_ATTR_WRITE, PLUGIN_ATTR_CLEAN_STRUCTS)
    from .webif import WebInterface


#############################################################################################################################################################################################################################################
#
# class MultiDevice
#
#############################################################################################################################################################################################################################################

class MultiDevice(SmartPlugin):
    """ MultiDevice class provides the SmartPlugin class for SmartHomeNG

    This class does the actual interface work between SmartHomeNG and the device
    classes. Mainly it parses plugin and item configuration data, sets up
    associations between devices and items and handles data exchange between
    SmartHomeNG and the device classes. Furthermore, it calls all devices'
    `run()` and `stop()` methods if so instructed by SmartHomeNG.

    It also looks good.
    """

    PLUGIN_VERSION = '0.4.0'

    def __init__(self, sh, standalone_device='', logger=None, **kwargs):
        """
        Initalizes the plugin. For this plugin, this means collecting all device
        modules and initializing them by instantiating the proper class.
        """
        if not sh:
            self.logger = logger

        self.logger.info(f'Initializing MultiDevice-Plugin as {__name__}')

        self._devices = {}              # contains all configured devices - <device_id>: {'device_type': <device_type>, 'device': <class-instance>, 'logger': <logger-instance>, 'params': {'param1': val1, 'param2': val2...}}
        self._items_write = {}          # contains all items with write command - <item_id>: {'device_id': <device_id>, 'command': <command>}
        self._items_read_all = {}       # contains items which trigger 'read all' - <item_id>: <device_id>
        self._items_read_grp = {}       # contains items which trigger 'read group foo' - <item_id>: [<device_id>, <foo>]
        self._commands_read = {}        # contains all commands per device with read command - <device_id>: {<command>: [<item_object>, <item_object>...]}
        self._commands_pseudo = {}      # contains all pseudo commands per device (without command sequence) - <device_id>: {<command>: [<item_object>, <item_object>...]}
        self._commands_read_grp = {}    # contains all commands per device with read group command - <device_id>: {<group>: [<command>, <command>...]}
        self._commands_initial = {}     # contains all commands per device to be read after run() is called - <device_id>: ['command', 'command', ...]
        self._commands_cyclic = {}      # contains all commands per device to be read cyclically - device_id: {<command>: {'cycle': <cycle>, 'next': <next>}}
        self._triggers_initial = {}     # contains all read groups per device to be triggered after run() is called - <device_id>: ['grp', 'grp', ...]
        self._triggers_cyclic = {}      # contains all read groups per device to be triggered cyclically - device_id: {<grp>: {'cycle': <cycle>, 'next': <next>}}
        self._items_custom = {}         # contains item md_custom<x> attributes - <item_id>: {1: custom1, 2: custom2, 3:custom3}

        self._sh = sh
        self._webif = None

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        if sh:
            # get the parameters for the plugin (as defined in metadata plugin.yaml):
            devices = self.get_parameter_value('devices')
        else:
            # set devices to 'only device, kwargs set as config'
            devices = {standalone_device: kwargs}

        # iterate over all items in plugin configuration 'devices' list
        #
        # example:
        #
        # multidevice:
        #     plugin_name: multidevice
        #     devices:
        #         - dev1                      # -> case 1, id = dev1, type = dev1, folder = dev_dev1
        #         - mydev: dev2               # -> case 2, id = mydev, type = dev2, folder = dev_dev2
        #         - my2dev:                   # -> case 3, id = my2dev, type = dev3, folder = dev_dev3
        #             - device_type: dev3
        #             - host: somehost
        #         - dev4:                     # -> case 4, id = dev4, type = dev4, folder = dev_dev4
        #             - host: someotherhost   #    handled implicitly by case 3

        for device in devices:
            param = {}
            if MD_standalone:

                device_type = device_id = device
                try:
                    for (k, v) in devices[device].items():
                        param[k] = sanitize_param(v)
                except Exception:
                    pass
            else:
                device_type = None
                if type(device) is str:
                    # case 1, device configuration is only string
                    device_type = device_id = device

                elif isinstance(device, OrderedDict):
                    # either we have devname: devid or devname: (list of arg: value)
                    device_id, conf = device.popitem()      # we only expect 1 pair per dict because of yaml parsing

                    if type(conf) is str:
                        # case 2, device_id: device_type
                        device_type = conf
                    # dev_id: (list of OrderedDict(arg: value))?
                    elif type(conf) is list and all(isinstance(arg, OrderedDict) for arg in conf):
                        # case 3, get device_type from parsing conf
                        device_type = device_id
                        for odict in conf:
                            for arg in odict.keys():

                                # store parameters
                                if arg == 'device_type':
                                    device_type = odict[arg]
                                else:
                                    param[arg] = sanitize_param(odict[arg])

                    else:
                        self.logger.warning(f'Configuration for device {device_id} has unknown format, skipping {device_id}')
                        device_type = device_id = None

            if device_id and device_id in self._devices:
                self.logger.warning(f'Duplicate device id {device_id} configured for device_types {device_type} and {self._devices[device_id]["device_type"]}. Skipping processing of spare device type {device_type}')
                continue

            # did we get a device type?
            if device_type:
                device_instance = None
                try:
                    # get module
                    mod_str = 'dev_' + device_type + '.device'
                    if not MD_standalone:
                        mod_str = '.' + mod_str
                    device_module = importlib.import_module(mod_str, __name__)
                    # get class
                    device_class = getattr(device_module, 'MD_Device')
                    # get class instance
                    device_instance = device_class(device_type, device_id, plugin=self, **param)
                except ImportError as e:
                    self.logger.warning(f'Importing external module {"dev_" + device_type + "/device.py"} for device {device_id} failed, disabling device. Error was: {e}')
                    device_instance = None

                if device_instance and not device_instance.disabled:

                    # create logger for device identity to use in update_item() and store in _devices dict
                    dev_logger = logging.getLogger(f'{__name__}.{device_id}')

                    # fill class dicts
                    self._devices[device_id] = {'device_type': device_type, 'device': device_instance, 'logger': dev_logger, 'params': param}
                    self._commands_read[device_id] = {}
                    self._commands_pseudo[device_id] = {}
                    self._commands_read_grp[device_id] = {}
                    self._commands_initial[device_id] = []
                    self._triggers_initial[device_id] = []
                    self._commands_cyclic[device_id] = {}
                    self._triggers_cyclic[device_id] = {}
                    dev_logger = None

                    # "alias" devices as class properties (prevent collisions)
                    if not hasattr(self, device_id):
                        setattr(self, device_id, self.get_device(device_id))

                    # check for and load struct definitions
                    if not MD_standalone:
                        self.logger.debug(f'trying to load struct definitions for device {device_id} from folder dev_{device_type}')
                        struct_file = os.path.join(self._plugin_dir, 'dev_' + device_type, 'struct.yaml')
                        raw_struct = shyaml.yaml_load(struct_file, ordered=True, ignore_notfound=True)

                        # if valid struct definition is found
                        if raw_struct is not None:

                            struct_list = list(raw_struct.keys())
                            self.logger.debug(f'loaded {len(struct_list)} structs for processing')
                            # replace all mentions of 'DEVICENAME' with the plugin/device's name
                            mod_struct = self._process_struct(raw_struct, device_id)

                            if param.get('model'):
                                mod_struct[INDEX_MODEL] = mod_struct[param['model']]
                            else:
                                mod_struct[INDEX_MODEL] = mod_struct[INDEX_GENERIC]

                            for struct_name in struct_list + [INDEX_MODEL]:
                                if struct_name in mod_struct:
                                    self.logger.debug(f'adding struct {self.get_shortname()}.{device_id}.{struct_name}')
                                    self._sh.items.add_struct_definition(self.get_shortname() + '.' + device_id, struct_name, mod_struct[struct_name])

        if not self._devices:
            self._init_complete = False
            self.logger.info('no devices configured, not loading plugin')
            return

        # if plugin should start even without web interface
        if sh:
            self.init_webinterface(WebInterface)

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug('Run method called')

        # hand over relevant assigned commands and runtime-generated data
        self._apply_on_all_devices('set_runtime_data', self._generate_runtime_data)

        # start the devices
        self.alive = True
        self._apply_on_all_devices('start')

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug('Stop method called')
        # self.scheduler_remove('poll_device')
        self.alive = False

        self._apply_on_all_devices('stop')

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is
        initialized. The plugin can, corresponding to its attribute keywords,
        decide what to do with the item in future, like adding it to an
        internal array for future reference
        :param item:    The item to process.
        :return:        Recall function for item updates
        """

        def find_custom_attr(item, index=1):
            """ find custom item attribute recursively. Returns attribute or None """
            # self.logger.debug(f'looking recursively for {ITEM_ATTR_CUSTOM_PREFIX + str(index)} in {item} with {item.conf}...')
            parent = item.return_parent()

            # parent(top_item) is sh.items
            if type(parent) != type(item):
                # reached top of item tree
                return None

            if self.has_iattr(parent.conf, ITEM_ATTR_CUSTOM_PREFIX + str(index)):
                return self.get_iattr_value(parent.conf, ITEM_ATTR_CUSTOM_PREFIX + str(index))

            return find_custom_attr(parent, index)

        # item is marked for plugin handling.
        device_id = self.get_iattr_value(item.conf, ITEM_ATTR_DEVICE)

        if device_id:

            # is device_id known?
            if device_id not in self._devices:
                self.logger.warning(f'Item {item} requests device {device_id}, which is not configured, ignoring item')
                return

            device = self.get_device(device_id)
            self.logger.debug(f'Item {item}: parse for device {device_id}')

            command = self.get_iattr_value(item.conf, ITEM_ATTR_COMMAND)

            # handle custom item attributes
            self._items_custom[item.id()] = {1: None, 2: None, 3: None}
            for index in (1, 2, 3):

                val = None
                if self.has_iattr(item.conf, ITEM_ATTR_CUSTOM_PREFIX + str(index)):
                    val = self.get_iattr_value(item.conf, ITEM_ATTR_CUSTOM_PREFIX + str(index))
                    self.logger.debug(f'Item {item} has custom item attribute {index} with value {val}')
                elif device.has_recursive_custom_attribute(index):
                    val = find_custom_attr(item, index)
                    if val is not None:
                        self.logger.debug(f'Item {item} inherited custom item attribute {index} with value {val}')
                if val is not None:
                    device.set_custom_item(item, command, index, val)
                    self._items_custom[item.id()][index] = val

            custom_token = ''
            if device.custom_commands and self._items_custom[item.id()][device.custom_commands]:
                custom_token = CUSTOM_SEP + self._items_custom[item.id()][device.custom_commands]

            if command:

                # command found, validate command for device
                if not device.is_valid_command(command):
                    self.logger.warning(f'Item {item} requests undefined command {command} for device {device_id}, ignoring item')
                    return

                # if "custom commands" are active for device <dev>, modify command to be
                # <command>#<customx>, where x is the index of the md_custom<x> item attribute
                # and <customx> is the value of the attribute.
                # By this modification, multiple items with the same command but different customx-Values
                # can "coexist" and be differentiated by the plugin and the device.
                command += custom_token

                # from here on command is combined if device.custom_commands is set and a valid custom token is found

                # command marked for reading
                if self.get_iattr_value(item.conf, ITEM_ATTR_READ):
                    if device.is_valid_command(command, COMMAND_READ):
                        if command not in self._commands_read[device_id]:
                            self._commands_read[device_id][command] = []
                        self._commands_read[device_id][command].append(item)
                        self.logger.debug(f'Item {item} saved for reading command {command} on device {device_id}')
                    else:
                        self.logger.warning(f'Item {item} requests command {command} for reading on device {device_id}, which is not allowed, read configuration is ignored')

                    # read in group?
                    group = self.get_iattr_value(item.conf, ITEM_ATTR_GROUP)
                    if group:
                        if isinstance(group, str):
                            group = [group]
                        if isinstance(group, list):
                            for grp in group:
                                if grp:
                                    grp += custom_token
                                    if grp not in self._commands_read_grp[device_id]:
                                        self._commands_read_grp[device_id][grp] = []
                                    self._commands_read_grp[device_id][grp].append(command)
                                    self.logger.debug(f'Item {item} saved for reading in group {grp} on device {device_id}')
                        else:
                            self.logger.warning(f'Item {item} wants to be read in group with invalid group identifier "{group}", ignoring.')

                    # read on startup?
                    if self.get_iattr_value(item.conf, ITEM_ATTR_READ_INIT):
                        if command not in self._commands_initial[device_id]:
                            self._commands_initial[device_id].append(command)
                            self.logger.debug(f'Item {item} saved for startup reading command {command} on device {device_id}')

                    # read cyclically?
                    cycle = self.get_iattr_value(item.conf, ITEM_ATTR_CYCLE)
                    if cycle:
                        # if cycle is already set for command, use the lower value of the two
                        self._commands_cyclic[device_id][command] = {'cycle': min(cycle, self._commands_cyclic[device_id].get(command, cycle)), 'next': 0}
                        self.logger.debug(f'Item {item} saved for cyclic reading command {command} on device {device_id}')

                # command marked for writing
                if self.get_iattr_value(item.conf, ITEM_ATTR_WRITE):
                    if device.is_valid_command(command, COMMAND_WRITE):
                        self._items_write[item.id()] = {'device_id': device_id, 'command': command}
                        self.logger.debug(f'Item {item} saved for writing command {command} on device {device_id}')
                        return self.update_item

                # pseudo commands
                if not self.get_iattr_value(item.conf, ITEM_ATTR_READ) and not self.get_iattr_value(item.conf, ITEM_ATTR_WRITE):
                    if command not in self._commands_pseudo[device_id]:
                        self._commands_pseudo[device_id][command] = []
                    self._commands_pseudo[device_id][command].append(item)
                    self.logger.debug(f'Item {item} saved for pseudo command {command} on device {device_id}')

            # is read_grp trigger item?
            grp = self.get_iattr_value(item.conf, ITEM_ATTR_READ_GRP)
            if grp:

                grp += custom_token
                item_msg = f'Item {item}'
                if custom_token:
                    item_msg += f' with token {custom_token}'
                item_msg += ' saved for '

                # trigger read on startup?
                if self.get_iattr_value(item.conf, ITEM_ATTR_READ_INIT):
                    if grp not in self._triggers_initial[device_id]:
                        self._triggers_initial[device_id].append(grp)
                        self.logger.debug(f'{item_msg} startup triggering of read group {grp} on device {device_id}')

                # read cyclically?
                cycle = self.get_iattr_value(item.conf, ITEM_ATTR_CYCLE)
                if cycle:
                    # if cycle is already set for command, use the lower value of the two
                    self._triggers_cyclic[device_id][grp] = {'cycle': min(cycle, self._triggers_cyclic[device_id].get(grp, cycle)), 'next': 0}
                    self.logger.debug(f'{item_msg} cyclic triggering of read group {grp} on device {device_id}')

                if grp == '0':
                    self._items_read_all[item.id()] = device_id
                    self.logger.debug(f'{item_msg} read_all on device {device_id}')
                    return self.update_item
                elif grp:
                    self._items_read_grp[item.id()] = [device_id, grp]
                    self.logger.debug(f'{item_msg} reading group {grp} on device {device_id}')
                    return self.update_item
                else:
                    self.logger.warning(f'Item {item} wants to trigger group read with invalid group identifier "{grp}", ignoring.')

            # is lookup table item?
            table = self.get_iattr_value(item.conf, ITEM_ATTR_LOOKUP)
            if table:
                mode = 'fwd'
                if '#' in table:
                    (table, mode) = table.split('#')
                lu = device.get_lookup(table, mode)
                item.set(lu, 'MultiDevice.' + device_id, source='Init')
                if lu:
                    self.logger.debug(f'Item {item} assigned lookup {table} from device {device_id} with contents {device.get_lookup(table)}')
                else:
                    self.logger.info(f'Item {item} requested lookup {table} from device {device_id}, which was empty or non-existent')

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by
        SmartHomeNG. It should write the changed value out to the device
        (hardware/interface) that is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive:

            self.logger.debug(f'Update_item was called with item "{item}" from caller {caller}, source {source} and dest {dest}')
            if not self.has_iattr(item.conf, ITEM_ATTR_DEVICE) and not self.has_iattr(item.conf, ITEM_ATTR_COMMAND):
                self.logger.warning(f'Update_item was called with item {item}, which is not configured for this plugin. This shouldn\'t happen...')
                return

            device_id = self.get_iattr_value(item.conf, ITEM_ATTR_DEVICE)

            # test if source of item change was not the item's device...
            if caller != self.get_shortname() + '.' + device_id:

                # from here on, use device's logger so messages are displayed for the device
                dev_log = self._get_device_logger(device_id)

                # okay, go ahead
                dev_log.info(f'Update item: {item.id()}: item has been changed outside this plugin')

                # item in list of write-configured items?
                if item.id() in self._items_write:

                    # get data and send new value
                    device_id = self._items_write[item.id()]['device_id']
                    device = self.get_device(device_id)
                    command = self._items_write[item.id()]['command']
                    dev_log.debug(f'Writing value "{item()}" from item {item.id()} with command "{command}"')
                    if not device.send_command(command, item(), custom=self._items_custom[item.id()]):
                        dev_log.debug(f'Writing value "{item()}" from item {item.id()} with command "{command}" failed, resetting item value')
                        item(item.property.last_value, self.get_shortname() + '.' + device_id)
                        return None

                elif item.id() in self._items_read_all:

                    # get data and trigger read_all
                    device_id = self._items_read_all[item.id()]
                    device = self.get_device(device_id)
                    dev_log.debug('Triggering read_all')
                    device.read_all_commands()

                elif item.id() in self._items_read_grp:

                    # get data and trigger read_grp
                    device_id, group = self._items_read_grp[item.id()]
                    device = self.get_device(device_id)
                    dev_log.debug(f'Triggering read_group {group}')
                    device.read_all_commands(group)

    def on_data_received(self, device_id, command, value, by=None):
        """
        Callback function - new data has been received from device.
        Value is already in item-compatible format, so find appropriate item
        and update value

        :param device_id: name of the originating device
        :param command: command for or in reply to which data was received
        :param value: data
        :type device_id: str
        :type command: str
        """
        if self.alive:

            # from here on, use device's logger so messages are displayed for the device
            dev_log = self._get_device_logger(device_id)
            item = None

            # check if combination of device_id and command is configured for reading
            if device_id in self._commands_read:
                items = self._commands_read[device_id].get(command, [])
            elif device_id in self._commands_pseudo:
                items = self._commands_pseudo[device_id].get(command, [])

            if not items:
                dev_log.warning(f'Command {command} yielded value {value}, not assigned to any item, discarding data')
                return

            for item in items:
                dev_log.debug(f'Command {command} updated item {item.id()} with value {value}')
                item(value, self.get_shortname() + '.' + device_id)

    def _update_device_params(self, device_id):
        """
        hand over all device parameters to the device and tell it to do whatever
        is necessary to apply the new values.
        The device _will_ ignore this while it is running. To avoid accidental
        service interruption, device.stop() is not called automatically.
        Do. this. yourself.

        :param device_id: device id (surprise!)
        :type device:name: string
        """
        if self.alive:
            return

        self.logger.debug(f'updating parameters for device {device_id}')
        device = self.get_device(device_id)
        if device:
            device.update_device_params(**self.get_device_params(device_id))

    def _apply_on_all_devices(self, method, args_function=None):
        """
        Call <method> on all devices stored in self._devices. If supplied,
        call args_function(device_id) for each device and hand over its
        returned dict as **kwargs.

        :param method: name of method to run
        :param args_function: function to build arguments dict
        :type method: str
        :type args_function: function
        """
        for device in self._devices:

            kwargs = {}
            if args_function:
                kwargs = args_function(device)
            getattr(self.get_device(device), method)(**kwargs)

    def _generate_runtime_data(self, device_id):
        """
        generate dict with device-specific data needed to run, which is
        - list of all 'read'-configured commands
        - dict of lists of all 'read group'-configured commands, key is group no
        - list of all cyclic commands with cycle times
        - list of all initial read commands
        - callback for returning data to the plugin
        """
        return {
            'read_commands': self._commands_read[device_id].keys(),
            'read_commands_grp': self._commands_read_grp[device_id],
            'cycle_commands': self._commands_cyclic[device_id],
            'cycle_triggers': self._triggers_cyclic[device_id],
            'initial_commands': self._commands_initial[device_id],
            'initial_triggers': self._triggers_initial[device_id],
            'callback': self.on_data_received
        }

    def get_device(self, device_id):
        """ getter method for device object """
        dev = self._devices.get(device_id, None)
        if dev:
            return dev['device']
        else:
            return None

    def _get_device_logger(self, device_id):
        """ getter for device logger, return plugin logger on error """
        log = self.logger
        dev = self._devices.get(device_id, None)
        if dev:
            log = dev.get('logger', self.logger)
        return log

    def _process_struct(self, raw_struct, device_id):
        """ clean structs before adding - remove unsupported commands """

        def walk(node, node_name, parent=None, func=None):
            for child in list(k for k in node.keys() if isinstance(node[k], OrderedDict)):
                walk(node[child], child, parent=node, func=func)
            if func is not None:
                func(node, node_name, parent=parent)

        def removeItemsUndefCmd(node, node_name, parent):
            if node.get(ITEM_ATTR_COMMAND, None) and not self._devices[device_id]['device'].is_valid_command(node.get(ITEM_ATTR_COMMAND, '')):
                del parent[node_name]

        def collectReadGroups(node, node_name, parent):
            self._collected_read_groups += node.get(ITEM_ATTR_GROUP, '')

        def removeItemsReadTrigger(node, node_name, parent):
            if ITEM_ATTR_READ_GRP in node:
                if node.get(ITEM_ATTR_READ_GRP) not in self._collected_read_groups:
                    del parent[node_name]

        def removeEmptyItems(node, node_name, parent):
            if len(node) == 0:
                del parent[node_name]

        # make struct items' md_device refer to our device
        try:
            mod_struct = eval(str(raw_struct).replace('DEVICENAME', device_id))
        except Exception as e:
            self.logger.warning(f'importing structs for device {device_id} failed, check struct definitions. Error was: {e}')
            return {}

        if not self._devices[device_id]['device']._params.get(PLUGIN_ATTR_CLEAN_STRUCTS, False):
            return mod_struct

        obj = OrderedDict({'structs': mod_struct})

        # remove all items with invalid 'md_command' attribute from structs
        walk(obj['structs'], 'structs', obj, removeItemsUndefCmd)

        # find all read groups
        self._collected_read_groups = []
        walk(obj['structs'], 'structs', obj, collectReadGroups)

        # remove all items with read group trigger for unknown read group
        self._collected_read_groups = set(self._collected_read_groups)
        walk(obj['structs'], 'structs', obj, removeItemsReadTrigger)

        # remove all empty items from structs
        walk(obj['structs'], 'structs', obj, removeEmptyItems)

        return obj['structs']


#############################################################################################################################################################################################################################################
#
#
# Standalone functions
#
#
#############################################################################################################################################################################################################################################

item_tree = {}


def create_struct_yaml(device, indentwidth=4, write_output=False, acl=False):
    """ read commands.py and export struct.yaml """
    global item_tree

    def add_item_to_tree(item_path, item_dict):
        """ add entry for custom read group triggers """
        global item_tree

        dst_path_elems = item_path.split('.')
        item = {dst_path_elems[-1]: item_dict}
        for elem in reversed(dst_path_elems[:-1]):
            item = {elem: item}

        update(item_tree, item)

    def walk(node, node_name, parent, func, path, indent, gpath, gpathlist, has_models, func_first=True, cut_levels=0):
        """ traverses a nested dict

        :param node: starting node
        :param node_name: name of the starting node on parent level ('key')
        :param parent: parent node
        :param func: function to call for each node
        :param path: path of the current node (pparent.parent.node)
        :param indent: indent level (indent is INDENT ** indent)
        :param gpath: path of 'current' (next above) read group
        :param gpathlist: list of all current (above) read groups
        :param has_models: True is command dict has models ('ALL') -> then include top level = model name in read groups and in command paths
        :param func_first: True if 'first work, then walk', False if 'first walk, then work'
        :param cut_levels: cut <n> levels from front of path
        :type node: dict
        :type node_name: str
        :type parent: dict
        :type func: function
        :type path: str
        :type indent: int
        :type gpath: str
        :type gpathlist: list
        :type has_models: bool
        :type func_first: bool
        """

        if func and func_first:
            # first call func -> print current node before descending
            func(node, node_name, parent, path, indent, gpath, gpathlist, cut_levels)

        # iterate over all children who are dicts
        for child in list(k for k in node.keys() if isinstance(node[k], dict)):

            # (path if path else ('' if has_models else node_name)) + ('.' if path or not has_models else '') + child
            if path:
                new_path = path + COMMAND_SEP
            elif not has_models:
                new_path = node_name + COMMAND_SEP
            else:
                new_path = ''
            new_path += child

            # and recursively walk them
            walk(node[child], child, node, func, new_path, indent + 1, path, gpathlist + ([path] if path else []), has_models, func_first, cut_levels)

        if func and not func_first:
            # last call func -> process current node after descending
            func(node, node_name, parent, path, indent, gpath, gpathlist)

    def find_read_group_triggers(node, node_name, parent, path, indent, gpath, gpathlist, cut_levels):
        """ find custom read trigger definitions, create trigger item

        for params see walk() above, they are the same there

        To keep things manageable, we only support relative addressing in the
        most simple form:

        ...path.to.item

        Every leading dot means 'up one level', so without a leading dot, the
        item will be created 'inside' the item with the 'read_groups' directive.
        """
        if CMD_ATTR_ITEM_ATTRS in node:
            # set sub-node for readability
            rg_list = node[CMD_ATTR_ITEM_ATTRS].get(CMD_IATTR_READ_GROUPS)
            if rg_list:
                if not isinstance(rg_list, list):
                    rg_list = [rg_list]
                for entry in rg_list:
                    itempath = entry.get('trigger')

                    # resolve relative item position
                    lvl_up = 0
                    while itempath[:1] == '.':
                        lvl_up += 1
                        itempath = itempath[1:]

                    if lvl_up:
                        src_path_elems = path.split(COMMAND_SEP)[:-lvl_up]
                    else:
                        src_path_elems = path.split(COMMAND_SEP)
                    item_path = '.'.join(['.'.join(src_path_elems), itempath])

                    add_item_to_tree(item_path, {'type': 'bool', 'enforce_updates': 'true', ITEM_ATTR_DEVICE: 'DEVICENAME', ITEM_ATTR_READ_GRP: entry.get('name')})

    def create_item(node, node_name, parent, path, indent, gpath, gpathlist, cut_levels=0):
        """ create item or read item for current node/command

        for params see walk() above, they are the same there
        """
        if not node_name:
            return

        # item name = item path is in path
        # item contents goes in item
        item = {}

        # skip known command sub-dict nodes, but include command nodes
        if CMD_ATTR_ITEM_TYPE in node or (node_name not in (CMD_ATTR_CMD_SETTINGS, CMD_ATTR_PARAMS, CMD_ATTR_ITEM_ATTRS, CMD_IATTR_ATTRIBUTES) and 'type' not in node):

            # item -> print item attributes
            if CMD_ATTR_ITEM_TYPE in node:
                item['type'] = node.get(CMD_ATTR_ITEM_TYPE, 'foo')
                item[ITEM_ATTR_DEVICE] = 'DEVICENAME'
                cmd = path if path else node_name
                if cut_levels:
                    cmd = COMMAND_SEP.join(cmd.split(COMMAND_SEP)[cut_levels:])
                item[ITEM_ATTR_COMMAND] = cmd
                item[ITEM_ATTR_READ] = node.get(CMD_ATTR_READ, True)
                item[ITEM_ATTR_WRITE] = node.get(CMD_ATTR_WRITE, False)
                if acl:
                    item['visu_acl'] = 'rw' if node.get(CMD_ATTR_WRITE, False) else 'ro'

                # set sub-node for readability
                inode = node.get(CMD_ATTR_ITEM_ATTRS)

                rg_level = None
                rg_list = None
                if inode:
                    rg_level = inode.get(CMD_IATTR_RG_LEVELS, None)
                    rg_list = inode.get(CMD_IATTR_READ_GROUPS)

                # rg_level = None: print all read groups (default)
                # rg_level = 0: don't print read groups
                # rg_level > 0: print last <x> levels of read groups plus custom read groups

                # only set read_groups if item 'can' trigger read.
                # no logging because standalone mode and syntax output active
                grps = gpathlist
                if rg_level != 0 and (node.get(CMD_ATTR_OPCODE) or node.get(CMD_ATTR_READ_CMD)):
                    if rg_level is not None:
                        grps = grps[-rg_level:]
                    if rg_list:
                        if not isinstance(rg_list, list):
                            rg_list = [rg_list]
                        for entry in rg_list:
                            grps.append(entry.get('name'))
                    item[ITEM_ATTR_GROUP] = grps

                if inode:
                    if inode.get(CMD_IATTR_ENFORCE):
                        item['enforce_updates'] = True
                    if inode.get(CMD_IATTR_INITIAL):
                        item[ITEM_ATTR_READ_INIT] = True
                    cycle = inode.get(CMD_IATTR_CYCLE)
                    if cycle:
                        item[ITEM_ATTR_CYCLE] = cycle

                    # custom item attributes: add 1:1
                    attrs = inode.get(CMD_IATTR_ATTRIBUTES)
                    if attrs:
                        update(item, attrs)

                    # custom item templates: add 1:!
                    templates = inode.get(CMD_IATTR_TEMPLATE)
                    if templates:
                        if not isinstance(templates, list):
                            templates = [templates]
                        for tmpl in templates:
                            if tmpl in item_templates:
                                update(item, item_templates[tmpl])

                    # if item has 'md_lookup' and item_attrs['lookup_item'] is set,
                    # create additional item with lookup values
                    lu_item = inode.get(CMD_IATTR_LOOKUP_ITEM)
                    if lu_item and node.get(CMD_ATTR_LOOKUP):
                        ltyp = inode.get(CMD_IATTR_LOOKUP_ITEM)
                        if ltyp is True:
                            ltyp = 'list'
                        item['lookup'] = {'type': 'list' if ltyp == 'list' else 'dict'}
                        item['lookup'][ITEM_ATTR_DEVICE] = 'DEVICENAME'
                        item['lookup'][ITEM_ATTR_LOOKUP] = f'{node.get(CMD_ATTR_LOOKUP)}#{ltyp}'

            # 'level node' -> print read item
            elif node_name not in (CMD_ATTR_CMD_SETTINGS, CMD_ATTR_PARAMS, CMD_ATTR_ITEM_ATTRS, CMD_IATTR_ATTRIBUTES, CMD_IATTR_READ_GROUPS):

                item['read'] = {'type': 'bool'}
                item['read']['enforce_updates'] = True
                item['read'][ITEM_ATTR_DEVICE] = 'DEVICENAME'
                item['read'][ITEM_ATTR_READ_GRP] = path if path else node_name
                try:
                    # set sub-node for readability
                    inode = node.get(CMD_ATTR_ITEM_ATTRS)
                    if inode.get(CMD_IATTR_INITIAL):
                        item['read'][ITEM_ATTR_READ_INIT] = True
                    if inode.get(CMD_IATTR_CYCLE):
                        item['read'][ITEM_ATTR_CYCLE] = inode.get(CMD_IATTR_CYCLE)
                except AttributeError:
                    pass

            if item:
                add_item_to_tree(path, item)

            if CMD_ATTR_ITEM_ATTRS in node:
                find_read_group_triggers(node, node_name, parent, path, indent, gpath, gpathlist, cut_levels)

    def print_item(node, node_name, parent, path, indent, gpath, gpathlist, cut_levels=0):
        """ print item """

        def p_text(text, add=0):
            """ print indented text """
            print(f'{INDENT * (indent + add)}{text}')

        # item / level definition
        p_text(f'{node_name}:')

        # print all non-dict children (dicts are visited later)
        for key in [key for key in node if not isinstance(node[key], dict)]:
            if isinstance(node[key], bool):
                p_text(f'{key}: {str(node[key]).lower()}', 1)
            else:
                p_text(f'{key}: {node[key]}', 1)

        print()

    def removeItemsUndefCmd(node, node_name, parent, path, indent, gpath, gpathlist, cut_levels=0):
        if CMD_ATTR_ITEM_TYPE in node and path not in cmdlist:
            del parent[node_name]

    def removeEmptyItems(node, node_name, parent, path, indent, gpath, gpathlist, cut_levels=0):
        if len(node) == 0:
            del parent[node_name]

    INDENT = ' ' * indentwidth
    MODELINE = f'# vim: expandtab:ts={indentwidth}:sw={indentwidth}'

    mod_str = 'plugins.multidevice.dev_' + device + '.commands'
    try:
        cmd_module = importlib.import_module(mod_str, __name__)
    except Exception as e:
        raise ImportError(f'error on importing commands, aborting. Error was {e}')

    commands = cmd_module.commands
    top_level_entries = list(commands.keys())

    item_templates = getattr(cmd_module, 'item_templates', {})
    old_stdout = sys.stdout
    err = None

    try:
        if write_output:
            file = 'plugins/multidevice/dev_' + device + '/struct.yaml'
            sys.stdout = open(file, 'w')

        print('%YAML 1.1')
        print('---')
        print(MODELINE)

        # this means the commands dict has 'ALL' and model names at the top level
        # otherwise, these be commands or sections
        cmds_has_models = INDEX_GENERIC in top_level_entries

        if cmds_has_models:

            for model in top_level_entries:

                # create model-specific commands dict
                m_commands = commands.get(INDEX_GENERIC, {})
                update(m_commands, commands.get(model))

                # create work obj for entry
                obj = {model: m_commands}

                item_tree = {}

                # create item tree
                walk(obj[model], '', None, create_item, '', 0, model, [model], True)

                # print item tree
                walk(item_tree, model, item_tree, print_item, '', 0, '', [], False)

        else:

            # create flat commands, 'valid command' comparison needs full cmd path
            flat_commands = deepcopy(commands)
            MD_Commands._flatten_cmds(None, flat_commands)

            # output sections separately and unchanged
            for section in top_level_entries:

                item_tree = {}

                obj = {section: commands[section]}

                # create item tree
                walk(obj[section], section, None, create_item, section, 0, '', [], True)

                # print item tree
                walk(item_tree[section], section, item_tree, print_item, '', 0, '', [], False)

            # get model definitions
            # if not present, fake it to include all sections
            models = getattr(cmd_module, 'models', [])
            if not models:
                models = {'ALL': list(commands.keys())}

            for model in models:

                item_tree = {}

                # create list of valid commands
                cmdlist = models[model]
                if model != INDEX_GENERIC:
                    cmdlist += models.get(INDEX_GENERIC, [])
                cmdlist = MD_Commands._get_cmdlist(None, flat_commands, cmdlist)

                # create new obj for model m, include m['ALL']
                # as we modify obj, we need to copy this
                obj = {model: deepcopy(commands)}

                # remove all items with model-invalid 'md_command' attribute obj
                walk(obj[model], model, obj, removeItemsUndefCmd, '', 0, model, [model], True, False)

                # remove all empty items from obj
                walk(obj[model], model, obj, removeEmptyItems, '', 0, model, [model], True, False)

                # create item tree
                walk(obj[model], model, obj, create_item, model, 0, '', [], False, cut_levels=1)

                # print item tree
                walk(item_tree[model], model, item_tree, print_item, '', 0, '', [], False)

    except OSError as e:
        err = f'Error: file {file} could not be opened. Original error: {e}'
    except Exception as e:
        err = f'Unknown error occured while processing. Original error: {e}'
    finally:
        sys.stdout = old_stdout

    if err:
        print(err)
    elif write_output:
        print(f'Created file {file}')


if __name__ == '__main__':

    usage = """
    Usage:
    ----------------------------------------------------------------------------------

    This plugin is meant to be used inside SmartHomeNG.

    Is is generally possible to run this plugin in standalone mode, usually for
    diagnostic purposes - IF the specified device supports this mode. As
    devices are modular extensions, it is not possible to print a list of
    supported devices.

    ===============

    You need to call this plugin with the device id as the first parameter, any
    necessary configuration options either as arg=value pairs or as a python
    dict(this needs to be enclosed in quotes).
    Be aware that later parameters, be they dict or pair type, overwrite earlier
    parameters of the same name.

    ``__init__.py <device> host=www.smarthomeng.de port=80``

    or

    ``__init__.py <device> '{'host': 'www.smarthomeng.de', 'port': 80}'``

    If you call it with -v as a parameter after the device id, you get additional
    debug information:

    ``__init__.py <device> -v``

    ===============

    If you call it with -s as a parameter after the device id, the plugin will
    print a struct.yaml file from the devices' commands.py:

    ``__init__.py <device> -s``

    If you call it with -S as a parameter, the plugin will write the created
    struct yaml to plugins/multidevice/dev_<device>/struct.yaml.
    BEWARE: an existing file will be overwritten.

    ``__init__.py <device> -S``

    An additional argument with a number can change the indent width from
    default 4 (both with -s and -S):

    ``__init__.py <device> -s -2``

    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.CRITICAL)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(message)s  @ %(lineno)d')
    ch.setFormatter(formatter)

    # add the handlers to the logger
    logger.addHandler(ch)

    device = ''
    struct_mode = False
    write_output = False
    acl = False
    indent = 4

    if len(sys.argv) > 1:
        device = sys.argv[1]

    if device and device not in ['-h', '--help', '-?', '/?', '/h', '/help']:

        # check for further command line arguments
        params = {}
        for arg in range(2, len(sys.argv)):

            arg_str = sys.argv[arg]

            if arg_str == '-v':
                print('Debug logging enabled')
                logger.setLevel(logging.DEBUG)

            elif arg_str[:2].lower() == '-s':
                struct_mode = True
                write_output = arg_str[1] == 'S'

            elif arg_str[:2].lower() == '-a':
                acl = True

            elif arg_str[1:].isnumeric():
                try:
                    indent = int(arg_str[1:])
                except ValueError:
                    pass

            else:
                try:
                    # convertible to dict?
                    params.update(literal_eval(arg_str))
                except Exception:
                    # if not: try to parse as 'name=value'
                    match = re.match('([^= \n]+)=([^= \n]+)', arg_str)
                    if match:
                        name, value = match.groups(0)
                        params[name] = value

    else:
        print(usage)
        exit()

    if struct_mode:

        # as we output a formatted syntax, we can not create any output now
        create_struct_yaml(device, indent, write_output, acl)
        exit(0)

    print('This is MultiDevice plugin running in standalone mode')
    print('=====================================================')

    md = MultiDevice(None, standalone_device=device, logger=logger, **params)

    if md._devices:
        dev = md._devices[list(md._devices.keys())[0]]
        print(f'Device loaded: {device} --- ', end='')

        if getattr(dev['device'], 'run_standalone', ''):
            print('running standalone method...')

            dev['device'].run_standalone()
        else:
            print('device doesn\'t have a standalone function.')
    else:
        print(f'Device {device} could not be loaded.')

    print('Done.')
