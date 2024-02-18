#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019-2020 Michael Wenzel               wenzel_michael@web.de
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

from lib.item import Items
from lib.model.smartplugin import SmartPlugin, SmartPluginWebIf, Modules

from bin.smarthome import VERSION

import threading
import logging
import time
import struct
from puresnmp import get

class Snmp(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = '1.6.1'

    _flip = {0: '1', False: '1', 1: '0', True: '0', '0': True, '1': False}

    _supported = {
        'value': 'Value',                    # Wert wird erwartet
        'string': 'String',                  # String wird erwartet; Rückmeldewert in String oder Bytearray wie bspw b'TS-251'
        'hex-string': 'hex-string',          # Text-String, der in Hex-übergeben wird
        'mac-adress': 'mac-adress',          # MAC-Adresse
        'ip-adress': 'ip-adress',            # IP-Adresse
        'error-state': 'error-state'         # Error-State bestehend aus 2 Byte; Darstellung als 16bit Array, wobei das Bit auf 1 den Fehler angibt
        }

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.
        """

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.logger.debug("init {}".format(__name__))

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.instance = self.get_parameter_value('instance')         # the instance of the plugin for questioning multiple smartmeter
        self.cycle = self.get_parameter_value('cycle')               # the frequency in seconds how often the query shoud be done
        self.host = self.get_parameter_value('snmp_host')            # IP Adress of the network device to be queried
        self.port = self.get_parameter_value('snmp_port')            # Port for SNMP queries
        self.community = self.get_parameter_value('snmp_community')  # SNMP Community

        # Initialization code goes here
        self._items = {}
        """
        self._items will contain something like
        {'1.3.6.1.4.1.24681.1.2.5.0': {'temp': {'item': Item: netzwerk.qnap_ts251.cpu_temp}}, '1.3.6.1.4.1.24681.1.2.1.0': {'precent': {'item': Item: netzwerk.qnap_ts251.cpu_usage}}, '1.3.6.1.4.1.24681.1.2.6.0': {'temp': {'item': Item: netzwerk.qnap_ts251.system_temp}}}
        """

        # log
        self.logger.debug("Instance {} of SNMP configured to use host '{}' with update cycle of {} seconds and Community {}".format(self.instance if self.instance else 0, self.host, self.cycle, self.community))

        # Init web interface
        self.init_webinterface()

        # init_complete to True
        self._init_complete = True

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True
        self.scheduler_add('update', self._poll_cycle, cycle=self.cycle)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False
        self.logger.debug("Stop method called")
        self.scheduler_remove('update')

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute propwords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        """
        if not self.has_iattr(item.conf, 'snmp_oid'):
            return
        oid = self.get_iattr_value(item.conf, 'snmp_oid')

        if not self.has_iattr(item.conf, 'snmp_prop'):
            self.logger.warning("SNMP: No snmp_prop for {0} defined, set to standard".format(item.property.path))
            prop = 'std'
        else:
            prop = self.get_iattr_value(item.conf, 'snmp_prop').lower()

        if prop not in self._supported:
            self.logger.info("Unknown properties specified for {0}".format(item.property.path))

        if oid in self._items:
            self.logger.debug("Set dict[{}][{}] as item:{}".format(oid, prop, item))
            self._items[oid][prop] = {'item': item}
        else:
            self.logger.debug("Set dict[{}] as prop:{} <item:{}>".format(oid, prop, item))
            self._items[oid] = {prop: {'item': item}}

        self.logger.debug(self._items)

    # Query data
    def _poll_cycle(self):
        """
        This method gets called by scheduler and queries all oids defined in items
        """
        self.logger.debug("Query cycle called")

        for oid in self._items:
            if not self.alive:
                self.logger.debug("Self not alive".format(oid))
                break
            for prop in self._items[oid]:
                item = self._items[oid][prop]['item']

                host = self.host
                community = self.community
                oid = oid
                prop = prop
                self.logger.debug('Poll for item: {} with property: {} using oid: {}, host: {}, community: {} '.format(item, prop, oid, host, community))

                # Request data
                try:
                    response = get(host, community, oid)
                    self.logger.debug('Successfully received response: {}'.format(response))
                except Exception as e:
                    self.logger.error('Exception occured when getting data of OID {}: {}'.format(oid, e))
                    return

                # Transform response
                result = 0
                unit = 0

                if prop == 'value':
                    try:
                        response = response.decode('ascii')
                    except Exception as e:
                        response = response
                        self.logger.debug('Response for OID {} not decoded, since it was no ASCII string. Result is: {}. Error was: {}'.format(oid, result, e))  
                    
                    # Prüfung, ob Leerzeichen vorhanden sind, um den Wert von Einheit zu trennen
                    try:
                        code_pos = response.index(" ")
                    except:
                        if isinstance(response, int) is True:
                            result = int(response)
                        else:
                            result = float(response)
                        self.logger.debug('Response did not contain units; therefore using standard conversion to float or int is used')
                    else:
                        unit_short = (response[(code_pos+1):(code_pos +2)]).lower()
                        value = float(response[:(code_pos)])

                        if unit_short == 'c':
                            result = int(value)
                            unit = unit_short.upper()
                        elif unit_short == '%':
                            result = round(value /100, 3)
                            unit = response[(code_pos+1):len(response)]
                        elif unit_short == 'm' or unit_short == 'g' or unit_short == 't':
                            result = round(value, 3)
                            unit = response[(code_pos+1):len(response)]
                        elif unit_short == 'r':
                            result = int(value)
                            unit = response[(code_pos+1):len(response)]
                        else:
                            result = round(value, 2)
                            self.logger.debug('Response value type not defined; using standard conversion to float')
                
                elif prop == 'string':
                    try:
                        result = str(response.decode('ascii'))
                        unit = 'no'
                    except Exception as e:
                        result = str(response)
                        self.logger.debug('Response for OID {} not decoded, since it was no ASCII string. Result is: {}. Error was: {}'.format(oid, result, e))
                    else:
                        self.logger.debug('String response decoded to: {}'.format(result))

                elif prop == 'hex-string':
                    try:
                        result = bytes.fromhex(response).decode("utf-8")
                        unit = 'no'
                    except Exception as e:
                        result = response
                        self.logger.debug('Response for OID {} not decoded from hex-string to string. Result is: {}. Error was: {}'.format(oid, result, e))
                    else:
                        self.logger.debug('hex-string decoded to: {}'.format(result))
                        
                elif prop == 'mac-adress':
                    try:
                        # result = response.hex(":")   # Pyhton 3.8 required
                        result = ':'.join(f'{x:02x}' for x in response)
                        unit = 'no'
                    except Exception as e:
                        result = response
                        self.logger.debug('Response for OID {} not decoded to mac-adress. Result is: {}. Error was: {}'.format(oid, result, e))
                    else:
                        self.logger.debug('mac-adress decoded as: {}'.format(result))
                
                elif prop == 'ip-adress':
                    try:
                        result = '.'.join(str(cc) for cc in response)
                        unit = 'no'
                    except Exception as e:
                        result = response
                        self.logger.debug('Response for OID {} not decoded to mac-adress. Result is: {}. Error was: {}'.format(oid, result, e))   
                    else: 
                        self.logger.debug('ip-adress decoded as: {}'.format(result))
                        
                    #if validate_ip(response) is True:
                    #    result = str(response)
                    #    self.logger.debug('ip-adress checked to: {}'.format(result))
                    #else:
                    #    self.logger.debug('Response for OID {} does not contain ip-adress'.format(oid))
                
                elif prop == 'error-state':
                    try:
                        binary = ''
                        for byte in response:
                            binary += "{0:08b}".format(byte)
                        self.logger.debug('error-state decoded to binary: {}'.format(binary)) 
                        if binary.find("1") is True:
                            result = binary.find("1")
                        else:
                          result = '-'
                        unit = 'no'                        
                    except Exception as e:
                        result = response
                        self.logger.debug('Response for OID {} not decoded to error-state.  Result is: {}. Error was: {}'.format(oid, result, e))
                    else:
                        self.logger.debug('error-state decoded to error-code: {}'.format(result))

                else:
                    self.logger.debug('Item property not defined in item.conf')

                # Set item value
                self.logger.debug('Response successfully transformed to: {} with unit: {} '.format(result, unit))
                item(result, 'SNMP')

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != self.get_shortname():
            try:
                # code to execute, only if the item has not been changed by this plugin:
                self.logger.debug("Update item: {}, item has been changed outside this plugin".format(item.property.path))
            except Exception as e:
                self.logger.warning("Problem setting output {0}: {1}".format(item._ow_path['path'], e))

    def get_items(self):
        return self._items
        
    def validate_ip(s):
        a = s.split('.')
        if len(a) != 4:
            return False
        for x in a:
            if not x.isdigit():
                return False
            i = int(x)
            if i < 0 or i > 255:
                return False
        return True
 
#
# webinterface
#

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
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(p=self.plugin)

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
