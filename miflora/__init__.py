#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 Marc René Frieß                   rene.friess@gmail.com
#########################################################################
#  This file is part of SmartHomeNG.   
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
from miflora.miflora_poller import MiFloraPoller, \
    MI_CONDUCTIVITY, MI_MOISTURE, MI_LIGHT, MI_TEMPERATURE, MI_BATTERY
from btlewrap import available_backends, BluepyBackend, GatttoolBackend, PygattBackend
from lib.model.smartplugin import *

class Miflora(SmartPlugin):
    PLUGIN_VERSION = "1.6.2"

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin.
        """
        self._bt_addr = self.get_parameter_value('bt_addr')
        self._bt_library = self.get_parameter_value('bt_library')
        self._cycle = self.get_parameter_value('cycle')
        self._items = []
        if self._bt_library == 'gatttool':
            self.poller = MiFloraPoller(self._bt_addr, GatttoolBackend)
        elif self._bt_library == 'pygatt':
            self.poller = MiFloraPoller(self._bt_addr, PygattBackend)
        else:
            self.poller = MiFloraPoller(self._bt_addr, BluepyBackend)

        self.init_webinterface()

    def run(self):
        """
        Run method for the plugin
        """        
        self.logger.debug("Plugin '{}': 'run' method called.".format(self.get_fullname()))
        self.scheduler_add(__name__, self._update_loop, prio=7, cycle=self._cycle)
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Plugin '{}': 'stop' method called.".format(self.get_fullname()))
        try:
            self.scheduler_remove(__name__)
        except:
            self.logger.error("Plugin '{}': Removing of scheduler failed: {}.".format(self.get_fullname(), sys.exc_info()))

        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        Selects each item corresponding to its attribute keywords and adds it to an internal array

        :param item: The item to process.
        """
        if self.has_iattr(item.conf, 'miflora_data_type'):
            self.logger.debug("Plugin '{}': Parse item: {}.".format(self.get_fullname(), item))
            self._items.append(item)

    def _update_loop(self):
        try:
            for item in self._items:
                if self.get_iattr_value(item.conf, 'miflora_data_type') == 'temperature':
                    item(self.poller.parameter_value('temperature'))
                elif self.get_iattr_value(item.conf, 'miflora_data_type') == 'light':
                    item(self.poller.parameter_value(MI_LIGHT))
                elif self.get_iattr_value(item.conf, 'miflora_data_type') == 'moisture':
                    item(self.poller.parameter_value(MI_MOISTURE))
                elif self.get_iattr_value(item.conf, 'miflora_data_type') == 'conductivity':
                    item(self.poller.parameter_value(MI_CONDUCTIVITY))
                elif self.get_iattr_value(item.conf, 'miflora_data_type') == 'battery':
                    item(self.poller.parameter_value(MI_BATTERY))
                elif self.get_iattr_value(item.conf, 'miflora_data_type') == 'name':
                    item(self.poller.name())
                elif self.get_iattr_value(item.conf, 'miflora_data_type') == 'firmware':
                    item(self.poller.firmware_version())
        except Exception as e:
            self.logger.error(str(e))

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
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
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
import json
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

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           interface=None, item_count=len(self.plugin.get_items()),
                           plugin_info=self.plugin.get_info(), tabcount=1,
                           tab1title="Items (%s)" % len(self.plugin.get_items()),
                           p=self.plugin)

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
            for item in self.plugin.get_items():
                data[item.property.path + "_value"] = item()
                data[item.property.path + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data[item.property.path + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            # return it as json the the web page
            return json.dumps(data)
        else:
            return