#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.8 and
#  upwards.
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

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface

from routeros_api import RouterOsApiPool
from routeros_api import exceptions

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class MikrotikPlugin(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = '1.0.0'

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._items = []
        self._interfaces = []
        self._identity = ''
        self._osversion = ''

        self._cycle = self.get_parameter_value('cycle')
        self._device = {
            'host': self.get_parameter_value('hostname'),
            'port': self.get_parameter_value('port'),
            'username': self.get_parameter_value('username'),
            'password': self.get_parameter_value('password'),
            'plaintext_login': True,
            'use_ssl': True,
            'ssl_verify': False,
            'ssl_verify_hostname': False
        }

        try:
            self._api_pool = RouterOsApiPool(**self._device)
            self._api = self._api_pool.get_api()

        except exceptions.RouterOsApiConnectionError:
            self.logger.error('Failed to connect to MikroTik device')
            self._init_complete = False
            return

        except exceptions.RouterOsApiError as e:
            self.logger.error(f'RouterOS API error: {e}')
            self._init_complete = False
            return

        self.init_webinterface(WebInterface)
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")

        try:
            # Get the device model and serial number
            deviceinfo = self._api.get_resource('/system/routerboard').get()[0]
            self._model = deviceinfo['model']
            self._serial = deviceinfo['serial-number']

        except exceptions.RouterOsApiConnectionError:
            self.logger.error('Failed to connect to MikroTik device')
            self._init_complete = False
            return

        except exceptions.RouterOsApiError as e:
            self.logger.error(f'RouterOS API error: {e}')
            self._init_complete = False
            return

        self.scheduler_add('poll_routeros', self.poll_device, cycle=self._cycle)
        self.alive = True
        # Do an initial poll without having to wait for the first scheduler cycle
        self.poll_device

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_routeros')
        #self._api.put()
        self._api_pool.disconnect()
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """

        if self.has_iattr(item.conf, 'mikrotik_parameter'):
            self.logger.debug(f"parse item: {item} with conf {item.conf}")
            function = self.get_iattr_value(item.conf, 'mikrotik_parameter')
            if not self.has_iattr(item.conf, 'mikrotik_port'):
                self.logger.warning(F'Item requested function {function}, but no port specified')
            else:
                port = self.get_iattr_value(item.conf, 'mikrotik_port')
                self.logger.debug(f"Item: {item} is parameter {function} of port {port}")
                self._items.append(item)
                return self.update_item

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.debug(f"update_item was called with item {item.property.path} from caller {caller}, source {source} and dest {dest}")

            port = self.get_iattr_value(item.conf, 'mikrotik_port')
            function = self.get_iattr_value(item.conf, 'mikrotik_parameter')

            if function == 'enabled':
                self.set_port_enabled(port, 'true' if item() == True else 'false')

            if function == 'poe':
                self.set_port_poe(port, 'true' if item() == True else 'false')

    def update_items(self):
        """
        Update items after polling

        This method is called after having successfully polled a device.
        It updates the configured items with the result of the device poll.
        """
        # Itter though configured items
        for item in self._items:
            port = self.get_iattr_value(item.conf, 'mikrotik_port')
            function = self.get_iattr_value(item.conf, 'mikrotik_parameter')
            # Try to find port in interfaces list
            interface = next((sub for sub in self._interfaces if sub['name'] == port), None)
            # If found update the item with the respective switch port property
            if interface:
                if function == 'active':
                    item(True if interface['running'] == 'true' else False, self.get_shortname())
                elif function == 'enabled':
                    item(True if interface['disabled'] == 'false' else False, self.get_shortname())
                elif function == 'poe':
                    item(True if interface['poe'] == 'auto-on' else False, self.get_shortname())
                #     # if the plugin is a gateway plugin which may receive updates from several external sources,
                #     # the source should be included when updating the the value:
                #     item(device_value, self.get_shortname(), source=device_source_id)

    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
    
        try:
            # Retrieve ethernet interface list
            ethernet_ports = self._api.get_resource(
                '/interface/ethernet').get()

            # Retrieve bridge port information for all interfaces
            bridge_ports = self._api.get_resource(
                '/interface/bridge/port').get()

            # Retrieve identity and RouterOS version
            self._identity = self._api.get_resource(
                '/system/identity').get()[0]['name']
            self._osversion = self._api.get_binary_resource(
                '/system/package').get()[0]['version'].decode()

        except exceptions.RouterOsApiConnectionError:
            self.logger.error(F"Failed to connect to MikroTik device {self._device['host']}")
            return

        except exceptions.RouterOsApiError as e:
            self.logger.error(f'RouterOS API error: {e}')
            return

        # Create a dictionary of bridge ports for faster lookups
        bridge_port_dict = {port['interface']: port for port in bridge_ports}

        # Parse output into a list of dictionaries
        interfaces = []
        for interface in ethernet_ports:
            # Get PVID for the ethernet interface from bridge port buffer
            bridge_port = bridge_port_dict.get(interface['name'])
            pvid = bridge_port['pvid'] if bridge_port else '-'
            if (interface['name'] == 'ether18'):
                {self.logger.debug(interface)}
            if (interface['id'][0] == '*'):
                interface['id'] = interface['id'][1:]
                interface['id'] = int(interface['id'], 16)
            self.logger.debug(interface)
            speed = '?'
            if 'speed' in interface:
                speed = interface['speed']
            interfaces.append({
                'id': interface['id'],
                'defaultname': interface['default-name'],
                'name': interface['name'],
                'running': interface['running'],
                'speed': speed,
                'disabled': interface['disabled'],
                'pvid': pvid,
                'poe': interface.get('poe-out', '-'),
                'comment': interface.get('comment', '')
            })
        self._interfaces = interfaces
        self.logger.debug(F"Polled {self._device['host']}, found {len(interfaces)} ports")
        self.update_items()

    def str2bool(self, v):
        return str(v).lower() in ("yes", "true", "on", "1")

    def get_port_status(self, port):
        active = False
        interface = next((sub for sub in self._interfaces if sub['name'] == port), None)
        if (interface):
            active = True if interface['running'] == 'true' else False
        else:
            self.logger.warning(F'Requested state of unknown interface {port}')
            return None
        return active

    def get_port_enabled(self, port):
        active = False
        interface = next((sub for sub in self._interfaces if sub['name'] == port), None)
        if (interface):
            active = False if interface['disabled'] == 'true' else True
        else:
            self.logger.warning(F'Requested enabled state of unknown interface {port}')
            return None
        return active

    def get_port_poe(self, port):
        active = False
        interface = next((sub for sub in self._interfaces if sub['name'] == port), None)
        if (interface):
            active = True if interface['poe'] == 'auto-on' else False
        else:
            self.logger.warning(F'Requested POE state of unknown interface {port}')
            return None
        return active

    def set_port_enabled(self, port, status):
        """
        Enables or disables a switch port

        This method is called when a switch port active status should be changed.

        :param port: switch port to be updated
        :param status: 'false' disables the port, 'true' enables it. Parameter must be a string.
        """
        self.logger.debug(F"Setting active state of port {port} to {self.str2bool(status)}")

        # send the command to the device
        try:
            if (self.str2bool(status) == False):
                self._api.get_binary_resource('/interface').call('disable', {'.id': port.encode()})
            else:
                self._api.get_binary_resource('/interface').call('enable', {'.id': port.encode()})
            interface = next((sub for sub in self._interfaces if sub['name'] == port), None)
            if (interface):
                interface['disabled'] = 'true' if self.str2bool(status) == False else 'false'
        except exceptions.RouterOsApiConnectionError:
            self.logger.error('Failed to connect to MikroTik device')
            return "NOK"

        except exceptions.RouterOsApiError as e:
            self.logger.error(f'RouterOS API error: {e}')
            return "NOK"

        return "OK"

    def set_port_poe(self, port, status):
        """
        Enables or disables POE power of a switch port

        This method is called when a switch port POE status should be changed.

        :param port: switch port to be updated
        :param status: 'false' disabled POE of the port, 'true' enables it. Parameter must be a string.
        """       
        self.logger.debug(F"Setting POE state of port {port} to {self.str2bool(status)}")

        # send the command to the device
        try:
            if self.str2bool(status) == True:
                self._api.get_binary_resource('/interface/ethernet').call('set', {'.id': port.encode(), 'poe-out': b'auto-on'})
            else:
                self._api.get_binary_resource('/interface/ethernet').call('set', {'.id': port.encode(), 'poe-out': b'off'})
            interface = next((sub for sub in self._interfaces if sub['name'] == port), None)
            if (interface):
                interface['poe'] = 'auto-on' if (self.str2bool(status) == True) else 'off'
        except exceptions.RouterOsApiConnectionError:
            self.logger.error('Failed to connect to MikroTik device')
            return "NOK"

        except exceptions.RouterOsApiError as e:
            self.logger.error(f'RouterOS API error: {e}')
            return "NOK"

        return "OK"
