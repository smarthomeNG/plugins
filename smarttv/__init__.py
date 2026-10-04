#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012 2ndsky
#  Copyright 2026 Bernd Meiners                     Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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

import asyncio

from lib.model.smartplugin import SmartPlugin
from lib.item import Items
from uuid import getnode as getmac

import socket
import time
import base64
from websocket import create_connection

from .webif import WebInterface

class SmartTV(SmartPlugin):
    PLUGIN_VERSION = '1.4.0'
    ALLOW_MULTIINSTANCE = True

    def __init__(self, sh, **kwargs):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()



        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        #
        # self._cycle = 60

        # if you want to use an item to toggle plugin execution, enable the
        # definition in plugin.yaml and uncomment the following line
        #
        # self._pause_item_path = self.get_parameter_value('pause_item')

        # Initialization code goes here

        self._tv_version = self.get_parameter_value('tv_version')
        self._host = self.get_parameter_value('host')
        self._port = self.get_parameter_value('port')
        self._delay = self.get_parameter_value('delay')
        self._remote_control_name = self.get_parameter_value('remote_control_name')
        self._remote_control_app_name = self.get_parameter_value('remote_control_app_name')
        self._tv_name = self.get_parameter_value('tv_name')
        
        if self._tv_version not in ['samsung_m_series', 'classic']:
            self.logger.error('No valid tv_version attribute specified to plugin')
            self._init_complete = False
        else:
            self.logger.debug('Smart TV plugin for {0} SmartTV device initalized'.format(self._tv_version))

        self.init_webinterface(WebInterface)
        # if plugin should not start without web interface
        #
        # if not self.init_webinterface():
        #     self._init_complete = False


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.dbghigh(self.translate("Methode '{method}' aufgerufen", {'method': 'run()'}))

        self.alive = True  # if using asyncio, do not set self.alive here. Set it in the session coroutine

        # let the plugin change the state of pause_item
        if self._pause_item:
            self._pause_item(False, self.get_fullname())

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.dbghigh(self.translate("Methode '{method}' aufgerufen", {'method': 'stop()'}))
        self.alive = False  # if using asyncio, do not set self.alive here. Set it in the session coroutine

        # let the plugin change the state of pause_item
        if self._pause_item:
            self._pause_item(True, self.get_fullname())

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
        # check for pause item
        if item.property.path == self._pause_item_path:
            self.logger.debug(f'pause item {item.property.path} registered')
            self._pause_item = item
            self.add_item(item, updating=True)
            return self.update_item

        if self.has_iattr(item.conf, 'smarttv'):
            self.logger.debug(
                'Smart TV Item {0} with value {1} for plugin instance {2} found!'.format(
                    item, self.get_iattr_value(item.conf, 'smarttv'), self.get_instance_name()
                )
            )
            # Register the item so update_item() is called when the item changes.
            # updating=True means the item is also tracked in get_trigger_items().
            self.add_item(item, updating=True)

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

        To prevent a loop, the changed value should only be written to the device, if the plugin is running and
        the value was changed outside of this plugin(-instance). That is checked by comparing the caller parameter
        with the fullname (plugin name & instance) of the plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        # check for pause item
        if item is self._pause_item:
            if caller != self.get_shortname():
                self.logger.debug(f'pause item changed to {item()}')
                if item() and self.alive:
                    self.stop()
                elif not item() and not self.alive:
                    self.run()
            return

        if not self.alive:
            return

        if self.alive and caller != self.get_fullname():
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


    def push_samsung_m_series(self, key):
        """
        | Pushes a key (as string) to a websocket connection

        :param key: key as string representation
        """
        try:
            ws = create_connection(f'ws://{self._host}:{self._port}/api/v2/channels/samsung.remote.control')
        except Exception as e:
            self.logger.error(f'Could not connect to ws://{self._host}:{self._port}/api/v2/channels/samsung.remote.control, to send key: {key}. Exception: {e}')
            return
        cmd = f'{{"method":"ms.remote.control","params":{{"Cmd":"Click","DataOfCmd":"{key}","Option":"false","TypeOfRemote":"SendRemoteKey"}}}}'
        self.logger.debug(f'Sending {cmd} via websocket connection to ws://{self._host}:{self._port}/api/v2/channels/samsung.remote.control')
        ws.send(cmd)
        ws.close()

    def push_classic(self, key):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self._host, int(self._port)))
            self.logger.debug('Connected to {0}:{1}'.format(self._host, self._port))
        except Exception:
            self.logger.warning(f'Could not connect to {self._host}:{self._port} to send key: {key}')
            return

        src = s.getsockname()[0]  # ip of remote
        mac = self._int_to_str(getmac())  # mac of remote
        dst = self._host  # ip of tv
        remote = self._remote_control_name.encode('ascii', errors='ignore')
        app = self._remote_control_app_name.encode('ascii', errors='ignore')
        tv = self._tv_name.encode('ascii', errors='ignore')

        self.logger.debug(f'{src=}, {mac=}, {remote=}, {dst=}, {app=}, {tv=}')

        src = base64.b64encode(src.encode())
        mac = base64.b64encode(mac.encode())
        cmd = base64.b64encode(key.encode())
        rem = base64.b64encode(remote)

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
        except OSError:
            try:
                s.close()
            except OSError:
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
        except Exception:
            return
        finally:
            try:
                s.close()
            except Exception:
                pass
        self.logger.debug('Send {0} to Smart TV'.format(key))
        time.sleep(0.1)


    def _int_to_words(self, int_val, word_size, num_words):
        max_int = 2 ** (num_words * word_size) - 1

        if not 0 <= int_val <= max_int:
            raise IndexError('integer out of bounds: %r!' % hex(int_val))

        max_word = 2**word_size - 1

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
