#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2022 De Filippis Ivan
# Copyright 2022 Ronny Schulz
# Copyright 2023-2025 Bernd Meiners
#########################################################################
# This file is part of SmartHomeNG.
#
# Modbus_TCP plugin for SmartHomeNG
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
#########################################################################

from lib.model.smartplugin import SmartPlugin
from datetime import datetime
import threading
import asyncio
import struct
import logging
import time
from .webif import WebInterface

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus import ModbusException

# pymodbus async client
from pymodbus.client import AsyncModbusTcpClient


AttrAddress = 'modBusAddress'
AttrType = 'modBusDataType'
AttrFactor = 'modBusFactor'
AttrByteOrder = 'modBusByteOrder'
AttrWordOrder = 'modBusWordOrder'
AttrSlaveUnit = 'modBusUnit'
AttrObjectType = 'modBusObjectType'
AttrDirection = 'modBusDirection'

BAD_VALUE_SINT16 = 0x8000
BAD_VALUE_SINT32 = 0x80000000
BAD_VALUE_UINT16 = 0xFFFF
BAD_VALUE_UINT32 = 0xFFFFFFFF
BAD_VALUE_UINT64 = 0xFFFFFFFFFFFFFFFF


class modbus_tcp(SmartPlugin):
    """
    This class provides a Plugin for SmarthomeNG to read and or write to modbus
    devices.
    """

    PLUGIN_VERSION = '1.1.0'

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the Modbus TCP plugin.
        The parameters are retrieved from get_parameter_value(parameter_name)
        """

        self.logger.info('Init modbus_tcp plugin')

        # Disable logging from imported modul 'pymodbus'
        if not self.logger.isEnabledFor(logging.DEBUG):
            disable_logger = logging.getLogger('pymodbus')
            if disable_logger is not None:
                self.logger.info(f'change logging level from: {disable_logger} to CRITICAL')
                disable_logger.setLevel(logging.CRITICAL)

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._sh = sh
        self._host = self.get_parameter_value('host')
        self._port = self.get_parameter_value('port')

        # cycle reinterpretation: we keep the original value for mode decisions
        self._cycle_param = self.get_parameter_value('cycle')
        self._cycle = self._cycle_param  # keep for scheduler flush usage when > 0

        self._crontab = self.get_parameter_value('crontab')
        if self._crontab == '':
            self._crontab = None

        self._slaveUnit = self.get_parameter_value('slaveUnit')
        self._slaveUnitRegisterDependend = False

        self._pause_item_path = self.get_parameter_value('pause_item')
        self._pause_item = None

        self._regToRead = {}
        self._regToWrite = {}
        self._pollStatus = {}

        # Buffer for cycle > 0 mode: store only latest value per reg-key
        # { reg_key: {'value': v, 'dt': datetime, 'raw': raw} }
        self._latest_values = {}

        # Threading lock for data shared between SmartHomeNG thread(s) and asyncio thread
        self.lock = threading.Lock()

        # Async infrastructure (SmartPlugin-managed event loop thread)
        self._connection_task = None          # background reconnect/connection keeper
        self._reader_task = None              # continuous acquisition task
        self._client_lock = None              # asyncio.Lock to serialize requests on one TCP connection

        self._aclient = None                  # AsyncModbusTcpClient instance (created in run()/async thread)

        self.connected = False
        self.error_count = 0

        # Small delay between single register reads to avoid a tight loop (still "continuous", but polite)
        self._read_inter_request_delay = 0.01

        self.init_webinterface(WebInterface)

    # ---------------------------------------------------------------------
    # SmartHomeNG lifecycle
    # ---------------------------------------------------------------------

    def run(self):
        """
        Start plugin:
          - start SmartPlugin-managed asyncio loop
          - start async connection management and (depending on cycle) acquisition task
          - optionally schedule "flush" to items for cycle > 0
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': run method called")
        if self.alive:
            return

        # Start asyncio loop in its own thread (SmartPlugin)
        self.start_asyncio(self.plugin_coro())

        # Wait briefly until asyncio loop is running and plugin_coro set alive
        while not self.alive:
            time.sleep(0.1)

        # Scheduler is only used as "flush trigger" for buffered mode (cycle > 0).
        # For cycle == 0/None: no incoming data is processed (no reads, no flush).
        # For cycle < 0: immediate writes from reader task (no flush scheduler).
        if self._cycle_param is not None and self._cycle_param > 0:
            self.error_count = 0
            self.scheduler_add(
                'flush_items_' + self._host,
                self._flush_buffer_to_items,
                cycle=self._cycle_param,
                cron=self._crontab,
                prio=5
            )

        self.logger.debug(f"Plugin '{self.get_fullname()}': run method finished")

    def stop(self):
        """
        Stop plugin:
          - stop scheduler flush
          - stop async tasks, close client, stop loop thread cleanly (SmartPlugin)
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method called")

        # Remove flush scheduler (if added)
        try:
            self.scheduler_remove('flush_items_' + self._host)
        except Exception:
            pass

        # Stop asyncio loop and thread (SmartPlugin)
        self.stop_asyncio()

        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method finished")

    # ---------------------------------------------------------------------
    # Item parsing / update
    # ---------------------------------------------------------------------

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        """
        # check for pause item
        if self._pause_item_path and item.property.path == self._pause_item_path:
            self.logger.debug(f'pause item {item.property.path} registered')
            self._pause_item = item
            self.add_item(item, updating=True)
            return self.update_item

        if self.has_iattr(item.conf, AttrAddress):
            self.logger.debug(f"parse item: {item}")
            regAddr = int(self.get_iattr_value(item.conf, AttrAddress))
            objectType = 'HoldingRegister'
            value = item()
            dataType = 'uint16'
            factor = 1
            byteOrderStr = 'Endian.BIG'
            wordOrderStr = 'Endian.BIG'
            slaveUnit = self._slaveUnit
            dataDirection = 'read'

            if self.has_iattr(item.conf, AttrType):
                dataType = self.get_iattr_value(item.conf, AttrType)

            if self.has_iattr(item.conf, AttrSlaveUnit):
                slaveUnit = int(self.get_iattr_value(item.conf, AttrSlaveUnit))
                if slaveUnit != self._slaveUnit:
                    self._slaveUnitRegisterDependend = True

            if self.has_iattr(item.conf, AttrObjectType):
                objectType = self.get_iattr_value(item.conf, AttrObjectType)

            reg = self.makedictkey(objectType, regAddr, slaveUnit)

            if self.has_iattr(item.conf, AttrDirection):
                dataDirection = self.get_iattr_value(item.conf, AttrDirection)

            if self.has_iattr(item.conf, AttrFactor):
                factor = float(self.get_iattr_value(item.conf, AttrFactor))

            if self.has_iattr(item.conf, AttrByteOrder):
                byteOrderStr = self.get_iattr_value(item.conf, AttrByteOrder)

            if self.has_iattr(item.conf, AttrWordOrder):
                wordOrderStr = self.get_iattr_value(item.conf, AttrWordOrder)

            try:
                byteOrder = Endian[(str(byteOrderStr).split('.')[-1]).upper()]
            except Exception as e:
                self.logger.warning(f"Invalid byteOrder -> default(Endian.BIG) is used. Error:{e}")
                byteOrder = Endian.BIG

            try:
                wordOrder = Endian[(str(wordOrderStr).split('.')[-1]).upper()]
            except Exception as e:
                self.logger.warning(f"Invalid wordOrder -> default(Endian.BIG) is used. Error:{e}")
                wordOrder = Endian.BIG

            regPara = {
                'regAddr': regAddr,
                'slaveUnit': slaveUnit,
                'dataType': dataType,
                'factor': factor,
                'byteOrder': byteOrder,
                'wordOrder': wordOrder,
                'item': item,
                'value': value,
                'objectType': objectType,
                'dataDir': dataDirection
            }

            if dataDirection == 'read':
                self._regToRead.update({reg: regPara})
                self.logger.info(f"parse item: {item} Attributes {regPara}")

            elif dataDirection == 'read_write':
                self._regToRead.update({reg: regPara})
                self._regToWrite.update({reg: regPara})
                self.logger.info(f"parse item: {item} Attributes {regPara}")
                return self.update_item

            elif dataDirection == 'write':
                self._regToWrite.update({reg: regPara})
                self.logger.info(f"parse item: {item} Attributes {regPara}")
                return self.update_item

            else:
                self.logger.warning("Invalid data direction -> default(read) is used")
                self._regToRead.update({reg: regPara})

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated (write to device).
        Writes are scheduled onto the plugin's own asyncio loop (non-blocking).
        """
        objectType = 'HoldingRegister'
        slaveUnit = self._slaveUnit
        dataDirection = 'read'

        # check for pause item
        if self._pause_item is not None and item is self._pause_item:
            if caller != self.get_shortname():
                self.logger.debug(f'pause item changed to {item()}')
                if item() and self.alive:
                    self.stop()
                elif (not item()) and (not self.alive):
                    self.run()
            return

        # ignore changes triggered by ourselves
        if caller == self.get_fullname():
            return

        if not self.alive:
            return

        if self.has_iattr(item.conf, AttrDirection):
            dataDirection = self.get_iattr_value(item.conf, AttrDirection)
            if not (dataDirection == 'read_write' or dataDirection == 'write'):
                self.logger.debug(f'update_item: {item} Writing is not allowed - selected dataDirection:{dataDirection}')
                return

            if self.has_iattr(item.conf, AttrAddress):
                regAddr = int(self.get_iattr_value(item.conf, AttrAddress))
            else:
                self.logger.warning(f'update_item:{item} Item has no register address')
                return

            if self.has_iattr(item.conf, AttrSlaveUnit):
                slaveUnit = int(self.get_iattr_value(item.conf, AttrSlaveUnit))
                if slaveUnit != self._slaveUnit:
                    self._slaveUnitRegisterDependend = True

            if self.has_iattr(item.conf, AttrObjectType):
                objectType = self.get_iattr_value(item.conf, AttrObjectType)

            reg = self.makedictkey(objectType, regAddr, slaveUnit)

            if reg in self._regToWrite:
                regPara = self._regToWrite[reg]
                self.logger.debug(f'update_item:{item} value:{item()} regToWrite: {reg}')

                # IMPORTANT ASYNC TRANSITION:
                # schedule non-blocking write coroutine onto SmartPlugin asyncio loop
                try:
                    self.run_asyncio_coro(self._schedule_write(regPara, item()), timeout=1)
                except Exception as e:
                    self.logger.error(f"update_item: scheduling async write failed: {e}")

    # ---------------------------------------------------------------------
    # Logging helper
    # ---------------------------------------------------------------------

    def log_error(self, message):
        """
        Logs an error message based on error count
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.error(message)
        else:
            if self.error_count < 10:
                self.logger.error(message)
            elif self.error_count < 100:
                if self.error_count % 10 == 0:
                    self.logger.error(f"{message} [Logging suppressed every 10th error]")
            else:
                if self.error_count % 100 == 0:
                    self.logger.error(f"{message} [Logging suppressed every 100th error]")

    # ---------------------------------------------------------------------
    # Scheduler flush for cycle > 0 (buffered writes to items)
    # ---------------------------------------------------------------------

    def _flush_buffer_to_items(self):
        """
        Called by SmartHomeNG scheduler every 'cycle' seconds (cycle > 0).
        Writes the latest buffered values to items.
        Older values are implicitly discarded because we only keep the latest value per register key.
        """
        if not self.alive:
            return
        # cycle==0/None => do not write anything
        if self._cycle_param is None or self._cycle_param == 0:
            return

        now = datetime.now()
        regCount = 0

        with self.lock:
            # snapshot keys to minimize time under lock
            keys = list(self._latest_values.keys())

        for reg in keys:
            with self.lock:
                entry = self._latest_values.get(reg)
                regPara = self._regToRead.get(reg)
                if entry is None or regPara is None:
                    continue

                value = entry.get('value')
                dt = entry.get('dt')

                # avoid re-writing the same buffered timestamp repeatedly
                last_item_write_dt = regPara.get('last_item_write_dt')
                if last_item_write_dt is not None and dt is not None and dt <= last_item_write_dt:
                    continue

                regPara['last_item_write_dt'] = dt

            try:
                item = regPara['item']
                item(value, self.get_fullname())
                regCount += 1

                with self.lock:
                    if 'read_dt' in regPara:
                        regPara['last_read_dt'] = regPara.get('read_dt')
                    if 'value' in regPara:
                        regPara['last_value'] = regPara.get('value')
                    regPara['read_dt'] = dt if dt is not None else now
                    regPara['value'] = value

            except Exception as e:
                self.logger.error(f"flush: cannot write item for {reg}: {e}")

        if regCount > 0:
            with self.lock:
                self._pollStatus['last_dt'] = now
                self._pollStatus['regCount'] = regCount

        self.logger.debug(f"flush_buffer_to_items: wrote {regCount} buffered values")

    # ---------------------------------------------------------------------
    # Async start/stop + tasks (SmartPlugin asyncio)
    # ---------------------------------------------------------------------

    async def plugin_coro(self):
        """
        Coroutine for the asyncio session that communicates with the Modbus device.
        It will only terminate when the plugin is stopped.
        """
        self.logger.info("plugin_coro started")

        # Create async primitives in the correct loop
        self._client_lock = asyncio.Lock()

        # Create client in our loop thread (important for asyncio transports)
        self._aclient = AsyncModbusTcpClient(self._host, port=self._port)
        self.connected = False
        self.error_count = 0

        # Start background connection management (reconnect on drop)
        self._connection_task = asyncio.create_task(self._connection_keeper(), name="connection_keeper")

        # Start acquisition task depending on cycle mode
        # cycle in (None, 0) => do NOT process incoming data (no reads, no item writes)
        if self._cycle_param is not None and self._cycle_param != 0:
            self._reader_task = asyncio.create_task(self._acquisition_loop(), name="acquisition_loop")
        else:
            self.logger.info(
                f"{self.get_fullname()}: cycle is None/0 -> no incoming data processing (no reads, no item updates)"
            )

        self.alive = True
        self.logger.info("plugin_coro: Plugin is running (self.alive=True)")

        # wait until STOP is received
        await self.wait_for_asyncio_termination()

        # Cancel tasks and close client
        for task in [self._reader_task, self._connection_task]:
            if task and not task.done():
                task.cancel()
        try:
            if self._aclient:
                self._aclient.close()
        except Exception:
            pass

        self._reader_task = None
        self._connection_task = None
        self._aclient = None
        self.connected = False

        self.alive = False
        self.logger.info("plugin_coro: Plugin is stopped (self.alive=False)")

        self.logger.info("plugin_coro finished")
        return

    async def _connection_keeper(self):
        """
        Keeps the TCP connection alive and performs automatic reconnect.
        Runs forever until stop event is set.
        """
        backoff = 1.0
        while self.alive:
            try:
                if self._aclient is None:
                    self._aclient = AsyncModbusTcpClient(self._host, port=self._port)
                    self.connected = False

                # If pymodbus exposes .connected use it; else rely on our flag
                pm_connected = getattr(self._aclient, "connected", None)
                if pm_connected is False:
                    self.connected = False

                if not self.connected:
                    try:
                        ok = await self._aclient.connect()
                    except Exception as e:
                        ok = False
                        self.error_count += 1
                        self.log_error(
                            f"connection exception: {self._host}:{self._port} {e}, errors: {self.error_count}"
                        )

                    if ok:
                        self.connected = True
                        self.error_count = 0
                        backoff = 1.0
                        self.logger.info(f"connected to {self._host}:{self._port}")
                    else:
                        self.connected = False
                        self.error_count += 1
                        self.log_error(
                            f"could not connect to {self._host}:{self._port}, connection_attempts: {self.error_count}"
                        )
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2.0, 30.0)
                        continue

                # Connected: sleep a bit, acquisition/writes will detect drops on errors
                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Never crash the plugin
                self.logger.error(f"connection_keeper unexpected error: {e}")
                await asyncio.sleep(2.0)

    async def _wait_connected(self):
        """
        Wait until connected or stop/alive condition ends.
        """
        while self.alive and (not self.connected):
            await asyncio.sleep(0.2)
        return self.connected

    async def _acquisition_loop(self):
        """
        Continuous async acquisition of Modbus values.

        This replaces classic scheduler polling. Values are acquired asynchronously and:
          - cycle > 0: buffered in self._latest_values (only latest per item)
          - cycle < 0: written immediately to items (no buffering)
        """
        while self.alive:
            try:
                # Wait for connection (reconnect handled by connection_keeper)
                if not await self._wait_connected():
                    await asyncio.sleep(0.5)
                    continue

                startTime = datetime.now()
                regCount = 0

                # Iterate over a snapshot of regToRead to avoid long locks
                with self.lock:
                    regs = list(self._regToRead.items())

                for reg, regPara in regs:
                    if not self.alive:
                        break

                    try:
                        raw_value = await self.__read_Registers_async(regPara)
                    except ModbusException as e:
                        self.logger.error(f"ModbusException raised while reading: {e}")
                        raw_value = None
                    except Exception as e:
                        # Most likely connection drop => mark disconnected and let keeper reconnect
                        self.logger.error(f"read exception: {e}")
                        self.connected = False
                        try:
                            if self._aclient:
                                self._aclient.close()
                        except Exception:
                            pass
                        raw_value = None

                    if raw_value is None:
                        await asyncio.sleep(self._read_inter_request_delay)
                        continue

                    if self.is_NaN(raw_value, regPara['dataType']):
                        await asyncio.sleep(self._read_inter_request_delay)
                        continue

                    value = raw_value
                    if regPara['factor'] != 1 and isinstance(value, (int, float)):
                        value *= regPara['factor']

                    dt = datetime.now()

                    # cycle < 0: immediate write to item (no buffering, no scheduler delay)
                    if self._cycle_param is not None and self._cycle_param < 0:
                        try:
                            item = regPara['item']
                            item(value, self.get_fullname())
                        except Exception as e:
                            self.logger.error(f"immediate item write failed for {reg}: {e}")
                        with self.lock:
                            if 'read_dt' in regPara:
                                regPara['last_read_dt'] = regPara.get('read_dt')
                            if 'value' in regPara:
                                regPara['last_value'] = regPara.get('value')
                            regPara['read_dt'] = dt
                            regPara['value'] = value

                    # cycle > 0: buffer latest only; flush scheduler writes later
                    else:
                        with self.lock:
                            self._latest_values[reg] = {'value': value, 'dt': dt, 'raw': raw_value}

                    regCount += 1
                    await asyncio.sleep(self._read_inter_request_delay)

                duration = datetime.now() - startTime
                if regCount > 0:
                    with self.lock:
                        self._pollStatus['last_dt'] = datetime.now()
                        self._pollStatus['regCount'] = regCount
                self.logger.debug(f"acquisition_loop: read {regCount} register(s) in {duration} seconds")

                # Yield control; do not spin too aggressively
                await asyncio.sleep(0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Never crash the plugin
                self.logger.error(f"acquisition_loop unexpected error: {e}")
                await asyncio.sleep(1.0)

    # ---------------------------------------------------------------------
    # Async Modbus IO (read/write) - based on original logic, but await-based
    # ---------------------------------------------------------------------

    async def _schedule_write(self, regPara, value):
        """
        Schedule a Modbus write without blocking the caller.
        """
        asyncio.create_task(self.__write_Registers_async(regPara, value))
        return True

    async def __write_Registers_async(self, regPara, value):
        """
        Async version of __write_Registers():
          - no blocking connect/read/write
          - uses persistent AsyncModbusTcpClient
          - serializes access with asyncio.Lock
        """
        objectType = regPara['objectType']
        address = regPara['regAddr']
        slaveUnit = regPara['slaveUnit']
        bo = regPara['byteOrder']
        wo = regPara['wordOrder']
        dataTypeStr = regPara['dataType']
        dataType = ''.join(filter(str.isalpha, dataTypeStr))  # vom dataType die Ziffen entfernen z.B. uint16 = uint

        try:
            bits = int(''.join(filter(str.isdigit, dataTypeStr)))  # bit-Zahl aus aus dataType z.B. uint16 = 16
        except:
            bits = 16

        # Wait for connection (reconnect in background)
        if not await self._wait_connected():
            self.log_error(f"write skipped (not connected): {self._host}:{self._port}")
            return

        if regPara['factor'] != 1:
            value = value * (1 / regPara['factor'])

        self.logger.debug(
            f"write {value} to {objectType}.{address}.{address} (address.slaveUnit) dataType:{dataTypeStr}"
        )

        builder = BinaryPayloadBuilder(byteorder=bo, wordorder=wo)

        if dataType.lower() == 'uint':
            if bits == 16:
                builder.add_16bit_uint(int(value))
            elif bits == 32:
                builder.add_32bit_uint(int(value))
            elif bits == 64:
                builder.add_64bit_uint(int(value))
            else:
                self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
                return
        elif dataType.lower() == 'int':
            if bits == 16:
                builder.add_16bit_int(int(value))
            elif bits == 32:
                builder.add_32bit_int(int(value))
            elif bits == 64:
                builder.add_64bit_int(int(value))
            else:
                self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
                return
        elif dataType.lower() == 'float':
            if bits == 32:
                builder.add_32bit_float(value)
            elif bits == 64:
                builder.add_64bit_float(value)
            else:
                self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
                return
        elif dataType.lower() == 'string':
            builder.add_string(value)
        elif dataType.lower() == 'bit':
            if objectType == 'Coil' or objectType == 'DiscreteInput':
                if not isinstance(value, bool):  # test is boolean
                    self.logger.error(f"Value is not boolean: {value}")
                    return
            else:
                if set(value).issubset({'0', '1'}) and bool(value):  # test is bit-string '00110101'
                    builder.add_bits(value)
                else:
                    self.logger.error(f"Value is not a bitstring: {value}")
                    return
        else:
            self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
            return

        # IMPORTANT ASYNC TRANSITION: actual Modbus write is awaited, never blocking a SmartHomeNG thread
        try:
            async with self._client_lock:
                if objectType == 'Coil':
                    result = await self._aclient.write_coil(address, value, slave=slaveUnit)
                elif objectType == 'HoldingRegister':
                    registers = builder.to_registers()
                    result = await self._aclient.write_registers(address, registers, slave=slaveUnit)
                elif objectType == 'DiscreteInput':
                    self.logger.warning(f"this object type cannot be written {objectType}:{address} slaveUnit:{slaveUnit}")
                    return
                elif objectType == 'InputRegister':
                    self.logger.warning(f"this object type cannot be written {objectType}:{address} slaveUnit:{slaveUnit}")
                    return
                else:
                    return
        except Exception as e:
            self.logger.error(f"write exception: {e}")
            self.connected = False
            try:
                if self._aclient:
                    self._aclient.close()
            except Exception:
                pass
            return

        if result is None or result.isError():
            self.logger.error(f"write error: {result} {objectType}.{address}.{slaveUnit} (address.slaveUnit)")
            return

        # Update stats dict (shared with webif) - protect with threading lock
        with self.lock:
            if 'write_dt' in regPara:
                regPara['last_write_dt'] = regPara['write_dt']
                regPara['write_dt'] = datetime.now()
            else:
                regPara.update({'write_dt': datetime.now()})

            if 'write_value' in regPara:
                regPara['last_write_value'] = regPara['write_value']
                regPara['write_value'] = value
            else:
                regPara.update({'write_value': value})

    async def __read_Registers_async(self, regPara: dict):
        """
        Async version of __read_Registers() - returns decoded value.
        """
        objectType = regPara['objectType']
        dataTypeStr = regPara['dataType']
        dataType = ''.join(filter(str.isalpha, dataTypeStr))
        bo = regPara['byteOrder']
        wo = regPara['wordOrder']
        slaveUnit = regPara['slaveUnit']
        address = regPara['regAddr']

        try:
            bits = int(''.join(filter(str.isdigit, dataTypeStr)))
        except Exception:
            bits = 16

        if dataType.lower() == 'string':
            registerCount = int(bits / 2)  # string: bits means bytes -> string16 = 16 bytes -> 8 registers
        else:
            registerCount = int(bits / 16)

        if not self.connected:
            # connection_keeper will reconnect; keep this silent-ish
            return None

        # IMPORTANT ASYNC TRANSITION: actual Modbus read is awaited
        try:
            async with self._client_lock:
                if objectType == 'Coil':
                    result = await self._aclient.read_coils(address, count=registerCount, slave=slaveUnit)
                elif objectType == 'DiscreteInput':
                    result = await self._aclient.read_discrete_inputs(address, count=registerCount, slave=slaveUnit)
                elif objectType == 'InputRegister':
                    result = await self._aclient.read_input_registers(address, count=registerCount, slave=slaveUnit)
                elif objectType == 'HoldingRegister':
                    result = await self._aclient.read_holding_registers(address, count=registerCount, slave=slaveUnit)
                else:
                    self.logger.error(f"{AttrObjectType} not supported: {objectType}")
                    return None
        except Exception as e:
            # Connection likely lost
            raise e

        if result is None or result.isError():
            self.logger.error(
                f"read error: {result} {objectType}.{address}.{slaveUnit} (address.slaveUnit) regCount:{registerCount}"
            )
            return None

        # Decode
        if objectType == 'Coil' or objectType == 'DiscreteInput':
            return result.bits[0]

        decoder = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=bo, wordorder=wo)
        self.logger.debug(
            f"read {objectType}.{address}.{slaveUnit} (address.slaveUnit) regCount:{registerCount} result:{result}"
        )

        try:
            if dataType.lower() == 'uint':
                if bits == 16:
                    return decoder.decode_16bit_uint()
                elif bits == 32:
                    return decoder.decode_32bit_uint()
                elif bits == 64:
                    return decoder.decode_64bit_uint()
                else:
                    self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")

            elif dataType.lower() == 'int':
                if bits == 16:
                    return decoder.decode_16bit_int()
                elif bits == 32:
                    return decoder.decode_32bit_int()
                elif bits == 64:
                    return decoder.decode_64bit_int()
                else:
                    self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")

            elif dataType.lower() == 'float':
                if bits == 32:
                    return decoder.decode_32bit_float()
                elif bits == 64:
                    return decoder.decode_64bit_float()
                else:
                    self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")

            elif dataType.lower() == 'string':
                # bei string: bits = bytes !! string16 -> 16Byte
                ret = decoder.decode_string(bits)
                return str(ret, 'ASCII')

            elif dataType.lower() == 'bit':
                # for register-based bits (not coils/discrete inputs)
                return decoder.decode_bits()

            else:
                self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")

        except struct.error:
            self.logger.error(
                f"unable to unpack data for datatype={dataType.lower()} for read "
                f"{objectType}.{address}.{slaveUnit} (address.slaveUnit) regCount:{registerCount}"
            )
            return None

        return None

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def is_NaN(value, dataType: str) -> bool:
        """
        Check if a returned value is a bad value and return True if it is
        """
        if dataType == 'int16':
            return value == BAD_VALUE_SINT16
        elif dataType == 'int32':
            return value == BAD_VALUE_SINT32
        elif dataType == 'uint16':
            return value == BAD_VALUE_UINT16
        elif dataType == 'uint32':
            return value == BAD_VALUE_UINT32
        elif dataType == 'uint64':
            return value == BAD_VALUE_UINT64
        return False

    @staticmethod
    def makedictkey(objectType: str, regAddr, slaveUnit) -> str:
        # dictionary key: objectType.regAddr.slaveUnit // HoldingRegister.528.1
        return f"{str(objectType)}.{str(regAddr)}.{str(slaveUnit)}"
