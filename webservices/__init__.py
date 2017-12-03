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
from jinja2 import Environment, FileSystemLoader
import datetime
from collections import OrderedDict
import collections
import json
import html
import os


class WebServices(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = '1.4.0.1'

    def __init__(self, smarthome, mode="all"):
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Backend.__init__')
        self._sh = smarthome
        self._mode = mode

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

        # Register the REST interface as a cherrypy app
        self.mod_http.register_service(RESTWebServicesInterface(webif_dir, self),
                                       self.get_shortname(),
                                       config,
                                       self.get_classname(), self.get_instance_name(),
                                       description='WebService Plugin für SmartHomeNG (REST)',
                                       servicename='rest')

        # Register the simple WebService interface as a cherrypy app
        self.mod_http.register_service(SimpleWebServiceInterface(webif_dir, self),
                                       self.get_shortname(),
                                       config,
                                       self.get_classname(), self.get_instance_name(),
                                       description='Webservice-Plugin für SmartHomeNG (simple)',
                                       servicename='ws')

        # Register the web overview of the webservices interfaces as a cherrypy app
        self.mod_http.register_webif(WebGuiInterface(self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='Webservice-Plugin für SmartHomeNG (Frontend)',
                                     webifname='ws_gui')

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


class WebGuiInterface:
    exposed = True
    env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__)) + '/templates'))

    def __init__(self, plugin):
        self.logger = logging.getLogger(__name__)
        self.plugin = plugin

    def render_template(self, tmpl_name, **kwargs):
        tmpl = self.env.get_template(tmpl_name)
        return tmpl.render(smarthome=self.plugin._sh, **kwargs)

    @cherrypy.expose
    def index(self):
        items_filtered = []
        item_sets = {}
        items_sorted = sorted(self.plugin._sh.return_items(), key=lambda k: str.lower(k['_path']), reverse=False)
        for item in items_sorted:
            if self.plugin._mode == 'all' or self.plugin.has_iattr(item.conf, 'webservices_set'):
                if item.type() in ['str', 'bool', 'num']:
                    items_filtered.append(item)
                    if self.plugin.has_iattr(item.conf, 'webservices_set'):
                        if isinstance(self.plugin.get_iattr_value(item.conf, 'webservices_set'), list):
                            for item_set in self.plugin.get_iattr_value(item.conf, 'webservices_set'):
                                if item_set not in item_sets:
                                    item_sets[item_set] = []
                                item_sets[item_set].append(item)
                        else:
                            item_set = self.plugin.get_iattr_value(item.conf, 'webservices_set')
                            if item_set not in item_sets:
                                item_sets[item_set] = []
                            item_sets[item_set].append(item)

        return self.render_template('main.html', item_data=items_filtered,
                                    ip=self.plugin.mod_http.get_local_ip_address(),
                                    port=self.plugin.mod_http.get_local_port(),
                                    servicesport=self.plugin.mod_http.get_local_servicesport(),
                                    item_sets=item_sets)


class WebServiceInterface:
    exposed = True
    env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__)) + '/templates'))

    def __init__(self, webif_dir, plugin):
        self.webif_dir = webif_dir
        self.logger = logging.getLogger(__name__)
        self.plugin = plugin

    def check_set(self, set_id, item_sets):
        if isinstance(item_sets, list):
            if set_id in item_sets:
                return True
            else:
                return False
        else:
            if set_id == item_sets:
                return True
            else:
                return False

    def assemble_item_data(self, item, webservices_data='full'):
        if item is not None:
            if item.type() in ['str', 'bool', 'num']:
                if webservices_data == 'full':
                    prev_value = item.prev_value()
                    value = item._value

                    if isinstance(prev_value, datetime.datetime):
                        prev_value = str(prev_value)

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
                        prev_age = item.prev_age()

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
                                 'value': value,
                                 'age': item.age(),
                                 'last_update': str(item.last_update()),
                                 'last_change': str(item.last_change()),
                                 'changed_by': changed_by,
                                 'previous_value': prev_value,
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
                                 'config': item_conf_sorted,
                                 'logics': logics,
                                 'triggers': triggers
                                 }
                    return data_dict
                elif webservices_data == 'val':
                    return {'path': item._path, 'value': item._value}
            else:
                return None


