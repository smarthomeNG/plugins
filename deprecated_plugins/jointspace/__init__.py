#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2016 Serge Wagener (Foxi352)             serge@wagener.family
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

from lib.model.smartplugin import SmartPlugin
from time import sleep

import requests
import json

logger = logging.getLogger('Jointspace')


class Jointspace(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.1.2"
    # Initialize connection to receiver
    def __init__(self, smarthome, host, port=1925, cycle=15):
        logger.info("Jointspace: talking with jointspace running on TV set {0}:{1}".format(host, port))
        self._sh = smarthome
        self._items = {}
        self._host = host
        self._port = port
        self._version = 1
        self._volmin = 0
        self._volmax = 0
        self._muted = False
        self._power = False
        self._volume = 0
        # Poll status objects
        self._sh.scheduler.add('joinstpace-status-update', self._update_status, cycle=cycle)

    # Set plugin to alive
    def run(self):
        self.alive = True

    # Close connection to receiver and set alive to false
    def stop(self):
        self.alive = False
        self.close()

    # Parse items and bind commands to plugin
    def parse_item(self, item):

        if 'jointspace_cmd' in item.conf:
            cmd = item.conf['jointspace_cmd']
            if (cmd is None):
                return None
            else:
                self._items[cmd] = item
                logger.debug("Jointspace: Command {0} found".format(cmd))
            return self.update_item

        elif 'jointspace_listen' in item.conf:
            info = item.conf['jointspace_listen']
            if (info is None):
                return None
            else:
                self._items[info] = item
                logger.debug("Jointspace: Listening to {} info".format(info))
            return self.update_item
        else:
            return None

    # TODO: Logic not yet used
    def parse_logic(self, logic):
        pass

    # Receive commands, process them and forward them to receiver
    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'Jointspace':
            if 'jointspace_cmd' in item.conf:
                command = item.conf['jointspace_cmd']
                if (' ' in command):
                    args = command.split(' ')
                    command = args[0]
                    del args[0]
                value = item()
                logger.debug("Jointspace: {0} set {1} to {2} for {3}".format(caller, command, value, item.id()))
                if(command == 'power') and (isinstance(value, bool)):
                    if not value:
                        logger.info("Jointspace: Powering down")
                        self._send_key('Standby')
                    else:
                        logger.warning("Jointspace: Power on not supported by jointspace API interface")
                elif(command == 'mute') and (isinstance(value, bool)):
                    self._post_json("/audio/volume", body = {'muted': value})
                elif(command == 'volume') and (isinstance(value, int)):
                    self._post_json("/audio/volume", body = {'current': int(value * self._volmax / 255)})
                elif(command == 'channel'):
                    channel = args[0]
                    logger.info("Jointspace: switching to channel {}".format(channel))
                    for digit in channel:
                        self._send_key('Digit' + digit)
                        sleep(0.2)
                    self._send_key('Confirm')
                elif(command == 'source'):
                    self._post_json("/sources/current", body = {'id': value})
                elif(command == 'sendkey'):
                    key = args[0]
                    logger.info("Jointspace: sending key {}".format(key))
                    self._send_key(key)
                else:
                    logger.warning("Jointspace: Command {0} or value {1} invalid".format(command, value))

    # Poll Jointspace REST API for status
    def _update_status(self):
        resp = self._request_json("/audio/volume")
        logger.debug("RESP {}".format(resp))
        if(resp):
            self._volmin = int(resp['min'])
            self._volmax = int(resp['max'])
            self._muted = resp['muted']
            if not self._power:
                self._poll_channels
            self._power = True
            self._volume = int(resp['current']) * 255 / self._volmax
            if 'power' in self._items:
                self._items['power'](self._power, 'Jointspace', self._host)
            if 'mute' in self._items:
                self._items['mute'](self._muted, 'Jointspace', self._host)
            if 'volume' in self._items:
                self._items['volume'](self._volume, 'Jointspace', self._host)
        else:
            logger.debug("Jointspace: Error receiving response from TV, maybe switched off ?")
            self._power = False
            if 'power' in self._items:
                self._items['power'](self._power, 'Jointspace', self._host)
            self._muted = False
            if 'mute' in self._items:
                self._items['mute'](self._muted, 'Jointspace', self._host)
        resp = self._request_json("/channels/current")
        
        # Get ID of current channel and poll for preset number and channel name
        if(resp):
            logger.debug("Jointspace: Getting details for channel {}".format(resp['id']))
            resp = self._request_json("/channels/" + resp['id'])
            if(resp):
                self._channel = resp['preset'] + ' - ' + resp['name']
                logger.debug("Jointspace: Channel is {}".format(self._channel))
                if 'channel' in self._items:
                    self._items['channel'](self._channel, 'Jointspace', self._host)
        # Get current source
        resp = self._request_json("/sources/current")
        if(resp):
            _id = resp['id']
            logger.debug("Jointspace: Getting details for source {}".format(_id))
            resp = self._request_json("/sources")
            if(resp):
                self._source = resp[_id]['name']
                logger.debug("Jointspace: Source is {}".format(self._source))
                if 'source' in self._items:
                    self._items['source'](self._source, 'Jointspace', self._host)

    # Poll channellist
    def _poll_channels(self):
        return
        resp = self._request_json("/channels")
        if(resp):
            logger.debug("Jointspace: got channellist")
            print(resp)

    # simulate a TV remote key press
    def _send_key(self, key):
        return self._post_json("/input/key", body = {'key': key})

    # post json requests to Jointspace REST API
    def _post_json(self, path, body):
        headers = { 'User-Agent': 'SmartHomeNG', 'Content-Type': 'application/json; charset=UTF-8' }
        url = 'http://' + self._host + ':' + str(self._port) + '/' + str(self._version) + path
        logger.debug("Jointspace: Sending {0} to {1}".format(body, url))
        
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=1)
        except:
            return False

        logger.debug("Jointspace: Response-> {}".format(resp.text))

        if(resp.status_code != 200):
            return False

        return True

    # request json data from Jointspace REST API
    def _request_json(self, path):
        headers = { 'User-Agent': 'SmartHomeNG', 'Content-Type': 'application/json; charset=UTF-8' }
        url = 'http://' + self._host + ':' + str(self._port) + '/' + str(self._version) + path
        logger.debug("Jointspace: Reading from {}".format(url))

        try:
            resp = requests.get(url, headers=headers, timeout=1)
        except:
            return False
            
        if(resp.status_code != 200):
            return False

        logger.debug("Jointspace: Response -> {0}".format(resp.json()))
        return resp.json()
