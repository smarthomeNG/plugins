#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 KNX-User-Forum e.V.      http://knx-user-forum.de/
#########################################################################
#  This file is part of SmartHomeNG
#  https://github.com/smarthomeNG/smarthome
#  http://knx-user-forum.de/
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
#########################################################################

import sys
import logging
import socket
import threading
import struct
import time

from lib.model.smartplugin import SmartPlugin

MODES = {
    0: 'Heizbetrieb',
    1: 'Keine Anforderung',
    2: 'Netz- Einschaltverzoegerung',
    3: 'SSP Zeit',
    4: 'Sperrzeit',
    5: 'Brauchwasser',
    6: 'Estrich Programm',
    7: 'Abtauen',
    8: 'Pumpenvorlauf',
    9: 'Thermische Desinfektion',
    10: 'Kuehlbetrieb',
    12: 'Schwimmbad',
    13: 'Heizen Ext.',
    14: 'Brauchwasser Ext.',
    16: 'Durchflussueberwachung',
    17: 'ZWE Betrieb'
}


class luxex(Exception):
    pass


class LuxBase(SmartPlugin):

    # ATTENTION: This is NOT the SmartPlugin class of the plugin!!!

    def __init__(self, host, port=8888, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.host = host
        self.port = int(port)
        self._sock = False
        self._lock = threading.Lock()
        self.is_connected = False
        self._connection_attempts = 0
        self._connection_errorlog = 60
        self._params = []
        self._attrs = []
        self._calc = []

    def get_attribute(self, identifier):
        return self._attrs[identifier] if identifier < len(self._attrs) else None

    def get_parameter(self, identifier):
        return self._params[identifier] if identifier < len(self._params) else None

    def get_calculated(self, identifier):
        return self._calc[identifier] if identifier < len(self._calc) else None

    def get_attribute_count(self):
        return len(self._attrs)

    def get_parameter_count(self):
        return len(self._params)

    def get_calculated_count(self):
        return len(self._calc)

    def connect(self):
        self._lock.acquire()
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(2)
            self._sock.connect((self.host, self.port))
        except Exception as e:
            self._connection_attempts -= 1
            if self._connection_attempts <= 0:
                self.logger.error(
                    'Luxtronic2: could not connect to {0}:{1}: {2}'.format(self.host, self.port, e))
                self._connection_attempts = self._connection_errorlog
            return
        finally:
            self._lock.release()
        self.logger.info(
            'Luxtronic2: connected to {0}:{1}'.format(self.host, self.port))
        self.is_connected = True
        self._connection_attempts = 0

    def close(self):
        self.is_connected = False
        try:
            self._sock.close()
            self._sock = False
        except:
            pass

    def _request(self, request, length):
        if not self.is_connected:
            raise luxex("no connection to luxtronic.")
        try:
            self._sock.send(request)
        except Exception as e:
            self._lock.release()
            self.close()
            raise luxex("error sending request: {0}".format(e))
        try:
            answer = self._sock.recv(length)
        except socket.timeout:
            self._lock.release()
            raise luxex("error receiving answer: timeout")
        except Exception as e:
            self._lock.release()
            self.close()
            raise luxex("error receiving answer: {0}".format(e))
        return answer

    def _request_more(self, length):
        try:
            return self._sock.recv(length)
        except socket.timeout:
            self._lock.release()
            raise luxex("error receiving payload: timeout")
        except Exception as e:
            self._lock.release()
            self.close()
            raise luxex("error receifing payload: {0}".format(e))

    def set_param(self, param, value):
        param = int(param)
#       old = self._params[param] if param < len(self._params) else 0
        payload = struct.pack('!iii', 3002, int(param), int(value))
        self._lock.acquire()
        answer = self._request(payload, 8)
        self._lock.release()
        if len(answer) != 8:
            self.close()
            raise luxex("error receiving answer: no data")
        answer = struct.unpack('!ii', answer)
        fields = ['cmd', 'param']
        answer = dict(list(zip(fields, answer)))
        if answer['cmd'] == 3002 and answer['param'] == param:
            self.logger.debug(
                "Luxtronic2: value {0} for parameter {1} stored".format(value, param))
            return True
        else:
            self.logger.warning(
                "Luxtronic2: value {0} for parameter {1} not stored".format(value, param))
            return False

    def refresh_parameters(self):
        request = struct.pack('!ii', 3003, 0)
        self._lock.acquire()
        answer = self._request(request, 8)
        if len(answer) != 8:
            self._lock.release()
            self.close()
            raise luxex("error receiving answer: no data")
        answer = struct.unpack('!ii', answer)
        fields = ['cmd', 'len']
        answer = dict(list(zip(fields, answer)))
        if answer['cmd'] == 3003:
            params = []
            for i in range(0, answer['len']):
                param = self._request_more(4)
                params.append(struct.unpack('!i', param)[0])
            self._lock.release()
            if len(params) > 0:
                self._params = params
                return True
            return False
        else:
            self._lock.release()
            self.logger.warning("Luxtronic2: failed to retrieve parameters")
            return False

    def refresh_attributes(self):
        request = struct.pack('!ii', 3005, 0)
        self._lock.acquire()
        answer = self._request(request, 8)
        if len(answer) != 8:
            self._lock.release()
            self.close()
            raise luxex("error receiving answer: no data")
        answer = struct.unpack('!ii', answer)
        fields = ['cmd', 'len']
        answer = dict(list(zip(fields, answer)))
        if answer['cmd'] == 3005:
            attrs = []
            for i in range(0, answer['len']):
                attr = self._request_more(1)
                attrs.append(struct.unpack('!b', attr)[0])
            self._lock.release()
            if len(attrs) > 0:
                self._attrs = attrs
                return True
            return False
        else:
            self._lock.release()
            self.logger.warning("Luxtronic2: failed to retrieve attributes")
            return False

    def refresh_calculated(self):
        request = struct.pack('!ii', 3004, 0)
        self._lock.acquire()
        answer = self._request(request, 12)
        if len(answer) != 12:
            self._lock.release()
            self.close()
            raise luxex("error receiving answer: no data")
        answer = struct.unpack('!iii', answer)
        fields = ['cmd', 'state', 'len']
        answer = dict(list(zip(fields, answer)))
        if answer['cmd'] == 3004:
            calcs = []
            for i in range(0, answer['len']):
                calc = self._request_more(4)
                calcs.append(struct.unpack('!i', calc)[0])
            self._lock.release()
            if len(calcs) > 0:
                self._calc = calcs
                return answer['state']
            return 0
        else:
            self._lock.release()
            self.logger.warning("Luxtronic2: failed to retrieve calculated")
            return 0


class Luxtronic2(LuxBase):

    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = '1.3.3'

    _parameter = {}
    _attribute = {}
    _calculated = {}
    _decoded = {}
    alive = True

    def __init__(self, sh, **kwargs):
        self._is_connected = False
        self._cycle = self.get_parameter_value('cycle')
        LuxBase.__init__(self, self.get_parameter_value('host'), self.get_parameter_value('port'))
        self.connect()

    def run(self):
        self.alive = True
        self.scheduler_add('Luxtronic2', self._refresh, cycle=self._cycle)

    def stop(self):
        self.alive = False
        self.scheduler_remove('Luxtronic2')

    def _refresh(self):
        if not self.is_connected or not self.alive:
            return
        start = time.time()
        if len(self._parameter) > 0:
            self.refresh_parameters()
            for p in self._parameter:
                val = self.get_parameter(p)
                if val:
                    self._parameter[p](val, 'Luxtronic2')
        if len(self._attribute) > 0:
            self.refresh_attributes()
            for a in self._attribute:
                val = self.get_attribute(a)
                if val:
                    self._attribute[a](val, 'Luxtronic2')
        if len(self._calculated) > 0 or len(self._decoded) > 0:
            self.refresh_calculated()
            for c in self._calculated:
                val = self.get_calculated(c)
                if val is not None:
                    self._calculated[c](val, 'Luxtronic2')
            for d in self._decoded:
                val = self.get_calculated(d)
                if val is not None:
                    self._decoded[d](self._decode(d, val), 'Luxtronic2')
        cycletime = time.time() - start
        self.logger.debug("cycle takes {0} seconds".format(cycletime))

    def _decode(self, identifier, value):
        if identifier == 119:
            return MODES.get(value, '???')
        if identifier in (10, 11, 12, 15, 19, 20, 151, 152):
            return float(value) / 10
        return value

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'lux2'):
            d = self.get_iattr_value(item.conf, 'lux2')
            d = int(d)
            self._decoded[d] = item
        if self.has_iattr(item.conf, 'lux2_a'):
            a = self.get_iattr_value(item.conf, 'lux2_a')
            a = int(a)
            self._attribute[a] = item
        if self.has_iattr(item.conf, 'lux2_c'):
            c = self.get_iattr_value(item.conf, 'lux2_c')
            c = int(c)
            self._calculated[c] = item
        if self.has_iattr(item.conf, 'lux2_p'):
            p = self.get_iattr_value(item.conf, 'lux2_p')
            p = int(p)
            self._parameter[p] = item
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'Luxtronic2' and self.alive:
            self.set_param(self.get_iattr_value(item.conf, 'lux2_p'), item())


def main():
    lux = None
    try:
        lux = LuxBase('192.168.178.25')
        lux.connect()
        if not lux.is_connected:
            return 1
        start = time.time()
        lux.refresh_parameters()
        lux.refresh_attributes()
        lux.refresh_calculated()
        cycletime = time.time() - start
        print("{0} Parameters:".format(lux.get_parameter_count()))
        for i in range(0, lux.get_parameter_count()):
            print("  {0} = {1}".format(i + 1, lux.get_parameter(i)))
        print("{0} Attributes:".format(lux.get_attribute_count()))
        for i in range(0, lux.get_attribute_count()):
            print("  {0} = {1}".format(i + 1, lux.get_attribute(i)))
        print("{0} Calculated:".format(lux.get_calculated_count()))
        for i in range(0, lux.get_calculated_count()):
            print("  {0} = {1}".format(i + 1, lux.get_calculated(i)))
        print("cycle takes {0} seconds".format(cycletime))

    except Exception as e:
        print("[EXCEPTION] error main: {0}".format(e))
        return 1
    finally:
        if lux:
            lux.close()


if __name__ == "__main__":
    sys.exit(main())
