#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#
# Copyright 2014 KNX-User-Forum e.V. http://knx-user-forum.de/
#
# This file is part of SmartHomeNG. https://github.com/smarthomeNG//
#
# SmartHomeNG is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SmartHomeNG is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
# encoding=utf8

import logging
import threading
import os.path
import time
import string
import re
from lib.model.smartplugin import SmartPlugin
from bin.smarthome import VERSION

try:
    import serial
    REQUIRED_PACKAGE_IMPORTED = True
except Exception:
    REQUIRED_PACKAGE_IMPORTED = False

class DuW(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.5.1"

    def __init__(self, smarthome):
        self._name = self.get_fullname()
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)
        if not REQUIRED_PACKAGE_IMPORTED:
            self.logger.error("{}: Unable to import Python package 'serial'".format(self._name))
            self._init_complete = False
            return
        try:
            self._LU_ID = self.get_parameter_value('LU_ID')
            self._WP_ID = self.get_parameter_value('WP_ID')
            self._tty = self.get_parameter_value('tty')
            self._cmd = False
            self.LUregl = {}
            self.WPregl = {}
            self.LUcmdl = {}
            self.WPcmdl = {}
            self.devl = {}
            self._is_connected = False
            self._device = self.get_parameter_value('device')
            self._retrylimit = self.get_parameter_value('retrylimit')
            self._lock = threading.Lock()
            self.busmonitor = self.get_parameter_value('busmonitor')
            self._pollservice = False

            self.devl[1] = {'device': 'aerosilent primus', 'cmdpath':
                            smarthome.base_dir + '/plugins/drexelundweiss/aerosilent_primus.txt'}
            self.devl[2] = {'device': 'aerosilent topo', 'cmdpath':
                            smarthome.base_dir + '/plugins/drexelundweiss/aerosilent_topo.txt'}
            self.devl[3] = {'device': 'aerosilent micro', 'cmdpath':
                            smarthome.base_dir + '/plugins/drexelundweiss/aerosilent_micro.txt'}
            self.devl[4] = {'device': 'aerosmart s', 'cmdpath':
                            smarthome.base_dir + '/plugins/drexelundweiss/aerosmart_s.txt'}
            self.devl[5] = {'device': 'aerosmart m', 'cmdpath':
                            smarthome.base_dir + '/plugins/drexelundweiss/aerosmart_m.txt'}
            self.devl[6] = {'device': 'aerosmart l', 'cmdpath':
                            smarthome.base_dir + '/plugins/drexelundweiss/aerosmart_l.txt'}
            self.devl[7] = {'device': 'aerosmart xls', 'cmdpath':
                            smarthome.base_dir + '/plugins/drexelundweiss/aerosmart_xls.txt'}
            self.devl[8] = {'device': 'aerosilent centro', 'cmdpath':
                            smarthome.base_dir + '/plugins/drexelundweiss/aerosilent_centro.txt'}
            self.devl[9] = {'device': 'termosmart sc', 'cmdpath':
                            smarthome.base_dir + '/plugins/drexelundweiss/termosmart_sc.txt'}
            self.devl[10] = {'device': 'x2', 'cmdpath':
                             smarthome.base_dir + '/plugins/drexelundweiss/x2.txt'}
            self.devl[11] = {'device': 'aerosmart mono', 'cmdpath':
                             smarthome.base_dir + '/plugins/drexelundweiss/aerosmart_mono.txt'}
            self.devl[13] = {'device': 'aerosilent bianco', 'cmdpath':
                             smarthome.base_dir + '/plugins/drexelundweiss/aerosilent_bianco.txt'}
            self.devl[14] = {'device': 'x2 plus', 'cmdpath':
                             smarthome.base_dir + '/plugins/drexelundweiss/x2_plus.txt'}
            self.devl[15] = {'device': 'aerosilent business', 'cmdpath':
                             smarthome.base_dir + '/plugins/drexelundweiss/aerosilent_business.txt'}
            self.devl[17] = {'device': 'aerosilent stratos', 'cmdpath':
                             smarthome.base_dir + '/plugins/drexelundweiss/aerosilent_stratos.txt'}
        except Exception as err:
            self.logger.error("{}: Error on init {}.".format(self._name, err))
            self._init_complete = False
            return
        try:
            self._port = serial.Serial(self._tty, 115200, timeout=5)
        except:
            self.logger.error("{}: could not open {}.".format(self._name, self._tty))
            return
        else:
            self._is_connected = True

        self._get_device_type()
        if self._cmd:
            self._load_cmd()

    def _convertresponse(self,antwort,teil):
        antwort = antwort.decode()
        #self.logger.debug("{}: Antwort: {}".format(antwort))
        allow = string.digits + ' '
        antwort = re.sub('[^%s]' % allow, '', antwort)
        liste = antwort.splitlines()
        try:
            antwort = liste[0].split()
        except:
            antwort = str("-1")
        if type(antwort) is list and len(antwort) >= 2:
            if teil == 'id':
                antwort = str(antwort[0])
            elif teil == 'register':
                try:
                    antwort = str(antwort[1])
                except:
                    antwort = '-1'
            elif teil == 'data':
                try:
                    antwort = str(antwort[2])
                except:
                    antwort = '-1'
        else:
            antwort = str(antwort)
        allow = string.digits
        antwort = re.sub('[^%s]' % allow, '', antwort)
        return int(antwort)

    def _get_device_type(self):
        self.alive = True
        if self._is_connected:
            (data, done) = self._read_register('LU\n', 5000, 1, 0)
            if done:
                if data in self.devl:
                    self.logger.info("{}: device: {}".format(self._name, self.devl[data]['device']))
                    if os.path.isfile(self.devl[data]['cmdpath']):
                        self._cmd = self.devl[data]['cmdpath']
                        self.logger.debug("{}: Command File:{}".format(self._name, self._cmd))
                    else:
                        self.logger.error(
                            "{}: no command file found at {}".format(self._name, self.devl[data]['cmdpath']))
                        self._cmd = False

                else:
                    self.logger.error("{}: device not supported: {}".format(self._name, data))
                    self._cmd = False
            else:
                self.logger.error("{}: Error reading device type! Trying to activate configured device".format(self._name))
                if os.path.isfile(self.devl[self._device]['cmdpath']):
                        self._cmd = self.devl[self._device]['cmdpath']
                        self.logger.info("{}: device: {}".format(self._name, self.devl[self._device]['device']))
                #self._cmd = False
        else:
            self._cmd = False
            self.logger.error("{}: no connection".format(self._name))
        self.alive = False

    def _send_DW(self, data, pcb):
        if not self._is_connected:
            return False

        if (pcb == 'LU\n'):
            device_ID = self._LU_ID
        elif(pcb == 'WP\n'):
            device_ID = self._WP_ID
        else:
            self.logger.error("{}: wrong pcb description".format(self._name))
            return

        if not self._lock.acquire(timeout=2):
            return
        try:
            self._port.write("{0} {1}\r\n".format(device_ID,data).encode())
        except Exception as e:
            self.logger.error("{}: Problem sending {}".format(self._name, e))
        finally:
            self._lock.release()

    def _get_register_info(self, register, pcb):

        if (pcb == 'LU\n'):
            if register in self.LUcmdl:
                return self.LUcmdl[register]['reginfo']
            else:
                return False
        elif(pcb == 'WP\n'):
            if register in self.WPcmdl:
                return self.WPcmdl[register]['reginfo']
            else:
                return False
        else:
            self.logger.error("{}: wrong pcb description".format(self._name))
            return

    def _load_cmd(self):
        self.logger.debug("{}: Opening command file".format(self._name))
        f = open(self._cmd, "r")
        self.logger.debug("{}: Opened command file".format(self._name))
        try:
            for line in f:
                if not self._lock.acquire(timeout=2):
                    return
                try:
                    row = line.split(";")
                    # skip first row
                    if (row[1] == "<Description>"):
                        pass
                    else:
                        if row[7] == 'LU\n':
                            self.LUcmdl[int(row[0])] = {'reginfo': row}
                        elif row[7] == 'WP\n':
                            self.WPcmdl[int(row[0])] = {'reginfo': row}
                        else:
                            self.logger.debug("{}: Error in Commandfile: {}".format(self._name, line))
                except Exception as e:
                    self.logger.error("{}: problems loading commands: {}".format(self._name, e))
                finally:
                    self._lock.release()
        finally:
            f.close()

    def run(self):
        self.logger.debug("{}: run method called".format(self._name))
        if not self._cmd:
            self.alive = False
            try:
                if self._is_connected:
                    self._port.close()
            except Exception as e:
                self.logger.error("{}: Error {}".format(self._name, e))
            return

        self.alive = True

        # LU registers init
        for register in self.LUregl:
            reginfo = self.LUregl[register]['reginfo']
            divisor = int(reginfo[4])
            komma = int(reginfo[5])
            for item in self.LUregl[register]['items']:
                (data, done) = self._read_register(
                    reginfo[7], register, int(reginfo[4]), int(reginfo[5]))
                if done:
                    item(data, 'DuW', 'init process')
                else:
                    self.logger.debug("{}: Init LU register failed: {}".format(self._name, register))

        # WP register init
        for register in self.WPregl:
            reginfo = self.WPregl[register]['reginfo']
            divisor = int(reginfo[4])
            komma = int(reginfo[5])
            for item in self.WPregl[register]['items']:
                (data, done) = self._read_register(
                    reginfo[7], register, int(reginfo[4]), int(reginfo[5]))
                if done:
                    item(data, 'DuW', 'init process')
                else:
                    self.logger.debug("{}: Init WP register failed: {}".format(self._name, register))

        # poll DuW interface
        dw_id = 0
        dw_register = 0
        dw_data = 0
        response = bytes()
        self._pollservice = True
        self._port.flushInput()
        try:
            while self.alive:
                if self._port.inWaiting():
                    if not self._lock.acquire(timeout=2):
                        return
                    try:
                        response += self._port.read()
                        if (len(response) != 0):
                            if (response[-1] == 0x20 and dw_id == 0):
                                dw_id = self._convertresponse(response,'id')
                                response = bytes()

                            elif (response[-1] == 0x20 and dw_id != 0 and dw_register == 0):
                                dw_register = self._convertresponse(response,'register')
                                response = bytes()

                            elif (response[-1] == 0x0a):
                                dw_data = self._convertresponse(response,'data')

                                if (self.busmonitor):
                                    if dw_id == self._LU_ID:
                                        if dw_register in self.LUcmdl:
                                            reginfo = self.LUcmdl[
                                                dw_register]['reginfo']
                                            divisor = int(reginfo[4])
                                            komma = int(reginfo[5])
                                            self.logger.debug("DuW Busmonitor LU register: {} {}: {}".format(
                                                self._name, dw_register,reginfo[1],((dw_data / divisor) / (10 ** komma))))
                                        else:
                                            self.logger.debug("{} Busmonitor: unknown LU register: {} {}".format(
                                                self._name, dw_register,dw_data))
                                    elif dw_id == self._WP_ID:
                                        if dw_register in self.WPcmdl:
                                            reginfo = self.WPcmdl[dw_register][
                                                'reginfo']
                                            divisor = int(reginfo[4])
                                            komma = int(reginfo[5])
                                            self.logger.debug("DuW Busmonitor WP register: {} {}: {}".format(
                                                self._name, dw_register,reginfo[1],((dw_data / divisor) / (10 ** komma))))
                                        else:
                                            self.logger.debug("{} Busmonitor: unknown WP register: {} {}".format(
                                                self._name, dw_register,dw_data))
                                    else:
                                        self.logger.debug(
                                            "{} Busmonitor: unknown device ID: {}".format(self._name, dw_id))

                                if dw_id == self._LU_ID:
                                    if dw_register in self.LUregl:
                                        reginfo = self.LUregl[
                                            dw_register]['reginfo']
                                        divisor = int(reginfo[4])
                                        komma = int(reginfo[5])
                                        for item in self.LUregl[dw_register]['items']:
                                            item(
                                                ((dw_data / divisor)
                                                 / (10 ** komma)),
                                                'DuW', 'Poll')
                                    else:
                                        self.logger.debug("{}: Ignore LU register {}".format(self._name, dw_register))
                                elif dw_id == self._WP_ID:
                                    if dw_register in self.WPregl:
                                        reginfo = self.WPregl[
                                            dw_register]['reginfo']
                                        divisor = int(reginfo[4])
                                        komma = int(reginfo[5])
                                        for item in self.WPregl[dw_register]['items']:
                                            item(
                                                ((dw_data / divisor)
                                                 / (10 ** komma)),
                                                'DuW', 'Poll')
                                    else:
                                        self.logger.debug("{}: Ignore WP register {}" .format(self._name, dw_register))
                                else:
                                    self.logger.debug("{}: unknown device ID: {}".format(self._name, dw_id))

                                dw_id = 0
                                dw_register = 0
                                dw_data = 0
                                response = bytes()
                        else:
                            response = bytes()
                            dw_id = 0
                            dw_register = 0
                            dw_data = 0
                            self.logger.debug("{}: Read timeout".format(self._name))
                    except Exception as e:
                        self.logger.error("{}: Polling error {}".format(self._name, e))
                    finally:
                        self._lock.release()
                time.sleep(0.1)
            # exit poll service
            self._pollservice = False
        except Exception as e:
            self.logger.error("{}: not alive error, {}".format(self._name, e))

    def stop(self):
        self.alive = False
        self.logger.debug("{}: stop method called".format(self._name))
        while self._pollservice == True:
            pass

        try:
            if self._is_connected:
                self._port.close()
        except Exception as e:
            self.logger.error("{}: Stop Exception, {}".format(self._name, e))

    def write_DW(self, pcb, register, value):
        self._send_DW("{0:d} {1:d}".format(int(register), int(value)), pcb)

    def req_DW(self, pcb, register):
        self._send_DW("{0:d}".format(int(register)), pcb)

    def _read_register(self, pcb, register, divisor, komma):
        if (pcb == 'LU\n'):
            device_ID = self._LU_ID
        elif(pcb == 'WP\n'):
            device_ID = self._WP_ID
        else:
            self.logger.error("{}: wrong pcb description".format(self._name))

        self._port.flushInput()
        self.req_DW(pcb, str(register + 1))
        response = bytes()
        dw_id = 0
        dw_register = 0
        dw_data = 0
        retries = 0
        if not self._lock.acquire(timeout=2):
            return
        try:
            while self.alive:
                response += self._port.read()
                allow = string.digits
                test = re.sub('[^%s]' % allow, '', str(response.decode()))
                if len(test) != 0:
                    if (response[-1] == 0x20 and dw_id == 0):
                        dw_id = self._convertresponse(response,'id')
                        response = bytes()

                    elif response[-1] == 0x20 and dw_id != 0 and dw_register == 0:
                        dw_register = self._convertresponse(response,'register')
                        response = bytes()

                    elif response[-1] == 0x0a:
                        dw_data = self._convertresponse(response,'data')
                        break
                        response = bytes()
                else:
                    retries += 1
                    self.logger.info("{}: read timeout: {}. Retries: {}".format(self._name, response, retries))
                    if retries >= self._retrylimit:
                       break
                time.sleep(0.1)
        except Exception as e:
            self.logger.warning("{}: Read error: {}".format(self._name, e))
        finally:
            self._lock.release()

        if(dw_id == device_ID and (dw_register - 1) == register):
            self.logger.debug("{}:  Read {} on Register: {}".format(self._name, dw_data, register))
            try:
                return (((dw_data / divisor) / (10 ** komma)), 1)
            except:
                self.logger.debug("Division durch Null Problem")
                return (((dw_data / 1) / (10 ** 1)), 1)
        else:
            self.logger.error("{}: read errror Device ID: {}, register {}".format(self._name, dw_id, dw_register - 1))
            return (0, 0)

    def parse_item(self, item):
        if not self._cmd:
            return None
        if self.has_iattr(item.conf, 'DuW_LU_register'):
            register = int(self.get_iattr_value(item.conf, 'DuW_LU_register'))
            reginfo = self._get_register_info(register, 'LU\n')
            if reginfo:
                if not register in self.LUregl:
                    self.LUregl[register] = {'reginfo':
                                             reginfo, 'items': [item]}
                else:
                    if not item in self.LUregl[register]['items']:
                        self.LUregl[register]['items'].append(item)

                return self.update_item
            else:
                self.logger.warning("{}: LU register: {} not supported by configured device!".format(self._name, register))
                return None
        if self.has_iattr(item.conf, 'DuW_WP_register'):
            register = int(self.get_iattr_value(item.conf, 'DuW_WP_register'))
            reginfo = self._get_register_info(register, 'WP\n')
            if reginfo:
                if not register in self.WPregl:
                    self.WPregl[register] = {'reginfo':
                                             reginfo, 'items': [item]}
                else:
                    if not item in self.WPregl[register]['items']:
                        self.WPregl[register]['items'].append(item)

                return self.update_item
            else:
                self.logger.warning("{}: WP register: {} not supported by configured device!".format(self._name, register))
                return None

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'DuW':
            if self.has_iattr(item.conf, 'DuW_LU_register'):
                register = int(self.get_iattr_value(item.conf, 'DuW_LU_register'))
                if register in self.LUregl:
                    reginfo = self.LUregl[register]['reginfo']
                    data = item() * int(reginfo[4]) * (10 ** int(reginfo[5]))
                    if (data < int(reginfo[2]) or data > int(reginfo[3])):
                        self.logger.error("{}: value of LU register: {} out of range, changes ignored!".format(
                            self._name, register))
                        pass
                    else:
                        if reginfo[6] == 'R/W':
                            self.logger.debug("{}: update LU register: {} {} with {}".format(
                                self._name, register,reginfo[1],data))
                            self.write_DW(reginfo[7], register, data)
                        else:
                            (data, done) = self._read_register(reginfo[7], register, int(reginfo[4]), int(reginfo[5]))
                            if done:
                                item(data, 'DuW', 'query')
                                self.logger.info("{}: Queried read only LU register: {}".format(self._name, register))
                            else:
                                self.logger.debug("{}: Query LU register failed: {}".format(self._name, register))
            if self.has_iattr(item.conf, 'DuW_WP_register'):
                register = int(self.get_iattr_value(item.conf, 'DuW_WP_register'))
                if register in self.WPregl:
                    reginfo = self.WPregl[register]['reginfo']
                    data = item() * int(reginfo[4]) * (10 ** int(reginfo[5]))
                    if (data < int(reginfo[2]) or data > int(reginfo[3])):
                        self.logger.error("{}: value of WP register {} out of range, changes ignored!".format(register))
                        pass
                    else:
                        if reginfo[6] == 'R/W':
                            self.logger.debug("{}: update WP register: {} {} with {}".format(
                                self._name, register,reginfo[1],data))
                            self.write_DW(reginfo[7], register, data)
                        else:
                            (data, done) = self._read_register(reginfo[7], register, int(reginfo[4]), int(reginfo[5]))
                            if done:
                                item(data, 'DuW', 'query')
                                self.logger.info("{}: Queried read only WP register: {}".format(self._name, register))
                            else:
                                self.logger.debug("{}: Query WP register failed: {}".format(self._name, register))
