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
from .webif import WebInterface

import requests
import json
import datetime


class Solarforecast(SmartPlugin):
    PLUGIN_VERSION = '1.9.4'

    def __init__(self, sh):
        """
        Initalizes the plugin.

        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._sh = sh
        self._cycle = 7200
        self.session = requests.Session()
        
        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        if self.get_parameter_value('latitude') != 0 and self.get_parameter_value('longitude') != 0:
            self.latitude = self.get_parameter_value('latitude')
            self.longitude = self.get_parameter_value('longitude')
        else:
            self.logger.debug("__init__: latitude and longitude not provided, using shng system values instead.")
            self.latitude = self.get_sh()._lat
            self.longitude = self.get_sh()._lon

        self.declination = self.get_parameter_value('declination')
        self.azimuth = self.get_parameter_value('azimuth')
        self.kwp = self.get_parameter_value('kwp')
        self.service = self.get_parameter_value('service')
        self.webif_pagelength = self.get_parameter_value('webif_pagelength')

        if self.latitude is None or \
                self.longitude is None or \
                self.declination is None or \
                self.azimuth is None or \
                self.kwp is None:
            self.logger.error("Plugin needs valid latitude, longitude, declination, azimuth and kwp values")

        if self.service != 'solarforecast':
            self.logger.error(f"Service {self.service} is not supported yet.")
        
        self.logger.debug("Init completed.")
        self.init_webinterface(WebInterface)
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

        try:
            sessionrequest_response = self.session.get(
                urlService + functionURL, 
                headers={'content-type': 'application/json'}, timeout=10, verify=False)
        
#            self.logger.debug(f"Session request response: {sessionrequest_response.text}")
        except requests.exceptions.Timeout as e:
            self.logger.warning(f"Timeout exception during get command: {str(e)}")
            return 
        except Exception as e:
            self.logger.error(f"Exception during get command: {str(e)}")
            return

        statusCode = sessionrequest_response.status_code
        if statusCode == 200:
            self.logger.debug("Sending session request command successful")
            pass
        else:
            self.logger.error(f"Server error: {statusCode}")
            return 

        responseJson = sessionrequest_response.json()
        self.logger.debug(f"Json response: {responseJson}")
        
        # Decode Json data:        
        wattHoursToday = None
        wattHoursTomorrow = None
        today = self._sh.shtime.now().date()
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
#                   self.logger.debug(f"Ertrag today {wattHoursToday/1000} kWh, tomorrow: {wattHoursTomorrow/1000} kwH")


        for attribute, matchStringItems in self._items.items():

            if not self.alive:
                return

#            self.logger.warning("DEBUG: attribute: {0}, matchStringItems: {1}".format(attribute, matchStringItems))

            value = None

            if attribute == 'energy_today':
                value = wattHoursToday
            elif attribute == 'energy_tomorrow':
                value = wattHoursTomorrow
            elif attribute == 'date_today':
                value = str(today)
            elif attribute == 'date_tomorrow':
                value = str(tomorrow)
            
            # if a value was found, store it to item
            if value is not None:
                for sameMatchStringItem in matchStringItems:
                    sameMatchStringItem(value, self.get_shortname() )
                    self.logger.debug('_update: Value "{0}" written to item {1}'.format(value, sameMatchStringItem))
        pass

    def get_items(self):
        return self._items
  





