#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Ported by toggle, 2014-2016
#########################################################################
#  This software is based on the FHEM implementation
#  https://github.com/mhop/fhem-mirror/blob/master/fhem/FHEM/00_THZ.pm
#
#  THZ plugin for SmartHomeNG
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

"""
This file implements message definitions and
protocol encoding and decoding function for THZ/LWZ.
"""

import time
import sys
import logging
import threading
import datetime
import struct
from . import PortHandler

# mode mappings to plain text
OpMode = {'00': 'emergency', '01': 'standby', '03': 'DAYmode', '04': 'setback',
          '05': 'DHWmode', '11': 'automatic', '14': 'manual' }

OpModeHC = {'01': 'normal', '02': 'setback', '03': 'standby', '04': 'restart',
          '05': 'restart' }

logger = logging.getLogger('THZ')

"""
Decoding functions

data        contains the whole read data as bytes
offset      indicates the starting point where to start the conversion
length      provides the length of the data to convert
pos         alternative to a length this indicates the position within a packed binary
multiplier  provides a scalar to use for getting the converted data into the correct range
dummy       just a dummy with no meaning, keeping 4 params to the decoding API
"""

def decodeByte(data, offset, length, multiplier):
    return data[offset]

def decodeShort(data, offset, length, multiplier):
    val = int.from_bytes(data[offset:offset+length], byteorder='big')
    if val > 0x7FFF:
        val -= 0x10000
    return round(val * multiplier, 3)

def decodeLong(data, offset, length, multiplier):
    val = int.from_bytes(data[offset:offset+length], byteorder='big')
    if val > 0x7FFFFFFF:
        val -= 0x100000000
    return round(val * multiplier, 3)

def decodeFloat(data, offset, length, multiplier):
    val = struct.unpack('!f', data[offset:offset+4])[0]
    return round(val * multiplier, 3)

def decodeString(data, offset, length, dummy):
    return data[offset:offset+length].decode("utf-8")

def decodeHex(data, offset, length, dummy):
    return ''.join(format(x, '02x') for x in data[offset:offset+length])

def decodeBit(data, offset, pos, dummy):
    mask = 1 << pos
    value = 0
    if data[offset] & mask:
        value = 1
    return value

def decodeNBit(data, offset, pos, dummy):
    mask = 1 << pos
    value = 1
    if data[offset] & mask:
        value = 0
    return value

def decodeTime(data, offset, pos, dummy):
    str = '%02d:%02d:%02d'%(data[offset], data[offset+1], data[offset+2])
    return str

def decodeDate(data, offset, pos, dummy):
    str = '%02d/%02d/%02d'%(data[offset], data[offset+1], data[offset+2])
    return str

def decodeTime2(data, offset, pos, dummy):
    (hour, min) = divmod(int.from_bytes(data[offset:offset+2], byteorder='little'), 100)
    str = '%02d:%02d'%(hour, min)
    return str

def decodeDate2(data, offset, pos, dummy):
    # get the current year
    year = datetime.date.today().year - 2000

    # extract the date value
    val = int.from_bytes(data[offset:offset+2], byteorder='little')
    (day, month) = divmod(val, 100)

    # compute the current date value
    valCur = datetime.date.today().day * 100 + datetime.date.today().month
    if valCur < val:
        # the fault was reported last year
        year -= 1
    if day == 0 and month == 0:
        # date not set
        year = 0
    str = '%02d/%02d/%02d'%(year, month, day)
    return str

def decodeOpMode(data, offset, pos, dummy):
    try:
        str = OpMode[format(data[offset], '02d')]
    except:
        str = 'Unknown mode: ' . format(data[offset], '02d')
    return str

def decodeOpModeHC(data, offset, pos, dummy):
    try:
        str = OpModeHC[format(data[offset], '02d')]
    except:
        str = 'Unknown HC mode: ' . format(data[offset], '02d')
    return str

"""
Message definitions

message definitions for the version 5.39, SW ID 7278
"""

