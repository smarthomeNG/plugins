#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018-      Martin Sinn                         m.sinn@gmx.de
#  Copyright 2012-2013  KNX-User-Forum e.V.     http://knx-user-forum.de/
#########################################################################
#  This file is part of SmartHomeNG.py.
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  SmartHomeNG.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import socket
import threading
import time

from lib.model.smartplugin import *


class eBus(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.5.0'

    _items = []

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters descriptions for this method are pulled from the entry in plugin.yaml.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are imlemented
        to support older plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name) instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        logger = logging.getLogger(__name__)   # remove for shNG v1.6
        self.host = self.get_parameter_value('host')
        self.port = self.get_parameter_value('port')
        self._cycle = self.get_parameter_value('cycle')

        self._sock = False
        self.connected = False
        self._connection_attempts = 0
        self._connection_errorlog = 60
        # smarthome.connections.monitor(self)
        self.get_sh().connections.monitor(self)
        self._lock = threading.Lock()
        # self.refresh_cycle = self._cycle      # not used


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
        if 'ebus_type' in item.conf and 'ebus_cmd' in item.conf:
            self._items.append(item)
            return self.update_item


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called".format(self.get_fullname()))
        self.alive = True
        self.scheduler_add('eBusd', self.refresh, prio=5, cycle=self._cycle, offset=2)


    def refresh(self):
        """
        Refresh items with data from ebusd
        """
        for item in self._items:
            time.sleep(1)
            ebus_type = item.conf['ebus_type']
            ebus_cmd = item.conf['ebus_cmd']
            if ebus_cmd == "cycle":
                request = ebus_type + " " + ebus_cmd  # build command
            else:
                request = "get" + " " + ebus_cmd  # build command
            value = self.request(request)
            #if reading fails (i.e. at broadcast-commands) the value will not be updated
            if 'command not found' not in str(value) and value is not None:
                item(value, 'eBus', 'refresh')
            if not self.alive:
                break


    def request(self, request):
        """
        send request to ebusd deamon

        :param request: Command to send to ebusd
        :type request: str
        """
        if not self.connected:
            self.logger.info("eBusd not connected")
            return
        self._lock.acquire()
        try:
            self._sock.send(request.encode())
            self.logger.debug("REQUEST: {0}".format(request))
        except Exception as e:
            self._lock.release()
            self.close()
            self.logger.warning("error sending request: {0} => {1}".format(request, e))
            return
        try:
            answer = self._sock.recv(256).decode()[:-2]
            self.logger.debug("ANSWER: {0}".format(answer))
        except socket.timeout:
            self._lock.release()
            self.logger.warning("error receiving answer: timeout")
            return
        except Exception as e:
            self._lock.release()
            self.close()
            self.logger.warning("error receiving answer: {0}".format(e))
            return
        self._lock.release()
        return answer


    def connect(self):
        """
        Open socket connection to ebusd deamon
        """
        self._lock.acquire()
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(2)
            self._sock.connect((self.host, self.port))
        except Exception as e:
            self._connection_attempts -= 1
            if self._connection_attempts <= 0:
                self.logger.error('eBus:	could not connect to ebusd at {0}:{1}: {2}'.format(self.host, self.port, e))
                self._connection_attempts = self._connection_errorlog
            self._lock.release()
            return
            self.logger.info('Connected to {0}:{1}'.format(self.host, self.port))
        self.connected = True
        self._connection_attempts = 0
        self._lock.release()


    def close(self):
        """
        Close socket connection
        """
        self.connected = False
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            self._sock.close()
            self._sock = False
            self.logger.info('Connection closed to {0}:{1}'.format(self.host, self.port))
        except:
            pass


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called".format(self.get_fullname()))
        self.close()
        self.alive = False


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if caller != 'eBus':
            value = str(int(item()))
            cmd = item.conf['ebus_cmd']
            request = "set " + cmd + " " + value
            set_answer = self.request(request)
            #just check if set was no broadcast-message
            if 'broadcast done' not in set_answer:
                request = "get " + cmd
                answer = self.request(request)
                #transfer value and answer to float for better comparsion
                if float(answer) != float(value) or answer is None:
                    self.logger.warning("Failed to set parameter: value: {0} cmd: {1} answer {2}".format(value, request, answer))
