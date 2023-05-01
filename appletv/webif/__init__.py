#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018- Serge Wagener                     serge@wagener.family
#########################################################################
#  This file is part of SmartHomeNG.
#
#  AppleTV plugin
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
import pyatv
from random import randint
from time import sleep

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
        self.pinentry = False

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        # get list of items with the attribute knx_dpt
        plgitems = []
        _instance = self.plugin.get_instance_name()
        if _instance:
            _keyword = 'appletv@{}'.format(_instance)
        else:
            _keyword = 'appletv'
        for item in self.items.return_items():
            if _keyword in item.conf:
                plgitems.append(item)
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(p=self.plugin, items=sorted(plgitems, key=lambda k: str.lower(k['_path'])), pinentry=self.pinentry)

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
            data['state'] = self.plugin._state
            # return it as json the the web page
            try:
                return json.dumps(data)
            except Exception as e:
                self.logger.error("get_data_html exception: {}".format(e))
                #self.logger.debug(data)
        return {}

    @cherrypy.expose
    def button_pressed(self, button=None, pin=None):
        if button == "discover":
            self.logger.debug('Discover button pressed')
            self.plugin._loop.create_task(self.plugin.discover())
        elif button == "start_authorization":
            self.logger.debug('Start authentication')
            self.pinentry = True

            _protocol = self.plugin._atv.main_service().protocol
            _task = self.plugin._loop.create_task(
                pyatv.pair(self.plugin._atv, _protocol, self.plugin._loop)
            )
            while not _task.done():
                sleep(0.1)
            self._pairing = _task.result()
            if self._pairing.device_provides_pin:
                self._pin = None
                self.logger.info('Device provides pin')
            else:
                self._pin = randint(1111,9999)
                self.logger.info('SHNG must provide pin: {}'.format(self._pin))

            self.plugin._loop.create_task(self._pairing.begin())

        elif button == "finish_authorization":
            self.logger.debug('Finish authentication')
            self.pinentry = False
            self._pairing.pin(pin)
            _task = self.plugin._loop.create_task(self._pairing.finish())
            while not _task.done():
                sleep(0.1)
            if self._pairing.has_paired:
                self.logger.info('Pairing successfull !')
                self.plugin._credentials = self._pairing.service.credentials
                self.plugin.save_credentials()
            else:
                self.logger.error('Unable to pair, wrong Pin ?')
            self.plugin._loop.create_task(self._pairing.close())
        else:
            self.logger.warning(
                "Unknown button pressed in webif: {}".format(button))
        raise cherrypy.HTTPRedirect('index')
