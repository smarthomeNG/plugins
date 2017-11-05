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

# import logging
# import threading
# import json
# 
# import lib.connection
# 
# logger = logging.getLogger('')
# 
# 
# class Kodi(object):
#     
#     def __init__(self, smarthome, host, port='9090'):
#         self._sh = smarthome
#         self._boxes = []
# 
#     def run(self):
#         self.alive = True
# 
#     def stop(self):
#         self.alive = False
#         for box in self._boxes:
#             box.handle_close()
# 
#     def notify_all(self, title, message, image=None):
#         for box in self._boxes:
#             box.notify(title, message, image)
# 
#     def parse_item(self, item):
#         if 'kodi_host' in item.conf:
#             self._boxes.append(kodi(self._sh, item))
# 
# 
# class kodi(lib.connection.Client):
# 
#     _notification_time = 10000
#     _listen_keys = ['volume', 'mute', 'title', 'media', 'state']
#     _send_keys = {'volume': 'Application.SetVolume', 'mute': 'Application.SetMute',
#                   'left': 'Input.Left', 'right': 'Input.Right', 'up': 'Input.Up', 'down': 'Input.Down',
#                   'home': 'Input.Home', 'back': 'Input.Back', 'select': 'Input.Select'}
# 
#     def __init__(self, smarthome, item):
#         if 'kodi_port' in item.conf:
#             port = int(item.conf['kodi_port'])
#         else:
#             port = 9090
#         host = item.conf['kodi_host']
#         lib.connection.Client.__init__(self, host, port, monitor=True)
#         self.terminator = 0
#         self.balance(b'{', b'}')
#         self._sh = smarthome
#         self.message_id = 1
#         self._rid = None
#         self._cmd_lock = threading.Lock()
#         self._reply_lock = threading.Condition()
#         self._reply = None
#         self._items = {'state': item}
#         for child in self._sh.find_children(item, 'kodi_listen'):
#             listen_to = child.conf['kodi_listen']
#             if listen_to in self._listen_keys:
#                 self._items[listen_to] = child
#         for child in self._sh.find_children(item, 'kodi_send'):
#             send_to = child.conf['kodi_send']
#             if send_to in self._send_keys:
#                 child.add_method_trigger(self._send_value)
#         item.notify = self.notify
# 
#     def notify(self, title, message, image=None):
#         if image is None:
#             self._send('GUI.ShowNotification', {'title': title, 'message': message, 'displaytime': self._notification_time})
#         else:
#             self._send('GUI.ShowNotification', {'title': title, 'message': message, 'image': image, 'displaytime': self._notification_time})
# 
#     def _send_value(self, item, caller=None, source=None, dest=None):
#         if caller != 'Kodi':
#             if 'kodi_params' not in item.conf or item.conf['kodi_params'] == 'None':
#                 params = None
#             else:
#                 params = item.conf['kodi_params']
#             self._send(self._send_keys[item.conf['kodi_send']], params, wait=False)
# 
#     def run(self):
#         self.alive = True
# 
#     def _send(self, method, params=None, id=None, wait=True):
#         self._cmd_lock.acquire()
#         self._reply = None
#         if id is None:
#             self.message_id += 1
#             id = self.message_id
#             if id > 100:
#                 self.message_id = 0
#         self._rid = id
#         if params is not None:
#             data = {"jsonrpc": "2.0", "id": id, "method": method, 'params': params}
#         else:
#             data = {"jsonrpc": "2.0", "id": id, "method": method}
#         self._reply_lock.acquire()
#         #logger.debug("Kodi sending: {0}".format(json.dumps(data, separators=(',', ':'))))
#         self.send((json.dumps(data, separators=(',', ':')) + '\r\n').encode())
#         if wait:
#             self._reply_lock.wait(2)
#         self._reply_lock.release()
#         reply = self._reply
#         self._reply = None
#         self._cmd_lock.release()
#         return reply
# 
#     def _set_item(self, key, value):
#         if key in self._items:
#             self._items[key](value, 'Kodi')
# 
#     def found_balance(self, data):
#         event = json.loads(data.decode())
#         #logger.debug("Kodi receiving: {0}".format(event))
#         if 'id' in event:
#             if event['id'] == self._rid:
#                 self._rid = None
#                 self._reply = event
#             self._reply_lock.acquire()
#             self._reply_lock.notify()
#             self._reply_lock.release()
#             return
#         if 'method' in event:
#             if event['method'] == 'Player.OnPause':
#                 if 'state' in self._items:
#                     self._items['state']('Pause', 'Kodi')
#             elif event['method'] == 'Player.OnStop':
#                 if 'state' in self._items:
#                     self._items['state']('Menu', 'Kodi')
#                 if 'media' in self._items:
#                     self._items['media']('', 'Kodi')
#                 if 'title' in self._items:
#                     self._items['title']('', 'Kodi')
#             elif event['method'] == 'GUI.OnScreensaverActivated':
#                 if 'state' in self._items:
#                     self._items['state']('Screensaver', 'Kodi')
#             if event['method'] in ['Player.OnPlay']:
#                 # use a different thread for event handling
#                 self._sh.trigger('kodi-event', self._parse_event, 'Kodi', value={'event': event})
#             elif event['method'] in ['Application.OnVolumeChanged']:
#                 if 'mute' in self._items:
#                     self._set_item('mute', event['params']['data']['muted'])
#                 if 'volume' in self._items:
#                     self._set_item('volume', event['params']['data']['volume'])
#             
# 
#     def _parse_event(self, event):
#         if event['method'] == 'Player.OnPlay':
#             result = self._send('Player.GetActivePlayers')['result']
#             if len(result) == 0:
#                 logger.info("Kodi: no active player found.")
#                 return
#             playerid = result[0]['playerid']
#             typ = result[0]['type']
#             self._items['state']('Playing', 'Kodi')
#             if typ == 'video':
#                 result = self._send('Player.GetItem', {"properties": ["title"], "playerid": playerid}, "VideoGetItem")['result']
#                 title = result['item']['title']
#                 if not title and 'label' in result['item']:
#                     title = result['item']['label']
#                 if 'media' in self._items:
#                     typ = result['item']['type']
#                     self._items['media'](typ.capitalize(), 'Kodi')
#             elif typ == 'audio':
#                 if 'media' in self._items:
#                     self._items['media'](typ.capitalize(), 'Kodi')
#                 result = self._send('Player.GetItem', {"properties": ["title", "artist"], "playerid": playerid}, "AudioGetItem")['result']
#                 if len(result['item']['artist']) == 0:
#                     artist = 'unknown'
#                 else:
#                     artist = result['item']['artist'][0]
#                 title = artist + ' - ' + result['item']['title']
#             elif typ == 'picture':
#                 if 'media' in self._items:
#                     self._items['media'](typ.capitalize(), 'Kodi')
#                 title = ''
#             else:
#                 logger.warning("Kodi: Unknown type: {0}".format(typ))
#                 return
#             if 'title' in self._items:
#                 self._items['title'](title, 'Kodi')
                
        
        ###
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

    _listen_keys = ['volume', 'mute', 'title', 'media', 'state']
    _send_keys = {'volume': dict(method='Application.SetVolume', params=dict(volume='ITEM_VALUE')),
                  'mute  ': dict(method='Application.SetMute', params = dict(mute='ITEM_VALUE')),
                  'left'  : dict(method='Input.Left', params=None),
                  'right' : dict(method='Input.Right', params=None),
                  'up'    : dict(method='Input.Up', params=None),
                  'down'  : dict(method='Input.Down', params=None),
                  'home'  : dict(method='Input.Home', params=None),
                  'back'  : dict(method='Input.Back', params=None),
                  'select': dict(method='Input.Select', params=None)}
    
    def __init__(self, sh, *args, **kwargs):
        '''
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions **beyond** 1.3: **Don't use it**! 
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!
        
        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.
        
        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are implemented
        to support oder plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method `get_parameter_value(parameter_name)` instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling `self.get_parameter_value(parameter_name)`. It
        returns the value in the datatype that is defined in the metadata.
        '''
        # init logger
        self.logger = logging.getLogger(__name__)
        self.logger.info('Init Kodi Plugin')
        
        # setup everything for the connection later
