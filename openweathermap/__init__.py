#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2018 René Frieß                      rene.friess(a)gmail.com
#  Updated in 2021 by Jens Höppner to make use of one-call API
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
import math
import functools
from .webif import WebInterface
from datetime import datetime, timedelta, timezone
from lib.model.smartplugin import *
from bin.smarthome import VERSION
from pprint import pformat


class OpenWeatherMapNoValueHardException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class OpenWeatherMapNoValueSoftException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class OpenWeatherMap(SmartPlugin):
    PLUGIN_VERSION = "1.8.3"

    _base_url = 'https://api.openweathermap.org/%s'
    _base_img_url = 'https://tile.openweathermap.org/map/%s/%s/%s/%s.png?appid=%s'

    # source for german descriptions https://www.smarthomeng.de/vom-winde-verweht
    _beaufort_descriptions_de = ["Windstille",
                                 "leiser Zug",
                                 "leichte Brise",
                                 "schwacher Wind",
                                 "mäßiger Wind",
                                 "frischer Wind",
                                 "starker Wind",
                                 "steifer Wind",
                                 "stürmischer Wind",
                                 "Sturm",
                                 "schwerer Sturm",
                                 "orkanartiger Sturm",
                                 "Orkan"]
    # source for english descriptions https://simple.wikipedia.org/wiki/Beaufort_scale
    _beaufort_descriptions_en = ["Calm",
                                 "Light air",
                                 "Light breeze",
                                 "Gentle breeze",
                                 "Moderate breeze",
                                 "Fresh breeze",
                                 "Strong breeze",
                                 "High wind",
                                 "Fresh Gale",
                                 "Strong Gale",
                                 "Storm",
                                 "Violent storm",
                                 "Hurricane-force"]

    _placebo_alarm = {'sender_name': 'Placebo', 'event': 'None',
                      'start': 1609455600, 'end': 1924988400,
                      'description': 'No Alarm', 'tags': []}

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

        softfail_mode_precipitation = self.get_parameter_value('softfail_precipitation')
        softfail_mode_wind_gust = self.get_parameter_value('softfail_wind_gust')

        self._soft_fails = {
            "rain/1h": softfail_mode_precipitation,
            "rain/3h": softfail_mode_precipitation,
            "snow/1h": softfail_mode_precipitation,
            "snow/3h": softfail_mode_precipitation,
            "rain/": softfail_mode_precipitation,
            "snow/": softfail_mode_precipitation,
            "wind_gust/": softfail_mode_wind_gust
        }

        self._data_source_key_weather = 'weather'
        self._data_source_key_forecast = 'forecast'
        self._data_source_key_uvi = 'uvi'
        self._data_source_key_back0day = 'onecall-0'
        self._data_source_key_back1day = 'onecall-1'
        self._data_source_key_back2day = 'onecall-2'
        self._data_source_key_back3day = 'onecall-3'
        self._data_source_key_back4day = 'onecall-4'
        self._data_source_key_onecall = 'onecall'

        self._data_source_key_airpollution_current = 'airpollution_current'
        self._data_source_key_airpollution_forecast = 'airpollution_forecast'
        self._data_source_key_airpollution_back1day = 'airpollution-1'
        self._data_source_key_airpollution_back2day = 'airpollution-2'
        self._data_source_key_airpollution_back3day = 'airpollution-3'
        self._data_source_key_airpollution_back4day = 'airpollution-4'

        self._data_sources = {self._data_source_key_weather:  {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_forecast: {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_uvi:      {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_back0day: {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_back1day: {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_back2day: {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_back3day: {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_back4day: {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_onecall:  {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_airpollution_current:  {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_airpollution_forecast:  {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_airpollution_back1day:  {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_airpollution_back2day:  {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_airpollution_back3day:  {'url': '', 'fetched': '', 'data': 'Not downloaded!'},
                              self._data_source_key_airpollution_back4day:  {'url': '', 'fetched': '', 'data': 'Not downloaded!'}}

        self._session = requests.Session()
        self._cycle = int(self.get_parameter_value('cycle'))
        self._items = {}
        self._raw_items = {}

        self._request_weather = False
        self._request_forecast = False
        self._request_uvi = False

        self._request_airpollution_current = False
        self._request_airpollution_forecast = False
        self._request_airpollution_back1day = False
        self._request_airpollution_back2day = False
        self._request_airpollution_back3day = False
        self._request_airpollution_back4day = False

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

        self._forced_download_happened = False

        self._origins_onecall = ['lat', 'lon',
                                 'timezone', 'timezone_offset', 'alerts']

        self._origins_weather = ['base', 'clouds', 'cod', 'coord', 'dt', 'id', 'name',
                                 'main/feels_like', 'main/humidity', 'main/pressure', 'main/temp', 'main/temp_max', 'main/temp_min',
                                 'sys/country', 'sys/id', 'sys/sunrise', 'sys/sunset', 'sys/type',
                                 'snow/3h', 'snow/1h', 'rain/3h', 'rain/1h',
                                 'timezone', 'visibility', 'weather', 'wind/deg', 'wind/speed', 'wind/gust']

        self._origins_layer = [
            'clouds_new', 'precipitation_new', 'pressure_new', 'wind_new', 'temp_new']

        if not self.init_webinterface(WebInterface):
            self.logger.error("Unable to start Webinterface")
            self._init_complete = False
        else:
            self.logger.debug("Init complete")

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

    def force_download_all_data(self):
        """
        Downloads data according to items' demands
        """
        self.__query_api_if(self._data_source_key_weather, force=True)
        self.__query_api_if(self._data_source_key_forecast, force=True)
        self.__query_api_if(self._data_source_key_uvi, force=True)
        self.__query_api_if(self._data_source_key_airpollution_current, force=True)
        self.__query_api_if(self._data_source_key_airpollution_forecast, force=True)

        self.__query_api_if(self._data_source_key_airpollution_back1day, force=True, delta_t=-1)
        self.__query_api_if(self._data_source_key_airpollution_back2day, force=True, delta_t=-2)
        self.__query_api_if(self._data_source_key_airpollution_back3day, force=True, delta_t=-3)
        self.__query_api_if(self._data_source_key_airpollution_back4day, force=True, delta_t=-4)

        self.__query_api_if(self._data_source_key_onecall, force=True)

        self.__query_api_if(self._data_source_key_back0day,force=True, delta_t=0)
        self.__query_api_if(self._data_source_key_back1day, force=True, delta_t=-1)
        self.__query_api_if(self._data_source_key_back2day, force=True, delta_t=-2)
        self.__query_api_if(self._data_source_key_back3day, force=True, delta_t=-3)
        self.__query_api_if(self._data_source_key_back4day, force=True, delta_t=-4)

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
        self.__query_api_if(self._data_source_key_airpollution_current,
                            only_if=self._request_airpollution_current)
        self.__query_api_if(self._data_source_key_airpollution_forecast,
                            only_if=self._request_airpollution_forecast)

        self.__query_api_if(self._data_source_key_airpollution_back1day,
                            only_if=self._request_airpollution_back1day, delta_t=-1)
        self.__query_api_if(self._data_source_key_airpollution_back2day,
                            only_if=self._request_airpollution_back2day, delta_t=-2)
        self.__query_api_if(self._data_source_key_airpollution_back3day,
                            only_if=self._request_airpollution_back3day, delta_t=-3)
        self.__query_api_if(self._data_source_key_airpollution_back4day,
                            only_if=self._request_airpollution_back4day, delta_t=-4)

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

    def get_value_with_meta(self, owm_matchstring, correlation_hint=""):
        s = owm_matchstring
        wrk_typ = "WRONG"
        ret_val = None
        was_ok = True

        if s.startswith('forecast/daily/'):
            ret_val = self.get_daily_forecast(s)
            wrk_typ = "forecast [calculation]"
            return (ret_val, wrk_typ, s, True)
        elif s.startswith('virtual/'):
            ret_val = self.__get_virtual_value(s[8:], correlation_hint)
            wrk_typ = "virtual [calculation]"
            return (ret_val, wrk_typ, s, True)

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
        elif s.startswith('airpollution/forecast/'):
            wrk = self._data_sources[self._data_source_key_airpollution_forecast]['data']
            prefix = f"airpollution/forecast/"
            s = s.replace(prefix, "list/")
            wrk_typ = self._data_source_key_airpollution_forecast
        elif s.startswith('airpollution/day/-'):
            minus_days = s[18]
            wrk = self._data_sources[f"airpollution-{minus_days}"]['data']
            prefix = f"airpollution/day/-{minus_days}"
            s = s.replace(f"{prefix}/hour/", "list/")
            wrk_typ = f"airpollution-{minus_days}"
        elif s.startswith('airpollution/hour/'):
            wrk = self._data_sources[self._data_source_key_airpollution_forecast]['data']
            prefix = f"airpollution/hour/"
            s = s.replace(prefix, "list/")
            wrk_typ = self._data_source_key_airpollution_forecast
        elif s.startswith('airpollution/'):
            wrk = self._data_sources[self._data_source_key_airpollution_current]['data']
            s = s.replace("airpollution/", "list/0/")
            wrk_typ = self._data_source_key_airpollution_current
        elif s.startswith('alerts'):
            wrk = self._data_sources[self._data_source_key_onecall]['data']
            if "alerts" not in wrk:
                wrk.update({'alerts': [self._placebo_alarm]})
            wrk_typ = self._data_source_key_onecall
        elif s in self._origins_onecall:
            wrk = self._data_sources[self._data_source_key_onecall]['data']
            wrk_typ = self._data_source_key_onecall
        elif s.startswith('day/-'):
            minus_days = s[5]
            wrk = self._data_sources[f"onecall-{minus_days}"]['data']
            prefix = f"day/-{minus_days}"
            s = s.replace(f"{prefix}/hour/", "hourly/")
            # wierd to have a "current" in historic data :-)
            if not s.endswith('/eto'):
                s = s.replace(f"{prefix}/", "current/")
            wrk_typ = f"onecall-{minus_days}"
        elif s.startswith('day/'):
            wrk = self._data_sources[self._data_source_key_onecall]['data']
            try:
                new_day = int(s[4])
                s = s.replace(s[0:5], 'daily/' + str(new_day))
            except:
                s = s.replace('day/', 'daily/0/')
                was_ok = False
                self.logger.warning(
                    f"{correlation_hint}Missing integer after 'day/' assuming 'day/0/' in matchstring {owm_matchstring}")
            wrk_typ = self._data_source_key_onecall
        elif s.startswith('hour/'):
            wrk = self._data_sources[self._data_source_key_onecall]['data']
            try:
                new_day = int(s[5])
                s = s.replace(s[0:6], 'hourly/' + str(new_day))
            except:
                s = s.replace('hour/', 'hourly/0/')
                was_ok = False
                self.logger.warning(
                    f"{correlation_hint}Missing integer after 'hour/' assuming 'hour/0/' in matchstring {owm_matchstring}")
            wrk_typ = self._data_source_key_onecall
        else:
            wrk_typ = self._data_source_key_weather
            wrk = self._data_sources[self._data_source_key_weather]['data']

        try:
            if (s.startswith("current/") or s.startswith("daily/") or s.startswith("day/")) and s.endswith('/eto'):
                s = s.replace("current/", "day/0/")
                s = s.replace("daily/", "day/")
                ret_val = self.__calculate_eto(s, correlation_hint)
                wrk_typ = "onecall [eto-calculation]"
            elif (s.startswith("current/") or s.startswith("daily/") or s.startswith("day/") or s.startswith("hour/")) and (s.endswith('/wind_speed/beaufort') or s.endswith('/wind_speed/description')):
                wrk_typ = "onecall [bft-calculation]"
                mps_string = s.replace('/wind_speed/beaufort', '/wind_speed')
                mps_string = mps_string.replace(
                    '/wind_speed/description', '/wind_speed')
                wind_mps, updated_s = self.__get_val_from_dict(
                    mps_string, wrk, correlation_hint, owm_matchstring)
                bft_val = self.get_beaufort_number(wind_mps)
                if s.endswith('/beaufort'):
                    ret_val = bft_val
                elif s.endswith('/description'):
                    ret_val = self.get_beaufort_description(bft_val)
                else:
                    raise Exception(f"Cannot make sense of {s}")
                s = updated_s
            else:
                ret_val, s = self.__get_val_from_dict(s, wrk, correlation_hint, owm_matchstring)
        except Exception as e:
            was_ok = False
            ret_val = e

        return (ret_val, wrk_typ, s, was_ok)

    def get_value(self, owm_matchstring, correlation_hint=""):
        ret_val, _, _, _ = self.get_value_with_meta(
            owm_matchstring, correlation_hint)
        return ret_val

    def get_value_or_raise(self, owm_matchstring, correlation_hint=""):
        ret_val, _, _, _ = self.get_value_with_meta(
            owm_matchstring, correlation_hint)
        if isinstance(ret_val, Exception):
            raise ret_val
        return ret_val

    def _update(self):
        """
        Updates information on diverse items
        """
        self._download_data()

        for item_path, owm_item_data in self._raw_items.items():
            data_source_key, item = owm_item_data
            raw = json.dumps(self._data_sources[data_source_key]['data'], indent=4)
            item(raw, self.get_shortname(), f"raw // {data_source_key}")
            pass

        for item_path, owm_item_data in self._items.items():
            owm_matchstring, item = owm_item_data
            if owm_matchstring in self._origins_layer:
                ret_val = self.__build_url('owm_layer', item)
                wrk_typ = 'owm_layer'
                item(ret_val, self.get_shortname(),
                     f"{wrk_typ} // {owm_matchstring}")
                self.logger.debug(
                    "%s OK: owm-string: %s as layer" % (item, owm_matchstring))
            else:
                try:
                    ret_val, wrk_typ, changed_match_string, was_ok = self.get_value_with_meta(
                        owm_matchstring, f"{item_path} ")

                    if ret_val is None:
                        return
                    elif isinstance(ret_val, OpenWeatherMapNoValueSoftException):
                        self.logger.info(
                            "%s INFO: owm-string: %s --> %s from wrk=%s, Info: %s" % (item, owm_matchstring, changed_match_string, wrk_typ, ret_val))
                    elif isinstance(ret_val, Exception):
                        self.logger.error(
                            "%s ERROR: owm-string: %s --> %s from wrk=%s, Error: %s" % (item, owm_matchstring, changed_match_string, wrk_typ, ret_val))
                    else:
                        item(ret_val, self.get_shortname(),
                             f"{wrk_typ} // {changed_match_string}")
                        if was_ok:
                            self.logger.debug(
                                "%s OK: owm-string: %s --> %s from wrk=%s" % (item, owm_matchstring, changed_match_string, wrk_typ))
                        else:
                            self.logger.warning(
                                "%s OK, FIXED: owm-string: %s --> %s from wrk=%s" % (item, owm_matchstring, changed_match_string, wrk_typ))
                except Exception as e:
                    self.logger.error(
                        "%s FATAL: owm-string: %s, Error: %s" % (item, owm_matchstring, e))

        return

    def __calculate_eto(self, s, correlation_hint):
        """
        Origin: https://github.com/MTry/homebridge-smart-irrigation
        Based on: https://edis.ifas.ufl.edu/pdffiles/ae/ae45900.pdf
                  http://www.fao.org/3/X0490E/x0490e00.htm#Contents

        TODO: solar_rad values are kWh/m2 - the uvi values seem to coincidentally fit the scale.
        """
        self.logger.debug("%s _calculate_eto: for %s" %
                          ((correlation_hint, s)))
        sunrise_value = self.get_value_or_raise(
            s.replace('/eto', "/sunrise"), correlation_hint)
        climate_sunrise = datetime.utcfromtimestamp(int(sunrise_value))
        climate_humidity = self.get_value_or_raise(
            s.replace('/eto', "/humidity"), correlation_hint)
        climate_pressure = self.get_value_or_raise(
            s.replace('/eto', "/pressure"), correlation_hint)
        climate_min = self.get_value_or_raise(
            s.replace('/eto', "/temp" if s.startswith('day/-') else "/temp/min"), correlation_hint)
        climate_max = self.get_value_or_raise(
            s.replace('/eto', "/temp" if s.startswith('day/-') else "/temp/max"), correlation_hint)
        climate_speed = self.get_value_or_raise(
            s.replace('/eto', "/wind_speed"), correlation_hint)
        solarRad = self.get_value_or_raise(
            s.replace('/eto', "/uvi"), correlation_hint)
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

        self.logger.debug("%s _calculate_eto: %s, eTo: %s" %
                          (correlation_hint, s, eTo))
        return eTo

    def __tokenize_matchstring(self, virtual_ms):
        tokens = virtual_ms.split('/')
        if tokens[0].startswith("next"):
            mode = 'next'
        elif tokens[0].startswith("past"):
            mode = 'past'
        numbers = ''.join(filter(str.isdigit, tokens[0]))
        operation = tokens[1]
        unit = tokens[0].replace(f'{mode}{numbers}', '')
        data_field = '/'.join(tokens[2:])

        self.logger.debug(
            f"transformed {virtual_ms} into: M:{mode}, n:{numbers}, u:{unit}, O:{operation}, DF: {data_field}")

        return (mode, int(numbers), unit, operation, data_field)

    def __get_virtual_value(self, virtual_ms, correlation_hint):
        pool = []
        mode, number, unit, operation, data_field = self.__tokenize_matchstring(
            virtual_ms)

        if mode == 'next':
            if unit == 'h':
                if number > 48:
                    raise Exception(
                        "Cannot get value further than 48h in future, switch unit to 'd' to see further into the future")
                for hr in range(0, number):
                    val = self.get_value(f'hour/{hr}/{data_field}', correlation_hint)
                    if not isinstance(val, Exception):
                        pool.append(val)
            elif unit == 'd':
                if number > 6:
                    raise Exception(
                        "Cannot get value further than 6d in future")
                for day in range(0, number):
                    val = self.get_value(f'day/{day}/{data_field}', correlation_hint)
                    if not isinstance(val, Exception):
                        pool.append(val)
        elif mode == 'past':
            if unit == 'd':
                hours = number * 24
            else:
                hours = number

            days_back = int(hours / 24) + 1
            self.logger.debug(
                f"PAST: {virtual_ms} into: hrs:{hours}, days_back:{days_back}")
            for day_back in range(days_back, -1, -1):
                for hr in range(0, 24):
                    try:
                        val = self.get_value(
                            f'day/-{day_back}/hour/{hr}/{data_field}', correlation_hint)
                        if not isinstance(val, Exception):
                            pool.append(val)
                    except:
                        pass
            pool = pool[-hours:]

        self.logger.debug(
            f"{correlation_hint} {virtual_ms}  Pool: {pformat(pool, width=4000)}")

        if operation == "max":
            return max(pool)
        elif operation == "min":
            return min(pool)
        elif operation == "avg":
            if len(pool) == 0:
                return 0
            return round(functools.reduce(
                lambda x, y: x + y, pool) / len(pool), 2)
        elif operation == "sum":
            if len(pool) == 0:
                return 0
            return round(functools.reduce(
                lambda x, y: x + y, pool), 2)
        elif operation == "all":
            return pool
        else:
            return f"Unknown operation '{operation}' in match_string '{virtual_ms}'"

    def __handle_fail(self, last_popped, current_leaf, successful_path, original_match_string, correlation_hint):
        missing_child_path = last_popped if len(current_leaf) == 0 else f"{last_popped}/{'/'.join(current_leaf)}"
        fail_match_string = f"{last_popped}/{'/'.join(current_leaf)}"

        if fail_match_string in self._soft_fails:
            soft_fail_mode = self._soft_fails[fail_match_string]
            if soft_fail_mode == "log_info":
                raise OpenWeatherMapNoValueSoftException(
                    f"Missing child '{last_popped}' after '{'/'.join(successful_path)}' (complete path missing: {missing_child_path})")
            elif soft_fail_mode == "no_update":
                changed_match_string = '/'.join(successful_path) + missing_child_path
                self.logger.debug(
                            "%s DEBUG: owm-string: %s --> %s, Missing Child, Soft-Fail to no_update" % (correlation_hint, original_match_string, changed_match_string))
                return None
            elif soft_fail_mode.startswith("number="):
                return int(soft_fail_mode.replace("number=", ""))
            elif soft_fail_mode.startswith("string="):
                return soft_fail_mode.replace("string=", "")
            elif soft_fail_mode.startswith("relative="):
                relative_match_string = soft_fail_mode.replace("relative=", "")
                match_path = original_match_string.split('/')
                for fragment in relative_match_string.split('/'):
                    if fragment == "..":
                        match_path.pop()
                    else:
                        match_path.append(fragment)
                new_match_string = "/".join(match_path)
                self.logger.debug(f"{correlation_hint} '{original_match_string}' is matching soft_fail '{fail_match_string}' and will query '{new_match_string}'")
                return self.get_value_or_raise(new_match_string, correlation_hint)

        raise OpenWeatherMapNoValueHardException(
            f"Missing child '{last_popped}' after '{'/'.join(successful_path)}' (complete path missing: {missing_child_path})")



    def __get_val_from_dict(self, s, wrk, correlation_hint, original_match_string):
        """
        Uses string s as a path to navigate to the requested value in dict wrk.
        """
        successful_path = []
        last_popped = None
        sp = s.split('/')
        while True:
            if (len(sp) == 0) or (wrk is None):
                if wrk is None:
                    wrk = self.__handle_fail(last_popped, sp, successful_path, original_match_string, correlation_hint)
                break

            if type(wrk) is list:
                if self.is_int(sp[0]):
                    if int(sp[0]) < len(wrk):
                        wrk = wrk[int(sp[0])]
                    else:
                        raise OpenWeatherMapNoValueHardException(
                            f"Integer index ({int(sp[0])}) out of range after '{'/'.join(successful_path)}'")
                elif sp[0] == '@count':
                    if last_popped == 'alerts' and wrk[0] == self._placebo_alarm:
                        wrk = 0
                    else:
                        wrk = len(wrk)
                    break
                else:
                    wrk = wrk[0]
                    self.logger.warning(
                        f"{correlation_hint}Integer expected in matchstring after '{'/'.join(successful_path)}/{last_popped}', inserting '/0' to match FIRST entry.")
                    if last_popped is not None:
                        successful_path.append(last_popped)
                    last_popped = '0'
                    continue
            else:
                if type(wrk) is not dict:
                    self.logger.error(
                        f"{correlation_hint}s={s} wrk={wrk} type(wrk)={type(wrk)}")
                wrk = wrk.get(sp[0])

            if last_popped is not None:
                successful_path.append(last_popped)
            last_popped = sp.pop(0)
        return (wrk, f"{'/'.join(successful_path)}/{last_popped}")

    def get_daily_forecast(self, s):
        """
        Calculates daily forecast from (free) 3-hours data.
        This builds the average/min/max of all available 3-hour entries that match the
        requested period (1, 2, ..., 5 days in the future).
        Uses local time to determine which entries to include/exclude.
        """
        original_match_string = s
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
                        val, _ = self.__get_val_from_dict("/".join(sp), entry, "", original_match_string)
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

    def __query_api_if(self, data_source_key, only_if=False, delta_t=0, force=False):
        if only_if or force:
            self.__query_api(data_source_key, delta_t, force)
        else:
            if self._data_sources[data_source_key]['data'] == 'Not downloaded!':
                self._data_sources[data_source_key]['data'] = "Not requested by any item, you may download this via the web-interface!"
            # otherwise keep previous data

    def __query_api(self, data_source_key, delta_t=0, force=False):
        """
        Requests the weather information at openweathermap.com
        """
        try:
            url = self.__build_url(data_source_key, delta_t=delta_t, force=force)
            response = self._session.get(url)
        except Exception as e:
            self.logger.error(
                "__query_api: Exception when sending GET request for data_source_key '%s': %s" % (data_source_key, str(e)))
            return
        num_bytes = len(response.content)
        self.logger.debug(f"Received {num_bytes} bytes for {data_source_key} from {url}")
        if num_bytes < 50:
            self.logger.error(f"Response for {data_source_key} from {url} was too short to be meaningful: '{response.content}'")
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
        owm_raw = self.get_iattr_value(item.conf, 'owm_raw_file')
        if owm_raw:
            for ds_key in self._data_sources:
                if owm_raw == ds_key:
                    self._raw_items[item.id()] = (ds_key, item)
                    return
            self.logger.warn(f"Unmatched owm_raw_file name '{owm_raw}'")
            return

        owm_pfx = self.get_iattr_value(item.conf, 'owm_match_prefix')
        owm_ms = self.get_iattr_value(item.conf, 'owm_matchstring')
        if owm_ms:
            if owm_pfx:
                owm_ms = f"{owm_pfx}/{owm_ms}"
                owm_ms = owm_ms.replace('///', '/')
                owm_ms = owm_ms.replace('//', '/')

            self._items[item.id()] = (owm_ms, item)

            if owm_ms in self._origins_weather:
                self._request_weather = True
            elif owm_ms.startswith('uvi_'):
                self.logger.warning(
                    f"{item.path()} The UVI API is deprecated - if you intend to query the current UV-index, use 'current/uvi' instead")
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
            elif owm_ms.startswith('airpollution/hour'):
                self._request_airpollution_forecast = True
            elif owm_ms.startswith('airpollution/day/-1'):
                self._request_airpollution_back1day = True
            elif owm_ms.startswith('airpollution/day/-2'):
                self._request_airpollution_back2day = True
            elif owm_ms.startswith('airpollution/day/-3'):
                self._request_airpollution_back3day = True
            elif owm_ms.startswith('airpollution/day/-4'):
                self._request_airpollution_back4day = True
            elif owm_ms.startswith('airpollution/'):
                self._request_airpollution_current = True
            elif owm_ms.startswith('day'):
                self._request_daily = True
            elif owm_ms.startswith('alerts'):
                self._request_alerts = True
            elif owm_ms.startswith('virtual/past'):
                _, number, unit, _, _ = self.__tokenize_matchstring(owm_ms[8:])
                if unit == 'd':
                    hours = number * 24
                else:
                    hours = number
                days_back = int(hours / 24) + 1
                if days_back > 3:
                    self._request_back4day = True
                if days_back > 2:
                    self._request_back3day = True
                if days_back > 1:
                    self._request_back2day = True
                self._request_back0day = True
                self._request_back1day = True
            elif owm_ms.startswith('virtual/next'):
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

    def __build_url(self, url_type=None, item=None, delta_t=0, force=False):
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
        elif url_type == self._data_source_key_airpollution_current:
            url = self._base_url % 'data/2.5/air_pollution'
            parameters = "?lat=%s&lon=%s&appid=%s" % (
                self._lat, self._lon, self._key)
            url = '%s%s' % (url, parameters)
        elif url_type == self._data_source_key_airpollution_forecast:
            url = self._base_url % 'data/2.5/air_pollution/history'
            parameters = "?lat=%s&lon=%s&start=%i&end=%i&appid=%s" % (
                self._lat, self._lon, datetime.utcnow().timestamp(), self.__get_timestamp_for_delta_days(5), self._key)
            url = '%s%s' % (url, parameters)
        elif url_type.startswith('airpollution-'):
            url = self._base_url % 'data/2.5/air_pollution/history'
            parameters = "?lat=%s&lon=%s&start=%i&end=%i&appid=%s" % (self._lat, self._lon,  self.__get_timestamp_for_delta_days(
                delta_t), self.__get_timestamp_for_delta_days(delta_t + 1), self._key)
            url = '%s%s' % (url, parameters)
        elif url_type == self._data_source_key_onecall:
            url = self._base_url % 'data/2.5/onecall'
            if force:
                exclude = ""
            else:
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
        elif url_type.startswith('onecall-'):
            url = self._base_url % 'data/2.5/onecall/timemachine'
            parameters = "?lat=%s&lon=%s&dt=%i&appid=%s&lang=%s&units=%s" % (self._lat, self._lon, self.__get_timestamp_for_delta_days(delta_t),
                                                                             self._key, self._lang, self._units)
            url = '%s%s' % (url, parameters)
        elif url_type == 'owm_layer':
            if self.has_iattr(item.conf, 'owm_matchstring'):
                layer = self.get_iattr_value(item.conf, 'owm_matchstring')
            elif 'owm_matchstring' in item.conf:
                layer = item.conf['owm_matchstring']

            if self.has_iattr(item.conf, 'owm_coord_z'):
                z = self.get_iattr_value(item.conf, 'owm_coord_z')
            elif 'owm_coord_z' in item.conf:
                z = item.conf['owm_coord_z']
            else:
                self.logger.warning(
                    f"{item.property.path} owm_coord_z attribute not set for item, setting default 7")
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
                    f"{item.property.path} owm_coord_x attribute not set for item, setting default as per plugin-coordinates: {x}")

            if self.has_iattr(item.conf, 'owm_coord_y'):
                y = self.get_iattr_value(item.conf, 'owm_coord_y')
            elif 'owm_coord_y' in item.conf:
                y = item.conf['y']
            else:
                y = y_fallback
                self.logger.warning(
                    f"{item.property.path} owm_coord_y attribute not set for item, setting default as per plugin-coordinates: {y}")

            url = self._base_img_url % (layer, z, x, y, self._key)
        else:
            self.logger.error(
                '%s __build_url: Wrong url type specified: %s' % (item.property.path, url_type))
        return url

    def _get_all_data_for_webif(self):
        rslt = []
        for data_source_key in self._data_sources:
            src = self._data_sources[data_source_key]['data']
            rslt.append({
                "key": data_source_key.replace('-', '_minus_'),
                "data": json.dumps(src, indent=4),
                "url": self._data_sources[data_source_key]['url'],
                "fetched": self._data_sources[data_source_key]['fetched']
            })

        return rslt

    def get_raw_data_file(self, data_source_key):
        src = self._data_sources[data_source_key]['data']
        return json.dumps(src, indent=4)

    def _get_position_hint_within_json(self, data_source_key, match_string_within_file):
        splitted = match_string_within_file.split("/")
        src = self._data_sources[data_source_key]['data']
        daten = json.dumps(src, indent=4).splitlines()

        last_line = 0
        for pos_in_match_string in range(len(splitted)):
            if splitted[pos_in_match_string].isnumeric():
                number = int(splitted[pos_in_match_string]) + 1
                for line_in_file in range(last_line, len(daten)):
                    now_search_for = ((" " * 4) * (pos_in_match_string + 1)) + "{"
                    if daten[line_in_file] == now_search_for:
                        number = number - 1
                        if number == 0:
                            last_line = line_in_file
                            break
            else:
                now_search_for = ((" " * 4) * (pos_in_match_string + 1)) + f'"{splitted[pos_in_match_string]}":'
                for line_in_file in range(last_line, len(daten)):
                    if daten[line_in_file].startswith(now_search_for):
                        last_line = line_in_file
                        break
        return (last_line, 4 * (pos_in_match_string + 1), len(daten[line_in_file]))

    def get_beaufort_number(self, speed_in_mps):
        try:
            # Origin of table: https://www.smarthomeng.de/vom-winde-verweht
            table = [
                (0.3, 0),
                (1.6, 1),
                (3.4, 2),
                (5.5, 3),
                (8.0, 4),
                (10.8, 5),
                (13.9, 6),
                (17.2, 7),
                (20.8, 8),
                (24.5, 9),
                (28.5, 10),
                (32.7, 11),
                (999,  12)]
            return min(filter(lambda x: x[0] >= speed_in_mps, table))[1]
        except ValueError:
            self.logger.error(
                f"Cannot translate wind-speed to beaufort-number, received: '{speed_in_mps}'")
            return None

    def get_beaufort_description(self, speed_in_bft):
        if speed_in_bft is None:
            self.logger.warning(f"speed_in_bft is given as None")
            return None
        if type(speed_in_bft) is not int:
            self.logger.error(
                f"speed_in_bft is not given as int: '{speed_in_bft}'")
            return None
        if (speed_in_bft < 0) or (speed_in_bft > 12):
            self.logger.error(
                f"speed_in_bft is out of scale: '{speed_in_bft}'")
            return None
        if self._lang == 'de':
            return self._beaufort_descriptions_de[speed_in_bft]
        return self._beaufort_descriptions_en[speed_in_bft]
