import datetime
import time
import os
import logging

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf

# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
import json
from jinja2 import Environment, FileSystemLoader
class NukiWebServiceInterface:
    exposed = True

    def __init__(self, webif_dir, plugin):
        self.webif_dir = webif_dir
        self.logger = logging.getLogger(__name__)
        self.plugin = plugin

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def index(self):
        try:
            input_json = cherrypy.request.json
            self.plugin.logger.debug(
                "Plugin '{}' - NukiWebServiceInterface: Getting JSON String".format(self.plugin.get_shortname()))
            nuki_id = input_json['nukiId']
            state_name = input_json['stateName']
            self.plugin.logger.debug(
                "Plugin '{pluginname}' - NukiWebServiceInterface: Status Smartlock: ID: {nuki_id} Status: {state_name}".
                format(pluginname=self.plugin.get_shortname(), nuki_id=nuki_id, state_name=state_name))
            self.plugin.update_lock_state(nuki_id, input_json)
        except Exception as err:
            self.plugin.logger.error(
                "Plugin '{}' - NukiWebServiceInterface: Error parsing nuki response!\nError: {}".format(
                    self.plugin.get_shortname(), err))
        pass

class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()
        self.logger = plugin.logger
        self.items = Items.get_instance()

    @cherrypy.expose
    def index(self, reload=None, mode=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])))

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           interface=None,
                           item_count=len(self.plugin.get_event_items()) + len(self.plugin.get_door_items()) +
                                      len(self.plugin.get_action_items()) + len(self.plugin.get_battery_items()),
                           plugin_info=self.plugin.get_info(), paired_nukis=self.plugin.get_paired_nukis(), tabcount=1,
                           p=self.plugin)

    @cherrypy.expose
    def triggerAction(self, path, value):
        if path is None:
            self.plugin.logger.error(
                "Plugin '{}': Path parameter is missing when setting action item value!".format(self.get_shortname()))
            return
        if value is None:
            self.plugin.logger.error(
                "Plugin '{}': Value parameter is missing when setting action item value!".format(self.get_shortname()))
            return
        item = self.plugin.items.return_item(path)
        item(int(value), caller=self.plugin.get_shortname(), source='triggerAction()')
        return

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
            for item, value in self.plugin.get_event_items().items():
                data[item.property.path + "_value"] = item()
                data[item.property.path + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data[item.property.path + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')
            for item, value in self.plugin.get_door_items().items():
                data[item.property.path + "_value"] = item()
                data[item.property.path + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data[item.property.path + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')
            for item, value in self.plugin.get_action_items().items():
                data[item.property.path + "_value"] = item()
                data[item.property.path + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data[item.property.path + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')
            for item, value in self.plugin.get_battery_items().items():
                data[item.property.path + "_value"] = item()
                data[item.property.path + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data[item.property.path + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')
            # return it as json the the web page
            return json.dumps(data)
        else:
            return