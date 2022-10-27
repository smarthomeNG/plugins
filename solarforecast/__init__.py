#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022 Alexander Schwithal 
#########################################################################
#  This file is part of SmartHomeNG.   
#
#  Solarforecast plugin
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

from lib.model.smartplugin import *
from lib.item import Items
import requests
import json
import datetime


class Solarforecast(SmartPlugin):
    PLUGIN_VERSION = '1.9.0'

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin.

        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._sh = sh
        self._cycle = 7200
        self.session = requests.Session()
        
        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.latitude  = self.get_parameter_value('latitude')
        self.longitude = self.get_parameter_value('longitude')
        self.declination = self.get_parameter_value('declination')
        self.azimuth = self.get_parameter_value('azimuth')
        self.kwp = self.get_parameter_value('kwp')
        self.service = self.get_parameter_value('service')

        if self.latitude is None or \
                self.longitude is None or \
                self.declination is None or \
                self.azimuth is None or \
                self.kwp is None:
            self.logger.error("Plugin needs valid latitude, longitude, declination, azimuth and kwp values")

        if self.service != 'solarforecast':
            self.logger.error(f"Service {self.service} is not supported yet.")
        
        self.logger.debug("Init completed.")
        self.init_webinterface()
        self._items = {}
        return

    def run(self):
        #self.logger.debug("Run method called")
        self.scheduler_add('poll_backend', self.poll_backend, prio=5, cycle=self._cycle)
        self.alive = True
        #self.poll_backend()

    def stop(self):
        self.scheduler_remove('poll_backend')
        #self.logger.debug("Stop method called")
        self.alive = False

    def parse_item(self, item):
        
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the neato_attribute and adds it to an internal array

        :param item: The item to process.
        """
        if self.get_iattr_value(item.conf, 'solarforecast_attribute'):
            if not self.get_iattr_value(item.conf, 'solarforecast_attribute') in self._items:
                self._items[self.get_iattr_value(item.conf, 'solarforecast_attribute')] = []
            self._items[self.get_iattr_value(item.conf, 'solarforecast_attribute')].append(item)
#            self.logger.debug(f"Appending item {item.id()}")


    def parse_logic(self, logic):
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        pass


    def poll_backend(self):

        self.logger.debug(f"polling backend...")
        urlService = 'https://api.forecast.solar/estimate/'
        functionURL = '{0}/{1}/{2}/{3}/{4}'.format(self.latitude,self.longitude,self.declination,self.azimuth,self.kwp)

        #self.logger.debug(f"DEBUG URL: {urlService + functionURL}")

        sessionrequest_response = self.session.get(
            urlService + functionURL, 
            headers={'content-type': 'application/json'}, timeout=10, verify=False)
        
#        self.logger.debug(f"Session request response: {sessionrequest_response.text}")
        statusCode = sessionrequest_response.status_code
        if statusCode == 200:
            pass
            #self.logger.debug("Sending session request command successful")
        else:
            self.logger.error(f"Server error: {statusCode}")
            return 

        responseJson = sessionrequest_response.json()
        
        # Decode Json data:        
        wattHoursToday = None
        wattHoursTomorrow = None
        today = self._sh.now().date()
        tomorrow = today + datetime.timedelta(days=1)
        self.last_update = today

        if responseJson:
            if 'result' in responseJson:
                resultJson = responseJson['result']
                if 'watt_hours_day' in resultJson:
                    wattHoursJson = resultJson['watt_hours_day']
#                   self.logger.debug(f"wattHourJson: {wattHoursJson}")
        
                    if str(today) in wattHoursJson:
                        wattHoursToday = float(wattHoursJson[str(today)])
                    if str(tomorrow) in wattHoursJson:
                        wattHoursTomorrow = float(wattHoursJson[str(tomorrow)])
#                    self.logger.debug(f"Ertrag today {wattHoursToday/1000} kWh, tomorrow: {wattHoursTomorrow/1000} kwH")


        for attribute, matchStringItems in self._items.items():

#            if not self.alive:
#                return

#            self.logger.warning("DEBUG: attribute: {0}, matchStringItems: {1}".format(attribute, matchStringItems))

            value = None

            if attribute == 'power_today':
                value = wattHoursToday
            elif attribute == 'power_tomorrow':
                value = wattHoursTomorrow
            elif attribute == 'date_today':
                value = str(today)
            elif attribute == 'date_tomorrow':
                value = str(tomorrow)
            
            # if a value was found, store it to item
            if value is not None:
                for sameMatchStringItem in matchStringItems:
                    sameMatchStringItem(value, self.get_shortname() )
#                    self.logger.debug('_update: Value "{0}" written to item {1}'.format(value, sameMatchStringItem))
        pass

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
    def index(self, reload=None, action=None, email=None, hashInput=None, code=None, tokenInput=None, mapIDInput=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        calculatedHash = ''
        codeRequestSuccessfull  = None
        token = ''
        configWriteSuccessfull  = None
        resetAlarmsSuccessfull  = None
        boundaryListSuccessfull = None



        if action is not None:
            self.logger.error("Unknown command received via webinterface")

        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, 
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])))


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


