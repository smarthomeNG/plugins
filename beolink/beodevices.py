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


# ------------------------------------------
#    Class for handling B&O devices
# ------------------------------------------

import os
import requests

import lib.shyaml as shyaml
from lib.constants import (YAML_FILE)


class BeoDevices():

    beodeviceinfo = {}
    beo_keys = []

    def __init__(self, fromip, toip, logger, datadir, translate):

        self.fromip = fromip
        self.toip = toip
        self.logger = logger
        self.datadir = datadir
        self.translate = translate

        self.beodeviceinfo = {}
        self.beo_keys = []

        self.filename = os.path.join(self.datadir, 'bo_deviceinfo'+YAML_FILE)

        pass

    def get_devicelist(self):
        """
        Get list of Beolink devices from file
        If no devices where read from the file, the configured subnet of the network is scanned
        """
        self.beodeviceinfo = shyaml.yaml_load(self.filename, ordered=False, ignore_notfound=True)
        self.logger.info('devicelist: {}'.format(self.beodeviceinfo))
        if self.beodeviceinfo is None:
            self.scan_subnet()
        else:
            self.update_devices_info()
        self.beo_keys = list(self.beodeviceinfo.keys())
        self.beo_keys.sort()
        return

    def scan_subnet(self, scan_fromip=None, scan_toip=None):
        """
        Scans the given ip range of the network for Beolink devices

        :param scan_fromip:
        :param scan_toip:
        """
        if scan_fromip is None:
            scan_fromip = self.fromip
        if scan_toip is None:
            scan_toip = self.toip
        self.logger.info(f"Scanning network range ({scan_fromip} to {scan_toip}) for Bang & Olufsen devices")

        fromip = scan_fromip.split('.')
        toip = scan_toip.split('.')
        searchnet = '.'.join(fromip[0:3]) + '.'
        min_ip = int(fromip[3])
        max_ip = int(toip[3])

        filename = os.path.join(self.datadir, 'bo_deviceinfo' + YAML_FILE)
        scan_devicelist = shyaml.yaml_load(filename, ordered=False, ignore_notfound=True)
        self.logger.info('old list {}'.format(scan_devicelist))
        if scan_devicelist is None:
            scan_devicelist = {}

        filename = os.path.join(self.datadir, 'bo_rawinfo' + YAML_FILE)
        scan_rawinfo = shyaml.yaml_load(filename, ordered=False, ignore_notfound=True)
        #self.logger.info('old rawinfo {}'.format(scan_rawinfo))
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
                    #scan_devicelist[beo_id]['Device-Jid'] = r.headers.get('Device-Jid', '')

                    if scan_devicelist[beo_id].get('device', None) is None:
                        scan_devicelist[beo_id]['device'] = {}
                    #scan_devicelist[beo_id]['ip'] = ip
                    scan_devicelist[beo_id]['device']['ip'] = ip
                    scan_devicelist[beo_id]['device']['productType'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['productId']['productType']
                    scan_devicelist[beo_id]['device']['typeNumber'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['productId']['typeNumber']
                    scan_devicelist[beo_id]['device']['itemNumber'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['productId']['itemNumber']
                    scan_devicelist[beo_id]['device']['serialNumber'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['productId']['serialNumber']
                    scan_devicelist[beo_id]['device']['FriendlyName'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['productFriendlyName']['productFriendlyName']
                    scan_devicelist[beo_id]['device']['swVersion'] = scan_rawinfo[beo_id]['BeoDevice']['beoDevice']['software']['version']

                    #pwr = requests.get(device + '/BeoDevice/powerManagement/standby', timeout=0.5)
                    #actual_pwr = pwr.json()
                    #scan_devicelist[serial]['powerstate'] = actual_pwr['standby']['powerState']

                    #self.logger.info("- found B&O device on ip {0: <10}: {1} ({2})".format(ip, scan_devicelist[beo_id]['Device-Jid'], scan_devicelist[beo_id]['FriendlyName']))


        self.logger.info('Scanning network range ({} to {}) finished'.format(scan_fromip, scan_toip))

        filename = os.path.join(self.datadir, 'bo_deviceinfo'+YAML_FILE)
        shyaml.yaml_save(filename, scan_devicelist)

        filename = os.path.join(self.datadir, 'bo_rawinfo'+YAML_FILE)
        shyaml.yaml_save(filename, scan_rawinfo)
        self.logger.info("Bang & Olufsen device info saved to directory {}".format(self.datadir))

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
                    # self.logger.info("update_deviceinfo: ip = {}, mode_dict = {}, active_mode = {}".format(ip, mode_dict, active_mode))
                    if active_mode != '-1':
                        if mode_dict['id'] == active_mode:
                            mode = mode_dict['friendlyName']
                            break
                else:
                    mode = '-'
            #self.beodeviceinfo[beo_key]['device']['videomode'] = mode.lower()
            #self.logger.info("update_deviceinfo: ip: {} videomode-friendly = {}".format(ip, mode))

        return (mode.lower(), int(active_mode))


    def update_deviceinfo(self, beo_id):
        """
        Update info for one of the found devices

        :param beo_id: device key for the device-info dict
        """
        if self.beodeviceinfo[beo_id].get('device', None) is None:
            self.beodeviceinfo[beo_id]['device'] = {}
        if self.beodeviceinfo[beo_id].get('source', None) is None:
            self.beodeviceinfo[beo_id]['source'] = {}
        if self.beodeviceinfo[beo_id].get('content', None) is None:
            self.beodeviceinfo[beo_id]['content'] = {}
        if self.beodeviceinfo[beo_id].get('volume', None) is None:
            self.beodeviceinfo[beo_id]['volume'] = {}

        ip = self.beodeviceinfo[beo_id]['device']['ip']
        fn = self.beodeviceinfo[beo_id]['device'].get('FriendlyName', ip)

        # get speaker info (vol. level, muted) from B&O deivce
        speaker_info, error = self.get_speaker_info(beo_id)
        if speaker_info:
            self.logger.debug("update_deviceinfo: {} - level={}, muted={}".format(fn.ljust(16), speaker_info['level'], speaker_info['muted']))
            self.beodeviceinfo[beo_id]['volume']['level'] = speaker_info['level']
            self.beodeviceinfo[beo_id]['volume']['muted'] = speaker_info['muted']
        if error:
            #self.logger.info("update_deviceinfo: {} - error={}".format(fn, error))
            self.logger.info("update_deviceinfo: {} speaker_info - ERROR={}, type={}".format(fn.ljust(16), error['message'], error['type']))


        self.beodeviceinfo[beo_id]['device']['powerstate'] = self.translate(self.get_beo_api(ip, '/BeoDevice/powerManagement/standby', ['standby','powerState']))
        if self.beodeviceinfo[beo_id]['device']['powerstate'] in ['Standby', 'unbekannt']:
            self.beodeviceinfo[beo_id]['source']['source'] = '-'
            self.beodeviceinfo[beo_id]['content'] = {}
            self.beodeviceinfo[beo_id]['device']['videomode'] = ['-', -1]
            self.beodeviceinfo[beo_id]['device']['audiomode'] = ['-', -1]
            self.beodeviceinfo[beo_id]['device']['stand'] = ['-', -1]
        else:
            try:
                self.beodeviceinfo[beo_id]['source']['source'] = self.get_beo_api(ip, '/BeoZone/Zone/ActiveSources', ['primaryExperience','source','friendlyName'])

                # get picture-mode of the B&O device
                self.beodeviceinfo[beo_id]['device']['videomode'] = list(self.read_list_value(ip, '/Picture/Mode', 'mode'))
                self.logger.debug("update_deviceinfo: ip: {} videomode-friendly = {}".format(ip, self.beodeviceinfo[beo_id]['device']['videomode']))

                # get sound-mode of the B&O device
                self.beodeviceinfo[beo_id]['device']['audiomode'] = list(self.read_list_value(ip, '/Sound/Mode', 'mode'))
                self.logger.debug("update_deviceinfo: ip: {} audiomode-friendly = {}".format(ip, self.beodeviceinfo[beo_id]['device']['audiomode']))

                # get stand position of the B&O device
                self.beodeviceinfo[beo_id]['device']['stand'] = list(self.read_list_value(ip, '/Stand', 'stand'))
                self.logger.debug("update_deviceinfo: ip: {} stand-friendly = {}".format(ip, self.beodeviceinfo[beo_id]['device']['stand']))
            except Exception as ex:
                self.logger.warning(f"beodevices/update_deviceinfo: {beo_id} - Exception '{ex}'")
        # get possible sources of the B&O device
        #raw_sources = self.get_beo_api(ip, '/BeoZone/Zone/Sources', [])
        #self.beodeviceinfo[beo_id]['sources'] = []
        #for source in raw_sources.keys():
        #    self.logger.info("update_deviceinfo: ip: {} source = {}".format(ip, source))

        return


    def send_beo_command(self, beo_id, api_url, json_elements=None):
        ip = self.beodeviceinfo[beo_id]['device']['ip']
        self.send_beo_api('put', ip, api_url, json_elements)
        return


    def post_beo_command(self, beo_id, api_url, json_elements=None):
        ip = self.beodeviceinfo[beo_id]['device']['ip']
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
            self.logger.debug("Could not get data from device {} for {}".format(device, api_url))
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

        self.logger.info("send_beo_api: mode {}, ip {}, url {}, data {}".format(mode, ip, api_url, json_elements))
        result = '-'
        try:
            if mode.lower() == 'post':
                r = requests.post(device + api_url, data=json_elements, timeout=0.5)
            else:
                r = requests.put(device + api_url, data=json_elements, timeout=0.5)
            self.logger.info("send_beo_api: request result = {}".format(r.status_code))
            request_result = True
        except:
            self.logger.debug("Could not get data from device {} for {}".format(device, api_url))
            request_result = False
            result = 'unknown'

        return request_result

    # ----------------------------------------------------------------------------

    def get_speaker_info(self, beo_id):

        ip = self.beodeviceinfo[beo_id]['device']['ip']
        fn = self.beodeviceinfo[beo_id]['device'].get('FriendlyName', ip)

        req_result = self.beo_get_request(ip, '/BeoZone/Zone/Sound/Volume/Speaker')
        if req_result.get('error', None):
            if req_result['error']['message'] != '':
                self.logger.info("get_speaker_info: {} - error = {}".format(fn, req_result['error']['message'] ))
            return {}, req_result['error']
        else:
            #self.logger.info("get_speaker_info: {} - speaker={}".format(fn, req_result['speaker']))
            return req_result['speaker'], {}
        return {}, {}


    def get_speaker_volume(self, beo_id):

        ip = self.beodeviceinfo[beo_id]['device']['ip']
        fn = self.beodeviceinfo[beo_id]['device'].get('FriendlyName', ip)

        req_result = self.beo_get_request(ip, '/BeoZone/Zone/Sound/Volume/Speaker/Level')
        try:
            if req_result.get('error', None):
                if req_result['error']['message'] != '':
                    self.logger.info("get_speaker_volume: {} - error = {}".format(fn, req_result['error']['message'] ))
                return -1
            else:
                self.logger.info("get_speaker_volume: {} - level={}".format(fn, req_result['level']))
                return req_result['level']
        except Exception as e:
            self.logger.error("get_speaker_volume: {} - req_result={} - Exception = {}".format(fn, req_result, e))

        return


    def set_speaker_volume(self, beo_id, volume):

        ip = self.beodeviceinfo[beo_id]['device']['ip']
        fn = self.beodeviceinfo[beo_id]['device'].get('FriendlyName', ip)

        data = '{'+'"level": {}'.format(volume)+'}'
        req_result = self.beo_put_request(ip, '/BeoZone/Zone/Sound/Volume/Speaker/Level', data)

        return


    def set_speaker_muted(self, beo_id, state):

        ip = self.beodeviceinfo[beo_id]['device']['ip']
        fn = self.beodeviceinfo[beo_id]['device'].get('FriendlyName', ip)

        data = '{'+'"muted": {}'.format(str(state).lower())+'}'
        req_result = self.beo_put_request(ip, '/BeoZone/Zone/Sound/Volume/Speaker/Muted', data)

        return


    def get_stand(self, beo_id):

        ip = self.beodeviceinfo[beo_id]['device']['ip']
        fn = self.beodeviceinfo[beo_id]['device'].get('FriendlyName', ip)

        req_result = self.beo_get_request(ip, '/BeoZone/Zone/Stand/Active')
        try:
            if req_result.get('error', None):
                if req_result['error']['message'] != '':
                    self.logger.info("get_stand: {} - error = {}".format(fn, req_result['error']['message'] ))
                return -1
            else:
                self.logger.info("get_stand: {} - level={}".format(fn, req_result['active']))
                return req_result['active']
        except Exception as e:
            self.logger.error("get_stand: {} - req_result={} - Exception = {}".format(fn, req_result, e))

        return


    def set_stand(self, beo_id, position):

        ip = self.beodeviceinfo[beo_id]['device']['ip']
        fn = self.beodeviceinfo[beo_id]['device'].get('FriendlyName', ip)

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
            self.logger.debug("Could not get data from device {} for {}".format(device, api_url))
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
            self.logger.debug("Could not get data from device {} for {}".format(device, api_url))
            request_result = {'error': { 'message': '', 'type': 'NO_RESPONSE'}}
        return request_result


