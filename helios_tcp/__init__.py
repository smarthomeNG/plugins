#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020 Thilo Schneider                   freget@googlemail.com
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
#  upwards.
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

import logging
from lib.model.smartplugin import SmartPlugin

from pymodbus3.client.sync import ModbusTcpClient

VARLIST = {
    "outside_temp"              : {"var": "v00104", "length": 8, "type": float, "read": True, "write": False},
    "exhaust_temp"              : {"var": "v00107", "length": 8, "type": float, "read": True, "write": False},
    "inside_temp"               : {"var": "v00106", "length": 8, "type": float, "read": True, "write": False},
    "incoming_temp"             : {"var": "v00105", "length": 8, "type": float, "read": True, "write": False},
    "pre_heating_temp"          : {"var": "v00108", "length": 8, "type": float, "read": True, "write": False},
    "post_heating_temp"         : {"var": "v00146", "length": 8, "type": float, "read": True, "write": False},
    "post_heating_reflux_temp"  : {"var": "v00110", "length": 8, "type": float, "read": True, "write": False},
    "error_count"               : {"var": "v01300", "length": 5, "type": int,   "read": True, "write": False},
    "warning_count"             : {"var": "v01301", "length": 5, "type": int,   "read": True, "write": False},
    "info_count"                : {"var": "v01302", "length": 5, "type": int,   "read": True, "write": False},
    "fan_in_rpm"                : {"var": "v00348", "length": 6, "type": int,   "read": True, "write": False},
    "fan_out_rpm"               : {"var": "v00349", "length": 6, "type": int,   "read": True, "write": False},
    "internal_humidity"         : {"var": "v02136", "length": 6, "type": int,   "read": True, "write": False},
    "sensor1_humidity"          : {"var": "v00111", "length": 6, "type": int,   "read": True, "write": False},
    "sensor2_humidity"          : {"var": "v00112", "length": 6, "type": int,   "read": True, "write": False},
    "sensor3_humidity"          : {"var": "v00113", "length": 6, "type": int,   "read": True, "write": False},
    "sensor4_humidity"          : {"var": "v00114", "length": 6, "type": int,   "read": True, "write": False},
    "sensor5_humidity"          : {"var": "v00115", "length": 6, "type": int,   "read": True, "write": False},
    "sensor6_humidity"          : {"var": "v00116", "length": 6, "type": int,   "read": True, "write": False},
    "sensor7_humidity"          : {"var": "v00117", "length": 6, "type": int,   "read": True, "write": False},
    "sensor8_humidity"          : {"var": "v00118", "length": 6, "type": int,   "read": True, "write": False},
    "sensor1_temperature"       : {"var": "v00119", "length": 8, "type": float, "read": True, "write": False},
    "sensor2_temperature"       : {"var": "v00120", "length": 8, "type": float, "read": True, "write": False},
    "sensor3_temperature"       : {"var": "v00121", "length": 8, "type": float, "read": True, "write": False},
    "sensor4_temperature"       : {"var": "v00122", "length": 8, "type": float, "read": True, "write": False},
    "sensor5_temperature"       : {"var": "v00123", "length": 8, "type": float, "read": True, "write": False},
    "sensor6_temperature"       : {"var": "v00124", "length": 8, "type": float, "read": True, "write": False},
    "sensor7_temperature"       : {"var": "v00125", "length": 8, "type": float, "read": True, "write": False},
    "sensor8_temperature"       : {"var": "v00126", "length": 8, "type": float, "read": True, "write": False},
    "sensor1_co2"               : {"var": "v00128", "length": 6, "type": float, "read": True, "write": False},
    "sensor2_co2"               : {"var": "v00129", "length": 6, "type": float, "read": True, "write": False},
    "sensor3_co2"               : {"var": "v00130", "length": 6, "type": float, "read": True, "write": False},
    "sensor4_co2"               : {"var": "v00131", "length": 6, "type": float, "read": True, "write": False},
    "sensor5_co2"               : {"var": "v00132", "length": 6, "type": float, "read": True, "write": False},
    "sensor6_co2"               : {"var": "v00133", "length": 6, "type": float, "read": True, "write": False},
    "sensor7_co2"               : {"var": "v00134", "length": 6, "type": float, "read": True, "write": False},
    "sensor8_co2"               : {"var": "v00135", "length": 6, "type": float, "read": True, "write": False},
    "sensor1_voc"               : {"var": "v00136", "length": 6, "type": float, "read": True, "write": False},
    "sensor2_voc"               : {"var": "v00137", "length": 6, "type": float, "read": True, "write": False},
    "sensor3_voc"               : {"var": "v00138", "length": 6, "type": float, "read": True, "write": False},
    "sensor4_voc"               : {"var": "v00139", "length": 6, "type": float, "read": True, "write": False},
    "sensor5_voc"               : {"var": "v00140", "length": 6, "type": float, "read": True, "write": False},
    "sensor6_voc"               : {"var": "v00141", "length": 6, "type": float, "read": True, "write": False},
    "sensor7_voc"               : {"var": "v00142", "length": 6, "type": float, "read": True, "write": False},
    "sensor8_voc"               : {"var": "v00143", "length": 6, "type": float, "read": True, "write": False},
    "filter_remaining"          : {"var": "v01033", "length": 9, "type": int,   "read": True, "write": False},
    "boost_remaining"           : {"var": "v00093", "length": 6, "type": int,   "read": True, "write": False},
    "sleep_remaining"           : {"var": "v00098", "length": 6, "type": int,   "read": True, "write": False},
    "fan_level_percent"         : {"var": "v00103", "length": 6, "type": int,   "read": True, "write": False},
    "bypass_open"               : {"var": "v02119", "length": 5, "type": bool,  "read": True, "write": False},
    "humidity_control_status"   : {"var": "v00033", "length": 5, "type": int,   "read": True, "write": True, "min": 0, "max": 2},
    "humidity_control_target"   : {"var": "v00034", "length": 5, "type": int,   "read": True, "write": True, "min": 20, "max": 80},
    "co2_control_status"        : {"var": "v00037", "length": 5, "type": int,   "read": True, "write": True, "min": 0, "max": 2},
    "co2_control_target"        : {"var": "v00038", "length": 6, "type": int,   "read": True, "write": True, "min": 300, "max": 2000},
    "voc_control_status"        : {"var": "v00037", "length": 5, "type": int,   "read": True, "write": True, "min": 0, "max": 2},
    "voc_control_target"        : {"var": "v00038", "length": 6, "type": int,   "read": True, "write": True, "min": 300, "max": 2000},
    "comfort_temperature"       : {"var": "v00037", "length": 6, "type": float, "read": True, "write": True, "min": 10, "max": 25},
    "fan_in_voltage_level1"     : {"var": "v00013", "length": 6, "type": float, "read": True, "write": True, "min": 1.6, "max": 10},
    "fan_out_voltage_level1"    : {"var": "v00012", "length": 6, "type": float, "read": True, "write": True, "min": 1.6, "max": 10},
    "fan_in_voltage_level2"     : {"var": "v00015", "length": 6, "type": float, "read": True, "write": True, "min": 1.6, "max": 10},
    "fan_out_voltage_level2"    : {"var": "v00014", "length": 6, "type": float, "read": True, "write": True, "min": 1.6, "max": 10},
    "fan_in_voltage_level3"     : {"var": "v00017", "length": 6, "type": float, "read": True, "write": True, "min": 1.6, "max": 10},
    "fan_out_voltage_level3"    : {"var": "v00016", "length": 6, "type": float, "read": True, "write": True, "min": 1.6, "max": 10},
    "fan_in_voltage_level4"     : {"var": "v00019", "length": 6, "type": float, "read": True, "write": True, "min": 1.6, "max": 10},
    "fan_out_voltage_level4"    : {"var": "v00018", "length": 6, "type": float, "read": True, "write": True, "min": 1.6, "max": 10},
    "manual_mode"               : {"var": "v00101", "length": 5, "type": int,   "read": True, "write": True, "min": 0, "max": 1},
    "filter_change"             : {"var": "v01031", "length": 5, "type": bool,  "read": True, "write": True, "min": 0, "max": 1},
    "filter_changeinterval"     : {"var": "v01032", "length": 5, "type": int,   "read": True, "write": True, "min": 0, "max": 12},
    "bypass_roomtemperature"    : {"var": "v01035", "length": 5, "type": int,   "read": True, "write": True, "min": 10, "max": 40},
    "bypass_minoutsidetemp"     : {"var": "v01036", "length": 5, "type": int,   "read": True, "write": True, "min": 5, "max": 20},
    "fan_level"                 : {"var": "v00102", "length": 5, "type": int,   "read": True, "write": True, "min": 0, "max": 4},
    "fan_in_level"              : {"var": "v01050", "length": 5, "type": int,   "read": True, "write": True, "min": 0, "max": 4},
    "fan_out_level"             : {"var": "v01051", "length": 5, "type": int,   "read": True, "write": True, "min": 0, "max": 4},
    "boost_duration"            : {"var": "v00091", "length": 6, "type": int,   "read": True, "write": True, "min": 5, "max": 180},
    "boost_level"               : {"var": "v00092", "length": 5, "type": int,   "read": True, "write": True, "min": 0, "max": 4},
    "boost_on"                  : {"var": "v00094", "length": 5, "type": bool,  "read": True, "write": True, "min": 0, "max": 1},
    "sleep_duration"            : {"var": "v00096", "length": 6, "type": int,   "read": True, "write": True, "min": 5, "max": 180},
    "sleep_level"               : {"var": "v00097", "length": 5, "type": int,   "read": True, "write": True, "min": 0, "max": 4},
    "sleep_on"                  : {"var": "v00099", "length": 5, "type": bool,  "read": True, "write": True, "min": 0, "max": 1},
    "preheating_status"         : {"var": "v00024", "length": 5, "type": bool,  "read": True, "write": True, "min": 0, "max": 1}
}


