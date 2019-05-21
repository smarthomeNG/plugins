#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 Marcus Popp                              marcus@popp.mx
#  Copyright 2017 Sebastian Sudholt      sebastian.sudholt@tu-dortmund.de
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
import re
from collections import OrderedDict

from lib.model.smartplugin import SmartPlugin
from lib.network import Tcp_client
import time


class Kodi(SmartPlugin):
    '''
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    '''

    PLUGIN_VERSION = '1.5.0'
    ALLOW_MULTIINSTANCE = True

    # list of all possible input actions for Kodi
    _possible_input_actions = [
        'left', 'right', 'up', 'down', 'pageup', 'pagedown', 'select', 'highlight',
        'parentdir', 'parentfolder', 'back', 'menu', 'previousmenu', 'info',
        'pause', 'stop', 'skipnext', 'skipprevious', 'fullscreen', 'aspectratio',
        'stepforward', 'stepback', 'bigstepforward', 'bigstepback',
        'chapterorbigstepforward', 'chapterorbigstepback', 'osd', 'showsubtitles',
        'nextsubtitle', 'cyclesubtitle', 'playerdebug', 'codecinfo', 'playerprocessinfo',
        'nextpicture', 'previouspicture', 'zoomout', 'zoomin', 'playlist', 'queue',
        'zoomnormal', 'zoomlevel1', 'zoomlevel2', 'zoomlevel3', 'zoomlevel4',
        'zoomlevel5', 'zoomlevel6', 'zoomlevel7', 'zoomlevel8', 'zoomlevel9',
        'nextcalibration', 'resetcalibration', 'analogmove', 'analogmovex',
        'analogmovey', 'rotate', 'rotateccw', 'close', 'subtitledelayminus',
        'subtitledelay', 'subtitledelayplus', 'audiodelayminus', 'audiodelay',
        'audiodelayplus', 'subtitleshiftup', 'subtitleshiftdown', 'subtitlealign',
        'audionextlanguage', 'verticalshiftup', 'verticalshiftdown', 'nextresolution',
        'audiotoggledigital', 'number0', 'number1', 'number2', 'number3', 'number4',
        'number5', 'number6', 'number7', 'number8', 'number9', 'smallstepback',
        'fastforward', 'rewind', 'play', 'playpause', 'switchplayer', 'delete', 'copy',
        'move', 'screenshot', 'rename', 'togglewatched', 'scanitem', 'reloadkeymaps',
        'volumeup', 'volumedown', 'mute', 'backspace', 'scrollup', 'scrolldown',
        'analogfastforward', 'analogrewind', 'moveitemup', 'moveitemdown', 'contextmenu',
        'shift', 'symbols', 'cursorleft', 'cursorright', 'showtime', 'analogseekforward',
        'analogseekback', 'showpreset', 'nextpreset', 'previouspreset', 'lockpreset', 'randompreset',
        'increasevisrating', 'decreasevisrating', 'showvideomenu', 'enter', 'increaserating',
        'decreaserating', 'setrating', 'togglefullscreen', 'nextscene', 'previousscene', 'nextletter',
        'prevletter', 'jumpsms2', 'jumpsms3', 'jumpsms4', 'jumpsms5', 'jumpsms6', 'jumpsms7', 'jumpsms8',
        'jumpsms9', 'filter', 'filterclear', 'filtersms2', 'filtersms3', 'filtersms4', 'filtersms5',
        'filtersms6', 'filtersms7', 'filtersms8', 'filtersms9', 'firstpage', 'lastpage', 'guiprofile',
        'red', 'green', 'yellow', 'blue', 'increasepar', 'decreasepar', 'volampup', 'volampdown',
        'volumeamplification', 'createbookmark', 'createepisodebookmark', 'settingsreset',
        'settingslevelchange', 'stereomode', 'nextstereomode', 'previousstereomode',
        'togglestereomode', 'stereomodetomono', 'channelup', 'channeldown', 'previouschannelgroup',
        'nextchannelgroup', 'playpvr', 'playpvrtv', 'playpvrradio', 'record', 'togglecommskip',
        'showtimerrule', 'leftclick', 'rightclick', 'middleclick', 'doubleclick', 'longclick',
        'wheelup', 'wheeldown', 'mousedrag', 'mousemove', 'tap', 'longpress', 'pangesture',
        'zoomgesture', 'rotategesture', 'swipeleft', 'swiperight', 'swipeup', 'swipedown', 'error', 'noop', 'resume']

    _get_items = ['volume', 'mute', 'title', 'media', 'state', 'favourites']

    _set_items = {'volume': dict(method='Application.SetVolume', params=dict(volume='ITEM_VALUE')),
                  'mute'  : dict(method='Application.SetMute', params=dict(mute='ITEM_VALUE')),
                  'input' : dict(method='Input.ExecuteAction', params=dict(action='ITEM_VALUE')),
                  'on_off': dict(method='System.Shutdown', params=None),
                  'player': dict(method='Player.GetActivePlayers', params=None)}

    _player_items = {'audiostream': dict(method='Player.SetAudioStream', params=dict(stream='ITEM_VALUE')),
                     'subtitle': dict(method='Player.SetAudioStream', params=dict(subtitle='ITEM_VALUE[0]', enable='ITEM_VALUE[1]')),
                     'seek': dict(method='Player.Seek', params=dict(value='ITEM_VALUE')),
                     'speed': dict(method='Player.SetSpeed', params=dict(speed='ITEM_VALUE'))}

    _macro = {'resume': {"play": dict(method='Input.ExecuteAction', params=dict(action='play')), "resume": dict(method='Input.ExecuteAction', params=dict(action='select'))},
              'beginning': {"play": dict(method='Input.ExecuteAction', params=dict(action='play')),
                           "down": dict(method='Input.ExecuteAction', params=dict(action='down')), "select": dict(method='Input.ExecuteAction', params=dict(action='select'))}}

    _initcommands = {"ping": {"method": "JSONRPC.Ping"}, "getvolume": {"method": 'Application.GetProperties', "params": dict(properties=['volume', 'muted'])},
                    "favourites": {"method": 'Favourites.GetFavourites', "params": dict(properties=['window', 'path', 'thumbnail', 'windowparameter'])},
                    "player": {"method": "Player.GetActivePlayers"} }


    def __init__(self, sh, *args, **kwargs):
        '''
        Initalizes the plugin.
        '''
        # init logger
        self.logger = logging.getLogger(__name__)
        self.logger.info('Init Kodi Plugin')
        self.host = self.get_parameter_value('host')
        self.port = self.get_parameter_value('port')
        self.autoreconnect = self.get_parameter_value('autoreconnect')
        self.connect_retries = self.get_parameter_value('connect_retries')
        self.connect_cycle = self.get_parameter_value('connect_cycle')
        self.send_retries = self.get_parameter_value('send_retries')
        self.kodi_tcp_connection = Tcp_client(host=self.host,
                                              port=self.port,
                                              name='KodiTCPConnection',
                                              autoreconnect=self.autoreconnect,
                                              connect_retries=self.connect_retries,
                                              connect_cycle=self.connect_cycle)
        self.kodi_tcp_connection.set_callbacks(connected=self.on_connect,
                                               data_received=self.received_data,
                                               disconnected=self.on_disconnect)
        self.kodi_server_alive = False
