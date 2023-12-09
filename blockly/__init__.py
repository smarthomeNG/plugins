#!/usr/bin/env python3
# -*- coding: utf8 -*-
#########################################################################
# Copyright 2016-       Martin Sinn                         m.sinn@gmx.de
#                       René Frieß                  rene.friess@gmail.com
#                       Dirk Wallmeier                dirk@wallmeier.info
#########################################################################
#  Blockly plugin for SmartHomeNG
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import socket
import time

import collections
import ast

import lib.config
from lib.model.smartplugin import SmartPlugin
from .webif import WebInterface

#from lib.module import Modules


from .utils import *

import lib.shyaml as shyaml
#from lib.constants import (YAML_FILE, CONF_FILE)


class Blockly(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION='1.5.0'


    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions **beyond** 1.3: **Don't use it**! Use the method self.get_sh() instead
        """
#        self.logger = SmartPluginLogger(__name__, self)
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Blockly.__init__')

        self.init_webinterface(WebInterface)


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Plugin '{}': run method called".format(self.get_shortname()))
        self.alive = True
        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Plugin '{}': stop method called".format(self.get_shortname()))
        self.alive = False


    def parse_item(self, item):
        """
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
        """
        if self.has_iattr(item.conf, 'foo_itemtag'):
            self.logger.debug("Plugin '{}': parse item: {}".format(self.get_shortname(), item))

        # todo
        # if interesting item for sending values:
        #   return update_item


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        # todo
        # change 'foo_itemtag' into your attribute name
        if item():
            if self.has_iattr(item.conf, 'foo_itemtag'):
                self.logger.debug("Plugin '{}': update_item ws called with item '{}' from caller '{}', source '{}' and dest '{}'".format(self.get_shortname(), item, caller, source, dest))
            pass
