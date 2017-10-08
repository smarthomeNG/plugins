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

import logging
import requests
from lib.model.smartplugin import SmartPlugin

class NokiaHealth(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.3.1"
    BASE_URL = "http://api.health.nokia.com/"
    ALLOWED_MEASURE_TYPES = [1, 4, 5, 6, 8, 11]

    # see https://developer.health.nokia.com/api/doc

    def __init__(self, smarthome, oauth_consumer_key, oauth_nonce, oauth_signature, oauth_token, userid, cycle=300):
        self.logger = logging.getLogger(__name__)
        self._sh = smarthome
        self._oauth_consumer_key = oauth_consumer_key
        self._oauth_nonce = oauth_nonce
        self._oauth_signature = oauth_signature
        self._oauth_token = oauth_token
        self._userid = userid
        self._cycle = cycle
        self._items = {}

    def run(self):
        self.alive = True
        self._sh.scheduler.add(__name__, self._update_loop, cycle=self._cycle)

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
        if 'last_update' not in self._items:
            self.logger.error("Cannot update measure values, last_update item is missing!")
            return

        if 'weight' not in self._items:
            self.logger.error("Cannot update measure values, weight item is missing!")
            return

        last_measure = self.get_last_measure()

        if 'weight' in last_measure and self._items['last_update']() < last_measure['date']:
            self.logger.debug(last_measure)
            self._items['weight'](last_measure['weight'])
            self._items['last_update'](last_measure['date'])
            if 'height' in last_measure and 'height' in self._items:
                self._items['height'](last_measure['height'])

            if 'height' in self._items and 'bmi' in self._items:
                if self._items['height']() > 0:
                    bmi = round(
                        last_measure['weight'] / ((self._items['height']()) * (self._items['height']())), 2)
                    self._items['bmi'](bmi)
                else:
                    self.logger.error(
                        "Cannot calculate BMI: height is 0, please set height (in m) for height item manually.")
            else:
                self.logger.error("Cannot calculate BMI: height and / or bmi item missing.")

            if 'fat_ratio' in last_measure and 'fat_ratio' in self._items:
                self._items['fat_ratio'](last_measure['fat_ratio'])

            if 'fat_free_mass' in last_measure and 'fat_free_mass' in self._items:
                self._items['fat_free_mass'](last_measure['fat_free_mass'])

            if 'fat_mass_weight' in last_measure and 'fat_mass_weight' in self._items:
                self._items['fat_mass_weight'](last_measure['fat_mass_weight'])

            if 'heart_pulse' in last_measure and 'heart_pulse' in self._items:
                self._items['heart_pulse'](last_measure['heart_pulse'])
        else:
            self.logger.debug("No update - no weight data or no new values since last update!")

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the Nokia Health identifier and adds it to an internal array

        :param item: The item to process.
        """
        # items specific to call monitor
        if self.get_iattr_value(item.conf, 'nh_type') in ['weight', 'height', 'bmi', 'fat_ratio', 'fat_free_mass',
                                                          'fat_mass_weight', 'heart_pulse', 'last_update']:
            self._items[self.get_iattr_value(item.conf, 'nh_type')] = item

    def get_last_measure(self):
        measure_url = self.BASE_URL + "measure?action=getmeas&oauth_consumer_key=%s&oauth_nonce=%s&oauth_signature=%s&oauth_signature_method=HMAC-SHA1&oauth_token=%s&oauth_version=1.0&userid=%s&limit=10" % (
            self._oauth_consumer_key, self._oauth_nonce, self._oauth_signature, self._oauth_token, self._userid)
        response = requests.get(measure_url)
        json = response.json()

        result = {}
        if json['status'] == 0:
            body = json['body']
            measuregrps = body['measuregrps']
            date = measuregrps[0]['date']
            result['date'] = date

            for mgrp in measuregrps:
                if date != mgrp['date']:
                    break

                for m in mgrp['measures']:
                    if m['type'] in self.ALLOWED_MEASURE_TYPES:
                        if m['type'] == 1:
                            result['weight'] = m['value'] * pow(10, m['unit'])
                        elif m['type'] == 4:
                            result['height'] = m['value'] * pow(10, m['unit'])
                        elif m['type'] == 5:
                            result['fat_free_mass'] = m['value'] * pow(10, m['unit'])
                        elif m['type'] == 6:
                            result['fat_ratio'] = m['value'] * pow(10, m['unit'])
                        elif m['type'] == 8:
                            result['fat_mass_weight'] = m['value'] * pow(10, m['unit'])
                        elif m['type'] == 11:
                            result['heart_pulse'] = m['value'] * pow(10, m['unit'])
                    else:
                        self.logger.error('Measure Type %s currently not supported' % m['type'])
        else:
            self.logger.error('Status: %s' % json['status'])

        return result
        # Status Codes:
        #  0 : Operation was successful
        # 247 : The userid provided is absent, or incorrect
        # 250 : The provided userid and/or Oauth credentials do not match
        # 283 : Token is invalid or doesn't exist
        # 286 : No such subscription was found
        # 293 : The callback URL is either absent or incorrect
        # 294 : No such subscription could be deleted
        # 304 : The comment is either absent or incorrect
        # 305 : Too many notifications are already set
        # 328: The user is deactivated
        # 342 : The signature (using Oauth) is invalid
        # 343 : Wrong Notification Callback Url don't exist
        # 601 : Too Many Request
        # 2554 : Wrong action or wrong webservice
        # 2555 : An unknown error occurred
        # 2556 : Service is not defined