#         if 'kodi_port' in item.conf:
#             port = int(item.conf['kodi_port'])
#         else:
#             port = 9090
#         host = item.conf['kodi_host']
        Client.__init__(self,
                        self.get_parameter_value('host'),
                        self.get_parameter_value('port'),
                        monitor=True)
        self.terminator = 0
        self.balance(b'{', b'}')
#         self._sh = smarthome
        self.message_id = 1
        self.response_id = None
        self.cmd_lock = threading.Lock()
        self.reply_lock = threading.Condition()
        self.reply = None
        self.registered_items = {key: [] for key in set(Kodi._send_keys.keys() + Kodi._listen_keys)}
#         self._items = {'state': item}
#         for child in self._sh.find_children(item, 'kodi_listen'):
#             listen_to = child.conf['kodi_listen']
#             if listen_to in self._listen_keys:
#                 self._items[listen_to] = child
#         for child in self._sh.find_children(item, 'kodi_send'):
#             send_to = child.conf['kodi_send']
#             if send_to in self._send_keys:
#                 child.add_method_trigger(self._send_value)
#         item.notify = self.notify


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


    def parse_item(self, item):
        '''
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
        '''
        if self.has_iattr(item.conf, 'kodi_item'):
            self.logger.debug('Plugin \'{}\': parse item: {}'.format(self.get_shortname(), item))
            if item.name in Kodi._send_keys:
                return self.update_item

        # todo
        # if interesting item for sending values:
        #   return update_item


    def parse_logic(self, logic):
        '''
        Default plugin parse_logic method
        '''
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
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
                # update item was triggered from sometthing else then this plugin -> send to Kodi
                kodi_item = self.get_iattr_value(item.conf, 'kodi_item')
                if kodi_item in Kodi._send_keys:
                    self.logger.debug('Plugin \'{}\': update_item ws called with item \'{}\' from caller \'{}\', source \'{}\' and dest \'{}\''.format(self.get_shortname(), item, caller, source, dest))
                    method = self._send_keys[kodi_item]['method']
                    params = self._send_keys[kodi_item]['params']
                    if params is not None:
                        # copy so we don't interfer with the class variable
                        params = params.copy()
                        # replace the wild card ITEM_VALUE with the item's value
                        for key, value in params.items():
                            if value == 'ITEM_VALUE':
                                params[key] = item()
                    self._send(method, params, wait=False)
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

