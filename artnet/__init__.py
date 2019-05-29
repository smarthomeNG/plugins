#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013-     mode2k                              mode@gmx.co.uk
#  Extended  2019      jentz1986
#########################################################################
#  This file is part of SmartHomeNG
#  https://github.com/smarthomeNG/smarthome
#  http://knx-user-forum.de/
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
#########################################################################

import logging
import socket
import struct

from lib.model.smartplugin import *
from lib.module import Modules

class ArtNet_Model:

    def __init__(self, host, port, universe, net, subnet, instance_name, update_cycle):
        self._host = host
        self._port = port
        
        self._universe = universe
        self._net = net
        self._subnet = subnet
        self._instance_name = instance_name
        self._update_cycle = update_cycle
        
        self._items = []        

    def get_ip(self):
        """
        Returns the IP of the ArtNet node

        :return: hostname of the device, as set in plugin.conf
        """
        return self._host

    def get_port(self):
        """
        Returns the port of the ArtNet node

        :return: port of the device, as set in plugin.conf
        """
        return self._port

    def get_universe(self):
        """
        Returns the Universe of the ArtNet node

        :return: Universe of the device, as set in plugin.conf
        """
        return self._universe

    def get_net(self):
        """
        Returns the net of the ArtNet node

        :return: net of the device, as set in plugin.conf
        """
        return self._net
        
    def get_subnet(self):
        """
        Returns the Subnet of the ArtNet node

        :return: Subnet of the device, as set in plugin.conf
        """
        return self._subnet
        
    def get_items(self):
        """
        Returns added items

        :return: array of items held by the device
        """
        return self._items

class ArtNet(SmartPlugin):

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.5.1"
    ADDR_ATTR = 'artnet_address'

    packet_counter = 1
    dmxdata = [0, 0]
    
    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.
        """
        # self.logger = logging.getLogger(__name__)
        self.logger.info('Init ArtNet Plugin')
        
        self._model = ArtNet_Model(self.get_parameter_value('ip') or '127.0.0.1', 
                                   port=int(self.get_parameter_value('port') or 6454),
                                   universe=int(self.get_parameter_value('artnet_universe') or 0),
                                   net=int(self.get_parameter_value('artnet_net') or 0),
                                   subnet=int(self.get_parameter_value('artnet_subnet') or 0),
                                   instance_name=self.get_instance_name(),
                                   update_cycle=int(self.get_parameter_value('update_cycle') or 0),
                                   )

        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.init_webinterface()

        self.logger.debug("Init ArtNet Plugin for %s done" % self._model._instance_name)

    def parse_item(self, item):
        # items bound to this artnet-subnet
        if self.has_iattr(item.conf, self.ADDR_ATTR):
            adr = int(self.get_iattr_value(item.conf, self.ADDR_ATTR))
            if adr > 0 and adr < 513:
                while len(self.dmxdata) < (adr - 1):
                    self.dmxdata.append(0)
                
                self.logger.debug("Bound address %s to item %s" % (adr, item))
                self._model._items.append(item)
                return self.update_item
            else:
                self.logger.error("Invalid address %s in item %s" % (adr, item))

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'ArtNet':
            adr = int(self.get_iattr_value(item.conf, self.ADDR_ATTR))
            if item() < 0 or item() > 255:
                self.logger.warning("Impossible to update address: %s to value %s from item %s, value has to be >=0 and <=255" % (adr, item(), item))
            else:
                self.logger.debug("Updating address: %s to value %s" % (adr, item()))
                self.send_single_value(adr, item())
            
                
    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("run method called")
        if self._model._update_cycle > 0:
            self.scheduler_add('updateArtnet', self._update_loop, prio=5, cycle=self._model._update_cycle, offset=2)
        self.alive = True
        for it in self._model._items:
            adr = int(self.get_iattr_value(it.conf, self.ADDR_ATTR))
            val = it()
            if val < 0 or val > 255:
                self.logger.warning("Impossible to update address: %s to value %s from item %s, value has to be >=0 and <=255" % (adr, val, it))
            else:
                self.logger.debug("Updating address: %s to value %s" % (adr, vaL))
            set_address_value(adr, val)
        self.__ArtDMX_broadcast()
       
            

    def stop(self):
        self.s.close()
        self.alive = False

    def __call__(self, var1=None, var2=None):
        if type(var1) == int and type(var2) == int:
            self.send_single_value(var1, var2)
        if type(var1) == int and type(var2) == list:
            self.send_frame_starting_at(var1, var2)
        if type(var1) == list and type(var2) == type(None):
            self.send_frame(var1)

    def _update_loop(self):
        if not self.alive:
            return
        if len(self.dmxdata) < 1:
            return
        self.__ArtDMX_broadcast()

    def get_address_value(self, req_adr):
        adr = int(req_adr)
        while len(self.dmxdata) < adr:
            self.dmxdata.append(0)
        return self.dmxdata[adr - 1]
        
    def set_address_value(self, req_adr, val):
        while len(self.dmxdata) < req_adr:
            self.dmxdata.append(0)
        self.dmxdata[adr - 1] = value
        
    def send_single_value(self, adr, value):
        if adr < 1 or adr > 512:
            self.logger.error("DMX address %s invalid" % adr)
            return

        set_address_value(adr, value)
        self.__ArtDMX_broadcast()

    def send_frame_starting_at(self, adr, values):
        if adr < 1 or adr > (512 - len(values) + 1):
            self.logger.error("DMX address %s with length %s invalid" %
                         (adr, len(values)))
            return

        while len(self.dmxdata) < (adr + len(values) - 1):
            self.dmxdata.append(0)
        cnt = 0
        for value in values:
            self.dmxdata[adr - 1 + cnt] = value
            cnt += 1
        self.__ArtDMX_broadcast()

    def send_frame(self, dmxframe):
        if len(dmxframe) < 2:
            self.logger.error("Send at least 2 channels")
            return
        self.dmxdata = dmxframe
        self.__ArtDMX_broadcast()

    def __ArtDMX_broadcast(self):
#       self.logger.info("Incomming DMX: %s"%self.dmxdata)
        # New Array
        data = []
        # Fix ID 7byte + 0x00
        data.append("Art-Net\x00")
        # OpCode = OpOutput / OpDmx -> 0x5000, Low Byte first
        data.append(struct.pack('<H', 0x5000))
        # ProtVerHi and ProtVerLo -> Protocol Version 14, High Byte first
        data.append(struct.pack('>H', 14))
        # Order 1 to 255
        data.append(struct.pack('B', self.packet_counter))
        self.packet_counter += 1
        if self.packet_counter > 255:
            self.packet_counter = 1
        # Physical Input Port
        data.append(struct.pack('B', 0))
        # Artnet source address
        data.append(
            struct.pack('<H', self._model._net << 8 | self._model._subnet << 4 | self._model._universe))
        # Length of DMX Data, High Byte First
        data.append(struct.pack('>H', len(self.dmxdata)))
        # DMX Data
        for d in self.dmxdata:
            data.append(struct.pack('B', d))
        # convert from list to string
        result = bytes()
        for token in data:
            try:  # Handels all strings
                result = result + token.encode('utf-8', 'ignore')
            except:  # Handels all bytes
                result = result + token
#       data = "".join(data)
        # debug
#       self.logger.info("Outgoing Artnet:%s"%(':'.join(x.encode('hex') for x in data)))
        # send over ethernet
        self.s.sendto(result, (self._model._host, self._model._port))

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True

# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy

class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface
        
        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = logging.getLogger(__name__)
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
        tabcount = 1

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), 
                           plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(), 
                           tabcount=tabcount,
                           p=self.plugin)
