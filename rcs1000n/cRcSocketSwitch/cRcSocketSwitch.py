#!/usr/bin/python3
# -*- coding: utf-8 -*-

from rpi_rf import RFDevice
import logging

def sanity_check_Systemcode(SystemCode_raw):
    '''
    check is SystemCode has the intented format of str (e.g: '10000')
    '''
    # check if SystemCode ist of type str
    if isinstance(SystemCode_raw, str):
        # check now the length of the SystemCode
        if len(SystemCode_raw) == 5:
            if set(SystemCode_raw) <= {'0','1'}:
                # check if SystemCode contains only '0' or '1'
                # SystemCode ok
                logging.info("SystemCode is ok: {} - {}\n".format(SystemCode_raw, type(SystemCode_raw)))
                return True
            else:
                logging.error("SystemCode is type of str BUT contains NOT only '0' or '1': {} - {}\n".format(SystemCode_raw, type(SystemCode_raw)))
                return False
        else:
            # SystemCode not ok
            logging.error("SystemCode length is NOT 5: {} - {}\n".format(SystemCode_raw, type(SystemCode_raw)))
            return False
    else:
        logging.error("SystemCode is not a type of str: {} - {}\n".format(SystemCode_raw, type(SystemCode_raw)))
        return False


def sanity_check_Buttoncode(ButtonCode_raw):
    '''
    check the intented format of ButtonCode
    The ButtonCode can have the following formats:
        - type str like 'a' or 'A'
        - type str like '10000'
        - type int like 1, 2, 4, ...etc
    '''
    # check if ButtonCode is of type str
    if ButtonCode_raw in RCS1000N._button_list:
        # ok fine ButtonCode is type of str like 'A', 'B, etc...
        logging.info("ButtonCode is ok: {} - {}\n".format(ButtonCode_raw, type(ButtonCode_raw)))
        return True
    elif isinstance(ButtonCode_raw, str):
        if len(ButtonCode_raw) == 5:
            # check if ButtonCode is like '10000'
            if set(ButtonCode_raw) <= {'0','1'}:
                # check if Buttoncode contains only '0' or '1'
                logging.info("ButtonCode is ok: {} - {}\n".format(ButtonCode_raw, type(ButtonCode_raw)))
                return True
            else:
                logging.error("ButtonCode is type of str BUT contains NOT only '0' or '1': {} - {}\n".format(ButtonCode_raw, type(ButtonCode_raw)))
                return False
        else:
            logging.error("ButtonCode is type of str BUT len i NOT 5: {} - {}\n".format(ButtonCode_raw, type(ButtonCode_raw)))
            return False
    elif isinstance(ButtonCode_raw, int) and ButtonCode_raw < 32:
        # ButtonCode is of type int and has valid value
        logging.info("ButtonCode is ok: {} - {}\n".format(ButtonCode_raw, type(ButtonCode_raw)))
        return True
    else:
        logging.error("ButtonCode is type of int BUT has wrong value: {} - {}\n".format(ButtonCode_raw, type(ButtonCode_raw)))
        return False