class SimpleWebServiceInterface(WebServiceInterface):
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def itemset(self, set_id=None):
        """
        REST function for items
        """
        if set_id is not None:
            self.logger.debug(cherrypy.request.method)
            if cherrypy.request.method not in 'GET':
                return {"Error": "%s requests not allowed for this URL" % cherrypy.request.method}

            elif cherrypy.request.method == 'GET':
                items_sorted = sorted(self.plugin._sh.return_items(), key=lambda k: str.lower(k['_path']),
                                      reverse=False)
                items = {}
                for item in items_sorted:
                    if self.plugin.has_iattr(item.conf, 'webservices_set'):
                        if self.check_set(set_id, self.plugin.get_iattr_value(item.conf, 'webservices_set')):
                            if self.plugin.get_iattr_value(item.conf, 'webservices_data') == 'val':
                                item_data = self.assemble_item_data(item, 'val')
                                items[item_data['path']] = item_data['value']
                            else:
                                item_data = self.assemble_item_data(item, 'full')
                                if item_data is not None:
                                    item_data['url'] = "http://%s:%s/ws/items/%s" % (
                                        self.plugin.mod_http.get_local_ip_address(),
                                        self.plugin.mod_http.get_local_port(), item._path)
                                    items[item._path] = item_data
                return items
        else:
            return {"Error": "No set-ID for item set is given."}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def items(self, item_path=None, value=None):
        """
        Simpole WS functions for item
        """
        if item_path is None:
            self.logger.debug(cherrypy.request.method)
            if cherrypy.request.method not in 'GET':
                return {"Error": "%s requests not allowed for this URL" % cherrypy.request.method}

            elif cherrypy.request.method == 'GET':
                items_sorted = sorted(self.plugin._sh.return_items(), key=lambda k: str.lower(k['_path']),
                                      reverse=False)
                items = {}
                for item in items_sorted:
                    if self.plugin._mode == 'all' or self.plugin.has_iattr(item.conf, 'webservices_set'):
                        mode = "full"
                        if self.plugin.get_iattr_value(item.conf, 'webservices_data') == 'val':
                            mode = "val"
                        item_data = self.assemble_item_data(item, mode)
                        if item_data is not None:
                            if mode != "val":
                                item_data['url'] = "http://%s:%s/ws/items/%s" % (
                                    self.plugin.mod_http.get_local_ip_address(),
                                    self.plugin.mod_http.get_local_servicesport(), item._path)
                            items[item_data['path']] = item_data
                return items
        else:
            item = self.plugin._sh.return_item(item_path)
            if item is None:
                return {"Error": "No item with item path %s found." % item_path}

            if self.plugin._mode == 'all' or self.plugin.has_iattr(item.conf, 'webservices_set'):
                if item.type() in ['str', 'bool', 'num']:
                    if value is not None:
                        item(value)
                        return {"Success": "Item with item path %s set to %s." % (item_path, value)}
                    else:
                        mode = "full"
                        if self.plugin.get_iattr_value(item.conf, 'webservices_data') == 'val':
                            mode = "val"
                        item_data = self.assemble_item_data(item, mode)
                        if item_data is not None:
                            return item_data
                else:
                    return {"Error": "Item with path %s is type %s, only str, num and bool types are supported." %
                                     (item_path, item.type())}
            else:
                return {"Error": "Item with path %s not allowed for access via Webservice plugin." %
                                 item_path}