class HeliosTCP(SmartPlugin):

    PLUGIN_VERSION = "1.0.2"
    MODBUS_SLAVE = 180
    PORT = 502
    START_REGISTER = 1

    _items = {}

    def __init__(self, sh):
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self._helios_ip = self.get_parameter_value('helios_ip')
        self._client = ModbusTcpClient(self._helios_ip)
        self.alive = False
        self._is_connected = False
        self._update_cycle = self.get_parameter_value('update_cycle')


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self._is_connected = self._client.connect()
        if not self._is_connected:
            self.logger.error("Helios TCP: Failed to connect to Modbus Server at {0}".format(self._helios_ip))
        self.scheduler_add('Helios TCP', self._update_values, cycle=self._update_cycle)
        self.alive = True


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('Helios TCP')
        self._client.close()
        self.alive = False


    def parse_item(self, item):
        if 'helios_tcp' in item.conf:
            varname = item.conf['helios_tcp']
            if varname in VARLIST.keys():
                self._items[varname] = item
                return self.update_item
            else:
                self.logger.warning("Helios TCP: Ignoring unknown variable '{0}'".format(varname))

    def _update_values(self):
        for item in self._items:
            self._read_value(self._items[item])


    @staticmethod
    def _string_to_registers(instr: str):
        l = bytearray(instr, 'ascii')
        return [k[0]*256 + k[1] for k in zip(l[::2], l[1::2])] + [0]


    def _read_value(self, item):
        try:
            var = item.conf['helios_tcp']
        except ValueError:
            return

        try:
            varprop = VARLIST[var]
        except KeyError:
            self.logger.error("Helios TCP: Failed to find variable '{0}'".format(var))
            return

        # At first we write the variable name to read into the input registers:
        payload = self._string_to_registers(varprop['var'])
        request = self._client.write_registers(self.START_REGISTER, payload, unit=self.MODBUS_SLAVE)
        if request is None:
            self.logger.warning("Helios TCP: Failed to send read request for variable '{0}'".format(var))
            return

        # Now we may read the holding registers:
        response = self._client.read_holding_registers(self.START_REGISTER, varprop['length'], unit=self.MODBUS_SLAVE)
        if response is None:
            self.logger.warning("Helios TCP: Failed to send read response for variable '{0}'".format(var))
            return

        # Now we may dedocde the result
        # Note that we immediatly strip the varname from the result.
        result = response.encode().decode('ascii')[8:]
        result = list(result)

        # Remove trailing zeros:
        while result[-1] == '\x00':
            result.pop()

        result = ''.join(result)

        # Finally we may cast the result and return the obtained value:
        try:
            item(varprop["type"](result), self.get_shortname())
        except ValueError:
            self.logger.warning("Helios TCP: Could not assign {0} to item {1}".format(varprop["type"](result), item.property.path))
            return


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
        if self.alive and caller != self.get_shortname():
            try:
                var = item.conf['helios_tcp']
            except ValueError:
                return

            newval = item()

            try:
                varprop = VARLIST[var]
            except KeyError:
                self.logger.error("Helios TCP: Failed to find variable '{0}'".format(var))
                return

            if not varprop["write"]:
                return

            if type(newval) != varprop["type"]:
                self.logger.error("Helios TCP: Type mismatch for variable '{0}'".format(var))
                return

            if newval < varprop["min"] or newval > varprop["max"]:
                self.logger.error("Helios TCP: Variable '{0}' out of bounds. The allowed range is [{1}, {2}]".format(var, varprop["min"], varprop["max"]))
                return

            if varprop["type"] == bool:
                payload_string = "{0}={1}".format(varprop["var"], int(newval))
            elif varprop["type"] == int:
                payload_string = "{0}={1}".format(varprop["var"], int(newval))
            elif varprop["type"] == float:
                payload_string = "{0}={1:.1f}".format(varprop["var"], newval)
            else:
                self.logger.error("Helios TCP: Type {0} of varible '{1}' not known".format(varprop["type"], var))
                return

            payload = self._string_to_registers(payload_string)
            request = self._client.write_registers(self.START_REGISTER, payload, unit=self.MODBUS_SLAVE)
            if request is None:
                self.logger.warning("Helios TCP: Failed to send write request for variable '{0}'".format(var))
                return

