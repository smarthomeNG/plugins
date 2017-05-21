#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2013 KNX-User-Forum e.V.            http://knx-user-forum.de/
#########################################################################
#  This file is part of SmartHome.py.    http://mknx.github.io/smarthome/
#
#  SmartHome.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import urllib.request
import json
import requests
import lib.connection
import re
from lib.model.smartplugin import SmartPlugin

nuki_action_items = {}
nuki_event_items = {}
nuki_battery_items = {}
paired_nukis = []

class NukiTCPDispatcher(lib.connection.Server):
    def __init__(self, ip, port):
        self._logger = logging.getLogger(__name__)
        lib.connection.Server.__init__(self, ip, port, proto='TCP')
        self.dest = 'tcp:' + ip + ':{port}'.format(port=port)
        self._logger.debug('Nuki: starting tcp listener with {url}'.format(url=self.dest))
        self.connect()

    def handle_connection(self):
        try:
            conn, address = self.socket.accept()
            data = conn.recv(1024)
            address = "{}:{}".format(address[0], address[1])
            self._logger.info("Nuki: {}: incoming connection from {}".format('test', address))
        except Exception as err:
            self._logger.error("Nuki:: {}: {}".format(self._name, err))
            return

        try:
            result = re.search('\{.*\}', data.decode('utf-8'))
            self._logger.debug('Nuki: Getting JSON String')
            nuki_bridge_response = json.loads(result.group(0))
            nuki_id = nuki_bridge_response['nukiId']
            state_name = nuki_bridge_response['stateName']
            self._logger.debug("Nuki: Status Smartlock: ID: {nuki_id} Status: {state_name}".
                               format(nuki_id=nuki_id, state_name=state_name))
            conn.send(b"HTTP/1.1 200 OK\nContent-Type: text/html\n\n")

            Nuki.update_lock_state(nuki_id, nuki_bridge_response)
        except Exception as err:
            self._logger.error("Nuki: Error parsing nuki response!\nError: {}".format(err))


