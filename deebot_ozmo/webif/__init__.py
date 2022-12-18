#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019-      Serge Wagener                serge@wagener.family
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
        self.tplenv = self.init_template_environment()
        self.tplenv.filters['dateformat'] = self.dateformat
        self.tplenv.filters['timeformat'] = self.timeformat
        self.items = Items.get_instance()

    @cherrypy.expose
    def index(self, reload=None, cmd=None, speed=None, level=None, type=None, id=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """

        if cmd:
            self.logger.debug(f'Command: {cmd}')
            if cmd == 'clean':
                self.logger.info("WebIf: Start cleaning")
                self.plugin.clean()
            elif cmd == 'clean_room':
                self.logger.info(
                    f"WebIf: Start cleaning {type} (id: {id})")
                self.plugin.clean(id)
            elif cmd == 'pause':
                self.logger.info("WebIf: Pause cleaning")
                self.plugin.pause()
            elif cmd == 'charge':
                self.logger.info("WebIf: Return to charging station")
                self.plugin.charge()
            elif cmd == 'locate':
                self.logger.info("WebIf: Locating robot")
                self.plugin.locate()
            elif cmd == 'set_fan_speed':
                self.logger.info(f"WebIf: Update fan speed to {speed}")
                self.plugin.set_fan_speed(speed)
            elif cmd == 'set_water_level':
                self.logger.info(
                    f"WebIf: Update water level to {level}")
                self.plugin.set_water_level(level)
            else:
                self.logger.warning(f'Unknown command: {cmd}')

        # get list of items with the attribute knx_dpt
        plgitems = []
        for item in self.items.return_items():
            self.logger.debug(f'For: {item.conf}')
            if self.plugin.get_shortname() in item.conf:
                self.logger.debug(f'Item: {item}')
                plgitems.append(item)

        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, items=sorted(plgitems, key=lambda k: str.lower(k['_path'])))

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            data = {}
            data['mybot'] = self.plugin.mybot
            # return it as json the the web page
            try:
                return json.dumps(data)
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")
        return {}

    # Jinja2 filter to format int timestamp as string
    def dateformat(self, timestamp):
        try:
            _datetime = datetime.datetime.fromtimestamp(timestamp)
            result = _datetime.strftime("%d/%m/%Y")
        except:
            result = 'ERROR'
        return result

    def timeformat(self, timestamp):
        try:
            _datetime = datetime.datetime.fromtimestamp(timestamp)
            result = _datetime.strftime("%H:%M:%S")
        except:
            result = 'ERROR'
        return result
