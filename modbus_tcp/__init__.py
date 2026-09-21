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
import inspect
import logging
import time
from .webif import WebInterface

from pymodbus import ModbusException

# pymodbus async client
from pymodbus.client import AsyncModbusTcpClient

# pymodbus >= 3.10 renamed the 'slave' keyword argument to 'device_id'.
# Detect once at import time so the plugin runs with both old and new pymodbus.
try:
    _UNIT_KWARG = 'slave' if 'slave' in inspect.signature(
        AsyncModbusTcpClient.read_holding_registers
    ).parameters else 'device_id'
except Exception:
    _UNIT_KWARG = 'slave'


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
        self._cycle = self._cycle_param

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

        # Threading lock for data shared between SmartHomeNG thread(s) and asyncio thread
        self.lock = threading.Lock()

        # Async infrastructure (SmartPlugin-managed event loop thread)
        self._connection_task = None          # background reconnect/connection keeper
        self._reader_task = None              # continuous acquisition task
        self._scheduled_read_task = None      # scheduler-triggered one-shot read task
        self._write_tasks = set()             # currently pending/running async write tasks
        self._client_lock = None              # asyncio.Lock to serialize requests on one TCP connection
        self._read_cycle_lock = None          # asyncio.Lock to avoid overlapping full read passes

        self._aclient = None                  # AsyncModbusTcpClient instance (created in run()/async thread)

        self.connected = False
        self.error_count = 0

        # Small delay between single register reads to avoid a tight loop (still "continuous", but polite)
        self._read_inter_request_delay = 0.01
        self._read_idle_delay = 1.0
        self._shutdown_timeout = 5.0
        self._write_timeout = 10.0

        self.init_webinterface(WebInterface)

    # ---------------------------------------------------------------------
    # SmartHomeNG lifecycle
    # ---------------------------------------------------------------------

    def run(self):
        """
        Start plugin:
          - start SmartPlugin-managed asyncio loop
          - start async connection management
          - optionally schedule cycle/crontab-triggered read passes
          - start continuous acquisition task only for cycle < 0
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': run method called")
        if self.alive:
            return

        # Start asyncio loop in its own thread (SmartPlugin)
        self.start_asyncio(self.plugin_coro())

        # Wait briefly until asyncio loop is running and plugin_coro set alive
        start = time.monotonic()
        while not self.alive:
            if time.monotonic() - start > 10:
                self.logger.error(f"Plugin '{self.get_fullname()}': asyncio startup timed out")
                return
            time.sleep(0.1)

        scheduler_cycle = self._cycle_param if self._cycle_param is not None and self._cycle_param > 0 else None
        if not self._cycle_is_immediate() and (scheduler_cycle is not None or self._crontab is not None):
            self.error_count = 0
            self.scheduler_add(
                self._scheduler_name(),
                self._trigger_async_read,
                cycle=scheduler_cycle,
                cron=self._crontab,
                prio=5
            )

        self.logger.debug(f"Plugin '{self.get_fullname()}': run method finished")

    def stop(self):
        """
        Stop plugin:
          - stop scheduler trigger
          - stop async tasks, close client, stop loop thread cleanly (SmartPlugin)
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method called")

        # Remove scheduler trigger (if added)
        try:
            self.scheduler_remove(self._scheduler_name())
        except Exception:
            pass

        # Remove obsolete scheduler name from previous async implementation if present
        try:
            self.scheduler_remove('flush_items_' + self._host)
        except Exception:
            pass

        self.alive = False

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

            byteOrder = (str(byteOrderStr).split('.')[-1]).upper()
            if byteOrder not in ('BIG', 'LITTLE'):
                self.logger.warning(f"Invalid byteOrder -> default(BIG) is used. Error:{byteOrderStr}")
                byteOrder = 'BIG'

            wordOrder = (str(wordOrderStr).split('.')[-1]).upper()
            if wordOrder not in ('BIG', 'LITTLE'):
                self.logger.warning(f"Invalid wordOrder -> default(BIG) is used. Error:{wordOrderStr}")
                wordOrder = 'BIG'

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
        self._read_cycle_lock = asyncio.Lock()

        # Create client in our loop thread (important for asyncio transports)
        self._aclient = AsyncModbusTcpClient(self._host, port=self._port)
        self.connected = False
        self.error_count = 0

        incoming_enabled = self._incoming_data_enabled()
        write_enabled = self._write_data_enabled()

        if not incoming_enabled and self._regToRead:
            self.logger.warning(
                f"{self.get_fullname()}: cycle is 0 and no crontab is configured; "
                f"{len(self._regToRead)} read item(s) will keep init/cache/database values"
            )

        # Start background connection management only when reads or writes can happen.
        if incoming_enabled or write_enabled:
            self._connection_task = asyncio.create_task(self._connection_keeper(), name="connection_keeper")
        else:
            self.logger.info(
                f"{self.get_fullname()}: no incoming data processing and no write items; "
                f"not opening a Modbus TCP connection"
            )

        # Start continuous acquisition task only for immediate mode.
        # Positive cycle/crontab reads are triggered by SmartHomeNG scheduler.
        if self._cycle_is_immediate():
            self._reader_task = asyncio.create_task(self._acquisition_loop(), name="acquisition_loop")
        else:
            self.logger.info(
                f"{self.get_fullname()}: no continuous incoming data processing"
            )

        self.alive = True
        self.logger.info("plugin_coro: Plugin is running (self.alive=True)")

        # wait until STOP is received
        await self.wait_for_asyncio_termination()
        self.alive = False

        self._close_client()

        # Cancel tasks and close client
        tasks_to_cancel = [
            task for task in [
                self._reader_task,
                self._scheduled_read_task,
                self._connection_task,
                *self._write_tasks
            ]
            if task and not task.done()
        ]
        for task in tasks_to_cancel:
            task.cancel()
        if tasks_to_cancel:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                    timeout=self._shutdown_timeout
                )
            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Timeout while stopping Modbus async tasks after {self._shutdown_timeout} seconds"
                )

        self._close_client()

        self._reader_task = None
        self._scheduled_read_task = None
        self._connection_task = None
        self._write_tasks.clear()
        self._read_cycle_lock = None

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

    async def _wait_connected(self, timeout=None):
        """
        Wait until connected or stop/alive condition ends.
        """
        start = time.monotonic()
        while self.alive and (not self.connected):
            if timeout is not None:
                remaining = timeout - (time.monotonic() - start)
                if remaining <= 0:
                    return False
                await asyncio.sleep(min(0.2, remaining))
            else:
                await asyncio.sleep(0.2)
        return self.connected

    async def _acquisition_loop(self):
        """
        Continuous async acquisition of Modbus values for cycle < 0 mode.
        """
        while self.alive:
            try:
                regCount = await self._read_registers_once()
                if regCount is None:
                    await asyncio.sleep(self._read_idle_delay)
                    continue

                if self._cycle_is_immediate():
                    await asyncio.sleep(0)
                else:
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Never crash the plugin
                self.logger.error(f"acquisition_loop unexpected error: {e}")
                await asyncio.sleep(1.0)

    async def _read_registers_once(self):
        """
        Read all configured registers once and write successful values directly to items.
        Returns None when there are no read items.
        """
        if not await self._wait_connected():
            await asyncio.sleep(0.5)
            return 0

        if self._read_cycle_lock is not None and self._read_cycle_lock.locked():
            self.logger.debug("read cycle already running, skipping overlapping trigger")
            return 0

        async with self._read_cycle_lock:
            startTime = datetime.now()
            regCount = 0

            with self.lock:
                regs = list(self._regToRead.items())

            if not regs:
                return None

            for reg, regPara in regs:
                if not self.alive:
                    break

                try:
                    raw_value = await self.__read_Registers_async(regPara)
                except ModbusException as e:
                    if not self.alive:
                        self.logger.debug(f"Modbus read cancelled while stopping: {e}")
                        break
                    self.logger.error(f"ModbusException raised while reading: {e}")
                    self._close_client()
                    raw_value = None
                except Exception as e:
                    if not self.alive:
                        self.logger.debug(f"read cancelled while stopping: {e}")
                        break
                    self.logger.error(f"read exception: {e}")
                    self._close_client()
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
                try:
                    item = regPara['item']
                    item(value, self.get_fullname())
                except Exception as e:
                    self.logger.error(f"item write failed for {reg}: {e}")

                with self.lock:
                    if 'read_dt' in regPara:
                        regPara['last_read_dt'] = regPara.get('read_dt')
                    if 'value' in regPara:
                        regPara['last_value'] = regPara.get('value')
                    regPara['read_dt'] = dt
                    regPara['value'] = value

                regCount += 1
                await asyncio.sleep(self._read_inter_request_delay)

            duration = datetime.now() - startTime
            if regCount > 0:
                with self.lock:
                    self._pollStatus['last_dt'] = datetime.now()
                    self._pollStatus['regCount'] = regCount
            self.logger.debug(f"read cycle: read {regCount} register(s) in {duration} seconds")
            return regCount

    def _trigger_async_read(self):
        """
        Scheduler callback for cycle/crontab-triggered read passes.
        """
        if not self.alive:
            return
        try:
            self.run_asyncio_coro(self._schedule_triggered_read(), timeout=1)
        except Exception as e:
            self.logger.error(f"trigger_async_read: scheduling read failed: {e}")

    async def _schedule_triggered_read(self):
        if self._scheduled_read_task is not None and not self._scheduled_read_task.done():
            self.logger.debug("triggered read already running")
            return False
        self._scheduled_read_task = asyncio.create_task(self._read_registers_once(), name="triggered_read")
        self._scheduled_read_task.add_done_callback(self._log_read_task_result)
        return True

    def _log_read_task_result(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"read task failed: {e}")

    # ---------------------------------------------------------------------
    # Async Modbus IO (read/write) - based on original logic, but await-based
    # ---------------------------------------------------------------------

    async def _schedule_write(self, regPara, value):
        """
        Schedule a Modbus write without blocking the caller.
        """
        task = asyncio.create_task(self.__write_Registers_async(regPara, value))
        self._write_tasks.add(task)
        task.add_done_callback(self._log_write_task_result)
        return True

    def _log_write_task_result(self, task):
        """
        Make sure exceptions from fire-and-forget write tasks are logged.
        """
        self._write_tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"write task failed: {e}")

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
        except Exception:
            bits = 16

        # Wait for connection (reconnect in background)
        if not await self._wait_connected(timeout=self._write_timeout):
            self.log_error(
                f"write skipped (not connected after {self._write_timeout} seconds): {self._host}:{self._port}"
            )
            return

        if regPara['factor'] != 1:
            value = value * (1 / regPara['factor'])

        self.logger.debug(
            f"write {value} to {objectType}.{address}.{address} (address.slaveUnit) dataType:{dataTypeStr}"
        )

        registers = None
        if objectType == 'Coil':
            if not isinstance(value, bool):
                self.logger.error(f"Value is not boolean: {value}")
                return
        elif objectType in ('HoldingRegister',):
            try:
                registers = self._value_to_registers(value, dataType, bits, bo, wo)
            except (TypeError, ValueError, ModbusException) as e:
                self.logger.error(f"cannot encode value for datatype={dataTypeStr}: {e}")
                return

        # IMPORTANT ASYNC TRANSITION: actual Modbus write is awaited, never blocking a SmartHomeNG thread
        try:
            async with self._client_lock:
                if objectType == 'Coil':
                    result = await asyncio.wait_for(
                        self._aclient.write_coil(address, value, **{_UNIT_KWARG: slaveUnit}),
                        timeout=self._write_timeout
                    )
                elif objectType == 'HoldingRegister':
                    result = await asyncio.wait_for(
                        self._aclient.write_registers(address, registers, **{_UNIT_KWARG: slaveUnit}),
                        timeout=self._write_timeout
                    )
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
            self._close_client()
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
            registerCount = max(1, (bits + 15) // 16)

        if not self.connected:
            # connection_keeper will reconnect; keep this silent-ish
            return None

        # IMPORTANT ASYNC TRANSITION: actual Modbus read is awaited
        try:
            async with self._client_lock:
                if objectType == 'Coil':
                    result = await self._aclient.read_coils(address, count=registerCount, **{_UNIT_KWARG: slaveUnit})
                elif objectType == 'DiscreteInput':
                    result = await self._aclient.read_discrete_inputs(address, count=registerCount, **{_UNIT_KWARG: slaveUnit})
                elif objectType == 'InputRegister':
                    result = await self._aclient.read_input_registers(address, count=registerCount, **{_UNIT_KWARG: slaveUnit})
                elif objectType == 'HoldingRegister':
                    result = await self._aclient.read_holding_registers(address, count=registerCount, **{_UNIT_KWARG: slaveUnit})
                else:
                    self.logger.error(f"{AttrObjectType} not supported: {objectType}")
                    return None
        except Exception as e:
            # Connection likely lost
            raise e

        if result is None or result.isError():
            self.error_count += 1
            self.log_error(
                f"read error: {result} {objectType}.{address}.{slaveUnit} (address.slaveUnit) regCount:{registerCount}"
            )
            return None

        # Decode
        if objectType == 'Coil' or objectType == 'DiscreteInput':
            return result.bits[0]

        self.logger.debug(
            f"read {objectType}.{address}.{slaveUnit} (address.slaveUnit) regCount:{registerCount} result:{result}"
        )

        try:
            return self._registers_to_value(result.registers, dataType, bits, bo, wo)
        except (TypeError, ValueError, ModbusException) as e:
            self.logger.error(
                f"unable to unpack data for datatype={dataType.lower()} for read "
                f"{objectType}.{address}.{slaveUnit} (address.slaveUnit) regCount:{registerCount}: {e}"
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

    @classmethod
    def _value_to_registers(cls, value, dataType: str, bits: int, byteOrder, wordOrder):
        data_type = dataType.lower()
        if data_type == 'string':
            return AsyncModbusTcpClient.convert_to_registers(
                cls._normalize_value_for_datatype(value, data_type),
                AsyncModbusTcpClient.DATATYPE.STRING,
                word_order='big',
                string_encoding='ASCII'
            )
        if data_type == 'bit':
            registers = cls._encode_register_bits(value, bits)
        else:
            modbus_type = cls._modbus_datatype(data_type, bits)
            if modbus_type is None:
                raise ValueError(f"Number of bits or datatype not supported: {dataType}{bits}")
            registers = AsyncModbusTcpClient.convert_to_registers(
                cls._normalize_value_for_datatype(value, data_type),
                modbus_type,
                word_order=cls._word_order_string(wordOrder),
                string_encoding='ASCII'
            )

        if cls._is_little_endian(byteOrder):
            registers = cls._swap_register_bytes(registers)
        return registers

    @classmethod
    def _registers_to_value(cls, registers, dataType: str, bits: int, byteOrder, wordOrder):
        data_type = dataType.lower()
        if data_type == 'string':
            value = AsyncModbusTcpClient.convert_from_registers(
                registers,
                AsyncModbusTcpClient.DATATYPE.STRING,
                word_order='big',
                string_encoding='ASCII'
            )
            return value.rstrip('\x00')

        if cls._is_little_endian(byteOrder):
            registers = cls._swap_register_bytes(registers)

        if data_type == 'bit':
            return cls._decode_register_bits(registers, bits)

        modbus_type = cls._modbus_datatype(data_type, bits)
        if modbus_type is None:
            raise ValueError(f"Number of bits or datatype not supported: {dataType}{bits}")

        value = AsyncModbusTcpClient.convert_from_registers(
            registers,
            modbus_type,
            word_order=cls._word_order_string(wordOrder),
            string_encoding='ASCII'
        )
        return value

    def _cycle_is_immediate(self) -> bool:
        return self._cycle_param is not None and self._cycle_param < 0

    def _incoming_data_enabled(self) -> bool:
        return self._crontab is not None or (self._cycle_param is not None and self._cycle_param != 0)

    def _write_data_enabled(self) -> bool:
        return bool(self._regToWrite)

    def _scheduler_name(self) -> str:
        return f"poll_device_{self.get_fullname()}"

    def _close_client(self):
        client = self._aclient
        self._aclient = None
        self.connected = False
        try:
            if client:
                client.close()
        except Exception:
            pass

    @staticmethod
    def _normalize_value_for_datatype(value, dataType: str):
        if dataType in ('uint', 'int'):
            return int(value)
        if dataType == 'float':
            return float(value)
        if dataType == 'string':
            return str(value)
        return value

    @staticmethod
    def _modbus_datatype(dataType: str, bits: int):
        if dataType == 'string':
            return getattr(AsyncModbusTcpClient.DATATYPE, 'STRING', None)

        datatype_name = {
            ('uint', 16): 'UINT16',
            ('uint', 32): 'UINT32',
            ('uint', 64): 'UINT64',
            ('int', 16): 'INT16',
            ('int', 32): 'INT32',
            ('int', 64): 'INT64',
            ('float', 32): 'FLOAT32',
            ('float', 64): 'FLOAT64',
        }.get((dataType, bits))
        return getattr(AsyncModbusTcpClient.DATATYPE, datatype_name, None) if datatype_name else None

    @staticmethod
    def _word_order_string(wordOrder) -> str:
        return 'little' if modbus_tcp._is_little_endian(wordOrder) else 'big'

    @staticmethod
    def _is_little_endian(order) -> bool:
        if getattr(order, 'name', '').upper() == 'LITTLE':
            return True
        if getattr(order, 'value', None) == '<':
            return True
        return str(order).split('.')[-1].upper() == 'LITTLE'

    @staticmethod
    def _swap_register_bytes(registers):
        return [((register & 0x00FF) << 8) | ((register & 0xFF00) >> 8) for register in registers]

    @staticmethod
    def _decode_register_bits(registers, bits: int):
        values = []
        for register in registers:
            for bit in range(15, -1, -1):
                values.append(bool(register & (1 << bit)))
        return values[:bits]

    @staticmethod
    def _encode_register_bits(value, bits: int):
        if isinstance(value, str):
            if not value or not set(value).issubset({'0', '1'}):
                raise ValueError(f"Value is not a bitstring: {value}")
            bit_values = [char == '1' for char in value]
        else:
            try:
                bit_values = [bool(bit) for bit in value]
            except TypeError as e:
                raise ValueError(f"Value is not a bitstring or bit list: {value}") from e

        bit_count = max(bits, len(bit_values))
        register_count = max(1, (bit_count + 15) // 16)
        padded_bits = bit_values + [False] * (register_count * 16 - len(bit_values))
        registers = []
        for offset in range(0, len(padded_bits), 16):
            register = 0
            for index, bit in enumerate(padded_bits[offset:offset + 16]):
                if bit:
                    register |= 1 << (15 - index)
            registers.append(register)
        return registers

    @staticmethod
    def makedictkey(objectType: str, regAddr, slaveUnit) -> str:
        # dictionary key: objectType.regAddr.slaveUnit // HoldingRegister.528.1
        return f"{str(objectType)}.{str(regAddr)}.{str(slaveUnit)}"
