#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2023-  Martin Sinn                             m.sinn@gmx.de
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

import json
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

        json_data = json.dumps(self.plugin.get_json_data(), indent=4)

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(p=self.plugin,
                           webif_pagelength=self.plugin.get_parameter_value('webif_pagelength'),
                           items=sorted(self.plugin.get_item_list(), key=lambda k: str.lower(k['_path'])),

                           json_data=json_data )


    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            result_array = []

            # callect data for 'items' tab
            item_list = []
            for item in self.plugin.get_item_list():
                item_config = self.plugin.get_item_config(item)
                value_dict = {}
                value_dict['path'] = item.property.path
                value_dict['type'] = item.type()
                value_dict['matchstring'] = self.plugin.get_item_mapping(item)
                value_dict['value'] = item()
                value_dict['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                value_dict['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')
                item_list.append(value_dict)

            result = {'items': item_list}

            # send result to wen interface
            try:
                data = json.dumps(result)
                if data:
                    return data
                else:
                    return None
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")

        return {}
