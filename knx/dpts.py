#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#  Copyright 2021 Bernd Meiners                     Bernd.Meiners@mail.de
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
#  along with SmartHomeNG.  If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import struct
import datetime
import math

"""
Datapoint Types are described in detail e.g. in **03_07_02 Datapoint Types v01.08.02 AS**
from ``The KNX Standard v2.1`` chapter ``03 Volume 3 System Specifications``.


"""

"""
Datapoint type one byte with one bit information
"""
def en1(value):
    return [int(value) & 0x01]


def de1(payload):
    if len(payload) != 1:
        return None
    return bool(payload[0] & 0x01)

"""
Datapoint type one byte with two bit information
"""

def en2(payload):
    # control, value
    return [(payload[0] << 1) & 0x02 | payload[1] & 0x01]


def de2(payload):
    if len(payload) != 1:
        return None
    return [payload[0] >> 1 & 0x01, payload[0] & 0x01]

"""
Datapoint type one byte for dimming control
"""

def en3(vlist):
    # direction, value
    return [(int(vlist[0]) << 3) & 0x08 | int(vlist[1]) & 0x07]


def de3(payload):
    if len(payload) != 1:
        return None
    # up/down, stepping
    return [payload[0] >> 3 & 0x01, payload[0] & 0x07]

"""
Datapoint type one byte for one character
"""

def en4002(value):
    if isinstance(value, str):
        value = value.encode('iso-8859-1', 'replace')
    else:
        value = str(value)
    return [0, ord(value) & 0xff]


def de4002(payload):
    if len(payload) != 1:
        return None
    return payload.decode('iso-8859-1')


"""
Datapoint type one byte with unsigned value
"""

def en5(value):
    if value < 0:
        value = 0
    elif value > 255:
        value = 255
    return [0, int(value) & 0xff]


def de5(payload):
    if len(payload) != 1:
        return None
    return round(struct.unpack('>B', payload)[0], 1)


def en5001(value):
    if value < 0:
        value = 0
    elif value > 100:
        value = 100
    return [0, int(value * 255.0 / 100) & 0xff]


def de5001(payload):
    if len(payload) != 1:
        return None
    return round(struct.unpack('>B', payload)[0] * 100.0 / 255, 1)


def en5999(value):
    # artificial data point for tebis TS systems
    if value < 0:
        value = 0
    elif value > 255:
        value = 255
    return [0, int(value) & 0xff]


def de5999(payload):
    # artificial data point for tebis TS systems
    if len(payload) != 1:
        return None
    return struct.unpack('>B', payload)[0] & 0x0f


"""
Datapoint type hex/raw
"""

def enhex(value):
    import binascii
    return binascii.unhexlify(value)


def dehex(payload):
    import binascii
    return binascii.hexlify(payload).decode()


"""
Datapoint type one Byte with signed relative value
"""

def en6(value):
    if value < -128:
        value = -128
    elif value > 127:
        value = 127
    return [0, struct.pack('b', int(value))[0]]


def de6(payload):
    if len(payload) != 1:
        return None
    return struct.unpack('b', payload)[0]

"""
Datapoint type two Bytes with unsigned value 
"""

def en7(value):
    ret = bytearray([0])
    ret.extend(struct.pack('>H', int(value)))
    return ret


def de7(payload):
    if len(payload) != 2:
        return None
    return struct.unpack('>H', payload)[0]

"""
Datapoint type two Bytes with signed value 
"""

def en8(value):
    if value < -32768:
        value = -32768
    elif value > 32767:
        value = 32767
    ret = bytearray([0])
    ret.extend(struct.pack('>h', int(value)))
    return ret


def de8(payload):
    if len(payload) != 2:
        return None
    return struct.unpack('>h', payload)[0]

