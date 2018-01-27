#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Original SMA-EM Tool Copyright 2015 Wenger Florian    wenger@unifox.at
#  https://github.com/datenschuft/SMA-EM
#  Adaptions Copyright 2016 Marc René Frieß         rene.friess@gmail.com
#########################################################################
#
# This file is part of SmartHomeNG.
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
import socket
import time
import struct
import binascii

from lib.model.smartplugin import SmartPlugin


class SMA_EM(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.3.0.2"

    # listen to the Multicast; SMA-Energymeter sends its measurements to 239.12.255.254:9522
    MCAST_GRP = '239.12.255.254'
    MCAST_PORT = 9522

    def __init__(self, smarthome, serial, time_sleep=5):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param smarthome:  The instance of the smarthome object, save it for later references
        :param serial: Serial of the SMA Energy Meter
        :param time_sleep: The time in seconds to sleep after a multicast was received
        """
        self._sh = smarthome
        self.logger = logging.getLogger(__name__)
        self._items = {}
        self._time_sleep = int(time_sleep)
        self._serial = serial

        # prepare listen to socket-Multicast
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.MCAST_PORT))
        mreq = struct.pack("4sl", socket.inet_aton(self.MCAST_GRP), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    def run(self):
        """
        Run method for the plugin
        """
        self.alive = True

        while self.alive:
            emparts = self.readem()
            if self._serial == format(emparts['serial']):
                if 'pregard' in self._items:
                    self._items['pregard'](emparts['pregard'])
                if 'pregardcounter' in self._items:
                    self._items['pregardcounter'](emparts['pregardcounter'])
                if 'psurplus' in self._items:
                    self._items['psurplus'](emparts['psurplus'])
                if 'psurpluscounter' in self._items:
                    self._items['psurpluscounter'](emparts['psurpluscounter'])

                if 'sregard' in self._items:
                    self._items['sregard'](emparts['sregard'])
                if 'sregardcounter' in self._items:
                    self._items['sregardcounter'](emparts['sregardcounter'])
                if 'ssurplus' in self._items:
                    self._items['ssurplus'](emparts['ssurplus'])
                if 'ssurpluscounter' in self._items:
                    self._items['ssurpluscounter'](emparts['ssurpluscounter'])

                if 'qregard' in self._items:
                    self._items['qregard'](emparts['qregard'])
                if 'qregardcounter' in self._items:
                    self._items['qregardcounter'](emparts['qregardcounter'])
                if 'qsurplus' in self._items:
                    self._items['qsurplus'](emparts['qsurplus'])
                if 'qsurpluscounter' in self._items:
                    self._items['qsurpluscounter'](emparts['qsurpluscounter'])

                if 'cosphi' in self._items:
                    self._items['cosphi'](emparts['cosphi'])

                if 'p1regard' in self._items:
                    self._items['p1regard'](emparts['p1regard'])
                if 'p1regardcounter' in self._items:
                    self._items['p1regardcounter'](emparts['p1regardcounter'])
                if 'p1surplus' in self._items:
                    self._items['p1surplus'](emparts['p1surplus'])
                if 'p1surpluscounter' in self._items:
                    self._items['p1surpluscounter'](emparts['p1surpluscounter'])

                if 's1regard' in self._items:
                    self._items['s1regard'](emparts['s1regard'])
                if 's1regardcounter' in self._items:
                    self._items['s1regardcounter'](emparts['s1regardcounter'])
                if 's1surplus' in self._items:
                    self._items['s1surplus'](emparts['s1surplus'])
                if 's1surpluscounter' in self._items:
                    self._items['s1surpluscounter'](emparts['s1surpluscounter'])

                if 'q1regard' in self._items:
                    self._items['q1regard'](emparts['q1regard'])
                if 'q1regardcounter' in self._items:
                    self._items['q1regardcounter'](emparts['q1regardcounter'])
                if 'q1surplus' in self._items:
                    self._items['q1surplus'](emparts['q1surplus'])
                if 'q1surpluscounter' in self._items:
                    self._items['q1surpluscounter'](emparts['q1surpluscounter'])

                if 'v1' in self._items:
                    self._items['v1'](emparts['v1'])
                if 'thd1' in self._items:
                    self._items['thd1'](emparts['thd1'])
                if 'cosphi1' in self._items:
                    self._items['cosphi1'](emparts['cosphi1'])

                if 'p2regard' in self._items:
                    self._items['p2regard'](emparts['p2regard'])
                if 'p2regardcounter' in self._items:
                    self._items['p2regardcounter'](emparts['p2regardcounter'])
                if 'p2surplus' in self._items:
                    self._items['p2surplus'](emparts['p2surplus'])
                if 'p2surpluscounter' in self._items:
                    self._items['p2surpluscounter'](emparts['p2surpluscounter'])

                if 's2regard' in self._items:
                    self._items['s2regard'](emparts['s2regard'])
                if 's2regardcounter' in self._items:
                    self._items['s2regardcounter'](emparts['s2regardcounter'])
                if 's2surplus' in self._items:
                    self._items['s2surplus'](emparts['s2surplus'])
                if 's2surpluscounter' in self._items:
                    self._items['s2surpluscounter'](emparts['s2surpluscounter'])

                if 'q2regard' in self._items:
                    self._items['q2regard'](emparts['q2regard'])
                if 'q2regardcounter' in self._items:
                    self._items['q2regardcounter'](emparts['q2regardcounter'])
                if 'q2surplus' in self._items:
                    self._items['q2surplus'](emparts['q2surplus'])
                if 'q2surpluscounter' in self._items:
                    self._items['q2surpluscounter'](emparts['q2surpluscounter'])

                if 'v2' in self._items:
                    self._items['v2'](emparts['v2'])
                if 'thd2' in self._items:
                    self._items['thd2'](emparts['thd2'])
                if 'cosphi2' in self._items:
                    self._items['cosphi2'](emparts['cosphi2'])

                if 'p3regard' in self._items:
                    self._items['p3regard'](emparts['p3regard'])
                if 'p3regardcounter' in self._items:
                    self._items['p3regardcounter'](emparts['p3regardcounter'])
                if 'p3surplus' in self._items:
                    self._items['p3surplus'](emparts['p3surplus'])
                if 'p3surpluscounter' in self._items:
                    self._items['p3surpluscounter'](emparts['p3surpluscounter'])

                if 's3regard' in self._items:
                    self._items['s3regard'](emparts['s3regard'])
                if 's3regardcounter' in self._items:
                    self._items['s3regardcounter'](emparts['s3regardcounter'])
                if 's3surplus' in self._items:
                    self._items['s3surplus'](emparts['s3surplus'])
                if 's3surpluscounter' in self._items:
                    self._items['s3surpluscounter'](emparts['s3surpluscounter'])

                if 'q3regard' in self._items:
                    self._items['q3regard'](emparts['q3regard'])
                if 'q3regardcounter' in self._items:
                    self._items['q3regardcounter'](emparts['q3regardcounter'])
                if 'q3surplus' in self._items:
                    self._items['q3surplus'](emparts['q3surplus'])
                if 'q3surpluscounter' in self._items:
                    self._items['q3surpluscounter'](emparts['q3surpluscounter'])

                if 'v3' in self._items:
                    self._items['v3'](emparts['v3'])
                if 'thd3' in self._items:
                    self._items['thd3'](emparts['thd3'])
                if 'cosphi3' in self._items:
                    self._items['cosphi3'](emparts['cosphi3'])

            time.sleep(self._time_sleep)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        Selects each item corresponding to its attribute keywords and adds it to an internal array

        :param item: The item to process.
        """
        if self.has_iattr(item.conf, 'sma_em_data_type'):
            self._items[self.get_iattr_value(item.conf, 'sma_em_data_type')] = item

    def hex2dec(self, s):
        """
        Return the integer value of a hexadecimal string s

        :param string: Hexadecimal string s
        :return int: Integer value of hexadecimal string
        """
        return int(s, 16)

    def readem(self):
        """
        Splits the multicast message into the available data

        :return emparts: dict with all available data of a multicast
        """
        smainfo = self.sock.recv(600)
        smainfoasci = binascii.b2a_hex(smainfo)

        # split the received message to separate vars
        # summary
        # regard/Bezug=getting energy from main grid
        # surplus/surplus=putting energy to the main grid

        smaserial = self.hex2dec(smainfoasci[40:48])
        pregard = self.hex2dec(smainfoasci[64:72]) / 10
        pregardcounter = self.hex2dec(smainfoasci[80:96]) / 3600000
        psurplus = self.hex2dec(smainfoasci[104:112]) / 10
        psurpluscounter = self.hex2dec(smainfoasci[120:136]) / 3600000
        qregard = self.hex2dec(smainfoasci[144:152]) / 10
        qregardcounter = self.hex2dec(smainfoasci[160:176]) / 3600000
        qsurplus = self.hex2dec(smainfoasci[184:192]) / 10
        qsurpluscounter = self.hex2dec(smainfoasci[200:216]) / 3600000
        sregard = self.hex2dec(smainfoasci[224:232]) / 10
        sregardcounter = self.hex2dec(smainfoasci[240:256]) / 3600000
        ssurplus = self.hex2dec(smainfoasci[264:272]) / 10
        ssurpluscounter = self.hex2dec(smainfoasci[280:296]) / 3600000
        cosphi = self.hex2dec(smainfoasci[304:312]) / 1000
        # L1
        p1regard = self.hex2dec(smainfoasci[320:328]) / 10
        p1regardcounter = self.hex2dec(smainfoasci[336:352]) / 3600000
        p1surplus = self.hex2dec(smainfoasci[360:368]) / 10
        p1surpluscounter = self.hex2dec(smainfoasci[376:392]) / 3600000
        q1regard = self.hex2dec(smainfoasci[400:408]) / 10
        q1regardcounter = self.hex2dec(smainfoasci[416:432]) / 3600000
        q1surplus = self.hex2dec(smainfoasci[440:448]) / 10
        q1surpluscounter = self.hex2dec(smainfoasci[456:472]) / 3600000
        s1regard = self.hex2dec(smainfoasci[480:488]) / 10
        s1regardcounter = self.hex2dec(smainfoasci[496:512]) / 3600000
        s1surplus = self.hex2dec(smainfoasci[520:528]) / 10
        s1surpluscounter = self.hex2dec(smainfoasci[536:552]) / 3600000
        thd1 = self.hex2dec(smainfoasci[560:568]) / 1000
        v1 = self.hex2dec(smainfoasci[576:584]) / 1000
        cosphi1 = self.hex2dec(smainfoasci[592:600]) / 1000
        # L2
        p2regard = self.hex2dec(smainfoasci[608:616]) / 10
        p2regardcounter = self.hex2dec(smainfoasci[624:640]) / 3600000
        p2surplus = self.hex2dec(smainfoasci[648:656]) / 10
        p2surpluscounter = self.hex2dec(smainfoasci[664:680]) / 3600000
        q2regard = self.hex2dec(smainfoasci[688:696]) / 10
        q2regardcounter = self.hex2dec(smainfoasci[704:720]) / 3600000
        q2surplus = self.hex2dec(smainfoasci[728:736]) / 10
        q2surpluscounter = self.hex2dec(smainfoasci[744:760]) / 3600000
        s2regard = self.hex2dec(smainfoasci[768:776]) / 10
        s2regardcounter = self.hex2dec(smainfoasci[784:800]) / 3600000
        s2surplus = self.hex2dec(smainfoasci[808:816]) / 10
        s2surpluscounter = self.hex2dec(smainfoasci[824:840]) / 3600000
        thd2 = self.hex2dec(smainfoasci[848:856]) / 1000
        v2 = self.hex2dec(smainfoasci[864:872]) / 1000
        cosphi2 = self.hex2dec(smainfoasci[880:888]) / 1000
        # L3
        p3regard = self.hex2dec(smainfoasci[896:904]) / 10

        p3regardcounter = self.hex2dec(smainfoasci[912:928]) / 3600000
        p3surplus = self.hex2dec(smainfoasci[936:944]) / 10
        p3surpluscounter = self.hex2dec(smainfoasci[952:968]) / 3600000
        q3regard = self.hex2dec(smainfoasci[976:984]) / 10
        q3regardcounter = self.hex2dec(smainfoasci[992:1008]) / 3600000
        q3surplus = self.hex2dec(smainfoasci[1016:1024]) / 10
        q3surpluscounter = self.hex2dec(smainfoasci[1032:1048]) / 3600000
        s3regard = self.hex2dec(smainfoasci[1056:1064]) / 10
        s3regardcounter = self.hex2dec(smainfoasci[1072:1088]) / 3600000
        s3surplus = self.hex2dec(smainfoasci[1096:1104]) / 10
        s3surpluscounter = self.hex2dec(smainfoasci[1112:1128]) / 3600000
        thd3 = self.hex2dec(smainfoasci[1136:1144]) / 1000
        v3 = self.hex2dec(smainfoasci[1152:1160]) / 1000
        cosphi3 = self.hex2dec(smainfoasci[1168:1176]) / 1000

        # Returning values
        emparts = {'serial': smaserial, 'pregard': pregard, 'pregardcounter': pregardcounter, 'psurplus': psurplus,
                   'psurpluscounter': psurpluscounter,
                   'sregard': sregard, 'sregardcounter': sregardcounter, 'ssurplus': ssurplus,
                   'ssurpluscounter': ssurpluscounter,
                   'qregard': qregard, 'qregardcounter': qregardcounter, 'qsurplus': qsurplus,
                   'qsurpluscounter': qsurpluscounter,
                   'cosphi': cosphi,
                   'p1regard': p1regard, 'p1regardcounter': p1regardcounter, 'p1surplus': p1surplus,
                   'p1surpluscounter': p1surpluscounter,
                   's1regard': s1regard, 's1regardcounter': s1regardcounter, 's1surplus': s1surplus,
                   's1surpluscounter': s1surpluscounter,
                   'q1regard': q1regard, 'q1regardcounter': q1regardcounter, 'q1surplus': q1surplus,
                   'q1surpluscounter': q1surpluscounter,
                   'v1': v1, 'thd1': thd1, 'cosphi1': cosphi1,
                   'p2regard': p2regard, 'p2regardcounter': p2regardcounter, 'p2surplus': p2surplus,
                   'p2surpluscounter': p2surpluscounter,
                   's2regard': s2regard, 's2regardcounter': s2regardcounter, 's2surplus': s2surplus,
                   's2surpluscounter': s2surpluscounter,
                   'q2regard': q2regard, 'q2regardcounter': q2regardcounter, 'q2surplus': q2surplus,
                   'q2surpluscounter': q2surpluscounter,
                   'v2': v2, 'thd2': thd2, 'cosphi2': cosphi2,
                   'p3regard': p3regard, 'p3regardcounter': p3regardcounter, 'p3surplus': p3surplus,
                   'p3surpluscounter': p3surpluscounter,
                   's3regard': s3regard, 's3regardcounter': s3regardcounter, 's3surplus': s3surplus,
                   's3surpluscounter': s3surpluscounter,
                   'q3regard': q3regard, 'q3regardcounter': q3regardcounter, 'q3surplus': q3surplus,
                   'q3surpluscounter': q3surpluscounter,
                   'v3': v3, 'thd3': thd3, 'cosphi3': cosphi3}
        return emparts

    def get_items(self):
        return self._items
