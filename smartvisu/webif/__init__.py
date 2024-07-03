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
from lib.logic import Logics
from lib.model.smartplugin import SmartPluginWebIf


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
from jinja2 import Environment, FileSystemLoader

import socket


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

        # try to get API handles
        self.items = Items.get_instance()
        self.logics = Logics.get_instance()


    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Display a list of all connected visu clients
        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """

        # get API handles that were unavailable during __init__
        if self.items is None:
            self.items = Items.get_instance()
        if self.logics is None:
            self.logics = Logics.get_instance()

        clients = []

        for clientinfo in self.plugin.return_clients():
            c = clientinfo.get('addr', '')
            client = dict()
            client['ip'] = clientinfo.get('ip', '')
            client['port'] = clientinfo.get('port', '')
            try:
                client['name'] = socket.gethostbyaddr(client['ip'])[0]
            except:
                client['name'] = client['ip']

            client['proto'] = clientinfo.get('proto', '')
            client['sw'] = clientinfo.get('sw', '')
            client['swversion'] = clientinfo.get('swversion', '')
            client['protocol'] = clientinfo.get('protocol', '')
            client['hostname'] = clientinfo.get('hostname', '')
            client['browser'] = clientinfo.get('browser', '')
            client['browserversion'] = clientinfo.get('browserversion', '')

            client['osname'] = clientinfo.get('os_name', '')
            client['osversion'] = clientinfo.get('os_vers', '')
            client['osversionname'] = clientinfo.get('os_vname', '')
            client['platformtype'] = clientinfo.get('pl_type', '')
            client['platformvendor'] = clientinfo.get('pl_vendor', '')
            clients.append(client)

        clients_sorted = sorted(clients, key=lambda k: k['name'])

        plgitems = []
        for item in self.items.return_items():
            if ('visu_acl' in item.conf):
                plgitems.append(item)

        plglogics = []
        if self.logics:
            for logic in self.logics.return_logics():
                plglogics.append(self.logics.get_logic_info(logic))
        pagelength = self.plugin.get_parameter_value('webif_pagelength')
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(p=self.plugin,
                           webif_pagelength=pagelength,
                           items=sorted(plgitems, key=lambda k: str.lower(k['_path'])),
                           logics=sorted(plglogics, key=lambda k: str.lower(k['name'])),
                           clients=clients_sorted, client_count=len(clients_sorted))


    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            # callect data for 'items' tab
            item_dict = {}
            for item in self.plugin.get_item_list():
                item_config = self.plugin.get_item_config(item)
                value_dict = {}
                value_dict['type'] = item.property.type
                if ('visu_acl' in item.conf):
                    value_dict['acl'] = item.conf.get('visu_acl')
                value_dict['value'] = str(item.property.value)
                value_dict['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                value_dict['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')
                item_dict[item.property.path] = value_dict

            # callect data for 'clients' tab
            client_list = []
            for clientinfo in self.plugin.return_clients():
                value_dict = {}
                value_dict['ip'] = clientinfo.get('ip', '')
                value_dict['port'] = clientinfo.get('port', '')
                try:
                    value_dict['name'] = socket.gethostbyaddr(value_dict['ip'])[0]
                except:
                    value_dict['name'] = value_dict['ip']
                value_dict['proto'] = clientinfo.get('proto', '')
                value_dict['sw'] = clientinfo.get('sw', '')
                value_dict['swversion'] = clientinfo.get('swversion', '')
                value_dict['protocol'] = clientinfo.get('protocol', '')
                value_dict['hostname'] = clientinfo.get('hostname', '')
                value_dict['browser'] = clientinfo.get('browser', '')
                value_dict['browserversion'] = clientinfo.get('browserversion', '')

                value_dict['osname'] = clientinfo.get('os_name', '')
                value_dict['osversion'] = clientinfo.get('os_vers', '')
                value_dict['osversionname'] = clientinfo.get('os_vname', '')
                value_dict['platformtype'] = clientinfo.get('pl_type', '')
                value_dict['platformvendor'] = clientinfo.get('pl_vendor', '')
                client_list.append(value_dict)

            plglogics = []
            if self.logics:
                for logic in self.logics.return_logics():
                    plglogics.append(self.logics.get_logic_info(logic))

            result = {'items': item_dict, 'clients': client_list, 'logics': plglogics}
            #self.logger.error(result)
            # send result to web interface
            try:
                data = json.dumps(result)
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")
                self.logger.error(result)
            else:
                if data:
                    return data
                else:
                    return None

        return {}