class RESTWebServicesInterface(WebServiceInterface):
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def itemset(self, set_id=None):
        """
        REST function for items
        """
        if set_id is not None:
            self.logger.debug(cherrypy.request.method)
            if cherrypy.request.method not in 'GET':
                return {"Error": "%s requests not allowed for this URL" % cherrypy.request.method}

            elif cherrypy.request.method == 'GET':
                items_sorted = sorted(self.plugin._sh.return_items(), key=lambda k: str.lower(k['_path']),
                                      reverse=False)
                items = {}
                for item in items_sorted:
                    if self.plugin.has_iattr(item.conf, 'webservices_set'):
                        if self.check_set(set_id, self.plugin.get_iattr_value(item.conf, 'webservices_set')):
                            if self.plugin.get_iattr_value(item.conf, 'webservices_data') == 'val':
                                item_data = self.assemble_item_data(item, 'val')
                                items[item_data['path']] = item_data['value']
                            else:
                                item_data = self.assemble_item_data(item, 'full')
                                if item_data is not None:
                                    item_data['url'] = "http://%s:%s/rest/items/%s" % (
                                        self.plugin.mod_http.get_local_ip_address(),
                                        self.plugin.mod_http.get_local_port(), item._path)
                                    items[item_data['path']] = item_data
                return items
        else:
            return {"Error": "No set-ID for item set is given."}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def items(self, item_path=None):
        """
        REST function for items
        """
        if item_path is None:
            self.logger.debug(cherrypy.request.method)
            if cherrypy.request.method not in 'GET':
                return {"Error": "%s requests not allowed for this URL" % cherrypy.request.method}

            elif cherrypy.request.method == 'GET':
                items_sorted = sorted(self.plugin._sh.return_items(), key=lambda k: str.lower(k['_path']),
                                      reverse=False)
                items = {}
                for item in items_sorted:
                    if self.plugin._mode == 'all' or self.plugin.has_iattr(item.conf, 'webservices_set'):
                        mode = "full"
                        if self.plugin.get_iattr_value(item.conf, 'webservices_data') == 'val':
                            mode = "val"
                        item_data = self.assemble_item_data(item, mode)
                        if item_data is not None:
                            if mode != 'val':
                                item_data['url'] = "http://%s:%s/rest/items/%s" % (
                                    self.plugin.mod_http.get_local_ip_address(),
                                    self.plugin.mod_http.get_local_port(), item._path)
                            items[item_data['path']] = item_data
                return items
        else:
            item = self.plugin._sh.return_item(item_path)

            if item is None:
                return {"Error": "No item with item path %s found." % item_path}

            if self.plugin._mode == 'all' or self.plugin.has_iattr(item.conf, 'webservices_set'):
                if cherrypy.request.method == 'PUT':
                    data = cherrypy.request.json
                    self.logger.error(data)
                    if 'num' in item.type():
                        if self.plugin.is_int(data) or self.plugin.is_float(data):
                            item(data)
                            self.logger.debug("Item with item path %s set to %s." % (item_path, data))
                        else:
                            return {"Error": "Item with item path %s is type num, value is %s." % (item_path, data)}
                    elif 'bool' in item.type():
                        if self.plugin.is_int(data):
                            if data == 0 or data == 1:
                                item(data)
                                self.logger.debug("Item with item path %s set to %s." % (item_path, data))
                            else:
                                return {
                                    "Error": "Item with item path %s is type bool, only 0 and 1 are accepted as integers, "
                                             "value is %s." % (
                                                 item_path,
                                                 data)}
                        else:
                            try:
                                data = self.plugin.to_bool(data)
                                item(data)
                                self.logger.debug("Item with item path %s set to %s." % (item_path, data))
                            except Exception as e:
                                return {"Error": "Item with item path %s is type bool, value is %s." % (item_path,
                                                                                                        data)}
                    elif 'str' in item.type():
                        item(data)
                        self.logger.debug("Item with item path %s set to %s." % (item_path, data))
                    else:
                        return {
                            "Error": "Only str, num and bool items are supported by the REST PUT interface. Item with item path %s is %s"
                                     % (
                                         item_path,
                                         item.type())}

                elif cherrypy.request.method == 'GET':
                    mode = "full"
                    if self.plugin.get_iattr_value(item.conf, 'webservices_data') == 'val':
                        mode = "val"
                    item_data = self.assemble_item_data(item, mode)
                    if item_data is not None:
                        if mode != 'val':
                            item_data['url'] = "http://%s:%s/rest/items/%s" % (
                            self.plugin.mod_http.get_local_ip_address(),
                            self.plugin.mod_http.get_local_servicesport(),
                            item._path)
                        return item_data
                    else:
                        return {"Error": "Item with path %s is type %s, only str, num and bool types are supported." %
                                         (item_path, item.type())}
            else:
                return {"Error": "Item with path %s not allowed for access via Webservice plugin." %
                                 item_path}
