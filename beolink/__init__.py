#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022-      Martin Sinn                         m.sinn@gmx.de
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

from lib.module import Modules
from lib.model.smartplugin import SmartPlugin

from .webif import WebInterface
from .beodevices import *
import plugins.beolink.beonotifications as beonotify

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class BeoNetlink(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '0.8.1'

    def __init__(self, sh):
        """
        Initalizes the plugin.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions 1.4 and up: **Don't use it**!

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (MqttPlugin)
        super().__init__()
        if self._init_complete == False:
            return

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        # self.param1 = self.get_parameter_value('param1')
        self.fromip = self.get_parameter_value('scan_fromip')
        self.toip = self.get_parameter_value('scan_toip')
        self.rescan_on_start = self.get_parameter_value('rescan_on_start')

        if self.fromip == '0.0.0.0' or self.toip == '0.0.0.0':
            self.logger.error('network scan range (scan_fromip, scan_toip) not propperly defined')
            # self._init_complete = False
            # return

        fromip = self.fromip.split('.')
        toip = self.toip.split('.')
        if fromip[0] != toip[0] or fromip[1] != toip[1] or fromip[2] != toip[2]:
            self.logger.error('scan_fromip and scan_toip are not in same class-c subnet')
            # self._init_complete = False

        self.datadir = os.path.join(self._sh.base_dir, 'var', 'bo_netlink')
        if not os.path.isdir(self.datadir):
            os.mkdir(self.datadir)
            self.logger.info('Data directory for plugin created: {}'.format(self.datadir))


        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = 5

        # Initialization code goes here

        # On initialization error use:
        #   self._init_complete = False
        #   return

        self.beo_keys = []
        self.beodevices = BeoDevices(self.fromip, self.toip, self.logger, self.datadir, self.translate)

        self._attrib_current_number = 0  # current number of the subscription entry
        self.beo_items = {}      # key= beo_id + '_' + beo_status + '_' + self._attrib_current_number
        self._item_values = {}  # dict of dicts

        # The following part of the __init__ method is only needed, if a webinterface is being implemented:

        # Rescan devices on startup, since they can have a new IP addrress
        if self.rescan_on_start:
            self.beodevices.scan_subnet()

        # if plugin should start even without web interface
        self.init_webinterface(WebInterface)

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)

        #self.scheduler_add('scheduler_param_test_1', self.scheduler_param_test, value={'param1':'val1'}, cycle=30)
        #self.scheduler_add('scheduler_param_test_2', self.scheduler_param_test, value={'value':'val2'}, cycle=30)

        self.beodevices.get_devicelist()
        #self.beodeviceinfo = self.beodevices.get_devicelist()0
        #self.beo_keys = list(self.beodeviceinfo.keys())
        #self.beo_keys.sort()

        self.create_notification_objects()

        #for beo_key in self.beodevices.beo_keys:
        #    self.scheduler_add('process_notification_'+beo_key, self.process_notification, value={'id': beo_key}, cycle=2)

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        #for beo_key in self.beodevices.beo_keys:
        #    self.scheduler_remove('process_notification_'+beo_key)
        self.scheduler_remove('poll_device')
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
        if self.has_iattr(item.conf, 'beo_id'):
            self.logger.debug("parse item: {}".format(item))

            beo_id = self.get_iattr_value(item.conf, 'beo_id').upper()
            beo_status = self.get_iattr_value(item.conf, 'beo_status')
            beo_command = self.get_iattr_value(item.conf, 'beo_command')
            if beo_status:
                self._attrib_current_number += 1
                beo_item_key = beo_id + '_' + beo_status.lower() + '_' + str(self._attrib_current_number).zfill(3)
                self.beo_items[beo_item_key] = item
                self.logger.debug("beo_item_key: {}, item: {}".format(beo_item_key, item.property.path))

            if beo_command:
                return self.update_item


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
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
        self.logger.debug("update_item: {}".format(item.property.path))

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.property.path))

            if self.has_iattr(item.conf, 'beo_id'):
                self.logger.debug("update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item, caller, source, dest))

                beo_id = self.get_iattr_value(item.conf, 'beo_id').upper()
                beo_command = self.get_iattr_value(item.conf, 'beo_command').lower()
                value = item()
                if beo_command == 'muted':
                    self.beodevices.set_speaker_muted(beo_id, item())
                    api_url = ''
                elif beo_command == 'volume':
                    self.beodevices.set_speaker_volume(beo_id, item())
                    api_url = ''
                elif beo_command == 'vol_rel':
                    vol = self.beodevices.get_speaker_volume(beo_id)
                    vol = vol + item()
                    self.beodevices.set_speaker_volume(beo_id, vol)
                    api_url = ''
                elif beo_command == 'stand':
                    if item._type == 'num':
                        self.beodevices.set_stand(beo_id, item())
                    elif item._type == 'str':
                        pass
                    api_url = ''

                elif beo_command == 'step_up':
                    api_url = '/BeoOneWay/Input'
                    data = '{"timestamp":0,"command":"STEP_UP"}'
                elif beo_command == 'step_dn':
                    api_url = '/BeoOneWay/Input'
                    data = '{"timestamp":0,"command":"STEP_DOWN"}'
                else:
                    api_url = ''

                if api_url:
                    self.beodevices.post_beo_command(beo_id, api_url, data)
                    self.logger.info("update_item: {} url = '{}', data = '{}'".format(beo_id, api_url, data))

        # self.put_beo_api('10.0.0.239', '/BeoZone/Zone/Stand/Active', json_elements='{"active":0}')


    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler.
        """
        self.logger.debug("poll_device: Got called")

        # get the value(s) from the device
        self.beodevices.update_devices_info()

        # loop through items to set value from beodevices info
        for beo_itemkey in self.beo_items.keys():
            item = self.beo_items[beo_itemkey]
            beo_id = item.conf['beo_id']
            beo_status = item.conf['beo_status']
            if beo_status and beo_id != '':
                # set items according to beo_status
                #if beo_status == 'beoname':
                #    deviceinfo = self.beodevices.beodeviceinfo[beo_id].get('FriendlyName', None)
                #elif beo_status == 'beotype':
                #    deviceinfo = self.beodevices.beodeviceinfo[beo_id].get('productType', None)
                #else:
                #    deviceinfo = self.beodevices.beodeviceinfo[beo_id].get(beo_status, None)
                beo_device = self.beodevices.beodeviceinfo.get(beo_id, None)
                if beo_device is None:
                    self.logger.warning(f"poll_device: No deviceinfo found  for device-id '{beo_id}'")
                else:
                    if beo_status == 'audiomode':
                        deviceinfo = self.beodevices.beodeviceinfo[beo_id]['device'].get('audiomode'[1], False)
                    elif beo_status == 'videomode':
                        deviceinfo = self.beodevices.beodeviceinfo[beo_id]['device'].get('videomode'[1], False)
                    elif beo_status == 'powerstate':
                        deviceinfo = self.beodevices.beodeviceinfo[beo_id]['device'].get('powerstate', False)
                    elif beo_status == 'stand':
                        deviceinfo = self.beodevices.beodeviceinfo[beo_id]['device'].get('stand'[1], False)
                    elif beo_status == 'source':
                        deviceinfo = self.beodevices.beodeviceinfo[beo_id]['source'].get('source', '-')
                    elif beo_status == 'volume':
                        deviceinfo = self.beodevices.beodeviceinfo[beo_id]['volume'].get('level', 0)
                    elif beo_status == 'muted':
                        deviceinfo = self.beodevices.beodeviceinfo[beo_id]['volume'].get('muted', False)
                    elif beo_status == 'FriendlyName':
                        deviceinfo = self.beodevices.beodeviceinfo[beo_id]['device'].get('FriendlyName', False)
                    elif beo_status == 'productType':
                        deviceinfo = self.beodevices.beodeviceinfo[beo_id]['device'].get('productType', False)

                    else:
                        deviceinfo = self.beodevices.beodeviceinfo[beo_id].get(beo_status, None)
                    #self.logger.info(f"poll_device: item={item.property.path}, beo_id={beo_id}, beo_status={beo_status}, self.beodevices.beodeviceinfo[beo_id]={self.beodevices.beodeviceinfo[beo_id]}")
                    #self.logger.info(f"poll_device: item={item.property.path}, deviceinfo={deviceinfo}")
                    if isinstance(deviceinfo, tuple):
                        if item._type == 'num':
                            beo_value = deviceinfo[1]
                        else:
                            beo_value = deviceinfo[0]
                    else:
                        beo_value = deviceinfo

                    if item() == beo_value:
                        self.logger.debug("update_deviceinfo: Updated item {} with beo-{} {}".format(item.property.path, beo_status, beo_value))
                    else:
                        self.logger.info("update_deviceinfo: Changed item {} with beo-{} {}".format(item.property.path, beo_status, beo_value))
                    item(beo_value, self.get_shortname())
                    self._update_item_values(item, beo_value)
            else:
                self.logger.info(f"poll_device: No beo_status")
        return


    notification_objects = {}

    def create_notification_objects(self):

        for id in self.beodevices.beo_keys:
            self.logger.info(f"No Instance of notification class for device '{self.beodevices.beodeviceinfo[id]['device']['FriendlyName']}', creating one")
            self.notification_objects[id] = beonotify.beo_notifications(device_dict=self.beodevices.beodeviceinfo[id], logger_name=self.logger.name + '.notify')


    def process_notification(self, id=None ):

        #if self.notification_objects.get('id', None) is None:
        #    self.logger.notice(f"No Instance of notification class for device '{self.beodevices.beodeviceinfo[id]['FriendlyName']}', creating one")
        #    self.notification_objects[id] = beonotify.beo_notifications(device_dict=self.beodevices.beodeviceinfo[id], logger_name=self.logger.name + '.notify')
        #    self.logger.notice(f"notification_objects='{self.notification_objects}'")

        if self.notification_objects.get(id, None) is not None:
            self.notification_objects[id].process_stream()


    def _update_item_values(self, item, payload):
        """
        Update dict for periodic updates of the web interface

        :param item:
        :param payload:
        """
        if not self._item_values.get(item.property.path):
            self._item_values[item.property.path] = {}
        if isinstance(payload, bool):
            self._item_values[item.property.path]['value'] = str(payload)
        else:
            self._item_values[item.property.path]['value'] = payload
        self._item_values[item.property.path]['last_update'] = item.last_update().strftime('%d.%m.%Y %H:%M:%S')
        self._item_values[item.property.path]['last_change'] = item.last_change().strftime('%d.%m.%Y %H:%M:%S')
        return


