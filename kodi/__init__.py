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
import lib.connection

logger = logging.getLogger('')


class Kodi():

    def __init__(self, smarthome):
        self._sh = smarthome
        self._boxes = []

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False
        for box in self._boxes:
            box.handle_close()

    def notify_all(self, title, message, image=None):
        for box in self._boxes:
            box.notify(title, message, image)

    def parse_item(self, item):
        if 'kodi_host' in item.conf:
            self._boxes.append(kodi(self._sh, item))


class kodi(lib.connection.Client):

    _notification_time = 10000
    _listen_keys = ['volume', 'mute', 'title', 'media', 'state']
    _send_keys = {'volume': 'Application.SetVolume', 'mute': 'Application.SetMute',
                  'left': 'Input.Left', 'right': 'Input.Right', 'up': 'Input.Up', 'down': 'Input.Down',
                  'home': 'Input.Home', 'back': 'Input.Back', 'select': 'Input.Select'}

    def __init__(self, smarthome, item):
        if 'kodi_port' in item.conf:
            port = int(item.conf['kodi_port'])
        else:
            port = 9090
        host = item.conf['kodi_host']
        lib.connection.Client.__init__(self, host, port, monitor=True)
        self.terminator = 0
        self.balance(b'{', b'}')
        self._sh = smarthome
        self._id = 1
        self._rid = None
        self._cmd_lock = threading.Lock()
        self._reply_lock = threading.Condition()
        self._reply = None
        self._items = {'state': item}
        for child in self._sh.find_children(item, 'kodi_listen'):
            listen_to = child.conf['kodi_listen']
            if listen_to in self._listen_keys:
                self._items[listen_to] = child
        for child in self._sh.find_children(item, 'kodi_send'):
            send_to = child.conf['kodi_send']
            if send_to in self._send_keys:
                child.add_method_trigger(self._send_value)
        item.notify = self.notify

    def notify(self, title, message, image=None):
        if image is None:
            self._send('GUI.ShowNotification', {'title': title, 'message': message, 'displaytime': self._notification_time})
        else:
            self._send('GUI.ShowNotification', {'title': title, 'message': message, 'image': image, 'displaytime': self._notification_time})

    def _send_value(self, item, caller=None, source=None, dest=None):
        if caller != 'Kodi':
            if 'kodi_params' not in item.conf or item.conf['kodi_params'] == 'None':
                params = None
            else:
                params = item.conf['kodi_params']
            self._send(self._send_keys[item.conf['kodi_send']], params, wait=False)

    def run(self):
        self.alive = True

    def _send(self, method, params=None, id=None, wait=True):
        self._cmd_lock.acquire()
        self._reply = None
        if id is None:
            self._id += 1
            id = self._id
            if id > 100:
                self._id = 0
        self._rid = id
        if params is not None:
            data = {"jsonrpc": "2.0", "id": id, "method": method, 'params': params}
        else:
            data = {"jsonrpc": "2.0", "id": id, "method": method}
        self._reply_lock.acquire()
        #logger.debug("Kodi sending: {0}".format(json.dumps(data, separators=(',', ':'))))
        self.send((json.dumps(data, separators=(',', ':')) + '\r\n').encode())
        if wait:
            self._reply_lock.wait(2)
        self._reply_lock.release()
        reply = self._reply
        self._reply = None
        self._cmd_lock.release()
        return reply

    def _set_item(self, key, value):
        if key in self._items:
            self._items[key](value, 'Kodi')

    def found_balance(self, data):
        event = json.loads(data.decode())
        #logger.debug("Kodi receiving: {0}".format(event))
        if 'id' in event:
            if event['id'] == self._rid:
                self._rid = None
                self._reply = event
            self._reply_lock.acquire()
            self._reply_lock.notify()
            self._reply_lock.release()
            return
        if 'method' in event:
            if event['method'] == 'Player.OnPause':
                if 'state' in self._items:
                    self._items['state']('Pause', 'Kodi')
            elif event['method'] == 'Player.OnStop':
                if 'state' in self._items:
                    self._items['state']('Menu', 'Kodi')
                if 'media' in self._items:
                    self._items['media']('', 'Kodi')
                if 'title' in self._items:
                    self._items['title']('', 'Kodi')
            elif event['method'] == 'GUI.OnScreensaverActivated':
                if 'state' in self._items:
                    self._items['state']('Screensaver', 'Kodi')
            if event['method'] in ['Player.OnPlay']:
                # use a different thread for event handling
                self._sh.trigger('kodi-event', self._parse_event, 'Kodi', value={'event': event})
            elif event['method'] in ['Application.OnVolumeChanged']:
                if 'mute' in self._items:
                    self._set_item('mute', event['params']['data']['muted'])
                if 'volume' in self._items:
                    self._set_item('volume', event['params']['data']['volume'])
            

    def _parse_event(self, event):
        if event['method'] == 'Player.OnPlay':
            result = self._send('Player.GetActivePlayers')['result']
            if len(result) == 0:
                logger.info("Kodi: no active player found.")
                return
            playerid = result[0]['playerid']
            typ = result[0]['type']
            self._items['state']('Playing', 'Kodi')
            if typ == 'video':
                result = self._send('Player.GetItem', {"properties": ["title"], "playerid": playerid}, "VideoGetItem")['result']
                title = result['item']['title']
                if not title and 'label' in result['item']:
                    title = result['item']['label']
                if 'media' in self._items:
                    typ = result['item']['type']
                    self._items['media'](typ.capitalize(), 'Kodi')
            elif typ == 'audio':
                if 'media' in self._items:
                    self._items['media'](typ.capitalize(), 'Kodi')
                result = self._send('Player.GetItem', {"properties": ["title", "artist"], "playerid": playerid}, "AudioGetItem")['result']
                if len(result['item']['artist']) == 0:
                    artist = 'unknown'
                else:
                    artist = result['item']['artist'][0]
                title = artist + ' - ' + result['item']['title']
            elif typ == 'picture':
                if 'media' in self._items:
                    self._items['media'](typ.capitalize(), 'Kodi')
                title = ''
            else:
                logger.warning("Kodi: Unknown type: {0}".format(typ))
                return
            if 'title' in self._items:
                self._items['title'](title, 'Kodi')
