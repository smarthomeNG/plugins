#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 Marcus Popp                              marcus@popp.mx
#  Copyright 2017 Sebastian Sudholt      sebastian.sudholt@tu-dortmund.de
#  Copyright 2020 Sebastian Helms
#########################################################################
#
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
#
#########################################################################
import logging
import threading
import json
import queue

from collections import OrderedDict
from lib.model.smartplugin import SmartPlugin
from lib.network import Tcp_client
import time

from . import commands


class Kodi(SmartPlugin):
    '''
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    '''
    PLUGIN_VERSION = '1.6.1'
    ALLOW_MULTIINSTANCE = True
    _initcommands = ['get_actplayer', 'get_status_au', 'get_favourites']

    def __init__(self, sh, *args, **kwargs):
        '''
        Initalizes the plugin.
        '''
        # init logger
        self.logger = logging.getLogger(__name__)
        self.logger.info('Init Plugin')
        self._host = self.get_parameter_value('host')
        self._port = self.get_parameter_value('port')
        self._autoreconnect = self.get_parameter_value('autoreconnect')
        self._connect_retries = self.get_parameter_value('connect_retries')
        self._connect_cycle = self.get_parameter_value('connect_cycle')

        self._command_timeout = self.get_parameter_value('command_timeout')
        self._command_repeat = self.get_parameter_value('command_repeat')

        self._check_stale_cycle = float(self._command_timeout) / 2
        self._next_stale_check = 0
        self._last_stale_check = 0

        self._kodi_tcp_connection = Tcp_client(host=self._host,
                                               port=self._port,
                                               name='KodiTCPConnection',
                                               autoreconnect=self._autoreconnect,
                                               connect_retries=self._connect_retries,
                                               connect_cycle=self._connect_cycle)
        self._kodi_tcp_connection.set_callbacks(connected=self._on_connect,
                                                data_received=self._on_received_data,
                                                disconnected=self._on_disconnect)
        self._kodi_server_alive = False

        self._registered_items = {key: [] for key in set(list(commands.commands.keys()))}
        self._CMD = commands.commands
        self._MACRO = commands.macros

        self._message_id = 0
        self._msgid_lock = threading.Lock()
        self._send_queue = queue.Queue()
        self._stale_lock = threading.Lock()

        # self._message_archive[str message_id] = [time.time() sendtime, str method, str params or None, int repeat]
        self._message_archive = {}

        self._activeplayers = []
        self._playerid = 0

        self._shutdown_active = False

        if not self._check_commands_data():
            self._init_complete = False

    def run(self):
        '''
        Run method for the plugin
        '''
        self.logger.debug('run method called')
        self._connect('run')
        self.alive = True
        self._next_stale_check = time.time() + self._check_stale_cycle

    def stop(self):
        '''
        Stop method for the plugin
        '''
        self.alive = False
        self.logger.debug('stop method called')
        self._kodi_tcp_connection.close()
        self._kodi_server_alive = False

    def parse_item(self, item):
        '''
        Method for parsing Kodi items.
        If the item carries the kodi_item field, this item is registered to the plugin.

        :param item:    The item to process.
        :type item:     object

        :return:        The item update method to be triggered if the kodi_item is in the set item dict.
        :rtype:         object
        '''
        if self.has_iattr(item.conf, 'kodi_item'):
            command = self.get_iattr_value(item.conf, 'kodi_item')
            self.logger.debug('Registering item: {}'.format(item))
            if command in self._registered_items:
                self._registered_items[command].append(item)
            else:
                self.logger.warning('I do not know the kodi_item {}, skipping!'.format(command))
            if self._CMD[command]['set']:
                return self.update_item

    def parse_logic(self, logic):
        '''
        Method to parse plugin logics

        :note: Not implemented
        '''
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        '''
        Callback method for sending values to Kodi when a registered item has changed

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        '''
        # !! self.logger.debug('update_item called for item {} by {} with value {}'.format(item, caller, item()))
        if item() is not None and caller != self.get_shortname() and self.has_iattr(item.conf, 'kodi_item'):
            # update item was triggered by something other than this plugin -> send to Kodi

            kodi_item = self.get_iattr_value(item.conf, 'kodi_item')
            self.logger.debug('Updating item {} using kodi command {} with value {}, called by {}'.format(item, kodi_item, item(), caller))

            # power is handled specially as it is not a command for kodi per se
            if kodi_item == 'power' and item():
                # if item is set to True, try to (re)establish a connection to Kodi
                self._connect('update')
                # if item is set to False, send shutdown command to Kodi.
                # This is handled in the standard block below though

            # trigger status update mechanism
            elif kodi_item == 'update':
                if item():
                    self._update_status()

            # macros
            elif kodi_item == 'macro':
                self._process_macro(item)

            # writable item
            elif kodi_item in self._CMD and self._CMD[kodi_item]['set']:
                # !! self.logger.debug('Running send_command({}, {}, False)'.format(kodi_item, item()))
                self._send_command(kodi_item, item())

            else:
                self.logger.info('kodi_item "%s" not in send_keys, skipping!', kodi_item)

            # set flag if shutdown of kodi server was ordered
            if kodi_item == 'power' and not item():
                self._shutdown_active = True

        elif self.has_iattr(item.conf, 'kodi_item'):
            self.logger.debug('Not acting on item update: {} has set item {} to {}'.format(caller, item, item()))

    def notify(self, title, message, image=None, display_time=10000):
        '''
        Send a notification to Kodi to be displayed on the screen

        :param title: the title of the message
        :param message: the message itself
        :param image: an optional image to be displayed alongside the message
        :param display_time: how long the message is displayed in milli seconds
        '''
        params = {'title': title, 'message': message, 'displaytime': display_time}
        if image is not None:
            params['image'] = image
        self._send_rpc_message('GUI.ShowNotification', params)

    def _on_connect(self, by=None):
        '''
        Recall method for succesful connect to Kodi
        On a connect first check if the JSON-RPC API is available.
        If this is the case query Kodi to initialize all items

        :param by: caller information
        :type by: str
        '''
        self._kodi_server_alive = True
        if isinstance(by, (dict, Tcp_client)):
            by = 'TCP_Connect'
        self.logger.info('Connected to {}, onconnect called by {}, send queue contains {} commands'.format(self._host, by, self._send_queue.qsize()))
        self._set_all_items('power', True)
        if self._send_queue.qsize() == 0:
            for command in self._initcommands:
                self.logger.debug('Sending command after connect: {}'.format(command))
                self._send_command(command, None)

    def _on_disconnect(self, obj=None):
        '''
        Recall method for TCP disconnect
        '''
        self.logger.info('Received disconnect from {}'.format(self._host))
        self._set_all_items('power', False)
        self._kodi_server_alive = False
        for item in self._registered_items['power']:
            item(False, caller=self.get_shortname())

        # did we power down kodi? then clear queues
        if self._shutdown_active:
            old_queue = self._send_queue
            self._send_queue = queue.Queue()
            del old_queue
            self._stale_lock.acquire()
            self._message_archive = {}
            self._stale_lock.release()
            self._shutdown_active = False

    def _on_received_data(self, connection, response):
        '''
        This method is called by the TCP connection object whenever data is received from the host.
        '''

        self.logger.debug('Received data from TCP: {}'.format(response))

        # split multi-response data into list items
        try:
            datalist = response.replace('}{', '}-#-{').split('-#-')
            datalist = list(OrderedDict((x, True) for x in datalist).keys())
        except:
            datalist = [response]

        # process all response items
        for data in datalist:
            self.logger.debug('Processing received data item #{} ({})'.format(datalist.index(data), data))

            try:
                jdata = json.loads(data)
            except Exception as err:
                self.logger.warning('Could not json.load data item {} with error {}'.format(data, err))
                continue

            # formerly there was a check for error responses, which triggered up to <param>
            # retries. Re-sending a command which produces an error seem quite ignorant, so
            # this functionality was dropped

            # check for replies
            if 'id' in jdata:
                response_id = jdata['id']

                # reply or error received, remove command
                if response_id in self._message_archive:
                    # possibly the command was resent and removed before processing the reply
                    # so let's 'try' at least...
                    try:
                        cmd = self._message_archive[response_id][1]
                        del self._message_archive[response_id]
                    except KeyError:
                        cmd = '(deleted)' if '#' not in response_id else response_id[response_id.find('#')+1:]
                else:
                    cmd = None

                # log possible errors
                if 'error' in jdata:
                    self.logger.error('Received error {} in response to command {}'.format(jdata, cmd))
                elif cmd:
                    self.logger.debug('Command sent successfully: {}'.format(cmd))

            # process data
            self._parse_response(jdata)

        # check _message_archive for old commands - check time reached?
        if self._next_stale_check < time.time():

            # try to lock check routine, fail quickly if already locked = running
            if self._stale_lock.acquire(False):

                # we cannot deny access to self._message_archive as this would block sending
                # instead, copy it and check the copy
                stale_cmds = self._message_archive.copy()
                remove_ids = []
                requeue_cmds = []

                # self._message_archive[message_id] = [time.time(), method, params, repeat]
                self.logger.debug('Checking for unanswered commands, last check was {} seconds ago, {} commands saved'.format(int(time.time()) - self._last_stale_check, len(self._message_archive)))
                # !! self.logger.debug('Stale commands: {}'.format(stale_cmds))
                for (message_id, (send_time, method, params, repeat)) in stale_cmds.items():

                    if send_time + self._command_timeout < time.time():

                        # reply timeout reached, check repeat count
                        if repeat <= self._command_repeat:

                            # send again, increase counter
                            self.logger.info('Repeating unanswered command {} ({}), try {}'.format(method, params, repeat + 1))
                            requeue_cmds.append([method, params, message_id, repeat + 1])
                        else:
                            self.logger.info('Unanswered command {} ({}) repeated {} times, giving up.'.format(method, params, repeat))
                            remove_ids.append(message_id)

                for msgid in remove_ids:
                    # it is possible that while processing stale commands, a reply arrived
                    # and the command was removed. So just to be sure, 'try' and delete...
                    self.logger.debug('Removing stale msgid {} from archive'.format(msgid))
                    try:
                        del self._message_archive[msgid]
                    except KeyError:
                        pass

                # resend pending repeats - after original
                for (method, params, message_id, repeat) in requeue_cmds:
                    self._send_rpc_message(method, params, message_id, repeat)

                # set next stale check time
                self._last_stale_check = time.time()
                self._next_stale_check = self._last_stale_check + self._check_stale_cycle

                del stale_cmds
                del requeue_cmds
                del remove_ids
                self._stale_lock.release()

