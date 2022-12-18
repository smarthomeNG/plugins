#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2015 R.Rauer                              software@rrauer.de
#  Copyright 2020 Bernd Meiners                     Bernd.Meiners@mail.de
#  Copyright 2021- Michael Wenzel                   wenzel_michael@web.de
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

import os
import io

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface


class Rpi1Wire(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.8.1'

    def __init__(self, sh):
        """"
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        self.logger.info(f'Init of Plugin {self.get_shortname()} started')

        # Call init code of parent class (SmartPlugin or MqttPlugin)
        super().__init__()
        if not self._init_complete:
            return
            
        # check if shNG is running on Raspberry Pi
        if not self._is_raspberrypi():
            self.logger.error(f"Plugin '{self.get_shortname()}': Plugin just works with Raspberry Pi or equivalent.")
            self._init_complete = False
            return

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        try:
            self.dirname = self.get_parameter_value('dirname')
            if self.get_parameter_value('cycle') is not None:
                self.cycle = self.get_parameter_value('cycle')
            else:
                self.cycle = 120
        except KeyError as e:
            self.logger.critical(f"Plugin '{self.get_shortname()}': Inconsistent plugin (invalid metadata definition: {e} not defined)")
            self._init_complete = False
            return

        # Initialization code goes here
        self._sensordata = {}                  # dict to hold all 1w information read from given directory
        self.sysitems = {}                     # dict to hold Plugin system items
        self.sensoritems = {}                  # dict to hold Plugin sensor items

        self.update = False

        # On initialization error use:
        #   self._init_complete = False
        #   return

        if not self.init_webinterface(WebInterface):
            self.logger.error("Unable to start Webinterface")
            self._init_complete = False
        else:
            self.logger.debug(f"Init of Plugin {self.get_shortname()} complete")
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.scheduler_add('rpi1wire', self.update_sensors, prio=3, cycle=self.cycle)
        self.alive = True
        # Update sensors and items
        self.get_sensors()
        self.update_system()

    def update_system(self):
        """
        Method to update basic information of plugin like count of sensors and sensor list
        """

        count_item = self.sysitems.get('count')
        if count_item is not None:
            count_item(int(len(self._sensordata)), self.get_shortname())
            self.logger.debug(f"Item <{count_item.id()}> set to <{int(len(self._sensordata))}>.")

        list_item = self.sysitems.get('list')
        if list_item is not None:
            sensor_list = ", ".join(list(self._sensordata.keys()))
            list_item(sensor_list, self.get_shortname())
            self.logger.debug(f"Item <{list_item.id()}> set to <{sensor_list}>.")

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """

        if self.has_iattr(item.conf, 'rpi1wire_sys'):
            self.logger.info(f"parse item: {item.id()}")
            rpi1wire_sys = self.get_iattr_value(item.conf, 'rpi1wire_sys')
            self.sysitems[rpi1wire_sys] = item
            if rpi1wire_sys == 'update':
                return self.update_item

        elif self.has_iattr(item.conf, 'rpi1wire_id'):
            self.logger.info(f"parse item: {item.id()}")
            addr = self.get_iattr_value(item.conf, 'rpi1wire_id')
            self.sensoritems[addr] = item

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
        if self.update is True:
            return None

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info(f"Update item: <{item.id()}>, item has been changed outside this plugin")
            self.logger.info("Re-read of 1wire data from dictonary has been initiated.")
            self.update_sensors()
            return None

    def update_item_values(self):
        """
        Updates the value of connected items
        """
        for sensor in self.sensoritems:
            item = self.sensoritems[sensor]
            value_dict = self._sensordata.get(sensor)
            if value_dict is not None:
                value = value_dict.get('value')
                sensortype = value_dict.get('sensortype')
                self.logger.debug(f"For Item <{item.id()}> the value <{value}> for sensortype <{sensortype}> will be set.")
                if item is not None:
                    item(value, self.get_shortname())
            else:
                self.logger.warning(f"For Item <{item.id()}> no sensordata are available. Sensor probably not connected.")

    def get_sensors(self):
        """
        Search for connected sensors and insert into self.sensors, self.values and self._sensordata
        """
        self.logger.debug(f"get_sensors called to read directory for new onewire data.")
        objects = self.folder_objects(self.dirname)
        if objects:
            # walking through the path objects
            for sensor in objects:
                if 'w1_bus' in sensor:
                    continue
                typ = sensor.rsplit("-", 1)
                # only proceed if filename starts with known sensor ID
                if typ[0] in ['10', '22', '28']:
                    value = self.get_value(sensor)
                    if value == 99999:
                        self.logger.warning(f"1wire sensor {sensor} - has no value")
                    else:
                        self._sensordata[sensor] = {'sensortype': "temp", 'value': round(value / float(1000), 1)}
            self.logger.debug(f"{self.get_shortname()} plugin found <{len(self._sensordata)}> sensors.")

            # set item values
            self.update_item_values()

        else:
            self.logger.warning(f"{self.get_shortname()} plugin did not find directory at <{self.dirname}>")

    def folder_objects(self, dirname, otype="all"):
        """
        Search in given directory for sensors and return them as a list of objects
        If successful returns a list of sensors starting at given param dirname
        """
        if (os.path.exists(dirname) is False or
            os.path.isdir(dirname) is False or
            os.access(dirname, os.R_OK) is False):
            return None
        else:
            objects = os.listdir(dirname)
            result = []
            for objectname in objects:
                objectpath = dirname + "/" + objectname
                if (otype == "all" or
                    (otype == "dir" and os.path.isdir(objectpath) is True) or
                    (otype == "file" and os.path.isfile(objectpath) is True) or
                    (otype == "link" and os.path.islink(objectpath) is True)):
                    result.append(objectname)
            result.sort()
            return result

    def get_value(self, owid):
        """
        reads a single sensor for a given id
        Source like here https://www.raspberrypi-spy.co.uk/2013/03/raspberry-pi-1-wire-digital-thermometer-sensor/
        """
        try:
            filename = 'w1_slave'
            f = open('/' + self.dirname + '/' + owid + '/' + filename, 'r')
            line = f.readline()  # read 1st line
            crc = line.rsplit(' ', 1)
            crc = crc[1].replace('\n', '')
            if crc == 'YES':
                line = f.readline()  # read 2nd line
                mytemp = line.rsplit('t=', 1)
            else:
                self.logger.warning(f"{owid} - return no value")
                mytemp = '99999'
            f.close()
            return int(mytemp[1])
        except:
            self.logger.warning(f"can not read sensor {owid}")
            return 99999

    def update_sensors(self):
        """
        Update of all sensor values
        """
        self.update = True
        self.get_sensors()
        self.update_system()

        update_item = self.sysitems.get('update')
        if update_item is not None:
            update_item(False, self.get_shortname())
            self.logger.debug(f"Update of data and items done; Item <{update_item.id()}> set to <False>")
        self.update = False
        
    def _is_raspberrypi(self):
        try:
            with io.open('/sys/firmware/devicetree/base/model', 'r') as m:
                if 'raspberry pi' in m.read().lower(): return True
        except Exception: pass
        return False