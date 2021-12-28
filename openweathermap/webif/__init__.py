#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-     Jens Höppner (jentz1986)
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.5 and
#  upwards.
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

from datetime import datetime, timezone
import time
import os

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
import json
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
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin)

    @cherrypy.expose
    def force_download_all(self):
        self.plugin.force_download_all_data()

    @cherrypy.expose
    def test_match_string(self, match_string):
        success = True
        req_correlation_key = f"webif_req {str(datetime.now().replace(tzinfo=timezone.utc).timestamp())}:"
        self.logger.debug(f'Queried to test match_string "{match_string}" as request "{req_correlation_key}"')

        if not self.plugin._forced_download_happened:
            self.plugin.force_download_all_data()

        try:
            ret_val, queried_source, s, was_ok = self.plugin.get_value_with_meta(match_string, req_correlation_key)
            str_value = str(ret_val)
            line, char, line_len = self.plugin._get_position_hint_within_json(queried_source, s)
            path_in_source = s
            position_in_file = f"{line},{char},{line_len}"
            success = was_ok
        except Exception as e:
            success = False
            str_value = repr(e)
            queried_source = ""
            path_in_source = ""
            position_in_file = ""

        return json.dumps({
            "success": success,
            "value": str_value,
            "queried_source": queried_source,
            "path_in_source": path_in_source,
            "position_in_file": position_in_file
        })
