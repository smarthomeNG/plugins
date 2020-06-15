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
            data = {}
            for key, item in self.plugin.get_items().items():
                if item.property.type == 'bool':
                    data[item.id() + "_value"] = str(item())
                else:
                    data[item.id() + "_value"] = item()
                data[item.id() + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data[item.id() + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')
            for key, items in self.plugin.get_battery_items().items():
                for item in items:
                    data[item.id() + "_value"] = item()
                    data[item.id() + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                    data[item.id() + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')
            return json.dumps(data)
        else:
            return
