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
import cherrypy
import time
from jinja2 import Environment, FileSystemLoader
from lib.model.smartplugin import *
from lib.item import Items
from bin.smarthome import VERSION

nuki_action_items = {}
nuki_event_items = {}
nuki_battery_items = {}
paired_nukis = []
lock = False


class NukiTCPDispatcher(lib.connection.Server):
    def __init__(self, plugin):
        self.plugin = plugin
        lib.connection.Server.__init__(self, self.plugin.get_callback_ip(), self.plugin.get_callback_port(),
                                       proto='TCP')
        self.dest = 'tcp:' + self.plugin.get_callback_ip() + ':{port}'.format(port=self.plugin.get_callback_port())
        self.plugin.logger.debug("Plugin '{pluginname}' - NukiTCPDispatcher: starting tcp listener with {url}".format(
            pluginname=self.plugin.get_shortname(), url=self.dest))
        self.connect()

    def handle_connection(self):
        try:
            conn, address = self.socket.accept()
            data = conn.recv(1024)
            address = "{}:{}".format(address[0], address[1])
            self.plugin.logger.info(
                "Plugin '{}' - NukiTCPDispatcher: {}: incoming connection from {}".format(self.plugin.get_shortname(),
                                                                                          'test', address))
        except Exception as err:
            self.logger.error("Plugin '{pluginname}':: {}: {}".format(self.plugin.get_shortname(), self._name, err))
            return

        try:
            result = re.search('\{.*\}', data.decode('utf-8'))
            self.plugin.logger.debug(
                "Plugin '{}' - NukiTCPDispatcher: Getting JSON String".format(self.plugin.get_shortname()))
            nuki_bridge_response = json.loads(result.group(0))
            nuki_id = nuki_bridge_response['nukiId']
            state_name = nuki_bridge_response['stateName']
            self.plugin.logger.debug(
                "Plugin '{pluginname}' - NukiTCPDispatcher: Status Smartlock: ID: {nuki_id} Status: {state_name}".
                format(pluginname=self.plugin.get_shortname(), nuki_id=nuki_id, state_name=state_name))
            conn.send(b"HTTP/1.1 200 OK\nContent-Type: text/html\n\n")

            Nuki.update_lock_state(nuki_id, nuki_bridge_response)
        except Exception as err:
            self.plugin.logger.error("Plugin '{}' - NukiTCPDispatcher: Error parsing nuki response!\nError: {}".format(
                self.plugin.get_shortname(), err))