class RCS1000N:
    '''
    class for switching remote socket devices as:
    Brennenstuhl RCS 1000 N
    I calculated the corresponding send code in decimal value
    and uses the library rpi-rf to send the command via 433 MHz send device 
    '''
    sanity_check_Systemcode = staticmethod(sanity_check_Systemcode)
    sanity_check_Buttoncode = staticmethod(sanity_check_Buttoncode)

    _button_list = ['a', 'A', 'b', 'B', 'c', 'C', 'd', 'D', 'e', 'E']
    _button_mapping = {'A':16, 'B':8, 'C':4, 'D':2, 'E':1}


    def __init__(self, gpio_pin = 17):
        '''
        Constructor for GPIO Pin and Configuration
        '''
        self.gpio = gpio_pin
        self.config = {'code': None, 'tx_proto': 1, 'tx_pulselength': 320, 'tx_length': 24}
        logging.info("Brennenstuhl RCS1000 N object created with GPIO pin {}".format(self.gpio))


    def prepareCodes(self, SystemCode_raw, ButtonCode_raw, status):
        '''
        this method prepares the codes and checks the imput format in case
        of different usecases
        '''
        # check if the input for the ButtonCode is in the Case 'A', 'B', etc...
        if ButtonCode_raw in self._button_list:
            ButtonCode_raw = ButtonCode_raw.upper()
            ButtonCode = self._button_mapping[ButtonCode_raw]
            ButtonCode = '{:05b}'.format(ButtonCode)
            logging.info("Buttoncode: {}\n".format(ButtonCode))
        
        # check if the ButtonCode is an integer like 1, 2, 3, etc...
        elif isinstance(ButtonCode_raw, int):
            logging.info("ButtonCode_raw is of type int")
            ButtonCode = '{:05b}'.format(ButtonCode_raw)
            logging.info("Buttoncode: {}\n".format(ButtonCode))
        
        # assume the code is in the way '01000' check the length (5)
        elif isinstance(ButtonCode_raw, str):
            logging.info("ButtonCode_raw is of type str")
            # check length of 5 
            if len(ButtonCode_raw) == 5:
                ButtonCode = ButtonCode_raw
                logging.info("Buttoncode: {} - {}\n".format(ButtonCode, type(ButtonCode)))
            else:
                ButtonCode = None
                logging.error("ERROR: wrong len of ButtonCode_raw!")
        
        # check now the lenght of the SystemCode
        if len(SystemCode_raw) == 5:
            SystemCode = SystemCode_raw
            logging.info("SystemCode: {} - {}\n".format(SystemCode, type(SystemCode)))
        else:
            SystemCode = None
            logging.error("ERROR: wrong len of SystemCode_raw!")
        
        # check the status
        if isinstance(status, bool):
            if status:
                status = 1
            else:
                status = 0
        return (SystemCode, ButtonCode, status)


    def calcTristateCode(self, SystemCode, ButtonCode, status):
        '''
        calculate the corresponding Tristate Code in the same way as the library
        wiringPi does it in c-code
        return value is the TriState String Code
        '''
        code = ""
        for c in SystemCode:
            if c == '0':
                code += 'F'
            else:
                code += '0'
        
        for c in ButtonCode:
            if c == '0':
                code += 'F'
            else:
                code += '0'
        
        if status:
            code += '0F'
        else:
            code += 'F0'
        return code


    def calcBinaryCode(self, strCode):
        '''
        calculate the Binary Code of the switch command in the same way as th library
        wiringPi does it in c-code
        return value is then a decimal value of the switch command
        '''
        code = 0
        len = 0
        for c in strCode:
            code <<= 2
            #print(c, type(c))
            #print(bin(code))
            if c == '0':
                # bit pattern 00
                pass
            elif c == 'F':
                # bit pattern 01 
                code += 1
            elif c =='1':
                # bit pattern 11
                code += 3
            len += 2
        logging.info("Length of code: {}\n".format(len))
        logging.info("code: {}\n".format(int(code)))
        return code


    def calc_DecimalCode_python_style(self, SystemCode, ButtonCode, status):
        '''
        calculate the decimal Code in a python style
        this combines the methods:
        calcTristateCode + calcBinaryCode in on step
        '''
        code = str(SystemCode + ButtonCode)
        help = code.replace('0', 'F').replace('1', '0')
        if status:
            help += '0F'
        else:
            help += 'F0'
        logging.info("Py - TriState code: {}\n".format(help))
        code = help.replace('0','00').replace('F', '01')
        binstr = '0b' + code
        logging.info("binary string: {}\n".format(binstr))
        return int(binstr, 2)


    def send(self, systemCode, btn_code, status):
        '''
        Method to prepare the codes and send it to the actuator
        '''
        try:
            rfdevice = RFDevice(self.gpio)
            rfdevice.enable_tx()
            rfdevice.tx_repeat = 10
            values = self.prepareCodes(systemCode, btn_code, status)
            send_code = self.calc_DecimalCode_python_style(*values)
            self.config['code'] = send_code
            rfdevice.tx_code(**self.config)

        finally:
            rfdevice.cleanup()