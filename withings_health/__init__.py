#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2017-2018 Marc René Frieß            rene.friess(a)gmail.com
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

import cherrypy
import datetime
from lib.model.smartplugin import *
from lib.shtime import Shtime
from nokia import NokiaAuth, NokiaApi, NokiaCredentials


class WithingsHealth(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.5.3"
    ALLOWED_MEASURE_TYPES = [1, 4, 5, 6, 8, 11]

    def __init__(self, sh, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.shtime = Shtime.get_instance()
        self._user_id = self.get_parameter_value('user_id')
        self._client_id = self.get_parameter_value('client_id')
        self._consumer_secret = self.get_parameter_value('consumer_secret')
        self._cycle = self.get_parameter_value('cycle')
        self._creds = None
        self._client = None
        self._items = {}

        if not self.init_webinterface():
            self._init_complete = False

    def run(self):
        self.alive = True
        self.scheduler_add('poll_data', self._update_loop, cycle=self._cycle)

    def stop(self):
        self.alive = False

    def _store_tokens(self, token):
        self.logger.debug(
            "Plugin '{}': Updating tokens to items: access_token - {} token_expiry - {} token_type - {} refresh_token - {}".
                format(self.get_fullname(), token['access_token'], token['expires_in'], token['token_type'],
                       token['refresh_token']))
        self.get_item('access_token')(token['access_token'])
        self.get_item('token_expiry')(
            int((datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds()) + int(
                token['expires_in']))
        self.get_item('token_type')(token['token_type'])
        self.get_item('refresh_token')(token['refresh_token'])

    def _update_loop(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug(
            "Plugin '{}': Starting update loop".format(self.get_fullname()))
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

        if 'access_token' not in self.get_items() or 'token_expiry' not in self.get_items() or 'token_type' not in self.get_items() or 'refresh_token' not in self.get_items():
            self.logger.error(
                "Plugin '{}': Mandatory Items for OAuth2 Data do not exist. Verify that you have items with withings_type: token_expiry, token_type, refresh_token and access_token in your item tree.".format(
                    self.get_fullname()))
            return

        if self._client is None:
            if self.get_item('access_token')() and self.get_item(
                    'token_expiry')() > 0 and self.get_item(
                'token_type')() and self.get_item('refresh_token')():

                if (self.shtime.now() < datetime.datetime.fromtimestamp(self.get_item(
                        'token_expiry')(), tz=self.shtime.tzinfo())):
                    self.logger.debug(
                        "Plugin '{}': Token is valid, will expire on {}.".format(
                            self.get_fullname(), datetime.datetime.fromtimestamp(self.get_item(
                                'token_expiry')(), tz=self.shtime.tzinfo()).strftime('%d.%m.%Y %H:%M:%S')))
                    self.logger.debug(
                        "Plugin '{}': Initializing NokiaCredentials: access_token - {} token_expiry - {} token_type - {} refresh_token - {} user_id - {} client_id - {} consumer_secret - {}".
                            format(self.get_fullname(), self.get_item('access_token')(),
                                   self.get_item('token_expiry')(),
                                   self.get_item('token_type')(),
                                   self.get_item('refresh_token')(),
                                   self._user_id,
                                   self._client_id,
                                   self._consumer_secret))
                    self._creds = NokiaCredentials(self.get_item('access_token')(),
                                                   self.get_item('token_expiry')(),
                                                   self.get_item('token_type')(),
                                                   self.get_item('refresh_token')(),
                                                   self._user_id, self._client_id,
                                                   self._consumer_secret)
                    self._client = NokiaApi(self._creds, refresh_cb=self._store_tokens)
                else:
                    self.logger.error(
                        "Plugin '{}': Token is expired, run OAuth2 again from Web Interface (Expiry Date: {}).".format(
                            self.get_fullname(), datetime.datetime.fromtimestamp(self.get_item(
                                'token_expiry')(), tz=self.shtime.tzinfo()).strftime('%d.%m.%Y %H:%M:%S')))
                    return
            else:
                self.logger.error(
                    "Plugin '{}': Items for OAuth2 Data are not set with required values. Please run process via WebGUI of the plugin.".format(
                        self.get_fullname()))
                return
        measures = self._client.get_measures()
        last_measure = measures[0]

        if last_measure.get_measure(11) is not None and 'heart_pulse' in self._items:
            self._items['heart_pulse'](last_measure.get_measure(11), self.get_shortname())
            self.logger.debug("Plugin '{}': heart_pulse - {}".format(self.get_fullname(), last_measure.get_measure(11)))

        # Bugfix for strange behavior of returning heart_pulse as seperate dataset..
        if last_measure.get_measure(1) is None:
            last_measure = measures[1]

        if last_measure.get_measure(1) is not None and 'weight' in self._items:
            self._items['weight'](last_measure.get_measure(1), self.get_shortname())
            self.logger.debug("Plugin '{}': weight - {}".format(self.get_fullname(), last_measure.get_measure(1)))

        if last_measure.get_measure(4) is not None and 'height' in self._items:
            self._items['height'](last_measure.get_measure(4), self.get_shortname())
            self.logger.debug("Plugin '{}': height - {}".format(self.get_fullname(), last_measure.get_measure(4)))

        if last_measure.get_measure(5) is not None and 'fat_free_mass' in self._items:
            self._items['fat_free_mass'](last_measure.get_measure(5), self.get_shortname())
            self.logger.debug(
                "Plugin '{}': fat_free_mass - {}".format(self.get_fullname(), last_measure.get_measure(5)))

        if last_measure.get_measure(6) is not None and 'fat_ratio' in self._items:
            self._items['fat_ratio'](last_measure.get_measure(6), self.get_shortname())
            self.logger.debug("Plugin '{}': fat_ratio - {}".format(self.get_fullname(), last_measure.get_measure(6)))

        if last_measure.get_measure(8) is not None and 'fat_mass_weight' in self._items:
            self._items['fat_mass_weight'](last_measure.get_measure(8), self.get_shortname())
            self.logger.debug(
                "Plugin '{}': fat_mass_weight - {}".format(self.get_fullname(), last_measure.get_measure(8)))

        if last_measure.get_measure(9) is not None and 'diastolic_blood_pressure' in self._items:
            self._items['diastolic_blood_pressure'](last_measure.get_measure(9), self.get_shortname())
            self.logger.debug(
                "Plugin '{}': diastolic_blood_pressure - {}".format(self.get_fullname(), last_measure.get_measure(9)))

        if last_measure.get_measure(10) is not None and 'systolic_blood_pressure' in self._items:
            self._items['systolic_blood_pressure'](last_measure.get_measure(10), self.get_shortname())
            self.logger.debug(
                "Plugin '{}': systolic_blood_pressure - {}".format(self.get_fullname(), last_measure.get_measure(10)))

        if last_measure.get_measure(11) is not None and 'heart_pulse' in self._items:
            self._items['heart_pulse'](last_measure.get_measure(11), self.get_shortname())
            self.logger.debug("Plugin '{}': heart_pulse - {}".format(self.get_fullname(), last_measure.get_measure(11)))

        if last_measure.get_measure(12) is not None and 'temperature' in self._items:
            self._items['temperature'](last_measure.get_measure(12), self.get_shortname())
            self.logger.debug("Plugin '{}': temperature - {}".format(self.get_fullname(), last_measure.get_measure(12)))

        if last_measure.get_measure(54) is not None and 'spo2' in self._items:
            self._items['spo2'](last_measure.get_measure(54), self.get_shortname())
            self.logger.debug("Plugin '{}': spo2 - {}".format(self.get_fullname(), last_measure.get_measure(54)))

        if last_measure.get_measure(71) is not None and 'body_temperature' in self._items:
            self._items['body_temperature'](last_measure.get_measure(71), self.get_shortname())
            self.logger.debug(
                "Plugin '{}': body_temperature - {}".format(self.get_fullname(), last_measure.get_measure(71)))

        if last_measure.get_measure(72) is not None and 'skin_temperature' in self._items:
            self._items['skin_temperature'](last_measure.get_measure(72), self.get_shortname())
            self.logger.debug(
                "Plugin '{}': skin_temperature - {}".format(self.get_fullname(), last_measure.get_measure(72)))

        if last_measure.get_measure(76) is not None and 'muscle_mass' in self._items:
            self._items['muscle_mass'](last_measure.get_measure(76), self.get_shortname())
            self.logger.debug("Plugin '{}': muscle_mass - {}".format(self.get_fullname(), last_measure.get_measure(76)))

        if last_measure.get_measure(77) is not None and 'hydration' in self._items:
            self._items['hydration'](last_measure.get_measure(77), self.get_shortname())
            self.logger.debug("Plugin '{}': hydration - {}".format(self.get_fullname(), last_measure.get_measure(77)))

        if last_measure.get_measure(88) is not None and 'bone_mass' in self._items:
            self._items['bone_mass'](last_measure.get_measure(88), self.get_shortname())
            self.logger.debug("Plugin '{}': bone_mass - {}".format(self.get_fullname(), last_measure.get_measure(88)))

        if last_measure.get_measure(91) is not None and 'pulse_wave_velocity' in self._items:
            self._items['pulse_wave_velocity'](last_measure.get_measure(91), self.get_shortname())
            self.logger.debug(
                "Plugin '{}': pulse_wave_velocity - {}".format(self.get_fullname(), last_measure.get_measure(91)))

        if 'height' in self._items and ('bmi' in self._items or 'bmi_text' in self._items) and last_measure.get_measure(
                1) is not None:
            if self._items['height']() > 0:
                bmi = round(
                    last_measure.get_measure(1) / ((self._items['height']()) * (self._items['height']())), 2)
                if 'bmi' in self._items:
                    self._items['bmi'](bmi, self.get_shortname())
                if 'bmi_text' in self._items:
                    if bmi < 16:
                        self._items['bmi_text']('starkes Untergewicht', self.get_shortname())
                    elif 16 <= bmi < 17:
                        self._items['bmi_text']('mäßiges Untergewicht', self.get_shortname())
                    elif 17 <= bmi < 18.5:
                        self._items['bmi_text']('leichtes Untergewicht', self.get_shortname())
                    elif 18.5 <= bmi < 25:
                        self._items['bmi_text']('Normalgewicht', self.get_shortname())
                    elif 25 <= bmi < 30:
                        self._items['bmi_text']('Präadipositas (Übergewicht)', self.get_shortname())
                    elif 30 <= bmi < 35:
                        self._items['bmi_text']('Adipositas Grad I', self.get_shortname())
                    elif 35 <= bmi < 40:
                        self._items['bmi_text']('Adipositas Grad II', self.get_shortname())
                    elif 40 <= bmi:
                        self._items['bmi_text']('Adipositas Grad III', self.get_shortname())
            else:
                self.logger.error(
                    "Plugin '{}': Cannot calculate BMI: height is 0, please set height (in m) for height item manually.".format(
                        self.get_fullname()))
        else:
            self.logger.error(
                "Plugin '{}': Cannot calculate BMI: height and / or bmi item missing.".format(self.get_fullname()))

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the Nokia Health identifier and adds it to an internal array

        :param item: The item to process.
        """
        # items specific to call monitor
        if self.get_iattr_value(item.conf, 'withings_type') in ['weight', 'height', 'fat_free_mass', 'fat_mass_weight',
                                                                'fat_ratio', 'fat_mass_weight',
                                                                'diastolic_blood_pressure',
                                                                'systolic_blood_pressure', 'heart_pulse', 'temperature',
                                                                'spo2', 'body_temperature', 'skin_temperature',
                                                                'muscle_mass',
                                                                'hydration', 'bone_mass', 'pulse_wave_velocity', 'bmi',
                                                                'bmi_text', 'access_token', 'token_expiry',
                                                                'token_type',
                                                                'refresh_token']:
            self._items[self.get_iattr_value(item.conf, 'withings_type')] = item

    def get_items(self):
        return self._items

    def get_item(self, key):
        return self._items[key]

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
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_fullname()))
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
        self._creds = None
        self._auth = None

        self.tplenv = self.init_template_environment()

    def _get_callback_url(self):
        ip = self.plugin.mod_http.get_local_ip_address()
        port = self.plugin.mod_http.get_local_port()
        web_ifs = self.plugin.mod_http.get_webifs_for_plugin(self.plugin.get_shortname())
        for web_if in web_ifs:
            if web_if['Instance'] == self.plugin.get_instance_name():
                callback_url = "http://{}:{}{}".format(ip, port, web_if['Mount'])
                self.logger.debug("Plugin '{}': WebIf found, callback is {}".format(self.plugin.get_fullname(),
                                                                                    callback_url))
            return callback_url
        self.logger.error("Plugin '{}': Callback URL cannot be established.".format(self.plugin.get_fullname()))

    @cherrypy.expose
    def index(self, reload=None, state=None, code=None, error=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        if self._auth is None:
            self._auth = NokiaAuth(
                self.plugin._client_id,
                self.plugin._consumer_secret,
                callback_uri=self._get_callback_url(),
                scope='user.info,user.metrics,user.activity'
            )

        if not reload and code:
            self.logger.debug("Plugin '{}': Got code as callback: {}".format(self.plugin.get_fullname(), code))
            credentials = None
            try:
                credentials = self._auth.get_credentials(code)
            except Exception as e:
                self.logger.error(
                    "Plugin '{}': An error occurred, perhaps code parameter is invalid or too old? Message: {}".format(
                        self.plugin.get_fullname(), str(e)))
            if credentials is not None:
                self._creds = credentials
                self.logger.debug(
                    "Plugin '{}': New credentials are: access_token {}, token_expiry {}, token_type {}, refresh_token {}".
                        format(self.plugin.get_fullname(), self._creds.access_token, self._creds.token_expiry,
                               self._creds.token_type, self._creds.refresh_token))
                self.plugin.get_item('access_token')(self._creds.access_token)
                self.plugin.get_item('token_expiry')(self._creds.token_expiry)
                self.plugin.get_item('token_type')(self._creds.token_type)
                self.plugin.get_item('refresh_token')(self._creds.refresh_token)

                self.plugin._client = None

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           interface=None, item_count=len(self.plugin.get_items()),
                           plugin_info=self.plugin.get_info(), tabcount=2, callback_url=self._get_callback_url(),
                           tab1title="Withings Health Items (%s)" % len(self.plugin.get_items()),
                           tab2title="OAuth2 Data", authorize_url=self._auth.get_authorize_url(),
                           p=self.plugin, token_expiry=datetime.datetime.fromtimestamp(self.plugin.get_item(
                'token_expiry')(), tz=self.plugin.shtime.tzinfo()), now=self.plugin.shtime.now(), code=code,
                           state=state, reload=reload, language=self.plugin.get_sh().get_defaultlanguage())
