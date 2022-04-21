#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018 <AUTHOR>                                        <EMAIL>
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

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class BeoNetlink(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '0.6.0'

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
        self.beodevices = BeoDevices(self)
        #self.beodevices.get_devicelist()

        self._attrib_current_number = 0  # current number of the subscription entry
        self.beo_items = {}      # key= beo_id + '_' + beo_status + '_' + self._attrib_current_number
        self._item_values = {}  # dict of dicts

        # The following part of the __init__ method is only needed, if a webinterface is being implemented:

        # Rescan devices on startup, since they can have a new IP addrress
        if self.rescan_on_start:
            self.beodevices.scan_subnet(self.fromip, self.toip)

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

        self.beodevices.get_devicelist()
        #self.beodeviceinfo = self.beodevices.get_devicelist()
        #self.beo_keys = list(self.beodeviceinfo.keys())
        #self.beo_keys.sort()

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

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
                self.logger.debug("beo_item_key: {}, item: {}".format(beo_item_key, item.id()))

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
        self.logger.debug("update_item: {}".format(item.id()))

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))

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
            if beo_status:
                # set items according to beo_status
                #if beo_status == 'beoname':
                #    deviceinfo = self.beodevices.beodeviceinfo[beo_id].get('FriendlyName', None)
                #elif beo_status == 'beotype':
                #    deviceinfo = self.beodevices.beodeviceinfo[beo_id].get('productType', None)
                #else:
                #    deviceinfo = self.beodevices.beodeviceinfo[beo_id].get(beo_status, None)
                deviceinfo = self.beodevices.beodeviceinfo[beo_id].get(beo_status, None)
                #self.logger.info(f"poll_device: item={item.id()}, beo_id={beo_id}, beo_status={beo_status}, self.beodevices.beodeviceinfo[beo_id]={self.beodevices.beodeviceinfo[beo_id]}")
                #self.logger.info(f"poll_device: item={item.id()}, deviceinfo={deviceinfo}")
                if isinstance(deviceinfo, tuple):
                    if item._type == 'num':
                        beo_value = deviceinfo[1]
                    else:
                        beo_value = deviceinfo[0]
                else:
                    beo_value = deviceinfo

                if item() == beo_value:
                    self.logger.debug("update_deviceinfo: Updated item {} with beo-{} {}".format(item.id(), beo_status, beo_value))
                else:
                    self.logger.info("update_deviceinfo: Changed item {} with beo-{} {}".format(item.id(), beo_status, beo_value))
                item(beo_value, self.get_shortname())
                self._update_item_values(item, beo_value)
            else:
                self.logger.info(f"poll_device: No beo_status")
        return


    def _update_item_values(self, item, payload):
        """
        Update dict for periodic updates of the web interface

        :param item:
        :param payload:
        """
        if not self._item_values.get(item.id()):
            self._item_values[item.id()] = {}
        if isinstance(payload, bool):
            self._item_values[item.id()]['value'] = str(payload)
        else:
            self._item_values[item.id()]['value'] = payload
        self._item_values[item.id()]['last_update'] = item.last_update().strftime('%d.%m.%Y %H:%M:%S')
        self._item_values[item.id()]['last_change'] = item.last_change().strftime('%d.%m.%Y %H:%M:%S')
        return


# ------------------------------------------
#    Class for handling B&O devices
# ------------------------------------------

import requests

import lib.shyaml as shyaml
from lib.constants import (YAML_FILE)


