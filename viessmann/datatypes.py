#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

import lib.model.sdp.datatypes as DT

import re
import dateutil
import datetime


# V = Viessmann, generic numeric type
class DT_Number(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        if data is None:
            return None

        len = kwargs.get('len', 1)
        signed = kwargs.get('signed', False)
        mult = kwargs.get('mult', 0)
        if mult:
            data = int(float(data) * float(mult))
        bytes = int2bytes(data, len, signed)
        return bytes

    def get_shng_data(self, data, type=None, **kwargs):
        signed = kwargs.get('signed', False)
        mult = kwargs.get('mult', 0)

        val = bytes2int(data, signed)
        if mult:
            val = round(float(val) / float(mult), 2)
            if isinstance(mult, int):
                val = int(val)

        if type is None:
            return val
        else:
            return type(val)


# S = serial
class DT_Serial(DT_Number):
    def get_send_data(self, data, **kwargs):
        raise RuntimeError('write of serial number not possible')

    def get_shng_data(self, data, type=None, **kwargs):
        b = data[:7]
        sn = 0
        b.reverse()
        for byte in range(0, len(b)):
            sn += (b[byte] - 48) * 10 ** byte
        return hex(sn).upper()


# T = time
class DT_Time(DT_Number):
    def get_send_data(self, data, **kwargs):
        try:
            datestring = dateutil.parser.isoparse(data).strftime('%Y%m%d%w%H%M%S')
            # Viessmann erwartet 2 digits für Wochentag, daher wird hier noch eine 0 eingefügt
            datestring = datestring[:8] + '0' + datestring[8:]
            valuebytes = bytes.fromhex(datestring)
            self.logger.debug(f'created value bytes as bytes: {valuebytes}')
            return valuebytes
        except Exception as e:
            raise ValueError(f'incorrect data format, YYYY-MM-DD expected. Error was: {e}')

    def get_shng_data(self, data, type=None, **kwargs):
        return datetime.strptime(data.hex(), '%Y%m%d%W%H%M%S').isoformat()


# D = date
class DT_Date(DT_Time):
    def get_shng_data(self, data, type=None, **kwargs):
        return datetime.strptime(data.hex(), '%Y%m%d%W%H%M%S').date().isoformat()


# C = control timer (?)
class DT_Control(DT_Number):
    def get_send_data(self, data, **kwargs):
        try:
            times = ''
            for switching_time in data:
                an = encode_timer(switching_time['An'])
                aus = encode_timer(switching_time['Aus'])
                times += f'{an:02x}{aus:02x}'
            valuebytes = bytes.fromhex(times)
            self.logger.debug(f'created value bytes as hexstring: {bytes2hexstring(valuebytes)} and as bytes: {valuebytes}')
        except Exception as e:
            raise ValueError(f'incorrect data format, (An: hh:mm Aus: hh:mm) expected. Error was: {e}')

    def get_shng_data(self, data, type=None, **kwargs):
        timer = self._decode_timer(data.hex())
        return [{'An': on_time, 'Aus': off_time} for on_time, off_time in zip(timer, timer)]


# H = hex
class DT_Hex(DT_Number):
    def get_send_data(self, data, **kwargs):
        if isinstance(data, str):
            try:
                data = int(data, 16)
            except ValueError:
                pass

        return super().get_send_data(data, **kwargs)

    def get_shng_data(self, data, type=None, **kwargs):
        try:
            return data.hex().upper()
        except AttributeError:
            return

        # return ' '.join([hexstr[i:i + 2] for i in range(0, len(hexstr), 2)])


"""
'BA':      {'unit_de': 'Betriebsart',       'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: BA
'BT':      {'unit_de': 'Brennertyp',        'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit:
'CT':      {'unit_de': 'CycleTime',         'type': 'timer',    'signed': False, 'read_value_transform': 'non'},        # vito unit: CT
'DA':      {'unit_de': 'Date',              'type': 'date',     'signed': False, 'read_value_transform': 'non'},        # vito unit:
'DT':      {'unit_de': 'DeviceType',        'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: DT
'ES':      {'unit_de': 'ErrorState',        'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: ES
'HEX':     {'unit_de': 'HexString',         'type': 'string',   'signed': False, 'read_value_transform': 'hex'},        # vito unit:
'IS10':    {'unit_de': 'INT signed 10',     'type': 'integer',  'signed': True,  'read_value_transform': '10'},         # vito unit: UT, UN
'IS100':   {'unit_de': 'INT signed 100',    'type': 'integer',  'signed': True,  'read_value_transform': '100'},        # vito unit:
'IS1000':  {'unit_de': 'INT signed 1000',   'type': 'integer',  'signed': True,  'read_value_transform': '1000'},       # vito unit:
'IS2':     {'unit_de': 'INT signed 2',      'type': 'integer',  'signed': True,  'read_value_transform': '2'},          # vito unit: UT1, PR
'ISNON':   {'unit_de': 'INT signed non',    'type': 'integer',  'signed': True,  'read_value_transform': 'non'},        # vito unit:
'IU10':    {'unit_de': 'INT unsigned 10',   'type': 'integer',  'signed': False, 'read_value_transform': '10'},         # vito unit:
'IU100':   {'unit_de': 'INT unsigned 100',  'type': 'integer',  'signed': False, 'read_value_transform': '100'},        # vito unit:
'IU1000':  {'unit_de': 'INT unsigned 1000', 'type': 'integer',  'signed': False, 'read_value_transform': '1000'},        # vito unit:
'IU2':     {'unit_de': 'INT unsigned 2',    'type': 'integer',  'signed': False, 'read_value_transform': '2'},          # vito unit: UT1U, PR1
'IU3600':  {'unit_de': 'INT unsigned 3600', 'type': 'integer',  'signed': False, 'read_value_transform': '3600'},       # vito unit: CS
'IUBOOL':  {'unit_de': 'INT unsigned bool', 'type': 'integer',  'signed': False, 'read_value_transform': 'bool'},       # vito unit:
'IUINT':   {'unit_de': 'INT unsigned int',  'type': 'integer',  'signed': False, 'read_value_transform': '1'},          # vito unit:
'IUNON':   {'unit_de': 'INT unsigned non',  'type': 'integer',  'signed': False, 'read_value_transform': 'non'},        # vito unit: UTI, CO
'IUPR':    {'unit_de': 'INT unsigned 2.55', 'type': 'integer',  'signed': False, 'read_value_transform': '2.55'},       # vito unit: PP
'RT':      {'unit_de': 'ReturnStatus',      'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: ST, RT
'SC':      {'unit_de': 'SystemScheme',      'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit:
'SN':      {'unit_de': 'Sachnummer',        'type': 'serial',   'signed': False, 'read_value_transform': 'non'},        # vito unit:
'SR':      {'unit_de': 'SetReturnStatus',   'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit:
'TI':      {'unit_de': 'SystemTime',        'type': 'datetime', 'signed': False, 'read_value_transform': 'non'},        # vito unit: TI
"""


def int2bytes(value, length=0, signed=False):
    """ convert value to bytearray, see MD_Command.py """
    if not length:
        length = len(value)
    value = value % (2 ** (length * 8))
    return value.to_bytes(length, byteorder='big', signed=signed)


def bytes2int(rawbytes, signed):
    """ convert bytearray to value, see MD_Command.py """
    return int.from_bytes(rawbytes, byteorder='little', signed=signed)


def bytes2hexstring(bytesvalue):
    """ create hex-string from bytearray, see MD_Command.py """
    return ''.join(f'{c:02x}' for c in bytesvalue)


def decode_timer(rawdatabytes):
    """ generator to convert byte sequence to a number of time strings """
    while rawdatabytes:
        hours, minutes = divmod(int(rawdatabytes[:2], 16), 8)
        if minutes >= 6 or hours >= 24:
            # not a valid time
            yield '00:00'
        else:
            yield f'{hours:02d}:{(minutes * 10):02d}'
        rawdatabytes = rawdatabytes[2:]
    return None


def encode_timer(switching_time):
    """ convert time string to encoded time value """
    if switching_time == '00:00':
        return 0xff
    clocktime = re.compile(r'(\d\d):(\d\d)')
    mo = clocktime.search(switching_time)
    number = int(mo.group(1)) * 8 + int(mo.group(2)) // 10
    return number
