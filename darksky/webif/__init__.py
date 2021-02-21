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
from collections import OrderedDict

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

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """

        def printdict(OD, mode='dict', s="", indent=' '*4, level=0):
            def is_number(s):
                try:
                    float(s)
                    return True
                except Exception:
                    return False

            def fstr(s):
                return s if is_number(s) else '"{}"'.format(s)
            if mode != 'dict':
                kv_tpl = '("{}")'.format(s)
                ST = 'OrderedDict([\n'
                END = '])'
            else:
                kv_tpl = '"%s": %s'
                ST = '{\n'
                END = '}'
            for i, k in enumerate(OD.keys()):
                if type(OD[k]) in [dict, OrderedDict]:
                    level += 1
                    s += (level-1)*indent+kv_tpl%(k,ST+printdict(OD[k], mode=mode, indent=indent, level=level)+(level-1)*indent+END)
                    level -= 1
                else:
                    s += level*indent+kv_tpl%(k,fstr(OD[k]))
                if i != len(OD) - 1:
                    s += ","
                s += "\n"
            return s

        tmpl = self.tplenv.get_template('index.html')
        pf = printdict(self.plugin.get_json_data())
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(), p=self.plugin, json_data=pf.replace('\n', '<br>').replace(' ', '&nbsp;'),)