#     def _send_value(self, item, caller=None, source=None, dest=None):
#         if caller != 'Kodi':
#             if 'kodi_params' not in item.conf or item.conf['kodi_params'] == 'None':
#                 params = None
#             else:
#                 params = item.conf['kodi_params']
#             self.send_kodi_rpc(self._send_keys[item.conf['kodi_send']], params, wait=False)

    def send_kodi_rpc(self, method, params=None, message_id=None, wait=True):
        self.cmd_lock.acquire()
        self.reply = None
        if message_id is None:
            self.message_id += 1
            message_id = self.message_id
            if id > 100:
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

#     def _set_item(self, key, value):
#         if key in self._items:
#             self._items[key](value, 'Kodi')

    def found_balance(self, data):
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
#                 if 'state' in self._items:
#                     self._items['state']('Pause', 'Kodi')
            elif event['method'] == 'Player.OnStop':
#                 if 'state' in self._items:
#                     self._items['state']('Menu', 'Kodi')
                for elem in self.registered_items['state']:
                    elem('Pause', caller='Kodi')
#                 if 'media' in self._items:
#                     self._items['media']('', 'Kodi')
                for elem in self.registered_items['media']:
                    elem('', caller='Kodi')
#                 if 'title' in self._items:
#                     self._items['title']('', 'Kodi')
                for elem in self.registered_items['title']:
                    elem('Pause', caller='Kodi')
            elif event['method'] == 'GUI.OnScreensaverActivated':
#                 if 'state' in self._items:
#                     self._items['state']('Screensaver', 'Kodi')
                for elem in self.registered_items['state']:
                    elem('Screensaver', caller='Kodi')
            if event['method'] in ['Player.OnPlay']:
                # use a different thread for event handling
                self.get_sh().trigger('kodi-event', self._parse_event, 'Kodi', value={'event': event})
            elif event['method'] in ['Application.OnVolumeChanged']:
#                 if 'mute' in self._items:
#                     self._set_item('mute', event['params']['data']['muted'])
                for elem in self.registered_items['mute']:
                    elem(event['params']['data']['muted'], caller='Kodi')
#                 if 'volume' in self._items:
#                     self._set_item('volume', event['params']['data']['volume'])
                for elem in self.registered_items['volume']:
                    elem(event['params']['data']['volume'], caller='Kodi')

    def _parse_event(self, event):
        if event['method'] == 'Player.OnPlay':
            result = self.send_kodi_rpc(method='Player.GetActivePlayers')['result']
            if len(result) == 0:
                self.logger.info('Kodi: no active player found.')
                return
            playerid = result[0]['playerid']
            typ = result[0]['type']
#             self._items['state']('Playing', 'Kodi')
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
#                 if 'media' in self._items:
#                     typ = result['item']['type']
#                     self._items['media'](typ.capitalize(), 'Kodi')
                for elem in self.registered_items['media']:
                    elem(typ.capitalize(), caller='Kodi')
            elif typ == 'audio':
#                 if 'media' in self._items:
#                     self._items['media'](typ.capitalize(), 'Kodi')
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
#                 if 'media' in self._items:
#                     self._items['media'](typ.capitalize(), 'Kodi')
                for elem in self.registered_items['media']:
                    elem('Picture', caller='Kodi')
                title = ''
            else:
                self.logger.warning('Kodi: Unknown type: {0}'.format(typ))
                return
#             if 'title' in self._items:
#                 self._items['title'](title, 'Kodi')
            for elem in self.registered_items['title']:
                elem(title, caller='Kodi')
