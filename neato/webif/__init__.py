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

        self.items = Items.get_instance()

    @cherrypy.expose
    def index(self, reload=None, action=None, email=None, hashInput=None, code=None, tokenInput=None, mapIDInput=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        calculatedHash = ''
        codeRequestSuccessfull  = None
        token = ''
        configWriteSuccessfull  = None
        resetAlarmsSuccessfull  = None
        boundaryListSuccessfull = None



        if action is not None:
            if action == "generateHash":
                ret = self.plugin.generateRandomHash()
                calculatedHash = str(ret)
                self.logger.info("Generate hash triggered via webinterface: {0}".format(calculatedHash))
            elif action == "requestCode" and (email is not None) and (hashInput is not None):
                self.logger.warning("Request Vorwerk code triggered via webinterface (Email:{0} hashInput:{1})".format(email, hashInput))
                codeRequestSuccessfull = self.plugin.request_oauth2_code(str(hashInput))
            elif action == "requestCode":
                if email is None:
                    self.logger.error("Cannot request Vorwerk code as email is empty: {0}.".format(str(email)))
                elif hash is None:
                    self.logger.error("Cannot request Vorwerk code as hash is empty: {0}.".format(str(email)))
            elif action == "requestToken":
                self.logger.info("Request Vorwerk token triggered via webinterface")
                if (email is not None) and (hashInput is not None) and (code is not None) and (not code == '') :
                    token = self.plugin.request_oauth2_token(str(code), str(hashInput))
                elif (code is None) or (code == ''):
                    self.logger.error("Request Vorwerk token: Email validation code missing.")
                else:
                    self.logger.error("Request Vorwerk token: Missing argument.")
            elif action =="writeToPluginConfig":
                if (tokenInput is not None) and (not tokenInput == ''):
                    self.logger.warning("Writing token to plugin.yaml")
                    param_dict = {"token": str(tokenInput)}
                    self.plugin.update_config_section(param_dict)
                    configWriteSuccessfull = True
                else:
                    self.logger.error("writeToPluginConfig: Missing argument.")
                    configWriteSuccessfull = False
            elif action =="clearAlarms":
                    self.logger.warning("Resetting alarms via webinterface")
                    self.plugin.dismiss_current_alert()
                    resetAlarmsSuccessfull = True
            elif action =="listAvailableMaps":
                    boundaryListSuccessfull = self.plugin.get_map_boundaries(map_id=mapIDInput)
                    self.logger.warning(f"Request all available maps via webinterface successfull: {boundaryListSuccessfull }")
            else:
                self.logger.error("Unknown command received via webinterface")

        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, calculatedHash=calculatedHash,
                           token=token,
                           codeRequestSuccessfull=codeRequestSuccessfull,
                           configWriteSuccessfull=configWriteSuccessfull,
                           resetAlarmsSuccessfull=resetAlarmsSuccessfull,
                           boundaryListSuccessfull=boundaryListSuccessfull,
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])))


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
