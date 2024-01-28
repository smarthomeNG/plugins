#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2017      Daniel Frank                knx-user-forum.de:dafra
#########################################################################
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
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

from lib.model.smartplugin import SmartPlugin
from socket import gethostname
import time
import threading
import subprocess
import os
from subprocess import DEVNULL
import shlex


class RCswitch(SmartPlugin):

    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.2.2"

    def __init__(self, sh, **kwargs):
        self.setupOK = True
        self.mapping = {'a': 1, 'A': 1, 'b': 2, 'B': 2, 'c': 3, 'C': 3, 'd': 4, 'D': 4, 'e': 5, 'E': 5}
        self.rcswitch_dir = self.get_parameter_value('rcswitch_dir')
        self.rcswitch_sendDuration = self.get_parameter_value('rcswitch_sendDuration')
        self.rcswitch_host = self.get_parameter_value('rcswitch_host')
        self.rcswitch_user = self.get_parameter_value('rcswitch_user')
        self.rcswitch_password = self.get_parameter_value('rcswitch_password')

        # format path: cut possible '/' at end of rcswitch_dir parameter
        if self.rcswitch_dir.endswith('/'):
            self.rcswitch_dir = self.rcswitch_dir[:-1]

        # Handle host, check if anything is defined in self.rcswitch_host parameter and if is valid hostname or valid IPv4 adress
        if self.rcswitch_host:
            # then check if user defined its own local host -> error
            if ((self.rcswitch_host == gethostname()) or (self.rcswitch_host == '127.0.0.1')):
                self.logger.error('RCswitch: rcswitch_host is defined as your own machine, not the remote address! Please check the parameter rcswitch_host, >>{}<< it seems to be not correct!'.format(self.rcswitch_host))

            # check connection to remote host and accept fingerprint
            user = None
            try:
                # following line shall raise an error in case connection is not possible.
                user = subprocess.check_output(shlex.split('sshpass -p {} ssh -o StrictHostKeyChecking=no {}@{} grep {} /etc/passwd'.format(self.rcswitch_password, self.rcswitch_user, self.rcswitch_host, self.rcswitch_user)), stderr=DEVNULL).decode('utf8')[:len(self.rcswitch_user)]
                # check  if rc switch is installed at the specified path on remote host
                self.fileStat = subprocess.check_output(shlex.split('sshpass -p {} ssh {}@{} stat -c %a {}'.format(self.rcswitch_password, self.rcswitch_user, self.rcswitch_host, self.rcswitch_dir)), stderr=DEVNULL).decode('utf8')
                self.rcswitch_dir = 'sshpass -p {} ssh {}@{} {}'.format(self.rcswitch_password, self.rcswitch_user, self.rcswitch_host, self.rcswitch_dir)
                self.logger.info('RCswitch: Using {} as host.'.format(self.rcswitch_host))
            except subprocess.CalledProcessError as e:
                self.setupOK = False
                # give user hint where the problem is located
                try:
                    if (user == self.rcswitch_user):
                        self.logger.error('RCswitch: send file of RCswitch not found at {} on {}. Check if RCswitch is installed correctly at specifed path on {}. System returned: {}'.format(self.rcswitch_dir, self.rcswitch_host, self.rcswitch_host, e))
                    else:
                        self.logger.error('RCswitch: send file of RCswitch not found at {} on {}. Additional problem with user authentication possible. System returned: {}'.format(self.rcswitch_dir, self.rcswitch_host, e))
                except UnboundLocalError as e:
                    self.logger.error('RCswitch: Cannot connect to {}. Check rcswitch_host, rcswitch_user and rcswitch_password are set (correctly). Ensure SSH server is running on {}. System returned: {}'.format(self.rcswitch_host, self.rcswitch_host, e))
        else:
            # check if rc switch is installed at the specified path
            if not os.path.isfile('{}/send'.format(self.rcswitch_dir)):
                self.logger.error('RCswitch: send file of RCswitch not found at {} on localhost. Check path, if RCswitch is installed correctly on target, and correct format of v4 IP adress (in case rcswitch_host is defined).'.format(self.rcswitch_dir))
                self.setupOK = False
            else:
                self.logger.info('RCswitch: setup on localhost OK')

        # setup semaphore
        self.lock = threading.Lock()

        # don't load plugin if init didn't work
        if not self.setupOK:
            self._init_complete = False

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        # generate warnings for incomplete configured itemns
        if self.has_iattr(item.conf, 'rc_device'):
            if self.has_iattr(item.conf, 'rc_code'):
                return self.update_item
            else:
                self.logger.warning('RC Switch: attribute rc_code for {} missing. Item will be ignored by RCswitch plugin'.format(item))
                return None
        elif self.has_iattr(item.conf, 'rc_code'):
            self.logger.warning('RC Switch: attribute rc_device for {} missing. Item will be ignored by RCswitch plugin'.format(item))
            return None
        else:
            return None

    def update_item(self, item, caller=None, source=None, dest=None):
        # send commands to devices
        if self.has_iattr(item.conf, 'rc_code') and self.has_iattr(item.conf, 'rc_device') and self.alive:
            # prepare parameters
            value = item()
            rcCode = self.get_iattr_value(item.conf, 'rc_code')
            rcDevice = self.get_iattr_value(item.conf, 'rc_device')

            # avoid parallel access by use of semaphore
            self.lock.acquire()
            # sending commands
            if (rcDevice in self.mapping):  # handling of device encoded with a,A,b,...
                subprocess.call(shlex.split('{}/send {} {} {}'.format(self.rcswitch_dir, rcCode, self.mapping[rcDevice], int(value))), stdout=DEVNULL, stderr=DEVNULL)
                self.logger.info('RC Switch: setting device {} with system code {} to {}'.format(rcDevice, rcCode, value))
            else:
                try:  # handling of devices encoded with 1,2,3
                    subprocess.call(shlex.split('{}/send {} {} {}'.format(self.rcswitch_dir, rcCode, int(rcDevice), int(value))), stdout=DEVNULL, stderr=DEVNULL)
                    self.logger.info('RC Switch: setting device {} with system code {} to {}'.format(rcDevice, rcCode, value))
                except Exception:  # invalid encoding of device
                    self.logger.error('RC Switch: requesting invalid device {} with system code {} '.format(rcDevice, rcCode))
            time.sleep(min(self.rcswitch_sendDuration, 10))  # give the transmitter time to complete sending of the command (but not more than 10s)
            self.lock.release()
