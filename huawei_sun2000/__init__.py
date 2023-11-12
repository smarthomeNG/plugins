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


READITEM_CYCLE_DEFAULT = 0
READITEM_CYCLE_STARTUP = -1


class ReadItem:
    def __init__(self, register, cycle=READITEM_CYCLE_DEFAULT, initialized=False):
        self.register = register
        self.cycle = cycle
        self.initialized = initialized


class Huawei_Sun2000(SmartPlugin):
    PLUGIN_VERSION = '0.0.2'    # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release

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

        asyncio.run(self.validate_equipment())

        # On initialization error use:
        #   self._init_complete = False
        #   return

        self.init_webinterface(WebInterface)
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False
        return

    async def connect(self):
        try:
            client = await AsyncHuaweiSolar.create(self._host, self._port, self._slave)
        except Exception as e:
            self.logger.error(f"Error connecting {self._host}:{self._port}, slave_id {self._slave}: {e}.")
            return None
        if not client._client.connected:
            client.stop()
            return None
        return client

    async def read_from_inverter(self):
        client = await self.connect()
        if client is not None:
            try:
                for item in self._read_item_dictionary:
                    # check for cycle
                    cycle = self._read_item_dictionary[item].cycle
                    initialized = self._read_item_dictionary[item].initialized
                    if not initialized or cycle == READITEM_CYCLE_DEFAULT or cycle != READITEM_CYCLE_STARTUP or cycle < item.property.last_update_age:
                        # get register and set item
                        result = await client.get(self._read_item_dictionary[item].register, self._slave)
                        item(result.value, self.get_shortname())
                        self._read_item_dictionary[item].initialized = True
            except Exception as e:
                self.logger.error(f"Error reading register from {self._host}:{self._port}, slave_id {self._slave}: {e}.")

    async def write_to_inverter(self, register, value):
        client = await self.connect()
        if client is not None:
            try:
                await client.set(register, value, self._slave)
            except Exception as e:
                self.logger.error(f"Error writing register '{register}' to {self._host}:{self._port}, slave_id {self._slave}: {e}.")

    async def validate_equipment(self):
        client = await self.connect()
        if client is not None:
            try:
                for equipment_key in EquipmentDictionary:
                    result = await client.get(EquipmentDictionary[equipment_key].register, self._slave)
                    if EquipmentDictionary[equipment_key].true_comparator == ">":
                        if result.value > EquipmentDictionary[equipment_key].true_value:
                            EquipmentDictionary[equipment_key].status = True
                        else:
                            EquipmentDictionary[equipment_key].status = False
                    elif EquipmentDictionary[equipment_key].true_comparator == "<":
                        if result.value < EquipmentDictionary[equipment_key].true_value:
                            EquipmentDictionary[equipment_key].status = True
                        else:
                            EquipmentDictionary[equipment_key].status = False
                    else:
                        if result.value == EquipmentDictionary[equipment_key].true_value:
                            EquipmentDictionary[equipment_key].status = True
                        else:
                            EquipmentDictionary[equipment_key].status = False
            except Exception as e:
                self.logger.error(f"Error reading register from {self._host}:{self._port}, slave_id {self._slave}: {e}.")

    def check_equipment(self, item):
        if self.has_iattr(item.conf, 'equipment_part'):
            equipment_key = self.get_iattr_value(item.conf, 'equipment_part')
            if equipment_key in EquipmentDictionary:
                self.logger.debug(f"Equipment status for item '{item.property.path}': {EquipmentDictionary[equipment_key].status}.")
                return EquipmentDictionary[equipment_key].status
            else:
                self.logger.warning(f"Invalid key for equipment_part '{equipment_key}' configured.")
        return True

    def string_to_seconds_special(self, timestring):
        timestring = timestring.lower()
        if timestring == "startup":
            return READITEM_CYCLE_STARTUP
        if timestring.isnumeric():
            time_value = float(timestring)
            if time_value > 0:
                return time_value
            else:
                return 0
        time_len = len(timestring)
        if time_len > 1:
            time_format = timestring[-1:]
            time_value = float(timestring[:-1])
            match time_format:
                case "m":
                    time_value *= 60
                case "h":
                    time_value *= 60*60
                case "d":
                    time_value *= 60*60*24
                case "w":
                    time_value *= 60*60*24*7
            self.logger.debug(f"timestring: {timestring}, time_format: {time_format}, time_value: {time_value}")
            return time_value
        else:
            return 0

    def run(self):
        self.logger.debug("Run method called.")
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)
        self.alive = True

    def stop(self):
        self.logger.debug("Stop method called.")
        self.scheduler_remove('poll_device')
        self.alive = False

    def parse_item(self, item):
        # check for attribute 'sun2000_read'
        if self.has_iattr(item.conf, 'sun2000_read'):
            self.logger.debug(f"Parse read item: {item}.")
            register = self.get_iattr_value(item.conf, 'sun2000_read')
            if hasattr(rn, register):
                # check equipment
                if self.check_equipment(item):
                    self._read_item_dictionary.update({item: ReadItem(getattr(rn, register))})
                    # check for cycle_time
                    if self.has_iattr(item.conf, 'cycle_time'):
                        cycle = self.string_to_seconds_special(self.get_iattr_value(item.conf, 'cycle_time'))
                        self._read_item_dictionary[item].cycle = cycle
                        self.logger.debug(f"Item {item.property.path}, Zyklus {cycle}.")
                    self.logger.debug(f"Content of the dictionary _read_item_dictionary: '{self._read_item_dictionary}'")
                else:
                    self.logger.debug(f"Equipment check skipped item '{item.property.path}'.")
            else:
                self.logger.warning(f"Invalid key for '{read_attr}' '{register}' configured.")

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if self.alive and caller != self.get_shortname():
            # check for attribute 'sun2000_write'
            if self.has_iattr(item.conf, 'sun2000_write'):
                register = self.get_iattr_value(item.conf, 'sun2000_write')
                if hasattr(rn, register):
                    value = item()
                    asyncio.run(self.write_to_inverter(register, value))
                    self.logger.debug(f"Update_item was called with item {item.property.path} from caller {caller}, source {source} and dest {dest}.")
                else:
                    self.logger.warning(f"Invalid key for sun2000_write '{register}' configured.")

    def poll_device(self):
        if self.alive:
            asyncio.run(self.read_from_inverter())
