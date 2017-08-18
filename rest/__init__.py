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

    def __init__(self, webif_dir, plugin):
        self.webif_dir = webif_dir
        self.logger = logging.getLogger(__name__)
        self.plugin = plugin

    @cherrypy.expose
    def get(self, item_path):
        """
        get item values
        """
        item = self.plugin._sh.return_item(item_path)
        if item is not None:
            return json.dumps(item())
        else:
            return json.dumps({"Error": "No item with item path %s found."%item_path})

    @cherrypy.expose
    def put(self, item_path, value):
        """
        set item value
        """
        item = self.plugin._sh.return_item(item_path)
        if item is not None:
            item(value)
            return json.dumps({"Success": "Item with item path %s set to %s." % (item_path, value)})
        else:
            return json.dumps({"Error": "No item with item path %s found." % item_path})

    @cherrypy.expose
    def head(self, item_path):
        """
        get item meta data
        """
        item_data = []
        item = self.plugin._sh.return_item(item_path)
        if item is not None:
            cycle = ''
            crontab = ''
            for entry in self.plugin._sh.scheduler._scheduler:
                if entry == item._path:
                    if self.plugin._sh.scheduler._scheduler[entry]['cycle']:
                        cycle = self.plugin._sh.scheduler._scheduler[entry]['cycle']
                    if self.plugin._sh.scheduler._scheduler[entry]['cron']:
                        crontab = str(self.plugin._sh.scheduler._scheduler[entry]['cron'])
                    break

            changed_by = item.changed_by()
            if changed_by[-5:] == ':None':
                changed_by = changed_by[:-5]

            item_conf_sorted = collections.OrderedDict(sorted(item.conf.items(), key=lambda t: str.lower(t[0])))

            if item.prev_age() < 0:
                prev_age = ''
            else:
                prev_age = self.disp_age(item.prev_age())

            logics = []
            for trigger in item.get_logic_triggers():
                logics.append(format(trigger))
            triggers = []
            for trigger in item.get_method_triggers():
                trig = format(trigger)
                trig = trig[1:len(trig) - 27]
                triggers.append(format(trig.replace("<", "")))

            data_dict = {'path': item._path,
                         'name': item._name,
                         'type': item.type(),
                         'age': item.age(),
                         'last_update': str(item.last_update()),
                         'last_change': str(item.last_change()),
                         'changed_by': changed_by,
                         'previous_age': prev_age,
                         'previous_change': str(item.prev_change()),
                         'enforce_updates': str(item._enforce_updates),
                         'cache': str(item._cache),
                         'eval': str(item._eval),
                         'eval_trigger': str(item._eval_trigger),
                         'cycle': str(cycle),
                         'crontab': str(crontab),
                         'autotimer': str(item._autotimer),
                         'threshold': str(item._threshold),
                         'config': json.dumps(item_conf_sorted),
                         'logics': json.dumps(logics),
                         'triggers': json.dumps(triggers)
            }

            item_data.append(data_dict)
            return json.dumps(item_data)
        else:
            return json.dumps({"Error": "No item with item path %s found." % item_path})