class Nuki(SmartPlugin):

    PLUGIN_VERSION = "1.3.0.1"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh, bridge_ip, bridge_port, bridge_api_token, bridge_callback_ip=None,
                 bridge_callback_port=8090, protocol='http'):

        global paired_nukis
        global nuki_event_items
        global nuki_action_items
        global nuki_battery_items
        self._logger = logging.getLogger(__name__)
        self._sh = sh
        self._base_url = protocol + '://' + bridge_ip + ":" + bridge_port + '/'
        self._token = bridge_api_token
        self._callback_ip = bridge_callback_ip
        self._callback_port = bridge_callback_port
        self._action = ''
        self._noWait = ''

        if self._callback_ip is None:
            self._callback_ip = get_lan_ip()

            if not self._callback_ip:
                self._logger.critical("Nuki: Could not fetch internal ip address. Set it manually!")
                self.alive = False
                return
            self._logger.info("Nuki: using local ip address {ip}".format(ip=self._callback_ip))
        else:
            self._logger.info("Nuki: using given ip address {ip}".format(ip=self._callback_ip))

        self._callback_url = "http://{ip}:{port}/".format(ip=self._callback_ip, port=self._callback_port)

        NukiTCPDispatcher(self._callback_ip, self._callback_port)

        self._lockActions = [1,     # unlock
                             2,     # lock
                             3,     # unlatch
                             4,     # lockAndGo
                             5,     # lockAndGoWithUnlatch
                             ]

    def run(self):
        self._clear_callbacks()
        self._sh.scheduler.add("nuki_scheduler", self._scheduler_job, prio=3, cron=None, cycle=300, value=None,
                               offset=None, next=None)
        self.alive = True

    def _scheduler_job(self):
        # will also be executed at start
        self._get_paired_nukis()
        self._register_callback()
        self._get_nuki_status()

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'nuki_id'):
            self._logger.debug("parse item: {0}".format(item))
            nuki_id = self.get_iattr_value(item.conf, 'nuki_id')

            if self.has_iattr(item.conf, 'nuki_trigger'):
                nuki_trigger = self.get_iattr_value(item.conf, "nuki_trigger")
                if nuki_trigger.lower() not in ['state', 'action', 'battery']:
                    self._logger.warning("Nuki: Item {item} defines an invalid Nuki trigger {trigger}! "
                                         "It has to be 'state' or 'action'.".format(item=item, trigger=nuki_trigger))
                    return
                if nuki_trigger.lower() == 'state':
                    nuki_event_items[item] = int(nuki_id)
                elif nuki_trigger.lower() == 'action':
                    nuki_action_items[item] = int(nuki_id)
                else:
                    nuki_battery_items[item] = int(nuki_id)
            else:
                self._logger.warning("Nuki: Item {item} defines a Nuki ID but no nuki trigger! "
                                     "This item has no effect.".format(item=item))
                return
            return self.update_item

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'plugin':
            if item in nuki_action_items:
                action = item()
                if action not in self._lockActions:
                    self._logger.warning("Nuki: action {action} not in list of possible actions.".format(action=action))
                    return

                response = self._api_call(self._base_url, nuki_id=nuki_action_items[item], endpoint='lockAction',
                                          action=action, token=self._token, no_wait=self._noWait)
                if response['success']:
                    # self._get_nuki_status()
                    self._logger.info("Nuki: update item: {0}".format(item.id()))

    @staticmethod
    def update_lock_state(nuki_id, lock_state):

        nuki_battery = None
        nuki_state = None

        if 'state' in lock_state:
            nuki_state = lock_state['state']
        if 'batteryCritical' in lock_state:
            nuki_battery = 0 if not lock_state['batteryCritical'] else 1

        for item, key in nuki_event_items.items():
            if key == nuki_id:
                item(nuki_state, 'NUKI')
        for item, key in nuki_battery_items.items():
            if key == nuki_id:
                item(nuki_battery, 'NUKI')

    def _get_paired_nukis(self):
        # reset list of nukis
        del paired_nukis[:]
        response = self._api_call(self._base_url, endpoint='list', token=self._token)
        if response is None:
            return
        for nuki in response:
            paired_nukis.append(nuki['nukiId'])
            self._logger.info('Nuki: Paired Nuki Lock found: {name} - {id}'.format(name=nuki['name'], id=nuki['nukiId']))
            self._logger.debug(paired_nukis)

    def _clear_callbacks(self):
        callbacks = self._api_call(self._base_url, endpoint='callback/list', token=self._token)
        if callbacks is not None:
            for c in callbacks['callbacks']:
                response = self._api_call(self._base_url, endpoint='callback/remove', token=self._token, id=c['id'])
                if response['success']:
                    self._logger.debug("Nuki: Callback with id {id} removed.".format(id=c['id']))
                    return
                self._logger.debug("Nuki: Could not remove callback with id {id}: {message}".
                                   format(id=c['id'], message=c['message']))

    def _register_callback(self):
        found = False
        # Setting up the callback URL
        if self._callback_ip != "":
            callbacks = self._api_call(self._base_url, endpoint='callback/list', token=self._token)
            for c in callbacks['callbacks']:
                if c['url'] == self._callback_url:
                    found = True
            if not found:
                response = self._api_call(self._base_url, endpoint='callback/add', token=self._token,
                                          callback_url=self._callback_url)
                if not response['success']:
                    self._logger.warning('Nuki: Error establishing the callback url: {message}'.format
                                         (message=response['message']))
                else:
                    self._logger.info('Nuki: Callback URL registered.')
            else:
                self._logger.info('Nuki: Callback URL already registered')
        else:
            self._logger.warning('Nuki: No callback ip set. Automatic Nuki lock status updates not available.')

    def _get_nuki_status(self):
        self._logger.info("Nuki: Getting Nuki status ...")
        for nuki_id in paired_nukis:
            response = self._api_call(self._base_url, endpoint='lockState', nuki_id=nuki_id, token=self._token,
                                      no_wait=self._noWait)
            Nuki.update_lock_state(nuki_id, response)

    def _api_call(self, base_url, endpoint=None, nuki_id=None, token=None, action=None, no_wait=None, callback_url=None,
                  id=None):
        try:
            payload = {}
            if nuki_id is not None:
                payload['nukiID'] = nuki_id
            if token is not None:
                payload['token'] = token
            if action is not None:
                payload['action'] = action
            if no_wait is not None:
                payload['noWait'] = no_wait
            if callback_url is not None:
                payload['url'] = callback_url
            if id is not None:
                payload['id'] = id

            response = requests.get(url=urllib.parse.urljoin(base_url, endpoint), params=payload)
            response.raise_for_status()
            return json.loads(response.text)
        except Exception as ex:
            self._logger.error(ex)

#######################################################################
# UTIL FUNCTION
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
