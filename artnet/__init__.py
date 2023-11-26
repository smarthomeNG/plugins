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

import cherrypy
import logging
import socket
import struct

from lib.model.smartplugin import *
from lib.module import Modules
from .webif import WebInterface

class ArtNet_Model:

    def __init__(self, ip, port: int, net: int, subnet: int, universe: int, instance_name, update_cycle: int, min_channels: int, plugin):
        self._ip = ip
        self._port = port

        self._universe = universe
        self._net = net
        self._subnet = subnet
        self._instance_name = instance_name
        self._update_cycle = update_cycle
        self._min_channels = min_channels
        self._plugin = plugin

        self._items = []

    def get_ip(self):
        """
        Returns the IP of the ArtNet node

        :return: IP-address of the device, as set in plugin.conf
        """
        return self._ip

    def get_port(self):
        """
        Returns the port of the ArtNet node

        :return: port of the device, as set in plugin.conf
        """
        return self._port

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

    def get_universe(self):
        """
        Returns the Universe of the ArtNet node

        :return: Universe of the device, as set in plugin.conf
        """
        return self._universe

    def get_items(self):
        """
        Returns added items

        :return: array of items held by the device, sorted by their DMX-address
        """
        return sorted(self._items, key=lambda i: self._plugin.get_iattr_value(i.conf, "artnet_address"))


    def get_min_channels(self):
        """
        Returns minimum channels to be sent

        :return: number of minimum channels to be sent
        """
        return self._min_channels


class ArtNet(SmartPlugin):

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.6.1"
    ADDR_ATTR = 'artnet_address'

    packet_counter = 1
    dmxdata = [0, 0]

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.
        """
        super().__init__()
        self.logger.info('Init ArtNet Plugin')

        self._model = ArtNet_Model(ip=self.get_parameter_value('ip'),
                                   port=self.get_parameter_value('port'),
                                   net=self.get_parameter_value('artnet_net'),
                                   subnet=self.get_parameter_value('artnet_subnet'),
                                   universe=self.get_parameter_value('artnet_universe'),
                                   instance_name=self.get_instance_name(),
                                   update_cycle=self.get_parameter_value('update_cycle'),
                                   min_channels=self.get_parameter_value('min_channels'),
                                   plugin=self
                                   )

        while len(self.dmxdata) < self._model._min_channels:
            self.dmxdata.append(0)

        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.init_webinterface(WebInterface)

        self.logger.debug("Init ArtNet Plugin for %s done" %
                          self._model._instance_name)

    def parse_item(self, item):
        # items bound to this artnet-universe
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
                self.logger.warning(
                    "Impossible to update address: %s to value %s from item %s, value has to be >=0 and <=255" % (adr, item(), item))
            else:
                self.logger.debug("Updating address: %s to value %s" % (adr, item()))
                self.send_single_value(adr, item())

    def _update_loop(self):
        if not self.alive:
            return
        if len(self.dmxdata) < 1:
            return
        self.__ArtDMX_broadcast()

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("run method called")
        if self._model._update_cycle > 0:
            self.scheduler_add('updateArtnet', self._update_loop,
                               prio=5, cycle=self._model._update_cycle, offset=2)
        self.alive = True
        for it in self._model._items:
            adr = int(self.get_iattr_value(it.conf, self.ADDR_ATTR))
            val = it()
            if val is None:
                self.logger.warning(f"Value for address {adr} is None.")
                continue
            elif val < 0 or val > 255:
                self.logger.warning(
                    "Impossible to update address: %s to value %s from item %s, value has to be >=0 and <=255" % (adr, val, it))
            else:
                self.logger.debug("Updating address: %s to value %s" % (adr, val))
            self.set_address_value(adr, val)
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

    def get_address_value(self, req_adr):
        adr = int(req_adr)
        while len(self.dmxdata) < adr:
            self.dmxdata.append(0)
        return self.dmxdata[adr - 1]

    def set_address_value(self, req_adr, val):
        while len(self.dmxdata) < req_adr:
            self.dmxdata.append(0)
        self.dmxdata[req_adr - 1] = val

    def send_single_value(self, adr, value):
        if adr < 1 or adr > 512:
            self.logger.error("DMX address %s invalid" % adr)
            return

        self.set_address_value(adr, value)
        self.__ArtDMX_broadcast()

    def send_frame_starting_at(self, adr, values):
        if adr < 1 or adr > (512 - len(values) + 1):
            self.logger.error("DMX address %s with length %s invalid" % (adr, len(values)))
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
        """
        Assemble data according to ArtDmx packet definition, see at
        https://artisticlicence.com/WebSiteMaster/User Guides/art-net.pdf
        """
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
            if d is not None:
                data.append(struct.pack('B', int(d)))

        # convert from list to string
        result = bytes()
        for token in data:
            try:  # Handels all strings
                result = result + token.encode('utf-8', 'ignore')
            except:  # Handels all bytes
                result = result + token

        # send over ethernet
        self.logger.debug("Sending %s channels to %s:%s as Net/SubNet/Unv: %s/%s/%s" % (len(self.dmxdata),
                                                                                        self._model._ip,
                                                                                        self._model._port,
                                                                                        self._model._net,
                                                                                        self._model._subnet,
                                                                                        self._model._universe))
        self.s.sendto(result, (self._model._ip, self._model._port))
