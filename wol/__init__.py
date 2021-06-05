#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2016-     Christian Strassburg            c.strassburg@gmx.de
#########################################################################
#  This file is part of SmartHomeNG
#  https://github.com/smarthomeNG/smarthome
#  http://knx-user-forum.de/

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

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface

ITEM_TAG = ['wol_mac', 'wol_ip']


class WakeOnLan(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = "1.2.0"

    def __init__(self, sh, *args, **kwargs):
        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # if plugin should start even without web interface
        self.init_webinterface(WebInterface)


    def __call__(self, mac_adr):
        self.wake_on_lan(mac_adr)

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False


    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, ITEM_TAG[0]):
            return self.update_item

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and item():
            if self.has_iattr(item.conf, ITEM_TAG[0]):
                if self.has_iattr(item.conf, ITEM_TAG[1]):
                    self.wake_on_lan(self.get_iattr_value(item.conf, ITEM_TAG[0]),
                                     self.get_iattr_value(item.conf, ITEM_TAG[1]))
                else:
                    self.wake_on_lan(self.get_iattr_value(item.conf, ITEM_TAG[0]))

    def wake_on_lan(self, mac_adr, ip_adr=None):
        """
        Prepare a magic packet and send to given mac address, optionally via given ip address

        :param mac_adr: mac addres of device to wake up
        :type mac_adr: mac
        :param ip_adr: ip address, if not given defaults to '<broadcast>'
        :type ip_adr: ip4
        """
        self.logger.debug(f"WakeOnLan: send magic paket to {mac_adr}")
        # check length and format 
        if self.is_mac(mac_adr) != True:
            self.logger.warning(f"WakeOnLan: invalid mac address {mac_adr}!")
            return
        if len(mac_adr) == 12 + 5:
            sep = mac_adr[2]
            mac_adr = mac_adr.replace(sep, '')
        # create magic packet 
        data = ''.join(['FF' * 6, mac_adr * 20])

        # Broadcast
        if isinstance(ip_adr, str):
            if ip_adr.strip() == "":
                ip_adr = None
        
        if ip_adr is None: ip_adr = '<broadcast>'

        if ip_adr:
            self.logger.debug(f"WakeOnLan: send magic paket {data} to ip/mac {ip_adr}/{mac_adr}")
        else:
            self.logger.debug(f"WakeOnLan: send magic paket {data} to mac {mac_adr}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(bytearray.fromhex(data), (ip_adr, 7))
