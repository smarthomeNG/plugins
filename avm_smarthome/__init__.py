#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
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

from lib.module import Modules
from lib.model.smartplugin import *
from lib.item import Items

from pyfritzhome import Fritzhome, LoginError

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class AVM_smarthome(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.0.A'    # (must match the version specified in plugin.yaml)

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

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self._cycle = self.get_parameter_value('cycle')                    # the frequency in seconds how often the query shoud be done
        self.host = self.get_parameter_value('host')                       # IP Adress of the fritzbox
        self.user = self.get_parameter_value('username')                   # Username
        self.password = self.get_parameter_value('password')               # Password
        
        # Initialization code goes here
        self.fritzbox = None
        self.alive = False
        self._ain_items = []                                               # Liste aller Items, die die AIN als Datentyp haben
        self._device_dict = {}                                             # Dict, in das die Daten der AVM Abfrage geschrieben werden
        self.avm_smarthome_items = []                                      # to hold items for web interface
        self.avm_smarthome_devices = {}                                    # to hold device information for web interface
        self.avm_smarthome_meta = {}                                       # to hold meta information for web interface

        # On initialization error use:
        #   self._init_complete = False
        #   return

        # if plugin should start even without web interface
        self.init_webinterface()
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False
        
        self.connect()
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)
        self.alive = True
        
        # discover all connected AVM smarthome devices
        self.poll_device

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.disconnect()
        self.alive = False
        
    def connect(self):
        """
        Connects to the AVM Fritzbox
        """
        try:
            self.fritzbox = Fritzhome(host=self.host, user=self.user, password=self.password)
            self.fritzbox.login()
            self.logger.debug('Login to Fritz!Box {} as {} successful.'.format(self.host, self.user))
        except LoginError:
            self.logger.debug('Login to Fritz!Box {} as {} failed.'.format(self.host, self.user))
            
    def disconnect(self):
        """
        Disconnects from the AVM Fritzbox
        """
        if self.fritzbox is not None:
            self.fritzbox.logout()
            self.logger.debug('Logout successful')

    def reconnect(self):
        """
        Reconnects to the call monitor of the AVM device
        """
        self.disconnect()
        self.connect()

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
        
        if self.has_iattr(item.conf, 'avm_smarthome_data') or self.has_iattr(item.conf, 'avm_ain'):
            self.logger.debug(f"parsing item: {item.id()}")
                
            datatype = self.get_iattr_value(item.conf, 'avm_smarthome_data')
            ain = self.get_iattr_value(item.conf, 'avm_ain')
            
            if ain is not None:
                self.logger.debug(f" Item {item.id()} with avm_ain attribut found; append to list")
                self._ain_items.append(item)
            else:
                parent_item = item.return_parent()
                ain = self.get_iattr_value(parent_item.conf, 'avm_ain')
                
            if datatype is not None:
                self.logger.debug(f" Item {item.id()} with avm_smarthome_data attribut found; append to list")
                self.avm_smarthome_items.append(item)
                
            if not self.avm_smarthome_devices.get(ain):
                self.avm_smarthome_devices[ain] = {}
                self.avm_smarthome_devices[ain]['connected_to_item'] = False
                # self.avm_smarthome_devices[ain]['connected_items'] = {}
                self.avm_smarthome_devices[ain]['switch'] = {}
                self.avm_smarthome_devices[ain]['temperature_sensor'] = {}
                self.avm_smarthome_devices[ain]['thermostat'] = {}
                self.avm_smarthome_devices[ain]['alarm'] = {}
            
            self.logger.debug(f"Item parsed connected with AIN: {ain} and datatype: {datatype}")
            self.avm_smarthome_devices[ain]['connected_to_item'] = True
            # if datatype is not None:
                # self.avm_smarthome_devices[ain]['connected_items']['item_'+datatype] = item
                
            # self.logger.debug(f"--parse_item-- avm_smarthome_devices: {self.avm_smarthome_devices}")
            # self.logger.debug(f"--parse_item-- _ain_items: {self._ain_items}")

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
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))
            
            if self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'set_temperature':
                self.logger.debug("update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item, caller, source, dest))
                cmd_temperature = float(item())
                self.logger.debug("cmd_temp is: {0}".format(cmd_temperature))
                parentItem = item.return_parent()
                ainDevice = '0'
                if isinstance(parentItem.conf['avm_ain'], str):
                    ainDevice = parentItem.conf['avm_ain']
                else:
                    self.logger.error('device ain is not a string value')
                self.logger.info("Target ain is {0}".format(ainDevice))
                self.fritzbox.set_target_temperature(ainDevice, cmd_temperature)
                
            if self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'set_switch_state':
                self.logger.debug("update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item, caller, source, dest))
                state = bool(item())
                parentItem = item.return_parent()
                ainDevice = '0'
                if isinstance(parentItem.conf['avm_ain'], str):
                    ainDevice = parentItem.conf['avm_ain']
                else:
                    self.logger.error('device ain is not a string value')
                self.logger.info("Target ain is {0}".format(ainDevice))
                if state is True:
                    self.fritzbox.set_switch_state_on(ainDevice)
                else:
                    self.fritzbox.set_switch_state_off(ainDevice)
                    
            if self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'set_switch_state_toggle':
                self.logger.debug("update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item, caller, source, dest))
                state = bool(item())
                parentItem = item.return_parent()
                ainDevice = '0'
                if isinstance(parentItem.conf['avm_ain'], str):
                    ainDevice = parentItem.conf['avm_ain']
                else:
                    self.logger.error('device ain is not a string value')
                self.logger.info("Target ain is {0}".format(ainDevice))
                self.fritzbox.set_switch_state_toggle(ainDevice)

            pass

    def poll_device(self):
        """
        This method gets called by scheduler and queries all data
        """
        self.logger.debug('Starting update loop for instance {}.'.format(self.get_instance_name()))
        
        # Request AVM Data
        self._device_dict = self.fritzbox.get_devices_as_dict()
        
        # Update WebIF Dict
        for ain in self._device_dict:
            if not self.avm_smarthome_devices.get(ain):
                self.avm_smarthome_devices[ain] = {}
                self.avm_smarthome_devices[ain]['connected_to_item'] = False
                # self.avm_smarthome_devices[ain]['connected_items'] = {}
                self.avm_smarthome_devices[ain]['switch'] = {}
                self.avm_smarthome_devices[ain]['temperature_sensor'] = {}
                self.avm_smarthome_devices[ain]['thermostat'] = {}
                self.avm_smarthome_devices[ain]['alarm'] = {}
                
            self.avm_smarthome_devices[ain]['online'] = bool(self._device_dict[ain].present)
            self.avm_smarthome_devices[ain]['name'] = self._device_dict[ain].name
            self.avm_smarthome_devices[ain]['productname'] = self._device_dict[ain].productname
            self.avm_smarthome_devices[ain]['manufacturer'] = self._device_dict[ain].manufacturer
            self.avm_smarthome_devices[ain]['fw_version'] = self._device_dict[ain].fw_version
            self.avm_smarthome_devices[ain]['lock'] = bool(self._device_dict[ain].lock)
            self.avm_smarthome_devices[ain]['device_lock'] = bool(self._device_dict[ain].device_lock)
            self.avm_smarthome_devices[ain]['has_switch'] = bool(self._device_dict[ain].has_switch)
            self.avm_smarthome_devices[ain]['has_temperature_sensor'] = bool(self._device_dict[ain].has_temperature_sensor)
            self.avm_smarthome_devices[ain]['has_thermostat'] = bool(self._device_dict[ain].has_thermostat)
            self.avm_smarthome_devices[ain]['has_alarm'] = bool(self._device_dict[ain].has_alarm)
            
            if self._device_dict[ain].has_thermostat:
                self.avm_smarthome_devices[ain]['thermostat']['actual_temperature'] = self._device_dict[ain].actual_temperature
                self.avm_smarthome_devices[ain]['thermostat']['target_temperature'] = self._device_dict[ain].target_temperature
                self.avm_smarthome_devices[ain]['thermostat']['comfort_temperature'] = self._device_dict[ain].comfort_temperature
                self.avm_smarthome_devices[ain]['thermostat']['eco_temperature'] = self._device_dict[ain].eco_temperature
                self.avm_smarthome_devices[ain]['thermostat']['battery_low'] = bool(self._device_dict[ain].battery_low)
                self.avm_smarthome_devices[ain]['thermostat']['battery_level'] = self._device_dict[ain].battery_level
                self.avm_smarthome_devices[ain]['thermostat']['window_open'] = bool(self._device_dict[ain].window_open)
                self.avm_smarthome_devices[ain]['thermostat']['summer_active'] = bool(self._device_dict[ain].summer_active)
                self.avm_smarthome_devices[ain]['thermostat']['holiday_active'] = bool(self._device_dict[ain].holiday_active)
                
            if self._device_dict[ain].has_switch:  
                self.avm_smarthome_devices[ain]['switch']['switch_state'] = bool(self._device_dict[ain].switch_state)
                self.avm_smarthome_devices[ain]['switch']['power'] = self._device_dict[ain].power
                self.avm_smarthome_devices[ain]['switch']['energy'] = self._device_dict[ain].energy
                self.avm_smarthome_devices[ain]['switch']['voltage'] = self._device_dict[ain].voltage
                
            if self._device_dict[ain].has_temperature_sensor:  
                self.avm_smarthome_devices[ain]['temperature_sensor']['temperature'] = self._device_dict[ain].temperature
                self.avm_smarthome_devices[ain]['temperature_sensor']['offset'] = self._device_dict[ain].offset
                
            if self._device_dict[ain].has_alarm:  
                self.avm_smarthome_devices[ain]['alarm']['alert_state'] = bool(self._device_dict[ain].alert_state)

        self.logger.debug(f"Discovered avm smarthome devices and data: {self.avm_smarthome_devices}")
        
        # update tasmota_meta auf Basis von tasmota_devices
        self.avm_smarthome_meta = {}
        for ain in self.avm_smarthome_devices:
            if self.avm_smarthome_devices[ain]['has_switch']:
                self.avm_smarthome_meta['switch'] = True
            if self.avm_smarthome_devices[ain]['has_thermostat']:
                self.avm_smarthome_meta['thermostat'] = True
            if self.avm_smarthome_devices[ain]['has_temperature_sensor']:
                self.avm_smarthome_meta['temperature_sensor'] = True
            if self.avm_smarthome_devices[ain]['has_alarm']:
                self.avm_smarthome_meta['alarm'] = True
        
        # update items
        for item in self._ain_items:
            if self.has_iattr(item.conf, 'avm_ain'):
                item_ain = self.get_iattr_value(item.conf, 'avm_ain')
                self.logger.debug(f" Item {item.id()} with defined avm_ain attribut {item_ain}")

                device = self._device_dict[item_ain]
                
                if self.has_iattr(item.conf, 'avm_smarthome_data'):
                    self._set_item_value(item, device)
                else:
                    self.logger.debug(f" No attribut 'avm_smarthome_data' found on item {item.id()}; checking child items")
                    for child in item.return_children():
                        self.logger.debug(f" Child item {child.id()} processed and checked for attribut 'avm_smarthome_data' ")
                        if self.has_iattr(child.conf, 'avm_smarthome_data'):
                            self._set_item_value(child, device)
        pass

        
    def _set_item_value(self, item, device):
        if self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'name':
            item(device.name, self.get_shortname())
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'ain':
            item(device.ain, self.get_shortname())
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'identifier':
            item(device.identifier, self.get_shortname())
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'productname':
            item(device.productname, self.get_shortname())
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'manufacturer':
            item(device.manufacturer, self.get_shortname())
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'firmware_version':
            item(device.fw_version, self.get_shortname())   
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'present':
            item(device.present, self.get_shortname())
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'lock':
            item(device.lock, self.get_shortname())
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'device_lock':
            item(device.device_lock, self.get_shortname())
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'has_switch':
            item(device.has_switch, self.get_shortname())
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'has_temperature_sensor':
            item(device.has_temperature_sensor, self.get_shortname())
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'has_thermostat':
            item(device.has_thermostat, self.get_shortname())
        elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'has_alarm':
            item(device.has_alarm, self.get_shortname())
            
        if device.has_switch:
            if self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'switch_state':
                item(device.switch_state, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'power':
                item(device.power, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'energy':
                item(device.energy, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'voltage':
                item(device.voltage, self.get_shortname())
                
        if device.has_temperature_sensor:
            if self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'temperature':
                item(device.temperature, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'offset':
                item(device.offset, self.get_shortname())
                
        if device.has_thermostat:
            if self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'actual_temperature':
                item(device.actual_temperature, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'target_temperature':
                item(device.target_temperature, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'comfort_temperature':
                item(device.comfort_temperature, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'eco_temperature':
                item(device.eco_temperature, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'battery_low':
                item(device.battery_low, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'battery_level':
                item(device.battery_level, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'window_open':
                item(device.window_open, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'summer_active':
                item(device.summer_active, self.get_shortname())
            elif self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'holiday_active':
                item(device.holiday_active, self.get_shortname())
                
        if device.has_alarm:
            if self.get_iattr_value(item.conf, 'avm_smarthome_data') == 'alert_state':
                item(device.alert_state, self.get_shortname())
    

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Not initializing the web interface")
            return False

        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface")
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
from jinja2 import Environment, FileSystemLoader


class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()

        self.items = Items.get_instance()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])))


    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            # get the new data
            data = {}

            # data['item'] = {}
            # for i in self.plugin.items:
            #     data['item'][i]['value'] = self.plugin.getitemvalue(i)
            #
            # return it as json the the web page
            # try:
            #     return json.dumps(data)
            # except Exception as e:
            #     self.logger.error("get_data_html exception: {}".format(e))
        return {}

