#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2017-2021 Marc René Frieß            rene.friess(a)gmail.com
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  onewire plugin to run with SmartHomeNG
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

import cherrypy
import datetime
from lib.model.smartplugin import *
from lib.shtime import Shtime
from .webif import WebInterface
from .api import HomeConnect
import json
import os
import time

class SHNGHomeConnect(SmartPlugin):
    PLUGIN_VERSION = "1.0.0"

    def __init__(self, sh):
        super().__init__()
        self.shtime = Shtime.get_instance()
        self._client_id = self.get_parameter_value('client_id')
        self._client_secret = self.get_parameter_value('client_secret')
        self._cycle = self.get_parameter_value('cycle')
        self._simulate = self.get_parameter_value('simulate')
        self._token = None
        self._items = {}

        if not self.init_webinterface(WebInterface):
            self._init_complete = False
        else:
            self._hc = HomeConnect(self._client_id, self._client_secret, self.get_redirect_uri(), simulate=self._simulate, token_cache=self.get_sh().get_basedir()+"/plugins/homeconnect/homeconnect_oauth_token.json", token_listener=self.set_token)
            self._token = self.get_hc().token_load()
            self.logger.debug("Token loaded: %s"%self._token)
            if self._token:
                if not self.get_hc().token_expired(self._token):
                    self._init_appliance_listeners()

    def run(self):
        self.alive = True
        self.scheduler_add('poll_data', self._update_loop, cycle=self._cycle)

    def stop(self):
        self.scheduler_remove('poll_data')
        self.alive = False

    def _update_loop(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug("Starting update loop")

        if not self.alive:
            return

        self._update()

    def _update(self):
        """
        Updates information on diverse items
        """
        self.logger.debug("Token in _update is %s"%self._token)
        if self._token:
            if not self.get_hc().token_expired(self._token):
                try:
                    for appliance in self.get_hc().get_appliances():
                        if appliance.haId + "_status" in self._items:
                            self._items[appliance.haId + "_status"](appliance.connected)
                except Exception as e:
                    self.logger.error("An exception occurred in _update %s"%e)
        pass

    def _update_listener(self):
        pass

    def _init_appliance_listeners(self):
        if self._token and not self.get_hc().token_expired(self._token):
            try:
                for appliance in self.get_hc().get_appliances():
                    appliance.listen_events(self._update_listener)
            except Exception as e:
                self.logger.error("An exception occurred in _update %s" % e)

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the Nokia Health identifier and adds it to an internal array

        :param item: The item to process.
        """
        if self.get_iattr_value(item.conf, 'homeconnect_data_type'):
            self._items[self.get_iattr_value(item.conf, 'ha_id')+"_"+self.get_iattr_value(item.conf, 'homeconnect_data_type')] = item
        pass

    def get_items(self):
        return self._items

    def get_item(self, key):
        return self._items[key]

    def get_client_id(self):
        return self._client_id

    def get_token(self):
        return self._token

    def get_programs_available(self, ha_id):
        for appliance in self.get_hc().get_appliances():
            if appliance.haId == ha_id:
                return appliance.get_programs_available()

    def get_programs_active(self, ha_id):
        for appliance in self.get_hc().get_appliances():
            if appliance.haId == ha_id:
                try:
                    return appliance.get_programs_active()
                except Exception as e:
                    self.logger.debug("An exception occurred: %s"%str(e))
                    return ""

    def get_programs_selected(self, ha_id):
        for appliance in self.get_hc().get_appliances():
            if appliance.haId == ha_id:
                return appliance.get_programs_selected()

    def get_program_options(self, ha_id, program_key):
        for appliance in self.get_hc().get_appliances():
            if appliance.haId == ha_id:
                try:
                    return appliance.get_program_options(program_key)
                except Exception as e:
                    self.logger.debug("An exception occurred: %s"%str(e))
                    return ""

    def start_program(self, ha_id, program_key, options=None):
        for appliance in self.get_hc().get_appliances():
            if appliance.haId == ha_id:
                try:
                    return appliance.start_program(program_key, options)
                except Exception as e:
                    self.logger.debug("An exception occurred: %s" % str(e))
                    return ""

    def stop_program(self, ha_id, program_key, options=None):
        for appliance in self.get_hc().get_appliances():
            if appliance.haId == ha_id:
                try:
                    return appliance.stop_program(program_key, options)
                except Exception as e:
                    self.logger.debug("An exception occurred: %s" % str(e))
                    return ""

    def set_token(self, new_token):
        self.logger.debug("Updating token: %s"%new_token)
        self._token = new_token

    def get_client_secret(self):
        return self._client_secret

    def get_hc(self):
        return self._hc

    def get_redirect_uri(self):
        ip = self.mod_http.get_local_ip_address()
        port = self.mod_http.get_local_port()
        web_ifs = self.mod_http.get_webifs_for_plugin(self.get_shortname())
        for web_if in web_ifs:
            if web_if['Instance'] == self.get_instance_name():
                redirect_uri = "http://{}:{}{}".format(ip, port, web_if['Mount'])
                self.logger.debug("WebIf of plugin {} found, callback is {}".format(self.get_fullname(),
                                                                       redirect_uri))
            return redirect_uri
        self.logger.error("Redirect URL cannot be established.".format(self.get_fullname()))

