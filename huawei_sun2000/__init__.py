#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2023      Ronny Schulz                   ronny_schulz@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Inverter plugin for the Huawei SUN2000 to run with SmartHomeNG version
#  1.8 and upwards.
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

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface

import time
from huawei_solar import AsyncHuaweiSolar, register_names as rn
import asyncio


class EquipmentCheck:
    def __init__(self, register, true_value, true_comparator, status=False):
        self.register = register
        self.true_value = true_value
        self.true_comparator = true_comparator
        self.status = status


EquipmentDictionary = {
    "STORAGE": EquipmentCheck(rn.STORAGE_RATED_CAPACITY, 0, '>'),
    "STORAGE_UNIT_1": EquipmentCheck(rn.STORAGE_UNIT_1_NO, 0, '>'),
    "STORAGE_UNIT_1_BATTERY_PACK_1": EquipmentCheck(rn.STORAGE_UNIT_1_PACK_1_NO, 0, '>'),
    "STORAGE_UNIT_1_BATTERY_PACK_2": EquipmentCheck(rn.STORAGE_UNIT_1_PACK_2_NO, 0, '>'),
    "STORAGE_UNIT_1_BATTERY_PACK_3": EquipmentCheck(rn.STORAGE_UNIT_1_PACK_3_NO, 0, '>'),
    "STORAGE_UNIT_2": EquipmentCheck(rn.STORAGE_UNIT_2_NO, 0, '>'),
    "STORAGE_UNIT_2_BATTERY_PACK_1": EquipmentCheck(rn.STORAGE_UNIT_2_PACK_1_NO, 0, '>'),
    "STORAGE_UNIT_2_BATTERY_PACK_2": EquipmentCheck(rn.STORAGE_UNIT_2_PACK_2_NO, 0, '>'),
    "STORAGE_UNIT_2_BATTERY_PACK_3": EquipmentCheck(rn.STORAGE_UNIT_2_PACK_3_NO, 0, '>')
}


ITEM_CYCLE_DEFAULT = "default"
ITEM_CYCLE_STARTUP = "startup"
ITEM_SLAVE_DEFAULT = "default"

class ReadItem:
    def __init__(self, register, cycle=ITEM_CYCLE_DEFAULT, slave=ITEM_SLAVE_DEFAULT, equipment=None, initialized=False):
        self.register = register
        self.cycle = cycle
        self.slave = slave
        self.equipment = equipment
        self.initialized = initialized


