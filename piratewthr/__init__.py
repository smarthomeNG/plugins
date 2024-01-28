#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2023-  Martin Sinn                             m.sinn@gmx.de
# based on darksky plugin:
#  Copyright 2018   René Frieß                    rene.friess(a)gmail.com
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
from collections import OrderedDict
from lib.module import Modules
from lib.model.smartplugin import *

from .webif import WebInterface


class PirateWeather(SmartPlugin):


    PLUGIN_VERSION = "1.2.5"

    # https://api.pirateweather.net/forecast/[apikey]/[latitude],[longitude]
    _base_url = 'https://api.pirateweather.net/forecast/'

    _http_response = {
        500: 'Internal Server Error',
        501: 'Not Implemented',
        502: 'Bad Gateway',
        503: 'Service Unavailable',
        504: 'Internal Server Error',
    }


    def get_http_response(self, code):

        description = self._http_response.get(code, None)
        if description is None:
            if code >= 100 and code < 200:
                description = 'Informational'
            elif code < 300:
                description = 'Success'
            elif code < 400:
                description = 'Redirection'
            elif code < 500:
                description = 'Client Error'
            elif code < 600:
                description = 'Server Error'
            else:
                description = 'Unknown Response'
        description += ' (' + str(code) + ')'
        return description


    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self._key = self.get_parameter_value('key')
        if self.get_parameter_value('latitude') != 0 and self.get_parameter_value('longitude') != 0:
            self._lat = self.get_parameter_value('latitude')
            self._lon = self.get_parameter_value('longitude')
        else:
            self.logger.debug("__init__: latitude and longitude not provided, using shng system values instead.")
            self._lat = self.get_sh().lat
            self._lon = self.get_sh().lon
        self._lang = self.get_parameter_value('lang')
        self._units = self.get_parameter_value('units')
        self._jsonData = {}
        self._session = requests.Session()
        self._cycle = int(self.get_parameter_value('cycle'))
        self._items = {}        # Items that are handled by this plugin

        self.init_webinterface(WebInterface)


    def run(self):
        self.scheduler_add(__name__, self._update_loop, prio=5, cycle=self._cycle, offset=2)
        self.alive = True

    def stop(self):
        self.alive = False


    def _update_loop(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug('Starting update loop for instance {}'.format(self.get_instance_name()))
        if not self.alive:
            return

        self._update()


    def _update(self):
        """
        Updates information on items when it becomes available on the weather service
        """
        forecast = self.get_forecast()
        if forecast is None:
            self.logger.info("Forecast is None! Server did not answer or sent an invalid reply?")
            return
        self._jsonData = forecast
        for s, matchStringItems in self._items.items():
            wrk = forecast
            sp = s.split('/')
            if s == "flags/sources":
                wrk = ', '.join(wrk['flags']['sources'])
            elif s == "alerts" or s == "alerts_string":
                if 'alerts' in wrk:
                    if s == "alerts":
                        wrk = wrk['alerts']
                    else:
                        alerts_string = ''
                        if 'alerts' in wrk:
                            for alert in wrk['alerts']:
                                start_time = datetime.datetime.fromtimestamp(
                                    int(alert['time'])
                                ).strftime('%d.%m.%Y %H:%M')
                                expire_time = datetime.datetime.fromtimestamp(
                                    int(alert['expires'])
                                ).strftime('%d.%m.%Y %H:%M')
                                alerts_string_wrk = "<p><h1>"+alert['title']+" ("+start_time+" - "+expire_time+")</h1>"
                                alerts_string_wrk = alerts_string_wrk + "<span>"+alert['description']+"</span></p>"
                                alerts_string = alerts_string + alerts_string_wrk
                        wrk = alerts_string
                else:
                    if s == "alerts_string":
                        wrk = ''
                    else:
                        wrk = []
            else:
                while True:
                    if (len(sp) == 0) or (wrk is None):
                        break
                    if type(wrk) is list:
                        if self.is_int(sp[0]):
                            if int(sp[0]) < len(wrk):
                                wrk = wrk[int(sp[0])]
                            else:
                                self.logger.error(
                                    "_update: invalid pw_matchstring '{}'; integer too large in matchstring".format(
                                        s))
                                break
                        else:
                            self.logger.error(
                                "_update: invalid pw_matchstring '{}'; integer expected in matchstring".format(
                                    s))
                            break
                    else:
                        wrk = wrk.get(sp[0])
                    if len(sp) == 1:
                        spl = s.split('/')
                        self.logger.debug(
                            "_update: pw_matchstring split len={}, content={} -> '{}'".format(str(len(spl)),
                                                                                              str(spl),
                                                                                              str(wrk)))
                    sp.pop(0)

            # if a value was found, store it to item
            if wrk is not None:
                for sameMatchStringItem in matchStringItems:
                    sameMatchStringItem(wrk, 'piratewthr')
                    self.logger.debug('_update: Value "{0}" written to item {1}'.format(wrk, sameMatchStringItem))

        return


    def get_forecast(self):
        """
        Requests the forecast information at pirateweather.net
        """
        url_to_send = self._build_url()
        self.logger.info(f"get_forecast: url={url_to_send}")
        json_obj = None
        try:
            response = self._session.get(url_to_send)
        except Exception as e:
            self.logger.warning(f"get_forecast: Exception when sending GET request: {e}")
            return
        try:
            json_obj = response.json()
        except Exception as e:
            self.logger.warning(f"get_forecast: Response '{response}' is no valid json format: {e}")
            return
        self.logger.info(f"get_forecast: json response={json_obj}")

        if response.status_code >= 500:
            self.logger.warning(f"api.pirateweather.net: {self.get_http_response(response.status_code)} - Ignoring response.")
            return

        if json_obj['flags']['units'].lower() != self._units.lower():
            # Log data, if receiving data in other format than the requested units
            self.logger.notice(f"get_forecast: url sent={url_to_send}")
            self.logger.notice(f"get_forecast: Ignoring data in other units than requested: {json_obj}")
            return

        # if json_obj['currently']['temperature'] > 45:
        #     # Log data, if receiving data in imperial units
        #     self.logger.notice(f"get_forecast: url sent={url_to_send}")
        #     self.logger.notice(f"get_forecast: Data in imperial units?: {json_obj}")

        daily_data = OrderedDict()
        if not json_obj.get('daily', False):
            self.logger.warning(f"api.pirateweather.net: {self.get_http_response(response.status_code)} - No info for daily values.")
            #return
        else:
            # add icon_visu to daily
            json_obj['daily'].update({'icon_visu': self.map_icon(json_obj['daily']['icon'])})

        if not json_obj.get('hourly', False):
            self.logger.warning(f"api.pirateweather.net: {self.get_http_response(response.status_code)} - No info for hourly values.")
            #return
        else:
            # add icon_visu to hourly
            json_obj['hourly'].update({'icon_visu': self.map_icon(json_obj['hourly']['icon'])})

        if not json_obj.get('currently'):
            self.logger.warning(f"api.pirateweather.net: {self.get_http_response(response.status_code)} - No info for current values. Skipping update for 'currently' values.")
        else:
            date_entry = datetime.datetime.fromtimestamp(json_obj['currently']['time']).strftime('%d.%m.%Y')
            day_entry = datetime.datetime.fromtimestamp(json_obj['currently']['time']).strftime('%A')
            hour_entry = datetime.datetime.fromtimestamp(json_obj['currently']['time']).hour
            json_obj['currently'].update({'date': date_entry, 'weekday': day_entry,
                                          'hour': hour_entry, 'icon_visu':
                                          self.map_icon(json_obj['currently']['icon'])})

        if json_obj.get('daily', False):
            # add icon_visu, date and day to each day
            for day in json_obj['daily'].get('data'):
                date_entry = datetime.datetime.fromtimestamp(day['time']).strftime('%d.%m.%Y')
                day_entry = datetime.datetime.fromtimestamp(day['time']).strftime('%A')
                day.update({'date': date_entry, 'weekday': day_entry, 'icon_visu': self.map_icon(day['icon'])})
                daily_data.update({datetime.datetime.fromtimestamp(day['time']).date(): day})
            json_obj['daily'].update(daily_data)
            json_obj['daily'].pop('data')

        if json_obj.get('hourly', False):
            # add icon_visu, date and day to each hour. Add the hours to the corresponding day as well as map to hour0, hour1, etc.
            for number, hour in enumerate(json_obj['hourly'].get('data')):
                date_entry = datetime.datetime.fromtimestamp(hour['time']).strftime('%d.%m.%Y')
                day_entry = datetime.datetime.fromtimestamp(hour['time']).strftime('%A')
                hour_entry = datetime.datetime.fromtimestamp(hour['time']).hour
                date_key = datetime.datetime.fromtimestamp(hour['time']).date()
                hour.update({'date': date_entry, 'weekday': day_entry, 'hour': hour_entry, 'icon_visu': self.map_icon(hour['icon'])})
                if json_obj['daily'].get(date_key) is None:
                    json_obj['daily'].update({date_key: {}})
                if json_obj['daily'][date_key].get('hours') is None:
                    json_obj['daily'][date_key].update({'hours': {}})
                json_obj['daily'][date_key]['hours'].update(OrderedDict({hour_entry: hour}))
                json_obj['hourly'].update(OrderedDict({'hour{}'.format(number): hour}))
                if json_obj['daily'][date_key].get('precipProbability_mean') is None:
                    json_obj['daily'][date_key].update({'precipProbability_mean': []})
                if json_obj['daily'][date_key].get('precipIntensity_mean') is None:
                    json_obj['daily'][date_key].update({'precipIntensity_mean': []})
                if json_obj['daily'][date_key].get('temperature_mean') is None:
                    json_obj['daily'][date_key].update({'temperature_mean': []})
                json_obj['daily'][date_key]['precipProbability_mean'].append(hour.get('precipProbability'))
                json_obj['daily'][date_key]['precipIntensity_mean'].append(hour.get('precipIntensity'))
                json_obj['daily'][date_key]['temperature_mean'].append(hour.get('temperature'))
            json_obj['hourly'].pop('data')

        if json_obj.get('daily', False):
            # add mean values to each day and replace datetime object by day0, day1, day2, etc.
            i = 0
            # for entry in json_obj['daily']:
            json_keys = list(json_obj['daily'].keys())
            for entry in json_keys:
                if isinstance(entry, datetime.date):
                    try:
                        precip_probability = json_obj['daily'][entry]['precipProbability_mean']
                        json_obj['daily'][entry]['precipProbability_mean'] = round(sum(precip_probability)/len(precip_probability), 2)
                        precip_intensity = json_obj['daily'][entry]['precipIntensity_mean']
                        json_obj['daily'][entry]['precipIntensity_mean'] = round(sum(precip_intensity)/len(precip_intensity), 2)
                        temperature = json_obj['daily'][entry]['temperature_mean']
                        json_obj['daily'][entry]['temperature_mean'] = round(sum(temperature)/len(temperature), 2)
                    except Exception:
                        pass
                    json_obj['daily']['day{}'.format(i)] = json_obj['daily'].pop(entry)
                    i += 1

        return json_obj

    def map_icon(self, icon):
        """
        Maps the icons from pirateweather.net to the icons in SmartVisu

        :param icon icon to map, as string.
        :return SmartVisu icon as string.
        """
        if icon == 'clear-day':
            return 'sun_1'
        elif icon == 'clear-night':
            return 'sun_1'
        elif icon == 'partly-cloudy-day':
            return 'sun_4'
        elif icon == 'partly-cloudy-night':
            return 'sun_4'
        elif icon == 'fog':
            return 'sun_6'
        elif icon == 'rain':
            return 'cloud_8'
        elif icon == 'wind':
            return 'sun_10'
        elif icon == 'snow':
            return 'sun_12'
        elif icon == 'cloudy':
            return 'cloud_4'
        elif icon == 'sleet':
            return 'cloud_11'
        else:
            return 'high'

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the pw_matchstring and adds it to an internal array

        :param item: The item to process.
        """
        pw_matchstring = self.get_iattr_value(item.conf, 'pw_matchstring')
        if pw_matchstring:
            if not pw_matchstring in self._items:
                self._items[pw_matchstring] = []
            self._items[pw_matchstring].append(item)

            self.add_item(item, mapping=pw_matchstring, config_data_dict={})

        return


    def get_items(self):
        return self._items

    def get_json_data(self):
        return self._jsonData

    def get_dumped_json_data(self):

        return json.dumps(self._jsonData, indent=4)

    def _build_url(self, url_type='forecast'):
        """
        Builds a request url
        @param url_type: url type (currently on 'forecast', as historic data are not supported.
        @return: string of the url
        """
        url = ''
        if url_type == 'forecast':
            #url = self._base_forecast_url % (self._key, self._lat, self._lon)
            url = self._base_url + f"{self._key}/{self._lat},{self._lon}"
            parameters = f"?lang={self._lang}"
            if self._units is not None:
                parameters += f"&units={self._units}"
            url += parameters
        else:
            self.logger.error(f"_build_url: Wrong url type specified: {url_type}")
        return url

