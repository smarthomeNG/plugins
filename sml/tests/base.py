import re
import common
import unittest

from plugins.sml import Sml
from tests.mock.core import MockSmartHome

class SmlPacket:

    def __init__(self, data, type='string'):
        self.data = bytearray()
        self.add(data, type)

    def add(self, data, type='string'):
        if type == 'string':
            self.data.extend(map(ord, data))
        elif type == 'hex':
            self.data = bytearray.fromhex(re.sub('[^0-9a-f]', '', data))
        elif type == 'byte':
            self.data = data
        else:
            raise Exception("Type {} not supported by SmlPacket".format(type))

    def get_data(self, start=None, length=None):
        if start is None:
           start = 0
        if length is None:
           length = len(self.data) - start
        return self.data[start:start+length]


class SmlPacketReader:

    def __init__(self):
        self.packets = []
        self.packet = -1
        self.pos = 0
        self.buf = bytearray()

    def add(self, packet):
        self.packets.append(packet)

    def read(self, length):
        if length > len(self.buf):
            self.buf = self.buf[self.pos:]
            if self.packet < len(self.packets):
                self.buf.extend(self.packets[self.packet].get_data())
                self.packet = self.packet + 1

        if length > len(self.buf):
            length = len(self.buf)

        data = self.buf[0:length]
        self.buf = self.buf[length:]

        return data


class TestSmlBase(unittest.TestCase):

    def plugin(self):
        self.sh = MockSmartHome()
        plugin = Sml(self.sh)
        plugin.connect()
        plugin.data = SmlPacketReader()
        plugin._serial = plugin.data
        return plugin

    def assertEntry(self, values, obis, value, unit=None, unitname=None, status=None, scaler=None):
        self.assertTrue(obis in values)
        self.assertEqual(   value, values[obis]['value']);
        if unit is not None:
            self.assertEqual(    unit, values[obis]['unit']);
        if unitname is not None:
            self.assertEqual(unitname, values[obis]['unitName']);
        if status is not None:
            self.assertEqual(  status, values[obis]['status']);
        if scaler is not None:
            self.assertEqual(  scaler, values[obis]['scaler']);


