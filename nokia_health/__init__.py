#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2017 Marc René Frieß                 rene.friess(a)gmail.com
#  Version 1.3.1
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

import requests
from lib.model.smartplugin import *
from nokia import NokiaAuth, NokiaApi, NokiaCredentials


class NokiaHealth(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.5.3"
    ALLOWED_MEASURE_TYPES = [1, 4, 5, 6, 8, 11]

    def __init__(self, sh, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self._access_token = self.get_parameter_value('access_token')
        self._token_expiry = self.get_parameter_value('token_expiry')
        self._token_type = self.get_parameter_value('token_type')
        self._refresh_token = self.get_parameter_value('refresh_token')
        self._user_id = self.get_parameter_value('user_id')
        self._client_id = self.get_parameter_value('client_id')
        self._consumer_secret = self.get_parameter_value('consumer_secret')
        self._cycle = self.get_parameter_value('cycle')

        self._creds = NokiaCredentials(self._access_token, self._token_expiry, self._token_type, self._refresh_token, self._user_id, self._client_id,
                                 self._consumer_secret)
        self._client = NokiaApi(self._creds)
        self._items = {}

        if not self.init_webinterface():
            self._init_complete = False

    def run(self):
        self.alive = True
        self.scheduler_add(__name__, self._update_loop, cycle=self._cycle)

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
        Mappings:
        ('weight', 1),
        ('height', 4),
        ('fat_free_mass', 5),
        ('fat_ratio', 6),
        ('fat_mass_weight', 8),
        ('diastolic_blood_pressure', 9),
        ('systolic_blood_pressure', 10),
        ('heart_pulse', 11),
        ('temperature', 12),
        ('spo2', 54),
        ('body_temperature', 71),
        ('skin_temperature', 72),
        ('muscle_mass', 76),
        ('hydration', 77),
        ('bone_mass', 88),
        ('pulse_wave_velocity', 91)
        """
        measures = self._client.get_measures()
        last_measure = measures[0]

        if last_measure.get_measure(11) is not None and 'heart_pulse' in self._items:
            self._items['heart_pulse'](last_measure.get_measure(11))
            self.logger.debug(last_measure.get_measure(11))

        # Bugfix for strange behavior of returning heart_pulse as seperate dataset..
        if last_measure.get_measure(1) is None:
            last_measure = measures[1]

        if last_measure.get_measure(1) is not None and 'weight' in self._items:
            self._items['weight'](last_measure.get_measure(1))
            self.logger.debug(last_measure.get_measure(1))

        if last_measure.get_measure(4) is not None and 'height' in self._items:
            self._items['height'](last_measure.get_measure(4))
            self.logger.debug(last_measure.get_measure(4))

        if last_measure.get_measure(5) is not None and 'fat_free_mass' in self._items:
            self._items['fat_free_mass'](last_measure.get_measure(5))
            self.logger.debug(last_measure.get_measure(5))

        if last_measure.get_measure(6) is not None and 'fat_ratio' in self._items:
            self._items['fat_ratio'](last_measure.get_measure(6))
            self.logger.debug(last_measure.get_measure(6))

        if last_measure.get_measure(8) is not None and 'fat_mass_weight' in self._items:
            self._items['fat_mass_weight'](last_measure.get_measure(8))
            self.logger.debug(last_measure.get_measure(8))

        if last_measure.get_measure(9) is not None and 'diastolic_blood_pressure' in self._items:
            self._items['diastolic_blood_pressure'](last_measure.get_measure(9))
            self.logger.debug(last_measure.get_measure(9))

        if last_measure.get_measure(10) is not None and 'systolic_blood_pressure' in self._items:
            self._items['systolic_blood_pressure'](last_measure.get_measure(10))
            self.logger.debug(last_measure.get_measure(10))

        if last_measure.get_measure(11) is not None and 'heart_pulse' in self._items:
            self._items['heart_pulse'](last_measure.get_measure(11))
            self.logger.debug(last_measure.get_measure(11))

        if last_measure.get_measure(12) is not None and 'temperature' in self._items:
            self._items['temperature'](last_measure.get_measure(12))
            self.logger.debug(last_measure.get_measure(12))

        if last_measure.get_measure(54) is not None and 'spo2' in self._items:
            self._items['spo2'](last_measure.get_measure(54))
            self.logger.debug(last_measure.get_measure(54))

        if last_measure.get_measure(71) is not None and 'body_temperature' in self._items:
            self._items['body_temperature'](last_measure.get_measure(71))
            self.logger.debug(last_measure.get_measure(71))

        if last_measure.get_measure(72) is not None and 'skin_temperature' in self._items:
            self._items['skin_temperature'](last_measure.get_measure(72))
            self.logger.debug(last_measure.get_measure(72))

        if last_measure.get_measure(76) is not None and 'muscle_mass' in self._items:
            self._items['muscle_mass'](last_measure.get_measure(76))
            self.logger.debug(last_measure.get_measure(76))

        if last_measure.get_measure(77) is not None and 'hydration' in self._items:
            self._items['hydration'](last_measure.get_measure(77))
            self.logger.debug(last_measure.get_measure(77))

        if last_measure.get_measure(88) is not None and 'bone_mass' in self._items:
            self._items['bone_mass'](last_measure.get_measure(88))
            self.logger.debug(last_measure.get_measure(88))

        if last_measure.get_measure(91) is not None and 'pulse_wave_velocity' in self._items:
            self._items['pulse_wave_velocity'](last_measure.get_measure(91))
            self.logger.debug(last_measure.get_measure(91))

        if 'height' in self._items and ('bmi' in self._items or 'bmi_text' in self._items) and last_measure.get_measure(
                1) is not None:
            if self._items['height']() > 0:
                bmi = round(
                    last_measure.get_measure(1) / ((self._items['height']()) * (self._items['height']())), 2)
                if 'bmi' in self._items:
                    self._items['bmi'](bmi)
                if 'bmi_text' in self._items:
                    if bmi < 16:
                        self._items['bmi_text']('starkes Untergewicht')
                    elif 16 <= bmi < 17:
                        self._items['bmi_text']('mäßiges Untergewicht ')
                    elif 17 <= bmi < 18.5:
                        self._items['bmi_text']('leichtes Untergewicht ')
                    elif 18.5 <= bmi < 25:
                        self._items['bmi_text']('Normalgewicht')
                    elif 25 <= bmi < 30:
                        self._items['bmi_text']('Präadipositas (Übergewicht)')
                    elif 30 <= bmi < 35:
                        self._items['bmi_text']('Adipositas Grad I')
                    elif 35 <= bmi < 40:
                        self._items['bmi_text']('Adipositas Grad II')
                    elif 40 <= bmi:
                        self._items['bmi_text']('Adipositas Grad III')
            else:
                self.logger.error(
                    "Cannot calculate BMI: height is 0, please set height (in m) for height item manually.")
        else:
            self.logger.error("Cannot calculate BMI: height and / or bmi item missing.")

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the Nokia Health identifier and adds it to an internal array

        :param item: The item to process.
        """
        # items specific to call monitor
        if self.get_iattr_value(item.conf, 'nh_type') in ['weight', 'height', 'fat_free_mass', 'fat_mass_weight',
                                                          'fat_ratio', 'fat_mass_weight', 'diastolic_blood_pressure',
                                                          'systolic_blood_pressure', 'heart_pulse', 'temperature',
                                                          'spo2', 'body_temperature', 'skin_temperature', 'muscle_mass',
                                                          'hydration', 'bone_mass', 'pulse_wave_velocity', 'bmi',
                                                          'bmi_text']:
            self._items[self.get_iattr_value(item.conf, 'nh_type')] = item

    def get_items(self):
        return self._items

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


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

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
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           interface=None, item_count=len(self.plugin.get_items()),
                           plugin_info=self.plugin.get_info(), tabcount=1,
                           tab1title="Nokia Health Items (%s)" % len(self.plugin.get_items()),
                           p=self.plugin)