class Huawei_Sun2000(SmartPlugin):
    PLUGIN_VERSION = '0.2.0'    # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release

    def __init__(self, sh):
        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # get parameters
        self._host = self.get_parameter_value('host')
        self._port = self.get_parameter_value('port')
        self._slave = self.get_parameter_value('slave')
        self._cycle = self.get_parameter_value('cycle')

        # global vars
        self._read_item_dictionary = {}
        self._write_buffer = []
        self._loop = asyncio.new_event_loop()
        self._client = None

        # On initialization error use:
        #   self._init_complete = False
        #   return

        self.init_webinterface(WebInterface)
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False
        return

    async def connect(self):
        if self._client is None:
            try:
                self.logger.debug(f"Connecting to {self._host}:{self._port}, slave_id {self._slave}")
                self._client = await AsyncHuaweiSolar.create(self._host, self._port, self._slave)
            except Exception as e:
                self.logger.error(f"Error connecting {self._host}:{self._port}, slave_id {self._slave}: {e}")
                return None
            self.logger.debug(f"Connected to {self._host}:{self._port}, slave_id {self._slave}")
        return self._client

    async def disconnect(self, client):
        await client.stop()
        self._client = None

    async def inverter_read(self, hold_connection=False):
        client = await self.connect()
        if client is not None:
            try:
                for item in self._read_item_dictionary:
                    if not self.alive:
                        break
                    # at first write buffer, if neccessary
                    await self.write_buffer(True)
                    # check for cycle
                    cycle = self._read_item_dictionary[item].cycle
                    equipment = self._read_item_dictionary[item].equipment
                    initialized = self._read_item_dictionary[item].initialized
                    if not initialized or cycle == ITEM_CYCLE_DEFAULT or cycle != ITEM_CYCLE_STARTUP or cycle < item.property.last_update_age:
                        if equipment is None or equipment.status:
                            # get register and set item
                            result = await client.get(getattr(rn, self._read_item_dictionary[item].register), self._read_item_dictionary[item].slave)
                            item(result.value, self.get_shortname())
                            self._read_item_dictionary[item].initialized = True
                        else:
                            self.logger.debug(f"Equipment check skipped item '{item.property.path}'")
            except Exception as e:
                self.logger.error(f"inverter_read: Error reading register '{self._read_item_dictionary[item].register}' from {self._host}:{self._port}, slave_id {self._read_item_dictionary[item].slave}: {e}")
            if not hold_connection:
                await self.disconnect(client)
        else:
            self.logger.error("inverter_read: Client not connected")

    async def inverter_write(self, register, value, slave, hold_connection=False):
        client = await self.connect()
        if client is not None:
            try:
                await client.set(getattr(rn, register), value, slave)
                self.logger.info(f"inverter_write: Register '{register}' to {self._host}:{self._port}, slave_id {slave} with value '{value}' written")
            except Exception as e:
                self.logger.error(f"inverter_write: Error writing register '{register}' to {self._host}:{self._port}, slave_id {slave}: {e}")
            if not hold_connection:
                await self.disconnect(client)
        else:
            self.logger.error("inverter_write: Client not connected")

    async def write_buffer(self, hold_connection=False):
        while len(self._write_buffer) > 0:
            first = self._write_buffer[0]
            register = first[0]
            value = first[1]
            slave = first[2]
            self._write_buffer.pop(0)
            self.inverter_write(register, value, slave, hold_connection)

    async def validate_equipment(self, hold_connection=False):
        client = await self.connect()
        if client is not None:
            try:
                for item in self._read_item_dictionary:
                    if not self.alive:
                        break
                    # at first write buffer, if neccessary
                    await self.write_buffer(True)
                    equipment = self._read_item_dictionary[item].equipment
                    if equipment is not None:
                        result = await client.get(equipment.register, self._read_item_dictionary[item].slave)
                        match equipment.true_comparator:
                            case ">":
                                if result.value > equipment.true_value:
                                    self._read_item_dictionary[item].equipment.status = True
                                else:
                                    self._read_item_dictionary[item].equipment.status = False
                            case "<":
                                if result.value < equipment.true_value:
                                    self._read_item_dictionary[item].equipment.status = True
                                else:
                                    self._read_item_dictionary[item].equipment.status = False
                            case _:
                                if result.value == equipment.true_value:
                                    self._read_item_dictionary[item].equipment.status = True
                                else:
                                    self._read_item_dictionary[item].equipment.status = False
            except Exception as e:
                self.logger.error(f"validate_equipment: Error reading register from {self._host}:{self._port}, slave_id {self._read_item_dictionary[item].slave}: {e}")
            if not hold_connection:
                await self.disconnect(client)
        else:
            self.logger.error("validate_equipment: Client not connected")

    def string_to_seconds_special(self, input_str):
        input_str = input_str.lower()
        if input_str == ITEM_CYCLE_STARTUP:
            return ITEM_CYCLE_STARTUP
        if input_str == ITEM_CYCLE_DEFAULT:
            return ITEM_CYCLE_DEFAULT
        if input_str.isnumeric():
            time_value = float(input_str)
            if time_value > 0:
                return time_value
            else:
                return ITEM_CYCLE_DEFAULT
        time_len = len(input_str)
        if time_len > 1:
            time_format = input_str[-1:]
            time_value = float(input_str[:-1])
            match time_format:
                case "m":
                    time_value *= 60
                case "h":
                    time_value *= 60*60
                case "d":
                    time_value *= 60*60*24
                case "w":
                    time_value *= 60*60*24*7
            if time_value > 0:
                return time_value
            else:
                return ITEM_CYCLE_DEFAULT
        else:
            return ITEM_CYCLE_DEFAULT

    def string_to_int_special(self, input_str, default_str, default_value):
        if input_str.lower() == default_str.lower():
            return default_value
        if input_str.isnumeric():
            return int(input_str)
        return default_value 

    def wait_running_loop(self):
        while self._loop.is_running():
            time.sleep(1)
        
    def run(self):
        self.logger.debug("Run method called")
        self.logger.debug(f"Content of the dictionary _read_item_dictionary: '{self._read_item_dictionary}'")
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)
        self.alive = True
        self._loop.run_until_complete(self.validate_equipment())

    def stop(self):
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_device')
        self.alive = False
        self.wait_running_loop()
        self._loop.close()

    def parse_item(self, item):
        # check for attribute 'sun2000_read'
        if self.has_iattr(item.conf, 'sun2000_read'):
            self.logger.debug(f"Parse sun2000_read item: {item}")
            register = self.get_iattr_value(item.conf, 'sun2000_read')
            if hasattr(rn, register):
                # check for slave id
                if self.has_iattr(item.conf, 'sun2000_slave'):
                    slave = self.string_to_int_special(self.get_iattr_value(item.conf, 'sun2000_slave'), ITEM_SLAVE_DEFAULT, self._slave)
                    self.logger.debug(f"Item {item.property.path}, slave {slave}")
                else:
                    slave = self._slave
                # check for sun2000_cycle
                if self.has_iattr(item.conf, 'sun2000_cycle'):
                    cycle = self.string_to_seconds_special(self.get_iattr_value(item.conf, 'sun2000_cycle'))
                    self.logger.debug(f"Item {item.property.path}, cycle {cycle}")
                else:
                    cycle = self._cycle
                # check equipment
                if self.has_iattr(item.conf, 'sun2000_equipment'):
                    equipment_key = self.get_iattr_value(item.conf, 'sun2000_equipment')
                    if equipment_key in EquipmentDictionary:
                        equipment = EquipmentDictionary[equipment_key]
                        self.logger.debug(f"Item {item.property.path}, equipment {equipment_key}")
                    else:
                        self.logger.warning(f"Invalid key for sun2000_equipment '{equipment_key}' configured")
                else:
                    equipment = None
                self._read_item_dictionary.update({item: ReadItem(register, cycle, slave, equipment)})
            else:
                self.logger.warning(f"Invalid key for 'sun2000_read' '{register}' configured")
        # check for attribute 'sun2000_write'
        if self.has_iattr(item.conf, 'sun2000_write'):
            self.logger.debug(f"Parse sun2000_write item: {item}")
            register = self.get_iattr_value(item.conf, 'sun2000_write')
            if hasattr(rn, register):
                return self.update_item
            else:
                self.logger.warning(f"Invalid key for 'sun2000_write' '{register}' configured")

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if self.alive and caller != self.get_shortname():
            # get attribute for 'sun2000_write'
            register = self.get_iattr_value(item.conf, 'sun2000_write')
            value = item()
            # check for slave id
            if self.has_iattr(item.conf, 'sun2000_slave'):
                slave = self.string_to_int_special(self.get_iattr_value(item.conf, 'sun2000_slave'), ITEM_SLAVE_DEFAULT, self._slave)
                self.logger.debug(f"Item {item.property.path}, slave {slave}")
            else:
                slave = self._slave
            self.logger.debug(f"Update_item was called with item {item.property.path} from caller {caller}, source {source} and dest {dest}")
            if not self._loop.is_running():
                # write directly
                self._loop.run_until_complete(self.inverter_write(register, value, slave))
                self.logger.info("Update was running in direct mode")
            else:
                # put to write buffer
                self._write_buffer.append([register, value, slave])
                self.logger.info("Update is running in buffered mode")

    def poll_device(self):
        if self.alive:
            # skip cylce if last poll is not finished yet
            if not self._loop.is_running():
                # read inverter registers
                self._loop.run_until_complete(self.inverter_read())
            else:
                self.logger.debug("Cycle poll skipped, because loop is not finished.")
