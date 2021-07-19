#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2018 René Frieß                      rene.friess(a)gmail.com
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

from jinja2 import Environment, FileSystemLoader
import cherrypy
import logging
import requests
import datetime
import json
import math
import functools
from datetime import datetime, timedelta, timezone
from lib.module import Modules
from lib.model.smartplugin import *
from bin.smarthome import VERSION
from pprint import pformat


class OpenWeatherMap(SmartPlugin):
    PLUGIN_VERSION = "1.8.2"

    _base_url = 'https://api.openweathermap.org/%s'
    _base_img_url = 'https://tile.openweathermap.org/map/%s/%s/%s/%s.png?appid=%s'

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin
        """
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)
        self._key = self.get_parameter_value('key')
        if self.get_parameter_value('latitude') != '' and self.get_parameter_value('longitude') != '' and self.get_parameter_value('altitude') != '':
            self._lat = self.get_parameter_value('latitude')
            self._lon = self.get_parameter_value('longitude')
            self._elev = self.get_parameter_value('altitude')
        else:
            self.logger.debug(
                "__init__: latitude and longitude not provided, using shng system values instead.")
            self._lat = self.get_sh()._lat
            self._lon = self.get_sh()._lon
            self._elev = self.get_sh()._elev
        self._lang = self.get_parameter_value('lang')
        self._units = self.get_parameter_value('units')

        self._data_source_key_weather = 'weather'
        self._data_source_key_forecast = 'forecast'
        self._data_source_key_uvi = 'uvi'
        self._data_source_key_back0day = 'onecall-0'
        self._data_source_key_back1day = 'onecall-1'
        self._data_source_key_back2day = 'onecall-2'
        self._data_source_key_back3day = 'onecall-3'
        self._data_source_key_back4day = 'onecall-4'
        self._data_source_key_onecall = 'onecall'

        self._data_sources = {self._data_source_key_weather:  {'url': '', 'fetched': '', 'data': None},
                              self._data_source_key_forecast: {'url': '', 'fetched': '', 'data': None},
                              self._data_source_key_uvi:      {'url': '', 'fetched': '', 'data': None},
                              self._data_source_key_back0day: {'url': '', 'fetched': '', 'data': None},
                              self._data_source_key_back1day: {'url': '', 'fetched': '', 'data': None},
                              self._data_source_key_back2day: {'url': '', 'fetched': '', 'data': None},
                              self._data_source_key_back3day: {'url': '', 'fetched': '', 'data': None},
                              self._data_source_key_back4day: {'url': '', 'fetched': '', 'data': None},
                              self._data_source_key_onecall:  {'url': '', 'fetched': '', 'data': None}}

        self._soft_fails = ['rain/1h',
                            'rain/3h',
                            'snow/1h',
                            'snow/3h']

        self._session = requests.Session()
        self._cycle = int(self.get_parameter_value('cycle'))
        self._items = {}

        self._request_weather = False
        self._request_forecast = False
        self._request_uvi = False

        # Via one-call timemachine
        self._request_back0day = False
        self._request_back1day = False
        self._request_back2day = False
        self._request_back3day = False
        self._request_back4day = False

        # Via one-call
        self._request_current = False
        self._request_minutely = False
        self._request_hourly = False
        self._request_daily = False
        self._request_alerts = False

        self._origins_weather = ['base', 'clouds', 'cod', 'coord', 'dt', 'id', 'name',
                                 'main/feels_like', 'main/humidity', 'main/pressure', 'main/temp', 'main/temp_max', 'main/temp_min',
                                 'sys/country', 'sys/id', 'sys/sunrise', 'sys/sunset', 'sys/type',
                                 'snow/3h', 'snow/1h', 'rain/3h', 'rain/1h',
                                 'timezone', 'visibility', 'weather', 'wind/deg', 'wind/speed', 'wind/gust']

        self._origins_layer = [
            'clouds_new', 'precipitation_new', 'pressure_new', 'wind_new', 'temp_new']

        self.init_webinterface()

    def run(self):
        self.scheduler_add(__name__, self._update_loop,
                           prio=5, cycle=self._cycle, offset=2)
        self.alive = True

    def stop(self):
        self.alive = False

    def _update_loop(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug('Starting update loop for instance %s' %
                          self.get_instance_name())
        if not self.alive:
            return

        self._update()

    def _download_data(self):
        """
        Downloads data according to items' demands
        """
        self.__query_api_if(self._data_source_key_weather,
                            only_if=self._request_weather)
        self.__query_api_if(self._data_source_key_forecast,
                            only_if=self._request_forecast)
        self.__query_api_if(self._data_source_key_uvi,
                            only_if=self._request_uvi)

        get_onecall = self._request_current or \
            self._request_minutely or \
            self._request_hourly or \
            self._request_daily or \
            self._request_alerts
        self.__query_api_if(self._data_source_key_onecall, only_if=get_onecall)

        self.__query_api_if(self._data_source_key_back0day,
                            only_if=self._request_back0day, delta_t=0)
        self.__query_api_if(self._data_source_key_back1day,
                            only_if=self._request_back1day, delta_t=-1)
        self.__query_api_if(self._data_source_key_back2day,
                            only_if=self._request_back2day, delta_t=-2)
        self.__query_api_if(self._data_source_key_back3day,
                            only_if=self._request_back3day, delta_t=-3)
        self.__query_api_if(self._data_source_key_back4day,
                            only_if=self._request_back4day, delta_t=-4)

    def get_value_with_meta(self, owm_matchstring):
        s = owm_matchstring
        wrk_typ = "WRONG"
        ret_val = None

        if s.startswith('forecast/daily/'):
            ret_val = self.get_daily_forecast(s)
            wrk_typ = "forecast [calculation]"
            return (ret_val, wrk_typ, s)
        elif s.startswith('virtual/'):
            ret_val = self.__get_virtual_value(s[8:])
            wrk_typ = "virtual [calculation]"
            return (ret_val, wrk_typ, s)

        if s.startswith('forecast/'):
            wrk = self._data_sources[self._data_source_key_forecast]['data']
            wrk_typ = self._data_source_key_forecast
            s = s.replace("forecast/", "list/")
        elif s.startswith('uvi_'):
            wrk = self._data_sources[self._data_source_key_uvi]['data']
            wrk_typ = self._data_source_key_uvi
            s = s.replace("uvi_", "")
        elif s.startswith('current/'):
            wrk = self._data_sources[self._data_source_key_onecall]['data']
            wrk_typ = self._data_source_key_onecall
        elif s.startswith('day/-'):
            minus_days = s[5]
            wrk = self._data_sources[f"onecall-{minus_days}"]['data']
            prefix = f"day/-{minus_days}"
            s = s.replace(f"{prefix}/hour/", "hourly/")
            # wierd to have a "current" in historic data :-)
            s = s.replace(f"{prefix}/", "current/")
            wrk_typ = f"onecall-{minus_days}"
        elif s.startswith('day/'):
            wrk = self._data_sources[self._data_source_key_onecall]['data']
            try:
                new_day = int(s[4])
                s = s.replace(s[0:5], 'daily/' + str(new_day))
            except:
                s = s.replace('day/', 'daily/0/')
                self.logger.warning(f"Missing integer after 'day/' assuming 'day/0/' in matchstring {owm_matchstring}")
            wrk_typ = self._data_source_key_onecall
        elif s.startswith('hour/'):
            wrk = self._data_sources[self._data_source_key_onecall]['data']
            try:
                new_day = int(s[5])              
                s = s.replace(s[0:6], 'hourly/' + str(new_day))
            except:
                s = s.replace('hour/', 'hourly/0/')
                self.logger.warning(f"Missing integer after 'hour/' assuming 'hour/0/' in matchstring {owm_matchstring}")  
            wrk_typ = self._data_source_key_onecall
        else:
            wrk_typ = self._data_source_key_weather
            wrk = self._data_sources[self._data_source_key_weather]['data']

        try:
            if (s.startswith("current/") or s.startswith("daily/")) and s.endswith('/eto'):
                s = s.replace("current/", "day/0/")
                s = s.replace("daily/", "day/")
                ret_val = self._calculate_eto(s)
                wrk_typ = "onecall [eto-calculation]"
            else:
                ret_val = self._get_val_from_dict(s, wrk)
        except Exception as e:
            ret_val = e

        return (ret_val, wrk_typ, s)

    def get_value(self, owm_matchstring):
        ret_val, wrk_typ, s = self.get_value_with_meta(owm_matchstring)
        return ret_val

    def _update(self):
        """
        Updates information on diverse items
        """
        self._download_data()

        for item_path, owm_item_data in self._items.items():
            owm_matchstring, item = owm_item_data
            if owm_matchstring in self._origins_layer:
                ret_val = self._build_url('owm_layer', item)
                wrk_typ = 'owm_layer'
                item(ret_val, self.get_shortname(),
                     f"{wrk_typ} // {owm_matchstring}")
                self.logger.debug(
                    "_update: -OK- : owm-string: %s as layer for item %s" % (owm_matchstring, item))
            else:
                try:
                    ret_val, wrk_typ, changed_match_string = self.get_value_with_meta(
                        owm_matchstring)
                    if isinstance(ret_val, Exception):
                        self.logger.error(
                            "_update: ERROR: owm-string: %s --> %s from wrk=%s, Error: %s for item %s" % (owm_matchstring, changed_match_string, wrk_typ, ret_val, item))
                    else:
                        item(ret_val, self.get_shortname(),
                             f"{wrk_typ} // {changed_match_string}")
                        self.logger.debug(
                            "_update: -OK- : owm-string: %s --> %s from wrk=%s for item %s" % (owm_matchstring, changed_match_string, wrk_typ, item))
                except Exception as e:
                    self.logger.error(
                        "_update: EXCPT: owm-string: %s, Error: %s, for item %s" % (owm_matchstring, e, item))

        return

    def _calculate_eto(self, s):
        """
        Origin: https://github.com/MTry/homebridge-smart-irrigation
        Based on: https://edis.ifas.ufl.edu/pdffiles/ae/ae45900.pdf
                  http://www.fao.org/3/X0490E/x0490e00.htm#Contents


        TODO: solar_rad values are kWh/m2 - the uvi values seem to coincidentally fit the scale.
        """
        self.logger.debug("_calculate_eto: for %s" % (s))

        climate_sunrise = datetime.utcfromtimestamp(
            int(self.get_value(s.replace('/eto', "/sunrise"))))
        climate_humidity = self.get_value(s.replace('/eto', "/humidity"))
        climate_pressure = self.get_value(s.replace('/eto', "/pressure"))
        climate_min = self.get_value(s.replace('/eto', "/temp/min"))
        climate_max = self.get_value(s.replace('/eto', "/temp/max"))
        climate_speed = self.get_value(s.replace('/eto', "/wind_speed"))
        solarRad = self.get_value(s.replace('/eto', "/uvi"))
        alt = float(self._elev)
        lat = float(self._lat)

        tMean = (climate_max + climate_min) / 2
        rS = solarRad * 3.6
        U_2 = climate_speed * 0.748
        slopeSvpc = 4098 * (0.6108 * math.exp((17.27 * tMean) /
                            (tMean + 237.3))) / math.pow((tMean + 237.3), 2)
        pA = climate_pressure / 10
        pSc = pA * 0.000665
        DT = slopeSvpc / (slopeSvpc + (pSc * (1 + (0.34 * U_2))))
        PT = pSc / (slopeSvpc + (pSc * (1 + (0.34 * U_2))))
        TT = U_2 * (900 / (tMean + 273))
        eTmax = 0.6108 * math.exp(17.27 * climate_max / (climate_max + 237.3))
        eTmin = 0.6108 * math.exp(17.27 * climate_min / (climate_min + 237.3))
        eS = (eTmax + eTmin) / 2
        eA = climate_humidity * eS / 100

        DoY = climate_sunrise.timetuple().tm_yday
        dR = 1 + 0.033 * math.cos(2 * math.pi * DoY / 365)
        sD = 0.409 * math.sin((2 * math.pi * DoY / 365) - 1.39)
        lRad = lat * math.pi / 180
        sunsetHA = math.acos(-(math.tan(sD) * math.tan(lRad)))
        Ra = (1440 / math.pi) * 0.082 * dR * ((sunsetHA * math.sin(lRad) *
                                               math.sin(sD)) + (math.cos(lRad) * math.cos(sD) * math.sin(sunsetHA)))
        Rso = Ra * (0.75 + (2 * alt / 100000))
        Rns = rS * (1 - 0.23)
        Rnl = 4.903 * math.pow(10, -9) * (math.pow((273.16 + climate_max),
                                                   4) + math.pow((273.16 + climate_min), 4)) / 2
        Rnl = Rnl * (0.34 - (0.14 * math.sqrt(eA)))
        Rnl = Rnl * ((1.35 * rS / Rso) - 0.35)
        rN = Rns - Rnl
        rNg = 0.408 * rN
        etRad = DT * rNg
        etWind = PT * TT * (eS - eA)
        eTo = etRad + etWind

        self.logger.debug("_calculate_eto: %s, eTo: %s" % (s, eTo))
        return eTo

    def __get_virtual_value(self, virtual_ms):
        pool = []
        data_field = virtual_ms[12:]
        operation = virtual_ms[8:11]
        if virtual_ms.startswith("next24h/"):
            for hr in range(0, 24):
                pool.append(self.get_value(f'hour/{hr}/{data_field}'))
        elif virtual_ms.startswith("next12h/"):
            for hr in range(0, 12):
                pool.append(self.get_value(f'hour/{hr}/{data_field}'))
        elif virtual_ms.startswith("past24h/"):
            for hr in range(0, 24):
                pool.append(self.get_value(f'day/-1/hour/{hr}/{data_field}'))
            for hr in range(0, 24):
                try:
                    val = self.get_value(f'day/-0/hour/{hr}/{data_field}')
                    if not isinstance(val, Exception):
                        pool.append(val)
                except:
                    pass
            pool = pool[-24:]
        elif virtual_ms.startswith("past12h/"):
            for hr in range(12, 24):
                pool.append(self.get_value(f'day/-1/hour/{hr}/{data_field}'))
            for hr in range(0, 24):
                try:
                    val = self.get_value(f'day/-0/hour/{hr}/{data_field}')
                    if not isinstance(val, Exception):
                        pool.append(val)
                except:
                    pass
            pool = pool[-12:]

        self.logger.debug(f"{virtual_ms} / Pool: {pformat(pool)}")

        if operation == "max":
            return max(pool)
        elif operation == "min":
            return min(pool)
        elif operation == "avg":
            return round(functools.reduce(
                lambda x, y: x + y, pool) / len(pool), 2)
        elif operation == "sum":
            return round(functools.reduce(
                lambda x, y: x + y, pool), 2)
        else:
            return f"Unknown operation '{operation}' in match_string '{virtual_ms}'"

    def _get_val_from_dict(self, s, wrk):
        """
        Uses string s as a path to navigate to the requested value in dict wrk.
        """
        successful_path = []
        last_popped = None
        sp = s.split('/')
        while True:
            if (len(sp) == 0) or (wrk is None):
                if wrk is None:
                    if f"{last_popped}/{'/'.join(sp)}" in self._soft_fails:
                        wrk = 0
                        self.logger.debug(
                            f"No defined value for '{s}', missing '{last_popped}/{'/'.join(sp)}', defaulting to 0")
                    else:
                        raise Exception(
                            f"Missing child '{last_popped}/{'/'.join(sp)}' after '{'/'.join(successful_path)}'")
                break

            if type(wrk) is list:
                if self.is_int(sp[0]):
                    if int(sp[0]) < len(wrk):
                        wrk = wrk[int(sp[0])]
                    else:
                        raise Exception(
                            f"Integer index ({int(sp[0])}) out of range after '{'/'.join(successful_path)}'")
                else:
                    raise Exception(
                        f"Integer expected in matchstring after '{'/'.join(successful_path)}/{last_popped}'")
            else:
                if type(wrk) is not dict:
                    self.logger.error("s=%s wrk=%s type(wrk)=%s" %
                                      (s, wrk, type(wrk)))
                wrk = wrk.get(sp[0])

            if last_popped is not None:
                successful_path.append(last_popped)
            last_popped = sp.pop(0)
        return wrk

    def get_daily_forecast(self, s):
        """
        Calculates daily forecast from (free) 3-hours data.
        This builds the average/min/max of all available 3-hour entries that match the
        requested period (1, 2, ..., 5 days in the future).
        Uses local time to determine which entries to include/exclude.
        """
        s = s.replace("forecast/daily/", "")
        forecast = self._data_sources[self._data_source_key_forecast]['data']
        if forecast is None:
            self.logger.error(
                "get_daily_forecast: forecast is None")
            return None
        datetime_now = datetime.now()
        date_requested = datetime(
            datetime_now.year, datetime_now.month, datetime_now.day)
        sp = s.split('/')
        if self.is_int(sp[0]):
            days_in_future = int(sp[0]) + 1
            date_requested = date_requested + timedelta(days=days_in_future)
            sp.pop(0)
        else:
            self.logger.error(
                "get_daily_forecast: invalid owm_matchstring '{}'; integer expected after forecast/daily/ matchstring".format(
                    s))
            return None

        too_far = date_requested + timedelta(days=1)
        wrk = []
        if forecast is not None:
            forecast_list = forecast.get('list')
            if forecast_list is not None:
                for entry in forecast_list:
                    dt = int(entry.get('dt'))
                    if dt >= int(too_far.timestamp()):
                        break
                    if dt >= int(date_requested.timestamp()):
                        val = self._get_val_from_dict("/".join(sp), entry)
                        if isinstance(val, float) or isinstance(val, int):
                            wrk.append(val)
                        elif val is None:
                            self.logger.error(
                                "get_daily_forecast: found None value while calculating daily forecast for matchstring '{}'.".format(s))
                            return 0
                        else:
                            self.logger.error(
                                "get_daily_forecast: found unknown value while calculating daily forecast for matchstring '{}'; daily forecast only supported for int and float.".format(
                                    s))
                            return 0
            else:
                self.logger.error(
                    "get_daily_forecast: forecast.get('list') is None.")
        else:
            self.logger.error("get_daily_forecast: forecast data is None.")
            return 0

        result = 0
        if "max" in sp[len(sp) - 1]:
            result = max(wrk)
        elif "min" in sp[len(sp) - 1]:
            result = min(wrk)
        else:  # average
            result = round(functools.reduce(
                lambda x, y: x + y, wrk) / len(wrk), 2)
        return result

    def __query_api_if(self, data_source_key, only_if, delta_t=0):
        if only_if:
            self.__query_api(data_source_key, delta_t)
        else:
            self._data_sources[data_source_key]['data'] = "Not requested by any item!"

    def __query_api(self, data_source_key, delta_t=0):
        """
        Requests the weather information at openweathermap.com
        """
        try:
            url = self._build_url(data_source_key, delta_t=delta_t)
            response = self._session.get(url)
        except Exception as e:
            self.logger.error(
                "__query_api: Exception when sending GET request for data_source_key '%s': %s" % (data_source_key, str(e)))
            return
        json_obj = response.json()

        self._data_sources[data_source_key]['url'] = url
        self._data_sources[data_source_key]['fetched'] = datetime.now()
        self._data_sources[data_source_key]['data'] = json_obj

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the owm_matchstring and adds it to an internal array

        :param item: The item to process.
        """
        owm_ms = self.get_iattr_value(item.conf, 'owm_matchstring')
        if owm_ms:
            self._items[item.id()] = (owm_ms, item)

            if owm_ms in self._origins_weather:
                self._request_weather = True
            elif owm_ms.startswith('uvi_'):
                self._request_uvi = True
            elif owm_ms.startswith('forecast'):
                self._request_forecast = True
            elif owm_ms.startswith('current'):
                self._request_current = True
            elif owm_ms.startswith('minute'):
                self._request_minutely = True
            elif owm_ms.startswith('hour'):
                self._request_hourly = True
            elif owm_ms.startswith('day/-0'):
                self._request_back0day = True
            elif owm_ms.startswith('day/-1'):
                self._request_back1day = True
            elif owm_ms.startswith('day/-2'):
                self._request_back2day = True
            elif owm_ms.startswith('day/-3'):
                self._request_back3day = True
            elif owm_ms.startswith('day/-4'):
                self._request_back4day = True
            elif owm_ms.startswith('day'):
                self._request_daily = True
            elif owm_ms.startswith('alert'):
                self._request_alerts = True
            elif owm_ms.startswith('virtual/past24h/'):
                self._request_back0day = True
                self._request_back1day = True
            elif owm_ms.startswith('virtual/next24h/'):
                self._request_hourly = True

    def __get_timestamp_for_delta_days(self, delta_t):
        datetime_now = datetime.now(None)
        date_requested = datetime(
            datetime_now.year, datetime_now.month, datetime_now.day, tzinfo=timezone.utc)
        date_requested = date_requested + timedelta(days=delta_t)
        return date_requested.astimezone(timezone.utc).timestamp()

    def __get_map_tile_from_geo_coord(self, lat_deg, lon_deg, zoom):
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        xtile = int((lon_deg + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (xtile, ytile)

    def _build_url(self, url_type=None, item=None, delta_t=0):
        """
        Builds a request url
        @param url_type: url type (currently on 'forecast', as historic data are not supported.
        @return: string of the url
        """
        url = ''
        if url_type is None or url_type == self._data_source_key_weather:
            url = self._base_url % 'data/2.5/weather'
            parameters = "?lat=%s&lon=%s&appid=%s&lang=%s&units=%s" % (self._lat, self._lon, self._key, self._lang,
                                                                       self._units)
            url = '%s%s' % (url, parameters)
        elif url_type == self._data_source_key_forecast:
            url = self._base_url % 'data/2.5/forecast'
            parameters = "?lat=%s&lon=%s&appid=%s&lang=%s&units=%s" % (self._lat, self._lon, self._key, self._lang,
                                                                       self._units)
            url = '%s%s' % (url, parameters)
        elif url_type == self._data_source_key_uvi:
            url = self._base_url % 'data/2.5/uvi'
            parameters = "?lat=%s&lon=%s&appid=%s&lang=%s&units=%s" % (self._lat, self._lon, self._key, self._lang,
                                                                       self._units)
            url = '%s%s' % (url, parameters)
        elif url_type == self._data_source_key_onecall:
            url = self._base_url % 'data/2.5/onecall'
            excluded = []
            if not self._request_current:
                excluded.append("current")
            if not self._request_minutely:
                excluded.append("minutely")
            if not self._request_hourly:
                excluded.append("hourly")
            if not self._request_daily:
                excluded.append("daily")
            if not self._request_alerts:
                excluded.append("alerts")
            exclude = ",".join(excluded)
            parameters = "?lat=%s&lon=%s&exclude=%s&appid=%s&lang=%s&units=%s" % (self._lat, self._lon, exclude,
                                                                                  self._key, self._lang, self._units)
            url = '%s%s' % (url, parameters)
            self.logger.debug("_build_url: onecall URL: %s" % url)
        elif url_type.startswith('onecall-'):
            url = self._base_url % 'data/2.5/onecall/timemachine'
            parameters = "?lat=%s&lon=%s&dt=%i&appid=%s&lang=%s&units=%s" % (self._lat, self._lon, self.__get_timestamp_for_delta_days(delta_t),
                                                                             self._key, self._lang, self._units)
            url = '%s%s' % (url, parameters)
            self.logger.debug("_build_url: yesterday URL: %s" % url)
        elif url_type == 'owm_layer':
            if self.has_iattr(item.conf, 'owm_matchstring'):
                layer = self.get_iattr_value(item.conf, 'owm_matchstring')
            elif 'owm_matchstring' in item.conf:
                layer = item.conf['owm_matchstring']

            if self.has_iattr(item.conf, 'owm_coord_z'):
                z = self.get_iattr_value(item.conf, 'owm_coord_z')
            elif 'z' in item.conf:
                z = item.conf['owm_coord_z']
            else:
                self.logger.warning(
                    "_build_url: owm_coord_z attribute not set for item, setting default 7")
                z = 7

            x_fallback, y_fallback = self.__get_map_tile_from_geo_coord(
                float(self._lat), float(self._lon), z)

            if self.has_iattr(item.conf, 'owm_coord_x'):
                x = self.get_iattr_value(item.conf, 'owm_coord_x')
            elif 'owm_coord_x' in item.conf:
                x = item.conf['owm_coord_x']
            else:
                x = x_fallback
                self.logger.warning(
                    f"_build_url: owm_coord_x attribute not set for item, setting default as per plugin-coordinates: {x}")

            if self.has_iattr(item.conf, 'owm_coord_y'):
                y = self.get_iattr_value(item.conf, 'owm_coord_y')
            elif 'owm_coord_y' in item.conf:
                y = item.conf['y']
            else:
                y = y_fallback
                self.logger.warning(
                    f"_build_url: owm_coord_y attribute not set for item, setting default as per plugin-coordinates: {y}")

            url = self._base_img_url % (layer, z, x, y, self._key)
        else:
            self.logger.error(
                '_build_url: Wrong url type specified: %s' % url_type)
        return url

    def get_items(self):
        return self._items

    def get_json_data_for_webif(self, data_source_key):
        src = self._data_sources[data_source_key]['data']
        return json.dumps(src, indent=4)

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
            self.logger.error(
                "Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
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
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """

        tmpl = self.tplenv.get_template('index.html')

        json_data_weather = self.plugin.get_json_data_for_webif(
            self.plugin._data_source_key_weather)
        json_data_forecast = self.plugin.get_json_data_for_webif(
            self.plugin._data_source_key_forecast)
        json_data_uvi = self.plugin.get_json_data_for_webif(
            self.plugin._data_source_key_uvi)
        json_data_onecall = self.plugin.get_json_data_for_webif(
            self.plugin._data_source_key_onecall)
        json_data_back0day = self.plugin.get_json_data_for_webif(
            self.plugin._data_source_key_back0day)
        json_data_back1day = self.plugin.get_json_data_for_webif(
            self.plugin._data_source_key_back1day)
        json_data_back2day = self.plugin.get_json_data_for_webif(
            self.plugin._data_source_key_back2day)
        json_data_back3day = self.plugin.get_json_data_for_webif(
            self.plugin._data_source_key_back3day)
        json_data_back4day = self.plugin.get_json_data_for_webif(
            self.plugin._data_source_key_back4day)

        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(), p=self.plugin,
                           json_data_weather=json_data_weather,
                           json_data_forecast=json_data_forecast,
                           json_data_uvi=json_data_uvi,
                           json_data_onecall=json_data_onecall,
                           json_data_back0day=json_data_back0day,
                           json_data_back1day=json_data_back1day,
                           json_data_back2day=json_data_back2day,
                           json_data_back3day=json_data_back3day,
                           json_data_back4day=json_data_back4day)
