#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017 Nino Coric                       mail2n.coric@gmail.com
#  Copyright 2019- Andreas Künz                    onkelandy66@gmail.com
#########################################################################
#  This file is part of SmartHomeNG.
#
#  lirc plugin for USB remote
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

import threading
import logging
import time
from lib.network import Tcp_client
from .webif import WebInterface
from lib.item import Items

from lib.model.smartplugin import SmartPlugin
from bin.smarthome import VERSION

REMOTE_ATTRS = ['lirc_remote', 'lirc_key']
class LIRC(SmartPlugin):

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.5.1"

    def __init__(self, smarthome):
        super().__init__()
        self._host = self.get_parameter_value('host')
        if self._host is None:
            self._host = self.get_parameter_value('lirc_host')
        self._port = self.get_parameter_value('port')
        self._autoreconnect = self.get_parameter_value('autoreconnect')
        self._connect_retries = self.get_parameter_value('connect_retries')
        self._connect_cycle = self.get_parameter_value('connect_cycle')
        name = 'plugins.' + self.get_fullname()
        self.items = Items.get_instance()
        self._lirc_tcp_connection = Tcp_client(host=self._host,
                                               port=self._port,
                                               name=name,
                                               autoreconnect=self._autoreconnect,
                                               connect_retries=self._connect_retries,
                                               connect_cycle=self._connect_cycle,
                                               binary=True,
                                               terminator=b'\n')
        self._lirc_tcp_connection.set_callbacks(connected=self._on_connect,
                                                data_received=self._on_received_data,
                                                disconnected=self._on_disconnect)
        self._cmd_lock = threading.Lock()
        self._reply_lock = threading.Condition()

        self._lircd_version = ''
        self._responseStr = None
        self._parseLine = 0
        self._error = False
        self._lirc_server_alive = False
        if self._init_complete:
            self.init_webinterface(WebInterface)

    def run(self):
        self.alive = True
        self.logger.debug("run method called")
        self._connect('run')

    def stop(self):
        self.logger.debug("stop method called")
        self.alive = False
        self._reply_lock.acquire()
        self._reply_lock.notify()
        self._reply_lock.release()
        if self._cmd_lock.locked():
            self._cmd_lock.release()
        self._lirc_server_alive = False
        self.logger.debug("Threads released")
        self._lirc_tcp_connection.close()
        self.logger.debug("Connection closed")

    def parse_item(self, item):
        if self.has_iattr(item.conf, REMOTE_ATTRS[0]) and \
           self.has_iattr(item.conf, REMOTE_ATTRS[1]):
                self.logger.debug("{}: callback assigned".format(item))
                self.add_item(item, config_data_dict={'lirc': True})
                return self.update_item
        return None

    def _connect(self, by):
        '''
        Method to try to establish a new connection to lirc

        :note: While this method is called during the start-up phase of the plugin, it can also be used to establish a connection to the lirc server if the plugin was initialized before the server went up or the connection is interrupted.

        :param by: caller information
        :type by: str
        '''
        self.logger.debug('Initializing connection to {}:{}, initiated by {}'.format(self._host, self._port, by))
        if not self._lirc_tcp_connection.connected():
            self._lirc_tcp_connection.connect()
            # we allow for 2 seconds to connect
            time.sleep(2)
        if not self._lirc_tcp_connection.connected():
            # no connection could be established, lirc may be offline
            self.logger.info('Could not establish a connection to lirc at {}'.format(self._host))
            self._lirc_server_alive = False
        else:
            self._lirc_server_alive = True

    def _on_connect(self, by=None):
        '''
        Recall method for succesful connect to lirc
        On a connect first check if the JSON-RPC API is available.
        If this is the case query lirc to initialize all items

        :param by: caller information
        :type by: str
        '''
        self._lirc_server_alive = True
        if isinstance(by, (dict, Tcp_client)):
            by = 'TCP_Connect'
        self.logger.info('Connected to {}, onconnect called by {}.'.format(self._host, by))
        self.request_version()

    def _on_disconnect(self, obj=None):
        '''
        Recall method for TCP disconnect
        '''
        self.logger.info('Received disconnect from {}'.format(self._host))
        self._lirc_server_alive = False

    def _on_received_data(self, connection, response):
        data = response.decode()
        #self.logger.debug("Got: {0}".format(data))
        if data.startswith('BEGIN'):
            return None
        elif data.startswith('END'):
            self._parseLine = 0
            self._reply_lock.acquire()
            self._reply_lock.notify()
            self._reply_lock.release()
            return None
        if self._parseLine >= 0:
            self._parseLine += 1
            if self._parseLine == 1:
                self._responseStr = str(data) + '\n'
            elif self._parseLine == 2:
                if data.startswith('ERROR'):
                    self._error = True
                else:
                    self._error = False
            elif self._parseLine == 3:
                pass #ignore field DATA
            elif self._parseLine == 4:
                pass #ignore field n
            else:
                self._responseStr += str(data) + '\n'

    def update_item(self, item, caller=None, source=None, dest=None):
        val = item()
        if val == 0 and source == "Web Interface":
            val = 1
        elif val == 0:
            return None
        item(0)
        if val < 0:
            self.logger.warning("ignoring invalid value {}".format(val))
        else:
            remote = self.get_iattr_value(item.conf,REMOTE_ATTRS[0])
            key = self.get_iattr_value(item.conf,REMOTE_ATTRS[1])
            self.logger.debug("update_item {}, val: {}, remote: {}, key: {}".format(item, val, remote, key))
            command = "SEND_ONCE {} {} {}".format(remote,key,val)
            return self._send(command, item, True)

    def request_version(self):
        self._send("VERSION", None, True)

    def _send(self, command, item=None, reply=True):
        i = 0
        while not self._lirc_server_alive:
            self.logger.debug("Waiting to send command {} as connection is not yet established. Count: {}/10".format(command, i))
            i += 1
            time.sleep(1)
            if i >= 10:
                self.logger.warning("10 seconds wait time for sending {} is over. Sending it now.".format(command))
                break
        self._responseStr = None
        self._cmd_lock.acquire()
        self.logger.debug("send command: {}".format(command))
        self._reply_lock.acquire()
        self._lirc_tcp_connection.send(bytes(command + '\n', 'utf-8'))
        if reply:
            self._reply_lock.wait(1)
        self._reply_lock.release()
        self._cmd_lock.release()
        try:
            self._responseStr = self._responseStr.replace("\n", "")
        except Exception:
            pass
        if self._error:
            self.logger.error("error from lircd: {}".format(self._responseStr))
            self._error = False
        elif isinstance(self._responseStr, str):
            self.logger.debug("response: {}".format(self._responseStr.replace("\n","")))
            if command == "VERSION":
                self._lircd_version = self._responseStr
                self.logger.info("connected to lircd {} on {}:{}".format( \
                self._lircd_version.replace("VERSION\n","").replace("\n",""), \
                self._host, self._port))
        return self._responseStr

if __name__ == '__main__':
    myplugin = LIRC('smarthome-dummy')
    logging.basicConfig(level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
    myplugin._send('VERSION', None, True)
