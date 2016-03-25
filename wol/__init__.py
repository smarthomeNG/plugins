#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2016-     Christian Strassburg            c.strassburg@gmx.de
#########################################################################
#  This file is part of SmartHome.py.
#  https://github.com/smarthomeNG/smarthome
#  http://knx-user-forum.de/

#  SmartHome.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################
#  Usage:
#
#  1. activate the plugin in etc/plugins.conf
#    [wakeonlan]
#        class_name = WakeOnLan
#        class_path = plugins.wol
#
#  2. add to you items atribute  "wol_mac" with the mac for wake up
#  [wakeonlan_item]
#     type = bool
#     wol_mac = 01:02:03:04:05:06
#
#  type of separators are unimportant. you can use:
#    wol_mac = 01:02:03:04:05:06
#  or:
#    wol_mac = 01-02-03-04-05-06
#  or don't use any separators:
#    wol_mac = 010203040506
#

import logging
import socket

item_tag = ['wol_mac']

logger = logging.getLogger('')


class WakeOnLan():
    def __init__(self, sh):
        self._sh = sh

    def __call__(self, mac_adr):
        self.wake_on_lan(mac_adr)

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        logger.debug("wol parse item" )
        if item_tag[0] in item.conf:
            return self.update_item

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        logger.debug("wol update item" )
        if item():
            logger.debug("wol update item item" )
            if item_tag[0] in item.conf:
                logger.debug("wol update item tag" )
                self.wake_on_lan(item.conf[item_tag[0]])

    def wake_on_lan(self, mac_adr):
        data = ''
        logger.debug("WakeOnLan: send magic paket to {}".format(mac_adr))
        # prüfung auf länge und format
        if len(mac_adr) == 12:
            pass
        elif (len(mac_adr) == 12 + 5):
            sep = mac_adr[2]
            mac_adr = mac_adr.replace(sep, '')
        else:
            logger.warning("WakeOnLan: invalid mac address {}!".format(mac_adr))
            return
        # Magic packet erstellen
        data = ''.join(['FF' * 6, mac_adr * 20])
        # Broadcast
        logger.debug("WakeOnLan: send magic paket " + data)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(bytearray.fromhex(data), ('<broadcast>', 7))
