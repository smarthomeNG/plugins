#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2022 De Filippis Ivan
# Copyright 2022 Ronny Schulz
# Copyright 2023-2025 Bernd Meiners
#########################################################################
# This file is part of SmartHomeNG.
#
# Modbus plugin for SmartHomeNG
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

import asyncio
import logging
import struct
import threading
import time
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from pymodbus import ModbusException

from lib.model.smartplugin import SmartPlugin

from . import adapter, attributes, sunspec
from .codec import decode_available, default_registry, lookup_read, lookup_write, scale
from .model import Answer, Direction, Point, RegisterKey, RegisterSpec, Table, Value
from .planner import ReadBlock, plan, span
from .transport import UNIT_KWARG as _UNIT_KWARG
from .transport import from_parameters, new_client
from .webif import WebInterface


class Modbus(SmartPlugin):
    """
    Reads and writes Modbus devices over TCP, RTU over TCP or a serial RTU line.

    Each item with ``modBusAddress`` becomes a ``Point``: its ``RegisterSpec`` says where the value
    lives and how it is encoded, a codec from the registry converts registers and values.
    """

    PLUGIN_VERSION = '0.1.0'

    def __init__(self, sh, *args, **kwargs):
        """Read the plugin parameters; nothing connects before run()."""
        self.logger.info('Init modbus plugin')

        if not self.logger.isEnabledFor(logging.DEBUG):
            disable_logger = logging.getLogger('pymodbus')
            if disable_logger is not None:
                self.logger.info(f'change logging level from: {disable_logger} to CRITICAL')
                disable_logger.setLevel(logging.CRITICAL)

        super().__init__()

        self._sh = sh
        try:
            self._transport = from_parameters(self.get_parameter_value)
        except ValueError as e:
            self.logger.error(f'{e}; plugin not started')
            self._init_complete = False
            return

        self._cycle_param = self.get_parameter_value('cycle')
        self._cycle = self._cycle_param

        self._crontab = self.get_parameter_value('crontab')
        if self._crontab == '':
            self._crontab = None

        self._slaveUnit = self.get_parameter_value('slaveUnit')
        self._slaveUnitRegisterDependend = False

        self._pause_item_path = self.get_parameter_value('pause_item')
        self._invalidate_on_disconnect = bool(self.get_parameter_value('invalidate_on_disconnect'))
        self._pause_item = None

        try:
            self._adapter = adapter.create(self.get_parameter_value('adapter') or '')
        except ValueError as e:
            self.logger.error(f'{e}; plugin not started')
            self._init_complete = False
            return
        self._bus = _PluginBus(self)

        self._codecs = default_registry()
        # keyed by item: several items may decode the same register differently
        self._regToRead: dict[object, Point] = {}
        self._regToWrite: dict[object, Point] = {}
        self._pollStatus = {}
        self._poll_items = []
        self._sunspec: dict[object, sunspec.SunSpecItem] = {}
        self._sunspec_bound = 0
        self._sunspec_warned: set[tuple[object, str]] = set()
        self._scale_points: dict[RegisterKey, Point] = {}
        self._scales: dict[RegisterKey, int] = {}
        self._connections = 0
        # points the device rejected (illegal data address) on the current connection
        self._rejected: set[Point] = set()
        self.sunspec_listing: sunspec.DeviceListing | None = None

        # Threading lock for data shared between SmartHomeNG thread(s) and asyncio thread
        self.lock = threading.Lock()

        self._connection_task = None  # background reconnect/connection keeper
        self._reader_task = None  # continuous acquisition task
        self._scheduled_read_task = None  # scheduler-triggered one-shot read task
        self._write_tasks = set()  # currently pending/running async write tasks
        self._client_lock = None  # asyncio.Lock to serialize requests on one TCP connection
        self._read_cycle_lock = None  # asyncio.Lock to avoid overlapping full read passes

        self._aclient = None  # pymodbus async client (created in run()/async thread)

        self._connected = False
        self.error_count = 0

        self._read_inter_request_delay = 0.01
        self._read_idle_delay = 1.0
        self._shutdown_timeout = 5.0
        self._write_timeout = 10.0

        self.init_webinterface(WebInterface)

    # --- SmartHomeNG lifecycle ---

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

        self.start_asyncio(self.plugin_coro())

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
                self._scheduler_name(), self._trigger_async_read, cycle=scheduler_cycle, cron=self._crontab, prio=5
            )

        self.logger.debug(f"Plugin '{self.get_fullname()}': run method finished")

    def stop(self):
        """
        Stop plugin:
          - stop scheduler trigger
          - stop async tasks, close client, stop loop thread cleanly (SmartPlugin)
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method called")

        try:
            self.scheduler_remove(self._scheduler_name())
        except Exception:
            pass

        self.alive = False
        self.stop_asyncio()

        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method finished")

    # --- Item parsing / update ---

    def parse_item(self, item):
        """
        Bind the pause item, manual poll items and items with ``modBusAddress`` or ``modBusSunSpec``.

        Items with an unknown datatype are not bound. A write direction on a read-only table
        (inputs) is reduced to reading. SunSpec items get their register on each new connection.
        """
        if self._pause_item_path and item.property.path == self._pause_item_path:
            self.logger.debug(f'pause item {item.property.path} registered')
            self._pause_item = item
            self.add_item(item, updating=True)
            return self.update_item

        if self.has_iattr(item.conf, attributes.POLL) and self.get_iattr_value(item.conf, attributes.POLL):
            self._poll_items.append(item)
            return self.update_item

        def get(name):
            return self.get_iattr_value(item.conf, name) if self.has_iattr(item.conf, name) else None

        def warn(message):
            self.logger.warning(f'{item}: {message}')

        if self.has_iattr(item.conf, attributes.SUNSPEC):
            return self._parse_sunspec_item(item, get, warn)

        if not self.has_iattr(item.conf, attributes.ADDRESS):
            return None

        try:
            spec = attributes.parse_spec(get, self._slaveUnit, warn)
            codec = self._codecs.resolve(spec.datatype)
            if spec.bit is not None and not 0 <= spec.bit < 16 * codec.register_count(spec.datatype):
                raise ValueError(f'{attributes.BIT} {spec.bit} is outside {spec.datatype}')
        except (KeyError, ValueError) as e:
            self.logger.warning(f'{item}: ignored, {e}')
            return None

        if spec.direction.writes and not spec.key.table.writable:
            warn(f'{spec.key.table.value} cannot be written, reading only')
            spec = replace(spec, direction=Direction.READ)

        if spec.key.unit != self._slaveUnit:
            self._slaveUnitRegisterDependend = True

        point = Point(spec, item, item())
        self.logger.info(f'parse item: {item} {spec}')
        if spec.direction.reads:
            self._regToRead[item] = point
        if spec.direction.writes:
            self._regToWrite[item] = point
            return self.update_item
        return None

    def _parse_sunspec_item(self, item, get, warn):
        """Check an item's ``modBusSunSpec`` against the model definitions and keep it for binding."""
        text = str(get(attributes.SUNSPEC))
        try:
            ref = sunspec.PointRef.parse(text)
            definition = sunspec.default_catalog().point(ref)
            unit = attributes.parse_unit(get, self._slaveUnit)
        except ValueError as e:
            warn(f'ignored, modBusSunSpec {text}: {e}')
            return None
        if definition.datatype is None:
            warn(f'ignored, modBusSunSpec {ref}: SunSpec type {definition.type} is not supported')
            return None
        if get(attributes.ADDRESS) is not None:
            warn(f'modBusAddress ignored, modBusSunSpec {ref} is used')
        direction = attributes.parse_direction(get, warn)
        if direction.writes and not definition.writable:
            warn(f'modBusSunSpec {ref} is read-only, reading only')
            direction = Direction.READ
        self._sunspec[item] = sunspec.SunSpecItem(ref, unit, direction, get(attributes.INVALID_VALUE))
        self.logger.info(f'parse item: {item} SunSpec {ref} unit {unit}')
        return self.update_item if direction.writes else None

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated (write to device).
        Writes are scheduled onto the plugin's own asyncio loop (non-blocking).
        """
        # cores without _handle_pause_item (1.11) fall back to the inline handling below
        if item is self._pause_item:
            handler = getattr(super(), '_handle_pause_item', None)
            if handler is not None:
                handler(item, caller)
            elif caller != self.get_fullname():
                if item() and self.alive:
                    self.stop()
                elif not item() and not self.alive:
                    self.run()
            return

        if caller == self.get_fullname():
            return

        if not self.alive:
            return

        if any(item is poll_item for poll_item in self._poll_items):
            if item():
                self._trigger_async_read()
            return

        if item not in self._regToWrite and item not in self._sunspec:
            self.logger.debug(f'update_item: {item} is not written to the device')
            return

        self.logger.debug(f'update_item:{item} value:{item()}')
        try:
            self.run_asyncio_coro(self._schedule_write(item, item()), timeout=1)
        except Exception as e:
            self.logger.error(f'update_item: scheduling async write failed: {e}')

    # --- Logging helper ---

    @property
    def connected(self) -> bool:
        """Whether the client is connected to the device."""
        return self._connected

    @connected.setter
    def connected(self, value: bool) -> None:
        """Set the connection state; losing the connection while running opens database gaps."""
        lost = self._connected and not value
        self._connected = value
        if lost and self.alive and self._invalidate_on_disconnect:
            self.db_invalidate_items(list(self._regToRead), 'connection_lost')

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
                    self.logger.error(f'{message} [Logging suppressed every 10th error]')
            else:
                if self.error_count % 100 == 0:
                    self.logger.error(f'{message} [Logging suppressed every 100th error]')

    # --- Async start/stop + tasks (SmartPlugin asyncio) ---

    async def plugin_coro(self):
        """
        Coroutine for the asyncio session that communicates with the Modbus device.
        It will only terminate when the plugin is stopped.
        """
        self.logger.info('plugin_coro started')

        self._client_lock = asyncio.Lock()
        self._read_cycle_lock = asyncio.Lock()
        self._bind_lock = asyncio.Lock()

        self._aclient = self._new_client()
        self.connected = False
        self.error_count = 0

        incoming_enabled = self._incoming_data_enabled()
        write_enabled = self._write_data_enabled()

        if not incoming_enabled and (self._regToRead or self._sunspec):
            self.logger.warning(
                f'{self.get_fullname()}: cycle is 0 and no crontab is configured; '
                f'{len(self._regToRead)} read item(s) will keep init/cache/database values'
            )

        if incoming_enabled or write_enabled:
            self._connection_task = asyncio.create_task(self._connection_keeper(), name='connection_keeper')
        else:
            self.logger.info(
                f'{self.get_fullname()}: no incoming data processing and no write items; '
                f'not opening a Modbus connection'
            )

        # positive cycle/crontab reads are triggered by the SmartHomeNG scheduler instead
        if self._cycle_is_immediate():
            self._reader_task = asyncio.create_task(self._acquisition_loop(), name='acquisition_loop')
        else:
            self.logger.info(f'{self.get_fullname()}: no continuous incoming data processing')

        self.alive = True
        self.logger.info('plugin_coro: Plugin is running (self.alive=True)')

        await self.wait_for_asyncio_termination()
        self.alive = False

        self._close_client()

        tasks_to_cancel = [
            task
            for task in [self._reader_task, self._scheduled_read_task, self._connection_task, *self._write_tasks]
            if task and not task.done()
        ]
        for task in tasks_to_cancel:
            task.cancel()
        if tasks_to_cancel:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_cancel, return_exceptions=True), timeout=self._shutdown_timeout
                )
            except asyncio.TimeoutError:
                self.logger.warning(f'Timeout while stopping Modbus async tasks after {self._shutdown_timeout} seconds')

        self._close_client()

        self._reader_task = None
        self._scheduled_read_task = None
        self._connection_task = None
        self._write_tasks.clear()
        self._read_cycle_lock = None

        self.alive = False
        self.logger.info('plugin_coro: Plugin is stopped (self.alive=False)')

        self.logger.info('plugin_coro finished')
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
                    self._aclient = self._new_client()
                    self.connected = False

                pm_connected = getattr(self._aclient, 'connected', None)
                if pm_connected is False:
                    self.connected = False

                if not self.connected:
                    try:
                        ok = await self._aclient.connect()
                    except Exception as e:
                        ok = False
                        self.error_count += 1
                        self.log_error(f'connection exception: {self._transport} {e}, errors: {self.error_count}')

                    if ok:
                        self._connections += 1
                        self._rejected.clear()
                        self.connected = True
                        self.error_count = 0
                        backoff = 1.0
                        self.logger.info(f'connected to {self._transport}')
                    else:
                        self.connected = False
                        self.error_count += 1
                        self.log_error(
                            f'could not connect to {self._transport}, connection_attempts: {self.error_count}'
                        )
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2.0, 30.0)
                        continue

                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f'connection_keeper unexpected error: {e}')
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
                self.logger.error(f'acquisition_loop unexpected error: {e}')
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
            self.logger.debug('read cycle already running, skipping overlapping trigger')
            return 0

        async with self._read_cycle_lock:
            startTime = datetime.now()
            regCount = 0

            if not await self._ensure_sunspec_bound():
                return 0

            with self.lock:
                points = [*self._regToRead.values(), *self._scale_points.values()]
            points = [point for point in points if point not in self._rejected]

            if not points:
                return None

            raws: list[tuple[Point, list[int] | list[bool]]] = []
            for block in plan(points, self._codecs):
                if not self.alive:
                    break

                try:
                    raws.extend(await self._read_block(block))
                except Exception as e:
                    self._reraise_if_cancelled(e)
                    if not self.alive:
                        self.logger.debug(f'read cancelled while stopping: {e}')
                        break
                    kind = (
                        'ModbusException raised while reading' if isinstance(e, ModbusException) else 'read exception'
                    )
                    self.logger.error(f'{kind}: {e}')
                    self._close_client()

                await asyncio.sleep(self._read_inter_request_delay)

            # scale factors first: the points they scale may come earlier in the pass
            raws.sort(key=lambda pair: pair[0].item is not None)
            for point, raw in raws:
                if point.item is None:
                    self._store_scale(point, raw)
                    continue
                value = self._decode(point, raw)
                if value is None:
                    continue
                try:
                    point.item(value, self.get_fullname())
                except Exception as e:
                    self.logger.error(f'item write failed for {point.spec.key}: {e}')
                with self.lock:
                    point.record_read(value, datetime.now())
                regCount += 1

            duration = datetime.now() - startTime
            if regCount > 0:
                with self.lock:
                    self._pollStatus['last_dt'] = datetime.now()
                    self._pollStatus['regCount'] = regCount
            self.logger.debug(f'read cycle: read {regCount} register(s) in {duration} seconds')
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
            self.logger.error(f'trigger_async_read: scheduling read failed: {e}')

    async def _schedule_triggered_read(self):
        if self._scheduled_read_task is not None and not self._scheduled_read_task.done():
            self.logger.debug('triggered read already running')
            return False
        self._scheduled_read_task = asyncio.create_task(self._read_registers_once(), name='triggered_read')
        self._scheduled_read_task.add_done_callback(self._log_read_task_result)
        return True

    def _log_read_task_result(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f'read task failed: {e}')

    # --- Async Modbus IO (read/write) ---

    async def _schedule_write(self, item, value: Value):
        """
        Schedule a Modbus write without blocking the caller.
        """
        task = asyncio.create_task(self._write_item(item, value))
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
            self.logger.error(f'write task failed: {e}')

    async def _write_item(self, item, value: Value) -> None:
        """Write an item's value to its point; SunSpec items are bound first if the connection is new."""
        if item in self._sunspec:
            if not await self._wait_connected(timeout=self._write_timeout):
                self.log_error(f'write skipped (not connected after {self._write_timeout} seconds): {self._transport}')
                return
            if not await self._ensure_sunspec_bound():
                return
        point = self._regToWrite.get(item)
        if point is not None:
            await self._write_point(point, value)

    async def _write_point(self, point: Point, value: Value) -> None:
        """
        Write ``value`` (item units) to the device: the adapter writes it or prepares the write; else
        map through the lookup, divide by factor, encode, send.

        Waits up to ``_write_timeout`` for a connection; validation and transfer errors are
        logged, never raised.
        """
        spec = point.spec
        key = spec.key

        if not await self._wait_connected(timeout=self._write_timeout):
            self.log_error(f'write skipped (not connected after {self._write_timeout} seconds): {self._transport}')
            return

        try:
            if await self._adapter.write(self._bus, spec, value):
                with self.lock:
                    point.record_write(value, datetime.now())
                return
            value = lookup_write(spec, value)
        except ValueError as e:
            self.logger.error(f'write skipped: {e}')
            return
        if spec.bit is not None:
            self.logger.error(f'write skipped: single bits of {key} cannot be written')
            return
        if spec.factor == 0:
            self.logger.error('cannot write register with factor zero')
            return
        if spec.scale_ref is not None and spec.scale_ref not in self._scales:
            await self._read_scale(spec.scale_ref)
        if spec.scale_ref is not None and spec.scale_ref not in self._scales:
            self.logger.error(f'write skipped: scale factor of {key} not available')
            return
        try:
            if spec.factor != 1:
                value = value / spec.factor
            if spec.scale_ref is not None:
                value = scale(value, -self._scales[spec.scale_ref])
        except (TypeError, ValueError, OverflowError) as e:
            self.logger.error(f'cannot scale write value: {e}')
            return

        self.logger.debug(f'write {value} to {key} dataType:{spec.datatype}')

        registers = None
        if key.table is Table.COIL:
            if not isinstance(value, bool):
                self.logger.error(f'Value is not boolean: {value}')
                return
        else:
            try:
                registers = self._codecs.resolve(spec.datatype).encode(value, spec)
            except (TypeError, ValueError, OverflowError, struct.error, ModbusException) as e:
                self.logger.error(f'cannot encode value for datatype={spec.datatype}: {e}')
                return

        if await self._send(key.table, key.unit, key.address, value if registers is None else registers):
            with self.lock:
                point.record_write(value, datetime.now())

    async def _send(self, table: Table, unit: int, address: int, payload: Value | Sequence[int]) -> bool:
        """
        Write a coil (``payload`` bool) or holding registers from ``address`` on.

        :returns: False if not connected or the write failed (logged; transport errors close the client)
        """
        if not self.connected:
            return False
        key = RegisterKey(unit, table, address)
        try:
            async with self._client_lock:
                if table is Table.COIL:
                    request = self._aclient.write_coil(address, payload, **{_UNIT_KWARG: unit})
                else:
                    request = self._aclient.write_registers(address, list(payload), **{_UNIT_KWARG: unit})
                result = await self._await_request(request, timeout=self._write_timeout)
        except Exception as e:
            self._reraise_if_cancelled(e)
            self.logger.error(f'write exception: {e}')
            self._close_client()
            return False

        if result is None or result.isError():
            self.logger.error(f'write error: {result} {key} (table.address.unit)')
            return False
        return True

    async def _read_scale(self, key: RegisterKey) -> None:
        """Read one scale factor register into ``_scales``; dropped if unreadable or "not available"."""
        point = self._scale_points.get(key) or Point(RegisterSpec(key, datatype='int16'), item=None)
        raw = await self._request(key.table, key.unit, key.address, span(point, self._codecs))
        self._store_scale(point, [] if raw is None else raw)

    def _store_scale(self, point: Point, raw: list[int] | list[bool]) -> None:
        """Keep the exponent a scale factor register holds; forget it if unreadable or "not available"."""
        value = self._decode(point, raw) if raw else None
        if value is None:
            self._scales.pop(point.spec.key, None)
        else:
            self._scales[point.spec.key] = int(value)

    async def _ensure_sunspec_bound(self) -> bool:
        """
        Bind SunSpec items to this connection's registers, once per connection.

        :returns: False if the connection failed while binding
        """
        if not self._sunspec or self._sunspec_bound == self._connections:
            return True
        async with self._bind_lock:
            if self._sunspec_bound == self._connections:
                return True
            try:
                await self._bind_sunspec()
            except Exception as e:
                self._reraise_if_cancelled(e)
                self.logger.error(f'SunSpec scan failed: {e}')
                self._close_client()
                return False
            self._sunspec_bound = self._connections
            return True

    async def _bind_sunspec(self) -> None:
        """
        Scan each unit with SunSpec items and replace their points by the ones found on the device.

        Items whose point is not on the device are warned about once and stay unbound.
        """
        units: dict[int, dict[object, sunspec.SunSpecItem]] = {}
        for item, binding in self._sunspec.items():
            units.setdefault(binding.unit, {})[item] = binding

        points: dict[object, Point] = {}
        scale_points: dict[RegisterKey, Point] = {}
        for unit, bindings in units.items():
            try:
                found, missing = await sunspec.resolve(
                    self._sunspec_reader(unit), {b.ref for b in bindings.values()}, sunspec.default_catalog()
                )
            except sunspec.SunSpecError as e:
                self._warn_once(f'unit {unit}', f'SunSpec unit {unit}: {e}')
                continue
            for item, binding in bindings.items():
                if binding.ref in missing:
                    self._warn_once(
                        item, f'{item}: modBusSunSpec {binding.ref} not on the device ({missing[binding.ref]})'
                    )
                    continue
                point, scale_ref = self._sunspec_point(item, binding, found[binding.ref])
                points[item] = point
                if scale_ref is not None:
                    scale_points[scale_ref] = Point(RegisterSpec(scale_ref, datatype='int16'), item=None)

        with self.lock:
            for item in self._sunspec:
                self._regToRead.pop(item, None)
                self._regToWrite.pop(item, None)
            for item, point in points.items():
                if point.spec.direction.reads:
                    self._regToRead[item] = point
                if point.spec.direction.writes:
                    self._regToWrite[item] = point
            self._scale_points = scale_points
        self.logger.info(f'SunSpec: {len(points)} of {len(self._sunspec)} item(s) bound')

    def _sunspec_reader(self, unit: int) -> sunspec.Reader:
        """Holding register reader for SunSpec scans of ``unit``; error answers are expected there and not counted."""

        async def read(address: int, count: int) -> list[int] | None:
            raw = await self._request(Table.HOLDING_REGISTER, unit, address, count, quiet=True)
            return None if raw is None else [int(word) for word in raw]

        return read

    async def scan_sunspec(self, unit: int) -> sunspec.DeviceListing:
        """List the SunSpec models and points of ``unit`` for the web interface; kept as ``sunspec_listing``."""
        if not self.connected:
            listing = sunspec.DeviceListing(unit, datetime.now(), error=f'not connected to {self._transport}')
        else:
            try:
                models = await sunspec.list_device(self._sunspec_reader(unit), sunspec.default_catalog(), self._codecs)
                listing = sunspec.DeviceListing(unit, datetime.now(), tuple(models))
            except sunspec.SunSpecError as e:
                listing = sunspec.DeviceListing(unit, datetime.now(), error=str(e))
        self.sunspec_listing = listing
        return listing

    @staticmethod
    def _sunspec_point(item, binding: sunspec.SunSpecItem, found: sunspec.Resolved) -> tuple[Point, RegisterKey | None]:
        """Point of a SunSpec item at its address on the device, and the key of its scale factor register."""
        unit = binding.unit
        scale_ref = None if found.sf_address is None else RegisterKey(unit, Table.HOLDING_REGISTER, found.sf_address)
        spec = RegisterSpec(
            RegisterKey(unit, Table.HOLDING_REGISTER, found.address),
            datatype=found.point.datatype or 'uint16',
            factor=1.0 if found.sf_constant is None else float(10**found.sf_constant),
            direction=binding.direction,
            invalid_value=binding.invalid_value,
            scale_ref=scale_ref,
        )
        return Point(spec, item, item()), scale_ref

    def _warn_once(self, subject: object, message: str) -> None:
        """Log ``message`` as warning unless it was logged for ``subject`` before."""
        if (subject, message) not in self._sunspec_warned:
            self._sunspec_warned.add((subject, message))
            self.logger.warning(message)

    async def _read_block(self, block: ReadBlock) -> list[tuple[Point, list[int] | list[bool]]]:
        """
        Read ``block`` with one request; the registers (or bits) of each point that could be read.

        If the device answers a block of several points with an error, its points are read one
        by one, so a single unreadable register doesn't hide the others. Points the device rejects
        (illegal data address) are not read again until the next connection. Transport exceptions
        propagate; the caller closes the connection.
        """
        answer = await self._answer(block.table, block.unit, block.start, block.count, quiet_rejected=True)
        raw = answer.values
        if raw is None:
            if len(block.points) == 1:
                if answer.rejected:
                    self._reject(block.points[0])
                return []
            if not self.connected:
                return []
            results = []
            for point in block.points:
                key = point.spec.key
                single = await self._answer(
                    key.table, key.unit, key.address, span(point, self._codecs), quiet_rejected=True
                )
                if single.rejected:
                    self._reject(point)
                elif single.values is not None:
                    results.append((point, single.values))
            return results
        results = []
        for point in block.points:
            offset = point.spec.key.address - block.start
            results.append((point, raw[offset : offset + span(point, self._codecs)]))
        return results

    def _reject(self, point: Point) -> None:
        """Leave ``point`` out of the reads until the next connection."""
        self._rejected.add(point)
        self.logger.warning(
            f'{point.item if point.item is not None else point.spec.key}: device answers illegal data address '
            f'for {point.spec.key}, not read until the next connection'
        )

    async def _request(
        self, table: Table, unit: int, address: int, count: int, quiet: bool = False
    ) -> list[int] | list[bool] | None:
        """
        Registers (or bits) ``address`` .. ``address + count - 1``; None when not connected or on
        an error response (logged and counted unless ``quiet``).
        """
        return (await self._answer(table, unit, address, count, quiet)).values

    async def _answer(
        self, table: Table, unit: int, address: int, count: int, quiet: bool = False, quiet_rejected: bool = False
    ) -> Answer:
        """
        Read registers (or bits) ``address`` .. ``address + count - 1``.

        Error responses are logged and counted unless ``quiet``; with ``quiet_rejected`` an illegal
        data address answer is left to the caller.
        """
        if not self.connected:
            return Answer(None)
        kwargs = {_UNIT_KWARG: unit}
        async with self._client_lock:
            if table is Table.COIL:
                result = await self._aclient.read_coils(address, count=count, **kwargs)
            elif table is Table.DISCRETE_INPUT:
                result = await self._aclient.read_discrete_inputs(address, count=count, **kwargs)
            elif table is Table.INPUT_REGISTER:
                result = await self._aclient.read_input_registers(address, count=count, **kwargs)
            else:
                result = await self._aclient.read_holding_registers(address, count=count, **kwargs)

        if result is None or result.isError():
            answer = Answer(None, getattr(result, 'exception_code', None))
            if quiet or (quiet_rejected and answer.rejected):
                self.logger.debug(f'no answer at {table.value}.{address}.{unit} (table.address.unit): {result}')
                return answer
            self.error_count += 1
            self.log_error(f'read error: {result} {table.value}.{address}.{unit} (table.address.unit) regCount:{count}')
            return answer
        self.logger.debug(f'read {table.value}.{address}.{unit} (table.address.unit) regCount:{count} result:{result}')
        return Answer(list(result.bits[:count]) if table.bit_sized else list(result.registers))

    def _decode(self, point: Point, raw: list[int] | list[bool]) -> Value | None:
        """
        Item value from the point's registers: decode, replace "not available" values, apply factor,
        scale and rounding (or take the bit of ``spec.bit``), then ``spec.lookup``.

        Rounded values of str items are text with exactly ``spec.decimals`` decimals (``'2.10'``).

        Bit tables give the bit itself, through ``spec.lookup``. "Not available" values (codec sentinels and ``spec.invalid``)
        give ``spec.invalid_value`` unscaled; None for undecodable values and when it is unset.
        """
        spec = point.spec
        if spec.key.table.bit_sized:
            return lookup_read(spec, bool(raw[0]))
        try:
            value = decode_available(self._codecs, spec, raw)
        except (TypeError, ValueError, ModbusException) as e:
            self.logger.error(f'unable to unpack data for datatype={spec.datatype} for read {spec.key}: {e}')
            return None
        if value is None:
            return spec.invalid_value
        if spec.bit is not None:
            return lookup_read(spec, bool(int(value) >> spec.bit & 1))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if spec.factor != 1:
                value *= spec.factor
            if spec.scale_ref is not None:
                if spec.scale_ref not in self._scales:
                    return None
                value = scale(value, self._scales[spec.scale_ref])
            if spec.decimals is not None:
                value = round(value, spec.decimals) if spec.decimals > 0 else round(value)
                if point.item.type() == 'str':
                    value = f'{value:.{spec.decimals}f}'
        return lookup_read(spec, value)

    # --- Helpers ---

    @staticmethod
    async def _await_request(request, timeout):
        """
        Await a pymodbus request with a timeout.

        Before Python 3.12 ``asyncio.wait_for`` runs the request in an inner task. When the awaiting task is
        cancelled, pymodbus ends that task with a ModbusIOException; it is retrieved here so asyncio does not
        log it as 'Task exception was never retrieved'.
        """
        task = asyncio.ensure_future(request)
        try:
            return await asyncio.wait_for(task, timeout)
        finally:
            if task.done() and not task.cancelled():
                task.exception()

    @staticmethod
    def _reraise_if_cancelled(exc: Exception) -> None:
        """
        Raise CancelledError if exc is the result of cancelling the running task.

        pymodbus converts a CancelledError raised during a request into a ModbusIOException
        chained to it; handlers that log and continue would otherwise swallow the cancellation.
        Task.cancelling() (Python >= 3.11) covers any other exception raised after cancel().
        """
        cancelling = getattr(asyncio.current_task(), 'cancelling', None)
        if isinstance(exc.__cause__, asyncio.CancelledError) or (cancelling is not None and cancelling()):
            raise asyncio.CancelledError from exc

    def _cycle_is_immediate(self) -> bool:
        return self._cycle_param is not None and self._cycle_param < 0

    def _incoming_data_enabled(self) -> bool:
        return (
            bool(self._poll_items)
            or self._crontab is not None
            or (self._cycle_param is not None and self._cycle_param != 0)
        )

    def _write_data_enabled(self) -> bool:
        return bool(self._regToWrite) or any(binding.direction.writes for binding in self._sunspec.values())

    def _scheduler_name(self) -> str:
        return f'poll_device_{self.get_fullname()}'

    def _new_client(self):
        """
        Create the pymodbus client. Its built-in auto-reconnect is disabled because `_connection_keeper` is the
        only reconnect loop; two loops connecting concurrently leave an orphaned socket open on the device.
        """
        return new_client(self._transport)

    def _close_client(self):
        client = self._aclient
        self._aclient = None
        self.connected = False
        try:
            if client:
                client.close()
        except Exception:
            pass


class _PluginBus:
    """``adapter.Bus`` over a plugin's connection."""

    def __init__(self, plugin: Modbus) -> None:
        self._plugin = plugin

    async def read(self, unit: int, table: Table, address: int, count: int) -> list[int] | list[bool] | None:
        """Registers (or bits) from ``address`` on; None if not connected or on an error answer."""
        return await self._plugin._request(table, unit, address, count)

    async def write(self, unit: int, table: Table, address: int, registers: Sequence[int]) -> bool:
        """Write holding registers from ``address`` on; False if not connected or the write failed."""
        return await self._plugin._send(table, unit, address, registers)
