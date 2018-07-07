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
from lib.model.smartplugin import SmartPlugin


class DarkSky(SmartPlugin):
    _base_forecast_url = 'https://api.darksky.net/forecast/%s/%s,%s'

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin
        @param apikey: For accessing the free "Tankerkönig-Spritpreis-API" you need a personal
        api key. For your own key register to https://creativecommons.tankerkoenig.de
        """
        self.logger = logging.getLogger(__name__)
        self._key = self.get_parameter_value('key')
        if self.get_parameter_value('latitude') != '' and self.get_parameter_value('longitude') != '':
            self._lat = self.get_parameter_value('latitude')
            self._lon = self.get_parameter_value('longitude')
        else:
            self.logger.debug("__init__: latitude and longitude not provided, using shng system values instead.")
            self._lat = self.get_sh()._lat
            self._lon = self.get_sh()._lon
        self._lang = self.get_parameter_value('lang')
        self._units = self.get_parameter_value('units')
        self._session = requests.Session()
        self._cycle = int(self.get_parameter_value('cycle'))
        self._items = {}

    def run(self):
        self.scheduler_add(__name__, self._update_loop, prio=5, cycle=self._cycle, offset=2)
        self.alive = True

    def stop(self):
        self.alive = False

    def _update_loop(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug('Starting update loop for instance %s' % self.get_instance_name())
        if not self.alive:
            return

        self._update()

    def _update(self):
        """
        Updates information on diverse items
        """
        forecast = self.get_forecast()

        for s, item in self._items.items():
            sp = s.split('/')
            wrk = forecast
            if s == "flags/sources":
                wrk = ', '.join(wrk['flags']['sources'])
            elif s == "alerts" or s == "alerts_string":
                if 'alerts' in wrk:
                    if s == "alerts":
                        wrk = wrk['alerts']
                    else:
                        alerts_string = ''
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
                                    "_update: invalid ds_matchstring '{}'; integer too large in matchstring".format(
                                        s))
                                break
                        else:
                            self.logger.error(
                                "_update: invalid ds_matchstring '{}'; integer expected in matchstring".format(
                                    s))
                            break
                    else:
                        wrk = wrk.get(sp[0])
                    if len(sp) == 1:
                        spl = s.split('/')
                        self.logger.debug(
                            "_update: ds_matchstring split len={}, content={} -> '{}'".format(str(len(spl)),
                                                                                                             str(spl),
                                                                                                             str(wrk)))
                    sp.pop(0)

            # if a value was found, store it to item
            if wrk is not None:
                item(wrk, 'DarkSky')
                self.logger.debug('_update: Value "{0}" written to item'.format(wrk))

        return

    def get_forecast(self):
        """
        Requests the forecast information at darksky.net
        """
        try:
            response = self._session.get(self._build_url())
        except Exception as e:
            self.logger.error(
                "get_forecast: Exception when sending GET request for get_forecast: %s" % str(e))
            return
        json_obj = response.json()
        return json_obj

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the ds_matchstring and adds it to an internal array

        :param item: The item to process.
        """
        if self.get_iattr_value(item.conf, 'ds_matchstring'):
            self._items[self.get_iattr_value(item.conf, 'ds_matchstring')] = item

    def get_items(self):
        return self._items

    def _build_url(self, url_type='forecast'):
        """
        Builds a request url
        @param url_type: url type (currently on 'forecast', as historic data are not supported.
        @return: string of the url
        """
        url = ''
        if url_type == 'forecast':
            url = self._base_forecast_url % (self._key, self._lat, self._lon)
            parameters = "?lang=%s" % self._lang
            if self._units is not None:
                parameters = "%s&units=%s" % (parameters, self._units)
            url = '%s%s' % (url, parameters)
        else:
            self.logger.error('_build_url: Wrong url type specified: %s' %url_type)
        return url