"""
Datapoint type two bytes with float value
    Encoding: MEEEEMMM MMMMMMMM
    Float Value = (0,01*M)*2^E
    E = [0..15]
    M = [-2048 ... 2047 ] in two's complement notation
    Range:
    [-671 088,64 … 670 760,96]
    For all Datapoint Types 9.xxx, the encoded value 7FFFh shall always be used to denote invalid data.
"""

def en9(value):
    s = 0
    e = 0
    if value < 0:
        s = 0x8000
    m = int(value * 100)
    while (m > 2047) or (m < -2048):
        e = e + 1
        m = m >> 1
    num = s | (e << 11) | (int(m) & 0x07ff)
    return en7(num)


def de9(payload):
    if len(payload) != 2:
        return None
    i1 = payload[0]
    i2 = payload[1]
    s = (i1 & 0x80) >> 7
    e = (i1 & 0x78) >> 3
    m = (i1 & 0x07) << 8 | i2
    if s == 1:
        s = -1 << 11
    f = (m | s) * 0.01 * pow(2, e)
    return round(f, 2)

"""
Datapoint type three bytes with time value and optional day
"""

def en10(dt):
    return [0, (dt.isoweekday() << 5) | dt.hour, dt.minute, dt.second]


def de10(payload):
    h = payload[0] & 0x1f
    m = payload[1] & 0x3f
    s = payload[2] & 0x3f
    return datetime.time(h, m, s)

"""
Datapoint type three bytes with date value
"""

def en11(date):
    return [0, date.day, date.month, date.year - 2000]


def de11(payload):
    d = payload[0] & 0x1f
    m = payload[1] & 0x0f
    y = (payload[2] & 0x7f) + 2000  # sorry no 20th century...
    return datetime.date(y, m, d)

"""
Datapoint type four bytes with unsigned value
"""

def en12(value):
    if value < 0:
        value = 0
    elif value > 4294967295:
        value = 4294967295
    ret = bytearray([0])
    ret.extend(struct.pack('>I', int(value)))
    return ret


def de12(payload):
    if len(payload) != 4:
        return None
    return struct.unpack('>I', payload)[0]

"""
Datapoint type four bytes with signed value
"""

def en13(value):
    if value < -2147483648:
        value = -2147483648
    elif value > 2147483647:
        value = 2147483647
    ret = bytearray([0])
    ret.extend(struct.pack('>i', int(value)))
    return ret


def de13(payload):
    if len(payload) != 4:
        return None
    return struct.unpack('>i', payload)[0]

"""
Datapoint type four bytes with float value
"""
def en14(value):
    ret = bytearray([0])
    ret.extend(struct.pack('>f', value))
    return ret


def de14(payload):
    if len(payload) != 4:
        return None
    ret = struct.unpack('>f', payload)[0]
    if math.isnan(ret):
        return None
    else:
        return ret


"""
Datapoint type up to fourteen bytes with characters in ASCII or iso 8859-1
"""

def en16000(value):
    enc = bytearray(1)
    enc.extend(value.encode('ascii', 'replace')[:14])
    enc.extend([0] * (15 - len(enc)))
    return enc


def en16001(value):
    enc = bytearray(1)
    enc.extend(value.encode('iso-8859-1', 'replace')[:14])
    enc.extend([0] * (15 - len(enc)))
    return enc


def de16000(payload):
    return payload.rstrip(b'0').decode()


def de16001(payload):
    return payload.rstrip(b'0').decode('iso-8859-1')

"""
Datapoint type one byte with scene number
"""
def en17(value):
    return [0, int(value) & 0x3f]


def de17(payload):
    if len(payload) != 1:
        return None
    return struct.unpack('>B', payload)[0] & 0x3f


def en17001(value):
    return [0, (int(value) & 0x3f) - 1]


def de17001(payload):
    if len(payload) != 1:
        return None
    return (struct.unpack('>B', payload)[0] & 0x3f) + 1

"""
Datapoint type one byte with scene control
"""

def en18001(value):
    return [0, (int(value) & 0xbf) - 1]


