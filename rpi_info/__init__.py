#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.8 and
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

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface

import subprocess
from datetime import timedelta
import lib.cpuinfo


class RPi_Info(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the items
    """

    PLUGIN_VERSION = '1.0.0'

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object anymore.

        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._item_dict = {}
        self._flags_value = None
        self._cpu_info = None
        self._cyclic_update_active = False
        self._rpi_model = None
        self.suspended = False
        self.alive = False

        # check if shNG is running on Raspberry Pi
        if not self._is_rpi():
            self.logger.error(f"Plugin '{self.get_shortname()}': Plugin just works with Raspberry Pi or equivalent.")
            self._init_complete = False
            return

        try:
            self.webif_pagelength = self.get_parameter_value('webif_pagelength')
            self.poll_cycle = self.get_parameter_value('poll_cycle')
        except KeyError as e:
            self.logger.critical("Plugin '{}': Inconsistent plugin (invalid metadata definition: {} not defined)".format(self.get_shortname(), e))
            self._init_complete = False
            return

        self.init_webinterface(WebInterface)
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        self.scheduler_add('poll_device', self.poll_device, cycle=self.poll_cycle)
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_device')
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in the future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, 'rpiinfo_func'):
            self.logger.debug(f"parse item: {item}")
            self._item_dict[item] = self.get_iattr_value(item.conf, 'rpiinfo_func')

        elif self.has_iattr(item.conf, 'rpiinfo_sys'):
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped and only, if the item has not been changed by this plugin:
            self.logger.info(f"Update item: {item.property.path}, item has been changed outside this plugin")

            if self.has_iattr(item.conf, 'rpiinfo_sys'):
                self.logger.debug(f"update_item was called with item {item.property.path} from caller {caller}, source {source} and dest {dest}")
                if self.get_iattr_value(item.conf, 'rpiinfo_sys') == 'update' and bool(item()):
                    self.logger.info(f"Update of all items of RPi_Info Plugin requested. ")
                    self.poll_device()
                    item(False)
            pass

    def poll_device(self):
        """
        Polls for updates of the device
        """
        # check if another cyclic cmd run is still active
        if self._cyclic_update_active:
            self.logger.warning('Triggered cyclic poll_device, but previous cyclic run is still active. Therefore request will be skipped.')
            return
        elif self.suspended:
            self.logger.warning('Triggered cyclic poll_device, but Plugin in suspended. Therefore request will be skipped.')
            return
        else:
            self.logger.info('Triggering cyclic poll_device')

        # set lock
        self._cyclic_update_active = True

        for item in self._item_dict:
            # self.logger.debug(f"poll_device: handle item {item.property.path}")
            value = eval(f"self.{self.get_iattr_value(item.conf, 'rpiinfo_func')}()")
            # self.logger.info(f"poll_device: {value=} for item {item.property.path} will be set.")
            item(value, self.get_shortname())

        # release lock
        self._cyclic_update_active = False

        # Reset flags for next update
        self._flags_value = None
        pass

    @staticmethod
    def _call(cmd, arg):
        process = subprocess.Popen([cmd, arg], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        return stdout.decode('utf-8').strip()

    def _flags(self):
        if self._flags_value is None:
            __, __, thr = self._call('vcgencmd', 'get_throttled').strip().partition('=')
            self._flags_value = int(thr, 16)
        return self._flags_value

    @staticmethod
    def uptime():
        with open('/proc/uptime', 'r') as f:
            return int(float(f.readline().split()[0]))

    def uptime_string(self):
        time_str = str(timedelta(seconds=self.uptime()))
        return time_str

    @staticmethod
    def cpu_temperature():
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            tmp = int(float(f.read().strip()) / 100) / 10
        return tmp

    def frequency(self):
        __, __, frq = self._call('vcgencmd', 'measure_clock arm').strip().partition('=')
        return int(int(frq) / 1000000)

    def under_voltage(self):
        return bool(self._flags() >> 0 & 1)

    def frequency_capped(self):
        return bool(self._flags() >> 1 & 1)

    def throttled(self):
        return bool(self._flags() >> 2 & 1)

    def temperature_limit(self):
        return bool(self._flags() >> 3 & 1)

    def under_voltage_last_reboot(self):
        return bool(self._flags() >> 16 & 1)

    def throttled_last_reboot(self):
        return bool(self._flags() >> 17 & 1)

    def frequency_capped_last_reboot(self):
        return bool(self._flags() >> 18 & 1)

    def temperature_limit_last_reboot(self):
        return bool(self._flags() >> 19 & 1)

    def _get_cpuinfo(self):
        if not self._cpu_info:
            self._cpu_info = lib.cpuinfo._get_cpu_info_internal()
        return self._cpu_info

    def _get_rpi_model_by_revision_raw(self):
        try:
            revision_raw = self._get_cpuinfo().get('revision_raw', None)
        except Exception:
            pass
        else:
            model_info = rev_info.get(revision_raw, None)
            if not model_info:
                return f"Raspberry Pi (Rev. {revision_raw})"
            else:
                return model_info.get('model', None)

    def _get_rpi_ram(self):
        try:
            revision_raw = self._get_cpuinfo().get('revision_raw', None)
        except Exception:
            pass
        else:
            model_info = rev_info.get(revision_raw, None)
            if model_info:
                return model_info.get('ram', None)

    def _get_rpi_sn(self):
        try:
            with open('/sys/firmware/devicetree/base/serial-number', 'r') as m:
                _rpi_sn = m.read().strip()
        except Exception:
            pass
        else:
            return _rpi_sn

    def _get_rpi_model(self):
        try:
            with open('/sys/firmware/devicetree/base/model', 'r') as m:
                _rpi_model = m.read().strip()
        except Exception:
            self._rpi_model = False
            pass
        else:
            if 'raspberry pi' in _rpi_model.lower():
                self._rpi_model = _rpi_model
            else:
                self._rpi_model = False

    def _is_rpi(self):
        if self._rpi_model is None:
            self._get_rpi_model()

        return True if self._rpi_model else False

    @property
    def item_list(self):
        return list(self._item_dict.keys())

    def suspend(self, state: bool = False):
        """
        Will pause value evaluation of plugin
        """

        if state:
            self.logger.info("Plugins suspended. No information about RPi will be gathered.")
            self.suspended = True
            self._clear_queue()
        else:
            self.logger.info("Plugin suspension cancelled. Gathering of information about RPi will be resumed.")
            self.suspended = False

    @property
    def rpi_model_by_revision_raw(self):
        return self._get_rpi_model_by_revision_raw()

    @property
    def rpi_model(self):
        return self._rpi_model

    @property
    def rpi_ram(self):
        return self._get_rpi_ram()

    @property
    def rpi_sn(self):
        return self._get_rpi_sn()

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()


throttled = {
    0: 'Under-voltage!',
    1: 'ARM frequency capped!',
    2: 'Currently throttled!',
    3: 'Soft temperature limit active',
    16: 'Under-voltage has occurred since last reboot.',
    17: 'Throttling has occurred since last reboot.',
    18: 'ARM frequency capped has occurred since last reboot.',
    19: 'Soft temperature limit has occurred'
}

rev_info = {
    '0002': {'model': 'Raspberry Model B Rev 1',           'ram': '256MB', 'revision': '',    'manufacturer': ''},
    '0003': {'model': 'Raspberry Model B Rev 1 - ECN0001', 'ram': '256MB', 'revision': '',    'manufacturer': ''},
    '0004': {'model': 'Raspberry Model B Rev 2',           'ram': '256MB', 'revision': '',    'manufacturer': ''},
    '0005': {'model': 'Raspberry Model B Rev 2',           'ram': '256MB', 'revision': '',    'manufacturer': ''},
    '0006': {'model': 'Raspberry Model B Rev 2',           'ram': '256MB', 'revision': '',    'manufacturer': ''},
    '0007': {'model': 'Raspberry Model A',                 'ram': '256MB', 'revision': '',    'manufacturer': ''},
    '0008': {'model': 'Raspberry Model A',                 'ram': '256MB', 'revision': '',    'manufacturer': ''},
    '0009': {'model': 'Raspberry Model A',                 'ram': '256MB', 'revision': '',    'manufacturer': ''},
    '000d': {'model': 'Raspberry Model B Rev 2',           'ram': '512MB', 'revision': '',    'manufacturer': ''},
    '000e': {'model': 'Raspberry Model B Rev 2',           'ram': '512MB', 'revision': '',    'manufacturer': ''},
    '000f': {'model': 'Raspberry Model B Rev 2',           'ram': '512MB', 'revision': '',    'manufacturer': ''},
    '0010': {'model': 'Raspberry Model B+',                'ram': '512MB', 'revision': '',    'manufacturer': ''},
    '0013': {'model': 'Raspberry Model B+',                'ram': '512MB', 'revision': '',    'manufacturer': ''},
    '900032': {'model': 'Raspberry Model B+',              'ram': '512MB', 'revision': '',    'manufacturer': ''},
    '0011': {'model': 'Raspberry Compute Modul',           'ram': '512MB', 'revision': '',    'manufacturer': ''},
    '0014': {'model': 'Raspberry Compute Modul',           'ram': '512MB', 'revision': '',    'manufacturer': 'Embest, China'},
    '0012': {'model': 'Raspberry Model A+',                'ram': '256MB', 'revision': '',    'manufacturer': ''},
    '0015': {'model': 'Raspberry Model A+',                'ram': '256MB', 'revision': '',    'manufacturer': 'Embest, China'},
    'a01041': {'model': 'Raspberry Pi 2 Model B',          'ram': '1GB',   'revision': '1.1', 'manufacturer': 'Sony, UK'},
    'a21041': {'model': 'Raspberry Pi 2 Model B',          'ram': '1GB',   'revision': '1.1', 'manufacturer': 'Embest, China'},
    'a22042': {'model': 'Raspberry Pi 2 Model B',          'ram': '1GB',   'revision': '1.2', 'manufacturer': ''},
    '900092': {'model': 'Raspberry Pi Zero v1.2',          'ram': '512MB', 'revision': '1.2', 'manufacturer': ''},
    '900093': {'model': 'Raspberry Pi Zero v1.3',          'ram': '512MB', 'revision': '1.3', 'manufacturer': ''},
    '9000C1': {'model': 'Raspberry Pi Zero W',             'ram': '512MB', 'revision': '1.1', 'manufacturer': ''},
    'a02082': {'model': 'Raspberry Pi 3 Model B',          'ram': '1GB',   'revision': '1.2', 'manufacturer': 'Sony, UK'},
    'a22082': {'model': 'Raspberry Pi 3 Model B',          'ram': '1GB',   'revision': '1.2', 'manufacturer': 'Embest, China'},
    'a020d3': {'model': 'Raspberry Pi 3 Model B+',         'ram': '1GB',   'revision': '1.3', 'manufacturer': 'Sony, UK'},
    'a03111': {'model': 'Raspberry Pi 4',                  'ram': '1GB',   'revision': '1.1', 'manufacturer': 'Sony, UK'},
    'b03111': {'model': 'Raspberry Pi 4',                  'ram': '2GB',   'revision': '1.1', 'manufacturer': 'Sony, UK'},
    'b03112': {'model': 'Raspberry Pi 4',                  'ram': '2GB',   'revision': '1.2', 'manufacturer': 'Sony, UK'},
    'c03111': {'model': 'Raspberry Pi 4',                  'ram': '4GB',   'revision': '1.1', 'manufacturer': 'Sony, UK'},
    'c03112': {'model': 'Raspberry Pi 4',                  'ram': '4GB',   'revision': '1.2', 'manufacturer': 'Sony, UK'},
    'c03114': {'model': 'Raspberry Pi 4',                  'ram': '8GB',   'revision': '1.4', 'manufacturer': 'Sony, UK'},
}