class Nuki(SmartPlugin):
    PLUGIN_VERSION = "1.5.0.4"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh, *args, **kwargs):

        global paired_nukis
        global nuki_event_items
        global nuki_action_items
        global nuki_battery_items
        global lock
        global request_queue

        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self._base_url = self.get_parameter_value('protocol') + '://' + self.get_parameter_value(
            'bridge_ip') + ":" + str(self.get_parameter_value('bridge_port')) + '/'
        self._token = self.get_parameter_value('bridge_api_token')
        self._callback_ip = self.get_parameter_value('bridge_callback_ip')
        self._callback_port = self.get_parameter_value('bridge_callback_port')
        self._action = ''
        self._noWait = self.get_parameter_value('no_wait')
        self.items = Items.get_instance()

        if self._callback_ip is None or self._callback_ip in ['0.0.0.0', '']:
            self._callback_ip = self.get_local_ipv4_address()

            if not self._callback_ip:
                self.logger.critical(
                    "Plugin '{}': Could not fetch internal ip address. Set it manually!".format(self.get_shortname()))
                self.alive = False
                return
            self.logger.info(
                "Plugin '{pluginname}': using local ip address {ip}".format(pluginname=self.get_shortname(),
                                                                            ip=self._callback_ip))
        else:
            self.logger.info(
                "Plugin '{pluginname}': using given ip address {ip}".format(pluginname=self.get_shortname(),
                                                                            ip=self._callback_ip))

        self._callback_url = "http://{ip}:{port}/".format(ip=self._callback_ip, port=self._callback_port)

        NukiTCPDispatcher(self)

        self._lockActions = [1,  # unlock
                             2,  # lock
                             3,  # unlatch
                             4,  # lockAndGo
                             5,  # lockAndGoWithUnlatch
                             ]

        self.init_webinterface()

    def run(self):
        self._clear_callbacks()
        self.scheduler_add(__name__, self._scheduler_job, prio=3, cron=None, cycle=300, value=None,
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
            self.logger.debug("Plugin '{0}': parse item: {1}".format(self.get_shortname(), item))
            nuki_id = self.get_iattr_value(item.conf, 'nuki_id')

            if self.has_iattr(item.conf, 'nuki_trigger'):
                nuki_trigger = self.get_iattr_value(item.conf, "nuki_trigger")
                if nuki_trigger.lower() not in ['state', 'action', 'battery']:
                    self.logger.warning("Plugin '{pluginname}': Item {item} defines an invalid Nuki trigger {trigger}! "
                                        "It has to be 'state' or 'action'.".format(pluginname=self.get_shortname(),
                                                                                   item=item, trigger=nuki_trigger))
                    return
                if nuki_trigger.lower() == 'state':
                    nuki_event_items[item] = int(nuki_id)
                elif nuki_trigger.lower() == 'action':
                    nuki_action_items[item] = int(nuki_id)
                else:
                    nuki_battery_items[item] = int(nuki_id)
            else:
                self.logger.warning("Plugin '{pluginname}': Item {item} defines a Nuki ID but no nuki trigger! "
                                    "This item has no effect.".format(pluginname=self.get_shortname(), item=item))
                return
            return self.update_item

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'plugin':
            if item in nuki_action_items:
                action = item()
                if action not in self._lockActions:
                    self.logger.warning(
                        "Plugin '{pluginname}': action {action} not in list of possible actions.".format(
                            pluginname=self.get_shortname(), action=action))
                    return

                response = self._api_call(self._base_url, nuki_id=nuki_action_items[item], endpoint='lockAction',
                                          action=action, token=self._token, no_wait=self._noWait)
                if response is not None:
                    if response['success']:
                        # self._get_nuki_status()
                        self.logger.info("Plugin '{0}': update item: {1}".format(self.get_shortname(), item.id()))
                else:
                    self.logger.error("Plugin '{}': no response.".format(self.get_shortname()))

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
            self.logger.info(
                "Plugin '{pluginname}': Paired Nuki Lock found: {name} - {id}".format(pluginname=self.get_shortname(),
                                                                                      name=nuki['name'],
                                                                                      id=nuki['nukiId']))
            self.logger.debug(paired_nukis)

    def _clear_callbacks(self):
        callbacks = self._api_call(self._base_url, endpoint='callback/list', token=self._token)
        if callbacks is not None:
            for c in callbacks['callbacks']:
                response = self._api_call(self._base_url, endpoint='callback/remove', token=self._token, id=c['id'])
                if response['success']:
                    self.logger.debug(
                        "Plugin '{pluginname}': Callback with id {id} removed.".format(pluginname=self.get_shortname(),
                                                                                       id=c['id']))
                    return
                self.logger.debug("Plugin '{pluginname}': Could not remove callback with id {id}: {message}".
                                  format(pluginname=self.get_shortname(), id=c['id'], message=c['message']))

    def _register_callback(self):
        found = False
        # Setting up the callback URL
        if self._callback_ip != "":
            callbacks = self._api_call(self._base_url, endpoint='callback/list', token=self._token)
            if callbacks is not None:
                for c in callbacks['callbacks']:
                    if c['url'] == self._callback_url:
                        found = True
                if not found:
                    response = self._api_call(self._base_url, endpoint='callback/add', token=self._token,
                                              callback_url=self._callback_url)
                    if not response['success']:
                        self.logger.warning("Plugin '{pluginname}': Error establishing the callback url: {message}".format
                                            (pluginname=self.get_shortname(), message=response['message']))
                    else:
                        self.logger.info("Plugin '{}': Callback URL registered.".format
                                         (self.get_shortname()))
                else:
                    self.logger.info("Plugin '{}': Callback URL already registered".format
                                     (self.get_shortname()))
        else:
            self.logger.warning(
                "Plugin '{}': No callback ip set. Automatic Nuki lock status updates not available.".format
                (self.get_shortname()))

    def _get_nuki_status(self):
        self.logger.info("Plugin '{}': Getting Nuki status ...".format
                         (self.get_shortname()))
        for nuki_id in paired_nukis:
            response = self._api_call(self._base_url, endpoint='lockState', nuki_id=nuki_id, token=self._token,
                                      no_wait=self._noWait)
            Nuki.update_lock_state(nuki_id, response)

    def _api_call(self, base_url, endpoint=None, nuki_id=None, token=None, action=None, no_wait=None, callback_url=None,
                  id=None):
        global lock
        while lock:
            time.sleep(0.1)
        try:
            lock = True
            self.logger.debug("Plugin '{}': Lock set.".format(self.get_shortname()))
            payload = {}
            if nuki_id is not None:
                payload['nukiID'] = nuki_id
            if token is not None:
                payload['token'] = token
            if action is not None:
                payload['action'] = action
            if no_wait is not None:
                payload['noWait'] = int(no_wait)
                self.logger.debug("Plugin '{}': noWait is {}".format(self.get_shortname(), int(no_wait)))
            if callback_url is not None:
                payload['url'] = callback_url
            if id is not None:
                payload['id'] = id
            url = urllib.parse.urljoin(base_url, endpoint)
            self.logger.debug("Plugin '{}': starting API Call to Nuki Bridge at {} with payload {}.".format(self.get_shortname(), url, payload))
            response = requests.get(url=urllib.parse.urljoin(base_url, endpoint), params=payload)
            self.logger.debug("Plugin '{}': finishing API Call to Nuki Bridge at {}.".format(self.get_shortname(), url))
            response.raise_for_status()
            lock = False
            self.logger.debug("Plugin '{}': Lock removed.".format(self.get_shortname()))
            return json.loads(response.text)
        except Exception as ex:
            lock = False
            self.logger.error(ex)

    def get_event_items(self):
        return nuki_event_items

    def get_battery_items(self):
        return nuki_battery_items

    def get_action_items(self):
        return nuki_action_items

    def get_callback_ip(self):
        return self._callback_ip

    def get_callback_port(self):
        return self._callback_port

    def get_callback_url(self):
        return self._callback_url

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http is None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin

        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           interface=None,
                           item_count=len(self.plugin.get_event_items()) + len(self.plugin.get_action_items()) + len(
                               self.plugin.get_battery_items()),
                           plugin_info=self.plugin.get_info(), tabcount=1,
                           p=self.plugin)

    @cherrypy.expose
    def triggerAction(self, path, value):
        if path is None:
            self.plugin.logger.error("Plugin '{}': Path parameter is missing when setting action item value!".format(self.get_shortname()))
            return
        if value is None:
            self.plugin.logger.error("Plugin '{}': Value parameter is missing when setting action item value!".format(self.get_shortname()))
            return
        item = self.plugin.items.return_item(path)
        item(int(value), caller=self.plugin.get_shortname(), source='triggerAction()')
        return