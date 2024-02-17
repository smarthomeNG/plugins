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
from lib.model.smartplugin import *
from lib.module import Modules

sma_units = {
    "W": 10,
    "VA": 10,
    "VAr": 10,
    "kWh": 3600000,
    "kVAh": 3600000,
    "kVArh": 3600000,
    "A": 1000,
    "V": 1000,
    "°": 1000,
    "Hz": 1000,
}

sma_channels = {
    # totals
    1: ('pconsume', 'W', 'kWh'),
    2: ('psupply', 'W', 'kWh'),
    3: ('qconsume', 'VAr', 'kVArh'),
    4: ('qsupply', 'VAr', 'kVArh'),
    9: ('sconsume', 'VA', 'kVAh'),
    10: ('ssupply', 'VA', 'kVAh'),
    13: ('cosphi', '°'),
    14: ('frequency', 'Hz'),
    # phase 1
    21: ('p1consume', 'W', 'kWh'),
    22: ('p1supply', 'W', 'kWh'),
    23: ('q1consume', 'VAr', 'kVArh'),
    24: ('q1supply', 'VAr', 'kVArh'),
    29: ('s1consume', 'VA', 'kVAh'),
    30: ('s1supply', 'VA', 'kVAh'),
    31: ('i1', 'A'),
    32: ('u1', 'V'),
    33: ('cosphi1', '°'),
    # phase 2
    41: ('p2consume', 'W', 'kWh'),
    42: ('p2supply', 'W', 'kWh'),
    43: ('q2consume', 'VAr', 'kVArh'),
    44: ('q2supply', 'VAr', 'kVArh'),
    49: ('s2consume', 'VA', 'kVAh'),
    50: ('s2supply', 'VA', 'kVAh'),
    51: ('i2', 'A'),
    52: ('u2', 'V'),
    53: ('cosphi2', '°'),
    # phase 3
    61: ('p3consume', 'W', 'kWh'),
    62: ('p3supply', 'W', 'kWh'),
    63: ('q3consume', 'VAr', 'kVArh'),
    64: ('q3supply', 'VAr', 'kVArh'),
    69: ('s3consume', 'VA', 'kVAh'),
    70: ('s3supply', 'VA', 'kVAh'),
    71: ('i3', 'A'),
    72: ('u3', 'V'),
    73: ('cosphi3', '°'),
    # common
    36864: ('speedwire-version', ''),
}


