#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2016 René Frieß                        rene.friess(a)gmail.com
#  Version 1.1.1
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
import json
from lib.model.smartplugin import SmartPlugin


class TankerKoenig(SmartPlugin):
    PLUGIN_VERSION = "1.4.1"
    _base_url = 'https://creativecommons.tankerkoenig.de/json/'
    _detail_url_suffix = 'detail.php'
    _prices_url_suffix = 'prices.php'
    _list_url_suffix = 'list.php'

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin
        @param apikey: For accessing the free "Tankerkönig-Spritpreis-API" you need a personal
        api key. For your own key register to https://creativecommons.tankerkoenig.de
        """
        self.logger = logging.getLogger(__name__)
        self._apikey = self.get_parameter_value('apikey')
        self._session = requests.Session()

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def get_petrol_stations(self, lat, lon, type='diesel', sort='price', rad='4'):
        """
        Returns a list of information for petrol stations around a specific location and radius
        Should not be used extensively, due to performance issues on tankerkoenig side.
        https://creativecommons.tankerkoenig.de/#techInfo
        @param lat: latitude of center to retrieve petrol station information for
        @param long: longitude of center to retrieve petrol station information for
        @param type: price type, e.g. diesel
        @param sort: sort type, e.g. price
        @param rad: radius in kilometers
        """
        result_stations = []
        try:
            response = self._session.get(self._build_url("%s?lat=%s&lng=%s&rad=%s&sort=%s&type=%s&apikey=%s" % (
            self._list_url_suffix, lat, lon, rad, sort, type, self._apikey)))
        except Exception as e:
            self.logger.error(
                "Exception when sending GET request for get_petrol_stations: %s" % str(e))
            return
        self.logger.debug(self._build_url("%s?lat=%s&lng=%s&rad=%s&sort=%s&type=%s&apikey=%s" % (
        self._list_url_suffix, lat, lon, rad, sort, type, self._apikey)))
        json_obj = response.json()
        keys = ['place', 'brand', 'houseNumber', 'street', 'id', 'lng', 'name', 'lat', 'price', 'dist', 'isOpen',
                'postCode']
        if json_obj.get('stations', None) is None:
            self.logger.warning("Tankerkönig didn't return any station")
        else:
            for i in json_obj['stations']:
                result_station = {}
                for key in keys:
                    result_station[key] = i[key]
                result_stations.append(result_station)
        return result_stations

    def get_petrol_station_detail(self, id):
        """
        Returns detail information for a petrol station id
        Should not be used extensively, due to performance issues on tankerkoenig side.
        https://creativecommons.tankerkoenig.de/#techInfo
        @param id: Internal ID of petrol station to retrieve information for
        """
        try:
            response = self._session.get(
                self._build_url("%s?id=%s&apikey=%s" % (self._detail_url_suffix, id, self._apikey)))
        except Exception as e:
            self.logger.error(
                "Exception when sending GET request for get_petrol_station_detail: %s" % str(e))
            return
        json_obj = response.json()
        keys = ['e5', 'e10', 'diesel', 'street', 'houseNumber', 'postCode', 'place', 'brand', 'id', 'lng', 'name',
                'lat', 'isOpen']
        result_station = {}
        try:
            i = json_obj['station']
            for key in keys:
                result_station[key] = i[key]
        except:
            pass

        return result_station

    def get_petrol_station_prices(self, ids):
        """
        Returns a list of prices for an array of petrol station ids
        Recommended to be used by tankerkoenig team due to performance issues!!!
        https://creativecommons.tankerkoenig.de/#techInfo
        @param ids: Array of tankerkoenig internal petrol station ids to retrieve the prices for
        """
        result_station_prices = []
        station_ids_string = json.dumps(ids)
        try:
            response = self._session.get(
                self._build_url("%s?ids=%s&apikey=%s" % (self._prices_url_suffix, station_ids_string, self._apikey)))
        except Exception as e:
            self.logger.error(
                "Exception when sending GET request for get_petrol_station_detail: %s" % str(e))
            return
        json_obj = response.json()
        keys = ['e5', 'e10', 'diesel', 'status']

        for id in ids:
            if 'prices' in json_obj:
                if id in json_obj['prices']:
                    result_station = dict()
                    result_station['id'] = id
                    for key in keys:
                        if key in json_obj['prices'][id]:
                            result_station[key] = json_obj['prices'][id][key]
                        else:
                            result_station[key] = ""
                    result_station_prices.append(result_station)
                else:
                    self.logger.error("No result for station with id %s. Check manually!" % id)
            else:
                self.logger.error("'prices' key missing in json response! Check manually!" % id)
        return result_station_prices

    def _build_url(self, suffix):
        """
        Builds a request url
        @param suffix: url suffix
        @return: string of the url
        """
        url = "%s%s" % (self._base_url, suffix)
        return url
