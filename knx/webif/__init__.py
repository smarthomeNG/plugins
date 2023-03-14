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
from ..globals import *


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
from jinja2 import Environment, FileSystemLoader


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------


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
        self.last_upload = ""

        self.tplenv = self.init_template_environment()
        self.knxdaemon = ''
        if os.name != 'nt':
            if self.get_process_info("ps cax|grep eibd") != '':
                self.knxdaemon = 'eibd'
            if self.get_process_info("ps cax|grep knxd") != '':
                if self.knxdaemon != '':
                    self.knxdaemon += ' and '
                self.knxdaemon += 'knxd'
        else:
            self.knxdaemon = 'can not be determined when running on Windows'

    def get_process_info(self, command):
        """
        returns output from executing a given command via the shell.
        """
        ## get subprocess module
        import subprocess

        ## call date command ##
        p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)

        # Talk with date command i.e. read data from stdout and stderr. Store this info in tuple ##
        # Interact with process: Send data to stdin. Read data from stdout and stderr, until end-of-file is reached.
        # Wait for process to terminate. The optional input argument should be a string to be sent to the child process, or None, if no data should be sent to the child.
        (result, err) = p.communicate()

        ## Wait for date to terminate. Get return returncode ##
        p_status = p.wait()
        return str(result, encoding='utf-8', errors='strict')


    @cherrypy.expose
    def index(self, reload=None, knxprojfile=None, password=None):
        """
        Build index.html for cherrypy
        Render the template and return the html file to be delivered to the browser
        :return: contents of the template after beeing rendered
        """
        pagelength = self.plugin.get_parameter_value('webif_pagelength')
        if password is not None:
            if password != '':
                self.plugin.project_file_password = password
                self.logger.debug("Set password for knxproj file")
            else:
                self.logger.debug("Provided password is empty, will not replace the saved password")

        # if given knxprojfile then this is an upload
        if self.plugin.use_project_file and knxprojfile is not None:
            size = 0
            # ``knxprojfile.file`` is a memory file prepared by cherrypy,
            # it could however be ``None``` if no valid file was uploaded by html page
            if knxprojfile.file is not None:
                with open(self.plugin.projectpath, 'wb') as out:
                    while True:
                        data = knxprojfile.file.read(8192)
                        if not data:
                            break
                        out.write(data)
                        size += len(data)
                self.last_upload = "File received.\nFilename: {}\nLength: {}\nMime-type: {}\n".format(knxprojfile.filename, size, knxprojfile.content_type)
                self.logger.debug(f"Uploaded projectfile {knxprojfile.filename} with {size} bytes")
                self.plugin._parse_projectfile()
            else:
                self.logger.error(f"Could not upload projectfile {knxprojfile}")

        plgitems = []
        for item in self.items.return_items():
            if any(elem in item.property.attributes for elem in [KNX_DPT, KNX_STATUS, KNX_SEND, KNX_REPLY, KNX_CACHE, KNX_INIT, KNX_LISTEN, KNX_POLL]):
                plgitems.append(item)

        # build a dict with groupaddress as key to items and their attributes
        # ga_usage_by_Item = { '0/1/2' : { ItemA : { attribute1 : True, attribute2 : True },
        #                                  ItemB : { attribute1 : True, attribute2 : True }}, ...}
        # ga_usage_by_Attrib={ '0/1/2' : { attribut1 : { ItemA : True, ItemB : True },
        #                                  attribut2 : { ItemC : True, ItemD : True }}, ...}
        ga_usage_by_Item = {}
        ga_usage_by_Attrib = {}
        for item in plgitems:
            for elem in [KNX_DPT, KNX_STATUS, KNX_SEND, KNX_REPLY, KNX_CACHE, KNX_INIT, KNX_LISTEN, KNX_POLL]:
                if elem in item.property.attributes:
                    value = self.plugin.get_iattr_value(item.conf, elem)
                    # value might be a list or a string here
                    if isinstance(value, str):
                        values = [value]
                    else:
                        values = value
                    if values is not None:
                        for ga in values:
                            # create ga_usage_by_Item entries
                            if ga not in ga_usage_by_Item:
                                ga_usage_by_Item[ga] = {}
                            if item not in ga_usage_by_Item[ga]:
                                ga_usage_by_Item[ga][item] = {}
                            ga_usage_by_Item[ga][item][elem] = True

                            # create ga_usage_by_Attrib entries
                            if ga not in ga_usage_by_Attrib:
                                ga_usage_by_Attrib[ga] = {}
                            if item not in ga_usage_by_Attrib[ga]:
                                ga_usage_by_Attrib[ga][elem] = {}
                            ga_usage_by_Attrib[ga][elem][item] = True

        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           webif_pagelength=pagelength,
                           items=sorted(plgitems, key=lambda k: str.lower(k['_path'])),
                           knxdaemon=self.knxdaemon,
                           stats_ga=self.plugin.get_stats_ga(), stats_ga_list=sorted(self.plugin.get_stats_ga(), key=lambda k: str(int(k.split('/')[0]) + 100) + str(int(k.split('/')[1]) + 100) + str(int(k.split('/')[2]) + 1000)),
                           stats_pa=self.plugin.get_stats_pa(), stats_pa_list=sorted(self.plugin.get_stats_pa(), key=lambda k: str(int(k.split('.')[0]) + 100) + str(int(k.split('.')[1]) + 100) + str(int(k.split('.')[2]) + 1000)),
                           last_upload=self.last_upload,
                           ga_usage_by_Item=ga_usage_by_Item,
                           ga_usage_by_Attrib=ga_usage_by_Attrib,
                           knx_attribs=[KNX_DPT, KNX_STATUS, KNX_SEND, KNX_REPLY, KNX_CACHE, KNX_INIT, KNX_LISTEN, KNX_POLL]
                           )


    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet == 'itemtable':
            # get the new data
            data = self.plugin._webdata
            try:
                data = json.dumps(data)
                return data
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")
        if dataSet == 'patable':
            # get the new data
            data = self.plugin.get_stats_pa()
            try:
                data = json.dumps(data)
                return data
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")
        if dataSet == 'gatable':
            # get the new data
            data = self.plugin.get_stats_ga()
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
