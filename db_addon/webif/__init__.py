#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022-         Michael Wenzel           wenzel_michael@web.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  This plugin provides additional functionality to mysql database
#  connected via database plugin
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

import json

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
from jinja2 import Environment, FileSystemLoader


class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.items = Items.get_instance()

        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None, action=None, item_path=None, active=None, option=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after being rendered
        """

        pagelength = self.plugin.get_parameter_value('webif_pagelength')
        tmpl = self.tplenv.get_template('index.html')

        if action is not None:
            if action == "recalc_item" and item_path is not None:
                self.logger.info(f"Recalc of item={item_path} called via WebIF. Item put to Queue for new calculation.")
                self.plugin.execute_items(option='item', item=item_path)

            elif action == "clean_item_cache" and item_path is not None:
                self.logger.info(f"Clean item cache of item={item_path} called via WebIF. Plugin item value cache will be cleaned.")
                self.plugin._clean_item_cache(item=item_path)

            elif action == "_activate_item_calculation" and item_path is not None and active is not None:
                self.logger.info(f"Item calculation of item={item_path} will be set to {bool(int(active))} via WebIF.")
                self.plugin._activate_item_calculation(item=item_path, active=bool(int(active)))

        return tmpl.render(p=self.plugin,
                           webif_pagelength=pagelength,
                           suspended='true' if self.plugin.suspended else 'false',
                           items=self.plugin.get_item_list('db_addon', 'function'),
                           item_count=len(self.plugin.get_item_list('db_addon', 'function')),
                           plugin_shortname=self.plugin.get_shortname(),
                           plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(),
                           maintenance=True if self.plugin.log_level < 20 else False,
                           )

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            # get the new data
            data = dict()

            data['items'] = {}
            for item in self.plugin.get_item_list('db_addon', 'function'):
                data['items'][item.property.path] = {}
                data['items'][item.property.path]['value'] = item.property.value
                data['items'][item.property.path]['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data['items'][item.property.path]['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            data['plugin_suspended'] = self.plugin.suspended
            data['maintenance'] = True if self.plugin.log_level == 10 else False
            data['queue_length'] = self.plugin.queue_backlog()
            data['active_queue_item'] = self.plugin.active_queue_item

            data['debug_log'] = {}
            for debug in ['parse', 'execute', 'ondemand', 'onchange', 'prepare', 'sql']:
                data['debug_log'][debug] = getattr(self.plugin.debug_log, debug)

            try:
                return json.dumps(data, default=str)
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")

    @cherrypy.expose
    def submit(self, item=None):
        result = None
        item_path, cmd = item.split(':')
        if item_path is not None and cmd is not None:
            self.logger.debug(f"Received db_addon {cmd=} for {item_path=} via web interface")

            if cmd == "recalc_item":
                self.logger.info(f"Recalc of item={item_path} called via WebIF. Item put to Queue for new calculation.")
                result = self.plugin.execute_items(option='item', item=item_path)
                self.logger.debug(f"Result for web interface: {result}")
                return json.dumps(result).encode('utf-8')

            elif cmd == "clean_item_cache":
                self.logger.info(f"Clean item cache of item={item_path} called via WebIF. Plugin item value cache will be cleaned.")
                result = self.plugin._clean_item_cache(item=item_path)
                self.logger.debug(f"Result for web interface: {result}")
                return json.dumps(result).encode('utf-8')

            elif cmd.startswith("suspend_plugin_calculation"):
                self.logger.debug(f"set_plugin_calculation {cmd=}")
                cmd, value = cmd.split(',')
                value = True if value == "True" else False
                self.logger.info(f"Plugin will be set to suspended: {value} via WebIF.")
                result = self.plugin.suspend(value)
                self.logger.debug(f"Result for web interface: {result}")
                return json.dumps(result).encode('utf-8')

            elif cmd.startswith("suspend_item_calculation"):
                cmd, value = cmd.split(',')
                self.logger.info(f"Item calculation of item={item_path} will be set to suspended: {value} via WebIF.")
                value = True if value == "True" else False
                result = self.plugin._suspend_item_calculation(item=item_path, suspended=value)
                self.logger.debug(f"Result for web interface: {result}")
                return json.dumps(result).encode('utf-8')

        if result is not None:
            # JSON zurücksenden
            cherrypy.response.headers['Content-Type'] = 'application/json'
            self.logger.debug(f"Result for web interface: {result}")
            return json.dumps(result).encode('utf-8')

    @cherrypy.expose
    def recalc_all(self):
        self.logger.debug(f"recalc_all called")
        self.plugin.execute_items('all')

    @cherrypy.expose
    def clean_cache_dicts(self):
        self.logger.debug(f"_clean_cache_dicts called")
        self.plugin._init_cache_dicts()

    @cherrypy.expose
    def clear_queue(self):
        self.logger.debug(f"_clear_queue called")
        self.plugin._clear_queue()

    @cherrypy.expose
    def activate(self):
        self.logger.debug(f"active called")
        self.plugin.suspend(False)

    @cherrypy.expose
    def suspend(self):
        self.logger.debug(f"suspend called")
        self.plugin.suspend(True)

    @cherrypy.expose
    def debug_log_option(self, log: str = None, state: bool = None):
        self.logger.warning(f"debug_log_option called with {log=}, {state=}")
        _state = True if state == 'true' else False
        setattr(self.plugin.debug_log, log, _state)

    @cherrypy.expose
    def debug_log_option_parse_true(self):
        self.logger.debug("debug_log_option_parse_true")
        setattr(self.plugin.debug_log, 'parse', True)

    @cherrypy.expose
    def debug_log_option_parse_false (self):
        self.logger.debug("debug_log_option_parse_false")
        setattr(self.plugin.debug_log, 'parse', False)

    @cherrypy.expose
    def debug_log_option_execute_true(self):
        self.logger.debug("debug_log_option_execute_true")
        setattr(self.plugin.debug_log, 'execute', True)

    @cherrypy.expose
    def debug_log_option_execute_false (self):
        self.logger.debug("debug_log_option_execute_false")
        setattr(self.plugin.debug_log, 'execute', False)

    @cherrypy.expose
    def debug_log_option_ondemand_true(self):
        self.logger.debug("debug_log_option_ondemand_true")
        setattr(self.plugin.debug_log, 'ondemand', True)

    @cherrypy.expose
    def debug_log_option_ondemand_false (self):
        self.logger.debug("debug_log_option_ondemand_false")
        setattr(self.plugin.debug_log, 'ondemand', False)

    @cherrypy.expose
    def debug_log_option_onchange_true(self):
        self.logger.debug("debug_log_option_onchange_true")
        setattr(self.plugin.debug_log, 'onchange', True)

    @cherrypy.expose
    def debug_log_option_onchange_false (self):
        self.logger.debug("debug_log_option_onchange_false")
        setattr(self.plugin.debug_log, 'onchange', False)

    @cherrypy.expose
    def debug_log_option_prepare_true(self):
        self.logger.debug("debug_log_option_prepare_true")
        setattr(self.plugin.debug_log, 'prepare', True)

    @cherrypy.expose
    def debug_log_option_prepare_false (self):
        self.logger.debug("debug_log_option_prepare_false")
        setattr(self.plugin.debug_log, 'prepare', False)

    @cherrypy.expose
    def debug_log_option_sql_true(self):
        self.logger.debug("debug_log_option_sql_true")
        setattr(self.plugin.debug_log, 'sql', True)

    @cherrypy.expose
    def debug_log_option_sql_false (self):
        self.logger.debug("debug_log_option_sql_false")
        setattr(self.plugin.debug_log, 'sql', False)
