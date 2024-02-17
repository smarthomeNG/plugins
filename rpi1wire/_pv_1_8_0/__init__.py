#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2015 R.Rauer                              software@rrauer.de
#  Copyright 2020 Bernd Meiners                     Bernd.Meiners@mail.de
#  Copyright 2021 Michael Wenzel                    wenzel_michael@web.de
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

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface


class Rpi1Wire(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.8.0'

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
        
        self.logger.info('Init rpi1wire plugin')

        # Call init code of parent class (SmartPlugin or MqttPlugin)
        super().__init__()
        if not self._init_complete:
            return

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        try:
            self.dirname = self.get_parameter_value('dirname')
            if self.get_parameter_value('cycle') is not None:
                self.cycle = self.get_parameter_value('cycle')
            else:
                self.cycle = 120
        except KeyError as e:
            self.logger.critical(
                "Plugin '{}': Inconsistent plugin (invalid metadata definition: {} not defined)".format(self.get_shortname(), e))
            self._init_complete = False
            return

        # Initialization code goes here
        self.sensors = {}
        self._sensordaten = {}
        self.values = {}
        self.sysitems = {}
        self.update = False
        self.get_sensors()
        self.anz_sensors = len(self.sensors)
        self.logger.info(f"rpi1wire found {self.anz_sensors} sensors.")

        # On initialization error use:
        #   self._init_complete = False
        #   return

        if not self.init_webinterface(WebInterface):
            self.logger.error("Unable to start Webinterface")
            self._init_complete = False
        else:
            self.logger.debug("Init complete")
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        self.scheduler_add('rpi1wire', self.update_values, prio=3, cycle=self.cycle)

        self.alive = True
        self.update_values()
        self.update_basics()

    def update_basics(self):
        """
        Method to update basic information of plugin like count of sensors and sensor list
        """

        if self.sysitems.get('count'):
            anz = self.get_sh().return_item(self.sysitems['count'])
            anz(int(self.anz_sensors), 'rpi1wire')
            self.logger.debug("rpi1wire-item sensors: {0}".format(self.anz_sensors))

        if self.sysitems.get('list'):
            ids = self.get_sh().return_item(self.sysitems['list'])
            ids(str(self.sensors).replace("\'", ""), 'rpi1wire')
            self.logger.debug("rpi1wire-item sensor_list: {0}".format(self.sensors))

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
            type1 = self.get_iattr_value(item.conf, 'rpi1wire_sys')
            if type1 == 'update':
                self.logger.info("parse item: {}".format(item))
                return self.update_item
            else:
                try:
                    sitem = item._path
                    self.sysitems[type1] = str(sitem)
                    self.logger.info("Item {0} assignment on Item {1} successful".format(item, sitem))
                except:
                    self.logger.warning("Item {0} assignment on Item {1} not successful".format(item, sitem))

        if not self.has_iattr(item.conf, 'rpi1wire_id'):
            if not self.has_iattr(item.conf, 'rpi1wire_name'):
                return None

        not_found = False
        if self.has_iattr(item.conf, 'rpi1wire_id'):
            addr = self.get_iattr_value(item.conf, 'rpi1wire_id')
            try:
                for sn, sid in self.sensors.items():
                    if sid == self.get_iattr_value(item.conf, 'rpi1wire_id'):
                        name = sn
                        break
            except:
                self.logger.warning("Sensor {0} as Item defined but hardware not found".format(self.get_iattr_value(item.conf, 'rpi1wire_id')))
                not_found = True
        else:
            if self.has_iattr(item.conf, 'rpi1wire_name'):
                name = self.get_iattr_value(item.conf, 'rpi1wire_name')
                try:
                    addr = self.sensors[self.get_iattr_value(item.conf, 'rpi1wire_name')]
                except:
                    self.logger.warning("Sensor {0} Hardware not found".format(self.get_iattr_value(item.conf, 'rpi1wire_name')))
                    not_found = True
        if not_found is False:
            self._sensordaten[addr]['item'] = item

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
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.property.path))

            if self.has_iattr(item.conf, 'rpi1wire_update'):
                self.logger.info("rpi1wire_update has been called")
                self.update_sensors()
                return None

    def update_values(self):
        """
        Updates the values in plugin dict from 1wire directory
        """
        for sensor in self.sensors:
            owid = self.sensors[sensor]
            value = self.get_value(owid)
            # if value != 99999:
            text = sensor + "=" + sensor[0] + ": " + str(round(value/float(1000), 1)) + " (" + str(value)+")"
            self.logger.debug(text)
            self.values[sensor] = round(value/float(1000), 1)
            try:
                rpix = self._sensordaten[owid]
                temp = rpix['item']
                temp(round(value/float(1000), 1), "rpi1wire")
                self._sensordaten[owid]['value'] = round(value/float(1000), 1)
            except:
                self.logger.info("sensor {0} has no item".format(owid))

    def get_sensors(self):
        """
        Search for connected sensors and insert into self.sensors, self.values and self._sensordaten
        """
        objects = self.folder_objects(self.dirname)
        i = 1
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
                        self.logger.warning("rpi1wire {0} - has no value".format(sensor))
                    else:
                        text = "rpi_temp"+str(i)+"=" + sensor + ": " + str(round(value/float(1000), 1)) + " (" + str(value)+")"
                        self.logger.info(text)
                        self.sensors["rpi_temp"+str(i)] = sensor
                        self.values["rpi_temp"+str(i)] = round(value/float(1000), 1)
                        self._sensordaten[sensor] = {'name': "rpi_temp" + str(i), 'value': round(value / float(1000), 1)}
                        i += 1
        else:
            self.logger.warning("rpi1wire plugin did not find directory at {0}".format(self.dirname))

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
                self.logger.warning("rpi1wire {0} - return no value".format(owid))
                mytemp = '99999'
            f.close()
            return int(mytemp[1])
        except:
            self.logger.warning("can not read sensor {}".format(owid))
            return 99999

    def update_sensors(self):
        """
        Update of all sensor values
        """
        self.update = True
        self.sensors = {}
        self.anz_sensors = 0
        self.get_sensors()
        self.anz_sensors = len(self.sensors)
        self.search_item()
        self.update_basics()
        self.update_values()
        upd = self.get_sh().return_item(self.sysitems['update'])  # Item zum Updaten der Sensoren
        if upd is not None:
            upd(False, 'rpi1wire')
            self.logger.warning("{0} update value done, {1} sensors found".format(self.sysitems['update'], self.anz_sensors))
        self.update = False

    def search_item(self):
        """
        Search within all items for plugin specific attributes and add relevant items to plugin dict
        """
        items = self.get_sh().return_items()
        for item in items:
            if self.has_iattr(item.conf, 'rpi1wire_id'):
                addr = self.get_iattr_value(item.conf, 'rpi1wire_id')
                try:
                    for sn, sid in self.sensors.items():
                        if sid == addr:
                            name = sn
                            self._sensordaten[addr]['item'] = item
                            break
                except:
                    self.logger.warning("Sensor {0} Hardware not found".format(addr))
                    not_found = True
            if self.has_iattr(item.conf, 'rpi1wire_name'):
                name = self.get_iattr_value(item.conf, 'rpi1wire_name')
                try:
                    addr = self.sensors[name]
                    self._sensordaten[addr]['item'] = item
                except:
                    self.logger.warning("Sensor {0} Hardware not found".format(name))
            if self.has_iattr(item.conf, 'rpi1wire_sys'):
                type = self.get_iattr_value(item.conf, 'rpi1wire_sys')
                try:
                    sitem = item._path
                    self.sysitems[type] = str(sitem)
                    self.logger.info("Item {0} assignment on Item {1} successful".format(item, sitem))
                except:
                    self.logger.warning("Item {0} assignment on Item {1} NOT successful".format(item, sitem))
        self.logger.info("{0} rpi1wire-items registriert".format(len(self._sensordaten)))

    def save_sysitems(self, item):
        """
        Search within all items for plugin specific attribute 'rpi1wire_sys' and add relevant items to plugin dict
        """
        type1 = self.get_iattr_value(item.conf, 'rpi1wire_sys')
        try:
            path = item._path
            self.sysitems[type1]['item'] = path
        except:
            self.logger.warning("Item {0} assignment NOT successful".format(item))
