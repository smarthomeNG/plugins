#!/usr/bin/env python3
#
#########################################################################
# Copyright 2017 Henning Behrend
# Copyright 2020-2022 Ronny Schulz
#########################################################################
#
#  This file is part of SmartHomeNG.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
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

from datetime import datetime
import time
import threading
import logging
from lib.model.smartplugin import SmartPlugin

# pymodbus library from https://github.com/pymodbus-dev/pymodbus
from pymodbus.client.tcp import ModbusTcpClient

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder

class Pluggit(SmartPlugin):
    PLUGIN_VERSION="2.0.6"

    _itemReadDictionary = {}
    _itemWriteDictionary = {}
    
    DICT_READ_ADDRESS = 0
    DICT_WRITE_ADDRESS = 1
    DICT_ADDRESS_QUANTITY = 2
    DICT_VALUE_TYPE = 3
    DICT_ALLOWED_CONV_LIST = 4
    DICT_ROUND_VALUE = 5
    DICT_MIN_VALUE = 6
    DICT_MAX_VALUE = 7
    
    #============================================================================#
    # define variables for most important modbus registers of KWL "Pluggit AP310"
    #
    # Important: In the PDU Registers are addressed starting at zero.
    # Therefore registers numbered 1-16 are addressed as 0-15.
    # that means e.g. holding register "40169" is "40168" and so on
    #============================================================================#

    # 1: Bezeichnung des Registers (key)
    # 2: Lese-Adresse des Registers (0)
    # 3: Schreib-Adresse des Registers (1)
    # 4: Anzahl der zu lesenden/schreibenden Register (2)
    # 5: Typ des Wertes (3)
    # 6: erlaubte Umwandlungen des Types (4)
    # 7: Anzahl Kommastellen bei Rundungen oder -1 für keine (5)
    # 8: minimaler Wert oder -1 für nicht verwendet (6)
    # 9: maximaler Wert oder -1 für nicht verwendet (7)
    _modbusRegisterDictionary = {
        'prmSystemID': [2, -1, 2, 'uint', ['SID_FP1', 'SID_Week', 'SID_Bypass', 'SID_LRSwitch', 'SID_InternalPreheater', 'SID_ServoFlow', 'SID_RHSensor', 'SID_VOCSensor', 'SID_ExtOverride', 'SID_HAC1', 'SID_HRC2', 'SID_PCTool', 'SID_Apps', 'SID_ZeegBee', 'SID_DI1Override', 'SID_DI2Override'], -1, -1, -1],
        'prmSystemSerialNum': [4, -1, 4, 'uint', [], -1, -1, -1],
        'prmSystemName': [8, 8, 16, 'str', [], -1, -1, -1],
        'prmFWVersion': [24, -1, 1, 'version', [], -1, -1, -1],
        'prmDHCPEN': [26, -1, 1, 'bool', [], -1, 0, 1],
        'prmCurrentIPAddress': [28, -1, 2, 'ip', [], -1, -1, -1],
        'prmCurrentIPMask': [32, -1, 2, 'ip', [], -1, -1, -1],
        'prmCurrentIPGateway': [36, -1, 2, 'ip', [], -1, -1, -1],
        'prmMACAddr': [40, -1, 4, 'mac', [], -1, -1, -1],
        'prmHALLeft': [84, -1, 1, 'bool', [], -1, 0, 1],
        'prmHALRight': [86, -1, 1, 'bool', [], -1, 0, 1],
        'prmHALTaho1': [100, -1, 2, 'float', [], 0, 0, 5000],
        'prmHALTaho2': [102, -1, 2, 'float', [], 0, 0, 5000],
        'prmDateTime': [108, 110, 2, 'timestamp', ['ToDateTime', 'ToDate', 'ToTime'], -1, -1, -1],
        'prmDateTimeSet': [108, 110, 2, 'timestamp', ['ToDateTime', 'ToDate', 'ToTime'], -1, -1, -1],
        'prmRamIdxT1': [132, -1, 2, 'float', [], 2, -327.67, 327.67],
        'prmRamIdxT2': [134, -1, 2, 'float', [], 2, -327.67, 327.67],
        'prmRamIdxT3': [136, -1, 2, 'float', [], 2, -327.67, 327.67],
        'prmRamIdxT4': [138, -1, 2, 'float', [], 2, -327.67, 327.67],
        'prmRamIdxT5': [140, -1, 2, 'float', [], 2, -327.67, 327.67],
        'prmPreheaterDutyCycle': [160, -1, 1, 'uint', [], -1, 0, 100],
        'prmRamIdxUnitMode': [168, 168, 1, 'uint', ['UM_DemandMode', 'UM_ManualMode', 'UM_WeekProgramMode', 'UM_AwayMode', 'UM_FireplaceMode', 'UM_SummerMode', 'UM_NightMode', 'UM_ManualBypass'], -1, 0, 65535],
        'prmRamIdxHac1FirmwareVersion': [192, -1, 2, 'version_bcd', [], -1, -1, -1],
        'prmRamIdxRh3Corrected': [196, -1, 1, 'uint', [], -1, 0, 100],
        'prmRamIdxBypassActualState': [198, -1, 1, 'uint', ['ToBool', 'ToBool_inverted', 'ToString'], -1, 0, 255],
        'prmRamIdxHac1Components': [244, -1, 1, 'uint', ['ToString'], -1, 0, 255],
        'prmRamIdxBypassManualTimeout': [264, -1, 1, 'uint', [], -1, 60, 480],
        'prmRomIdxSpeedLevel': [324, 324, 1, 'uint', [], -1, 0, 4],
        'prmRomIdxNightModeStartHour': [332, 332, 1, 'uint', [], -1, 0, 23],
        'prmRomIdxNightModeStartMin': [334, 334, 1, 'uint', [], -1, 0, 59],
        'prmRomIdxNightModeEndHour': [336, 336, 1, 'uint', [], -1, 0, 23],
        'prmRomIdxNightModeEndMin': [338, 338, 1, 'uint', [], -1, 0, 59],
        'prmRomIdxRhSetPoint': [340, -1, 1, 'uint', [], -1, 35, 65],
        'prmRomIdxAfterHeaterT2SetPoint': [344, 344, 1, [], 'uint', -1, 0, 30],
        'prmRomIdxAfterHeaterT3SetPoint': [346, 346, 1, [], 'uint', -1, 0, 30],
        'prmRomIdxAfterHeaterT5SetPoint': [348, 348, 1, [], 'uint', -1, 0, 30],
        'prmVOC': [430, -1, 1, 'uint', [], -1, 0, 65536],
        'prmBypassTmin': [444, -1, 2, 'float', [], 1, 12.0, 15.0],
        'prmBypassTmax': [446, -1, 2, 'float', [], 1, 21.0, 27.0],
        'prmNumOfWeekProgram': [466, 467, 1, 'uint', [], -1, 0, 10],
        'prmCurrentBLState': [472, -1, 1, 'uint', ['ToString'], -1, -1, -1],
        'prmSetAlarmNum': [514, 514, 1, 'uint', [], -1, 0, 15],
        'prmLastActiveAlarm': [516, 516, 1, 'uint', ['ToString'], -1, -1, -1],
        'prmRefValEx': [518, -1, 1, 'uint', [], -1, 0, 65535],
        'prmRefValSupl': [520, -1, 1, 'uint', [], -1, 0, 65535],
        'prmFireplacePreset': [540, -1, 1, 'bool', [], -1, 0, 1],
        'prmFilterRemainingTime': [554, -1, 1, 'uint', [], -1, 0, 360],
        'prmFilterDefaultTime': [556, 556, 1, 'uint', [], -1, 0, 360],
        'prmFilterReset': [558, 558, 1, 'bool', [], -1, 0, 1],
        'prmPPM1Unit': [562, 562, 2, 'uint', [], -1, 0, 65535],
        'prmPPM2Unit': [564, 564, 2, 'uint', [], -1, 0, 65535],
        'prmPPM3Unit': [566, 566, 2, 'uint', [], -1, 0, 65535],
        'prmPPM1External': [568, 568, 1, 'uint', [], -1, 0, 65535],
        'prmPPM2External': [570, 570, 1, 'uint', [], -1, 0, 65535],
        'prmPPM3External': [572, 572, 1, 'uint', [], -1, 0, 65535],
        'prmHACCO2Val': [574, -1, 1, 'uint', [], -1, 0, 65535],
        'prmSystemIDComponents': [611, -1, 2, 'uint', [], -1, -1, -1],
        'prmWorkTime': [624, -1, 2, 'uint', [], -1, -1, -1],
        'PrmWeekMon': [626, 626, 6, 'weekprogram', [], -1, -1, -1],
        'PrmWeekTue': [632, 632, 6, 'weekprogram', [], -1, -1, -1],
        'PrmWeekWed': [638, 638, 6, 'weekprogram', [], -1, -1, -1],
        'PrmWeekThu': [644, 644, 6, 'weekprogram', [], -1, -1, -1],
        'PrmWeekFri': [650, 650, 6, 'weekprogram', [], -1, -1, -1],
        'PrmWeekSat': [656, 656, 6, 'weekprogram', [], -1, -1, -1],
        'PrmWeekSun': [662, 662, 6, 'weekprogram', [], -1, -1, -1],
        'prmStartExploitationDateStamp': [668, -1, 2, 'timestamp', ['ToDateTime', 'ToDate'], -1, -1, -1]
    }

    SID_DICT_VALUE_ENABLE = 0
    SID_DICT_TEXT = 1

    _SystemIDDict = {
        'SID_FP1': [0x0001, 'FP1'],
        'SID_Week': [0x0002, 'Week'],
        'SID_Bypass': [0x0004, 'Bypass'],
        'SID_LRSwitch': [0x0008, 'LRSwitch'],
        'SID_InternalPreheater': [0x0010, 'Internal preheater'],
        'SID_ServoFlow': [0x0020, 'Servo flow'],
        'SID_RHSensor': [0x0040, 'RH sensor'],
        'SID_VOCSensor': [0x0080, 'VOC sensor'],
        'SID_ExtOverride': [0x0100, 'Ext Override'],
        'SID_HAC1': [0x0200, 'HAC1'],
        'SID_HRC2': [0x0400, 'HRC2'],
        'SID_PCTool': [0x0800, 'PC Tool'],
        'SID_Apps': [0x1000, 'Apps'],
        'SID_ZeegBee': [0x2000, 'ZeegBee'],
        'SID_DI1Override': [0x4000, 'DI1 Override'],
        'SID_DI2Override': [0x8000, 'DI2 Override']
    }

    _CurrentBLStateDic = {
        0: 'Standby',
        1: 'Manual',
        2: 'Demand',
        3: 'Week program',
        4: 'Servo-flow',
        5: 'Away',
        6: 'Summer',
        7: 'DI Override',
        8: 'Hygrostat override',
        9: 'Fireplace',
        10: 'Installer',
        11: 'Fail Safe 1',
        12: 'Fail Safe 2',
        13: 'Fail Off',
        14: 'Defrost Off',
        15: 'Defrost',
        16: 'Night'
    }

    UM_DICT_VALUE_ENABLE = 0
    UM_DICT_VALUE_DISABLE = 1
    UM_DICT_TEXT = 2

    _RamIdxUnitModeDic = {
        'UM_DemandMode': [0x0002, -1, 'Demand Mode'],
        'UM_ManualMode': [0x0004, -1, 'Manual Mode'],
        'UM_WeekProgramMode': [0x0008, -1, 'Week Program Mode',],
        'UM_AwayMode': [0x0010, 0x8010, 'Away Mode',],
        'UM_NightMode': [0x0020, 0x8020, 'Night Mode'],
        'UM_FireplaceMode': [0x0040, 0x8040, 'Fireplace Mode',],
        'UM_ManualBypass': [0x0080, 0x8080, 'Manual Bypass'],
        'UM_SummerMode': [0x0800, 0x8800, 'Summer Mode']
    }

    _AlarmDic = {
        0: 'No Alarm',
        1: 'Exhaust FAN Alarm',
        2: 'Supply FAN Alarm',
        3: 'Bypass Alarm',
        4: 'T1 Alarm',
        5: 'T2 Alarm',
        6: 'T3 Alarm',
        7: 'T4 Alarm',
        8: 'T5 Alarm',
        9: 'RH Alarm',
        10: 'Outdoor13 Alarm',
        11: 'Supply5 Alarm',
        12: 'Fire Alarm',
        13: 'Communication Alarm',
        14: 'FireTermostat Alarm',
        15: 'High waterlevel Alarm'
    }

    _RamIdxBypassActualStateDic = {
        0: 'Closed',
        1: 'In process',
        32: 'Closing',
        64: 'Opening',
        255: 'Opened'
    }
    
    _RamIdxHac1ComponentsDic = {
        0x0001: 'CO2 Sensor',
        0x0004: 'PreHeater',
        0x0008: 'PreCooler',
        0x0010: 'AfterHeater',
        0x0020: 'AfterCooler',
        0x0040: 'Hygrostat'
    }

    # Initialize connection
    def __init__(self, sh, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self._host = self.get_parameter_value('host')
        self._port = int(self.get_parameter_value('port'))
        self._cycle = int(self.get_parameter_value('cycle'))
        self._lock = threading.Lock()
        self._is_connected = False
        self.connect()

    def connect(self):
        start_time = time.time()
        if self._is_connected:
            return True
        self._lock.acquire()
        try:
            self.logger.info("Pluggit: connecting to {0}:{1}".format(self._host, self._port))
            self._Pluggit = ModbusTcpClient(self._host, self._port)
        except Exception as e:
            self.logger.error("Pluggit: could not connect to {0}:{1}: {2}".format(self._host, self._port, e))
            return
        finally:
            self._lock.release()
        self.logger.info("Pluggit: connected to {0}:{1}".format(self._host, self._port))
        self._is_connected = True
        end_time = time.time()
        self.logger.debug("Pluggit: connection took {0} seconds".format(end_time - start_time))

    def disconnect(self):
        start_time = time.time()
        if self._is_connected:
            try:
                self._Pluggit.close()
            except:
                pass
        self._is_connected = False
        end_time = time.time()
        self.logger.debug("Pluggit: disconnect took {0} seconds".format(end_time - start_time))

    def run(self):
        self.scheduler_add(__name__, self._refresh, cycle=self._cycle)
        self.alive = True

    def stop(self):
        self.scheduler_remove(__name__)
        self.alive = False

    def parse_item(self, item):
        # check for smarthome.py attribute 'pluggit_read' in pluggit.conf
        if self.has_iattr(item.conf, 'pluggit_read'):
            self.logger.debug("Pluggit: parse read item: {0}".format(item))
            pluggit_key = self.get_iattr_value(item.conf, 'pluggit_read')
            if pluggit_key in self._modbusRegisterDictionary:
                self._itemReadDictionary[item] = pluggit_key
                self.logger.debug("Pluggit: Inhalt des dicts _itemReadDictionary nach Zuweisung zu item: '{0}'".format(self._itemReadDictionary))
            else:
                self.logger.warning("Pluggit: invalid key {0} configured".format(pluggit_key))
        # check for smarthome.py attribute 'pluggit_write' in pluggit.conf
        if self.has_iattr(item.conf, 'pluggit_write'):
            self.logger.debug("Pluggit: parse write item: {0}".format(item))
            pluggit_sendKey = self.get_iattr_value(item.conf, 'pluggit_write')
            if pluggit_sendKey in self._modbusRegisterDictionary:
                self._itemWriteDictionary[item] = pluggit_sendKey
                self.logger.debug("Pluggit: Inhalt des dicts _itemWriteDictionary nach Zuweisung zu write item: '{0}'".format(self._itemWriteDictionary))
                return self.update_item
            else:
                self.logger.warning("Pluggit: invalid key {0} configured".format(pluggit_key))
        else:
            return None

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'Pluggit':
            pluggit_sendkey = self._itemWriteDictionary[item]
            pluggit_paramList = self._modbusRegisterDictionary[pluggit_sendkey]
            value = item()
            writeItemValue = None

            if value is not None:
                if pluggit_paramList[self.DICT_WRITE_ADDRESS] != -1:
                    # check for conditions
                    # unit mode = manual?
                    self.logger.debug(f"Pluggit SendKey: {pluggit_sendkey}")
                    if pluggit_sendkey == 'prmRomIdxSpeedLevel':
                        self.SetUnitMode('UM_ManualMode', True)
                    # check for conversion
                    if self.has_iattr(item.conf, 'pluggit_convert'):
                        # with conversion
                        convType = self.get_iattr_value(item.conf, 'pluggit_convert')
                        if convType in pluggit_paramList[self.DICT_ALLOWED_CONV_LIST]:
                            value = self.ConvertValueFromItem(value, convType, pluggit_sendkey)
                        else:
                            self.logger.warning('Umwandlung von {} zu {} bei Item {} nicht zulässig.'.format(pluggit_paramList[self.DICT_VALUE_TYPE], convType, item))
                    if value is not None:
                        if pluggit_paramList[self.DICT_VALUE_TYPE] == 'uint' or pluggit_paramList[self.DICT_VALUE_TYPE] == 'bool' or pluggit_paramList[self.DICT_VALUE_TYPE] == 'timestamp':
                            writeItemValue = value & 0xFFFF, value >> 16 & 0xFFFF
                        if pluggit_paramList[self.DICT_VALUE_TYPE] == 'str':
                            writeItemValue = self.StringToBinWord(value, pluggit_paramList[self.DICT_ADDRESS_QUANTITY])
                        if writeItemValue is not None:
                            # write values to pluggit via modbus client registers
                            self.logger.debug('VALUE: {}'.format(writeItemValue))
                            self._Pluggit.write_registers(pluggit_paramList[self.DICT_WRITE_ADDRESS], writeItemValue)
                else:
                    self.logger.warning("Parameter {} bei Item {} kann nur gelesen werden.".format(pluggit_sendkey, item))

    def BinWordToString(self, binWord):
        result = ''
        for word in binWord:
            char = word & 0xFF
            if char == 0:
                break
            result += chr(char)
            char = word >> 8
            if char == 0:
                break
            result += chr(char)
        return result

    def StringToBinWord(self, bwString, wordCount):
        result = []
        vlen = len(bwString)
        for i in range (0, wordCount):
            binval1 = 0
            binval2 = 0
            if vlen > i*2:
                binval1 = ord(bwString[i*2])
            if vlen > i*2+1:
                binval2 = ord(bwString[i*2+1])
            result.append(binval1 | binval2 << 8)
        return result

    def SetUnitMode(self, modekey, enable):
        if 'prmRamIdxUnitMode' in self._modbusRegisterDictionary:
            if modekey in self._RamIdxUnitModeDic:
                unitmode = self._RamIdxUnitModeDic[modekey]
                if bool(enable):
                    unitstate = unitmode[self.UM_DICT_VALUE_ENABLE]
                else:
                    unitstate = unitmode[self.UM_DICT_VALUE_DISABLE]
                if unitstate != -1:
                    pluggit_paramList = self._modbusRegisterDictionary['prmRamIdxUnitMode']
                    registerValue = self._Pluggit.read_holding_registers(pluggit_paramList[self.DICT_READ_ADDRESS], pluggit_paramList[self.DICT_ADDRESS_QUANTITY])
                    vdecoder = BinaryPayloadDecoder.fromRegisters(registerValue.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE)
                    readItemValue = vdecoder.decode_16bit_uint()
                    #if readItemValue & unitstate != unitstate:
                        # workaround for manual bypass timeout
                        #if modekey == 'UM_ManualBypass' & bool(enable):
                            #self._Pluggit.write_registers(pluggit_paramList[self.DICT_WRITE_ADDRESS], unitmode[self.UM_DICT_VALUE_DISABLE])
                            #time.sleep(0.5)
                        # write value to registers
                    self.logger.debug('SetUnitMode(): Mode \"{}\".'.format(modekey))
                    self._Pluggit.write_registers(pluggit_paramList[self.DICT_WRITE_ADDRESS], unitstate)
                    time.sleep(0.5)
            else:
                self.logger.warning('SetUnitMode(): Illegal mode \"{}\".'.format(modekey))
        else:
            self.logger.warning('SetUnitMode(): Parameter \"prmRamIdxUnitMode\" for UnitMode not found in dictionary.')

    def ConvertValueFromItem(self, value, conversionType, pluggitKey):
        conversionValue = None

        pluggit_paramList = self._modbusRegisterDictionary[pluggitKey]

        if pluggit_paramList[self.DICT_VALUE_TYPE] == 'uint':
            if conversionType == 'ToBool':
                conversionValue = int(value)
            if conversionType == 'ToBool_inverted':
                conversionValue = int(not value)

            if pluggit_paramList [self.DICT_VALUE_TYPE] == 'timestamp':
                if conversionType == 'ToDateTime':
                    conversionValue = datetime(value).strftime("%s")
                # TODO: ToDate
                # TODO: ToTime

        # pluggit_key = prmRamIdxUnitMode
        if conversionType in self._RamIdxUnitModeDic:
            if bool(value):
                conversionValue = self._RamIdxUnitModeDic[conversionType][self.UM_DICT_VALUE_ENABLE]
            else:
                conversionValue = self._RamIdxUnitModeDic[conversionType][self.UM_DICT_VALUE_DISABLE]

        self.logger.debug("conVersion: {}".format(conversionValue))
        return conversionValue

    def ConvertValueToItem(self, value, conversionType, pluggitKey):
        conversionValue = None

        if conversionType == 'ToBool':
            conversionValue = bool(value)

        if conversionType == 'ToBool_inverted':
            conversionValue = not bool(value)

        if conversionType == 'ToDateTime':
            conversionValue = datetime.utcfromtimestamp(value)

        if conversionType == 'ToDate':
            conversionValue = datetime.utcfromtimestamp(value).date()

        if conversionType == 'ToTime':
            conversionValue = datetime.utcfromtimestamp(value).time()

        if conversionType == 'ToString':
            if pluggitKey == 'prmCurrentBLState':
                conversionValue = self._CurrentBLStateDic[value]
            if pluggitKey == 'prmLastActiveAlarm':
                conversionValue = self._AlarmDic[value]
            if pluggitKey == 'prmRamIdxBypassActualState':
                conversionValue = self._RamIdxBypassActualStateDic[value]

        # pluggit_key = prmSystemID
        if conversionType in self._SystemIDDict:
            conversionValue = bool(value & self._SystemIDDict[conversionType][self.SID_DICT_VALUE_ENABLE])

        # pluggit_key = prmRamIdxUnitMode
        if conversionType in self._RamIdxUnitModeDic:
            conversionValue = bool(value & self._RamIdxUnitModeDic[conversionType][self.UM_DICT_VALUE_ENABLE])

        return conversionValue

    def _refresh(self):
        readCacheDictionary = {}
        
        for item in self._itemReadDictionary:
            pluggit_key = self._itemReadDictionary[item]
            pluggit_paramList = self._modbusRegisterDictionary[pluggit_key]
            
            # read values from pluggit via modbus client registers, if not in cache
            if pluggit_paramList[self.DICT_READ_ADDRESS] != -1:
                if pluggit_key in readCacheDictionary:
                    registerValue = readCacheDictionary[pluggit_key] 
                else:
                    registerValue = self._Pluggit.read_holding_registers(pluggit_paramList[self.DICT_READ_ADDRESS], pluggit_paramList[self.DICT_ADDRESS_QUANTITY])
                    # TODO: auswerten, wenn Reigister nicht auslesbar
                    readCacheDictionary[pluggit_key] = registerValue
                vdecoder = BinaryPayloadDecoder.fromRegisters(registerValue.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE)

                readItemValue = None
                    
                if pluggit_paramList[self.DICT_VALUE_TYPE] == 'uint':
                    if pluggit_paramList[self.DICT_ADDRESS_QUANTITY] == 1 or pluggit_paramList[self.DICT_ADDRESS_QUANTITY] == 2:
                        readItemValue = vdecoder.decode_16bit_uint()
                    if pluggit_paramList[self.DICT_ADDRESS_QUANTITY] == 4:
                        readItemValue = vdecoder.decode_64bit_uint()

                if pluggit_paramList[self.DICT_VALUE_TYPE] == 'float':
                    if pluggit_paramList[self.DICT_ADDRESS_QUANTITY] == 2:
                        readItemValue = vdecoder.decode_32bit_float()
                        if pluggit_paramList[self.DICT_ROUND_VALUE] != -1:
                            readItemValue = round(readItemValue, pluggit_paramList[self.DICT_ROUND_VALUE])

                if pluggit_paramList[self.DICT_VALUE_TYPE] == 'bool':
                    if pluggit_paramList[self.DICT_ADDRESS_QUANTITY] == 1:
                        readItemValue = bool(vdecoder.decode_16bit_uint())

                if pluggit_paramList[self.DICT_VALUE_TYPE] == 'timestamp':
                    if pluggit_paramList[self.DICT_ADDRESS_QUANTITY] == 2:
                        readItemValue = vdecoder.decode_32bit_uint()

                if pluggit_paramList[self.DICT_VALUE_TYPE] == 'str':
                    readItemValue = self.BinWordToString(registerValue.registers)

                if pluggit_paramList[self.DICT_VALUE_TYPE] == 'ip':
                    readItemValue = '{}.{}.{}.{}'.format(registerValue.registers[1] >> 8, registerValue.registers[1] & 0xFF, registerValue.registers[0] >> 8, registerValue.registers[0] & 0xFF)

                if pluggit_paramList[self.DICT_VALUE_TYPE] == 'mac':
                    readItemValue = '{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}'.format(registerValue.registers[0] >> 8, registerValue.registers[0] & 0xFF, registerValue.registers[3] >> 8, registerValue.registers[3] & 0xFF, registerValue.registers[2] >> 8, registerValue.registers[2] & 0xFF)

                if pluggit_paramList[self.DICT_VALUE_TYPE] == 'version':
                    vresult = vdecoder.decode_16bit_uint()
                    readItemValue = '{}.{}'.format(vresult >> 8 & 0xFF, vresult & 0xFF)

                if pluggit_paramList[self.DICT_VALUE_TYPE] == 'version_bcd':
                    vresult = vdecoder.decode_16bit_uint()
                    readItemValue = '{}.{}{}'.format(vresult >> 12 & 0x0F, vresult >> 8 & 0x0F, vresult >> 4 & 0x0F, vresult & 0x0F)

                if pluggit_paramList[self.DICT_VALUE_TYPE] == 'weekprogram':
                    # 6 Register, 1 h = 4 Bit, 2 h = 8 bit, 4 h = 16 bit = 1 Register
                    #readItemValue = registerValue.registers
                    #readItemValue = str(registerValue.registers[0] & 0x0F)
                    #self.logger.info('{}'.format(readItemValue))
                    pass

                # check for conversion
                convItemValue = None
                if readItemValue is not None:
                    if self.has_iattr(item.conf, 'pluggit_convert'):
                        convType = self.get_iattr_value(item.conf, 'pluggit_convert')
                        if convType in pluggit_paramList[self.DICT_ALLOWED_CONV_LIST]:
                            convItemValue = self.ConvertValueToItem(readItemValue, convType, pluggit_key)
                            if convItemValue is not None:
                                item(convItemValue, 'Pluggit')
                            else:
                                self.logger.warning("Fehler bei der Umwandlung von Item {}.".format(item))
                        else:
                            self.logger.warn("Umwandlung von {} zu {} bei Item {} nicht zulässig.".format(pluggit_paramList[self.DICT_VALUE_TYPE], convType, item))
                    else:
                        if readItemValue is not None:
                            item(readItemValue, 'Pluggit')
                        else:
                            self.logger.warning("Unbekannter Wert-Typ: {} bei Item {}.".format(pluggit_paramList[self.DICT_VALUE_TYPE]), item)

            time.sleep(0.1)