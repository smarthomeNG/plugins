#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2016 René Frieß                      rene.friess(a)gmail.com
#  Copyright 2022 Michael Wenzel                  wenzel_michael(a)web.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Plugin to get prices from TankerKoenig
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
from lib.item import Items

import requests
import json

from .webif import WebInterface

'https://creativecommons.tankerkoenig.de/json/'


class TankerKoenig(SmartPlugin):
    PLUGIN_VERSION = "2.0.4"

    _base_url = 'https://creativecommons.tankerkoenig.de/json'
    _detail_url_suffix = 'detail.php'
    _prices_url_suffix = 'prices.php'
    _list_url_suffix = 'list.php'

    def __init__(self, sh):
        """
        Initializes the plugin

        For accessing the free "Tankerkönig-Spritpreis-API" you need a personal api key. For your own key register to https://creativecommons.tankerkoenig.de
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.item_dict = {}
        self.station_ids = []
        self.station_details = {}
        self.station_prices = {}
        self._lat = self.get_sh()._lat
        self._lon = self.get_sh()._lon
        self._session = requests.Session()
        self.alive = False

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        try:
            self.webif_pagelength = self.get_parameter_value('webif_pagelength')
            self._apikey = self.get_parameter_value('apikey')
            self.price_update_cycle = self.get_parameter_value('price_update_cycle')
            self.details_update_cycle = self.get_parameter_value('details_update_cycle')
        except KeyError as e:
            self.logger.critical(f"Plugin '{self.get_shortname()}': Inconsistent plugin (invalid metadata definition: {e} not defined).")
            self._init_complete = False
            return

        # init WebInterface
        self.init_webinterface(WebInterface)

    def run(self):
        """
        Run method for the plugin
        """

        self.logger.debug("Run method called")

        # create scheduler for price data updates
        self.scheduler_add('update_status_data', self.update_status_data, cycle=self.price_update_cycle)

        # create scheduler for detailed data updates
        _cycle = {'daily': 24*60*60, 'weekly': 7*24*60*60, 'monthly': 30.5*24*60*60}[self.details_update_cycle]
        self.scheduler_add('update_detail_data', self.update_detail_data, cron='init+30', cycle=_cycle)

        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """

        self.logger.debug("Stop method called")
        self.scheduler_remove('update_status_data')
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in the future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """

        if self.has_iattr(item.conf, 'tankerkoenig_id'):
            self.logger.debug(f"parse item: {item}")
            station_id = self.get_iattr_value(item.conf, 'tankerkoenig_id')
            tankerkoenig_attr = self.get_iattr_value(item.conf, 'tankerkoenig_attr')

            if station_id and tankerkoenig_attr:
                self.logger.debug(f"parse_item: tankerkoenig_attr={tankerkoenig_attr} with station_id={station_id} detected, item added")
                self.item_dict[item] = {'station_id': station_id, 'tankerkoenig_attr': tankerkoenig_attr.lower()}

                if station_id not in self.station_ids:
                    self.station_ids.append(station_id)

        if self.has_iattr(item.conf, 'tankerkoenig_admin'):
            self.logger.debug(f"parse item: {item.id()}")
            tankerkoenig_admin = self.get_iattr_value(item.conf, 'tankerkoenig_admin')
            if tankerkoenig_admin == 'update':
                return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """

        if self.alive and caller != self.get_shortname():
            self.logger.info(f"Update item: {item.property.path}, item has been changed outside this plugin")

            if self.get_iattr_value(item.conf, 'tankerkoenig_admin').lower() == 'update' and item():
                self.logger.debug("Data update has been initiated.")
                self.update_status_data()
                item(False)
            return None

