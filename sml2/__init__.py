#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2014 Oliver Hinckel                  github@ollisnet.de
#  Copyright 2018-2021                              Bernd.Meiners@mail.de
#  Copyright 2022-2022 Julian Scholle       julian.scholle@googlemail.com
#########################################################################
#
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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

import logging
import time
import re
import serial
import threading
import struct
import socket
import errno
import asyncio
import serial_asyncio
import traceback
from smllib import SmlStreamReader
from smllib import const as smlConst

from lib.module import Modules
from lib.item import Items

from lib.model.smartplugin import *
from .webif import WebInterface

SML_SCHEDULER_NAME = 'Sml2'


class Sml2(SmartPlugin):
    """
    ASYNC IO Related
    """

    def start_background_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    class Reader(asyncio.Protocol):

        def __init__(self):
            self.buf = None
            self.smlx = None
            self.transport = None

        def __call__(self):
            return self

        def connection_made(self, transport):
            """Store the serial transport and prepare to receive data.
            """
            self.transport = transport
            self.buf = bytes()
            self.smlx.logger.debug("Reader connection created")
            self.smlx.connected = True

        def data_received(self, chunk):
            """Store characters until a newline is received.
            """
            self.smlx.logger.debug(f"Smartmeter is sending {len(chunk)} bytes of data")
            self.buf += chunk

            if len(self.buf) < 100:
                return
            try:
                self.smlx.stream.add(self.buf)
                self.buf = bytes()
                self.smlx.parse_data()
            except Exception as e:
                self.smlx.logger.error(f'Reading data from {self.smlx._target} failed with exception {e}')
            # just in case of many errors, reset buffer
            if len(self.buf) > 100000:
                self.smlx.logger.error("Buffer got to large, doing buffer reset")
                self.buf = bytes()

        def connection_lost(self, exc):
            self.smlx.logger.error("Connection so serial device was closed")
            self.smlx.connected = False

    PLUGIN_VERSION = '2.0.0'

    def __init__(self, sh):
        """
        Initializes the plugin. The parameters described for this method are pulled from the entry in plugin.conf.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.cycle = self.get_parameter_value('cycle')

        self.host = self.get_parameter_value('host')  # None
        self.port = self.get_parameter_value('port')  # 0
        self.serialport = self.get_parameter_value('serialport')  # None

        self.use_polling = self.get_parameter_value('use_polling')  # false
        self.cycle = self.get_parameter_value('cycle')

        self.device = self.get_parameter_value('device')  # raw
        self.timeout = self.get_parameter_value('timeout')  # 5
        self.buffersize = self.get_parameter_value('buffersize')  # 1024
        self.date_offset = self.get_parameter_value('date_offset')  # 0

        self.connected = False
        self.alive = False
        self._serial = None
        self._sock = None
        self._target = None
        self._items = {}
        self._item_dict = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        self.reader = False
        self.loop = None
        self.loop_thread = None
        self.stream = SmlStreamReader()
        self.init_webinterface(WebInterface)
        self.task = None
        self.values = {}

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': run method called")
        # Setup scheduler for device poll loop
        if self.use_polling:
            self.scheduler_add(SML_SCHEDULER_NAME, self.poll_device, cycle=self.cycle)
        else:
            self.loop = asyncio.new_event_loop()
            self.loop_thread = threading.Thread(target=self.start_background_loop, args=(), daemon=True)
            self.loop_thread.start()

            self.reader = self.Reader()
            self.reader.smlx = self
            reader = serial_asyncio.create_serial_connection(self.loop, self.reader, self.serialport, baudrate=9600,
                                                             bytesize=serial.EIGHTBITS,
                                                             parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                                                             timeout=self.timeout)

            self.task = asyncio.run_coroutine_threadsafe(reader, self.loop)

        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method called")
        if self.use_polling:
            self.scheduler_remove(SML_SCHEDULER_NAME)
            self.alive = False
            self.disconnect()
        else:
            self.loop.stop()
            self.loop_thread.join()
            self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.

        :param item:    The item to process.
        :return:        returns update_item function if changes are to be watched
        """

        if self.has_iattr(item.conf, 'sml_obis'):
            obis = self.get_iattr_value(item.conf, 'sml_obis')
            prop = self.get_iattr_value(item.conf, 'sml_prop') if self.has_iattr(item.conf, 'sml_prop') else 'valueReal'
            if obis not in self._items:
                self._items[obis] = {}
            if prop not in self._items[obis]:
                self._items[obis][prop] = []
            self._items[obis][prop].append(item)
            self._item_dict[item] = (obis, prop)
            self.logger.debug(f'Attach {item.id()} with {obis=} and {prop=}')
        return None

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if caller != self.get_shortname():
            # Code to execute, only if the item has not been changed by this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))
            pass

    def connect(self):
        with self._lock:
            self._target = None
            try:
                if self.serialport is not None:
                    self._target = f'serial://{self.serialport}'
                    self._serial = serial.Serial(self.serialport, 9600, serial.EIGHTBITS, serial.PARITY_NONE,
                                                 serial.STOPBITS_ONE, timeout=self.timeout)

                elif self.host is not None:
                    self._target = f'tcp://{self.host}:{self.port}'
                    self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._sock.settimeout(2)
                    self._sock.connect((self.host, self.port))
                    self._sock.setblocking(False)

            except Exception as e:
                self.logger.error(f'SML: Could not connect to {self._target}: {e}')
                return

            self.logger.info(f'SML: Connected to {self._target}')
            self.connected = True

    def disconnect(self):
        with self._lock:
            if self.connected:
                try:
                    if self._serial is not None:
                        self._serial.close()
                        self._serial = None
                    elif self._sock is not None:
                        self._sock.shutdown(socket.SHUT_RDWR)
                        self._sock = None
                except Exception:
                    pass
                self.logger.info('SML: Disconnected!')
                self.connected = False
                self._target = None

    def _read(self, length):
        total = bytes()
        self.logger.debug('Start read')
        if self._serial is not None:
            while True:
                ch = self._serial.read()
                # self.logger.debug(f"Read {ch=}")
                if len(ch) == 0:
                    self.logger.debug('End read')
                    return total
                total += ch
                if len(total) >= length:
                    self.logger.debug('End read')
                    return total
        elif self._sock is not None:
            while True:
                try:
                    data = self._sock.recv(length)
                    if data:
                        total += data
                except socket.error as e:
                    if e.args[0] == errno.EAGAIN or e.args[0] == errno.EWOULDBLOCK:
                        break
                    else:
                        raise e

            self.logger.debug('End read')
            return b''.join(total)

    def poll_device(self):
        """
        Polls for updates of the device, called by the scheduler.
        """

        # check if another cyclic cmd run is still active
        successfully_acquired = self._lock.acquire(False)
        if not successfully_acquired:
            self.logger.warning(
                'Triggered cyclic poll_device, but previous cyclic run is still active. Therefore request will be skipped.')
            return

        start = time.time()

        try:
            self.logger.debug('Polling Smartmeter now')
            self.connect()

            if not self.connected:
                self.logger.error('Not connected, no query possible')
                return
            else:
                self.logger.debug('Connected, try to query')

            start = time.time()
            data = self._read(self.buffersize)
            if len(data) == 0:
                self.logger.error('Reading data from device returned 0 bytes!')
                return

            self.logger.debug(f'Read {len(data)} bytes')
            self.stream.add(data)
            self.parse_data()

        except Exception as e:
            self.logger.error(f'Reading data from {self._target} failed with exception {e}')
            return

        finally:
            cycletime = time.time() - start
            self.disconnect()
            self.logger.debug(f"Polling Smartmeter done. Poll cycle took {cycletime} seconds.")
            self._lock.release()

    def parse_data(self):
        while True:
            try:
                frame = self.stream.get_frame()
                if frame is None:
                    break

                obis_values = frame.get_obis()
                for sml_entry in obis_values:
                    obis_code = sml_entry.obis.obis_code
                    if obis_code not in self.values:
                        self.values[obis_code] = dict()
                        self.values[obis_code]['name'] = smlConst.OBIS_NAMES.get(sml_entry.obis)
                        self.values[obis_code]['unit'] = smlConst.UNITS.get(sml_entry.unit)
                    if obis_code in self._items:
                        if 'valueReal' in self._items[obis_code]:
                            for item in self._items[obis_code]['valueReal']:
                                item(sml_entry.get_value(), self.get_shortname())
            except Exception as e:
                detail = traceback.format_exc()
                self.logger.warning(f'Preparing and parsing data failed with exception {e}: and detail: {detail}')

    @property
    def item_list(self):
        return list(self._item_dict.keys())

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()
