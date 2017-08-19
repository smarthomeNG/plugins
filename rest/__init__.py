#!/usr/bin/env python3
# -*- coding: utf8 -*-
#########################################################################
# Copyright 2017        René Frieß                  rene.friess@gmail.com
#########################################################################
#  REST plugin for SmartHomeNG
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

from lib.model.smartplugin import SmartPlugin
import logging
import cherrypy
import datetime
from collections import OrderedDict
import collections
import json
import html
import os

class REST(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION='1.4.0.1'

    def __init__(self, smarthome):
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Backend.__init__')
        self._sh = smarthome

        try:
            self.mod_http = self._sh.get_module('http')
        except:
            self.mod_http = None
        if self.mod_http is None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return

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
        self.mod_http.register_app(RESTWebInterface(webif_dir, self),
                                   self.get_shortname(),
                                   config,
                                   self.get_classname(), self.get_instance_name(),
                                   description='REST-Plugin für SmartHomeNG')

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Plugin '{}': run method called".format(self.get_shortname()))
        self.alive = True


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Plugin '{}': stop method called".format(self.get_shortname()))
        self.alive = False



class RESTWebInterface():
    exposed = True

    def __init__(self, webif_dir, plugin):
        self.webif_dir = webif_dir
        self.logger = logging.getLogger(__name__)
        self.plugin = plugin

    #@cherrypy.tools.accept(media='application/json')


    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def item(self, item_path):
        """
        REST function for items
        """
        item = self.plugin._sh.return_item(item_path)
        if item is None:
            return json.dumps({"Error": "No item with item path %s found." % item_path})

        self.logger.debug(cherrypy.request.method)
        if cherrypy.request.method == 'PUT':
            data = cherrypy.request.body.read()
            self.logger.debug("Item with item path %s set to %s." % (item_path, data))
            if 'num' in item.type():
                if self.plugin.is_int(data) or self.plugin.is_float(data):
                    json_data = int(data)
                else:
                    return json.dumps({"Error": "Item with item path %s is type num, value is %s." % (item_path, data)})
            item(data)
        elif cherrypy.request.method == 'GET':
            return json.dumps(item())

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def items(self):
        """
        REST function for items
        """
        self.logger.debug(cherrypy.request.method)
        if cherrypy.request.method == 'PUT':
            return json.dumps({"Error": "Put requests not allowed for this URL"})

        elif cherrypy.request.method == 'GET':
            items_sorted = sorted(self.plugin._sh.return_items(), key=lambda k: str.lower(k['_path']), reverse=False)
            parent_items_sorted = []
            for item in items_sorted:
                if item._name not in ['env_daily', 'env_init', 'env_loc', 'env_stat'] and item._type == 'foo':
                    parent_items_sorted.append(item)

            item_data = self._build_item_tree(parent_items_sorted)
            return json.dumps(item_data)

    def _build_item_tree(self, parent_items_sorted):
        item_data = []

        for item in parent_items_sorted:
            nodes = self._build_item_tree(item.return_children())
            tags = []
            tags.append(len(nodes))
            item_data.append(item._path)

        return item_data
