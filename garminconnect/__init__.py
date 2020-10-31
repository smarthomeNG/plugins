#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019 Marc René Frieß                   rene.friess@gmail.com
#  The Plugin uses parts of the source code of the garminconnect pypi
#  package, without directly using the package. Thanks therefore go to
#  Ron Klinkien, the developer!
#########################################################################
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
import re
from lib.model.smartplugin import *

BASE_URL = 'https://connect.garmin.com'
SSO_URL = 'https://sso.garmin.com/sso'
MODERN_URL = 'https://connect.garmin.com/modern'
SIGNIN_URL = 'https://sso.garmin.com/sso/signin'


class GarminConnect(SmartPlugin):
    """
    Retrieves Garmin Connect Stats and Heart Rates.
    """
    PLUGIN_VERSION = "1.0.0"
    url_activities = MODERN_URL + '/proxy/usersummary-service/usersummary/daily/'
    url_heartrates = MODERN_URL + '/proxy/wellness-service/wellness/dailyHeartRate/'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36',
        'origin': 'https://sso.garmin.com'
    }

    def __init__(self, sh, *args, **kwargs):
        # Call init code of parent class (SmartPlugin or MqttPlugin)
        super().__init__()

        self._shtime = Shtime.get_instance()
        self._email = self.get_parameter_value("email")
        self._password = self.get_parameter_value("password")
        self._session = requests.session()
        self._login(self._email, self._password)

        self.init_webinterface()

    def run(self):
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False

    def parse_item(self, item):
        pass

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        pass

    def _login(self, username, password):
        """
        Login to portal
        """
        params = {
            'webhost': BASE_URL,
            'service': MODERN_URL,
            'source': SIGNIN_URL,
            'redirectAfterAccountLoginUrl': MODERN_URL,
            'redirectAfterAccountCreationUrl': MODERN_URL,
            'gauthHost': SSO_URL,
            'locale': 'en_US',
            'id': 'gauth-widget',
            'cssUrl': 'https://static.garmincdn.com/com.garmin.connect/ui/css/gauth-custom-v1.2-min.css',
            'clientId': 'GarminConnect',
            'rememberMeShown': 'true',
            'rememberMeChecked': 'false',
            'createAccountShown': 'true',
            'openCreateAccount': 'false',
            'usernameShown': 'false',
            'displayNameShown': 'false',
            'consumeServiceTicket': 'false',
            'initialFocus': 'true',
            'embedWidget': 'false',
            'generateExtraServiceTicket': 'false'
        }

        data = {
            'username': username,
            'password': password,
            'embed': 'true',
            'lt': 'e1s1',
            '_eventId': 'submit',
            'displayNameRequired': 'false'
        }

        response = self._session.post(SIGNIN_URL, headers=self.headers, params=params, data=data)
        response.raise_for_status()

        response_url = re.search(r'"(https:[^"]+?ticket=[^"]+)"', response.text)
        if not response_url:
            raise Exception('Could not find response URL')
        response_url = re.sub(r'\\', '', response_url.group(1))
        response = self._session.get(response_url)

        self.user_prefs = self.parse_json(response.text, 'VIEWER_USERPREFERENCES')
        self.display_name = self.user_prefs['displayName']
        response.raise_for_status()

    def parse_json(self, html, key):
        """
        Find and return json data
        """
        found = re.search(key + r" = JSON.parse\(\"(.*)\"\);", html, re.M)
        if found:
            text = found.group(1).replace('\\"', '"')
            return json.loads(text)

    def get_stats(self, date_str=None):
        date = self._get_date(date_str)
        stats = self._fetch_stats(date.strftime('%Y-%m-%d'))
        return stats

    def get_heart_rates(self, date_str=None):
        date = self._get_date(date_str)
        heart_rates = self._fetch_heart_rates(date.strftime('%Y-%m-%d'))
        return heart_rates

    def _get_date(self, date_str):
        if date_str is not None:
            date = self._shtime.datetime_transform(date_str)
        else:
            date = self._shtime.now()
        return date

    def _fetch_stats(self, cdate):  # cDate = 'YYY-mm-dd'
        """
        Fetch available activity data
        """
        getURL = self.url_activities + self.display_name + '?' + 'calendarDate=' + cdate

        try:
            response = self._session.get(getURL, headers=self.headers)
            if response.status_code == 429:
                raise GarminConnectTooManyRequestsError("Too many requests")

            self.logger.debug("Statistics response code %s", response.status_code)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self.logger.error("Exception occured during stats retrieval: %s" % e)
            raise GarminConnectConnectionError("Error connecting") from err

        if response.json()['privacyProtected'] is True:
            self.logger.info(
                "Session expired - trying relogin.")
            self._login(self._email, self._password)
            try:
                response = self._session.get(getURL, headers=self.headers)
                if response.status_code == 429:
                    raise GarminConnectTooManyRequestsError("Too many requests")

                self.logger.debug("Statistics response code %s", response.status_code)
                response.raise_for_status()

            except requests.exceptions.HTTPError as e:
                self.logger.error("Exception occured during stats retrieval: %s" % e)
                raise GarminConnectConnectionError("Error connecting") from err

        return response.json()

    def _fetch_heart_rates(self, cdate):  # cDate = 'YYYY-mm-dd'
        """
        Fetch available heart rates data
        """
        getURL = self.url_heartrates + self.display_name + '?date=' + cdate
        try:
            response = self._session.get(getURL, headers=self.headers)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self.logger.info(
                "Exception occured during heart rate retrieval - perhaps session expired - trying relogin: %s" % e)
            self._login(self._email, self._password)
            try:
                response = self._session.get(getURL, headers=self.headers)
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                self.logger.error("Exception occured during stats retrieval, relogin without effect: %s" % e)
                return
        return response.json()

    def init_webinterface(self):
        """
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
import json
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
    def index(self, reload=None, day=None, month=None, year=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           interface=None, plugin_info=self.plugin.get_info(), tabcount=3, now=self.plugin.shtime.now(),
                           day=day, month=month, year=year, p=self.plugin)
