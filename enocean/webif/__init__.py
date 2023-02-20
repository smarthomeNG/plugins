#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-     <AUTHOR>                                   <EMAIL>
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

import datetime
import time
import os
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
    def index(self, reload=None, action=None, item_id=None, item_path=None, device_id=None, device_offset=None,
              time_orig=None, changed_orig=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        learn_triggered = False

        if action is not None:
            if action == "toggle_tx_blocking":
                self.plugin.toggle_block_external_out_messages()
            elif action == "toggle_UTE":
                self.plugin.toggle_UTE_mode(device_offset)
                self.logger.warning(f"UTE mode triggered via webinterface (Offset: {device_offset})")
            elif action == "toggle_log_unknown":
                self.plugin.toggle_log_unknown_msg()
                self.logger.info(f"Toogle state of log unknown messages triggered via webinterface")
            elif action == "send_learn" and (device_id is not None) and not (device_id=="") and (device_offset is not None) and not(device_offset==""):
                self.logger.warning(f"Learn telegram triggered via webinterface (ID:{device_id} Offset:{device_offset})")
                ret = self.plugin.send_learn_protocol(int(device_offset), int(device_id))
                if ret == True:
                    learn_triggered = True
            else:
                self.logger.error("Unknown comman received via webinterface")

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(p=self.plugin,
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path']), reverse=False),
                           tabcount=1, item_id=item_id, learn_triggered=learn_triggered, action='')


    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        # if dataSets are used, define them here
        if dataSet == 'overview':
            # get the new data from the plugin variable called _webdata
            data = self.plugin._webdata
            try:
                data = json.dumps(data)
                return data
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")
        if dataSet is None:
            # get the new data
            data = {}

            # data['item'] = {}
            # for i in self.plugin.items:
            #     data['item'][i]['value'] = self.plugin.getitemvalue(i)
            #
            # return it as json the the web page
            # try:
            #     return json.dumps(data)
            # except Exception as e:
            #     self.logger.error("get_data_html exception: {}".format(e))
        return {}
