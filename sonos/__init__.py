#!/usr/bin/env python3
import http
import logging
import lib.connection
import lib.tools
import re
import threading
import json
import requests
import time
from lib.model.smartplugin import SmartPlugin

EXPECTED_BROKER_VERSION = "1.0"
sonos_speaker = {}


class UDPDispatcher(lib.connection.Server):
    def __init__(self, ip, port, sh):
        self._logger = logging.getLogger('sonos')
        lib.connection.Server.__init__(self, ip, port, proto='UDP')
        self.dest = 'udp:' + ip + ':{port}'.format(port=port)
        self._logger.debug('starting udp listener with {url}'.format(url=self.dest))
        self._sh = sh
        self.connect()

    def handle_connection(self):
        try:
            data, address = self.socket.recvfrom(10000)
            address = "{}:{}".format(address[0], address[1])
            self._logger.debug("{}: incoming connection from {}".format('sonos', address))
        except Exception as err:
            self._logger.error("{}: {}".format(self._name, err))
            return

        try:
            sonos = json.loads(data.decode('utf-8').strip())
            uid = sonos['uid']

            if not uid:
                self._logger.error("No uid found in sonos udp response!\nResponse: {}")
            if uid not in sonos_speaker:
                self._logger.warning("no sonos speaker configured with uid '{uid}".format(uid=uid))
                return

            for key, value in sonos.items():
                instance_var = getattr(sonos_speaker[uid], key)

                if isinstance(instance_var, list):
                    for item in instance_var:
                        item(value, 'Sonos', '')

        except Exception as err:
            self._logger.error("Error parsing sonos broker response!\nError: {}".format(err))


