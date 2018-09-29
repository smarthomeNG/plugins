#!/usr/bin/env python3
#
# Copyright 2013 Jan N. Klug
#
#
#  This SmartHomeNG plugin is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This software is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with it. If not, see <http://www.gnu.org/licenses/>.
#

import hashlib
import logging
import datetime
import threading
import xml.etree.cElementTree
from lib.model.smartplugin import SmartPlugin
from bin.smarthome import VERSION
from lib.tools import Tools


class wettercom(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.4.0"
    _server = 'api.wetter.com'

    def __init__(self, smarthome):
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)
        self._project = self.get_parameter_value('project')
        self._apikey = self.get_parameter_value('apikey')
        self._tools = Tools()
        self.lock = threading.Lock()

    def search(self, location):
        """
        get city code
        returns one or more city code(s) for use in forecast function
        """
        retval = {}
        searchURL = 'http://{}/location/index/search/{}/project/{}/cs/{}'.format(
            self._server, location, self._project, hashlib.md5(('{}{}{}'.format(
                self._project, self._apikey, location)).encode('UTF-8')).hexdigest())
        self.logger.debug('Search URL: {}'.format(searchURL))

        try:
            content = self._tools.fetch_url(searchURL)
        except Exception:
            content = None

        if content:
            searchXML = xml.etree.cElementTree.fromstring(content)

            for hits in searchXML.iter('hits'):
                numhits = int(hits.text)
                break

            if numhits > 0:
                retval = [ccodes.text for ccodes in searchXML.iter('city_code')]

        return retval

    def forecast(self, city_code):
        """
        get forecast data
        returns forecast data for the location city_code (use search to get it)
        forecast data is returned as dictionary for each date/time values are

        max. temperature, weather condition text, wind speed,
        condensation probability, min. temperatur, wind direction in degree,
        wind direction text, weather condition code
        """
        retval = {}
        forecastURL = 'http://{}/forecast/weather/city/{}/project/{}/cs/{}'.format(
            self._server, city_code, self._project, hashlib.md5(('{}{}{}'.format(
                self._project, self._apikey, city_code)).encode('UTF-8')).hexdigest())
        self.logger.debug('Forecast URL: {}'.format(forecastURL))

        try:
            content = self._tools.fetch_url(forecastURL)
        except Exception:
            content = None

        if content:
            forecastXML = xml.etree.cElementTree.fromstring(content)

            for days in forecastXML.findall('./forecast/date'):
                year, month, day = days.attrib['value'].split('-')
                for time in days.iter('time'):
                    hour, minute = time.attrib['value'].split(':')
                    d = datetime.datetime(int(year), int(month), int(day),
                                          int(hour))
                    items = [time.find('tn'),
                             time.find('tx'),
                             time.find('w_txt'),
                             time.find('pc'),
                             time.find('ws'),
                             time.find('wd'),
                             time.find('wd_txt'),
                             time.find('w')]

                    retval[d] = []
                    for item in items:
                      retval[d].append(None if item is None else item.text)

            return retval

    def run(self):
        self.alive = True
        self.logger.debug('run method called')

    def stop(self):
        self.alive = False
        self.logger.debug('stop method called')

    def parse_item(self, item):
        return None

    def parse_logic(self, logic):
        return None
