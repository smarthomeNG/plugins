#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2017 René Frieß                      rene.friess(a)gmail.com
#  Version 1.3.0.1
#########################################################################
#
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
import requests
from lib.model.smartplugin import SmartPlugin

class Traffic(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.3.0.1"
    _base_url = 'https://maps.googleapis.com/maps/api/directions/json'

    def __init__(self, smarthome, apikey, language='de'):
        """
        Initializes the plugin
        @param apikey: For accessing the free "Google Directions API" you need a personal
        api key. For your own key see https://developers.google.com/maps/documentation/directions/intro?hl=de#traffic-model
        @param language: two char language code. default: de
        """
        self.logger = logging.getLogger(__name__)
        self._sh = smarthome
        self._apikey = apikey
        self._language = language
        self._session = requests.Session()

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def get_route_info(self, origin, destination, alternatives=False, mode='driving'):
        """
        Returns route information for a provided origin and destination
        @param origin: string representing the origin according to google directions api
        @param destination: string representing the destination according to google directions api
        @param alternatives: returns alternative routes if true
        @param mode: driving (default), walking, bicycling, transit

        @return: return an array of routes if alternatives are true, or a route (as dict) if alternatives are false
        """
        routes = []
        try:
            response = self._session.get(
                '%s?language=%s&alternatives=%s&origin=%s&destination=%s&mode=%s&key=%s' % (self._base_url,
                self._language, alternatives, origin, destination, mode, self._apikey))
        except Exception as e:
            self.logger.error(
                "Exception when sending GET request for get_route_info: %s" % str(e))
            return
        json_obj = response.json()

        for route in json_obj['routes']:
            route_information = {}
            for leg in route['legs']:
                route_information['distance'] = leg['distance']['value']
                route_information['duration'] = leg['duration']['value']
                route_information['start_address'] = leg['start_address']
                route_information['start_location_lat'] = leg['start_location']['lat']
                route_information['start_location_lon'] = leg['start_location']['lng']
                route_information['end_address'] = leg['end_address']
                route_information['end_location_lat'] = leg['end_location']['lat']
                route_information['end_location_lon'] = leg['end_location']['lng']
                route_information['html_instructions'] = ''
                for step in leg['steps']:
                    route_information['html_instructions'] = route_information['html_instructions']+'<p>'+step['html_instructions']+'</p>'
            route_information['summary'] = route['summary']
            route_information['copyrights'] = route['copyrights']

        routes.append(route_information)
        if alternatives:
            return routes
        else:
            return route_information