MsgTemplate = {

# read-only messages

  'sHistory': {
    'cmd1': '09',
    'params': {
      'compressorHeatingCycles':  [0, 2, decodeShort, 1],
      'compressorCoolingCycles':  [2, 2, decodeShort, 1],
      'compressorDHWCycles':      [4, 2, decodeShort, 1],
      'boosterDHWCycles':         [6, 2, decodeShort, 1],
      'boosterHeatingCycles':     [8, 2, decodeShort, 1]
    }
  },
  'sSol': {
    'cmd1': '16',
    'params': {
      'collectorTempSol':    [ 0, 2, decodeShort, 0.1],
      'dhwTempSol':          [ 2, 2, decodeShort, 0.1],
      'flowTempSol':         [ 4, 2, decodeShort, 0.1],
      'ed_sol_pump_temp':  [ 6, 2, decodeShort, 0.1],
      #'x20':               [ 8, 2, decodeHex, 1],
      #'x24':               [10, 2, decodeHex, 1], 
      #'x28':               [12, 2, decodeHex, 1],
      #'x32':               [14, 1, decodeHex, 1] 
    }
  },
  'sDHW': {
    'cmd1': 'F3',
    'params': {
      #'dhwTemp':           [ 0, 2, decodeShort, 0.1],
      #'outside_temp':      [ 2, 2, decodeShort, 0.1],
      'dhwSetTemp':        [ 4, 2, decodeShort, 0.1],
      'compBlockTime':     [ 6, 2, decodeShort, 1],
      #'x20':               [ 8, 2, decodeShort, 1],
      'heatBlockTime':     [10, 2, decodeShort, 1],
      #'x28':               [12, 2, decodeShort, 1],
      #'x32':               [14, 2, decodeShort, 1],
      #'x36':               [16, 2, decodeShort, 1]
    }
  },
  # 01 00 46 f4 ff fb ff 17 01 1f ff a6 01 53 01 33 01 2d 01 00 02 01 68 08 00 64 01 00 00 00 00 d2 00 00 1b 00 00 d2 02 00 00 1b 00 11
  # .. .. .. .. otemp ?? ?? rtemp integ flowT setT  currT ?? ?? mo ?? bits  integ md ?? ?? ?? roomT roomT ?? ?? ?? ?? ?? ?? ?? ?? ?? ??
  'sHC1': {
    'cmd1': 'F4',
    'params': {
      #'outsideTemp':       [ 0, 2, decodeShort, 0.1],
      #'x08':               [ 2, 2, decodeShort, 0.1],
      'returnTempHC1':        [ 4, 2, decodeShort, 0.1],
      'integralHeatHC1':      [ 6, 2, decodeShort, 1],
      'flowTempHC1':          [ 8, 2, decodeShort, 0.1],
      'heatSetTempHC1':       [10, 2, decodeShort, 0.1],
      'heatTempHC1':          [12, 2, decodeShort, 0.1],
      'onHysteresisNo':       [14, 1, decodeByte, 1],
      'offHysteresisNo':      [15, 1, decodeByte, 1],
      'HCBoosterStage':       [16, 1, decodeByte, 1],
      #'seasonMode':        [17, 1, decodeShort, 1], # 1: winter, 2: summer
      #'x40':              [18, 2, decodeShort, 1],
      #'integralSwitch':    [20, 2, decodeShort, 1],
      'opModeHC':          [22, 1, decodeOpModeHC, 1],
      #'x52':              [24, 2, decodeShort, 1],
      'roomSetTempHC1':    [26, 2, decodeShort, 0.1],
      'roomTempRC':        [32, 2, decodeShort, 0.1]
    }
  },
  'sHC2': {
    'cmd1': 'F5',
    'params': {
      #'outsideTemp':       [ 0, 2, decodeShort, 0.1],
      'returnTempHC2':     [ 2, 2, decodeShort, 0.1],
      #'flowTempHC2':       [ 4, 2, decodeShort, 0.1],
      'heatSetTempHC2':    [ 6, 2, decodeShort, 0.1],
      'heatTempHC2':       [ 8, 2, decodeShort, 0.1],
      #'stellgroesse':      [10, 2, decodeShort, 0.1],
      #'seasonMode':        [13, 1, decodeShort, 1],
      #'opMode':            [16, 1, decodeOpModeHC, 1]
    }
  },
  'sLast10errors': {
    'cmd1': 'D1',
    'params': {
      'numberOfFaults':    [ 0, 1, decodeShort, 1],  
      'fault0Code':        [ 2, 1, decodeShort, 1],
      'fault0Time':        [ 4, 2, decodeTime2, 1],
      'fault0Date':        [ 6, 2, decodeDate2, 1],
      'fault1Code':        [ 8, 1, decodeShort, 1],
      'fault1Time':        [10, 2, decodeTime2, 1],
      'fault1Date':        [12, 2, decodeDate2, 1],
      'fault2Code':        [14, 1, decodeShort, 1],
      'fault2Time':        [16, 2, decodeTime2, 1],
      'fault2Date':        [18, 2, decodeDate2, 1],
      'fault3Code':        [20, 1, decodeShort, 1],
      'fault3Time':        [22, 2, decodeTime2, 1],
      'fault3Date':        [24, 2, decodeDate2, 1]
    }
  },
  'sF7': {
    'cmd1': 'F7',
    'params': {
      'f7_flowTempHC2':           [ 0, 2, decodeShort, 0.1, '°C'],
      'f7_evaporatorTemp':        [ 6, 2, decodeShort, 0.1, '°C'],
      'f7_returnTempHC2':         [10, 2, decodeShort, 0.1, '°C'],
      'f7_outsideTemp':           [12, 2, decodeShort, 0.1, '°C'],
      'f7_flowTemp':              [14, 2, decodeShort, 0.1, '°C'],
    }
  },
  'sGlobal': {
    'cmd1': 'FB',
    'params': {
      'collectorTemp':         [ 0, 2, decodeShort, 0.1, '°C'],
      'outsideTemp':           [ 2, 2, decodeShort, 0.1, '°C'],
      'flowTemp':              [ 4, 2, decodeShort, 0.1, '°C'],
      'returnTemp':            [ 6, 2, decodeShort, 0.1, '°C'],
      'hotGasTemp':            [ 8, 2, decodeShort, 0.1, '°C'],
      'dhwTemp':               [10, 2, decodeShort, 0.1, '°C'],
      'flowTempHC2':           [12, 2, decodeShort, 0.1, '°C'],
      'insideTemp':            [14, 2, decodeShort, 0.1, '°C'],
      'evaporatorTemp':        [16, 2, decodeShort, 0.1, '°C'],
      'condenserTemp':         [18, 2, decodeShort, 0.1, '°C'],
      'mixerOpen':             [20, 0, decodeBit, 1],
      'mixerClosed':           [20, 1, decodeBit, 1],
      'heatPipeValve':         [20, 2, decodeBit, 1],
      'diverterValve':         [20, 3, decodeBit, 1],
      'dhwPumpOn':             [20, 4, decodeBit, 1],
      'heatingCircuitPumpOn':  [20, 5, decodeBit, 1],
      'solarPumpOn':           [20, 7, decodeBit, 1],
      'compressorOn':          [21, 3, decodeBit, 1],
      'boosterStage3On':       [21, 4, decodeBit, 1],
      'boosterStage2On':       [21, 5, decodeBit, 1],
      'boosterStage1On':       [21, 6, decodeBit, 1],
      'highPressureSensorOn':  [22, 0, decodeNBit, 1],
      'lowPressureSensorOn':   [22, 1, decodeNBit, 1],
      'evaporatorIceMonitorOn':[22, 2, decodeBit, 1],
      'signalAnodeOn':         [22, 3, decodeBit, 1],
      'evuEnable':             [22, 4, decodeBit, 1],
      'ovenFireplaceOn':       [22, 5, decodeBit, 1],
      'STB_On':                [22, 6, decodeBit, 1],
      'outputVentilatorPower': [23, 2, decodeShort, 0.1],
      'inputVentilatorPower':  [25, 2, decodeShort, 0.1],
      'mainVentilatorPower':   [27, 2, decodeShort, 0.1],
      'outputVentilatorSpeed': [29, 2, decodeShort, 1],
      'inputVentilatorSpeed':  [31, 2, decodeShort, 1],
      'mainVentilatorSpeed':   [33, 2, decodeShort, 1],
      'outside_tempFiltered':  [35, 2, decodeShort, 0.1, '°C'],
      'relHumidity':           [37, 2, decodeShort, 0.1, '%'],
      'dewPoint':              [39, 2, decodeShort, 0.1, '°C'],
      'P_Nd':                  [41, 2, decodeShort, 0.01],
      'P_Hd':                  [43, 2, decodeShort, 0.01],
      'actualPower_Qc':        [45, 4, decodeFloat, 0.001],
      'actualPower_Pel':       [49, 4, decodeFloat, 1],
      'electricPower':         [53, 2, decodeShort, 1],
      'temp55':                [55, 2, decodeShort, 0.1, '°C'],
      'temp57':                [57, 2, decodeShort, 0.1, '°C'],
      'temp61':                [61, 2, decodeShort, 0.1, '°C'],
      'temp63':                [63, 2, decodeShort, 0.1, '°C'],
      'temp65':                [65, 2, decodeShort, 0.1, '°C'],
      'temp67':                [67, 2, decodeShort, 0.1, '°C'],
      'temp69':                [69, 2, decodeShort, 0.1, '°C'],
      'temp75':                [75, 2, decodeShort, 0.1, '°C']
    },
  },
  'sTimeDate': {
    'cmd1': 'FC',
    'params': {
      'time':                  [ 1, 3, decodeTime, 1],
      'date':                  [ 4, 3, decodeDate, 1],
    }
  },
  'sFirmware': {
    'cmd1': 'FD',
    'params': {
      'version':               [ 0, 2, decodeShort, 0.01]
    }
  },
  'sProdDate': {
    'cmd1': 'FE',
    'params': {
      'prodDate':              [ 16, 11, decodeString, 1]
    }
  },
  # 01 00 00 f3 7d 00 00 e3 c2 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 07 39 22 20 00 c8 00 c8 32 32 00
  'sVentilation': {
    'cmd1': 'E8',
    'params': {
      'inputVentSpeed':        [27, 1, decodeByte, 1],
      'outputVentSpeed':       [28, 1, decodeByte, 1],
      'inputAirFlow':          [29, 2, decodeShort, 1],
      'outputAirFlow':         [31, 2, decodeShort, 1]
      #'outputVentilatorPower': [33, 1, decodeByte, 0.1],
      #'inputVentilatorPower':  [34, 1, decodeByte, 0.1]
    }
  },
  # 01 00 3f e9 04 b0 02 5a 04 9c 02 49 02 8f 30 02 4a 11 52 60 08 11 11 fe b3 08 77 00 30
  # .. .. .. .. ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 30 02 4a 11 52 .. .. .. 11 fe b3 08 77 00 30
  'sE9': {
    'cmd1': 'E9',
    'params': {
      'e9_mixerOpen':             [15, 0, decodeBit, 1],
      'e9_mixerClosed':           [15, 1, decodeBit, 1],
      'e9_heatPipeValve':         [15, 2, decodeBit, 1],
      'e9_diverterValve':         [15, 3, decodeBit, 1],
      'e9_dhwPumpOn':             [15, 4, decodeBit, 1],
      'e9_heatingCircuitPumpOn':  [15, 5, decodeBit, 1],
      'e9_solarPumpOn':           [15, 7, decodeBit, 1],
      'e9_compressorOn':          [16, 3, decodeBit, 1],
      'e9_boosterStage3On':       [16, 4, decodeBit, 1],
      'e9_boosterStage2On':       [16, 5, decodeBit, 1],
      'e9_boosterStage1On':       [16, 6, decodeBit, 1],
      'e9_highPressureSensorOn':  [17, 0, decodeNBit, 1],
      'e9_lowPressureSensorOn':   [17, 1, decodeNBit, 1],
      'e9_evaporatorIceMonitorOn':[17, 2, decodeBit, 1],
      'e9_signalAnodeOn':         [17, 3, decodeBit, 1],
      'e9_evuEnable':             [17, 4, decodeBit, 1],
      'e9_ovenFireplaceOn':       [17, 5, decodeBit, 1],
      'e9_STB_On':                [17, 6, decodeBit, 1],
    }
  },
  'sFan': {
    'cmd1': 'F6',
    'params': {
      'fanStage':              [4, 1, decodeByte, 1]
    }
  },
  'sIcons': {
    'cmd1': '0A0176',
    'params': {
      'iconProgram':           [ 1, 0, decodeBit, 1],
      'iconCompressor':        [ 1, 1, decodeBit, 1],
      'iconHeating':           [ 1, 2, decodeBit, 1],
      'iconCooling':           [ 1, 3, decodeBit, 1],
      'iconDHW':               [ 1, 4, decodeBit, 1],
      'iconBooster':           [ 1, 5, decodeBit, 1],
      'iconService':           [ 1, 6, decodeBit, 1],
      'iconBothFilters':       [ 0, 0, decodeBit, 1],
      'iconVentilation':       [ 0, 1, decodeBit, 1],
      'iconCirculationPump':   [ 0, 2, decodeBit, 1],
      'iconDeicingCondenser':  [ 0, 3, decodeBit, 1],
      'iconUpperFilter':       [ 0, 4, decodeBit, 1],
      'iconLowerFilter':       [ 0, 5, decodeBit, 1]
    }
  },
  'sFlowRateHC1': {
    'cmd1': '0A033B',
    'params': {
      'flowRateHC1':           [ 0, 2, decodeShort, 0.1]
    }
  },
  'sSoftwareID': {
    'cmd1': '0A024B',
    'params': {
      'softwareID':            [ 0, 2, decodeShort, 1]
    }
  },
  'sBoostDHWTotal': {
    'cmd1': '0A0924', 'cmd2': '0A0925',
    'params': {
      'boostDHWTotal':         [ 0, 2, decodeShort, 1]
    }
  },
  'sBoostHCTotal': {
    'cmd1': '0A0928', 'cmd2': '0A0929',
    'params': {
      'boostHCTotal':          [ 0, 2, decodeShort, 1]
    }
  },
  'sHeatRecoveredDay': {
    'cmd1': '0A03AE', 'cmd2': '0A03AF',
    'params': {
      'heatRecoveredDay':      [ 0, 2, decodeShort, 0.001]
    }
  },
  'sHeatRecoveredTotal': {
    'cmd1': '0A03B0', 'cmd2': '0A03B1',
    'params': {
      'heatRecoveredTotal':    [ 0, 2, decodeShort, 1]
    }
  },
  'sHeatDHWDay': {
    'cmd1': '0A092A', 'cmd2': '0A092B',
    'params': {
      'heatDHWDay':            [ 0, 2, decodeShort, 0.001]
    }
  },
  'sHeatDHWTotal': {
    'cmd1': '0A092C', 'cmd2': '0A092D',
    'params': {
      'heatDHWTotal':          [ 0, 2, decodeShort, 1]
    }
  },
  'sHeatHCDay': {
    'cmd1': '0A092E', 'cmd2': '0A092F',
    'params': {
      'heatHCDay':             [ 0, 2, decodeShort, 0.001]
    }
  },
  'sHeatHCTotal': {
    'cmd1': '0A0930', 'cmd2': '0A0931',
    'params': {
      'heatHCTotal':           [ 0, 2, decodeShort, 1]
    }
  },
  'sEPowerDHWDay': {
    'cmd1': '0A091A', 'cmd2': '0A091B',
    'params': {
      'ePowerDHWDay':          [ 0, 2, decodeShort, 0.001]
    }
  },
  'sEPowerDHWTotal': {
    'cmd1': '0A091C', 'cmd2': '0A091D',
    'params': {
      'ePowerDHWTotal':        [ 0, 2, decodeShort, 1]
    }
  },
  'sEPowerHCDay': {
    'cmd1': '0A091E', 'cmd2': '0A091F',
    'params': {
      'ePowerHCDay':           [ 0, 2, decodeShort, 0.001]
    }
  },
  'sEPowerHCTotal': {
    'cmd1': '0A0920', 'cmd2': '0A0921',
    'params': {
      'ePowerHCTotal':         [ 0, 2, decodeShort, 1]
    }
  },

# read/write messages and parameters

  'pOpMode': {
    'cmd1': '0A0112', 'rw': 1,
    'params': {
      'pOpMode':               [0, 1, decodeOpMode, 1, 0, 14]
    }
  },
  'p01RoomTempDayHC1': {
    'cmd1': '0B0005', 'rw': 1,
    'params': {
      'p01RoomTempDayHC1': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p02RoomTempNightHC1': {
    'cmd1': '0B0008', 'rw': 1,
    'params': {
      'p02RoomTempNightHC1': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p03RoomTempStandbyHC1': {
    'cmd1': '0B013D', 'rw': 1,
    'params': {
      'p03RoomTempStandbyHC1': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p01RoomTempDayHC1SummerMode': {
    'cmd1': '0B0569', 'rw': 1,
    'params': {
      'p01RoomTempDayHC1SummerMode': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p02RoomTempNightHC1SummerMode': {
    'cmd1': '0B056B', 'rw': 1,
    'params': {
      'p02RoomTempNightHC1SummerMode': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p03RoomTempStandbyHC1SummerMode': {
    'cmd1': '0B056A', 'rw': 1,
    'params': {
      'p03RoomTempStandbyHC1SummerMode': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p13GradientHC1': {
    'cmd1': '0B010E', 'rw': 1,
    'params': {
      'p13GradientHC1': [0, 2, decodeShort, 0.01, 0, 5]
      }
  },
  'p14LowEndHC1': {
    'cmd1': '0B059E', 'rw': 1,
    'params': {
      'p14LowEndHC1': [0, 2, decodeShort, 0.1, 0, 20]
      }
  },
  'p15RoomInfluenceHC1': {
    'cmd1': '0B010F', 'rw': 1,
    'params': {
      'p15RoomInfluenceHC1': [0, 2, decodeShort, 1, 0, 100]
      }
  },
  'p19FlowProportionHC1': {
    'cmd1': '0B059D', 'rw': 1,
    'params': {
      'p19FlowProportionHC1': [0, 2, decodeShort, 1,  0, 100]
      }
  },
  'p01RoomTempDayHC2': {
    'cmd1': '0C0005', 'rw': 1,
    'params': {
      'p01RoomTempDayHC2': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p02RoomTempNightHC2': {
    'cmd1': '0C0008', 'rw': 1,
    'params': {
      'p02RoomTempNightHC2': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p03RoomTempStandbyHC2': {
    'cmd1': '0C013D', 'rw': 1,
    'params': {
      'p03RoomTempStandbyHC2': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p01RoomTempDayHC2SummerMode': {
    'cmd1': '0C0569', 'rw': 1,
    'params': {
      'p01RoomTempDayHC2SummerMode': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p02RoomTempNightHC2SummerMode': {
    'cmd1': '0C056B', 'rw': 1,
    'params': {
      'p02RoomTempNightHC2SummerMode': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p03RoomTempStandbyHC2SummerMode': {
    'cmd1': '0C056A', 'rw': 1,
    'params': {
      'p03RoomTempStandbyHC2SummerMode': [0, 2, decodeShort, 0.1, 10, 30]
      }
  },
  'p16GradientHC2': {
    'cmd1': '0C010E', 'rw': 1,
    'params': {
      'p16GradientHC2': [0, 2, decodeShort, 0.01, 0, 5]
      }
  },
  'p17LowEndHC2': {
    'cmd1': '0C059E', 'rw': 1,
    'params': {
      'p17LowEndHC2': [0, 2, decodeShort, 0.1, 0, 20]
      }
  },
  'p18RoomInfluenceHC2': {
    'cmd1': '0C010F', 'rw': 1,
    'params': {
      'p18RoomInfluenceHC2': [0, 2, decodeShort, 1, 0, 100]
      }
  },
  'p04DHWsetDayTemp': {
    'cmd1': '0A0013', 'rw': 1,
    'params': {
      'p04DHWsetDayTemp': [0, 2, decodeShort, 0.1, 10, 55]
      }
  },
  'p05DHWsetNightTemp': {
    'cmd1': '0A05BF', 'rw': 1,
    'params': {
      'p05DHWsetNightTemp': [0, 2, decodeShort, 0.1, 10, 55]
      }
  },
  'p83DHWsetSolarTemp': {
    'cmd1': '0A05BE', 'rw': 1,
    'params': {
      'p83DHWsetSolarTemp': [0, 2, decodeShort, 0.1, 10, 65]
      }
  },
  'p06DHWsetStandbyTemp': {
    'cmd1': '0A0581', 'rw': 1,
    'params': {
      'p06DHWsetStandbyTemp': [0, 2, decodeShort, 0.1, 10, 55]
      }
  },
  'p11DHWsetManualTemp': {
    'cmd1': '0A0580', 'rw': 1,
    'params': {
      'p11DHWsetManualTemp': [0, 2, decodeShort, 0.1, 10, 55]
      }
  },
  'p07FanStageDay': {
    'cmd1': '0A056C', 'rw': 1,
    'params': {
      'p07FanStageDay': [0, 2, decodeShort, 1,  0, 3]
      }
  },
  'p08FanStageNight': {
    'cmd1': '0A056D', 'rw': 1,
    'params': {
      'p08FanStageNight': [0, 2, decodeShort, 1,  0, 3]
      }
  },
  'p09FanStageStandby': {
    'cmd1': '0A056F', 'rw': 1,
    'params': {
      'p09FanStageStandby': [0, 2, decodeShort, 1,  0, 3]
      }
  },
  'p99FanStageParty': {
    'cmd1': '0A0570', 'rw': 1,
    'params': {
      'p99FanStageParty': [0, 2, decodeShort, 1,  0, 3]
      }
  },
  'p75passiveCooling': {
    'cmd1': '0A0575', 'rw': 1,
    'params': {
      'p75passiveCooling': [0, 2, decodeShort, 1,  0, 4]
      }
  },
  'p21Hyst1': {
    'cmd1': '0A05C0', 'rw': 1,
    'params': {
      'p21Hyst1': [0, 2, decodeShort, 0.1,  0, 10]
      }
  },
  'p22Hyst2': {
    'cmd1': '0A05C1', 'rw': 1,
    'params': {
      'p22Hyst2': [0, 2, decodeShort, 0.1,  0, 10]
      }
  },
  'p23Hyst3': {
    'cmd1': '0A05C2', 'rw': 1,
    'params': {
      'p23Hyst3': [0, 2, decodeShort, 0.1,  0, 5]
      }
  },
  'p24Hyst4': {
    'cmd1': '0A05C3', 'rw': 1,
    'params': {
      'p24Hyst4': [0, 2, decodeShort, 0.1,  0, 5]
      }
  },
  'p25Hyst5': {
    'cmd1': '0A05C4', 'rw': 1,
    'params': {
      'p25Hyst5': [0, 2, decodeShort, 0.1,  0, 5]
      }
  },
  'p29HystAsymmetry': {
    'cmd1': '0A05C5', 'rw': 1,
    'params': {
      'p29HystAsymmetry': [0, 2, decodeShort, 1,  1, 5]
      }
  },
  'p30integralComponent': {
    'cmd1': '0A0162', 'rw': 1,
    'params': {
      'p30integralComponent': [0, 2, decodeShort, 1,  10, 999]
      }
  },
  'p32hystDHW': {
    'cmd1': '0A0140', 'rw': 1,
    'params': {
      'p32hystDHW': [0, 2, decodeShort, 1,  0, 10]
      }
  },
  'p33BoosterTimeoutDHW': {
    'cmd1': '0A0588', 'rw': 1,
    'params': {
      'p33BoosterTimeoutDHW': [0, 2, decodeShort, 1,  0, 200]
      }
  },
  'p79BoosterTimeoutHC': {
    'cmd1': '0A05A0', 'rw': 1,
    'params': {
      'p79BoosterTimeoutHC': [0, 2, decodeShort, 1,  0, 240]
      }
  },
  'p46UnschedVent0': {
    'cmd1': '0A0571', 'rw': 1,
    'params': {
      'p46UnschedVent0': [0, 2, decodeShort, 1,  0, 900]
      }
  },
  'p45UnschedVent1': {
    'cmd1': '0A0572', 'rw': 1,
    'params': {
      'p45UnschedVent1': [0, 2, decodeShort, 1,  0, 900]
      }
  },
  'p44UnschedVent2': {
    'cmd1': '0A0573', 'rw': 1,
    'params': {
      'p44UnschedVent2': [0, 2, decodeShort, 1,  0, 900]
      }
  },
  'p43UnschedVent3': {
    'cmd1': '0A0574', 'rw': 1,
    'params': {
      'p43UnschedVent3': [0, 2, decodeShort, 1,  0, 900]
      }
  },
#  'p99UnschedVentStage': {
#    'cmd1': '0A05DD', 'rw': 1,
#    'params': {
#      'p99UnschedVentStage': [0, 2, decodeShort, 1, 0, 3]
#      }
#  },
  'p37FanStage1AirIn': {
    'cmd1': '0A0576', 'rw': 1,
    'params': {
      'p37FanStage1AirIn': [0, 2, decodeShort, 1,  50, 300]
      }
  },
  'p38FanStage2AirIn': {
    'cmd1': '0A0577', 'rw': 1,
    'params': {
      'p38FanStage2AirIn': [0, 2, decodeShort, 1,  50, 300]
      }
  },
  'p39FanStage3AirIn': {
    'cmd1': '0A0578', 'rw': 1,
    'params': {
      'p39FanStage3AirIn': [0, 2, decodeShort, 1,  50, 300]
      }
  },
  'p40FanStage1AirOut': {
    'cmd1': '0A0579', 'rw': 1,
    'params': {
      'p40FanStage1AirOut': [0, 2, decodeShort, 1,  50, 300]
      }
  },
  'p41FanStage2AirOut': {
    'cmd1': '0A057A', 'rw': 1,
    'params': {
      'p41FanStage2AirOut': [0, 2, decodeShort, 1,  50, 300]
      }
  },
  'p42FanStage3AirOut': {
    'cmd1': '0A057B', 'rw': 1,
    'params': {
      'p42FanStage3AirOut': [0, 2, decodeShort, 1,  50, 300]
      }
  },
  'p49SummerModeTemp': {
    'cmd1': '0A0116', 'rw': 1,
    'params': {
      'p49SummerModeTemp': [0, 2, decodeShort, 0.1, 10, 25]
      }
  },
  'p50SummerModeHysteresis': {
    'cmd1': '0A05A2', 'rw': 1,
    'params': {
      'p50SummerModeHysteresis': [0, 2, decodeShort, 0.1, 0.5, 5]
      }
  },
  'p78DualModePoint': {
    'cmd1': '0A01AC', 'rw': 1,
    'params': {
      'p78DualModePoint': [0, 2, decodeShort, 0.1, -10, 20]
      }
  },
  'p54MinPumpCycles': {
    'cmd1': '0A05B8', 'rw': 1,
    'params': {
      'p54MinPumpCycles': [0, 2, decodeShort, 1,  1, 24]
      }
  },
  'p55MaxPumpCycles': {
    'cmd1': '0A05B7', 'rw': 1,
    'params': {
      'p55MaxPumpCycles': [0, 2, decodeShort, 1, 25, 200]
      }
  },
  'p56OutTempMaxPumpCycles': {
    'cmd1': '0A05B9', 'rw': 1,
    'params': {
      'p56OutTempMaxPumpCycles': [0, 2, decodeShort, 0.1, 0, 20]
      }
  },
  'p57OutTempMinPumpCycles': {
    'cmd1': '0A05BA', 'rw': 1,
    'params': {
      'p57OutTempMinPumpCycles': [0, 2, decodeShort, 0.1, 0, 25]
      }
  },
  'p76RoomThermCorrection': {
    'cmd1': '0A0109', 'rw': 1,
    'params': {
      'p76RoomThermCorrection': [0, 2, decodeShort, 0.000390625, -5, 5]
      }
  },
  'p77OutThermFilterTime': {
    'cmd1': '0A010C', 'rw': 1,
    'params': {
      'p77OutThermFilterTime': [0, 2, decodeShort, 1, 1, 24]
      }
  },
  'p35PasteurisationInterval': {
    'cmd1': '0A0586', 'rw': 1,
    'params': {
      'p35PasteurisationInterval': [0, 2, decodeShort, 1, 1, 30]
      }
  },
  'p35PasteurisationTemp': {
    'cmd1': '0A0587', 'rw': 1,
    'params': {
      'p35PasteurisationTemp': [0, 2, decodeShort, 0.1, 10, 65]
      }
  },
  'p34BoosterDHWTempAct': {
    'cmd1': '0A0589', 'rw': 1,
    'params': {
      'p34BoosterDHWTempAct': [0, 2, decodeShort, 0.1, -10, 10]
      }
  },
  'p99DHWmaxFlowTemp': {
    'cmd1': '0A058C', 'rw': 1,
    'params': {
      'p99DHWmaxFlowTemp': [0, 2, decodeShort, 0.1, 10, 75]
      }
  },
  'p89DHWeco': {
    'cmd1': '0A058D', 'rw': 1,
    'params': {
      'p89DHWeco': [0, 2, decodeShort, 1, 0, 1]
      }
  },
  'p99startUnschedVent': {
    'cmd1': '0A05DD', 'rw': 1,
    'params': {
      'p99startUnschedVent': [0, 2, decodeShort, 1, 0, 3]
      }
  },
  'p99CoolingSwitch': {
    'cmd1': '0B0287', 'rw': 1,
    'params': {
      'p99CoolingSwitch': [0, 2, decodeShort, 1, 0, 1]
      }
  },
  'pClockDay': {
    'cmd1': '0A0122', 'rw': 1,
    'params': {
      'pClockDay': [0, 2, decodeShort, 1, 1, 31]
      }
  },
  'pClockMonth': {
    'cmd1': '0A0123', 'rw': 1,
    'params': {
      'pClockMonth': [0, 2, decodeShort, 1, 1, 12]
      }
  },
  'pClockYear': {
    'cmd1': '0A0124', 'rw': 1,
    'params': {
      'pClockYear': [0, 2, decodeShort, 1, 12, 20]
      }
  },
  'pClockHour': {
    'cmd1': '0A0125', 'rw': 1,
    'params': {
      'pClockHour': [0, 2, decodeShort, 1, 0, 23]
      }
  },
  'pClockMinute': {
    'cmd1': '0A0126', 'rw': 1,
    'params': {
      'pClockMinute': [0, 2, decodeShort, 1, 0, 59]
      }
  }
}

# Message deltas for other heat pumps
# The key may have the following values:
#   ap - add parameter (replace if already defined)
#   am - add message (replace if already defined)
#   dp - delete parameter
#   dm - delete message

VersionSpecificMsgData = {
# deltas for the 4.39 (303i)
  '4.39': {
    'ap':
      ['sGlobal', 'actualPower_Qc', [45, 4, decodeFloat, 1]]
  },
# deltas for the 5.19 (304)
  '5.19': {
  },
}


class ThzProtocol():
    """
    THZ high-level protocol implementation
    """
    def __init__(self, serial_port, baudrate, logger):
        self._portHandler = PortHandler.PortHandler(serial_port, baudrate, logger)
        self._serial_port = serial_port
        self._baudrate = baudrate
        self.logger = logger
        # lookup table for command names from code
        self._msgNameFromCode = {}
        self._msgNameFromParam = {}
        self._txCount = 0
        self._rxCount = 0
        self._rxChecksumErrorCount = 0
        self._rxNackCount = 0
        self._rxTimeoutCount = 0
        self._portErrorCount = 0
        self._lock = threading.Lock()

        # init message mappings
        self._opModeInv = {v: k for k, v in OpMode.items()}

        for name in MsgTemplate:
          # fill the mapping for decoding
          self._msgNameFromCode[MsgTemplate[name]['cmd1']] = name
          if 'cmd2' in MsgTemplate[name]:
            self._msgNameFromCode[MsgTemplate[name]['cmd2']] = name

          # fill the mapping from parameter to message
          for param in MsgTemplate[name]['params'].keys():
            if param in self._msgNameFromParam:
              raise ValueError('thz: Ambiguous parameter name: ', param)
            self._msgNameFromParam[param] = name

        self._portHandler.start()

        if self._portHandler.isPortOpen():
          # check the software version and configure messages appropriately
          msg = self._sendGetRequest(MsgTemplate['sFirmware']['cmd1'])
          if not msg == None:
            version = msg['sFirmware']['version']
            if version in VersionSpecificMsgData:
              # version-specific update available
              msgUpdate = VersionSpecificMsgData[version]
              for action in msgUpdate:
                if action == 'ap':
                  # add parameters
                  for i in msgUpdate[action]:
                    msgName = msgUpdate[action][i][0]
                    paramName = msgUpdate[action][i][1]
                    MsgTemplate[msgName][paramName] =  msgUpdate[action][i][2]
                elif action == 'dp':
                  # add parameters
                  for i in msgUpdate[action]:
                    msgName = msgUpdate[action][i][0]
                    paramName = msgUpdate[action][i][1]
                    MsgTemplate[msgName].pop(paramName, None)
                elif action == 'am':
                  # add messages
                  for i in msgUpdate[action]:
                    msgName = msgUpdate[action][i][0]
                    MsgTemplate[msgName] = msgUpdate[action][i][1]
                elif action == 'dm':
                  # delete messages
                  for i in msgUpdate[action]:
                    msgName = msgUpdate[action][i][0]
                    MsgTemplate.pop(msgName, None)
              self.logger.info('thz: Message templates adjusted to version {}'.format(version))
            else:
              # no version-specific data availble
              self.logger.info('thz: Using generic message templates with version {}'.format(version))
          else:
            self.logger.warning('thz: The messages could not be adjusted to the heat pump version due to missing heat pump response.')

        else:
          self.logger.warning('thz: The messages could not be adjusted to the heat pump version due to com port failure.')

    def __del__(self):
        self._portHandler.stop()

    def _computeChecksum(self, data):
        """
        _computeChecksum() computes message checksum
        """
        chksum = 0
        for x in data:
          chksum = chksum + x
        return chksum % 256

    def _encodeGetMsg(self, cmd):
        """
        _encodeGetMsg() encodes the message header and the payload of a GET message
        define the 'read' header including the checksum byte
        """
        msg = bytearray.fromhex('010000')
        msg += bytearray.fromhex(cmd)
        # set the checksum
        msg[2] = self._computeChecksum(msg)
        return msg

    def _encodeSetMsg(self, cmd, value):
        """_encodeSetMsg() encodes the message header and the payload of a SET message"""
        # define the 'write' header including the checksum byte
        msg = bytearray.fromhex('018000')
        msg += bytearray.fromhex(cmd)
        msg += int(value).to_bytes(2, byteorder='big')
        # set the checksum
        msg[2] = self._computeChecksum(msg)
        return msg

    def _decodeMsg(self, data):
        """_decodeMsg() decodes the message header and the payload"""
        if len(data) < 5:
          return None
        data = bytearray(data)

        if data[3] == 0x0a or data[3] == 0x0b or data[3] == 0x0c:
          reg = '%02X%02X%02X'%(data[3],data[4],data[5])
        else:
          reg = '%02X'%(data[3])

        if data[0] == 0x15:
          self._rxNackCount += 1
          self.logger.warning('NACK received (reg {})'.format(reg));
        elif data[0] == 0x01 and data[1] == 0x01:
          self._rxNackCount += 1
          self.logger.warning('NACK: Waiting for ACK');
        elif data[0] == 0x01 and data[1] == 0x02:
          self._rxNackCount += 1
          self.logger.warning('NACK: Unknown command {}'.format(reg));
        elif data[0] == 0x01 and data[1] == 0x03:
          self._rxNackCount += 1
          self.logger.warning('NACK: Invalid CRC');
        elif data[0] == 0x01 and data[1] == 0x04:
          self._rxNackCount += 1
          self.logger.warning('NACK: Unknown register {}'.format(reg));
        elif data[0] == 0x01 and data[1] == 0x00:
          # check the CRC
          crc = data[2]
          data[2] = 0x00
          if crc != self._computeChecksum(data):
            self._rxChecksumErrorCount += 1
            self.logger.warning('Received message with bad CRC')
            return None
          if data[3] == 0x0a or data[3] == 0x0b or data[3] == 0x0c:
            param = '%02X%02X%02X'%(data[3],data[4],data[5])
            payload = data[6:]
          else:
            param = '%02X'%(data[3])
            payload = data[4:]
          if param in self._msgNameFromCode:
            name = self._msgNameFromCode[param]
            self.logger.debug('param = {} ({})'.format(name, param))
          else:
            self.logger.warning('Rx: Unknown command - {}'.format(param))
            return None
          msg = {name: {}}
          for key in MsgTemplate[name]['params'].keys():
            # get the parameter definition
            item = MsgTemplate[name]['params'][key]
            # decode the parameter value according to the definition
            try:
              msg[name][key] = item[2](payload, item[0], item[1], item[3])
            except IndexError:
              self.logger.warning('Message {} too short (length = {}, index = {})'.format(name, len(payload), item[0]))
          return msg
        return None

    def _sendGetRequest(self, cmd):
        """_sendGetRequest() encodes and sends a GET message and processes the response"""
        self._lock.acquire()
        try:
          msg = self._encodeGetMsg(cmd)
          self._portHandler.sendData(msg)
          self._txCount += 1
          data = self._portHandler.readData()
          if not data == None:
            self._rxCount += 1
            self.logger.debug('Rx: ' + ' '.join(format(x, '02x') for x in data))
            msg = self._decodeMsg(data)
          else:
            self._rxTimeoutCount += 1
            msg = None
        except:
          self.logger.error('Get request failed - {:06x}\n{}'.format(cmd, sys.exc_info()))
        finally:
          self._lock.release()
        return msg

    def getMsgFromParameter(self, param):
        """returns the message name for the given parameter name"""
        if param in self._msgNameFromParam:
          return self._msgNameFromParam[param]
        else:
          return None

    def isParameterWritable(self, param):
        """returns True if the specified parameter is writable"""
        if param in self._msgNameFromParam:
          if 'rw' in MsgTemplate[self._msgNameFromParam[param]]:
            return True
        return False

    def sendSetRequest(self, param, value):
        """encodes and sends a SET request and processes the response"""
        # check the port status
        if not self._portHandler.isPortOpen():
          self._portErrorCount += 1
          if not self._portHandler.openPort(self._serial_port, self._baudrate):
            return

        if param in self._msgNameFromParam:
          # it is assumed that the message is a single-parameter message
          self._lock.acquire()
          try:
            tmpl = MsgTemplate[param]
            if param == 'pOpMode':
              # translate string to integer
              if value in self._opModeInv:
                value = int(self._opModeInv[value])
              else:
                self.logger.warning('Invalid parameter value - {}:{}'.format(param, value))
                return
            if (value < tmpl['params'][param][4] or
                value > tmpl['params'][param][5]):
              self.logger.warning('Parameter value out of range - {}={}, [{}:{}]'.format(param, value, tmpl['params'][param][4], tmpl['params'][param][5]))
            else:
              # value OK
              value = int(value / tmpl['params'][param][3])
              if (tmpl['params'][param][1] == 1):
                  value *= 256
              if value < 0:
                  value += 0x10000
              msg = self._encodeSetMsg(tmpl['cmd1'], value)
              self._portHandler.sendData(msg)
              self._txCount += 1

              # check the response
              data = self._portHandler.readData()
              if data == None:
                self.logger.warning('Set request timed out')
                self._rxTimeoutCount += 1
              else:
                self.logger.debug('Rx: ' + ' '.join(format(x, '02x') for x in data))
                self._rxCount += 1
              if not (data[0] == 0x01 and data[1] == 0x80):
                self.logger.warning('Set request failed - {}: {}'.format(param, ' '.join(format(x, '02x') for x in data)))
                self._rxNackCount += 1
          except:
            self.logger.error('Message encoding failed - {}\n{}'.format(param, sys.exc_info()))
          finally:
            self._lock.release()
        else:
          self.logger.warning('Invalid parameter name - {}'.format(param))

    def sendRawSetRequest(self, param, value):
        """encodes and sends a RAW SET request and processes the response. Param and value are hex strings."""
        # check the port status
        if not self._portHandler.isPortOpen():
          self._portErrorCount += 1
          if not self._portHandler.openPort(self._serial_port, self._baudrate):
            return

        self._lock.acquire()
        try:
            msg = self._encodeSetMsg(param, value)
            self._portHandler.sendData(msg)
            self._txCount += 1

            # check the response
            data = self._portHandler.readData()
            if data == None:
              self.logger.warning('Set request timed out')
              self._rxTimeoutCount += 1
            else:
              self.logger.info('Rx: ' + ' '.join(format(x, '02x') for x in data))
              self._rxCount += 1
            if not (data[0] == 0x01 and data[1] == 0x80):
              self.logger.warning('Set request failed - {}: {}'.format(param, ' '.join(format(x, '02x') for x in data)))
              self._rxNackCount += 1
        except:
          self.logger.error('Message encoding failed - {}\n{}'.format(param, sys.exc_info()))
        finally:
            self._lock.release()

    def requestData(self, request):
        """returns a dict with message and parameter values for the specified request"""
        # check the port status
        if not self._portHandler.isPortOpen():
          self._portErrorCount += 1
          if not self._portHandler.openPort(self._serial_port, self._baudrate):
            return {}

        response = {}
        try:
          noResponseCount = 0
          for name in request:
            msg1 = self._sendGetRequest(MsgTemplate[name]['cmd1'])
            if not msg1 == None:
              noResponseCount = 0
              if 'cmd2' in MsgTemplate[name]:
                # there is a second command to retrieve the most significant part
                msg2 = self._sendGetRequest(MsgTemplate[name]['cmd2'])
                if not msg2 == None:
                  # get the name of the one and only parameter
                  param = list(msg1[name].keys())[0]
                  try:
                    # combine the two values (the most significant part is to
                    # be multiplied by 1000)
                    msg1[name][param] = round(msg2[name][param] * 1000 + msg1[name][param],3)
                    response.update(msg1[name])
                  except:
                    self.logger.warning(sys.exc_info())
              else:
                # there is only one response
                response.update(msg1[name])
            else:
              # no response received
              noResponseCount += 1
              if noResponseCount > 10:
                # missing 10 responses in a row
                self.logger.error('Heat pump did not respond for 10 seconds')
                self._portHandler.closePort()
                break
        except:
          self.logger.warning(sys.exc_info())

        return response

    def stop(self):
        """passes the stop request to the port handler"""
        self._portHandler.stop()

    def getStats(self):
        """returns the counter values"""
        val = {}
        val['comPortStatus'] = self._portHandler.isPortOpen()
        val['comPortReopenAttempts'] = self._portErrorCount
        val['rxCount'] = self._rxCount
        val['txCount'] = self._txCount
        val['rxChecksumErrorCount'] = self._rxChecksumErrorCount
        val['rxNackCount'] = self._rxNackCount
        val['rxTimeoutCount'] = self._rxTimeoutCount
        val['rxFramingErrorCount'] = self._portHandler.rxFramingErrorCount
        return val

    def logRegister(self, cmd):
        """logs the value of the specified register"""
        self._lock.acquire()
        try:
          msg = self._encodeGetMsg(cmd)
          self._portHandler.sendData(msg)
          data = self._portHandler.readData()
          if not data == None:
            data = bytearray(data)
            if data[0] == 0x01 and data[1] == 0x00:
              self.logger.info('Rx: ' + ' '.join(format(x, '02x') for x in data))
        except:
          self.logger.error('Get request failed - {:06x}\n{}'.format(cmd, sys.exc_info()))
        finally:
          self._lock.release()

    def logFullScan(self):
        """performs a full register scan and logs the results"""
        for i in range(0x0,0x100):
          self.logRegister(format(i, '02x'))
        for i in range(0x0a0000,0x0a0c00):
          self.logRegister(format(i, '06x'))
        for i in range(0x0b0000,0x0b0700):
          self.logRegister(format(i, '06x'))

