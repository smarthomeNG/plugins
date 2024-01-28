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
    PLUGIN_VERSION = "1.0.6"
    ALLOW_MULTIINSTANCE = False

    #
    # public functions
    #

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
                             'total_time', 'play_time', 'pos', 'albumart',
                             'alarm_on', 'alarm_time', 'alarm_beep', 'passthru']

        # commands to ignore when checking for return values
        # these commands don't get / can't process (simple) return values
        self._yamaha_ignore_cmds_upd = ['state', 'preset', 'alarm_on', 'alarm_time', 'alarm_beep']

        # store items in 2D-array:
        # _yamaha_dev [host] [cmd] = item
        # also see parse_item()...
        self._yamaha_dev = {}
        # store host addresses of devices
        self._yamaha_hosts = {}

        self.srv_port = 41100
        self.srv_buffer = 1024
        self.sock = None
        self.last_total = 0

    def run(self):
        """
        Default run function

        Initializes class and sets up UDP listener.
        Main loop receives notifications and dispatches item updates
        based on notifications and triggers status updates.
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
                self.logger.debug(
                    "Received notify from unknown host {}".format(host))
            else:
                # connected device sends updates every second for
                # about 10 minutes without further interaction
                # self.logger.debug(
                #     "Yamaha unicast received {} bytes from {}: {}".format(
                #     len(data), host, data))
                data = json.loads(data.decode('utf-8'))

                # need to find lowest-level cmds in nested dicts
                # nesting is done by current zone and player
                # for now, assemble all relevant keys (main, netusb)
                # in non-nested dict. this is quite a kludge as of now...
                data_flat = {}
                try:
                    data_flat.update(data['main'])
                except:
                    pass
                try:
                    data_flat.update(data['netusb'])
                except:
                    pass

                # try all known command words...
                # this is relevant e.g. for "play_time" updates or song changes
                for cmd in self._yamaha_cmds:
                    # found it in data package?
                    if cmd in data_flat:
                        try:
                            # try to get command value and set item
                            notify_val = self._convert_value_yxc_to_plugin(data_flat[cmd], cmd, host)
                            item = self._yamaha_dev[host][cmd]
                            item(notify_val, "YamahaYXC")
                        except:
                            pass

                # device told us new info is available?
                if 'status_updated' in data_flat or 'play_info_updated' in data_flat:
                    # pull (full) status update from device
                    self._update_state(host)

                # log possible play errors
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
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except:
            pass

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
                self.logger.warn("{} not in valid commands: {}".format(
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
        if caller != "YamahaYXC" and self.alive:
            yamaha_cmd = item.conf['yamahayxc_cmd']
            yamaha_host = self._lookup_host(item)
            yamaha_payload = None

            if yamaha_cmd == 'power':
                yamaha_payload = self._build_cmd_power(item())
            elif yamaha_cmd == 'volume':
                yamaha_payload = self._build_cmd_volume(item())
            elif yamaha_cmd == 'mute':
                yamaha_payload = self._build_cmd_mute(item())
            elif yamaha_cmd == 'input':
                yamaha_payload = self._build_cmd_input(item())
            elif yamaha_cmd == 'playback':
                yamaha_payload = self._build_cmd_playback(item())
            elif yamaha_cmd == 'preset':
                yamaha_payload = self._build_cmd_preset(item())
            elif yamaha_cmd == "sleep":
                yamaha_payload = self._build_cmd_sleep(item())
            elif yamaha_cmd == "alarm_on":
                yamaha_payload = self._build_cmd_alarm_on(item())
            elif yamaha_cmd == "alarm_time":
                yamaha_payload = self._build_cmd_alarm_time(item())
            elif yamaha_cmd == "alarm_beep":
                yamaha_payload = self._build_cmd_alarm_beep(item())
            elif yamaha_cmd == "passthru":
                yamaha_payload = item()
            # no more check for "update" or "state" -> after updating item
            # _update_state is called anyway, would only duplicate update
            if yamaha_payload:
                self._submit_payload(yamaha_host, yamaha_payload)
            self._update_state(yamaha_host)
            return None

    #
    # initialization functions
    #

    def _initialize(self):
        """
        Default initialization function

        Calls _update_state for all registered hosts in _yamaha_hosts[]
        """
        self.logger.info("YamahaYXC now initializing current state")
        for yamaha_host in list(self._yamaha_hosts):
            self.logger.info(
                "Initializing items for host: {}".format(yamaha_host))
            self._update_state(yamaha_host, False)

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

    #
    # process not individually accessible items
    #

    def _update_state(self, yamaha_host, update_items=True):
        """
        retrieve state from device via cmd get_state and get_play_state

        As many items cannot be queried via yamahayxc by themselves, this
        function simply sends two state update commands and joins both
        state replies into one dict (this will probably not work with more
        than one input source and one zone!)
        Then for all relevant commands suitable return values are extracted
        and processed (items are updated)
        Return None prematurely if no network response was received
        Silently ignores invalid (None) values for commands
        """
        state = self._submit_payload(yamaha_host, self._build_cmd_get_state())
        if state is None:
            return
        state2 = self._submit_payload(yamaha_host, self._build_cmd_get_play_state())
        state2.update(state)
        state = state2

        # retrieving only single items from device is not possible
        # so just get everything and update sh.py items
        if update_items:
            for yamaha_cmd, item in self._yamaha_dev[yamaha_host].items():
                if yamaha_cmd not in self._yamaha_ignore_cmds_upd:
                    value = self._get_value_from_response(state, yamaha_cmd, yamaha_host)
                    if value is not None:
                        item(value, "YamahaYXC")

        # try updating the alarm clock state
        self._update_alarm_state(yamaha_host, update_items)

        return state

    def _update_alarm_state(self, yamaha_host, update_items=True):
        """
        parses alarm status from query response 'state'

        as alarm configuration is too complex to mirror in item configuration,
        this is excluded from the loop in _update_state()
        As alarm handling might be expanded later, this is a separate function.
        At the moment it will only be called from _update_state()
        """
        state = self._submit_payload(yamaha_host, self._build_cmd_get_alarm_state())
        if state:
            try:
                alarm = state["alarm"]
            except KeyError:
                return
            
            alarm_on = alarm["alarm_on"]
            alarm_time = alarm["oneday"]["time"]
            alarm_beep = alarm["oneday"]["beep"]

            if update_items:
                for yamaha_cmd, item in self._yamaha_dev[yamaha_host].items():
                    if yamaha_cmd == "alarm_on":
                        item(alarm_on, "YamahaYXC")
                    if yamaha_cmd == "alarm_time":
                        item(alarm_time, "YamahaYXC")
                    if yamaha_cmd == "alarm_beep":
                        item(alarm_beep, "YamahaYXC")

        return

    #
    # handle and format data values
    #

    def _get_value_from_response(self, state, cmd, host):
        """
        return value for selected command from response data

        tries to extract value for requested cmd
        returns None if state is None (network error), returns value otherwise
        returns error string if value is invalid or missing (this shoudn't happen
        and documents configuration or code error on my side - might lead to funny
        error logging)
        """
        if state is None:
            return None
        if cmd == "albumart":
            cmd = "albumart_url"
        try:
            value = state[cmd]
        except:
            return "Invalid data received (required item not found) - contact plugin author"
        return self._convert_value_yxc_to_plugin(value, cmd, host)

    def _convert_value_yxc_to_plugin(self, value, cmd, host):
        """
        convert network values to python format and
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
            return value == 'true'
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
                return int(100 * value / self.last_total)
        elif cmd == 'total_time':
            self.last_total = int(value)
            return int(value)
        elif cmd == 'albumart_url':
            value = 'http://{}{}'.format(host, value)
            return value
        elif cmd == 'alarm_on':
            return value == 'true'
        elif cmd == 'alarm_time':
            return value
        elif cmd == 'alarm_beep':
            if value == 'true':
                return True
            else:
                return False

    #
    # send network commands and receive responses
    #

    def _submit_payload(self, host, payload):
        """
        send cmd string to device and return response data as dict

        returns None on network error (no connection, device not plugged in?)
        always subscribes to unicast notification service
        log message "No payload received" probably indicates coding error or
        improper use of cmd 'passthru'

        payload can be
        - a string, will then be sent via HTTP GET
        - a list, will be sent via HTTP POST, needs
          payload[0] as URL, payload[1] as POST data
          Careful: POST data needs to be in proper JSON format
          MusicCast devices are quite picky about double quotes;
          single-quoted data is rewarded with errors!

        return data is None or a dict with json response data
        """
        if payload:

            if type(payload) is str:
                url = "http://{}/YamahaExtendedControl/{}".format(host, payload)
                headers = {
                    'X-AppName': 'MusicCast/{}'.format(self.PLUGIN_VERSION),
                    'X-AppPort': '{}'.format(self.srv_port)}
                try:
                    res = requests.get(url, headers=headers)
                    response = res.text
                    del res
                except:
                    self.logger.info("Device not answering: {}.".format(host))
                    response = None
            elif type(payload) is list:
                if len(payload) < 2:
                    self.logger.debug("Payload in list format, but insufficient arguments")
                    response = None
                else:
                    url = "http://{}/YamahaExtendedControl/{}".format(host, payload[0])
                    headers = {
                        'X-AppName': 'MusicCast/{}'.format(self.PLUGIN_VERSION),
                        'X-AppPort': '{}'.format(self.srv_port)}
                    try:
                        res = requests.post(url, data=payload[1], headers=headers)
                        response = res.text
                        del res
                    except:
                        self.logger.info("Device not answering: {}.".format(host))
                        response = None
            try:
                jdata = json.loads(response)
            except Exception:
                self.logger.debug("Invalid data received (not JSON). Data discarded.")
                jdata = None

            return jdata
        else:
            self.logger.warn("No payload received. Used 'passthru' without argument?")
            return None

    #
    # functions to create network commands
    #

    def _build_cmd_power(self, value, cmd='PUT'):
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

    def _build_cmd_input(self, value, cmd='PUT'):
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

    def _build_cmd_volume(self, value, cmd='PUT'):
        """
        return cmd string for "set volume"

        volume is numeric from 0..60
        """
        cmd = "v1/{}/setVolume?volume={}".format(self._yamaha_zone, value)
        return cmd

    def _build_cmd_mute(self, value, cmd='PUT'):
        """
        return cmd string for "set mute"
        """
        if value is True:
            cmdarg = 'true'
        elif value is False:
            cmdarg = 'false'
        cmd = "v1/{}/setMute?enable={}".format(self._yamaha_zone, cmdarg)
        return cmd

    def _build_cmd_playback(self, value, cmd="PUT"):
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

    def _build_cmd_get_state(self):
        """
        return cmd string for "get status" -> get general status for zone
        """
        cmd = "v1/{}/getStatus".format(self._yamaha_zone)
        return cmd

    def _build_cmd_get_play_state(self):
        """
        return cmd string for "get playstatus" -> get playing status

        at the moment only netusb zone is supported, no other device to test
        """
        cmd = "v1/netusb/getPlayInfo"
        return cmd

    def _build_cmd_get_alarm_state(self):
        """
        return cmd string for "get alarm status" -> get alarm clock info

        cmd will return empty result if alarm not supported
        """
        cmd = "v1/clock/getSettings"
        return cmd

    def _build_cmd_preset(self, value):
        """
        return cmd string for "set preset"

        value is integer preset index (1..)

        at the moment only netusb zone is supported (see above)
        """
        cmd = "v1/netusb/recallPreset?zone=main&num={}".format(value)
        return cmd

    def _build_cmd_sleep(self, value, cmd='PUT'):
        """
        return cmd string for "set sleep"

        volume is numeric 0 / 30 / 60 / 90 / 120 (minutes)
        """
        cmd = "v1/{}/setSleep?sleep={}".format(self._yamaha_zone, value)
        return cmd

    def _build_cmd_alarm_on(self, value, cmd='PUT'):
        """
        return cmd string for "switch alarm on/off"

        value is bool
        """
        cmd = "v1/clock/setAlarmSettings"
        data = json.dumps({"alarm_on": "true" if value else "false"})
        return ([cmd, data])

    def _build_cmd_alarm_time(self, value, cmd='PUT'):
        """
        return cmd string for "set alarm_time"

        value is string in 4 digit 24 hour time, e.g. "1430"
        """
        cmd = "v1/clock/setAlarmSettings"
        data = json.dumps({"detail": {"day": "oneday", "time": value}})
        return ([cmd, data])

    def _build_cmd_alarm_beep(self, value, cmd='PUT'):
        """
        return cmd string for "set alarm beep"

        value is bool
        """
        cmd = "v1/clock/setAlarmSettings"
        data = json.dumps({"detail": {"day": "oneday", "beep": "true" if value else "false"}})
        return ([cmd, data])