# !!
            else:
# !!
                self.logger.debug('Skipping stale check {} seconds after last check'.format(time.time() - self._last_stale_check))

    def _parse_response(self, data):
        '''
        This method parses (multi-)responses, extracts values and assigns values to assigned items

        :param data: json response data
        :type data: dict

        :return: True if no error was found in response
        :rtype: bool
        '''
        if 'error' in data:
            # errors should already have been logged in on_received_data(), as errors should
            # only occur in reply to commands, so they all have msg_ids. Errors without msg_id
            # will be silently and maliciously ignored
            return False

        query_playerinfo = []
        result_data = data.get('result')

        if 'id' in data:
            response_id = str(data['id'])
            if '#' in response_id:
                response_method = response_id.split('#')[1]
            else:
                response_method = response_id

            # got playerids
            if response_method == 'Player.GetActivePlayers':
                if len(result_data) == 1:
                    # one active player
                    query_playerinfo = self._activeplayers = [result_data[0].get('playerid')]
                    self._playerid = self._activeplayers[0]
                    self.logger.debug('Received GetActivePlayers, set playerid to {}'.format(self._playerid))
                    self._set_all_items('player', self._playerid)
                    self._set_all_items('media', result_data[0].get('type').capitalize())
                    # self._set_all_items('state', 'Playing')
                elif len(result_data) > 1:
                    # multiple active players. Have not yet seen this happen
                    self._activeplayers = []
                    for player in result_data:
                        self._activeplayers.append(player.get('playerid'))
                        query_playerinfo.append(player.get('playerid'))
                    self._playerid = min(self._activeplayers)
                    self.logger.debug('Received GetActivePlayers, set playerid to {}'.format(self._playerid))
                else:
                    # no active players
                    self._activeplayers = []
                    self._set_all_items('state', 'No active player')
                    self._set_all_items('player', 0)
                    self._set_all_items('title', '')
                    self._set_all_items('media', '')
                    self._set_all_items('stop', True)
                    self._set_all_items('playpause', False)
                    self._set_all_items('streams', None)
                    self._set_all_items('subtitles', None)
                    self._set_all_items('audio', '')
                    self._set_all_items('subtitle', '')
                    self._playerid = 0
                    self.logger.debug('Received GetActivePlayers, reset playerid to 0')

            # got status info
            elif response_method == 'Application.GetProperties':
                muted = result_data.get('muted')
                volume = result_data.get('volume')
                self.logger.debug('Received GetProperties: Change mute to {} and volume to {}'.format(muted, volume))
                self._set_all_items('mute', muted)
                self._set_all_items('volume', volume)

            # got favourites
            elif response_method == 'Favourites.GetFavourites':
                if not result_data.get('favourites'):
                    self.logger.debug('No favourites found.')
                else:
                    item_dict = {item['title']: item for item in result_data.get('favourites')}
                    self.logger.debug('Favourites found: {}'.format(item_dict))
                    self._set_all_items('get_favourites', item_dict)

            # got item info
            elif response_method == 'Player.GetItem':
                title = result_data['item'].get('title')
                player_type = result_data['item'].get('type')
                if not title:
                    title = result_data['item'].get('label')
                self._set_all_items('media', player_type.capitalize())
                if player_type == 'audio' and 'artist' in result_data['item']:
                    artist = 'unknown' if len(result_data['item'].get('artist')) == 0 else result_data['item'].get('artist')[0]
                    title = artist + ' - ' + title
                self._set_all_items('title', title)
                self.logger.debug('Received GetItem: update player info to title={}, type={}'.format(title, player_type))

            # got player status
            elif response_method == 'Player.GetProperties':
                self.logger.debug('Received Player.GetProperties, update media data')
                self._set_all_items('speed', result_data.get('speed'))
                self._set_all_items('seek', result_data.get('percentage'))
                self._set_all_items('streams', result_data.get('audiostreams'))
                self._set_all_items('audio', result_data.get('currentaudiostream'))
                self._set_all_items('subtitles', result_data.get('subtitles'))
                if result_data.get('subtitleenabled'):
                    subtitle = result_data.get('currentsubtitle')
                else:
                    subtitle = 'Off'
                self._set_all_items('subtitle', subtitle)

                # speed != 0 -> play; speed == 0 -> pause
                if result_data.get('speed') == 0:
                    self._set_all_items('state', 'Paused')
                    self._set_all_items('stop', False)
                    self._set_all_items('playpause', False)
                else:
                    self._set_all_items('state', 'Playing')
                    self._set_all_items('stop', False)
                    self._set_all_items('playpause', True)

        elif 'method' in data:
            # no id, notification or other
            if data['method'] == 'Player.OnResume':
                self.logger.debug('Received: resumed player')
                self._set_all_items('state', 'Playing')
                self._set_all_items('stop', False)
                self._set_all_items('playpause', True)
                query_playerinfo.append(data['params']['data']['player']['playerid'])

            elif data['method'] == 'Player.OnPause':
                self.logger.debug('Received: paused player')
                self._set_all_items('state', 'Paused')
                self._set_all_items('stop', False)
                self._set_all_items('playpause', False)
                query_playerinfo.append(data['params']['data']['player']['playerid'])

            elif data['method'] == 'Player.OnStop':
                self.logger.debug('Received: stopped player, set playerid to 0')
                self._set_all_items('state', 'No active player')
                self._set_all_items('media', '')
                self._set_all_items('title', '')
                self._set_all_items('player', 0)
                self._set_all_items('stop', True)
                self._set_all_items('playpause', False)
                self._set_all_items('streams', None)
                self._set_all_items('subtitles', None)
                self._set_all_items('audio', '')
                self._set_all_items('subtitle', '')
                self._activeplayers = []
                self._playerid = 0

            elif data['method'] == 'GUI.OnScreensaverActivated':
                self.logger.debug('Received: activated screensaver')
                self._set_all_items('state', 'Screensaver')

            elif data['method'] in ['Player.OnPlay', 'Player.OnAVChange']:
                self.logger.debug('Received: started/changed playback')
                self._set_all_items('state', 'Playing')
                query_playerinfo.append(data['params']['data']['player']['playerid'])

            elif data['method'] == 'Application.OnVolumeChanged':
                self.logger.debug('Received: volume changed, got new values mute: {} and volume: {}'.format(data['params']['data']['muted'], data['params']['data']['volume']))
                self._set_all_items('mute', data['params']['data']['muted'])
                self._set_all_items('volume', data['params']['data']['volume'])

        # if active playerid(s) was changed, update status for active player(s)
        if query_playerinfo:
            self.logger.debug('Player info query requested for playerid(s) {}'.format(query_playerinfo))
            for player_id in query_playerinfo:
                self.logger.debug('Getting player info for player #{}'.format(player_id))
                self._send_rpc_message('Player.GetItem', {'properties': ['title', 'artist'], 'playerid': player_id})
                self._send_rpc_message('Player.GetProperties', {'properties': ['speed', 'percentage', 'currentaudiostream', 'audiostreams', 'subtitleenabled', 'currentsubtitle', 'subtitles'], 'playerid': player_id})

        return True

    def _set_all_items(self, kodi_item, value):
        '''
        This method sets all items which are registered for kodi_item to value with own caller_id

        :parameter kodi_item: command name from commands.py / item config
        :type kodi_item: str
        :parameter value: value to set for all items
        '''
        for item in self._registered_items[kodi_item]:
            item(value, caller=self.get_shortname())

    def _check_commands_data(self):
        '''
        Method checks consistency of imported commands data

        :return: True if data is consistent
        :rtype: bool
        '''
        no_method = []
        wrong_keys = []
        unmatched = []
        bounds = []
        values = []
        for command, entry in commands.commands.items():
            # verify all keys are present
            if not ['method', 'set', 'get', 'params', 'values', 'bounds'].sort() == list(entry.keys()).sort():
                wrong_keys.append(command)
            elif not ['set', 'special'].sort() == list(entry.keys()).sort():
                # check that method is not empty
                if not entry['method']:
                    no_method.append(command)
                par = entry['params']
                val = entry['values']
                bnd = entry['bounds']
                # params and values must be either both None or both lists of equal length
                if par is None and val is not None or par is not None and val is None:
                    unmatched.append(command)
                elif par is not None and val is not None and len(par) != len(val):
                    unmatched.append(command)
                vals = 0
                if val is not None:
                    # check that max. one 'VAL' entry is present
                    for item in val:
                        if item == 'VAL':
                            vals += 1
                    if vals > 1:
                        values.append(command)
                # check that bounds are None or list or (tuple and len(bounds)=2)
                if bnd is not None and \
                   not isinstance(bnd, list) and \
                   (not (isinstance(bnd, tuple) and len(bnd) == 2)):
                    bounds.append(command)
                # check that bounds are only defined if 'VAL' is present
                if vals == 0 and bnd is not None:
                    bounds.append(command)

        # found any errors?
        if len(no_method + wrong_keys + unmatched + bounds + values) > 0:
            if len(wrong_keys) > 0:
                self.logger.error('Commands data not consistent: commands "' + '", "'.join(wrong_keys) + '" have wrong keys')
            if len(no_method) > 0:
                self.logger.error('Commands data not consistent: commands "' + '", "'.join(no_method) + '" have no method')
            if len(unmatched) > 0:
                self.logger.error('Commands data not consistent: commands "' + '", "'.join(unmatched) + '" have unmatched params/values')
            if len(bounds) > 0:
                self.logger.error('Commands data not consistent: commands "' + '", "'.join(bounds) + '" have erroneous bounds')
            if len(values) > 0:
                self.logger.error('Commands data not consistent: commands "' + '", "'.join(values) + '" have more than one "VAL" field')

            return False

        macros = []
        for macro, entry in commands.macros.items():
            if not isinstance(entry, list):
                macros.append(macro)
            else:
                for step in entry:
                    if not isinstance(step, list) or len(step) != 2:
                        macros.append(macro)

        if len(macros) > 0:
            self.logger.error('Macro data not consistent for macros "' + '", "'.join(macros) + '"')
            # errors in macro definition don't hinder normal plugin functionality, so just
            # refill self._MACRO omitting erroneous entries. With bad luck, _MACRO is empty ;)
            self._MACRO = {}
            for command, entry in command.macros:
                if command not in macros:
                    self._MACRO[command] = entry

        return True

    def _connect(self, by):
        '''
        Method to try to establish a new connection to Kodi

        :note: While this method is called during the start-up phase of the plugin, it can also be used to establish a connection to the Kodi server if the plugin was initialized before the server went up or the connection is interrupted.

        :param by: caller information
        :type by: str
        '''
        self.logger.debug('Initializing connection, initiated by {}'.format(by))
        if not self._kodi_tcp_connection.connected():
            self._kodi_tcp_connection.connect()
            # we allow for 2 seconds to connect
            time.sleep(2)
        if not self._kodi_tcp_connection.connected():
            # no connection could be established, Kodi may be offline
            self.logger.info('Could not establish a connection to Kodi at {}'.format(self._host))
            self._kodi_server_alive = False
        else:
            self._kodi_server_alive = True
        if self._kodi_server_alive:
            for item in self._registered_items['power']:
                item(True, caller=self.get_shortname())

    def _process_macro(self, item):
        '''
        This method processes macro sequences. Macros can be definded in commands.py
        or dynamically be submitted via the item value.

        :param item: the item refenencing the macro
        :type item: object
        '''
        if item() in self._MACRO:
            # predefined macro
            macro = item()
            macroseq = self._MACRO[macro]
        elif isinstance(item(), list):
            # custom/dynamic macro seq provided as item()
            for step in item():
                if not isinstance(step, list) or len(step) != 2:
                    self.logger.error('Custom macro "{}" from item {} is not a valid macro sequence'.format(item(), item))
                    return
            macro = '(custom {})'.format(item)
            macroseq = item()
        else:
            self.logger.error('Macro "{}"" not in macro definitions and no valid macro itself'.format(item()))
            return

        for [command, value] in macroseq:
            if command == 'wait':
                self.logger.debug('Macro {} waiting for {} second(s)'.format(item(), value))
                time.sleep(value)
            else:
                self.logger.debug('Macro {} calling command {} with value {}'.format(command, value))
                self._send_command(command, value)
        self.logger.debug('Macro {} finished'.format(item()))

    def _build_command_params(self, command, data):
        '''
        This method validates the data according to the command definitions and creates the parameter dict for the command

        :param command: command to send as defined in _CMD
        :type command: str
        :param data: parameter data to send, format according to command requirements

        :return: parameter for sending
        :rtype: dict
        '''
        if command not in self._CMD:
            self.logger.error('Command unknown: {}'.format(command))
            return False

        if self._CMD[command]['params'] is None:
            return None

        self.logger.debug('Building params set for {}'.format(data))

        cmdset = self._CMD[command]
        cmd_params = cmdset['params']
        cmd_values = cmdset['values']
        cmd_bounds = cmdset['bounds']

        if (isinstance(data, str) and data.isnumeric()):
            data = self._str2num(data)
            if data is None:
                self.logger.error('Invalid data: value {} is not numeric for command {}'.format(data, command))
                return False

        params = {}
        for idx in range(len(cmd_params)):

            # VAL field
            if cmd_values[idx] == 'VAL':

                # check validity if bounds are given
                if cmd_bounds is not None:
                    if isinstance(cmd_bounds, list):
                        if data not in cmd_bounds:
                            self.logger.debug('Invalid data: value {} not in list {}'.format(data, cmd_bounds))
                            return False
                    elif isinstance(cmd_bounds, tuple):
                        if not isinstance(data, type(cmd_bounds[0])):
                            if type(data) is float and type(cmd_bounds[0]) is int:
                                data = int(data)
                            else:
                                self.logger.error('Invalid data: type {} ({}) given for {} bounds {}'.format(type(data), data, type(cmd_bounds[0]), cmd_bounds))
                                return False
                        if not cmd_bounds[0] <= data <= cmd_bounds[1]:
                            self.logger.error('Invalid data: value {} out of bounds ({})'.format(data, cmd_bounds))
                            return False
                params[cmd_params[idx]] = data

            # playerid
            elif cmd_values[idx] == 'ID':
                params[cmd_params[idx]] = self._playerid

            # tuple => eval expression with VAL substituted for data
            elif isinstance(cmd_values[idx], tuple):
                try:
                    expr = str(cmd_values[idx][0]).replace('VAL', str(data))
                    result = eval(expr)
                except Exception as e:
                    self.logger.error('Invalid data: eval expression {} with argument {} raised error: {}'.format(cmd_values[idx][0], data, e.message))
                    return False
                params[cmd_params[idx]] = result

            # bare value (including list) => just send it
            else:
                params[cmd_params[idx]] = cmd_values[idx]

        self.logger.debug('Built params array {}'.format(params))

        return params

    def _send_command(self, command, data):
        '''
        This method prepares and send the command string to send to Kodi device

        :param command: command to send as defined in _CMD
        :type command: str
        :param data: parameter data to send, format according to command requirements

        :return: True if send succeeded / acknowledged by Kodi
        :rtype: bool
        '''

        if command not in self._CMD:
            self.logger.error('Command unknown: {}'.format(command))
            return False

        params = self._build_command_params(command, data)

        # error occured on param build? success yields dict or None
        if params is False:
            return False

        # !! self.logger.debug('Calling send_rpc method for command {} with method={} and params={}'.format(command, self._CMD[command]['method'], params))
        self._send_rpc_message(self._CMD[command]['method'], params)

    def _send_rpc_message(self, method, params=None, message_id=None, repeat=0):
        '''
        Send a JSON RPC to Kodi.
        The  JSON string is extracted from the supplied method and the given parameters.

        :param method: the Kodi method to be triggered
        :param params: parameters dictionary
        :param message_id: the message ID to be used. If none, use the internal counter
        '''
        self.logger.debug('Preparing message to send method {} with data {}, try #{}, connection is {}'.format(method, params, repeat, self._kodi_server_alive))

        if message_id is None:
            # safely acquire next message_id
            # !! self.logger.debug('Locking message id access ({})'.format(self._message_id))
            self._msgid_lock.acquire()
            self._message_id += 1
            new_msgid = self._message_id
            self._msgid_lock.release()
            message_id = str(new_msgid) + '#' + method
            # !! self.logger.debug('Releasing message id access ({})'.format(self._message_id))

        # create message packet
        data = {'jsonrpc': '2.0', 'id': message_id, 'method': method}
        if params:
            data['params'] = params
        try:
            send_command = json.dumps(data, separators=(',', ':'))
        except Exception as err:
            self.logger.error('Problem with json.dumps: {}'.format(err))
            send_command = data

        # push message in queue
        # !! self.logger.debug('Queuing message {}'.format(send_command))
        self._send_queue.put([message_id, send_command, method, params, repeat])
        # !! self.logger.debug('Queued message {}'.format(send_command))

        # try to actually send all queued messages
# !!
        self.logger.debug('Processing queue - {} elements'.format(self._send_queue.qsize()))
        while not self._send_queue.empty():
            (message_id, data, method, params, repeat) = self._send_queue.get()
            self.logger.debug('Sending queued msg {} - {} (#{})'.format(message_id, data, repeat))
            self._kodi_tcp_connection.send((data + '\r\n').encode())
            # !! self.logger.debug('Adding cmd to message archive: {} - {} (try #{})'.format(message_id, data, repeat))
            self._message_archive[message_id] = [time.time(), method, params, repeat]
            # !! self.logger.debug('Sent msg {} - {}'.format(message_id, data))
        # !! self.logger.debug('Processing queue finished - {} elements remaining'.format(self._send_queue.qsize()))

    def _update_status(self):
        '''
        This method requests several status infos
        '''
        if self.alive:
            if not self._kodi_server_alive:
                self._connect('update')
            else:
                self._send_command('get_status_au', None)
                if self._playerid:
                    self._send_command('get_status_play', None)
                    self._send_command('get_item', None)

    def _str2num(self, s):
        try:
            val = int(s)
            return(val)
        except ValueError:
            try:
                val = float(s)
                return(val)
            except ValueError:
                return None
