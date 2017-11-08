#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 Marcus Popp                              marcus@popp.mx
#  Copyright 2017 Sebastian Sudholt      sebastian.sudholt@tu-dortmund.de
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
#  along with SmartHome.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import threading
import json

from lib.model.smartplugin import SmartPlugin
from lib.connection import Client


class Kodi(SmartPlugin, Client):
    '''
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    '''
    
    PLUGIN_VERSION='1.3c.0'
    ALLOW_MULTIINSTANCE = True

    _get_items = ['volume', 'mute', 'title', 'media', 'state', 'favorites']
    
    _set_items = {'volume'    : dict(method='Application.SetVolume', params=dict(volume='ITEM_VALUE')),
                  'mute'      : dict(method='Application.SetMute', params = dict(mute='ITEM_VALUE')),
                  'left'      : dict(method='Input.Left', params=None),
                  'right'     : dict(method='Input.Right', params=None),
                  'up'        : dict(method='Input.Up', params=None),
                  'down'      : dict(method='Input.Down', params=None),
                  'home'      : dict(method='Input.Home', params=None),
                  'back'      : dict(method='Input.Back', params=None),
                  'select'    : dict(method='Input.Select', params=None),
                  'play_pause': dict(method='Player.PlayPause', params=None),
                  'stop'      : dict(method='Player.Stop', params=None)}
    
    def __init__(self, sh, *args, **kwargs):
        '''
        Initalizes the plugin.
        '''
        # init logger
        self.logger = logging.getLogger(__name__)
        self.logger.info('Init Kodi Plugin')
        Client.__init__(self,
                        self.get_parameter_value('host'),
                        self.get_parameter_value('port'),
                        monitor=True)
        self.terminator = 0
        self.balance(b'{', b'}')
        self.message_id = 1
        self.response_id = None
        self.cmd_lock = threading.Lock()
        self.reply_lock = threading.Condition()
        self.reply = None
        self.registered_items = {key: [] for key in set(list(Kodi._set_items.keys()) + Kodi._get_items)}

    def run(self):
        '''
        Run method for the plugin
        '''        
        self.logger.debug('Plugin \'{}\': run method called'.format(self.get_shortname()))
        self.alive = True

    def stop(self):
        '''
        Stop method for the plugin
        '''
        self.logger.debug('Plugin \'{}\': stop method called'.format(self.get_shortname()))
        self.alive = False
    
    def handle_connect(self):
        '''
        This method is called on a succesful connect to Kodi        
        On a connect initialize all items with values extracted from Kodi
        '''
        # get volume and mute state
        result = self.send_kodi_rpc(method='Application.GetProperties',
                                    params=dict(properties=['volume', 'muted']))['result']
        for elem in self.registered_items['mute']:
            elem(result['muted'], caller='Kodi')
        for elem in self.registered_items['volume']:
            elem(result['volume'], caller='Kodi')
        # get the list of favorites
        result = self.send_kodi_rpc(method='Favourites.GetFavourites',
                                    params=dict(properties=['window', 'path', 'thumbnail', 'windowparameter']))['result']
        item_dict = dict()                                    
        if result['favourites'] is not None:
            item_dict = {elem['title']: elem for elem in result['favourites']}
        for elem in self.registered_items['favorites']:
            elem(item_dict, caller='Kodi')        
        # parse active player (if present)
        self._get_player_info()

    def parse_item(self, item):
        '''
        Method for parsing Kodi items.
        If the item carries the kodi_item field, this item is registered to the plugin.
        :param item:    The item to process.
        :return:        The item update method to be triggered if the kodi_item is in the set item dict.
        '''
        if self.has_iattr(item.conf, 'kodi_item'):
            kodi_item = self.get_iattr_value(item.conf, 'kodi_item')
            self.logger.debug('Plugin \'%s\', instance \'%s\': registering item: %s',
                              self.get_shortname(),
                              self.get_instance_name(),
                              item)            
            if kodi_item in self.registered_items:
                self.registered_items[kodi_item].append(item)
            else:
                self.logger.warning('I do not know the kodi_item \'%s\', skipping!', kodi_item)
            if kodi_item in Kodi._set_items:
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
        if item():
            if caller != 'Kodi' and self.has_iattr(item.conf, 'kodi_item'):
                # update item was triggered from something else then this plugin -> send to Kodi
                kodi_item = self.get_iattr_value(item.conf, 'kodi_item')
                # handle play/pause and stop separately as we need to find the active player
                if kodi_item in ['play_pause', 'stop']:
                    self.get_sh().trigger('kodi-%s' % kodi_item, self._send_player_command, 'Kodi', value=dict(kodi_item=kodi_item))
                # all other Items can be handled through a standard interface
                elif kodi_item in Kodi._set_items:
                    self.logger.debug('Plugin \'{}\': update_item ws called with item \'{}\' from caller \'{}\', source \'{}\' and dest \'{}\''.format(self.get_shortname(), item, caller, source, dest))
                    method = self._set_items[kodi_item]['method']
                    params = self._set_items[kodi_item]['params']
                    if params is not None:
                        # copy so we don't interfer with the class variable
                        params = params.copy()
                        # replace the wild card ITEM_VALUE with the item's value
                        for key, value in params.items():
                            if value == 'ITEM_VALUE':
                                params[key] = item()
                    self.send_kodi_rpc(method, params, wait=False)
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
        params = dict(title=title, message=message,displaytime=display_time)
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
        self.cmd_lock.acquire()
        self.reply = None
        if message_id is None:
            self.message_id += 1
            message_id = self.message_id
            if message_id > 99:
                self.message_id = 0
        self.response_id = message_id
        if params is not None:
            data = {'jsonrpc': '2.0', 'id': message_id, 'method': method, 'params': params}
        else:
            data = {'jsonrpc': '2.0', 'id': message_id, 'method': method}
        self.reply_lock.acquire()
        self.logger.debug('Kodi sending: {0}'.format(json.dumps(data, separators=(',', ':'))))
        self.send((json.dumps(data, separators=(',', ':')) + '\r\n').encode())
        if wait:
            self.reply_lock.wait(2)
        self.reply_lock.release()
        reply = self.reply
        self.reply = None
        self.cmd_lock.release()
        return reply

    def found_balance(self, data):
        '''
        This method is called whenever data is received from the connection to
        Kodi.
        '''
        event = json.loads(data.decode())
        self.logger.debug('Kodi receiving: {0}'.format(event))
        if 'id' in event:
            if event['id'] == self.response_id:
                self.response_id = None
                self.reply = event
            self.reply_lock.acquire()
            self.reply_lock.notify()
            self.reply_lock.release()
            return
        if 'method' in event:
            if event['method'] == 'Player.OnPause':
                for elem in self.registered_items['state']:
                    elem('Pause', caller='Kodi')
            elif event['method'] == 'Player.OnStop':
                for elem in self.registered_items['state']:
                    elem('Stopped Player', caller='Kodi')
                for elem in self.registered_items['media']:
                    elem('', caller='Kodi')
                for elem in self.registered_items['title']:
                    elem('', caller='Kodi')
            elif event['method'] == 'GUI.OnScreensaverActivated':
                for elem in self.registered_items['state']:
                    elem('Screensaver', caller='Kodi')
            if event['method'] in ['Player.OnPlay']:
                # use a different thread for event handling
                self.get_sh().trigger('kodi-player-start', self._get_player_info, 'Kodi')
            elif event['method'] in ['Application.OnVolumeChanged']:
                for elem in self.registered_items['mute']:
                    elem(event['params']['data']['muted'], caller='Kodi')
                for elem in self.registered_items['volume']:
                    elem(event['params']['data']['volume'], caller='Kodi')
    
    def _send_player_command(self, kodi_item):
        '''
        This method should only be called from the update item method in
        a new thread in order to handle Play/Pause and Stop commands to
        the active Kodi players
        '''
        # get the currently active players
        result = self.send_kodi_rpc(method='Player.GetActivePlayers')
        result = result['result']
        if len(result) == 0:
            self.logger.warning('Kodi: no active player found, skipping request!')
        else:
            if len(result) > 1:
                self.logger.info('Kodi: there is more than one active player. Sending request to each player!')
            for player in result:
                player_id = player['playerid']
                self.send_kodi_rpc(method=self._set_items[kodi_item]['method'],
                                   params=dict(playerid=player_id),
                                   wait=False)

    def _get_player_info(self):
        '''
        Extract information from Kodi regarding the active player and save it
        to the respective items
        '''
        result = self.send_kodi_rpc(method='Player.GetActivePlayers')['result']
        if len(result) == 0:
            self.logger.info('Kodi: no active player found.')
            for elem in self.registered_items['title']:
                elem('', caller='Kodi')
            for elem in self.registered_items['media']:
                elem('', caller='Kodi')
            for elem in self.registered_items['state']:
                elem('No Active Player', caller='Kodi')
            return
        playerid = result[0]['playerid']
        typ = result[0]['type']
        for elem in self.registered_items['state']:
            elem('Playing', caller='Kodi')
        if typ == 'video':
            result = self.send_kodi_rpc(method='Player.GetItem',
                                        params=dict(properties=['title'], playerid=playerid),
                                        message_id='VideoGetItem')['result']
            title = result['item']['title']
            typ = result['item']['type']
            if not title and 'label' in result['item']:
                title = result['item']['label']
            for elem in self.registered_items['media']:
                elem(typ.capitalize(), caller='Kodi')
        elif typ == 'audio':
            for elem in self.registered_items['media']:
                elem('Audio', caller='Kodi')                
            result = self.send_kodi_rpc(method='Player.GetItem',
                                        params=dict(properties=['title', 'artist'], playerid=playerid),
                                        message_id='AudioGetItem')['result']
            if len(result['item']['artist']) == 0:
                artist = 'unknown'
            else:
                artist = result['item']['artist'][0]
            title = artist + ' - ' + result['item']['title']
        elif typ == 'picture':
            for elem in self.registered_items['media']:
                elem('Picture', caller='Kodi')
            title = ''
        else:
            self.logger.warning('Kodi: Unknown type: {0}'.format(typ))
            return
        for elem in self.registered_items['title']:
            elem(title, caller='Kodi')
