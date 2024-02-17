import datetime
import time
import os

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf

# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
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
        if mode is not None:
            if 'control/mode' in self.plugin.get_items():
                if mode in self.plugin.MODE_TYPES:
                    self.plugin.get_items()['control/mode'](mode)
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
            data = {}
            data['plugin_status'] = self.plugin.get_status()
            data['plugin_mode'] = self.plugin.get_mode()
            for key, item in self.plugin.get_items().items():
                if item.property.type == 'bool':
                    data[item.property.path + "_value"] = str(item())
                else:
                    data[item.property.path + "_value"] = item()
                data[item.property.path + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data[item.property.path + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            remote_battery_item_dict = dict(self.plugin.get_battery_items(), **self.plugin.get_remote_items())

            for key, items in remote_battery_item_dict.items():
                for item in items:
                    if item.property.type == 'bool':
                        data[item.property.path + "_value"] = str(item())
                    else:
                        data[item.property.path + "_value"] = item()
                    data[item.property.path + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                    data[item.property.path + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            for key, item in self.plugin.get_status_items().items():
                if item.property.type == 'bool':
                    data[item.property.path + "_value"] = str(item())
                else:
                    data[item.property.path + "_value"] = item()
                data[item.property.path + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data[item.property.path + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            for key, item in self.plugin.get_motor_items().items():
                if item.property.type == 'bool':
                    data[item.property.path + "_value"] = str(item())
                else:
                    data[item.property.path + "_value"] = item()
                data[item.property.path + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data[item.property.path + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            for key, item in self.plugin.get_weather_items().items():
                if item.property.type == 'bool':
                    data[item.property.path + "_value"] = str(item())
                else:
                    data[item.property.path + "_value"] = item()
                data[item.property.path + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data[item.property.path + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            return json.dumps(data)
        else:
            return