###################################################
#  Public Functions
###################################################

    def get_petrol_stations(self, lat: float = None, lon: float = None, price: str = 'diesel', sort: str = 'price', rad: float = 4) -> list:
        """
        Returns a list of information for petrol stations around a specific location and radius
        Should not be used extensively, due to performance issues on tankerkoenig side.

        @param lat: latitude of center to retrieve petrol station information for
        @param lon: longitude of center to retrieve petrol station information for
        @param price: price type, e.g. diesel
        @param sort: sort type, e.g. price
        @param rad: radius in kilometers
        """

        # set default for lat and lon
        if lat is None:
            lat = self._lat
        if lon is None:
            lon = self._lon

        # check if value for price
        if price not in ['e5', 'e10', 'diesel', 'all']:
            self.logger.error(f"Plugin '{self.get_fullname()}': Used value={price} for 'price' at 'get_petrol_stations' not allowed. Set to default 'all'.")
            price = 'all'

        # check if value for sort
        if sort not in ['price']:
            self.logger.error(f"Plugin '{self.get_fullname()}': Used value={sort} for 'sort' at 'get_petrol_stations' not allowed. Set to default 'price'.")
            sort = 'price'

        # limit radius to 25km
        if float(rad) > 25:
            self.logger.error(f"Plugin '{self.get_fullname()}': Used value={rad} for 'rad' at 'get_petrol_stations' not allowed. Set to max allowed value '25km'.")
            rad = 25

        result_stations = []
        json_obj = self._request_stations(lat=lat, lon=lon, price=price, sort=sort, rad=rad)

        keys = ['place', 'brand', 'houseNumber', 'street', 'id', 'lng', 'name', 'lat', 'price', 'dist', 'isOpen', 'postCode']
        if json_obj is None or json_obj.get('stations', None) is None:
            self.logger.warning(f"Plugin '{self.get_fullname()}': Tankerkönig didn't return any station")
        else:
            for i in json_obj['stations']:
                result_station = {}
                for key in keys:
                    result_station[key] = i[key]
                result_stations.append(result_station)
        return result_stations

    def get_petrol_station_detail(self, station_id: str) -> dict:
        """
        Returns detail information for a petrol station id

        Should not be used extensively, due to performance issues on tankerkoenig side.

        @param station_id: Internal ID of petrol station to retrieve information for
        """

        json_obj = self._request_station_detail(station_id)

        keys = ['e5', 'e10', 'diesel', 'street', 'houseNumber', 'postCode', 'place', 'brand', 'id', 'lng', 'name', 'lat', 'isOpen']
        result_station = {}

        try:
            i = json_obj['station']
            for key in keys:
                result_station[key] = i[key]
        except Exception:
            pass

        return result_station

    def get_petrol_station_detail_reduced(self, station_id: str) -> dict:
        """
        Returns reduced detail information (no príces and "open" status) for a petrol station id

        Should not be used extensively, due to performance issues on tankerkoenig side.

        @param station_id: Internal ID of petrol station to retrieve information for
        """
        station_details = self.get_petrol_station_detail(station_id)

        # clean dict
        keys_to_be_deleted = ['e5', 'e10', 'diesel', 'isOpen']
        for item in keys_to_be_deleted:
            if item in station_details:
                del station_details[item]

        # add address
        _street = station_details.get('street', None)
        _housenumber = station_details.get('houseNumber', None)
        _postcode = station_details.get('postCode', None)
        _place = station_details.get('place', None)
        station_details['address'] = f"{_street} {_housenumber}\n{_postcode} {_place}"

        return station_details

    def get_petrol_station_prices(self, station_ids: list) -> dict:
        """
        Returns a dict of prices for an array of petrol station ids

        Recommended to be used by tankerkoenig team due to performance issues!!!

        @param station_ids: Array of tankerkoenig internal petrol station ids to retrieve the prices for
        """
        _station_id_prices = self._request_station_prices(station_ids)
        if _station_id_prices is None:
            self.logger.error(
                f"get_petrol_station_prices: self._request_station_prices(station_ids) returned invalid result")
            return None
        _price_dict = _station_id_prices.get('prices', None)
        for station_id in station_ids:
            if station_id not in _price_dict:
               self.logger.error(f"Plugin '{self.get_fullname()}': No result for station with id {station_id}. Check manually!")

        if _price_dict and isinstance(_price_dict, dict):
            for station_id in _price_dict:
                if 'status' in _price_dict[station_id]:
                    _price_dict[station_id]['open'] = True if _price_dict[station_id]['status'].lower() == 'open' else False

        return _price_dict

