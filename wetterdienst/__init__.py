#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2018 René Frieß                      rene.friess(a)gmail.com
#  Version 1.5.0.1
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
import datetime
import json
import functools
import wetterdienst
from wetterdienst.dwd.observations import DWDObservationData, DWDObservationParameterSet, DWDObservationPeriod, \
    DWDObservationResolution
from datetime import datetime, timedelta, timezone
from lib.module import Modules
from lib.model.smartplugin import *
from bin.smarthome import VERSION


class Wetterdienst(SmartPlugin):
    PLUGIN_VERSION = "1.0.0"

    _base_url = 'https://api.openweathermap.org/%s'
    _base_img_url = 'https://tile.openweathermap.org/map/%s/%s/%s/%s.png?appid=%s'

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin
        """
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)
        self._cycle_1_minute = 60
        self._cycle_10_minutes = 600
        self._cycle_1_hour = 3600
        self.shtime = Shtime.get_instance()
        if self.get_parameter_value('latitude') != '' and self.get_parameter_value('longitude') != '':
            self._lat = self.get_parameter_value('latitude')
            self._lon = self.get_parameter_value('longitude')
        else:
            self.logger.debug("__init__: latitude and longitude not provided, using shng system values instead.")
            self._lat = float(self.get_sh()._lat)
            self._lon = float(self.get_sh()._lon)
        self._wetterdienst = wetterdienst
        self._items_1min = {}
        self._items_10min = {}
        self._items_1hr = {}
        self.init_webinterface()

    def run(self):
        self.scheduler_add(__name__ + "_1min", self._update_loop_1_minute, prio=5, cycle=self._cycle_1_minute, offset=2)
        self.scheduler_add(__name__ + "_10min", self._update_loop_10_minutes, prio=5, cycle=self._cycle_10_minutes,
                           offset=2)
        self.scheduler_add(__name__ + "_1hr", self._update_loop_1_hour, prio=5, cycle=self._cycle_1_hour, offset=2)
        self.alive = True

    def stop(self):
        self.alive = False

    def _update_loop_1_minute(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug('Starting 1 minute update loop for instance %s' % self.get_instance_name())
        if not self.alive:
            return

        self._update_1min()

    def _update_loop_5_minutes(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug('Starting 5 minute update loop for instance %s' % self.get_instance_name())
        if not self.alive:
            return

        self._update_5min()

    def _update_loop_10_minutes(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug('Starting 10 minute update loop for instance %s' % self.get_instance_name())
        if not self.alive:
            return

        self._update_10min()

    def _update_loop_15_minutes(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug('Starting 15 minute update loop for instance %s' % self.get_instance_name())
        if not self.alive:
            return

        self._update_15min()

    def _update_loop_1_hour(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug('Starting 1 hour update loop for instance %s' % self.get_instance_name())
        if not self.alive:
            return

        self._update_1hr()

    def _collect_data(self, parameter, station_ids, time_resolution, start_date=None):
        if start_date is not None:
            observations = DWDObservationData(
                station_ids=station_ids,
                parameter=parameter,
                time_resolution=time_resolution,
                tidy_data=True,
                start_date=start_date,
                humanize_column_names=True
            )
        else:
            observations = DWDObservationData(
                station_ids=station_ids,
                parameters=parameter,
                time_resolution=time_resolution,
                tidy_data=True,
                humanize_column_names=True
            )
        return observations.collect_data()

    def _update_1min(self):
        """
        Updates information on diverse items
        """
        self.logger.debug("Updating 1 min!")
        parameter = []
        station_ids = []
        time_resolution = DWDObservationResolution.MINUTE_1
        for key, item in self._items_1min.items():
            if self.convert_parameter(item['conf']['wetterdienst_parameter']) not in parameter:
                parameter.append(self.convert_parameter(item['conf']['wetterdienst_parameter']))
            if item['conf']['wetterdienst_station_id'] not in station_ids:
                station_ids.append(item['conf']['wetterdienst_station_id'])
        ##data = self._collect_data(parameter, list(dict.fromkeys(station_ids)), time_resolution, start_date=self.shtime.utcnow().strftime("%Y-%m-%d"))
        ##for value in data:
        ##self.logger.error(value['ELEMENT']+" "+str(value['VALUE']))
        return

    def _update_5min(self):
        """
        Updates information on diverse items
        """
        return

    def _update_10min(self):
        """
        Updates information on diverse items
        """
        return

    def _update_15min(self):
        """
        Updates information on diverse items
        """
        return

    def _update_1hr(self):
        """
        Updates information on diverse items
        """
        return

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the owm_matchstring and adds it to an internal array

        :param item: The item to process.
        """
        if 'wetterdienst_time_resolution' in item.conf:
            if item.conf['wetterdienst_station_id'] and item.conf['wetterdienst_parameter'] and item.conf[
                'wetterdienst_period_type']:
                keystring = '%s_%s_%s' % (
                    item.conf['wetterdienst_station_id'], item.conf['wetterdienst_parameter'],
                    item.conf['wetterdienst_period_type'])
                if item.conf['wetterdienst_time_resolution'] == "MINUTE_1":
                    if not keystring in self._items_1min:
                        self._items_1min[keystring] = []
                        self._items_1min[keystring] = item
                if item.conf['wetterdienst_time_resolution'] == "MINUTE_5":
                    if not keystring in self._items_10min:
                        self._items_5min[keystring] = []
                        self._items_5min[keystring] = item
                if item.conf['wetterdienst_time_resolution'] == "MINUTE_10":
                    if not keystring in self._items_10min:
                        self._items_10min[keystring] = []
                        self._items_10min[keystring] = item
                if item.conf['wetterdienst_time_resolution'] == "MINUTE_15":
                    if not keystring in self._items_15min:
                        self._items_10min[keystring] = []
                        self._items_10min[keystring] = item
                if item.conf['wetterdienst_time_resolution'] == "HOURLY":
                    if not keystring in self._items_1hr:
                        self._items_1hr[keystring] = []
                        self._items_1hr[keystring] = item
            else:
                self.logger.error(
                    'Invalid item %s: wetterdienst_time_resolution specified, but wetterdienst_parameter, wetterdienst_period_type or wetterdienst_time_resolution missing.' % item())
        return

    def get_items(self):
        return self._items

    def get_wetterdienst(self):
        return self._wetterdienst

    def get_nearby_stations(self, max_distance_in_km=25, lat=None, lon=None,
                            parameter=None, time_resolution=None,
                            period_type=None):
        tr = self.convert_time_resolution(time_resolution)
        p = self.convert_parameter(parameter)
        pt = self.convert_period_type(period_type)
        if lat is None or lat is '':
            lat = self._lat
        if lon is None or lon is '':
            lon = self._lon
        stations_df = None
        try:
            sites = DWDObservationSites(
                parameters=p,
                time_resolution=tr,
                periods=pt
            )
            stations_df = sites.nearby_radius(
                latitude=float(lat),
                longitude=float(lon),
                max_distance_in_km=int(max_distance_in_km)
            )

        except Exception as e:
            self.logger.error("Plugin '{}': error when searching for stations: {}".format(self.get_shortname(), str(e)))
        return stations_df

    def convert_parameter(self, parameter=None):
        if parameter == "PRECIPITATION":
            p = DWDObservationParameterSet.PRECIPITATION
        elif parameter == "TEMPERATURE_AIR":
            p = DWDObservationParameterSet.TEMPERATURE_AIR
        elif parameter == "TEMPERATURE_EXTREME":
            p = DWDObservationParameterSet.TEMPERATURE_EXTREME
        elif parameter == "WIND_EXTREME":
            p = DWDObservationParameterSet.WIND_EXTREME
        elif parameter == "SOLAR":
            p = DWDObservationParameterSet.SOLAR
        elif parameter == "CLOUD_TYPE":
            p = DWDObservationParameterSet.CLOUD_TYPE
        elif parameter == "CLOUDINESS":
            p = DWDObservationParameterSet.CLOUDINESS
        elif parameter == "DEW_POINT":
            p = DWDObservationParameterSet.DEW_POINT
        elif parameter == "WIND":
            p = DWDObservationParameterSet.WIND
        elif parameter == "PRESSURE":
            p = DWDObservationParameterSet.SOLAR
        elif parameter == "TEMPERATURE_SOIL":
            p = DWDObservationParameterSet.CLOUD_TYPE
        elif parameter == "SUNSHINE_DURATION":
            p = DWDObservationParameterSet.CLOUDINESS
        elif parameter == "VISIBILITY":
            p = DWDObservationParameterSet.DEW_POINT
        elif parameter == "WIND":
            p = DWDObservationParameterSet.WIND
        elif parameter == "WIND_SYNOPTIC":
            p = DWDObservationParameterSet.WIND_SYNOPTIC
        elif parameter == "MOISTURE":
            p = DWDObservationParameterSet.MOISTURE
        elif parameter == "PRESSURE":
            p = DWDObservationParameterSet.PRESSURE
        elif parameter == "SOIL":
            p = DWDObservationParameterSet.SOIL
        elif parameter == "CLIMATE_SUMMARY":
            p = DWDObservationParameterSet.CLIMATE_SUMMARY
        elif parameter == "PRECIPITATION_MORE":
            p = DWDObservationParameterSet.PRECIPITATION_MORE
        elif parameter == "WATER_EQUIVALENT":
            p = DWDObservationParameterSet.WATER_EQUIVALENT
        elif parameter == "WEATHER_PHENOMENA":
            p = DWDObservationParameterSet.WEATHER_PHENOMENA
        else:
            p = DWDObservationParameterSet.PRECIPITATION
        return p

    def convert_period_type(self, period_type=None):
        if period_type == "HISTORICAL":
            pt = DWDObservationPeriod.HISTORICAL
        elif period_type == "RECENT":
            pt = DWDObservationPeriod.RECENT
        elif period_type == "NOW":
            pt = DWDObservationPeriod.NOW
        else:
            pt = DWDObservationPeriod.RECENT
        return pt

    def convert_time_resolution(self, time_resolution=None):
        if time_resolution == "MINUTE_1":
            tr = DWDObservationResolution.MINUTE_1
        elif time_resolution == "MINUTE_5":
            tr = DWDObservationResolution.MINUTE_5
        elif time_resolution == "MINUTE_10":
            tr = DWDObservationResolution.MINUTE_10
        elif time_resolution == "MINUTE_15":
            tr = DWDObservationResolution.MINUTE_15
        elif time_resolution == "HOURLY":
            tr = DWDObservationResolution.HOURLY
        elif time_resolution == "SUBDAILY":
            tr = DWDObservationResolution.SUBDAILY
        elif time_resolution == "DAILY":
            tr = DWDObservationResolution.DAILY
        elif time_resolution == "MONTHLY":
            tr = DWDObservationResolution.MONTHLY
        elif time_resolution == "ANNUAL":
            tr = DWDObservationResolution.ANNUAL
        else:
            tr = DWDObservationResolution.MINUTE_10
        return tr

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
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
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
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.logger = self.plugin.logger
        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, time_resolution="MINUTE_10", parameter="PRECIPITATION", period_type="RECENT",
              max_distance_in_km=25, lat=None, lon=None, function=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        if lat is None or lat is '':
            lat = self.plugin._lat
        if lon is None or lon is '':
            lon = self.plugin._lon

        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(), p=self.plugin, time_resolution=time_resolution,
                           max_distance_in_km=max_distance_in_km, parameter=parameter, period_type=period_type,
                           function=function, lat=lat, lon=lon)
