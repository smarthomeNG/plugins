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
try:
    import requests
    REQUIRED_PACKAGE_IMPORTED = True
except:
    REQUIRED_PACKAGE_IMPORTED = False
import datetime
import json
from lib.module import Modules
from lib.model.smartplugin import *


class OpenWeatherMap(SmartPlugin):
    PLUGIN_VERSION = "1.5.0.2"

    _base_url = 'https://api.openweathermap.org/%s'
    _base_img_url = 'https://tile.openweathermap.org/map/%s/%s/%s/%s.png?appid=%s'

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin
        @param apikey: For accessing the free "Tankerkönig-Spritpreis-API" you need a personal
        api key. For your own key register to https://creativecommons.tankerkoenig.de
        """
        self.logger = logging.getLogger(__name__)
        if not REQUIRED_PACKAGE_IMPORTED:
            self.logger.error("{}: Unable to import Python package 'requests'".format(self.get_fullname()))
            self._init_complete = False
            return
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
        self.logger.debug('Starting update loop for instance %s' % self.get_instance_name())
        if not self.alive:
            return

        self._update()

    def _update(self):
        """
        Updates information on diverse items
        """
        weather = self.get_weather()
        uv = self.get_uv()

        self._jsonData['weather'] = weather
        self._jsonData['uvi'] = uv
        for s, item in self._items.items():

            if s in ['clouds_new', 'precipitation_new', 'pressure_new', 'wind_new', 'temp_new']:
                wrk = self.get_owm_layer(item)
            else:
                if 'uvi' not in s:
                    wrk = weather
                else:
                    wrk = uv
                    s = s.replace("uvi_", "")
                sp = s.split('/')

                while True:
                    if (len(sp) == 0) or (wrk is None):
                        break
                    if type(wrk) is list:
                        if self.is_int(sp[0]):
                            if int(sp[0]) < len(wrk):
                                wrk = wrk[int(sp[0])]
                            else:
                                self.logger.error(
                                    "_update: invalid owm_matchstring '{}'; integer too large in matchstring".format(
                                        s))
                                break
                        else:
                            self.logger.error(
                                "_update: invalid owm_matchstring '{}'; integer expected in matchstring".format(
                                    s))
                            break
                    else:
                        wrk = wrk.get(sp[0])
                    if len(sp) == 1:
                        spl = s.split('/')
                        self.logger.debug(
                            "_update: owm_matchstring split len={}, content={} -> '{}'".format(str(len(spl)),
                                                                                               str(spl),
                                                                                               str(wrk)))
                    sp.pop(0)

            # if a value was found, store it to item
            if wrk is not None:
                item(wrk, 'DarkSky')
                self.logger.debug('_update: Value "{0}" written to item'.format(wrk))

        return

    def get_owm_layer(self, item):
        """
        Requests the layer information (image links) at openweathermap.com
        """
        return self._build_url('owm_layer', item)

    def get_weather(self):
        """
        Requests the weather information at openweathermap.com
        """
        try:
            response = self._session.get(self._build_url('weather'))
        except Exception as e:
            self.logger.error(
                "get_weather: Exception when sending GET request for get_weather: %s" % str(e))
            return
        json_obj = response.json()
        return json_obj

    def get_uv(self):
        """
        Requests the uv index information at openweathermap.com
        """
        try:
            response = self._session.get(self._build_url('uv'))
        except Exception as e:
            self.logger.error(
                "get_uv: Exception when sending GET request for get_uv: %s" % str(e))
            return
        json_obj = response.json()
        return json_obj

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the owm_matchstring and adds it to an internal array

        :param item: The item to process.
        """
        if self.get_iattr_value(item.conf, 'owm_matchstring'):
            self._items[self.get_iattr_value(item.conf, 'owm_matchstring')] = item

    def get_items(self):
        return self._items

    def get_json_data_weather(self):
        return self._jsonData['weather']

    def get_json_data_uvi(self):
        return self._jsonData['uvi']

    def _build_url(self, url_type='weather', item=None):
        """
        Builds a request url
        @param url_type: url type (currently on 'forecast', as historic data are not supported.
        @return: string of the url
        """
        url = ''
        if url_type == 'weather':
            url = self._base_url % 'data/2.5/weather'
            parameters = "?lat=%s&lon=%s&appid=%s&lang=%s&units=%s" % (self._lat, self._lon, self._key, self._lang,
                                                                       self._units)
            url = '%s%s' % (url, parameters)
        elif url_type == 'uv':
            url = self._base_url % 'data/2.5/uvi'
            parameters = "?lat=%s&lon=%s&appid=%s&lang=%s&units=%s" % (self._lat, self._lon, self._key, self._lang,
                                                                       self._units)
            url = '%s%s' % (url, parameters)
        elif url_type == 'owm_layer':
            if self.has_iattr(item.conf, 'owm_matchstring'):
                layer = self.get_iattr_value(item.conf, 'owm_matchstring')
            elif 'owm_matchstring' in item.conf:
                layer = item.conf['owm_matchstring']

            if self.has_iattr(item.conf, 'x'):
                x = self.get_iattr_value(item.conf, 'x')
            elif 'x' in item.conf:
                x = item.conf['x']
            else:
                self.logger.warning("_build_url: x attribute not set for item, setting default 1")
                x = 1

            if self.has_iattr(item.conf, 'y'):
                y = self.get_iattr_value(item.conf, 'y')
            elif 'y' in item.conf:
                y = item.conf['y']
            else:
                self.logger.warning("_build_url: y attribute not set for item, setting default 1")
                y = 1

            if self.has_iattr(item.conf, 'z'):
                z = self.get_iattr_value(item.conf, 'z')
            elif 'z' in item.conf:
                z = item.conf['z']
            else:
                self.logger.warning("_build_url: z attribute not set for item, setting default 1")
                z = 1

            url = self._base_img_url % (layer, z, x, y, self._key)
        else:
            self.logger.error('_build_url: Wrong url type specified: %s' % url_type)
        return url

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
        from pprint import pformat

        tmpl = self.tplenv.get_template('index.html')
        json_data_weather = pformat(self.plugin.get_json_data_weather())
        json_data_uvi = pformat(self.plugin.get_json_data_uvi())
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(), p=self.plugin,
                           json_data_uvi=json_data_uvi.replace('\n', '<br>').replace(' ', '&nbsp;'),
                           json_data_weather=json_data_weather.replace('\n', '<br>').replace(' ', '&nbsp;'))
