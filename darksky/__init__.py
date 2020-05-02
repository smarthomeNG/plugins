#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2018 René Frieß                      rene.friess(a)gmail.com
#  Version 1.5.0.2
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


class DarkSky(SmartPlugin):


    PLUGIN_VERSION = "1.7.0"

    _base_forecast_url = 'https://api.darksky.net/forecast/%s/%s,%s'

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin
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
        self._jsonData = {}
        self._session = requests.Session()
        self._cycle = int(self.get_parameter_value('cycle'))
        self._items = {}

        if not self.init_webinterface():
            self._init_complete = False

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
        Updates information on diverse items
        """
        forecast = self.get_forecast()
        if forecast is None:
            self.logger.error("Forecast is None! Perhaps server did not reply?")
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
                for sameMatchStringItem in matchStringItems:
                    sameMatchStringItem(wrk, 'DarkSky')
                    self.logger.debug('_update: Value "{0}" written to item {1}'.format(wrk, sameMatchStringItem))

        return

    def get_forecast(self):
        """
        Requests the forecast information at darksky.net
        """
        try:
            response = self._session.get(self._build_url())
        except Exception as e:
            self.logger.error(
                "get_forecast: Exception when sending GET request for get_forecast: {}".format(e))
            return
        json_obj = response.json()
        daily_data = OrderedDict()

        # add icon_visu, date and day to daily and currently
        json_obj['daily'].update({'icon_visu': self.map_icon(json_obj['daily']['icon'])})
        date_entry = datetime.datetime.fromtimestamp(json_obj['currently']['time']).strftime('%d.%m.%Y')
        day_entry = datetime.datetime.fromtimestamp(json_obj['currently']['time']).strftime('%A')
        hour_entry = datetime.datetime.fromtimestamp(json_obj['currently']['time']).hour
        json_obj['currently'].update({'date': date_entry, 'weekday': day_entry, 'hour': hour_entry,
                                      'icon_visu': self.map_icon(json_obj['currently']['icon'])})
        json_obj['hourly'].update({'icon_visu': self.map_icon(json_obj['hourly']['icon'])})

        # add icon_visu, date and day to each day
        for day in json_obj['daily'].get('data'):
            date_entry = datetime.datetime.fromtimestamp(day['time']).strftime('%d.%m.%Y')
            day_entry = datetime.datetime.fromtimestamp(day['time']).strftime('%A')
            day.update({'date': date_entry, 'weekday': day_entry, 'icon_visu': self.map_icon(day['icon'])})
            daily_data.update({datetime.datetime.fromtimestamp(day['time']).date(): day})
        json_obj['daily'].update(daily_data)
        json_obj['daily'].pop('data')

        # add icon_visu, date and day to each hour. Add the hours to the corresponding day as well as map to hour0, hour1, etc.
        for number, hour in enumerate(json_obj['hourly'].get('data')):
            date_entry = datetime.datetime.fromtimestamp(hour['time']).strftime('%d.%m.%Y')
            day_entry = datetime.datetime.fromtimestamp(hour['time']).strftime('%A')
            hour_entry = datetime.datetime.fromtimestamp(hour['time']).hour
            date_key = datetime.datetime.fromtimestamp(hour['time']).date()
            hour.update({'date': date_entry, 'weekday': day_entry, 'hour': hour_entry, 'icon_visu': self.map_icon(hour['icon'])})
            if json_obj['daily'].get(date_key) is None:
                json_obj['daily'].update({date_key: {}})
            elif json_obj['daily'][date_key].get('hours') is None:
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

        # add mean values to each day and replace datetime object by day0, day1, day2, etc.
        i = 0
        for entry in json_obj['daily']:
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
        Maps the icons from darksky.net to the icons in SmartVisu

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
        the ds_matchstring and adds it to an internal array

        :param item: The item to process.
        """
        if self.get_iattr_value(item.conf, 'ds_matchstring'):
            if not self.get_iattr_value(item.conf, 'ds_matchstring') in self._items:
                self._items[self.get_iattr_value(item.conf, 'ds_matchstring')] = []
            self._items[self.get_iattr_value(item.conf, 'ds_matchstring')].append(item)

    def get_items(self):
        return self._items

    def get_json_data(self):
        return self._jsonData

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

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')   # try/except to handle running in a core version that does not support modules
        except Exception:
            self.mod_http = None
        if self.mod_http is None:
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
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """

        def printdict(OD, mode='dict', s="", indent=' '*4, level=0):
            def is_number(s):
                try:
                    float(s)
                    return True
                except Exception:
                    return False

            def fstr(s):
                return s if is_number(s) else '"{}"'.format(s)
            if mode != 'dict':
                kv_tpl = '("{}")'.format(s)
                ST = 'OrderedDict([\n'
                END = '])'
            else:
                kv_tpl = '"%s": %s'
                ST = '{\n'
                END = '}'
            for i, k in enumerate(OD.keys()):
                if type(OD[k]) in [dict, OrderedDict]:
                    level += 1
                    s += (level-1)*indent+kv_tpl%(k,ST+printdict(OD[k], mode=mode, indent=indent, level=level)+(level-1)*indent+END)
                    level -= 1
                else:
                    s += level*indent+kv_tpl%(k,fstr(OD[k]))
                if i != len(OD) - 1:
                    s += ","
                s += "\n"
            return s

        tmpl = self.tplenv.get_template('index.html')
        pf = printdict(self.plugin.get_json_data())
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(), p=self.plugin, json_data=pf.replace('\n', '<br>').replace(' ', '&nbsp;'),)