class Sonos(SmartPlugin):
    PLUGIN_VERSION = "1.3.0.1"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh, listen_host='0.0.0.0', listen_port=9999, broker_url=None, refresh=120):

        self._sonoslock = threading.Lock()
        self._lan_ip = get_lan_ip()
        self._logger = logging.getLogger('sonos')
        self._dpt3_vol_step = 1
        self._dpt3_vol_time = 1
        self._dpt3_vol_max = 100

        if not self._lan_ip:
            self._logger.critical("Could not fetch internal ip address. Set it manually!")
            self.alive = False
            return

        self._logger.info("using local ip address {ip}".format(ip=self._lan_ip))

        # check broker variable
        if broker_url:
            self._broker_url = broker_url
        else:
            self._broker_url = "http://{ip}:12900".format(ip=self._lan_ip)
            if self._broker_url:
                self._logger.warning("No broker url given, assuming current ip and default broker port: {url}".
                                     format(url=self._broker_url))
            else:
                self._logger.error("Could not detect broker url !!!")
                return

        # normalize broker url
        if not self._broker_url.startswith('http://'):
            self._broker_url = "http://{url}".format(url=self._broker_url)

        # version check against Sonos Broker

        broker_version = self._send_cmd(SonosCommand.sonos_broker_version())
        self._logger.debug("Sonos broker version: {version}".format(version=broker_version))
        try:
            if EXPECTED_BROKER_VERSION != broker_version:
                self._logger.warning("This plugin is desgined to work with Sonos Broker version {version}. "
                                     "Your plugin version is probably out-of-date or too new. "
                                     "Please update your plugin and/or the Sonos Broker Server".format(
                    version=EXPECTED_BROKER_VERSION))
        except Exception:
            self._logger.warning("Unknown Sonos broker version string '{version_string}.'".
                                 format(version_string=broker_version))

        self._listen_host = listen_host
        self._listen_port = listen_port
        self._sh = sh
        self._command = SonosCommand()

        self._logger.debug('refresh sonos speakers every {refresh} seconds'.format(refresh=refresh))

        # add current_state command to scheduler
        self._sh.scheduler.add('sonos-update', self._subscribe, cycle=refresh)

        # start UDP listener
        UDPDispatcher(self._listen_host, self._listen_port, self._sh)

    def run(self):
        self.alive = True
        self._subscribe()

    def _subscribe(self):
        """
        Subscribe the plugin to the Sonos Broker
        """
        self._logger.debug('(re)registering to sonos broker server ...')
        self._send_cmd(SonosCommand.subscribe(self._lan_ip, self._listen_port))

        for uid, speaker in sonos_speaker.items():
            self._send_cmd(SonosCommand.current_state(uid))

    def _unsubscribe(self):
        """
        Unsubscribe the plugin from the Sonos Broker
        """
        self._logger.debug('unsubscribing from sonos broker server ...')
        self._send_cmd(SonosCommand.unsubscribe(self._lan_ip, self._listen_port))

    def stop(self):
        """
        Will be executed, if Smarthome.py receives a terminate signal
        """
        # try to unsubscribe the plugin from the Sonos Broker
        self._unsubscribe()
        self.alive = False

    def _resolve_uid(self, item):
        uid = None

        if 'volume_dpt3.helper' in item._name:
            parent_item = item.return_parent().return_parent().return_parent()
        else:
            parent_item = item.return_parent()
        if (parent_item is not None) and ('sonos_uid' in parent_item.conf):
            uid = parent_item.conf['sonos_uid'].lower()
        else:
            self._logger.warning("sonos: could not resolve sonos_uid".format(item))
        return uid

    def parse_item(self, item):

        if 'sonos_recv' in item.conf:
            uid = self._resolve_uid(item)

            if uid is None:
                return None
            attr = item.conf['sonos_recv']

            self._logger.debug("sonos: {} receives updates by {}".format(item, attr))

            if not uid in sonos_speaker:
                sonos_speaker[uid] = SonosSpeaker()

            attr_list = getattr(sonos_speaker[uid], attr)

            if not item in attr_list:
                attr_list.append(item)

        if 'sonos_send' in item.conf:
            uid = self._resolve_uid(item)
            if uid is None:
                return None

            attr = item.conf['sonos_send']
            self._logger.debug("sonos: {} is send to {}".format(item, attr))
            return self._update_item

        if self.has_iattr(item.conf, 'sonos_volume_dpt3'):
            if not self.has_iattr(item.conf, 'sonos_vol_step'):
                item.conf['sonos_vol_step'] = self._dpt3_vol_step
                self._logger.warning("Sonos: no sonos_vol_step defined, using default value {step}.".
                                     format(step=self._dpt3_vol_step))

            if not self.has_iattr(item.conf, 'sonos_vol_time'):
                item.conf['sonos_vol_time'] = self._dpt3_vol_time
                self._logger.warning("Sonos: no sonos_vol_time defined, using default value {time}.".
                                     format(time=self._dpt3_vol_time))

            if not self.has_iattr(item.conf, 'sonos_vol_max'):
                item.conf['sonos_vol_max'] = self._dpt3_vol_max
                self._logger.warning("Sonos: no sonos_vol_max defined, using default value {max}.".
                                     format(max=self._dpt3_vol_max))

            return self._handle_volume_dpt3

        return None

    def _handle_volume_dpt3(self, item, caller=None, source=None, dest=None):
        self._logger.debug(caller)
        if caller != 'Sonos':

            volume_helper = None

            volume_item = item.return_parent()
            if volume_item is None:
                self._logger.warning("Sonos: no parent volume item found for volume_dpt3 item!")
                return

            dpt3_helper_name = '{}.helper'.format(item._name)

            for child in item.return_children():
                if child._name == dpt3_helper_name:
                    volume_helper = child

            if volume_helper is None:
                self._logger.warning("Sonos: no child helper item found for volume_dpt3 item!")
                return

            volume_helper(volume_item())
            vol_step = int(item.conf['sonos_vol_step'])
            vol_time = int(item.conf['sonos_vol_time'])
            vol_max = int(item.conf['sonos_vol_max'])

            if item()[1] == 1:
                if item()[0] == 1:
                    # up
                    volume_helper.fade(vol_max, vol_step, vol_time)
                else:
                    # down
                    volume_helper.fade(0-vol_step, vol_step, vol_time)
            else:
                volume_helper(int(volume_helper() + 1))
                volume_helper(int(volume_helper() - 1))

    def parse_logic(self, logic):
        pass

    def _update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'Sonos':
            value = item()

            if 'sonos_send' in item.conf:
                uid = self._resolve_uid(item)

                if not uid:
                    return None
                command = item.conf['sonos_send']

                cmd = ''

                if command == 'mute':
                    if isinstance(value, bool):
                        group_item_name = '{}.group_command'.format(item._name)
                        group_command = 0
                        for child in item.return_children():
                            if child._name.lower() == group_item_name.lower():
                                group_command = child()
                                break
                        cmd = self._command.mute(uid, value, group_command)

                if command == 'led':
                    if isinstance(value, bool):
                        group_item_name = '{}.group_command'.format(item._name)
                        group_command = 0
                        for child in item.return_children():
                            if child._name.lower() == group_item_name.lower():
                                group_command = child()
                                break
                        cmd = self._command.led(uid, value, group_command)

                if command == 'play':
                    if isinstance(value, bool):
                        cmd = self._command.play(uid, value)

                if command == 'pause':
                    if isinstance(value, bool):
                        cmd = self._command.pause(uid, value)

                if command == 'stop':
                    if isinstance(value, bool):
                        cmd = self._command.stop(uid, value)

                if command == 'volume':
                    if isinstance(value, int):
                        group_item_name = '{}.group_command'.format(item._name)
                        group_command = 0
                        for child in item.return_children():
                            if child._name.lower() == group_item_name.lower():
                                group_command = child()
                                break
                        value = 0 if value < 0 else value
                        cmd = self._command.volume(uid, value, group_command)

                if command == 'max_volume':
                    if isinstance(value, int):
                        group_item_name = '{}.group_command'.format(item._name)
                        group_command = 0
                        for child in item.return_children():
                            if child._name.lower() == group_item_name.lower():
                                group_command = child()
                                break
                        cmd = self._command.max_volume(uid, value, group_command)

                if command == 'bass':
                    if isinstance(value, int):
                        group_item_name = '{}.group_command'.format(item._name)
                        group_command = 0
                        for child in item.return_children():
                            if child._name.lower() == group_item_name.lower():
                                group_command = child()
                                break
                        cmd = self._command.bass(uid, value, group_command)

                if command == 'balance':
                    if isinstance(value, int):
                        group_item_name = '{}.group_command'.format(item._name)
                        group_command = 0
                        for child in item.return_children():
                            if child._name.lower() == group_item_name.lower():
                                group_command = child()
                                break
                        cmd = self._command.balance(uid, value, group_command)

                if command == 'treble':
                    if isinstance(value, int):
                        group_item_name = '{}.group_command'.format(item._name)
                        group_command = 0
                        for child in item.return_children():
                            if child._name.lower() == group_item_name.lower():
                                group_command = child()
                                break
                        cmd = self._command.treble(uid, value, group_command)

                if command == 'nightmode':
                    if isinstance(value, bool):
                        cmd = self._command.nightmode(uid, value)

                if command == 'loudness':
                    if isinstance(value, bool):
                        group_item_name = '{}.group_command'.format(item._name)
                        group_command = 0
                        for child in item.return_children():
                            if child._name.lower() == group_item_name.lower():
                                group_command = child()
                                break
                        cmd = self._command.loudness(uid, value, group_command)

                if command == 'playmode':
                    value = value.lower().strip('\'').strip('\"')
                    if value in ['normal', 'shuffle_norepeat', 'shuffle', 'repeat_all']:
                        cmd = self._command.playmode(uid, value)
                    else:
                        self._logger.warning(
                            "Ignoring PLAYMODE command. Value {value} not a valid paramter!".format(value=value))

                if command == 'next':
                    cmd = self._command.next(uid)

                if command == 'previous':
                    cmd = self._command.previous(uid)

                if command == 'play_uri':
                    cmd = self._command.play_uri(uid, value)

                if command == 'play_tunein':
                    cmd = self._command.play_tunein(uid, value)

                if command == 'play_snippet':
                    volume_item_name = '{}.volume'.format(item._name)
                    group_item_name = '{}.group_command'.format(item._name)
                    fade_item_name = '{}.fade_in'.format(item._name)
                    volume = -1
                    group_command = 0
                    fade_in = 0
                    for child in item.return_children():
                        if child._name.lower() == volume_item_name.lower():
                            volume = child()
                        if child._name.lower() == group_item_name.lower():
                            group_command = child()
                        if child._name.lower() == fade_item_name.lower():
                            fade_in = child()
                    cmd = self._command.play_snippet(uid, value, volume, group_command, fade_in)

                if command == 'play_tts':
                    volume_item_name = '{}.volume'.format(item._name)
                    language_item_name = '{}.language'.format(item._name)
                    group_item_name = '{}.group_command'.format(item._name)
                    force_item_name = '{}.force_stream_mode'.format(item._name)
                    fade_item_name = '{}.fade_in'.format(item._name)
                    volume = -1
                    language = 'de'
                    group_command = 0
                    force_stream_mode = 0
                    fade_in = 0
                    for child in item.return_children():
                        if child._name.lower() == volume_item_name.lower():
                            volume = child()
                        if child._name.lower() == language_item_name.lower():
                            language = child()
                        if child._name.lower() == group_item_name.lower():
                            group_command = child()
                        if child._name.lower() == force_item_name.lower():
                            force_stream_mode = child()
                        if child._name.lower() == fade_item_name.lower():
                            fade_in = child()
                        if child._name.lower() == fade_item_name.lower():
                            fade_in = child()
                    cmd = self._command.play_tts(uid, value, language, volume, group_command, fade_in,
                                                 force_stream_mode)

                if command == 'load_sonos_playlist':
                    clear_item_name = '{}.clear_queue'.format(item._name)
                    play_item_name = '{}.play_after_insert'.format(item._name)
                    clear_queue = 0
                    play_after_insert = 0
                    for child in item.return_children():
                        if child._name.lower() == clear_item_name.lower():
                            clear_queue = child()
                        if child._name.lower() == play_item_name.lower():
                            play_after_insert = child()
                    cmd = self._command.load_sonos_playlist(uid, value, play_after_insert, clear_queue)

                if command == 'seek':
                    if not re.match(r'^[0-9][0-9]?:[0-9][0-9]:[0-9][0-9]$', value):
                        self._logger.warning('invalid timestamp for sonos seek command, use HH:MM:SS format')
                        cmd = None
                    else:
                        cmd = self._command.seek(uid, value)

                if command == 'current_state':
                    cmd = self._command.current_state(uid)

                if command == 'join':
                    cmd = self._command.join(uid, value)

                if command == 'unjoin':
                    play_item_name = '{}.play'.format(item._name)
                    play = 0
                    for child in item.return_children():
                        if child._name.lower() == play_item_name.lower():
                            play = child()
                            break
                    cmd = self._command.unjoin(uid, play)

                if command == 'partymode':
                    cmd = self._command.partymode(uid)

                if command == 'volume_up':
                    group_item_name = '{}.group_command'.format(item._name)
                    group_command = 0
                    for child in item.return_children():
                        if child._name.lower() == group_item_name.lower():
                            group_command = child()
                            break
                    cmd = self._command.volume_up(uid, group_command)

                if command == 'volume_down':
                    group_item_name = '{}.group_command'.format(item._name)
                    group_command = 0
                    for child in item.return_children():
                        if child._name.lower() == group_item_name.lower():
                            group_command = child()
                            break
                    cmd = self._command.volume_down(uid, group_command)

                if command == 'clear_queue':
                    if value in ['y', '1', 'Y', 1, 'yes']:
                        cmd = self._command.clear_queue(uid)

                if command == 'wifi_state':
                    if isinstance(value, bool):
                        persistent_item_name = '{}.persistent'.format(item._name)
                        persistent = 0
                        for child in item.return_children():
                            if child._name.lower() == persistent_item_name.lower():
                                if value != 0 and persistent == 1:
                                    self._logger.warning("command wifi_state: persistent parameter with value '1' will"
                                                         "only affect wifi_state with value '1' (the wifi interface will"
                                                         "remain deactivated after reboot). Ignoring 'persistent' "
                                                         "parameter.")
                                else:
                                    persistent = child()
                                break
                        cmd = self._command.wifi_state(uid, value, persistent)

                if cmd:
                    self._send_cmd(cmd)
                    return
        return None

    def _send_cmd(self, payload):
        try:
            self._logger.debug("Sending request: {0}".format(payload))

            headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
            response = requests.post(self._broker_url, data=json.dumps(payload), headers=headers)

            html_start = "<html><head><title>Sonos Broker</title></head><body>"
            html_end = "</body></html>"

            if response.status_code == 200:
                self._logger.info("Sonos: Message %s %s successfully sent - %s %s" %
                                  (self._broker_url, payload, response.status_code, response.reason))
                return response.text.replace(html_start, "", 1).replace(html_end, "", 1)

            else:
                self._logger.warning("Sonos: Could not send message %s %s - %s %s" %
                                     (self._broker_url, payload, response.status_code, response.text))
                return None
        except Exception as e:
            self._logger.warning(
                "Could not send sonos notification: {0}. Error: {1}".format(payload, e))

    def _send_cmd_response(self, cmd):
        try:
            data = ''
            conn = http.client.HTTPConnection(self._broker_url)

            conn.request("GET", cmd)
            response = conn.getresponse()
            if response.status == 200:
                self._logger.info("Sonos: Message %s %s successfully sent - %s %s" %
                                  (self._broker_url, cmd, response.status, response.reason))
                data = response.read()
            else:
                self._logger.warning("Sonos: Could not send message %s %s - %s %s" %
                                     (self._broker_url, cmd, response.status, response.reason))
            conn.close()
            return data

        except Exception as e:
            self._logger.warning(
                "Could not send sonos notification: {0}. Error: {1}".format(cmd, e))

            self._logger.debug("Sending request: {0}".format(cmd))

    def load_sonos_playlist(self, uid, sonos_playlist, play_after_insert=0, clear_queue=0):
        return self._send_cmd(SonosCommand.load_sonos_playlist(uid, sonos_playlist, play_after_insert,
                                                               clear_queue))

    def get_favorite_radiostations(self, start_item=0, max_items=50):
        return self._send_cmd_response(SonosCommand.favradio(start_item, max_items))

    def refresh_media_library(self, display_option='none'):
        return self._send_cmd(SonosCommand.refresh_media_library(display_option))

    def version(self):
        return "v1.0\t2017-02-15"

    def discover(self):
        return self._send_cmd(SonosCommand.discover())


