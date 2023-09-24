import binascii
import hashlib
import hmac
import locale
import time
import logging
import pymodbus

from lib.model.smartplugin import *

from pymodbus.client.tcp import ModbusTcpClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian

class Inverter:
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
                    elif i.type == "S16":
                        i.value = self.__read_s16(i.adrDec)
                    elif i.type == "STR08":
                        i.value = self.__read_str08(i.adrDec)
                    elif i.type == "STR16":
                        i.value = self.__read_str16(i.adrDec)
                    elif i.type == "STR32":
                        i.value = self.__read_str32(i.adrDec)
        except Exception as exc:
            print("Error getting Data from Kostal Inverter :", exc)

        self.client.close()
        return self.registers

    def __read_float(self, adr_dec):
        result = self.client.read_holding_registers(adr_dec, 2, slave=71)
        float_value = BinaryPayloadDecoder.fromRegisters(result.registers,byteorder=Endian.BIG,wordorder=Endian.LITTLE)
        return round(float_value.decode_32bit_float(), 2)

    def __read_u16(self, adr_dec):
        result = self.client.read_holding_registers(adr_dec, 1, slave=71)

        u16_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG,wordorder=Endian.LITTLE)
        return u16_value.decode_16bit_uint()

    def __read_u16_2(self, adr_dec):
        result = self.client.read_holding_registers(adr_dec, 2, slave=71)
        u16_2_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG,wordorder=Endian.LITTLE)
        return u16_2_value.decode_16bit_uint()

    def __read_u32(self, adr_dec):
        result = self.client.read_holding_registers(adr_dec, 2, slave=71)
        u32_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG,wordorder=Endian.LITTLE)
        return u32_value.decode_32bit_uint()

    def __read_s16(self, adr_dec):
        result = self.client.read_holding_registers(adr_dec, 1, slave=71)
        s16_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG,wordorder=Endian.LITTLE)
        return s16_value.decode_16bit_uint()
        
    def __read_str08(self, adr_dec):
        result = self.client.read_holding_registers(adr_dec, 8, slave=71)
        str08_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG,wordorder=Endian.LITTLE)
        return str08_value.decode_string(size=16).rstrip(b'\0').decode('utf-8')
        
    def __read_str16(self, adr_dec):
        result = self.client.read_holding_registers(adr_dec, 16, slave=71)
        str08_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG,wordorder=Endian.LITTLE)
        return str08_value.decode_string(size=24).rstrip(b'\0').decode('utf-8')
        
    def __read_str32(self, adr_dec):
        result = self.client.read_holding_registers(adr_dec, 32, slave=71)
        str08_value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG,wordorder=Endian.LITTLE)
        return str08_value.decode_string(size=32).rstrip(b'\0').decode('utf-8')

    decRow = [30,32,34,36,54,56,100,104,106,108,110,112,114,116,118,120,122,124,144,150,152,154,156,
                       158,160,162,164,166,168,170,172,174,178,190,194,200,202,208,210,214,216,218,220,222,224,226,228,
                       230,232,234,236,238,240,242,244,246,248,250,252,254,256,258,260,266,268,270,276,278,280,286,320,
                       322,324,326,512,514,515,525,529,531,575,
                       577,582,586,588,1056,1058,1060,1062,1064,1066,98,
                       384,6,14,38,46,420,428,436,446,454,517,535,559,768,800]

    __descriptionRow = ['Number of bidirectional converter',
                'Number of AC phases', 'Number of PV strings','Hardware-Version','Power-ID','Inverter state2','Total DC power W','State of energy manager3',
                'Home own consumption from battery','Home own consumption from grid','Total home consumption Battery',
                'Total home consumption Grid','Total home consumption PV','Home own consumption from PV',
                'Total home consumption','Isolation resistance','Power limit from EVU','Total home consumption rate',
                'Worktime s Float','Actual cos','Grid frequency','Current Phase 1','Active power Phase 1','Voltage Phase 1',
                'Current Phase 2','Active power Phase 2','Voltage Phase 2','Current Phase 3','Active power Phase 3',
                'Voltage Phase 3','Total AC active power','Total AC reactive power','Total AC apparent power',
                'Battery charge current','Number of battery cycles','Actual battery charge (-) / discharge (+) current',
                'PSSB fuse state5','Battery ready flag','Act. state of charge','Battery temperature','Battery voltage',
                'Cos φ (powermeter)','Frequency (powermeter)','Current phase 1 (powermeter)',
                'Active power phase 1 (powermeter)','Reactive power phase 1 (powermeter)',
                'Apparent power phase 1 (powermeter)','Voltage phase 1 (powermeter)','Current phase 2 (powermeter)',
                'Active power phase 2 (powermeter)','Reactive power phase 2 (powermeter)',
                'Apparent power phase 2 (powermeter)','Voltage phase 2 (powermeter)','Current phase 3 (powermeter)',
                'Active power phase 3 (powermeter)','Reactive power phase 3 (powermeter)',
                'Apparent power phase 3 (powermeter)','Voltage phase 3 (powermeter)','Total active power (powermeter)',
                'Total reactive power  (powermeter)','Total apparent power (powermeter)','Current DC1','Power DC1',
                'Voltage DC1','Current DC2','Power DC2','Voltage DC2','Current DC3','Power DC3','Voltage DC3',
                'Total yield','Daily yield','Yearly yield','Monthly yield','Battery gross capacity','Battery actual SOC',
                'Firmware Maincontroller (MC)','Battery Model ID','Work Capacity','Inverter Max Power',
                'Inverter Generation Power (actual)','Generation Energy','Actual battery charge/discharge power',
                'Battery Firmware','Battery Type6','Total DC PV energy (sum of all PV inputs)','Total DC energy from PV1',
                'Total DC energy from PV2','Total DC energy from PV3','Total energy AC-side to grid','Total DC power (sum of all PV inputs)','Temperature of controller PCB',
                'Inverter Network Name','Inverter article number','Inverter serial number','Software-Version Maincontroller (MC)','Software-Version IO-Controller (IOC)','IP-address','IP-subnetmask','IP-gateway','IP-DNS1','IP-DNS2','Battery Manufacturer','Inverter Manufacturer','Inverter Serial Number','Productname','Power class']

    __unitRow = ['-','-','-','-','-','-','W','-','W','W','Wh','Wh','Wh','W','Wh','Ohm','%','%','Seconds',
                'cos','Hz','A','W','V','A','W','V','A','W','V','W','Var','VA','A','-','A','-','-','%','°C','V','cos',
                'Hz','A','W','Var','VA','V','A','W','Var','VA','V','A','W','Var','VA','V','W','Var','VA','A','W','V',
                'A','W','V','A','W','V','Wh','Wh','Wh','Wh','Ah','%','-','-','Wh','W','W','Wh','W','-','-','Wh','Wh','Wh','Wh','Wh','W','°C',
                '-','-','-','-','-','-','-','-','-','-','-','-','-','-','-']

    __typeRow = ['U16','U16','U16','U16_2','U16_2','U16_2','Float','U32','Float','Float',
               'Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float',
               'Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float',
               'Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float',
               'Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float',
               'Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','Float','U32',
               'U16','U32','U32','U32','U16','S16','U32','S16','U32','U16','Float','Float','Float','Float','Float','Float','Float',
               'STR32','STR08','STR08','STR08','STR08','STR08','STR08','STR08','STR08','STR08','STR08','STR16','STR16','STR32','STR32']


class Register:
    def __init__(self, adr_dec,description,val_type,unit):
        self.adrDec = adr_dec
        self.description = description
        self.type = val_type
        self.unit = unit
        self.value = ''