class BeoDevices():

    beodeviceinfo = {}
    beo_keys = []

    def __init__(self, plugin=None):
        self.plugin = plugin

        self.beodeviceinfo = {}
        self.beo_keys = []

        self.filename = os.path.join(self.plugin.datadir, 'bo_deviceinfo'+YAML_FILE)

        pass

    def get_devicelist(self):
        self.beodeviceinfo = shyaml.yaml_load(self.filename, ordered=False, ignore_notfound=True)
        self.plugin.logger.info('devicelist: {}'.format(self.beodeviceinfo))
        if self.beodeviceinfo is None:
            self.scan_subnet(self.plugin.fromip, self.plugin.toip)
        else:
            self.update_devices_info()
        self.beo_keys = list(self.beodeviceinfo.keys())
        self.beo_keys.sort()
        return

    def scan_subnet(self, scan_fromip, scan_toip):
        self.plugin.logger.info('Scanning network range ({} to {}) for Bang & Olufsen devices'.format(scan_fromip, scan_toip))

        fromip = scan_fromip.split('.')
        toip = scan_toip.split('.')
        searchnet = '.'.join(fromip[0:3]) + '.'
        min_ip = int(fromip[3])
        max_ip = int(toip[3])

        filename = os.path.join(self.plugin.datadir, 'bo_deviceinfo' + YAML_FILE)
        scan_devicelist = shyaml.yaml_load(filename, ordered=False, ignore_notfound=True)
        self.plugin.logger.info('old list {}'.format(scan_devicelist))
        if scan_devicelist is None:
            scan_devicelist = {}

        filename = os.path.join(self.plugin.datadir, 'bo_rawinfo' + YAML_FILE)
        scan_rawinfo = shyaml.yaml_load(filename, ordered=False, ignore_notfound=True)
        #self.plugin.logger.info('old rawinfo {}'.format(scan_rawinfo))
        if scan_rawinfo is None:
            scan_rawinfo = {}

        for i in range(min_ip, max_ip):
            ip = searchnet + str(i)

            device = 'http://' + ip + ':8080'
            try:
                r = requests.get(device + '/Ping', timeout=0.5)
                result = True
            except:
                result = False

            if result:
                if r.status_code == 200:
                    beodevice_info = requests.get(device + '/BeoDevice')
                    actual_device = beodevice_info.json()

                    beo_id = actual_device['beoDevice']['productId']['serialNumber']

                    if scan_rawinfo.get(beo_id, None) is None:
                        scan_rawinfo[beo_id] = {}
                    scan_rawinfo[beo_id]['BeoDevice'] = beodevice_info.json()

                    if scan_devicelist.get(beo_id, None) is None:
                        scan_devicelist[beo_id] = {}
                    scan_devicelist[beo_id]['Device-Jid'] = r.headers.get('Device-Jid', '')

                    scan_devicelist[beo_id]['ip'] = ip
                    scan_devicelist[beo_id]['productType'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['productId']['productType']
                    scan_devicelist[beo_id]['typeNumber'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['productId']['typeNumber']
                    scan_devicelist[beo_id]['itemNumber'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['productId']['itemNumber']
                    scan_devicelist[beo_id]['serialNumber'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['productId']['serialNumber']
                    scan_devicelist[beo_id]['FriendlyName'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['productFriendlyName']['productFriendlyName']
                    scan_devicelist[beo_id]['swVersion'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['software']['version']

                    #pwr = requests.get(device + '/BeoDevice/powerManagement/standby', timeout=0.5)
                    #actual_pwr = pwr.json()
                    #scan_devicelist[serial]['powerstate'] = actual_pwr['standby']['powerState']

                    #self.plugin.logger.info("- found B&O device on ip {0: <10}: {1} ({2})".format(ip, scan_devicelist[beo_id]['Device-Jid'], scan_devicelist[beo_id]['FriendlyName']))


        self.plugin.logger.info('Scanning network range ({} to {}) finished'.format(scan_fromip, scan_toip))

        filename = os.path.join(self.plugin.datadir, 'bo_deviceinfo'+YAML_FILE)
        shyaml.yaml_save(filename, scan_devicelist)

        filename = os.path.join(self.plugin.datadir, 'bo_rawinfo'+YAML_FILE)
        shyaml.yaml_save(filename, scan_rawinfo)
        self.plugin.logger.info("Bang & Olufsen device info saved to directory {}".format(self.plugin.datadir))

        # move result to public var
        self.beodeviceinfo = scan_devicelist
        self.beo_keys = list(self.beodeviceinfo.keys())
        self.beo_keys.sort()

        self.update_devices_info()
        return


    def update_devices_info(self):
        """
        Update info for all found devices
        """
        for beo_key in self.beo_keys:
            self.update_deviceinfo(beo_key)


    def read_list_value(self, ip, api_suburl, json_element='mode'):

        api_url = '/BeoZone/Zone' + api_suburl
        mode = '-'
        active_mode = -1
        raw_mode = self.get_beo_api(ip, api_url, [json_element])
        if raw_mode != '-':
            #active_mode = self.get_beo_api(ip, api_url, [json_element, 'active'])
            #mode_list = self.get_beo_api(ip, api_url, [json_element, 'list'])
            active_mode = raw_mode.get('active', -1)
            mode_list = raw_mode.get('list', [])
            mode = 'unknown'
            if mode_list != 'unknown':
                for mode_dict in mode_list:
                    # self.plugin.logger.info("update_deviceinfo: ip = {}, mode_dict = {}, active_mode = {}".format(ip, mode_dict, active_mode))
                    if active_mode != '-1':
                        if mode_dict['id'] == active_mode:
                            mode = mode_dict['friendlyName']
                            break
                else:
                    mode = '-'
            #self.beodeviceinfo[beo_key]['videomode'] = mode.lower()
            #self.plugin.logger.info("update_deviceinfo: ip: {} videomode-friendly = {}".format(ip, mode))

        return (mode.lower(), int(active_mode))


    def update_deviceinfo(self, beo_id):
        """
        Update info for one of the found devices

        :param beo_id: device key for the device-info dict
        """
        ip = self.beodeviceinfo[beo_id]['ip']
        fn = self.beodeviceinfo[beo_id].get('FriendlyName', ip)

        # get speaker info (vol. level, muted) from B&O deivce
        speaker_info, error = self.get_speaker_info(beo_id)
        if speaker_info:
            self.plugin.logger.debug("update_deviceinfo: {} - level={}, muted={}".format(fn.ljust(16), speaker_info['level'], speaker_info['muted']))
            self.beodeviceinfo[beo_id]['volume'] = speaker_info['level']
            self.beodeviceinfo[beo_id]['muted'] = speaker_info['muted']
        if error:
            #self.plugin.logger.info("update_deviceinfo: {} - error={}".format(fn, error))
            self.plugin.logger.info("update_deviceinfo: {} speaker_info - ERROR={}, type={}".format(fn.ljust(16), error['message'], error['type']))



        self.beodeviceinfo[beo_id]['powerstate'] = self.plugin.translate(self.get_beo_api(ip, '/BeoDevice/powerManagement/standby', ['standby','powerState']))
        if self.beodeviceinfo[beo_id]['powerstate'] in ['Standby', 'unbekannt']:
            self.beodeviceinfo[beo_id]['source'] = '-'
            self.beodeviceinfo[beo_id]['videomode'] = ('-', -1)
            self.beodeviceinfo[beo_id]['audiomode'] = ('-', -1)
            self.beodeviceinfo[beo_id]['stand'] = ('-', -1)
        else:
            self.beodeviceinfo[beo_id]['source'] = self.get_beo_api(ip, '/BeoZone/Zone/ActiveSources', ['primaryExperience','source','friendlyName'])

            # get picture-mode of the B&O device
            self.beodeviceinfo[beo_id]['videomode'] = self.read_list_value(ip, '/Picture/Mode', 'mode')
            self.plugin.logger.debug("update_deviceinfo: ip: {} videomode-friendly = {}".format(ip, self.beodeviceinfo[beo_id]['videomode']))

            # get sound-mode of the B&O device
            self.beodeviceinfo[beo_id]['audiomode'] = self.read_list_value(ip, '/Sound/Mode', 'mode')
            self.plugin.logger.debug("update_deviceinfo: ip: {} audiomode-friendly = {}".format(ip, self.beodeviceinfo[beo_id]['audiomode']))

            # get stand position of the B&O device
            self.beodeviceinfo[beo_id]['stand'] = self.read_list_value(ip, '/Stand', 'stand')
            self.plugin.logger.debug("update_deviceinfo: ip: {} stand-friendly = {}".format(ip, self.beodeviceinfo[beo_id]['stand']))

        # get possible sources of the B&O device
        #raw_sources = self.get_beo_api(ip, '/BeoZone/Zone/Sources', [])
        #self.beodeviceinfo[beo_id]['sources'] = []
        #for source in raw_sources.keys():
        #    self.plugin.logger.info("update_deviceinfo: ip: {} source = {}".format(ip, source))

        return


    def send_beo_command(self, beo_id, api_url, json_elements=None):
        ip = self.beodeviceinfo[beo_id]['ip']
        self.send_beo_api('put', ip, api_url, json_elements)
        return


    def post_beo_command(self, beo_id, api_url, json_elements=None):
        ip = self.beodeviceinfo[beo_id]['ip']
        self.send_beo_api('post', ip, api_url, json_elements)
        return


    def get_beo_api(self, ip, api_url, json_elements=None):
        """
        call the b&o netlink REST api on given ip address

        :param ip:
        :param api_url:
        :param json_elements:
        :return:
        """
        result = ''
        device = 'http://' + ip + ':8080'

        result = '-'
        try:
            r = requests.get(device + api_url, timeout=0.5)
            request_result = True
        except:
            self.plugin.logger.debug("Could not get data from device {} for {}".format(device, api_url))
            request_result = False
            result = '-'

        if request_result:
            try:
                actual_r = r.json()
                if json_elements:
                    if len(json_elements) == 1:
                        result = actual_r[json_elements[0]]
                    elif len(json_elements) == 2:
                        result = actual_r[json_elements[0]][json_elements[1]]
                    elif len(json_elements) == 3:
                        result = actual_r[json_elements[0]][json_elements[1]][json_elements[2]]
                    elif len(json_elements) == 4:
                        result = actual_r[json_elements[0]][json_elements[1]][json_elements[2]][json_elements[3]]
                    #result = actual_r['standby']['powerState']
                else:
                    result = actual_r
            except:
                pass
        return result


    def send_beo_api(self, mode, ip, api_url, json_elements=None):
        """
        call the b&o netlink REST api on given ip address with a PUT request

        :param ip:
        :param api_url:
        :param json_elements:
        :return:
        """
        result = ''
        device = 'http://' + ip + ':8080'

        self.plugin.logger.info("send_beo_api: mode {}, ip {}, url {}, data {}".format(mode, ip, api_url, json_elements))
        result = '-'
        try:
            if mode.lower() == 'post':
                r = requests.post(device + api_url, data=json_elements, timeout=0.5)
            else:
                r = requests.put(device + api_url, data=json_elements, timeout=0.5)
            self.plugin.logger.info("send_beo_api: request result = {}".format(r.status_code))
            request_result = True
        except:
            self.plugin.logger.debug("Could not get data from device {} for {}".format(device, api_url))
            request_result = False
            result = 'unknown'

        return request_result

    # ----------------------------------------------------------------------------

    def get_speaker_info(self, beo_id):

        ip = self.beodeviceinfo[beo_id]['ip']
        fn = self.beodeviceinfo[beo_id].get('FriendlyName', ip)

        req_result = self.beo_get_request(ip, '/BeoZone/Zone/Sound/Volume/Speaker')
        if req_result.get('error', None):
            if req_result['error']['message'] != '':
                self.plugin.logger.info("get_speaker_info: {} - error = {}".format(fn, req_result['error']['message'] ))
            return {}, req_result['error']
        else:
            #self.plugin.logger.info("get_speaker_info: {} - speaker={}".format(fn, req_result['speaker']))
            return req_result['speaker'], {}
        return {}, {}


    def get_speaker_volume(self, beo_id):

        ip = self.beodeviceinfo[beo_id]['ip']
        fn = self.beodeviceinfo[beo_id].get('FriendlyName', ip)

        req_result = self.beo_get_request(ip, '/BeoZone/Zone/Sound/Volume/Speaker/Level')
        try:
            if req_result.get('error', None):
                if req_result['error']['message'] != '':
                    self.plugin.logger.info("get_speaker_volume: {} - error = {}".format(fn, req_result['error']['message'] ))
                return -1
            else:
                self.plugin.logger.info("get_speaker_volume: {} - level={}".format(fn, req_result['level']))
                return req_result['level']
        except Exception as e:
            self.plugin.logger.error("get_speaker_volume: {} - req_result={} - Exception = {}".format(fn, req_result, e))

        return


    def set_speaker_volume(self, beo_id, volume):

        ip = self.beodeviceinfo[beo_id]['ip']
        fn = self.beodeviceinfo[beo_id].get('FriendlyName', ip)

        data = '{'+'"level": {}'.format(volume)+'}'
        req_result = self.beo_put_request(ip, '/BeoZone/Zone/Sound/Volume/Speaker/Level', data)

        return


    def set_speaker_muted(self, beo_id, state):

        ip = self.beodeviceinfo[beo_id]['ip']
        fn = self.beodeviceinfo[beo_id].get('FriendlyName', ip)

        data = '{'+'"muted": {}'.format(str(state).lower())+'}'
        req_result = self.beo_put_request(ip, '/BeoZone/Zone/Sound/Volume/Speaker/Muted', data)

        return


    def get_stand(self, beo_id):

        ip = self.beodeviceinfo[beo_id]['ip']
        fn = self.beodeviceinfo[beo_id].get('FriendlyName', ip)

        req_result = self.beo_get_request(ip, '/BeoZone/Zone/Stand/Active')
        try:
            if req_result.get('error', None):
                if req_result['error']['message'] != '':
                    self.plugin.logger.info("get_stand: {} - error = {}".format(fn, req_result['error']['message'] ))
                return -1
            else:
                self.plugin.logger.info("get_stand: {} - level={}".format(fn, req_result['active']))
                return req_result['active']
        except Exception as e:
            self.plugin.logger.error("get_stand: {} - req_result={} - Exception = {}".format(fn, req_result, e))

        return


    def set_stand(self, beo_id, position):

        ip = self.beodeviceinfo[beo_id]['ip']
        fn = self.beodeviceinfo[beo_id].get('FriendlyName', ip)

        data = '{'+'"active": {}'.format(str(position).lower())+'}'
        req_result = self.beo_put_request(ip, '/BeoZone/Zone/Stand/Active', data)

        return

    # ----------------------------------------------------------------------------

    def beo_get_request(self, ip, api_url):
        """
        call the b&o netlink REST api on given ip address

        :param ip:
        :param api_url:
        :return:
        """
        device = 'http://' + ip + ':8080'

        try:
            r = requests.get(device + api_url, timeout=0.5)
            request_result = r.json()
        except:
            self.plugin.logger.debug("Could not get data from device {} for {}".format(device, api_url))
            request_result = {'error': { 'message': '', 'type': 'NO_RESPONSE'}}
        return request_result


    def beo_put_request(self, ip, api_url, data):
        """
        call the b&o netlink REST api on given ip address

        :param ip:
        :param api_url:
        :return:
        """
        device = 'http://' + ip + ':8080'

        try:
            r = requests.put(device + api_url, data, timeout=0.5)
            request_result = r.json()
        except:
            self.plugin.logger.debug("Could not get data from device {} for {}".format(device, api_url))
            request_result = {'error': { 'message': '', 'type': 'NO_RESPONSE'}}
        return request_result


