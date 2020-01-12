#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2014 Marcus Popp                         marcus@popp.mx
#  Copyright 2019-2020 Bernd Meiners                Bernd.Meiners@mail.de
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

from lib.module import Modules
from lib.model.smartplugin import *
from lib.item import Items

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
    PLUGIN_VERSION = '1.6.0'

    _flip = {0: '1', False: '1', 1: '0', True: '0', '0': True, '1': False}

    _supported = {
        'value': 'Value',           #Wert wird erwartet
        'string': 'String'}         #String wird erwartet; Rückmeldewert in String oder Bytearray wie bspw b'TS-251'
    
    def __init__(self, sh, *args, **kwargs ):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.
        """

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("init {}".format(__name__))
        self._sh = self.get_sh()

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.cycle = int(self.get_parameter_value('cycle'))
        self.host = self.get_parameter_value('snmp_host')
        self.port = int(self.get_parameter_value('snmp_port'))
        self.communitiy = self.get_parameter_value('snmp_communitiy')

        # Initialization code goes here
        self._items = {}                    # Temperature, etc. populated in parse_item

        """
        self._items will contain something like 
        {'1.3.6.1.4.1.24681.1.2.5.0': {'temp': {'item': Item: netzwerk.qnap_ts251.cpu_temp}}, '1.3.6.1.4.1.24681.1.2.1.0': {'precent': {'item': Item: netzwerk.qnap_ts251.cpu_usage}}, '1.3.6.1.4.1.24681.1.2.6.0': {'temp': {'item': Item: netzwerk.qnap_ts251.system_temp}}}
        """
        # give some info to the user via webinterface
        self.init_webinterface()

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("init {} done".format(__name__))
        self._init_complete = True

    def run(self):
        """
        Run method for the plugin
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Run method called")
        self.alive = True
        self.scheduler_add('update', self._poll_cycle, cycle=self.cycle)
  
    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False
        if self.logger.isEnabledFor(logging.DEBUG):
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
        oid = self.get_iattr_value(item.conf,'snmp_oid')
            
        if not self.has_iattr(item.conf, 'snmp_prop'):
            if self.logger.isEnabledFor(logging.WARNING):
                self.logger.warning("SNMP: No snmp_prop for {0} defined, set to standard".format(item.id()))
                prop = 'std'
        else:
            prop = self.get_iattr_value(item.conf,'snmp_prop')

        prop = prop.lower()
        table = self._items
        
        if prop not in self._supported:  # unknown prop
            if self.logger.isEnabledFor(logging.INFO):
                self.logger.info("Snmp: unknown properties specified for {0}".format(item.id()))
        
        if oid in table:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("set dict[{}][{}] as item:{}".format(oid, prop, item))
            table[oid][prop] = {'item': item}
        else:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("set dict[{}] as prop:{} <item:{}>".format(oid, prop, item))
            table[oid] = {prop: {'item': item}}
            
        self.logger.debug(self._items)

    # Query data
    def _poll_cycle(self):
        """
        This method gets called by scheduler and queries all oids defined in items
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("SNMP: query cycle called")

        for oid in self._items:
            if not self.alive:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("SNMP: Self not alive".format(oid))
                break
            for prop in self._items[oid]:
                item = self._items[oid][prop]['item']
                
                host = self.host
                community = self.communitiy
                oid = oid
                prop = prop
                self.logger.debug('Poll for item: {} with property: {} using oid: {}, host: {}, community: {} '.format(item, prop, oid, host, community))
                
                # Request data
                response = get(host, community, oid)
                self.logger.debug('Successfully received response: {}'.format(response))
                
                # Transform response
                result = 0
                unit = 0
                
                if prop == 'value':
                    response = response.decode('ascii')
                    code_pos = response.index(" ")
                    unit_short = (response[(code_pos+1):(code_pos +2)]).lower()
                    value = float(response[:(code_pos)])
                    if unit_short is 'c':
                        result = int(value)
                        unit = unit_short.upper()
                    elif unit_short is '%':
                        result = round(value /100, 3)
                        unit = response[(code_pos+1):len(response)]
                    elif unit_short == 'm' or unit_short == 'g' or unit_short == 't':
                        result = round(value, 3)
                        unit = response[(code_pos+1):len(response)]
                    elif unit_short == 'r':
                        result >= int(value)
                        unit = response[(code_pos+1):len(response)]
                    else:
                        self.logger.debug('Responsevaluetype nicht erkannt')
                elif prop == 'string':
                    try:
                        result = response.decode('ascii')
                    except:
                        result = str(response)
                        self.logger.debug('Response war string')
                    else:
                        self.logger.debug('Response war bytearray')
                    unit = 'no'
                else:
                    self.logger.debug('Responsetype nicht definiert')

                self.logger.debug('Response successfully transformed to: {} with unit: {} '.format(result, unit))
                #Set item value
                item(result, 'SNMP')

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != self.get_shortname():
            try:
                # code to execute, only if the item has not been changed by this plugin:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("Update item: {}, item has been changed outside this plugin".format(item.id()))
            except Exception as e:
                if self.logger.isEnabledFor(logging.WARNING):
                    self.logger.warning("SNMP: problem setting output {0}: {1}".format(item._ow_path['path'], e))
                    
    def get_items(self):
        return self._items

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