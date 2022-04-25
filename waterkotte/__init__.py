#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2014- Thomas Kastner <github@mx.kastnerfamily.de>
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

import logging
from lib.model.smartplugin import SmartPlugin
import time
import re
import http.client

logger = logging.getLogger('')


class Waterkotte(SmartPlugin):

    ALLOW_MULTIINSTANCE = False

    PLUGIN_VERSION = "1.0.0"

    _key2tag = {
        'temp_aussen': 'A1',
        'temp_aussen_1h': 'A2',
        'temp_aussen_24h': 'A3',
        'temp_quelle_ein': 'A4',
        'temp_quelle_aus': 'A5',
        'temp_verdampfung': 'A6',
        'temp_sauggas': 'A7',
        'druck_verdampfung': 'A8',
        'temp_soll': 'A10',
        'temp_ruecklauf': 'A11',
        'temp_vorlauf': 'A12',
        'temp_kondensation': 'A14',
        'druck_kondensation': 'A15',
        'temp_speicher': 'A16',
        'temp_raum': 'A17',
        'temp_raum_1h': 'A18',
        'temp_ww': 'A19',
        'temp_sk': 'A24',
        'pow_comp': 'A25',
        'pow_therm': 'A26',
        'pow_cool': 'A27',
        'cop_comp': 'A28',
        'cop_cool': 'A29',
        'temp_hk': 'A30',
        'temp_gefordert_hk': 'A31',
        'temp_gefordert_ww': 'A37',
        'temp_soll_ww': 'A38',
        'rpm_hk': 'A51',
        'rpm_sole': 'A52',
        'valve_exp': 'A23',
        'jaz_wp': 'A460',
        'oh1_verdichter': 'A516',
        'oh2_verdichter': 'A517',
        'oh1_heizstab': 'A528',
        'oh2_heizstab': 'A529',
        'oh1_heizpumpe': 'A522',
        'oh2_heizpumpe': 'A523',
        'oh1_solepumpe': 'A524',
        'oh2_solepumpe': 'A525',
        'cop_jan': 'A924',
        'cop_feb': 'A925',
        'cop_mar': 'A926',
        'cop_apr': 'A927',
        'cop_may': 'A928',
        'cop_jun': 'A929',
        'cop_jul': 'A930',
        'cop_aug': 'A931',
        'cop_sep': 'A932',
        'cop_oct': 'A933',
        'cop_nov': 'A934',
        'cop_dec': 'A935',
        'f121': 'D8'
    }

    _tag_noconv = {
        'A516',
        'A517',
        'A528',
        'A529',
        'A522',
        'A523',
        'A524',
        'A525',
        'D8'
    }

    def __init__(self, smarthome, ip, user="waterkotte", passwd="waterkotte", cycle=300):
        self._sh = smarthome
        self.ip = ip
        self.user = user
        self.passwd = passwd
        self.cycle = int(cycle)
        self._items = []
        self._values = {}
        self.cycletime = 0

    def run(self):
        self.alive = True
        self._sh.scheduler.add('Waterkotte', self._refresh, cycle=self.cycle)

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        if 'waterkotte' in item.conf:
            waterkotte_key = item.conf['waterkotte']
            if waterkotte_key in self._key2tag:
                self._items.append([item, waterkotte_key])
                return self.update_item
            else:
                logger.warn('invalid key {0} configured', waterkotte_key)
        return None

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'Waterkotte':
            pass

    def _refresh(self):
        start = time.time()
        try:
            # log in to web interface, retrieve Cookie
            token = self._sh.tools.fetch_url('http://' + self.ip + '/cgi/login?username=' + self.user + '&password=' + self.passwd, timeout=10).decode()
            token = re.search('IDALToken=\w*', token)
            token = token.group(0)

            # first of all check and if required set D634 to show total consumption instead of annual
            data2 = self.fetch_url_cookie('http://' + self.ip +'/cgi/readTags?&n=1&t1=D634', token).decode()
            data2 = re.sub('#\w*\tS_OK\n\w*\t', '', data2)
            data2 = re.sub('\n', '', data2)
            # if D634 is not set, set it and skip this cycle --- note: updated readings may take 30s or longer!
            if int(data2) == 0:
                logger.error('D634 has not been set. Trying to set it and skipping this cycle.')
                data2 = self.fetch_url_cookie('http://' + self.ip +'/cgi/writeTags?&n=1&t1=D634&v1=1', token).decode()
                return

            # update all items
            for waterkotte_key in self._key2tag:

                # send request using previously aquired Cookie
                data2 = self.fetch_url_cookie('http://' + self.ip +'/cgi/readTags?&n=1&t1=' + self._key2tag[waterkotte_key], token).decode()
                data2 = re.sub('#\w*\tS_OK\n\w*\t', '', data2)
                data2 = re.sub('\n', '', data2)

                # do not convert values that are tagged as "noconv"
                if self._key2tag[waterkotte_key] in self._tag_noconv:
                    value = float(data2)
                else:
                    # analog values A### are 16 bit integers; divide by 10 to get real value
                    value = float(data2)/10

                self._values[waterkotte_key] = value
            for item_cfg in self._items:
                if item_cfg[1] in self._values:
                    item_cfg[0](self._values[item_cfg[1]], 'Waterkotte')
        except Exception as e:
            logger.error(
                'could not retrieve data from {0}: {1}'.format(self.ip, e))
        return

        cycletime = time.time() - start
        self.cycletime = cycletime
        logger.debug("cycle takes {0} seconds".format(cycletime))

    # this is fetch_url from lib/tools.py, extended to use the Cookie 'token' in the http request
    def fetch_url_cookie(self, url, token, username=None, password=None, timeout=10):
        headers = {'Accept': 'text/plain'}
        headers['Cookie'] = token
        plain = True
        if url.startswith('https'):
            plain = False
        lurl = url.split('/')
        host = lurl[2]
        purl = '/' + '/'.join(lurl[3:])
        if plain:
            conn = http.client.HTTPConnection(host, timeout=timeout)
        else:
            conn = http.client.HTTPSConnection(host, timeout=timeout)
        if username and password:
            headers['Authorization'] = ('Basic '.encode() + base64.b64encode((username + ':' + password).encode()))
        try:
            conn.request("GET", purl, headers=headers)
        except Exception as e:
            logger.warning("Problem fetching {0}: {1}".format(url, e))
            conn.close()
            return False
        resp = conn.getresponse()
        if resp.status == 200:
            content = resp.read()
        else:
            logger.warning("Problem fetching {0}: {1} {2}".format(url, resp.status, resp.reason))
            content = False
        conn.close()
        return content