#         self.terminator = 0
#         self.balance(b'{', b'}')
        self.message_id = 1
        self.response_id = None
        self.sendingcommand = None
        self.senderrors = {}
        self.cmd_lock = threading.Condition()
        self.reply_lock = threading.Condition()
        self.reply = None
        self.activeplayers = []
        self.sendcommands = []
        self.registered_items = {key: [] for key in set(list(Kodi._set_items.keys()) + ['macro'] + Kodi._get_items + list(Kodi._player_items.keys()))}

    def run(self):
        '''
        Run method for the plugin
        '''
        self.logger.debug('Plugin \'{}\': run method called'.format(self.get_shortname()))
        self.connect_to_kodi('run')
        self.alive = True

    def stop(self):
        '''
        Stop method for the plugin
        '''
        self.logger.debug('Plugin \'{}\': stop method called'.format(self.get_shortname()))
        self.kodi_tcp_connection.close()
        self.kodi_server_alive = False
        self.alive = False

    def on_connect(self, by=None):
        '''
        This method is called on a succesful connect to Kodi
        On a connect first check if the JSON-RPC API is available.
        If this is the case initialize all items with values extracted from Kodi
        '''
        # check if API is available
        self.kodi_server_alive = True
        if isinstance(by, (dict, Tcp_client)):
            by = 'TCP_Connect'
        self.logger.debug("Kodi running onconnect started by {}. Connection: {}. Selfcommands {}".format(by, self.kodi_server_alive, self.sendcommands))
        if len(self.sendcommands) == 0:
            for command in self._initcommands:
                self.logger.debug("Sending command after connect: {}".format(self._initcommands.get(command)))
                self.send_kodi_rpc(method=self._initcommands.get(command).get('method'), params=self._initcommands.get(command).get('params'), wait=False)

    def on_disconnect(self, obj=None):
        ''' function called when TCP connection to Kodi is disconnected '''
        self.logger.debug('Received disconnect from Kodi')
        self.kodi_server_alive = False
        for elem in self.registered_items['on_off']:
            elem(self.kodi_server_alive, caller='Kodi')

    def connect_to_kodi(self, by):
        '''
        try to establish a new connection to Kodi

        While this method is called during the start-up phase of the plugin,
        it can also be used to establish a connection to the Kodi server if the
        plugin was initialized before the server went up.
        '''
        self.logger.debug("Kodi connection initialized by {}".format(by))
        if not self.kodi_tcp_connection.connected():
            self.kodi_tcp_connection.connect()
            # we allow for 2 seconds to connect
            time.sleep(2)
        if not self.kodi_tcp_connection.connected():
            # no connection could be established, Kodi may be offline
            self.logger.info('Could not establish a connection to Kodi Server')
            self.kodi_server_alive = False
        else:
            self.kodi_server_alive = True
            #self.on_connect(by)
        for elem in self.registered_items['on_off']:
            elem(self.kodi_server_alive, caller='Kodi')

    def parse_item(self, item):
        '''
        Method for parsing Kodi items.
        If the item carries the kodi_item field, this item is registered to the plugin.
        :param item:    The item to process.
        :return:        The item update method to be triggered if the kodi_item is in the set item dict.
        '''
        if self.has_iattr(item.conf, 'kodi_item'):
            kodi_item = self.get_iattr_value(item.conf, 'kodi_item')
            self.logger.debug('Registering item: {}'.format(item))
            if kodi_item in self.registered_items:
                self.registered_items[kodi_item].append(item)
            else:
                self.logger.warning('I do not know the kodi_item {}, skipping!'.format(kodi_item))
            if kodi_item in Kodi._set_items or kodi_item == 'macro' or kodi_item in Kodi._player_items:
                return self.update_item

    def parse_logic(self, logic):
        '''
        Default plugin parse_logic method
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
        item_value = item()
        if item_value is not None and caller != 'Kodi' and self.has_iattr(item.conf, 'kodi_item'):
            # update item was triggered from something else then this plugin -> send to Kodi
            kodi_item = self.get_iattr_value(item.conf, 'kodi_item')
            self.logger.debug("Updating item {} using kodi command {}".format(item, kodi_item))

            if kodi_item == 'on_off' and item():
                # handle the on_off item as special case:
                # if item is on, try to establish a connection to Kodi
                self.connect_to_kodi('update')
                # if item is off send shutdown command to Kodi. This is
                # handled in the standard block below though
            elif kodi_item == 'macro' and item() in self._macro:
                macro = item()
                for command in self._macro.get(macro):
                    method = self._macro.get(macro).get(command).get('method')
                    params = self._macro.get(macro).get(command).get('params')
                    self.logger.debug("Command - Method: {}, Params: {}".format(method, params))
                    self.send_kodi_rpc(method=method, params=params, wait=False)
            elif kodi_item in Kodi._set_items:
                if kodi_item == 'player':
                    for elem in self.registered_items['player']:
                        elem(0, caller='Kodi')
                if kodi_item == 'input' and item() not in self._possible_input_actions:
                    self.logger.error('The action \'%s\' for the kodi_item \'input\' is not allowed, skipping!', item_value)
                else:
                    self.logger.debug('Plugin \'%s\': update_item was called with item \'%s\' from caller \'%s\', source \'%s\' and dest \'%s\'',
                                      self.get_shortname(), item, caller, source, dest)
                    method = self._set_items[kodi_item]['method']
                    params = self._set_items[kodi_item]['params']
                    if params is not None:
                        # copy so we don't interfer with the class variable
                        params = params.copy()
                        # replace the wild card ITEM_VALUE with the item's value
                        for key, value in params.items():
                            if value == 'ITEM_VALUE':
                                params[key] = item_value
                    self._send_player_command(method, params, kodi_item)
            elif kodi_item in Kodi._player_items:
                self.logger.debug('Plugin \'%s\': update_item was called with item \'%s\' from caller \'%s\', source \'%s\' and dest \'%s\'',
                                  self.get_shortname(), item, caller, source, dest)
                method = self._player_items[kodi_item]['method']
                params = self._player_items[kodi_item]['params'] or {}
                if params is not None:
                    # copy so we don't interfer with the class variable
                    params = params.copy()
                    # replace the wild card ITEM_VALUE with the item's value
                    for key, value in params.items():
                        if value == 'ITEM_VALUE':
                            params[key] = item_value
                    self._send_player_command(method, params, kodi_item)
            else:
                self.logger.info('kodi_item \'%s\' not in send_keys, skipping!', kodi_item)

    def notify(self, title, message, image=None, display_time=10000):
        '''
        Send a notification to Kodi to be displayed on the screen

        :param title: the title of the message
        :param message: the message itself
        :param image: an optional image to be displayed alongside the message
        :param display_time: how long the message is displayed in milli seconds
        '''
        params = dict(title=title, message=message, displaytime=display_time)
        if image is not None:
            params['image'] = image
        self.send_kodi_rpc(method='GUI.ShowNotification', params=params)

    def send_kodi_rpc(self, method, params=None, message_id=None, wait=True):
        '''
        Send a JSON RPC to Kodi.

        The  JSON string is extracted from the supplied method and the given parameters.
        :param method: the Kodi method to be triggered
        :param params: parameters dictionary
        :param message_id: the message ID to be used. If none, use the internal counter
        :param wait: whether to wait for the reply from Kodi or send off the RPC asynchronously
                     If wait is True, this method returns a dictionary parsed from the JSON
                     response from Kodi
        '''
        reply = None
        self.logger.debug("Sending method {}. Alive: {}".format(method, self.kodi_server_alive))
        if self.kodi_server_alive:
            self.cmd_lock.acquire()
            self.logger.debug("Command lock acquired")
            self.reply = None
            '''
            if message_id is None:
                self.message_id += 1
                message_id = self.message_id
                if message_id > 99:
                    self.message_id = 0
                message_id = "{}_{}".format(method, message_id)
            '''
            message_id = method
            self.logger.debug('Sendcommands while sending: {0}'.format(self.sendcommands))
            self.response_id = message_id
            if params is not None:
                data = {'jsonrpc': '2.0', 'id': message_id, 'method': method, 'params': params}
            else:
                data = {'jsonrpc': '2.0', 'id': message_id, 'method': method}
            if not data in self.sendcommands:
                self.sendcommands.append(data)
            else:
                self.sendcommands[self.sendcommands.index(data)] = data
            self.logger.debug('Sendcommands while sending: {0}'.format(self.sendcommands))
            self.reply_lock.acquire()
            try:
                self.sendingcommand = json.dumps(data, separators=(',', ':'))
            except Exception as err:
                self.sendingcommand = data
                self.logger.error("Problem with json.dumps: {}".format(err))
            self.logger.debug('Kodi sending: {0}'.format(self.sendingcommand))
            self.kodi_tcp_connection.send((self.sendingcommand + '\r\n').encode())
            if wait:
                self.logger.debug("Waiting for reply_lock..")
                self.reply_lock.wait(1)
            self.reply_lock.release()
            reply = self.reply
            self.reply = None
            self.cmd_lock.release()
            self.logger.debug("Command lock released")
        else:
            self.logger.debug('JSON-RPC command requested without an established connection to Kodi.')
        return reply

    def received_data(self, connection, data):
        '''
        This method is called whenever data is received from the connection to
        Kodi.
        '''
        self.logger.debug('Kodi receiving: {0}'.format(data))
        try:
            events = (re.sub(r'\}\{', '}-#-{', data)).split("-#-")
            events = list(OrderedDict((x, True) for x in events).keys())
        except Exception as err:
            self.logger.warning("Could not optimize reply. Error: {}".format(err))
        for event in events:
            try:
                event = json.loads(event)
            except Exception as err:
                self.logger.warning("Could not json.load reply. Error: {}".format(err))
            if len(events) > 1:
                self.logger.debug('Kodi checking from multianswer: {0}'.format(event))
            if 'id' in event:
                self.reply_lock.acquire()
                templist = []
                templist = self.sendcommands
                for entry in templist:
                    if entry.get('id') == event.get('id'):
                        if self.senderrors.get(event.get('id')):
                            self.senderrors[event.get('id')] = 0
                        if 'error' in event:
                            self.logger.warning("There was a problem with the {} command: {}. Removing from queue.".format(event.get('id'), event.get('error').get('message')))
                        elif event.get('id').startswith('Player.GetActivePlayers'):
                            if len(event.get('result')) > 1:
                                self.logger.info('There is more than one active player. Sending request to each player!')
                                self.activeplayers = []
                                for player in event.get('result'):
                                    self.activeplayers.append(player.get('playerid'))
                                    self._get_player_info(player)
                            elif len(event.get('result')) > 0:
                                self.activeplayers = [event.get('result')[0].get('playerid')]
                                self.logger.debug("Getting player info for {}".format(event.get('result')))
                                self._get_player_info(event.get('result'))
                                for elem in self.registered_items['player']:
                                    elem(event.get('result')[0].get('playerid'), caller='Kodi')
                            else:
                                self.activeplayers = []
                                for elem in self.registered_items['state']:
                                    elem('No Active Player', caller='Kodi')
                        elif event.get('result') and event.get('id').startswith('Application.GetProperties'):
                            muted = event['result'].get('muted')
                            volume = event['result'].get('volume')
                            self.logger.debug("Received GetProperties: Change mute to {} and volume to {}".format(muted, volume))
                            for elem in self.registered_items['mute']:
                                elem(muted, caller='Kodi')
                            for elem in self.registered_items['volume']:
                                elem(volume, caller='Kodi')
                        elif event.get('result') and event.get('id').startswith('Favourites.GetFavourites'):
                            item_dict = dict()
                            if event.get('result').get('favourites') is None:
                                self.logger.debug("No favourites found.")
                            else:
                                item_dict = {elem['title']: elem for elem in event.get('result').get('favourites')}
                                self.logger.debug("Favourites found: {}".format(item_dict))
                                for elem in self.registered_items['favourites']:
                                    elem(item_dict, caller='Kodi')
                        elif event.get('result') and event.get('id').startswith('Player.GetItem'):
                            title = event.get('result')['item'].get('title')
                            typ = event.get('result')['item'].get('type')
                            if not title and 'label' in event.get('result')['item']:
                                title = event.get('result')['item']['label']
                            for elem in self.registered_items['media']:
                                elem(typ.capitalize(), caller='Kodi')
                            if event.get('result')['item'].get('artist'):
                                artist = 'unknown' if len(event.get('result')['item'].get('artist')) == 0 else event.get('result')['item'].get('artist')[0]
                                title = artist + ' - ' + title
                            for elem in self.registered_items['title']:
                                elem(title, caller='Kodi')
                            self.logger.debug("Updated player info: title={}, type={}".format(title, typ))
                        else:
                            self.logger.debug("Sent successfully {}.".format(entry))
                        try:
                            self.sendcommands.remove(entry)
                        except Exception as err:
                            self.logger.error(err)
                        self.reply_lock.notify()
                        self.reply_lock.release()
                self.logger.debug('Sendcommands after receiving: {0}'.format(self.sendcommands))
            elif 'favourites' in event:
                item_dict = dict()
                item_dict = {elem['title']: elem for elem in result['favourites']}
                self.logger.debug("Favourites queried: {}".format(item_dict))
                for elem in self.registered_items['favourites']:
                    elem(item_dict, caller='Kodi')
            elif 'method' in event:
                if event['method'] == 'Player.OnPause':
                    self.logger.debug("Paused Player")
                    for elem in self.registered_items['state']:
                        elem('Pause', caller='Kodi')
                elif event['method'] == 'Player.OnStop':
                    self.logger.debug("Stopped Player")
                    for elem in self.registered_items['state']:
                        elem('Stopped Player', caller='Kodi')
                    for elem in self.registered_items['media']:
                        elem('', caller='Kodi')
                    for elem in self.registered_items['title']:
                        elem('', caller='Kodi')
                elif event['method'] == 'GUI.OnScreensaverActivated':
                    self.logger.debug("Activate Screensaver")
                    for elem in self.registered_items['state']:
                        elem('Screensaver', caller='Kodi')
                if event['method'] in ['Player.OnPlay', 'Player.OnAVChange']:
                    # use a different thread for event handling
                    self.logger.debug("Getting player info after player started")
                    data = {'jsonrpc': '2.0', 'id': 'Player.GetActivePlayers', 'method': 'Player.GetActivePlayers'}
                    if not data in self.sendcommands:
                        self.sendcommands.append(data)
                    else:
                        self.sendcommands[self.sendcommands.index(data)] = data
                    #self.scheduler_trigger('kodi-player-start', self.send_kodi_rpc, 'Kodi', 'OnPlay', {"method": "Player.GetActivePlayers"})
                elif event['method'] in ['Application.OnVolumeChanged']:
                    self.logger.debug("Change mute to {} and volume to {}".format(event['params']['data']['muted'], event['params']['data']['volume']))
                    for elem in self.registered_items['mute']:
                        elem(event['params']['data']['muted'], caller='Kodi')
                    for elem in self.registered_items['volume']:
                        elem(event['params']['data']['volume'], caller='Kodi')
        if len(self.sendcommands) > 0:
            id = self.sendcommands[0].get('id')
            if self.senderrors.get(id):
                self.senderrors[id] += 1
            else:
                self.senderrors[id] = 1
            if self.senderrors.get(id) <= self.send_retries:
                self.logger.debug("Sending again: {}. Retry {}/{}".format(self.sendcommands[0], self.senderrors.get(id), self.send_retries))
                self.send_kodi_rpc(self.sendcommands[0].get('method'), params=self.sendcommands[0].get('params'), message_id=self.sendcommands[0].get('id'))
            else:
                try:
                    self.senderrors.pop(id)
                except Exception:
                    pass
                self.logger.debug("Gave up resending {} because maximum retries {} reached. Error list: {}".format(
                    self.sendcommands[0], self.send_retries, self.senderrors))
                self.sendcommands.remove(self.sendcommands[0])
                if len(self.sendcommands) > 0:
                    self.logger.debug("Sending next command: {}".format(self.sendcommands[0]))
                    self.send_kodi_rpc(self.sendcommands[0].get('method'), params=self.sendcommands[0].get('params'), message_id=self.sendcommands[0].get('id'))

    def _send_player_command(self, method, params, kodi_item):
        '''
        This method should only be called from the update item method in
        a new thread in order to handle Play/Pause and Stop commands to
        the active Kodi players
        '''
        self.logger.debug("Active players: {}".format(self.activeplayers))
        if len(self.activeplayers) == 0:
            self.logger.warning('Kodi: no active player found, skipping request!')
        else:
            if len(self.activeplayers) > 1:
                self.logger.info('Kodi: there is more than one active player. Sending request to each player!')
            params = params or {}
            for player in self.activeplayers:
                params.update({'playerid':player})
                self.send_kodi_rpc(method=method,
                                   params=params,
                                   wait=False)

    def _get_player_info(self, result=None):
        '''
        Extract information from Kodi regarding the active player and save it
        to the respective items
        '''
        self.logger.debug("Getting player info. Checking {}".format(result))
        if not isinstance(result, list):
            return
        if len(result) == 0:
            self.logger.info('No active player found.')
            for elem in self.registered_items['title']:
                elem('', caller='Kodi')
            for elem in self.registered_items['media']:
                elem('', caller='Kodi')
            for elem in self.registered_items['state']:
                elem('No Active Player', caller='Kodi')
            return
        playerid = result[0].get('playerid')
        typ = result[0].get('type')
        for elem in self.registered_items['state']:
            elem('Playing', caller='Kodi')
        self.logger.debug("Now checking player item for player with id {}".format(playerid))
        if typ == 'video':
            self.send_kodi_rpc(method='Player.GetItem',
                               params=dict(properties=['title'], playerid=playerid),
                               message_id='Player.GetItem_Video')
        elif typ == 'audio':
            for elem in self.registered_items['media']:
                elem('Audio', caller='Kodi')
            self.send_kodi_rpc(method='Player.GetItem',
                               params=dict(properties=['title', 'artist'], playerid=playerid),
                               message_id='Player.GetItem_Audio')

        elif typ == 'picture':
            for elem in self.registered_items['media']:
                elem('Picture', caller='Kodi')
            title = ''
            for elem in self.registered_items['title']:
                elem(title, caller='Kodi')
        else:
            self.logger.warning('Unknown type: {0}'.format(typ))
            return