def de18001(payload):
    if len(payload) != 1:
        return None
    return (struct.unpack('>B', payload)[0] & 0xbf) + 1

"""
DPT_DateTime
needs to be implemented if needed
 8 octets: U8 [r4 U4][r3 U5][U3 U5][r2 U6][r2 U6]B16
"""
#def en19(value):
#    return

#def de19(payload)
#    return

def en20(value):
    return [0, int(value) & 0xff]


def de20(payload):
    if len(payload) != 1:
        return None
    return struct.unpack('>B', payload)[0]


def en24(value):
    enc = bytearray(1)
    enc.extend(value.encode('iso-8859-1', 'replace'))
    enc.append(0)
    return enc


def de24(payload):
    return payload.rstrip(b'\x00').decode('iso-8859-1')

"""
Datapoint Type unicode UTF-8 string A[n]
"""
def en28(value):
    enc = bytearray(1)
    enc.extend(value.encode('utf-8', 'replace'))
    enc.append(0)
    return enc

def de28(payload):
    return payload.rstrip(b'\x00').decode('utf-8')

"""
Datapoint Type six Bytes with V32N8Z8
    229.001 DPT_MeteringValue
    Item Value then is a list of V32, N8 and Z8
"""

def en229(value):
    if len(value) != 3:
        return None
    retval = [0]
    retval.extend(struct.pack('>lBB',value[0],value[1],value[2]))
    return retval


def de229(payload):
    if len(payload) != 6:
        return None
    return list(struct.unpack('>lBB',payload))

"""
Datapoint type with three bytes U8U8U8
    232.600 DPT_Colour_RGB
"""

def en232(value):
    return [0, int(value[0]) & 0xff, int(value[1]) & 0xff, int(value[2]) & 0xff]


def de232(payload):
    if len(payload) != 3:
        return None
    return list(struct.unpack('>BBB', payload))

"""
Datapoint Types U8U8U8U8
    251.600 DPT_Colour_RGBW
    Only 4Bytes are used, first 2Bytes are unused
"""

def en251(value):
    return [0, 0x00, 0x0f, int(value[0]) & 0xff, int(value[1]) & 0xff, int(value[2]) & 0xff, int(value[3]) & 0xff]


def de251(payload):
    if len(payload) != 6:
        return None
    return list(struct.unpack('>BBBBBB', payload))[2:6]

"""
Datapoint type with eight bytes F16F16F16F16
    275.100 DPT_TempRoomSetpSetF16[4]
    Item Value then is a list of four F16 values
"""

def en275100(value):
    if len(value) != 4:
        return None
    retval = [0]
    for v in range(0,4):
        payload = en9(value[v])
        retval.extend(payload[1:])
        #retval.extend(struct.pack('>eeee',value[0],value[1],value[2], value[3]))
    return retval

def de275100(payload):
    if len(payload) != 8:
        return None
    return [de9(payload[0:2]),de9(payload[2:4]), de9(payload[4:6]), de9(payload[6:8])]


"""
Decode Physical Address
"""

def depa(ba):
    """expects a bytearray with length 2 in big endian"""
    if len(ba) != 2:
        return None
    pa = struct.unpack(">H", ba)[0]
    return "{0}.{1}.{2}".format((pa >> 12) & 0x0f, (pa >> 8) & 0x0f, (pa) & 0xff)

def enpa(pa):
    """expects a string containing the physical address of a device separated with a dot and no whitespace anywhere"""
    pa = pa.split('.')
    if len(pa)==3:
        area = int(pa[0]) & 0x0f
        line = int(pa[1]) & 0x0f
        device = int(pa[2]) & 0xff
        return [area << 4 | line, device]
    else:
        return None

"""
Group Address from and to string
"""

def enga(ga):
    ga = ga.split('/')
    return [int(ga[0]) << 3 | int(ga[1]), int(ga[2])]


def dega(string):
    if len(string) != 2:
        return None
    ga = struct.unpack(">H", string)[0]
    return "{0}/{1}/{2}".format((ga >> 11) & 0x1f, (ga >> 8) & 0x07, (ga) & 0xff)