class SMA_EM(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.6.1"

    # listen to the Multicast; SMA-Energymeter sends its measurements to 239.12.255.254:9522
    MCAST_GRP = '239.12.255.254'
    MCAST_PORT = 9522
    ipbind = '0.0.0.0'

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.yaml.
        """
        # Call init code of parent class (SmartPlugin or MqttPlugin)
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self._items = {}
        self._cycle = self.get_parameter_value('cycle')
        self._serial = self.get_parameter_value('serial')

        # prepare listen to socket-Multicast
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.MCAST_PORT))

        try:
            mreq = struct.pack("4s4s", socket.inet_aton(self.MCAST_GRP), socket.inet_aton(self.ipbind))
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except BaseException as e:
            self.logger.error('Could not connect to multicast group or bind to given interface: %s' % e)
            return

        self.init_webinterface()

    def get_serial(self):
        return self._serial

    def get_cycle(self):
        return self._cycle

    def run(self):
        """
        Run method for the plugin
        """
        self.alive = True
        self.scheduler_add("update_sma_em", self._update_sma_em, prio=3, cron=None, cycle=self._cycle, value=None,
                           offset=None, next=None)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.scheduler_remove("update_sma_em")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        Selects each item corresponding to its attribute keywords and adds it to an internal array

        :param item: The item to process.
        """
        if self.has_iattr(item.conf, 'sma_em_data_type'):
            self._items[self.get_iattr_value(item.conf, 'sma_em_data_type')] = item
            return self.update_item

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'plugin':
            pass

    def _update_sma_em(self):
        emparts = self.readem()
        if self._serial == format(emparts['serial']):
            if 'pconsume' in self._items:
                self._items['pconsume'](emparts['pconsume'], __name__)
            if 'pconsumeunit' in self._items:
                self._items['pconsumeunit'](emparts['pconsumeunit'], __name__)
            if 'pconsumecounter' in self._items:
                self._items['pconsumecounter'](emparts['pconsumecounter'], __name__)
            if 'pconsumecounterunit' in self._items:
                self._items['pconsumecounterunit'](emparts['pconsumecounterunit'], __name__)
            if 'psupply' in self._items:
                self._items['psupply'](emparts['psupply'], __name__)
            if 'psupplyunit' in self._items:
                self._items['psupplyunit'](emparts['psupplyunit'], __name__)
            if 'psupplycounter' in self._items:
                self._items['psupplycounter'](emparts['psupplycounter'], __name__)
            if 'psupplycounterunit' in self._items:
                self._items['psupplycounterunit'](emparts['psupplycounterunit'], __name__)

            if 'sconsume' in self._items:
                self._items['sconsume'](emparts['sconsume'], __name__)
            if 'sconsumeunit' in self._items:
                self._items['sconsumeunit'](emparts['sconsumeunit'], __name__)
            if 'sconsumecounter' in self._items:
                self._items['sconsumecounter'](emparts['sconsumecounter'], __name__)
            if 'sconsumecounterunit' in self._items:
                self._items['sconsumecounterunit'](emparts['sconsumecounterunit'], __name__)
            if 'ssupply' in self._items:
                self._items['ssupply'](emparts['ssupply'], __name__)
            if 'ssupplyunit' in self._items:
                self._items['ssupplyunit'](emparts['ssupplyunit'], __name__)
            if 'ssupplycounter' in self._items:
                self._items['ssupplycounter'](emparts['ssupplycounter'], __name__)
            if 'ssupplycounterunit' in self._items:
                self._items['ssupplycounterunit'](emparts['ssupplycounterunit'], __name__)

            if 'qconsume' in self._items:
                self._items['qconsume'](emparts['qconsume'], __name__)
            if 'qconsumeunit' in self._items:
                self._items['qconsumeunit'](emparts['qconsumeunit'], __name__)
            if 'qconsumecounter' in self._items:
                self._items['qconsumecounter'](emparts['qconsumecounter'], __name__)
            if 'qconsumecounterunit' in self._items:
                self._items['qconsumecounterunit'](emparts['qconsumecounterunit'], __name__)
            if 'qsupply' in self._items:
                self._items['qsupply'](emparts['qsupply'], __name__)
            if 'qsupplyunit' in self._items:
                self._items['qsupplyunit'](emparts['qsupplyunit'], __name__)
            if 'qsupplycounter' in self._items:
                self._items['qsupplycounter'](emparts['qsupplycounter'], __name__)
            if 'qsupplycounterunit' in self._items:
                self._items['qsupplycounterunit'](emparts['qsupplycounterunit'], __name__)

            if 'cosphi' in self._items:
                self._items['cosphi'](emparts['cosphi'], __name__)
            if 'cosphiunit' in self._items:
                self._items['cosphiunit'](emparts['cosphiunit'], __name__)

            if 'p1consume' in self._items:
                self._items['p1consume'](emparts['p1consume'], __name__)
            if 'p1consumeunit' in self._items:
                self._items['p1consumeunit'](emparts['p1consumeunit'], __name__)
            if 'p1consumecounter' in self._items:
                self._items['p1consumecounter'](emparts['p1consumecounter'], __name__)
            if 'p1consumecounterunit' in self._items:
                self._items['p1consumecounterunit'](emparts['p1consumecounterunit'], __name__)
            if 'p1supply' in self._items:
                self._items['p1supply'](emparts['p1supply'], __name__)
            if 'p1supplyunit' in self._items:
                self._items['p1supplyunit'](emparts['p1supplyunit'], __name__)
            if 'p1supplycounter' in self._items:
                self._items['p1supplycounter'](emparts['p1supplycounter'], __name__)
            if 'p1supplycounterunit' in self._items:
                self._items['p1supplycounterunit'](emparts['p1supplycounterunit'], __name__)

            if 's1consume' in self._items:
                self._items['s1consume'](emparts['s1consume'], __name__)
            if 's1consumeunit' in self._items:
                self._items['s1consumeunit'](emparts['s1consumeunit'], __name__)
            if 's1consumecounter' in self._items:
                self._items['s1consumecounter'](emparts['s1consumecounter'], __name__)
            if 's1consumecounterunit' in self._items:
                self._items['s1consumecounterunit'](emparts['s1consumecounterunit'], __name__)
            if 's1supply' in self._items:
                self._items['s1supply'](emparts['s1supply'], __name__)
            if 's1supplyunit' in self._items:
                self._items['s1supplyunit'](emparts['s1supplyunit'], __name__)
            if 's1supplycounter' in self._items:
                self._items['s1supplycounter'](emparts['s1supplycounter'], __name__)
            if 's1supplycounterunit' in self._items:
                self._items['s1supplycounterunit'](emparts['s1supplycounterunit'], __name__)

            if 'q1consume' in self._items:
                self._items['q1consume'](emparts['q1consume'], __name__)
            if 'q1consumeunit' in self._items:
                self._items['q1consumeunit'](emparts['q1consumeunit'], __name__)
            if 'q1consumecounter' in self._items:
                self._items['q1consumecounter'](emparts['q1consumecounter'], __name__)
            if 'q1consumecounterunit' in self._items:
                self._items['q1consumecounterunit'](emparts['q1consumecounterunit'], __name__)
            if 'q1supply' in self._items:
                self._items['q1supply'](emparts['q1supply'], __name__)
            if 'q1supplyunit' in self._items:
                self._items['q1supplyunit'](emparts['q1supplyunit'], __name__)
            if 'q1supplycounter' in self._items:
                self._items['q1supplycounter'](emparts['q1supplycounter'], __name__)
            if 'q1supplycounterunit' in self._items:
                self._items['q1supplycounterunit'](emparts['q1supplycounterunit'], __name__)

            if 'i1' in self._items:
                self._items['i1'](emparts['i1'], __name__)
            if 'i1unit' in self._items:
                self._items['i1unit'](emparts['i1unit'], __name__)
            if 'u1' in self._items:
                self._items['u1'](emparts['u1'], __name__)
            if 'u1unit' in self._items:
                self._items['u1unit'](emparts['u1unit'], __name__)
            if 'cosphi1' in self._items:
                self._items['cosphi1'](emparts['cosphi1'], __name__)
            if 'cosphi1unit' in self._items:
                self._items['cosphi1unit'](emparts['cosphi1unit'], __name__)

            if 'p2consume' in self._items:
                self._items['p2consume'](emparts['p2consume'], __name__)
            if 'p2consumeunit' in self._items:
                self._items['p2consumeunit'](emparts['p2consumeunit'], __name__)
            if 'p2consumecounter' in self._items:
                self._items['p2consumecounter'](emparts['p2consumecounter'], __name__)
            if 'p2consumecounterunit' in self._items:
                self._items['p2consumecounterunit'](emparts['p2consumecounterunit'], __name__)
            if 'p2supply' in self._items:
                self._items['p2supply'](emparts['p2supply'], __name__)
            if 'p2supplyunit' in self._items:
                self._items['p2supplyunit'](emparts['p2supplyunit'], __name__)
            if 'p2supplycounter' in self._items:
                self._items['p2supplycounter'](emparts['p2supplycounter'], __name__)
            if 'p2supplycounterunit' in self._items:
                self._items['p2supplycounterunit'](emparts['p2supplycounterunit'], __name__)

            if 's2consume' in self._items:
                self._items['s2consume'](emparts['s2consume'], __name__)
            if 's2consumeunit' in self._items:
                self._items['s2consumeunit'](emparts['s2consumeunit'], __name__)
            if 's2consumecounter' in self._items:
                self._items['s2consumecounter'](emparts['s2consumecounter'], __name__)
            if 's2consumecounterunit' in self._items:
                self._items['s2consumecounterunit'](emparts['s2consumecounterunit'], __name__)
            if 's2supply' in self._items:
                self._items['s2supply'](emparts['s2supply'], __name__)
            if 's2supplyunit' in self._items:
                self._items['s2supplyunit'](emparts['s2supplyunit'], __name__)
            if 's2supplycounter' in self._items:
                self._items['s2supplycounter'](emparts['s2supplycounter'], __name__)
            if 's2supplycounterunit' in self._items:
                self._items['s2supplycounterunit'](emparts['s2supplycounterunit'], __name__)

            if 'q2consume' in self._items:
                self._items['q2consume'](emparts['q2consume'], __name__)
            if 'q2consumeunit' in self._items:
                self._items['q2consumeunit'](emparts['q2consumeunit'], __name__)
            if 'q2consumecounter' in self._items:
                self._items['q2consumecounter'](emparts['q2consumecounter'], __name__)
            if 'q2consumecounterunit' in self._items:
                self._items['q2consumecounterunit'](emparts['q2consumecounterunit'], __name__)
            if 'q2supply' in self._items:
                self._items['q2supply'](emparts['q2supply'], __name__)
            if 'q2supplyunit' in self._items:
                self._items['q2supplyunit'](emparts['q2supplyunit'], __name__)
            if 'q2supplycounter' in self._items:
                self._items['q2supplycounter'](emparts['q2supplycounter'], __name__)
            if 'q2supplycounterunit' in self._items:
                self._items['q2supplycounterunit'](emparts['q2supplycounterunit'], __name__)

            if 'i2' in self._items:
                self._items['i2'](emparts['i2'], __name__)
            if 'i2unit' in self._items:
                self._items['i2unit'](emparts['i2unit'], __name__)
            if 'u2' in self._items:
                self._items['u2'](emparts['u2'], __name__)
            if 'u2unit' in self._items:
                self._items['u2unit'](emparts['u2unit'], __name__)
            if 'cosphi2' in self._items:
                self._items['cosphi2'](emparts['cosphi2'], __name__)
            if 'cosphi2unit' in self._items:
                self._items['cosphi2unit'](emparts['cosphi2unit'], __name__)

            if 'p3consume' in self._items:
                self._items['p3consume'](emparts['p3consume'], __name__)
            if 'p3consumeunit' in self._items:
                self._items['p3consumeunit'](emparts['p3consumeunit'], __name__)
            if 'p3consumecounter' in self._items:
                self._items['p3consumecounter'](emparts['p3consumecounter'], __name__)
            if 'p3consumecounterunit' in self._items:
                self._items['p3consumecounterunit'](emparts['p3consumecounterunit'], __name__)
            if 'p3supply' in self._items:
                self._items['p3supply'](emparts['p3supply'], __name__)
            if 'p3supplyunit' in self._items:
                self._items['p3supplyunit'](emparts['p3supplyunit'], __name__)
            if 'p3supplycounter' in self._items:
                self._items['p3supplycounter'](emparts['p3supplycounter'], __name__)
            if 'p3supplycounterunit' in self._items:
                self._items['p3supplycounterunit'](emparts['p3supplycounterunit'], __name__)

            if 's3consume' in self._items:
                self._items['s3consume'](emparts['s3consume'], __name__)
            if 's3consumeunit' in self._items:
                self._items['s3consumeunit'](emparts['s3consumeunit'], __name__)
            if 's3consumecounter' in self._items:
                self._items['s3consumecounter'](emparts['s3consumecounter'], __name__)
            if 's3consumecounterunit' in self._items:
                self._items['s3consumecounterunit'](emparts['s3consumecounterunit'], __name__)
            if 's3supply' in self._items:
                self._items['s3supply'](emparts['s3supply'], __name__)
            if 's3supplyunit' in self._items:
                self._items['s3supplyunit'](emparts['s3supplyunit'], __name__)
            if 's3supplycounter' in self._items:
                self._items['s3supplycounter'](emparts['s3supplycounter'], __name__)
            if 's3supplycounterunit' in self._items:
                self._items['s3supplycounterunit'](emparts['s3supplycounterunit'], __name__)

            if 'q3consume' in self._items:
                self._items['q3consume'](emparts['q3consume'], __name__)
            if 'q3consumeunit' in self._items:
                self._items['q3consumeunit'](emparts['q3consumeunit'], __name__)
            if 'q3consumecounter' in self._items:
                self._items['q3consumecounter'](emparts['q3consumecounter'], __name__)
            if 'q3consumecounterunit' in self._items:
                self._items['q3consumecounterunit'](emparts['q3consumecounterunit'], __name__)
            if 'q3supply' in self._items:
                self._items['q3supply'](emparts['q3supply'], __name__)
            if 'q3supplyunit' in self._items:
                self._items['q3supplyunit'](emparts['q3supplyunit'], __name__)
            if 'q3supplycounter' in self._items:
                self._items['q3supplycounter'](emparts['q3supplycounter'], __name__)
            if 'q3supplycounterunit' in self._items:
                self._items['q3supplycounterunit'](emparts['q3supplycounterunit'], __name__)

            if 'i3' in self._items:
                self._items['i3'](emparts['i3'], __name__)
            if 'i3unit' in self._items:
                self._items['i3unit'](emparts['i3unit'], __name__)
            if 'u3' in self._items:
                self._items['u3'](emparts['u3'], __name__)
            if 'u3unit' in self._items:
                self._items['u3unit'](emparts['u3unit'], __name__)
            if 'cosphi3' in self._items:
                self._items['cosphi3'](emparts['cosphi3'], __name__)
            if 'cosphi3unit' in self._items:
                self._items['cosphi3unit'](emparts['cosphi3unit'], __name__)

            if 'speedwire-version' in self._items:
                self._items['speedwire-version'](emparts['speedwire-version'], __name__)

    def hex2dec(self, s):
        """
        Return the integer value of a hexadecimal string s

        :param string: Hexadecimal string s
        :return int: Integer value of hexadecimal string
        """
        return int(s, 16)

    def decode_OBIS(self, obis):
        measurement = int.from_bytes(obis[0:2], byteorder='big')
        raw_type = int.from_bytes(obis[2:3], byteorder='big')
        if raw_type == 4:
            datatype = 'actual'
        elif raw_type == 8:
            datatype = 'counter'
        elif raw_type == 0 and measurement == 36864:
            datatype = 'version'
        else:
            datatype = 'unknown'
            self.logger.error(
                'unknown datatype: measurement {} datatype {} raw_type {}'.format(measurement, datatype, raw_type))
        return measurement, datatype

    def decode_speedwire(self, datagram):
        emparts = {}
        # process data only of SMA header is present
        if datagram[0:3] == b'SMA':
            # datagram length
            datalength = int.from_bytes(datagram[12:14], byteorder='big') + 16
            # self.logger.debug('data lenght: {}'.format(datalength))
            # serial number
            emID = int.from_bytes(datagram[20:24], byteorder='big')
            # self.logger.debug('seral: {}'.format(emID))
            emparts['serial'] = emID
            # timestamp
            timestamp = int.from_bytes(datagram[24:28], byteorder='big')
            # self.logger.debug('timestamp: {}'.format(timestamp))
            # decode OBIS data blocks
            # start with header
            position = 28
            while position < datalength:
                # decode header
                # self.logger.debug('pos: {}'.format(position))
                (measurement, datatype) = self.decode_OBIS(datagram[position:position + 4])
                # self.logger.debug('measurement {} datatype: {}'.format(measurement,datatype))
                # decode values
                # actual values
                if datatype == 'actual':
                    value = int.from_bytes(datagram[position + 4:position + 8], byteorder='big')
                    position += 8
                    if measurement in sma_channels.keys():
                        emparts[sma_channels[measurement][0]] = value / sma_units[sma_channels[measurement][1]]
                        emparts[sma_channels[measurement][0] + 'unit'] = sma_channels[measurement][1]
                # counter values
                elif datatype == 'counter':
                    value = int.from_bytes(datagram[position + 4:position + 12], byteorder='big')
                    position += 12
                    if measurement in sma_channels.keys():
                        emparts[sma_channels[measurement][0] + 'counter'] = value / sma_units[
                            sma_channels[measurement][2]]
                        emparts[sma_channels[measurement][0] + 'counterunit'] = sma_channels[measurement][2]
                elif datatype == 'version':
                    value = datagram[position + 4:position + 8]
                    if measurement in sma_channels.keys():
                        bversion = (binascii.b2a_hex(value).decode("utf-8"))
                        version = str(int(bversion[0:2], 16)) + "." + str(int(bversion[2:4], 16)) + "." + str(
                            int(bversion[4:6], 16))
                        revision = str(chr(int(bversion[6:8])))
                        # revision definitions
                        if revision == "1":
                            # S – Spezial Version
                            version = version + ".S"
                        elif revision == "2":
                            # A – Alpha (noch kein Feature Complete, Version für Verifizierung und Validierung)
                            version = version + ".A"
                        elif revision == "3":
                            # B – Beta (Feature Complete, Version für Verifizierung und Validierung)
                            version = version + ".B"
                        elif revision == "4":
                            # R – Release Candidate / Release (Version für Verifizierung, Validierung und Feldtest / öffentliche Version)
                            version = version + ".R"
                        elif revision == "5":
                            # E – Experimental Version (dient zur lokalen Verifizierung)
                            version = version + ".E"
                        elif revision == "6":
                            # N – Keine Revision
                            version = version + ".N"
                        # adding versionnumber to compare versions
                        version = version + "|" + str(bversion[0:2]) + str(bversion[2:4]) + str(bversion[4:6])
                        emparts[sma_channels[measurement][0]] = version
                    position += 8
                else:
                    position += 8
        return emparts

    def readem(self):
        """
        Splits the multicast message into the available data

        :return emparts: dict with all available data of a multicast
        """

        # processing received messages
        smainfo = self.sock.recv(1024)

        # test-datagrem sma-em-1.2.4.R
        # smainfo=b'SMA\x00\x00\x04\x02\xa0\x00\x00\x00\x01\x02D\x00\x10`i\x01\x0eqB\xd1\xeb_\xc9\r\xd0\x00\x01\x04\x00\x00\x00\x87\x13\x00\x01\x08\x00\x00\x00\x00\x16R/\x00h\x00\x02\x04\x00\x00\x00\x00\x00\x00\x02\x08\x00\x00\x00\x00\x08\x9d\x14\xb8`\x00\x03\x04\x00\x00\x00\x00\x00\x00\x03\x08\x00\x00\x00\x00\x00\xc1%\xc1H\x00\x04\x04\x00\x00\x00\x11Q\x00\x04\x08\x00\x00\x00\x00\no\xce|\xe0\x00\t\x04\x00\x00\x00\x88.\x00\t\x08\x00\x00\x00\x00\x19\xdfo\x07\x18\x00\n\x04\x00\x00\x00\x00\x00\x00\n\x08\x00\x00\x00\x00\tJ\xc5x\xc8\x00\r\x04\x00\x00\x00\x03\xe0\x00\x15\x04\x00\x00\x00}P\x00\x15\x08\x00\x00\x00\x00\n.\x07o`\x00\x16\x04\x00\x00\x00\x00\x00\x00\x16\x08\x00\x00\x00\x00\n\xcb\xab\xf4 \x00\x17\x04\x00\x00\x00\x00\x00\x00\x17\x08\x00\x00\x00\x00\x00bF\x05p\x00\x18\x04\x00\x00\x00\r\xe4\x00\x18\x08\x00\x00\x00\x00\x04\xf3E\'\xc8\x00\x1d\x04\x00\x00\x00~\x14\x00\x1d\x08\x00\x00\x00\x00\x0c\x0f\xb7\xbd`\x00\x1e\x04\x00\x00\x00\x00\x00\x00\x1e\x08\x00\x00\x00\x00\x0b"p\x95\x90\x00\x1f\x04\x00\x00\x008G\x00 \x04\x00\x00\x03l\xd4\x00!\x04\x00\x00\x00\x03\xe2\x00)\x04\x00\x00\x00\x07,\x00)\x08\x00\x00\x00\x00\t\xdfT;\xf0\x00*\x04\x00\x00\x00\x00\x00\x00*\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00+\x04\x00\x00\x00\x00\x00\x00+\x08\x00\x00\x00\x00\x00\x03\x12\xb1H\x00,\x04\x00\x00\x00\x03\x89\x00,\x08\x00\x00\x00\x00\x05)\x8a\x93h\x001\x04\x00\x00\x00\x07\xff\x001\x08\x00\x00\x00\x00\x0c4\xa7\x9b@\x002\x04\x00\x00\x00\x00\x00\x002\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x003\x04\x00\x00\x00\x03\xba\x004\x04\x00\x00\x03\x85\t\x005\x04\x00\x00\x00\x03\x81\x00=\x04\x00\x00\x00\x02\x97\x00=\x08\x00\x00\x00\x00\x04sj\xe2h\x00>\x04\x00\x00\x00\x00\x00\x00>\x08\x00\x00\x00\x00\x00\x00\x00o\x18\x00?\x04\x00\x00\x00\x00\x1c\x00?\x08\x00\x00\x00\x00\x00\xe2\xa0\xb1\xe8\x00@\x04\x00\x00\x00\x00\x00\x00@\x08\x00\x00\x00\x00\x00\xd9\xd2`\x98\x00E\x04\x00\x00\x00\x02\x97\x00E\x08\x00\x00\x00\x00\x05K\xf5vp\x00F\x04\x00\x00\x00\x00\x00\x00F\x08\x00\x00\x00\x00\x00\x00\x00o\x18\x00G\x04\x00\x00\x00\x01\xe6\x00H\x04\x00\x00\x03\x84.\x00I\x04\x00\x00\x00\x03\xe7\x90\x00\x00\x00\x01\x02\x04R\x00\x00\x00\x00'

        # test-datagram sma-homemanager-2.3.4.R
        # smainfo=b'SMA\x00\x00\x04\x02\xa0\x00\x00\x00\x01\x02L\x00\x10`i\x01t\xb2\xfb\xdb\na3\xfe\xa4\x00\x01\x04\x00\x00\x00\x00\x00\x00\x01\x08\x00\x00\x00\x00\x01\xd6[.\xf8\x00\x02\x04\x00\x00\x00\xbe\x80\x00\x02\x08\x00\x00\x00\x00\x07\x81\x86E`\x00\x03\x04\x00\x00\x00\x17x\x00\x03\x08\x00\x00\x00\x00\x0144\xf6\x90\x00\x04\x04\x00\x00\x00\x00\x00\x00\x04\x08\x00\x00\x00\x00\x00\xd5#\xa7P\x00\t\x04\x00\x00\x00\x00\x00\x00\t\x08\x00\x00\x00\x00\x02\x0fv\xbb\xf8\x00\n\x04\x00\x00\x00\xbf\xf0\x00\n\x08\x00\x00\x00\x00\x07\xac\xcc\x0c\xa0\x00\r\x04\x00\x00\x00\x03\xe0\x00\x0e\x04\x00\x00\x00\xc3<\x00\x15\x04\x00\x00\x00\x00\x00\x00\x15\x08\x00\x00\x00\x00\x00jb\xee\x80\x00\x16\x04\x00\x00\x00B9\x00\x16\x08\x00\x00\x00\x00\x02\xb4\xc4\xfa \x00\x17\x04\x00\x00\x00\x07\x16\x00\x17\x08\x00\x00\x00\x00\x00d>U\x08\x00\x18\x04\x00\x00\x00\x00\x00\x00\x18\x08\x00\x00\x00\x00\x00EC\xec0\x00\x1d\x04\x00\x00\x00\x00\x00\x00\x1d\x08\x00\x00\x00\x00\x00\x87z=H\x00\x1e\x04\x00\x00\x00B\x99\x00\x1e\x08\x00\x00\x00\x00\x02\xc4G\xe0 \x00\x1f\x04\x00\x00\x00\x1d\x15\x00 \x04\x00\x00\x03\x80\xbb\x00!\x04\x00\x00\x00\x03\xe2\x00)\x04\x00\x00\x00\x00\x00\x00)\x08\x00\x00\x00\x00\x00\xcc\xc2b\xe0\x00*\x04\x00\x00\x00=j\x00*\x08\x00\x00\x00\x00\x02n\xbf)\x88\x00+\x04\x00\x00\x00\tt\x00+\x08\x00\x00\x00\x00\x00u\x08\xddh\x00,\x04\x00\x00\x00\x00\x00\x00,\x08\x00\x00\x00\x00\x00P\x11\xe9x\x001\x04\x00\x00\x00\x00\x00\x001\x08\x00\x00\x00\x00\x00\xe7\xdb\xc0\xa8\x002\x04\x00\x00\x00>#\x002\x08\x00\x00\x00\x00\x02~E=\xc0\x003\x04\x00\x00\x00\x1a\xc2\x004\x04\x00\x00\x03\x8e\xb2\x005\x04\x00\x00\x00\x03\xdc\x00=\x04\x00\x00\x00\x00\x00\x00=\x08\x00\x00\x00\x00\x00\xc6T\xc4 \x00>\x04\x00\x00\x00>\xdd\x00>\x08\x00\x00\x00\x00\x02\x85!\t\xa8\x00?\x04\x00\x00\x00\x06\xed\x00?\x08\x00\x00\x00\x00\x00x~\xa8\xd8\x00@\x04\x00\x00\x00\x00\x00\x00@\x08\x00\x00\x00\x00\x00]^\xb90\x00E\x04\x00\x00\x00\x00\x00\x00E\x08\x00\x00\x00\x00\x00\xe1K,\x88\x00F\x04\x00\x00\x00?>\x00F\x08\x00\x00\x00\x00\x02\x97>i(\x00G\x04\x00\x00\x00\x1bi\x00H\x04\x00\x00\x03\x88i\x00I\x04\x00\x00\x00\x03\xe2\x90\x00\x00\x00\x02\x03\x04R\x00\x00\x00\x00'

        # smainfoasci = binascii.b2a_hex(smainfo)
        # self.logger.debug(smainfoasci)
        emparts = self.decode_speedwire(smainfo)
        # self.logger.debug(emparts)

        return emparts

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
                           tab1title="SMA EM Items (%s)" % len(self.plugin.get_items()),
                           p=self.plugin)

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            # get the new data
            data = {}
            for key, item in self.plugin.get_items().items():
                data[item.property.path + "_value"] = item()
                data[item.property.path + "_last_update"] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data[item.property.path + "_last_change"] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            # return it as json the the web page
            return json.dumps(data)
        else:
            return