###################################################
#  Plugin Functions
###################################################

    def update_status_data(self):
        """
        Gets price and status data for all defined stations and updates item values
        """

        self.station_prices = self.get_petrol_station_prices(self.station_ids)
        return self.set_item_status_values()

    def update_detail_data(self):
        """
        Gets price and status data for all defined stations and updates item values
        """

        self.station_details = self.get_station_details()
        return self.set_item_detail_values()

    def get_station_details(self):
        """
        Gets details for all defined stations and put it to plugin dict.
        """

        stations_details = {}

        for station_id in self.station_ids:
            station_details = self.get_petrol_station_detail_reduced(station_id)
            stations_details[station_id] = station_details

        return stations_details

    def set_item_status_values(self):
        """
        Set values of status items
        """

        for item in self.item_dict:
            self.logger.debug(f"set_item_status_values: handle item {item} type {item.type()}")
            station_id = self.item_dict[item]['station_id']
            tankerkoenig_attr = self.item_dict[item]['tankerkoenig_attr']
            if self.station_prices.get(station_id, None) is not None:
                value = self.station_prices.get(station_id, None).get(tankerkoenig_attr, None)
            else:
                self.logger.error(
                    f"set_item_status_values: station_id with {station_id} does not exist in station_prices.")
            self.logger.debug(f"set_item_status_values: station_id={station_id}, tankerkoenig_attr={tankerkoenig_attr}, value={value}")
            if value:
                item(value, self.get_shortname())

    def set_item_detail_values(self):
        """
        Set values of details items
        """

        for item in self.item_dict:
            station_id = self.item_dict[item]['station_id']
            tankerkoenig_attr = self.item_dict[item]['tankerkoenig_attr']
            if self.station_details.get(station_id, None) is not None:
                value = self.station_details.get(station_id, None).get(tankerkoenig_attr, None)
            else:
                self.logger.error(
                    f"set_item_status_values: station_id with {station_id} does not exist in station_details.")
            self.logger.debug(f"set_item_detail_values: station_id={station_id}, tankerkoenig_attr={tankerkoenig_attr}, value={value}")
            if value:
                item(value, self.get_shortname())

    def _request_stations(self, lat: float = None, lon: float = None, price: str = 'diesel', sort: str = 'price', rad: float = 4) -> dict:
        """
        Returns a dict of information for petrol stations around a specific location and radius

        Should not be used extensively, due to performance issues on tankerkoenig side.
        https://creativecommons.tankerkoenig.de/#techInfo

        URL:
        https://creativecommons.tankerkoenig.de/json/list.php?lat=52.521&lng=13.438&rad=1.5&sort=dist&type=all&apikey=00000000-0000-0000-0000-000000000002

        Reponse:
            [
                {                                                     Datentyp, Bedeutung
                    "id": "474e5046-deaf-4f9b-9a32-9797b778f047",   - UUID, eindeutige Tankstellen-ID
                    "name": "TOTAL BERLIN",                         - String, Name
                    "brand": "TOTAL",                               - String, Marke
                    "street": "MARGARETE-SOMMER-STR.",              - String, Straße
                    "place": "BERLIN",                              - String, Ort
                    "lat": 52.53083,                                - float, geographische Breite
                    "lng": 13.440946,                               - float, geographische Länge
                    "dist": 1.1,                                    - float, Entfernung zum Suchstandort in km
                    "diesel": 1.109,                                \
                    "e5": 1.339,                                     - float, Spritpreise in Euro
                    "e10": 1.319,                                   /
                    "isOpen": true,                                 - boolean, true, wenn die Tanke zum Zeitpunkt der Abfrage offen hat, sonst false
                    "houseNumber": "2",                             - String, Hausnummer
                    "postCode": 10407                               - integer, PLZ
                },
                {weitere Tankstelle},
                {}
            ]

        @param lat: latitude of center to retrieve petrol station information for
        @param lon: longitude of center to retrieve petrol station information for
        @param price: price type, e.g. diesel
        @param sort: sort type, e.g. price
        @param rad: radius in kilometers
        """

        url = self._build_url(f"{self._list_url_suffix}?lat={lat}&lng={lon}&rad={rad}&sort={sort}&type={price}&apikey={self._apikey}")
        try:
            response = self._session.get(url)
        except Exception as e:
            self.logger.error(f"Plugin '{self.get_fullname()}': Exception when sending GET request for _request_petrol_stations: {e}")
            return

        try:
            return response.json()
        except Exception as e:
            self.logger.error(f"Plugin '{self.get_fullname()}': Exception when handling GET response to JSON for _request_petrol_stations: {e}")
            return

    def _request_station_detail(self, station_id: str) -> dict:
        """
        Returns detail information for a petrol station id
        Should not be used extensively, due to performance issues on tankerkoenig side.
        https://creativecommons.tankerkoenig.de/#techInfo

        URL: https://creativecommons.tankerkoenig.de/json/detail.php?id=24a381e3-0d72-416d-bfd8-b2f65f6e5802&apikey=00000000-0000-0000-0000-000000000002

        Response:
            {
                "ok": true,
                "license": "CC BY 4.0 -  https:\/\/creativecommons.tankerkoenig.de",
                "data": "MTS-K",
                "status": "ok",
                "station": {
                    "id": "24a381e3-0d72-416d-bfd8-b2f65f6e5802",
                    "name": "Esso Tankstelle",
                    "brand": "ESSO",
                    "street": "HAUPTSTR. 7",
                    "houseNumber": " ",
                    "postCode": 84152,
                    "place": "MENGKOFEN",
                    "openingTimes": [                                               - Array mit regulären Öffnungszeiten
                        {
                            "text": "Mo-Fr",
                            "start": "06:00:00",
                            "end": "22:30:00"
                        },
                        {
                            "text": "Samstag",
                            "start": "07:00:00",
                            "end": "22:00:00"
                        },
                        {
                            "text": "Sonntag",
                            "start": "08:00:00",
                            "end": "22:00:00"
                        }
                    ],
                    "overrides": [                                                  - Array mit geänderten Öffnungszeiten
                        "13.04.2017, 15:00:00 - 13.11.2017, 15:00:00: geschlossen"  - im angegebenen Zeitraum geschlossen
                    ],
                    "wholeDay": false,                                              - nicht ganztägig geöffnet
                    "isOpen": false,
                    "e5": 1.379,
                    "e10": 1.359,
                    "diesel": 1.169,
                    "lat": 48.72210601,
                    "lng": 12.44438439,
                    "state": null                                                   - Bundesland nicht angegeben
                }
            }

        @param station_id: Internal ID of petrol station to retrieve information for
        """

        url = self._build_url(f"{self._detail_url_suffix}?id={station_id}&apikey={self._apikey}")
        try:
            response = self._session.get(url)
        except Exception as e:
            self.logger.error(f"Plugin '{self.get_fullname()}': Exception when sending GET request for get_petrol_station_detail: {e}, response was {response}")
            return

        try:
            return response.json()
        except Exception as e:
            self.logger.error(f"Plugin '{self.get_fullname()}': Exception when handling GET response to JSON for get_petrol_station_detail: {e}")
            return

    def _request_station_prices(self, station_ids: list):
        """
        Returns a json object with prices for an array of petrol station ids

        Recommended to be used by tankerkoenig team due to performance issues!!!
        https://creativecommons.tankerkoenig.de/#techInfo

        URL: https://creativecommons.tankerkoenig.de/json/prices.php?ids=4429a7d9-fb2d-4c29-8cfe-2ca90323f9f8,446bdcf5-9f75-47fc-9cfa-2c3d6fda1c3b,60c0eefa-d2a8-4f5c-82cc-b5244ecae955,44444444-4444-4444-4444-444444444444&apikey=00000000-0000-0000-0000-000000000002

        Response:
            {
                "ok": true,
                "license": "CC BY 4.0 -  https:\/\/creativecommons.tankerkoenig.de",
                "data": "MTS-K",
                "prices": {
                    "60c0eefa-d2a8-4f5c-82cc-b5244ecae955": {
                        "status": "open",                               - Tankstelle ist offen
                        "e5": false,                                    - kein Super
                        "e10": false,                                   - kein E10
                        "diesel": 1.189                                 - Tankstelle führt nur Diesel
                    },
                    "446bdcf5-9f75-47fc-9cfa-2c3d6fda1c3b": {
                        "status": "closed"                              - Tankstelle ist zu
                    },
                    "4429a7d9-fb2d-4c29-8cfe-2ca90323f9f8": {
                        "status": "open",
                        "e5": 1.409,
                        "e10": 1.389,
                        "diesel": 1.129
                    },
                    "44444444-4444-4444-4444-444444444444": {
                        "status": "no prices"                           - keine Preise für Tankstelle verfügbar
                    }
                }
            }

        @param station_ids: Array of tankerkoenig internal petrol station ids to retrieve the prices for
        """

        station_ids_string = json.dumps(station_ids)
        url = self._build_url(f"{self._prices_url_suffix}?ids={station_ids_string}&apikey={self._apikey}")

        try:
            response = self._session.get(url)
        except Exception as e:
            self.logger.error(f"Plugin '{self.get_fullname()}': Exception when sending GET request for _request_station_prices: {e}")
            return

        try:
            return response.json()
        except Exception as e:
            self.logger.error(f"Plugin '{self.get_fullname()}': Exception when handling GET response to JSON for _request_station_prices: {e}")
            return

###################################################
#  Helper Functions
###################################################

    def _build_url(self, suffix):
        """
        Builds a request url
        @param suffix: url suffix
        @return: string of the url
        """
        return f"{self._base_url}/{suffix}"

    @property
    def station_list(self):
        """
        Returns a list of station ids to be requested
        """
        return self.station_ids

    @property
    def item_list(self):
        """
        Returns a list of items with defined station_ids
        """
        return list(self.item_dict.keys())

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()