decode = {
    '1': de1,
    '2': de2,
    '3': de3,
    '4002': de4002,
    '4.002': de4002,
    '5': de5,
    '5001': de5001,
    '5.001': de5001,
    '5999': de5999,
    '5.999': de5999,
    '6': de6,
    '7': de7,
    '8': de8,
    '9': de9,
    '10': de10,
    '11': de11,
    '12': de12,
    '13': de13,
    '14': de14,
    '16000': de16000,
    '16': de16000,
    '16001': de16001,
    '16.001': de16001,
    '17': de17,
    '17001': de17001,
    '17.001': de17001,
    '18001': de18001,
    '18.001': de18001,
    # '19' : de19,      #DPT_DateTime
    # '19001' : de19,   #DPT_DateTime
    # '19.001' : de19,  #DPT_DateTime
    '20': de20,
    '24': de24,
    '28': de28,         #DPT_UTF-8
    '28001': de28,      #DPT_UTF-8
    '28.001': de28,     #DPT_UTF-8
    '229': de229,
    '232': de232,
    '251': de251,       #RGBW
    '275.100' : de275100,
    'pa': depa,
    'ga': dega,
    'hex': dehex
}

encode = {
    '1': en1,           #One Bit
    '2': en2,           #Two Bits
    '3': en3,           #One Byte: relative Dimming or Blinds
    '4002': en4002,     # ASCII or 8859-1 encoded character
    '4.002': en4002,
    '5': en5,           #One Byte: unsigned value
    '5001': en5001,     #DPT_Scaling [0 ... 100] %
    '5.001': en5001,    #DPT_Scaling [0 ... 100] %
    # 5.003 -> DPT_Angle [0..360] °
    # 5.004 -> DPT_Percent_U8 [0..255] %
    # 5.005 -> DPT_DecimalFactor
    '5999': en5999,     #artificial data point for tebis TS systems
    '5.999': en5999,    #artificial data point for tebis TS systems
    '6': en6,           #One Byte: signed relative value or status with mode
    '7': en7,           #Two Bytes: unsigned value
    '8': en8,           #Two Bytes: signed value
    '9': en9,           #Two Bytes: float value
    '10': en10,         #Three Bytes: time (optional with day)
    '11': en11,         #Three Bytes: date
    '12': en12,         #Four Bytes: unsigned value
    '13': en13,         #Four Bytes: signed value
    '14': en14,         #Four Bytes: float value
    # '15': en15,       #Four Bytes: DPT_Access_Data
    '16': en16000,      #14 Bytes
    '16000': en16000,   #  ASCII
    '16001': en16001,   #  8859-1
    '16.001': en16001,
    '17': en17,         #One Byte: Scene Number
    '17001': en17001,
    '17.001': en17001,
    '18001': en18001,   #OneByte:
    '18.001': en18001,  #  DPT_SceneControl
    # '19' : en19,      #DPT_DateTime
    # '19001' : en19,   #DPT_DateTime
    # '19.001' : en19,  #DPT_DateTime
    '20': en20,         #One Byte: modes of several flavours
    # '21':en21,        #One Byte: status bit encoded
    # 22 undefined
    # '23': en23,       #OneByte: last two bits encode actions
    '24': en24,         #Variable lenght string encoded in 8859-1
    # 26                #One Byte: DPT_SceneInfo
    # 27                #Four Bytes: Combined Info On Off
    '28': en28,         #DPT_UTF-8
    '28001': en28,      #DPT_UTF-8
    '28.001': en28,     #DPT_UTF-8
    '229': en229,
    '232': en232,       #RGB
    '251': en251,       #RGBW
    '275.100' : en275100,   # Setpoint temperature, contains 4 values: Komfort, Standby, Night and Frost
    'pa': enpa,
    'ga': enga,
    'hex': enhex

}