class SonosSpeaker():
    def __init__(self):
        self.uid = []
        self.ip = []
        self.model = []
        self.model_number = []
        self.display_version = []
        self.household_id = []
        self.zone_name = []
        self.zone_icon = []
        self.is_coordinator = []
        self.serial_number = []
        self.software_version = []
        self.hardware_version = []
        self.mac_address = []
        self.playlist_position = []
        self.playlist_total_tracks = []
        self.volume = []
        self.mute = []
        self.led = []
        self.streamtype = []
        self.stop = []
        self.play = []
        self.pause = []
        self.track_title = []
        self.track_artist = []
        self.track_duration = []
        self.track_position = []
        self.track_album_art = []
        self.track_album = []
        self.track_uri = []
        self.radio_station = []
        self.radio_show = []
        self.status = []
        self.max_volume = []
        self.additional_zone_members = []
        self.bass = []
        self.treble = []
        self.loudness = []
        self.playmode = []
        self.nightmode = []
        self.alarms = []
        self.tts_local_mode = []
        self.wifi_state = []
        self.balance = []
        self.sonos_playlists = []
        self.transport_actions = []


class SonosCommand:
    @staticmethod
    def subscribe(ip, port):
        return {
            'command': 'client_subscribe',
            'parameter': {
                'ip': ip,
                'port': port,
            }
        }

    @staticmethod
    def unsubscribe(ip, port):
        return {
            'command': 'client_unsubscribe',
            'parameter': {
                'ip': ip,
                'port': port,
            }
        }

    @staticmethod
    def current_state(uid, group_command=0):
        return {
            'command': 'current_state',
            'parameter': {
                'uid': '{uid}'.format(uid=uid),
                'group_command': int(group_command)
            }
        }

    @staticmethod
    def join(uid, value):
        return {
            'command': 'join',
            'parameter': {
                'join_uid': '{j_uid}'.format(j_uid=value),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def unjoin(uid, play=0):
        return {
            'command': 'unjoin',
            'parameter': {
                'uid': '{uid}'.format(uid=uid),
                'play': play
            }
        }

    @staticmethod
    def mute(uid, value, group_command=0):
        return {
            'command': 'set_mute',
            'parameter': {
                'uid': '{uid}'.format(uid=uid),
                'mute': int(value),
                'group_command': int(group_command)
            }
        }

    @staticmethod
    def balance(uid, value, group_command=0):
        return {
            'command': 'set_balance',
            'parameter': {
                'uid': '{uid}'.format(uid=uid),
                'balance': int(value),
                'group_command': int(group_command)
            }
        }

    @staticmethod
    def next(uid):
        return {
            'command': 'next',
            'parameter': {
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def previous(uid):
        return {
            'command': 'previous',
            'parameter': {
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def play(uid, value):
        return {
            'command': 'set_play',
            'parameter': {
                'play': int(value),
                'uid': '{uid}'.format(uid=uid),
            }
        }

    @staticmethod
    def pause(uid, value):
        return {
            'command': 'set_pause',
            'parameter': {
                'pause': int(value),
                'uid': '{uid}'.format(uid=uid),
            }
        }

    @staticmethod
    def stop(uid, value):
        return {
            'command': 'set_stop',
            'parameter': {
                'stop': int(value),
                'uid': '{uid}'.format(uid=uid),
            }
        }

    @staticmethod
    def led(uid, value, group_command=0):
        return {
            'command': 'set_led',
            'parameter': {
                'led': int(value),
                'group_command': int(group_command),
                'uid': '{uid}'.format(uid=uid),
            }
        }

    @staticmethod
    def volume(uid, value, group_command=0):
        return {
            'command': 'set_volume',
            'parameter': {
                'uid': '{uid}'.format(uid=uid),
                'volume': int(value),
                'group_command': int(group_command)
            }
        }

    @staticmethod
    def volume_up(uid, group_command=0):
        return {
            'command': 'volume_up',
            'parameter': {
                'group_command': int(group_command),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def volume_down(uid, group_command=0):
        return {
            'command': 'volume_down',
            'parameter': {
                'group_command': int(group_command),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def max_volume(uid, value, group_command):
        return {
            'command': 'set_max_volume',
            'parameter': {
                'max_volume': int(value),
                'group_command': int(group_command),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def seek(uid, value):
        return {
            'command': 'set_track_position',
            'parameter': {
                'timestamp': '{value}'.format(value=value),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def play_uri(uid, uri):
        return {
            'command': 'play_uri',
            'parameter': {
                'uri': '{uri}'.format(uri=uri),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def play_tunein(uid, station_name):
        return {
            'command': 'play_tunein',
            'parameter': {
                'uid': uid.lower(),
                'station_name': station_name
            }
        }

    @staticmethod
    def play_snippet(uid, uri, volume, group_command, fade_in):
        return {
            'command': 'play_snippet',
            'parameter': {
                'uri': '{uri}'.format(uri=uri),
                'uid': '{uid}'.format(uid=uid),
                'volume': int(volume),
                'fade_in': int(fade_in),
                'group_command': group_command
            }
        }

    @staticmethod
    def play_tts(uid, tts, language, volume, group_command, force_stream_mode, fade_in):
        return {
            'command': 'play_tts',
            'parameter': {
                'tts': '{tts}'.format(tts=tts),
                'language': '{language}'.format(language=language),
                'volume': int(volume),
                'group_command': int(group_command),
                'force_stream_mode': int(force_stream_mode),
                'fade_in': int(fade_in),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def partymode(uid):
        return {
            'command': 'partymode',
            'parameter': {
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def bass(uid, value, group_command=0):
        return {
            'command': 'set_bass',
            'parameter': {
                'bass': int(value),
                'group_command': int(group_command),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def playmode(uid, value):
        return {
            'command': 'set_playmode',
            'parameter': {
                'playmode': '{playmode}'.format(playmode=value),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def treble(uid, value, group_command=0):
        return {
            'command': 'set_treble',
            'parameter': {
                'treble': int(value),
                'group_command': int(group_command),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def loudness(uid, value, group_command=0):
        return {
            'command': 'set_loudness',
            'parameter': {
                'loudness': int(value),
                'group_command': int(group_command),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def nightmode(uid, value):
        return {
            'command': 'set_nightmode',
            'parameter': {
                'nightmode': int(value),
                'uid': '{uid}'.format(uid=uid)
            }
        }

    @staticmethod
    def sonos_playlists(uid):
        return {
            'command': 'sonos_playlists',
            'parameter': {
                'uid': uid.lower(),
            }
        }

    @staticmethod
    def wifi_state(uid, wifi_state, persistent):
        return {
            'command': 'set_wifi_state',
            'parameter': {
                'uid': uid.lower(),
                'wifi_state': wifi_state,
                'persistent': persistent
            }
        }

    @staticmethod
    def load_sonos_playlist(uid, sonos_playlist, play_after_insert, clear_queue):
        return {
            'command': 'load_sonos_playlist',
            'parameter': {
                'uid': uid.lower(),
                'sonos_playlist': sonos_playlist,
                'play_after_insert': play_after_insert,
                'clear_queue': clear_queue
            }
        }

    @staticmethod
    def sonos_broker_version():
        return {
            'command': 'sonos_broker_version'
        }

    @staticmethod
    def favradio(start_item, max_items):
        _logger = logging.getLogger('sonos')
        try:
            start_item = int(start_item)
        except ValueError:
            _logger.error('favradio: command ignored - start_item value \'{}\' is not an integer'.format(start_item))
            return
        try:
            max_items = int(max_items)
        except ValueError:
            _logger.error('favradio: command ignored - max_items value \'{}\' is not an integer'.format(max_items))
            return
        return {
            'command': 'get_favorite_radio_stations',
            'parameter': {
                'start_item': start_item,
                'max_items': max_items
            }
        }

    @staticmethod
    def refresh_media_library(display_option):
        _logger = logging.getLogger('sonos')
        display_option = display_option.lower()
        if display_option not in ['none', 'itunes', 'wmp']:
            _logger.warning("refresh_media_library: invalid 'display_option' value '{val}'. Value has to be 'none', "
                            "'itunes' or 'wmp'. Using default value 'none'.".format(val=display_option))
            display_option = 'none'
        return {
            'command': 'refresh_media_library',
            'parameter': {
                'display_option': display_option.upper()
            }
        }

    @staticmethod
    def discover():
        return {'command': 'discover'}

    @staticmethod
    def clear_queue(uid):
        return {
            'command': 'clear_queue',
            'parameter': {
                'uid': uid.lower()
            }
        }


#######################################################################
# UTIL FUNCTIONS
#######################################################################

def get_lan_ip():
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(5)
        s.connect(("google.com", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return None
