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

        self.hm_id = self.plugin.hm_id
        self.hmip_id = self.plugin.hmip_id


    @cherrypy.expose
    def index(self, learn=None, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        if learn == 'on':
            self.plugin.hm.setInstallMode(self.plugin.hm_id)

        username = self.plugin.username
        host = self.plugin.host
        devices = []
        ipdevices = []

        try:
            interface = self.plugin.hm.listBidcosInterfaces(self.hm_id)[0]
            # [{'DEFAULT': True, 'DESCRIPTION': '', 'ADDRESS': 'OEQ1658621', 'TYPE': 'CCU2', 'DUTY_CYCLE': 1, 'CONNECTED': True, 'FIRMWARE_VERSION': '2.8.5'}]
        except:
            interface = None

        try:
            interfaceip = self.plugin.hm.listBidcosInterfaces(self.hmip_id)[0]
            # [{'DEFAULT': True, 'DESCRIPTION': '', 'ADDRESS': 'OEQ1658621', 'TYPE': 'CCU2', 'DUTY_CYCLE': 1, 'CONNECTED': True, 'FIRMWARE_VERSION': '2.8.5'}]
        except:
            interfaceip = None

        # get HomeMatic devices
        for dev_id in self.plugin.hm.devices[self.hm_id]:
            dev = self.plugin.hm.devices[self.hm_id][dev_id]
#            d_type = str(dev.__class__).replace("<class '"+dev.__module__+'.', '').replace("'>",'')
            d_type = self.plugin.get_hmdevicetype(dev_id)
            d = {}
            d['name'] = dev._name
            d['address'] = dev_id
            d['hmtype'] = dev._TYPE
            d['type'] = d_type
            d['firmware'] = dev._FIRMWARE
            d['version'] = dev._VERSION
            d['assigned'] = False
            for i in self.plugin.hm_items:
                if i[2] == dev_id:
                    d['assigned'] = True
                    break
            if d_type in ['Switch','SwitchPowermeter','ShutterContact']:
                try:
                    d['value'] = dev.getValue('STATE')
                except: pass

            devices.append(d)

            d['dev'] = dev
        device_count = len(devices)

        # get HomeMaticIP devices
        for dev_id in self.plugin.hmip.devices[self.hmip_id]:
            dev = self.plugin.hmip.devices[self.hmip_id][dev_id]
#            d_type = str(dev.__class__).replace("<class '"+dev.__module__+'.', '').replace("'>",'')
            d_type = self.plugin.get_hmdevicetype(dev_id)
            d = {}
            d['name'] = dev._name
            d['address'] = dev_id
            d['hmtype'] = dev._TYPE
            d['type'] = d_type
            d['firmware'] = dev._FIRMWARE
            d['version'] = dev._VERSION
            d['assigned'] = False
            for i in self.plugin.hm_items:
                if i[2] == dev_id:
                    d['assigned'] = True
                    break
            if d_type in ['Switch','SwitchPowermeter','ShutterContact']:
                try:
                    d['value'] = dev.getValue('STATE')
                except: pass

            ipdevices.append(d)

            d['dev'] = dev
        ipdevice_count = len(ipdevices)
        # self.logger.warning("ipdevice_count = {}, ipdevices = {}".format(ipdevice_count, ipdevices))

        tmpl = self.tplenv.get_template('index.html')
        # The first paramter for the render method has to be specified. the base template
        # for the web interface relys on the instance of the plugin to be passed as p
        return tmpl.render(p=self.plugin,
                           interface=interface, interfaceip=interfaceip,
                           devices=devices, device_count=device_count,
                           ipdevices=ipdevices, ipdevice_count=ipdevice_count,
                           items=sorted(self.plugin.hm_items), item_count=len(self.plugin.hm_items),
                           hm=self.plugin.hm, hm_id=self.plugin.hm_id )

