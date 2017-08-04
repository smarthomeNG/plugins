#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#
# Copyright 2012 KNX-User-Forum e.V.            http://knx-user-forum.de/
#
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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
#  along with SmartHomeNG.  If not, see <http://www.gnu.org/licenses/>.
#

import logging
import socket
import time
import base64
from websocket import create_connection
from lib.model.smartplugin import SmartPlugin
from uuid import getnode as getmac

class SmartTV(SmartPlugin):

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.3.2"

    def __init__(self, smarthome, host, port=55000, tv_version='classic', delay=1):
        self.logger = logging.getLogger(__name__)
        self._sh = smarthome
        self._host = host
        self._port = int(port)
        self._delay = delay
        if tv_version not in ['samsung_m_series', 'classic']:
            self.logger.error('No valid tv_version attribute specified to plugin')
        self._tv_version = tv_version
        self.logger.debug("Smart TV plugin for {0} SmartTV device initalized".format(tv_version))

    def push_samsung_m_series(self, key):
        """
        | Pushes a key (as string) to a websocket connection

        :param key: key as string representation
        """
        try:
            ws = create_connection('ws://%s:%d/api/v2/channels/samsung.remote.control' % (self._host, self._port))
        except Exception as e:
            self.logger.error(
                "Could not connect to ws://%s:%d/api/v2/channels/samsung.remote.control, to send key: %s. Exception: %s" % (self._host, self._port, key, str(e)))
            return
        cmd = '{"method":"ms.remote.control","params":{"Cmd":"Click","DataOfCmd":"%s","Option":"false","TypeOfRemote":"SendRemoteKey"}}' % key
        self.logger.debug("Sending %s via websocket connection to %s" % (cmd, 'ws://%s:%d/api/v2/channels/samsung.remote.control' % (self._host, self._port)))
        ws.send(cmd)
        ws.close()
        return

    def push_classic(self, key):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self._host, int(self._port)))
            self.logger.debug("Connected to {0}:{1}".format(self._host, self._port))
        except Exception:
            self.logger.warning("Could not connect to %s:%s, to send key: %s." %
                           (self._host, self._port, key))
            return

        src = s.getsockname()[0]            # ip of remote
        mac = self._int_to_str(getmac())    # mac of remote
        remote = 'sh.py remote'             # remote name
        dst = self._host                    # ip of tv
        app = b'python'                      # iphone..iapp.samsung
        tv = b'UE32ES6300'                   # iphone.UE32ES6300.iapp.samsung

        self.logger.debug("src = {0}, mac = {1}, remote = {2}, dst = {3}, app = {4}, tv = {5}".format(
            src, mac, remote, dst, app, tv))

        src = base64.b64encode(src.encode())
        mac = base64.b64encode(mac.encode())
        cmd = base64.b64encode(key.encode())
        rem = base64.b64encode(remote.encode())

        msg = bytearray([0x64, 0])
        msg.extend([len(src), 0])
        msg.extend(src)
        msg.extend([len(mac), 0])
        msg.extend(mac)
        msg.extend([len(rem), 0])
        msg.extend(rem)

        pkt = bytearray([0])
        pkt.extend([len(app), 0])
        pkt.extend(app)
        pkt.extend([len(msg), 0])
        pkt.extend(msg)

        try:
            s.send(pkt)
        except:
            try:
                s.close()
            except:
                pass
            return

        msg = bytearray([0, 0, 0])
        msg.extend([len(cmd), 0])
        msg.extend(cmd)

        pkt = bytearray([0])
        pkt.extend([len(tv), 0])
        pkt.extend(tv)
        pkt.extend([len(msg), 0])
        pkt.extend(msg)

        try:
            s.send(pkt)
        except:
            return
        finally:
            try:
                s.close()
            except:
                pass
        self.logger.debug("Send {0} to Smart TV".format(key))
        time.sleep(0.1)

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'smarttv'):
            self.logger.debug("Smart TV Item {0} with value {1} for plugin instance {2} found!".format(
                item, self.get_iattr_value(item.conf, 'smarttv'), self.get_instance_name()))
            return self.update_item
        else:
            return None

    def update_item(self, item, caller=None, source=None, dest=None):
        val = item()
        if isinstance(val, str):
            if val.startswith('KEY_'):
                if self._tv_version == 'classic':
                    self.push_classic(val)
                elif self._tv_version == 'samsung_m_series':
                    self.push_samsung_m_series(val)
            return
        if val:
            keys = self.get_iattr_value(item.conf, 'smarttv')
            if isinstance(keys, str):
                keys = [keys]
            i = 0
            for key in keys:
                i = i + 1
                if isinstance(key, str) and key.startswith('KEY_'):
                    if i != len(keys):
                        time.sleep(self._delay)
                    if self._tv_version == 'classic':
                        self.push_classic(key)
                    elif self._tv_version == 'samsung_m_series':
                        self.push_samsung_m_series(key)

    def parse_logic(self, logic):
        pass

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def _int_to_words(self, int_val, word_size, num_words):
        max_int = 2 ** (num_words * word_size) - 1

        if not 0 <= int_val <= max_int:
            raise IndexError('integer out of bounds: %r!' % hex(int_val))

        max_word = 2 ** word_size - 1

        words = []
        for _ in range(num_words):
            word = int_val & max_word
            words.append(int(word))
            int_val >>= word_size

        return tuple(reversed(words))

    def _int_to_str(self, int_val):
        words = self._int_to_words(int_val, 8, 6)
        tokens = ['%.2X' % i for i in words]
        addr = '-'.join(tokens)

        return addr
