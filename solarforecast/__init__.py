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

from lib.model.smartplugin import SmartPlugin
from .webif import WebInterface

import requests
import datetime

SERVICES = ['solarforecast']

# provide for locally cached data to prevent online requests while testing. Do not use.
TESTING = False
# TESTING = True
DUMMY = {}


class Solarforecast(SmartPlugin):
    PLUGIN_VERSION = '1.9.5'

    def __init__(self, sh):
        """
        Initalizes the plugin.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._sh = sh
        self._cycle = 7200
        self.json = {}

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.latitude = self.get_parameter_value('latitude')
        self.longitude = self.get_parameter_value('longitude')

        # hopefully, we don't have users using this off Africas western coast... ;-)
        if self.latitude == self.longitude == 0.0:
            self.latitude = self._sh._lat
            self.longitude = self._sh._lon
            self.logger.debug("latitude and longitude not provided, using shng system values instead.")

        self.declination = self.get_parameter_value('declination')
        self.azimuth = self.get_parameter_value('azimuth')
        self.kwp = self.get_parameter_value('kwp')
        self.service = self.get_parameter_value('service')
        self.webif_pagelength = self.get_parameter_value('webif_pagelength')

        # Note: as plugin.yaml makes providing parameters mandatory, they cannot be None anymore

        if self.service not in SERVICES:
            self.logger.error(f"Service {self.service} is not supported yet.")
            self._init_complete = False
            return

        self.logger.debug("Init completed.")
        self.init_webinterface(WebInterface)

    def run(self):
        self.logger.debug("Run method called")
        self.scheduler_add('poll_backend', self.poll_backend, prio=5, cycle=self._cycle)
        self.alive = True

    def stop(self):
        self.logger.debug("Stop method called")
        self.alive = False
        self.scheduler_remove('poll_backend')

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the solarforecast_attribute and adds it to an internal array

        :param item: The item to process.
        """
        super().parse_item(item)

        if self.get_iattr_value(item.conf, 'solarforecast_attribute'):
            # add_item automatically adds to self._plg_item_dict and self._item_lookup_dict
            # the last one is equal to old self._items, but supports (later) item removal
            self.add_item(item, mapping=self.get_iattr_value(item.conf, 'solarforecast_attribute'))

    def _get_json(self, url):

        if TESTING and url in DUMMY:

            # for testing, use cached responses to prevent frequent polling of service
            self.logger.debug('using dummy response for request url')
            self.json = DUMMY[url]
        else:
            try:
                response = requests.get(
                    url, headers={'content-type': 'application/json'}, timeout=10, verify=False)

            except requests.exceptions.Timeout as e:
                self.logger.warning(f"Timeout exception during get command: {e}")
                return
            except Exception as e:
                self.logger.error(f"Exception during get command: {e}")
                return

            statusCode = response.status_code
            if statusCode == 200:
                self.logger.debug("Sending session request command successful")
            else:
                self.logger.error(f"Server error: {statusCode}")
                return

            try:
                self.json = response.json()
            except Exception as e:
                self.logger.error(f"Exception during json decoding: {str(e)}")
                self.json = {}
                return

    def poll_backend(self):

        if not self.alive:
            return

        self.logger.debug("polling backend...")

        urlService = 'https://api.forecast.solar/estimate/'
        functionURL = f'{self.latitude}/{self.longitude}/{self.declination}/{self.azimuth}/{self.kwp}'

        self.logger.debug(f"DEBUG URL: {urlService + functionURL}")

        # fetch json data
        self._get_json(urlService + functionURL)

        self.logger.debug(f"Json response: {self.json}")

        # Decode Json data:
        wattHoursToday = None
        wattHoursTomorrow = None
        today = self._sh.shtime.now().date()
        tomorrow = today + datetime.timedelta(days=1)
        self.last_update = today

        if not self.json or 'result' not in self.json:
            return

        resultJson = self.json['result']
        if 'watt_hours_day' in resultJson:
            wattHoursJson = resultJson['watt_hours_day']
            # self.logger.debug(f"wattHourJson: {wattHoursJson}")
            if str(today) in wattHoursJson:
                wattHoursToday = float(wattHoursJson[str(today)])
            if str(tomorrow) in wattHoursJson:
                wattHoursTomorrow = float(wattHoursJson[str(tomorrow)])
            # self.logger.debug(f"Ertrag today {wattHoursToday/1000} kWh, tomorrow: {wattHoursTomorrow/1000} kwH")

        # check all attributes...
        for attribute, items in self._item_lookup_dict.items():
            value = None

            if attribute == 'energy_today':
                value = wattHoursToday
            elif attribute == 'energy_tomorrow':
                value = wattHoursTomorrow
            elif attribute == 'date_today':
                value = str(today)
            elif attribute == 'date_tomorrow':
                value = str(tomorrow)
            elif attribute == 'watts_hourly':

                # recalculate values for easier use
                now = self._sh.shtime.now()
                datestr = str(now.date())

                # {hour0: watts, hour1: watts, hour2: watts...}
                value = {int(k[11:13]): self.json['result']['watts'][k] for k in sorted(self.json['result']['watts'].keys()) if k.startswith(datestr)}

            # if a value was found, store it to item(s)
            if value is not None:
                for item in items:
                    item(value, self.get_shortname())
                    self.logger.debug(f'Value "{value}" written to item {item}')

    def is_power_available(self, power, hours):
        """
        This function should return a boolean value indicating if the requested
        power is estimated to be available for the next given number of hours.
        The current hour is counted, but to keep it simple, the given number of 
        hours are counten from the next full hour, so we count to "now + hours + 1".

        As errors cannot properly be handled in eval call stacks, we return False
        for every error, as there might be
        - server error, parameter error, timout, auth error (public limits)
        - json error, data error
        - connection error
        - plugin not running

        :param power: watts requested
        :ptype power: int
        :param hours: number of hours requested
        :ptype hours: int

        :return: True if power is estimated to be available, False else
        :rtype: bool
        """

        if not self.json:
            try:
                self.poll_backend()
            except Exception:
                return False

        # exceptions not appropriate for eval...
        if not self.json:
            return False

        # see self.poll_backend()
        datestr = str(self._sh.shtime.now().date())
        watts = {int(k[11:13]): self.json['result']['watts'][k] for k in sorted(self.json['result']['watts'].keys()) if k.startswith(datestr)}

        for hour in range(self.now().hour, self.now().hour + hours + 1):
            if watts.get(hour, 0) < power:
                return False

        return True
