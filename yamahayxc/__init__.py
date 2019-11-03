#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017 Sebastian Helms                    yamahayxc@shelms.de
#  based on original yamaha plugin by Raoul Thill
#########################################################################
#  This file is part of SmartHomeNG.
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
#########################################################################

# TODO
#
# - read system / call getFeatures
#   - parse distribution.server_zone_list -> read zones, system.zone_num
#   - parse zone().input_list().id -> read possible input values
#   - parse zone().func_list -> read allowed cmds
#   - parse zone().range_step -> read range/step for vol / eq

import logging
import requests
import socket
import json
from lib.model.smartplugin import SmartPlugin


class Ucast(socket.socket):
    """
    This class sets up a UDP unicast socket listener on local_port
    """
    def __init__(self, local_port):
        socket.socket.__init__(self, socket.AF_INET,
                               socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.bind(('0.0.0.0', local_port))


class YamahaYXC(SmartPlugin):
    """
    This is the main plugin class YamahaYXC to control YXC-compatible devices.
    """
    PLUGIN_VERSION = "1.0.5"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, smarthome):
        """
        Default init function
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info("Init YamahaYXC")
        self._sh = smarthome
        # valid commands for use in item configuration 'yamahayxc_cmd = ...'
        self._yamaha_cmds = ['state', 'power', 'input', 'playback', 'preset',
                             'volume', 'mute', 'track', 'artist', 'sleep',
                             'total_time', 'play_time', 'pos', 'albumart', 'passthru']
        # commands to ignore when checking for return values
        # these commands don't get / can't process (simple) return values
        self._yamaha_ignore_cmds_upd = ['state', 'preset']
        self._yamaha_dev = {}
        self._yamaha_hosts = {}
        self.srv_port = 41100
        self.srv_buffer = 1024
        self.sock = None
        self.last_total = 0

    def run(self):
        """
        Default run function

        Initializes class and sets up UDP listener.
        Main loop receives notifications and dispatches item/status updates.
        """
        self._sh.trigger('YamahaYXC', self._initialize)
        self.logger.info("YamahaYXC starting listener")
        self.alive = True
        self.sock = Ucast(self.srv_port)
        while self.alive:
            data, addr = self.sock.recvfrom(self.srv_buffer)
            try:
                host, port = addr
            except:
                self.logger.warn(
                    "Error receiving data - host/port not readable")
                return
            if host not in list(self._yamaha_dev.keys()):
                self.logger.warn(
                    "Yamaha received notify from unknown host {}".format(host))
            else:
                # this seemed good to log unter "info"
                # but running device sends updates every second...
                # self.logger.debug(
                #   "Yamaha unicast received {} bytes from {}: {}".format(
                #   len(data), host, data))
                data = json.loads(data.decode('utf-8'))
                # need to find lowest-level cmds in nested dicts
                # nesting is done by current zone and player
                # for now, assemble all relevant keys (main, netusb)
                # in non-nested dict. this is quite a kludge as of now...
                data_flat = data
                try:
                    data_flat.update(data['main'])
                except:
                    pass
                try:
                    data_flat.update(data['netusb'])
                except:
                    pass
                for cmd in self._yamaha_cmds:
                    if cmd in data_flat:
                        try:
                            notify_val = self._process_value(data_flat[cmd], cmd, host)
                            item = self._yamaha_dev[host][cmd]
                            item(notify_val, "YamahaYXC")
                        except:
                            pass
                if 'status_updated' in data_flat or 'play_info_updated' in data_flat:
                    self._update_state(host)
                if 'play_error' in data_flat:
                    if data_flat['play_error'] > 0:
                        self.logger.info(
                            "Received netusb error {} from host {}".format(
                                data_flat['play_error'], host))
        else:
            self.sock.close()

    def stop(self):
        """
        Default stop function

        Stops listener and shuts down plugin
        """
        self.alive = False
        self.sock.shutdown(socket.SHUT_RDWR)

    def _initialize(self):
        """
        Default initialization function

        Calls _update_state for all registered hosts in _yamaha_hosts[]
        """
        self.logger.info("YamahaYXC now initializing current state")
        for yamaha_host in list(self._yamaha_hosts):
            self.logger.info(
                "Initializing items for host: {}".format(yamaha_host))
            state = self._update_state(yamaha_host, False)

    def _power(self, value, cmd='PUT'):
        """
        return cmd string for "set power"

        value is boolean:
            True means "power on"
            False means "standby"
        """
        if value is True:
            cmdarg = 'on'
        elif value is False:
            cmdarg = 'standby'
        cmd = "v1/{}/setPower?power={}".format(self._yamaha_zone, cmdarg)
        return cmd

    def _input(self, value, cmd='PUT'):
        """
        return cmd string for "set input"

        value is string and device-dependent, e.g. 
            - tuner
            - cd
            - bluetooth
            - net_radio (internet radio stream)
            - server (UPNP client)
        """
        cmd = "v1/{}/setInput?input={}".format(self._yamaha_zone, value)
        return cmd

    def _volume(self, value, cmd='PUT'):
        """
        return cmd string for "set volume"

        volume is numeric from 0..60
        """
        cmd = "v1/{}/setVolume?volume={}".format(self._yamaha_zone, value)
        return cmd

    def _mute(self, value, cmd='PUT'):
        """
        return cmd string for "set mute"
        """
        if value is True:
            cmdarg = 'true'
        elif value is False:
            cmdarg = 'false'
        cmd = "v1/{}/setMute?enable={}".format(self._yamaha_zone, cmdarg)
        return cmd

    def _playback(self, value, cmd="PUT"):
        """
        return cmd string for "set playback"

        value is string and can be (for netusb)
            - play
            - stop
            - pause
            - play_pause (toggle)
            - previous
            - next
            - fast_reverse_start
            - fast_reverse_stop
            - fast_forward_start
            - fast_forward_stop
        """
        cmd = "v1/netusb/setPlayback?playback={}".format(value)
        return cmd

    def _get_state(self):
        """
        return cmd string for "get status" -> get general status for zone
        """
        cmd = "v1/{}/getStatus".format(self._yamaha_zone)
        return cmd

    def _get_play_state(self):
        """
        return cmd string for "get playstatus" -> get playing status

        at the moment only netusb zone is supported, no other device to test
        """
        cmd = "v1/netusb/getPlayInfo"
        return cmd

    def _preset(self, value):
        """
        return cmd string for "set preset"

        value is integer preset index (1..)

        at the moment only netusb zone is supported (see above)
        """
        cmd = "v1/netusb/recallPreset?zone=main&num={}".format(value)
        return cmd

    def _sleep(self, value, cmd='PUT'):
        """
        return cmd string for "set sleep"

        volume is numeric 0 / 30 / 60 / 90 / 120 (minutes)
        """
        cmd = "v1/{}/setSleep?sleep={}".format(self._yamaha_zone, value)
        return cmd

    def _get_value(self, notify_cmd, yamaha_host):
        """        
        gets value for notify_cmd from yamaha_host

        builds cmd string and runs network query
        calls _return_value to process value and assigns to item

        returns without further action if no network response is received
        """
        yamaha_payload = None
        if notify_cmd in ['power', 'volume', 'mute', 'input', 'sleep']:
            yamaha_payload = self._get_state()
        elif notify_cmd in ['track', 'artist', 'albumart', 
                            'play_time', 'total_time', 'playback']:
            yamaha_payload = self._get_play_state()

        if yamaha_payload:
            res = self._submit_payload(yamaha_host, yamaha_payload)
            if res is None:
                return
            value = self._return_value(res, notify_cmd, yamaha_host)
            if notify_cmd == "play_time" and value < 0:
                return
            else:
                item = self._yamaha_dev[yamaha_host][notify_cmd]
                item(value, "YamahaYXC")

    def _process_value(self, value, cmd, host):
        """
        return processed value depending on command

        formats and returns value from raw input value
        Needs valid cmd and value, no checking for None value
        called by self._return_value and self.run (push notify loop)
        """
        if cmd == 'input':
            return value
        elif cmd == 'volume':
            return int(value)
        elif cmd == 'mute':
            if value == 'false':
                return False
            elif value == 'true':
                return True
            return value
        elif cmd == 'power':
            if value == 'standby':
                return False
            elif value == 'on':
                return True
            return value
        elif cmd == 'playback':
            return value
        elif cmd == "sleep":
            return value
        elif cmd == 'track':
            return value
        elif cmd == 'artist':
            return value
        elif cmd == 'play_time':
            if self.last_total == 0:
                return (-1)
            else:
                return int(100*value/self.last_total)
        elif cmd == 'total_time':
            self.last_total = int(value)
            return int(value)
        elif cmd == 'albumart_url':
            value = 'http://{}{}'.format(host, value)
            return value

    def _return_value(self, state, cmd, host):
        """
        return selected value from response data

        transforms "state" response to json and extracts requested value
        returns None if state is None (network error), returns value otherwise
        returns error string if value is invalid or missing (this shoudn't happen
        and documents configuration or code error on my side)
        """
        if state is None:
            return None
        if cmd == "albumart":
            cmd = "albumart_url"
        try:
            jdata = json.loads(state)
        except Exception:
            return "Invalid data received (not JSON)"
        try:
            value = jdata[cmd]
        except:
            return "Invalid data received (required item not found)"
        return self._process_value(value, cmd, host)

    def _submit_payload(self, host, payload):
        """
        send cmd string to device and return response data

        returns None on network error (no connection, device not plugged in?)
        always subscribes to unicast notification service
        log message "No payload received" probably indicates coding error or 
        improper use of cmd 'passthru'
        """
        if payload:
            url = "http://{}/YamahaExtendedControl/{}".format(host, payload)
            headers = {
                'X-AppName': 'MusicCast/{}'.format(self.PLUGIN_VERSION),
                'X-AppPort': '{}'.format(self.srv_port)}
            try:
                res = requests.get(url, headers=headers)
                response = res.text
                del res
            except:
                self.logger.warn("Device not answering: {}.".format(host))
                response = None
            return response
        else:
            self.logger.warn("No payload received. Used 'passthru' without argument?")
            return None

    def _lookup_host(self, item):
        """
        get host IP stored for submitted item

        this does not work with nested items in item config, so don't nest items!
        """
        parent = item.return_parent()
        yamaha_host = socket.gethostbyname(parent.conf['yamahayxc_host'])
        return yamaha_host

    def _lookup_zone(self, item):
        """
        get zone config for item

        again, don't nest items.
        This is a stub function in preparation for later extension of the plugin
        to multiple zones. Maybe flexible config of multiple zones for items
        might become necessary -> rethink this approach then
        """
        parent = item.return_parent()
        yamaha_zone = parent.conf['yamahayxc_zone']
        return yamaha_zone

    def _add_host_info(self, host):
        """
        store local interface IP for connection to a given host

        just exists in case the server is multihomed. in most cases not necessary
        """
        try:
            local_ip = self._yamaha_hosts[host]
            return
        except:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((host, 80))
            local_ip = s.getsockname()[0]
            s.close()
            self._yamaha_hosts[host] = local_ip

    def parse_item(self, item):
        """
        parse all items at startup

        This function is called by the SmartPlugin manager in sh.py for every
        item. If item config "yamahayxc_cmd" is present, item ist stored together
        with associated host and zone.
        Returns update function for the item (update_item())
        """
        if 'yamahayxc_cmd' in item.conf:
            yamaha_host = self._lookup_host(item)
            self._add_host_info(yamaha_host)
            yamaha_zone = self._lookup_zone(item)
            self._yamaha_zone = yamaha_zone
            yamaha_cmd = item.conf['yamahayxc_cmd'].lower()
            if yamaha_cmd not in self._yamaha_cmds:
                self.logger.warning("{} not in valid commands: {}".format(
                    yamaha_cmd, self._yamaha_cmds))
                return None
            else:
                try:
                    self._yamaha_dev[yamaha_host][yamaha_cmd] = item
                except KeyError:
                    self._yamaha_dev[yamaha_host] = {}
                    self._yamaha_dev[yamaha_host][yamaha_cmd] = item
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        recall function if item is modified in sh.py

        Only for "write" commands: calls function to build cmd string 
        for given item and runs network query to execute cmd
        In any case _update_state is called afterwards to update sh.py items
        """
        if caller != "YamahaYXC":
            yamaha_cmd = item.conf['yamahayxc_cmd']
            yamaha_host = self._lookup_host(item)
            yamaha_payload = None

            if yamaha_cmd == 'power':
                yamaha_payload = self._power(item())
            elif yamaha_cmd == 'volume':
                yamaha_payload = self._volume(item())
            elif yamaha_cmd == 'mute':
                yamaha_payload = self._mute(item())
            elif yamaha_cmd == 'input':
                yamaha_payload = self._input(item())
            elif yamaha_cmd == 'playback':
                yamaha_payload = self._playback(item())
            elif yamaha_cmd == 'preset':
                yamaha_payload = self._preset(item())
            elif yamaha_cmd == "sleep":
                yamaha_payload = self._sleep(item())
            elif yamaha_cmd == "passthru":
                yamaha_payload = item()
            # no more check for "update" or "state" -> after updating item
            # _update_state is called in any way, would only duplicate update
            if yamaha_payload:
                self._submit_payload(yamaha_host, yamaha_payload)
            self._update_state(yamaha_host)
            return None

    def _update_state(self, yamaha_host, update_items=True):
        """
        retrieve state from device via cmd _get_state and _get_play_state

        As many items cannot be queried via yamahayxc by themselves, this
        function simply sends two state update commands and flattens both
        state replies into one flat dict (this is a kludge and does only work
        with netusb and a single zone!!!!!)
        Then for all relevant commands suitable return values are extracted
        and processed (items are updated)
        Return None prematurely if no network response was received
        Silently ignores invalid (None) values for commands
        """
        state1 = self._submit_payload(yamaha_host, self._get_state())
        if state1 is None:
            return
        state2 = self._submit_payload(yamaha_host, self._get_play_state())
        ostate = json.loads(state1)
        ostate.update(json.loads(state2))
        state = json.dumps(ostate)
        # retrieving only single items from device is not possible
        # so just get everything and update sh.py items
        if update_items:
            for yamaha_cmd, item in self._yamaha_dev[yamaha_host].items():
                #self.logger.debug(
                #    "Updating cmd {} for item {}".format(yamaha_cmd, item))
                if yamaha_cmd not in self._yamaha_ignore_cmds_upd:
                    value = self._return_value(state, yamaha_cmd, yamaha_host)
                    if value is not None:
                        item(value, "YamahaYXC")
        return state
