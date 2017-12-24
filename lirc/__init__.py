#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017 Nino Coric                       mail2n.coric@gmail.com
#########################################################################
#  This file is part of SmartHomeNG.   
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
import lib.connection

from lib.model.smartplugin import SmartPlugin

REMOTE_ATTRS = ['lirc_remote', 'lirc_key']
class LIRC(lib.connection.Client,SmartPlugin):

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.4.1"

    def __init__(self, sh, lirc_host, lirc_port=8765):
        self.instance = self.get_instance_name()
        self.logger = logging.getLogger(__name__)
        self.lircHost = lirc_host
        self.lircPort = lirc_port
        lib.connection.Client.__init__(self, self.lircHost, self.lircPort, monitor=True)
        self._sh = sh
        self._cmd_lock = threading.Lock()
        self._reply_lock = threading.Condition()
        self.terminator = b'\n'

        self.lircd_version = ''
        self._responseStr = None
        self._parseLine = 0
        self._error = False

    def loggercmd (self, logstr, level):
        if not logstr:
            return
        logstr = 'lirc_' + self.instance + ': ' + logstr
        if level == 'i' or level == 'info':
            self.logger.info(logstr)
        elif level == 'w' or level == 'warning':
            self.logger.warning(logstr)
        elif level == 'd' or level == 'debug':
            self.logger.debug(logstr)
        else:
            self.logger.error(logstr)

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False
        self._reply_lock.acquire()
        self._reply_lock.notify()
        self._reply_lock.release()
        self.close()

    def parse_item(self, item):
        if self.has_iattr(item.conf, REMOTE_ATTRS[0]) and \
           self.has_iattr(item.conf, REMOTE_ATTRS[1]):
                self.loggercmd("{}: callback assigned".format(item),'d')
                return self.update_item
        return None

    def handle_connect(self):
        self.found_terminator = self.parse_response
        self.request_version()

    def parse_response(self, data):
        data = data.decode()
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
        if val == 0:
            return None
        item(0)
        if val < 0:
            self.loggercmd("ignoring invalid value {}".format(val),'w')
        else:
            remote = self.get_iattr_value(item.conf,REMOTE_ATTRS[0])
            key = self.get_iattr_value(item.conf,REMOTE_ATTRS[1])
            self.loggercmd("update_item, val: {}".format(val),'d')
            self.loggercmd("remote: {}".format(remote),'d')
            self.loggercmd("key: {}".format(key),'d')
            command = "SEND_ONCE {} {} {}".format(remote,key,val)
            self.loggercmd("command: {}".format(command),'d')
            self._send(command)

    def request_version(self):
        self.lircd_version = self._send("VERSION")
        if self.lircd_version:
            self.loggercmd("connected to lircd {} on {}:{}".format( \
            self.lircd_version.replace("VERSION\n","").replace("\n",""), \
            self.lircHost,self.lircPort),'i')
            return True
        else:
            self.loggercmd("lircd Version not detectable",'e')
            return False

    def _send(self, command, reply=True):
        if not self.connected:
            return
        self._responseStr = None
        self._cmd_lock.acquire()
        self.loggercmd("send command: {}".format(command),'d')
        self._reply_lock.acquire()
        self.send((command + '\n').encode())
        if reply:
            self._reply_lock.wait(1)
        self._reply_lock.release()
        self._cmd_lock.release()
        if self._error:
            self.loggercmd("error from lircd: {}".format(self._responseStr),'e')
            self._error = False
        self.loggercmd("response: {}".format(self._responseStr),'d')
        return self._responseStr

if __name__ == '__main__':
    myplugin = LIRC('smarthome-dummy')
    logging.basicConfig(level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
    myplugin._send('VERSION')
