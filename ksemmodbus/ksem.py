import binascii
import hashlib
import hmac
import locale
import time
import logging
import pymodbus

from lib.model.smartplugin import *

# pymodbus library from https://github.com/riptideio/pymodbus
from pymodbus.version import version
pymodbus_baseversion = int(version.short().split('.')[0])

if pymodbus_baseversion > 2:
    # for newer versions of pymodbus
    from pymodbus.client.tcp import ModbusTcpClient
else:
    # for older versions of pymodbus
    from pymodbus.client.sync import ModbusTcpClient

from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian

class Ksem:
    def __init__(self, ip, port):
        self.__init_registers()
        self.client = ModbusTcpClient(ip, port=port)
        
    def __init_registers(self):
        self.registers = []
        for i in range(0, len(self.decRow)):
            reg = Register(self.decRow[i],self.__descriptionRow[i],self.__typeRow[i],self.__unitRow[i])
            self.registers.append(reg)

    def get_data(self):
        try:
            self.client.connect()
            for i in self.registers:
                    if i.type == "Float":
                        i.value = self.__read_float(i.adrDec)
                    elif i.type == "U16":
                        i.value = self.__read_u16(i.adrDec)
                    elif i.type == "U16_2":
                        i.value = self.__read_u16_2(i.adrDec)
                    elif i.type == "U32":
                        i.value = self.__read_u32(i.adrDec)
                    elif i.type == "U64":
                        i.value = self.__read_u64(i.adrDec)
                    elif i.type == "S16":
                        i.value = self.__read_s16(i.adrDec)
        except Exception as exc:
            print("Error getting Data from Kostal Smart Energy Meter :", exc)

        self.client.close()
        return self.registers

    def __read_float(self, adr_dec):
        if pymodbus_baseversion > 2:
            result = self.client.read_holding_registers(adr_dec, 2, slave=71)
        else:
            result = self.client.read_holding_registers(adr_dec, 2, unit=71)
        float_value = BinaryPayloadDecoder.fromRegisters(result.registers,byteorder=Endian.Big,wordorder=Endian.Little)
        return round(float_value.decode_32bit_float(), 2)

    def __read_u16(self, adr_dec):
        if pymodbus_baseversion > 2:
            result = self.client.read_holding_registers(adr_dec, 1, slave=71)
        else:
            result = self.client.read_holding_registers(adr_dec, 1, unit=71)
        u16_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.Big,wordorder=Endian.Little)
        return u16_value.decode_16bit_uint()

    def __read_u16_2(self, adr_dec):
        if pymodbus_baseversion > 2:
            result = self.client.read_holding_registers(adr_dec, 2, slave=71)
        else:
            result = self.client.read_holding_registers(adr_dec, 2, unit=71)
        u16_2_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.Big,wordorder=Endian.Little)
        return u16_2_value.decode_16bit_uint()

    def __read_s16(self, adr_dec):
        if pymodbus_baseversion > 2:
            result = self.client.read_holding_registers(adr_dec, 1, slave=71)
        else:
            result = self.client.read_holding_registers(adr_dec, 1, unit=71)
        s16_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.Big,wordorder=Endian.Little)
        return s16_value.decode_16bit_uint()

    def __read_u32(self, adr_dec):
        if pymodbus_baseversion > 2:
            result = self.client.read_holding_registers(adr_dec, 2, slave=71)
        else:
            result = self.client.read_holding_registers(adr_dec, 2, unit=71)
        u32_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.Big, wordorder=Endian.Big)
        return round((u32_value.decode_32bit_uint() * 0.1), 2)

    def __read_u64(self, adr_dec):
        if pymodbus_baseversion > 2:
            result = self.client.read_holding_registers(adr_dec, 4, slave=71)
        else:
            result = self.client.read_holding_registers(adr_dec, 4, unit=71)
        u64_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.Big, wordorder=Endian.Big)
        return round((u64_value.decode_64bit_uint() * 0.0001),2)


    decRow = [0, 2, 4, 6, 16, 18, 24, 512, 516, 520, 524, 544, 548]

    __descriptionRow = ['Active Power +', 'Active Power -', 'Reactive Power +', 'Reactive Power -', 'Apparent power +', 'Apparent power -', 'Power Factor', 'Active energy+', 'Active energy-', 'Reactive energy+', 'Reactive energy-', 'Apparent energy+', 'Apparent energy-']

    __unitRow = ['W', 'W', 'var', 'var', 'VA', 'VA', '', 'Wh', 'Wh' ,'varh', 'varh', 'VAh', 'VAh']

    __typeRow = ['U32', 'U32', 'U32', 'U32', 'U32', 'U32', 'Float', 'U64', 'U64', 'U64', 'U64', 'U64', 'U64']


class Register:
    def __init__(self, adr_dec,description,val_type,unit):
        self.adrDec = adr_dec
        self.description = description
        self.type = val_type
        self.unit = unit
        self.value = ''
