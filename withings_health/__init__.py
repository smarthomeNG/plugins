#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2017-2021 Marc René Frieß            rene.friess(a)gmail.com
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.5 and
#  upwards.
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
from oauthlib.oauth2.rfc6749.errors import MissingTokenError
from typing_extensions import Final
from withings_api import AuthScope, WithingsApi, WithingsAuth
from withings_api.common import Credentials, CredentialsType, get_measure_value, MeasureType
from .webif import WebInterface

class WithingsHealth(SmartPlugin):
    PLUGIN_VERSION = "1.8.1"

    def __init__(self, sh):
        super().__init__()
        self.shtime = Shtime.get_instance()
        self._user_id = self.get_parameter_value('user_id')
        self._client_id = self.get_parameter_value('client_id')
        self._consumer_secret = self.get_parameter_value('consumer_secret')
        self._cycle = self.get_parameter_value('cycle')
        self._creds = None
        self._client = None
        self._items = {}

        if not self.init_webinterface(WebInterface):
            self._init_complete = False

    def run(self):
        self.alive = True
        self.scheduler_add('poll_data', self._update_loop, cycle=self._cycle)

    def stop(self):
        self.scheduler_remove('poll_data')
        self.alive = False

    def _store_tokens(self, credentials2):
        self.logger.debug(
            "Updating tokens to items: access_token - {} token_expiry - {} token_type - {} refresh_token - {}".
                format(credentials2.access_token, credentials2.expires_in, credentials2.token_type,
                       credentials2.refresh_token))
        self.get_item('access_token')(credentials2.access_token)
        self.get_item('token_expiry')(
            int((datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds()) + int(
                credentials2.expires_in))
        self.get_item('token_type')(credentials2.token_type)
        self.get_item('refresh_token')(credentials2.refresh_token)

    def _update_loop(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug("Starting update loop")
        if not self.alive:
            return

        self._update()

    def _update(self):
        """
        Updates information on diverse items
        """

        if 'access_token' not in self.get_items() or 'token_expiry' not in self.get_items() or 'token_type' not in self.get_items() or 'refresh_token' not in self.get_items():
            self.logger.error(
                "Mandatory Items for OAuth2 Data do not exist. Verify that you have items with withings_type: token_expiry, token_type, refresh_token and access_token in your item tree.")
            return

        if self._client is None:
            if self.get_item('access_token')() and self.get_item(
                    'token_expiry')() > 0 and self.get_item(
                'token_type')() and self.get_item('refresh_token')():

                if (self.shtime.now() < datetime.datetime.fromtimestamp(self.get_item(
                        'token_expiry')(), tz=self.shtime.tzinfo())):
                    self.logger.debug(
                        "Token is valid, will expire on {}.".format(
                            datetime.datetime.fromtimestamp(self.get_item(
                                'token_expiry')(), tz=self.shtime.tzinfo()).strftime('%d.%m.%Y %H:%M:%S')))
                    self.logger.debug(
                        "Initializing NokiaCredentials: access_token - {} token_expiry - {} token_type - {} refresh_token - {} user_id - {} client_id - {} consumer_secret - {}".
                            format(self.get_item('access_token')(),
                                   self.get_item('token_expiry')(),
                                   self.get_item('token_type')(),
                                   self.get_item('refresh_token')(),
                                   self._user_id,
                                   self._client_id,
                                   self._consumer_secret))
                    self._creds = Credentials(
                        access_token=self.get_item('access_token')(),
                        token_expiry=self.get_item('token_expiry')(),
                        token_type=self.get_item('token_type')(),
                        refresh_token=self.get_item('refresh_token')(),
                        userid=self._user_id,
                        client_id=self._client_id,
                        consumer_secret=self._consumer_secret)
                    self._client = WithingsApi(self._creds, refresh_cb=self._store_tokens)
                else:
                    self.logger.error(
                        "Token is expired, run OAuth2 again from Web Interface (Expiry Date: {}).".format(
                            datetime.datetime.fromtimestamp(self.get_item(
                                'token_expiry')(), tz=self.shtime.tzinfo()).strftime('%d.%m.%Y %H:%M:%S')))
                    return
            else:
                self.logger.error(
                    "Items for OAuth2 Data are not set with required values. Please run process via WebGUI of the plugin.")
                return
        try:
            measures = self._client.measure_get_meas(startdate=None, enddate=None, lastupdate=None)
        except Exception as e:
            self.logger.error(
                "An exception occured when running measure_get_meas(): {}. Aborting update.".format(
                    str(e)))
            return

        if get_measure_value(measures,
                             with_measure_type=MeasureType.HEART_RATE) is not None and 'heart_rate' in self._items:
            self._items['heart_rate'](get_measure_value(measures, with_measure_type=MeasureType.HEART_RATE),
                                      self.get_shortname())
            self.logger.debug(
                "heart_rate - {}".format(get_measure_value(measures, with_measure_type=MeasureType.HEART_RATE)))

        if get_measure_value(measures, with_measure_type=MeasureType.WEIGHT) is not None and 'weight' in self._items:
            self._items['weight'](get_measure_value(measures, with_measure_type=MeasureType.WEIGHT),
                                  self.get_shortname())
            self.logger.debug("weight - {}".format(get_measure_value(measures, with_measure_type=MeasureType.WEIGHT)))

        if get_measure_value(measures, with_measure_type=MeasureType.HEIGHT) is not None and 'height' in self._items:
            self._items['height'](get_measure_value(measures, with_measure_type=MeasureType.HEIGHT),
                                  self.get_shortname())
            self.logger.debug("height - {}".format(get_measure_value(measures, with_measure_type=MeasureType.HEIGHT)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.FAT_FREE_MASS) is not None and 'fat_free_mass' in self._items:
            self._items['fat_free_mass'](get_measure_value(measures, with_measure_type=MeasureType.FAT_FREE_MASS),
                                         self.get_shortname())
            self.logger.debug(
                "fat_free_mass - {}".format(get_measure_value(measures, with_measure_type=MeasureType.FAT_FREE_MASS)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.FAT_RATIO) is not None and 'fat_ratio' in self._items:
            self._items['fat_ratio'](get_measure_value(measures, with_measure_type=MeasureType.FAT_RATIO),
                                     self.get_shortname())
            self.logger.debug(
                "fat_ratio - {}".format(get_measure_value(measures, with_measure_type=MeasureType.FAT_RATIO)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.FAT_MASS_WEIGHT) is not None and 'fat_mass_weight' in self._items:
            self._items['fat_mass_weight'](get_measure_value(measures, with_measure_type=MeasureType.FAT_MASS_WEIGHT),
                                           self.get_shortname())
            self.logger.debug(
                "fat_mass_weight - {}".format(
                    get_measure_value(measures, with_measure_type=MeasureType.FAT_MASS_WEIGHT)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.DIASTOLIC_BLOOD_PRESSURE) is not None and 'diastolic_blood_pressure' in self._items:
            self._items['diastolic_blood_pressure'](
                get_measure_value(measures, with_measure_type=MeasureType.DIASTOLIC_BLOOD_PRESSURE),
                self.get_shortname())
            self.logger.debug(
                "diastolic_blood_pressure - {}".format(
                    get_measure_value(measures, with_measure_type=MeasureType.DIASTOLIC_BLOOD_PRESSURE)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.SYSTOLIC_BLOOD_PRESSURE) is not None and 'systolic_blood_pressure' in self._items:
            self._items['systolic_blood_pressure'](
                get_measure_value(measures, with_measure_type=MeasureType.SYSTOLIC_BLOOD_PRESSURE),
                self.get_shortname())
            self.logger.debug(
                "systolic_blood_pressure - {}".format(
                    get_measure_value(measures, with_measure_type=MeasureType.SYSTOLIC_BLOOD_PRESSURE)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.TEMPERATURE) is not None and 'temperature' in self._items:
            self._items['temperature'](get_measure_value(measures, with_measure_type=MeasureType.TEMPERATURE),
                                       self.get_shortname())
            self.logger.debug(
                "temperature - {}".format(get_measure_value(measures, with_measure_type=MeasureType.TEMPERATURE)))

        if get_measure_value(measures, with_measure_type=MeasureType.SP02) is not None and 'spo2' in self._items:
            self._items['spo2'](get_measure_value(measures, with_measure_type=MeasureType.SP02), self.get_shortname())
            self.logger.debug("spo2 - {}".format(get_measure_value(measures, with_measure_type=MeasureType.SP02)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.BODY_TEMPERATURE) is not None and 'body_temperature' in self._items:
            self._items['body_temperature'](get_measure_value(measures, with_measure_type=MeasureType.BODY_TEMPERATURE),
                                            self.get_shortname())
            self.logger.debug(
                "body_temperature - {}".format(
                    get_measure_value(measures, with_measure_type=MeasureType.BODY_TEMPERATURE)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.SKIN_TEMPERATURE) is not None and 'skin_temperature' in self._items:
            self._items['skin_temperature'](get_measure_value(measures, with_measure_type=MeasureType.SKIN_TEMPERATURE),
                                            self.get_shortname())
            self.logger.debug(
                "skin_temperature - {}".format(
                    get_measure_value(measures, with_measure_type=MeasureType.SKIN_TEMPERATURE)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.MUSCLE_MASS) is not None and 'muscle_mass' in self._items:
            self._items['muscle_mass'](get_measure_value(measures, with_measure_type=MeasureType.MUSCLE_MASS),
                                       self.get_shortname())
            self.logger.debug(
                "muscle_mass - {}".format(get_measure_value(measures, with_measure_type=MeasureType.MUSCLE_MASS)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.HYDRATION) is not None and 'hydration' in self._items:
            self._items['hydration'](get_measure_value(measures, with_measure_type=MeasureType.HYDRATION),
                                     self.get_shortname())
            self.logger.debug(
                "hydration - {}".format(get_measure_value(measures, with_measure_type=MeasureType.HYDRATION)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.BONE_MASS) is not None and 'bone_mass' in self._items:
            self._items['bone_mass'](get_measure_value(measures, with_measure_type=MeasureType.BONE_MASS),
                                     self.get_shortname())
            self.logger.debug(
                "bone_mass - {}".format(get_measure_value(measures, with_measure_type=MeasureType.BONE_MASS)))

        if get_measure_value(measures,
                             with_measure_type=MeasureType.PULSE_WAVE_VELOCITY) is not None and 'pulse_wave_velocity' in self._items:
            self._items['pulse_wave_velocity'](
                get_measure_value(measures, with_measure_type=MeasureType.PULSE_WAVE_VELOCITY), self.get_shortname())
            self.logger.debug(
                "pulse_wave_velocity - {}".format(
                    get_measure_value(measures, with_measure_type=MeasureType.PULSE_WAVE_VELOCITY)))

        if 'height' in self._items and ('bmi' in self._items or 'bmi_text' in self._items) and get_measure_value(
                measures, with_measure_type=MeasureType.WEIGHT) is not None:
            if self._items['height']() > 0:
                bmi = round(
                    get_measure_value(measures, with_measure_type=MeasureType.WEIGHT) / (
                            (self._items['height']()) * (self._items['height']())), 2)
                if 'bmi' in self._items:
                    self._items['bmi'](bmi, self.get_shortname())
                if 'bmi_text' in self._items:
                    if bmi < 16:
                        self._items['bmi_text'](self.translate('starkes Untergewicht'), self.get_shortname())
                    elif 16 <= bmi < 17:
                        self._items['bmi_text'](self.translate('mäßiges Untergewicht'), self.get_shortname())
                    elif 17 <= bmi < 18.5:
                        self._items['bmi_text'](self.translate('leichtes Untergewicht'), self.get_shortname())
                    elif 18.5 <= bmi < 25:
                        self._items['bmi_text'](self.translate('Normalgewicht'), self.get_shortname())
                    elif 25 <= bmi < 30:
                        self._items['bmi_text'](self.translate('Präadipositas (Übergewicht)'), self.get_shortname())
                    elif 30 <= bmi < 35:
                        self._items['bmi_text'](self.translate('Adipositas Grad I'), self.get_shortname())
                    elif 35 <= bmi < 40:
                        self._items['bmi_text'](self.translate('Adipositas Grad II'), self.get_shortname())
                    elif 40 <= bmi:
                        self._items['bmi_text'](self.translate('Adipositas Grad III'), self.get_shortname())
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
        if self.get_iattr_value(item.conf, 'withings_type') in ['weight', 'height', 'fat_free_mass', 'fat_mass_weight',
                                                                'fat_ratio', 'fat_mass_weight',
                                                                'diastolic_blood_pressure',
                                                                'systolic_blood_pressure', 'heart_rate', 'temperature',
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

    def get_client_id(self):
        return self._client_id

    def get_consumer_secret(self):
        return self._consumer_secret

    def get_callback_url(self):
        ip = self.mod_http.get_local_ip_address()
        port = self.mod_http.get_local_port()
        web_ifs = self.mod_http.get_webifs_for_plugin(self.get_shortname())
        for web_if in web_ifs:
            if web_if['Instance'] == self.get_instance_name():
                callback_url = "http://{}:{}{}".format(ip, port, web_if['Mount'])
                self.logger.debug("WebIf found, callback is {}".format(self.get_fullname(),
                                                                       callback_url))
            return callback_url
        self.logger.error("Callback URL cannot be established.".format(self.get_fullname()))


