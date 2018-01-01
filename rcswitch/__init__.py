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

import logging
from lib.model.smartplugin import SmartPlugin
from datetime import datetime, timedelta
import time
import threading
import subprocess
import os
from subprocess import DEVNULL
import shlex

class RCswitch(SmartPlugin):

	ALLOW_MULTIINSTANCE = False
	PLUGIN_VERSION = "1.2.0.3"

	def __init__(self, smarthome, rcswitch_dir='/usr/local/bin/rcswitch-pi', rcswitch_sendDuration='0.5', rcswitch_host='', rcswitch_user='', rcswitch_password=''):
		self.logger = logging.getLogger(__name__)
		self.setupOK = True
		self.mapping = {'a':1,'A':1,'b':2,'B':2,'c':3,'C':3,'d':4,'D':4,'e':5,'E':5}
		self._sh=smarthome
		
		# format path: cut possible '/' at end of rcswitch_dir parameter
		if rcswitch_dir[len(rcswitch_dir)-1] == '/':
			self.rcswitch_dir = rcswitch_dir[0:len(rcswitch_dir)-1]
		else:
			self.rcswitch_dir = rcswitch_dir

		# Check optional Parameters: check sendDuration
		try:
			self.sendDuration = float(rcswitch_sendDuration)
		except Exception as e:
			self.sendDuration = float(0.5)
			self.logger.warning('RCswitch: Argument {} for rcswitch_sendDuration is not a valid number. Using default value instead.'.format(rcswitch_sendDuration))
		
		# Handle host
		if self.is_ip(rcswitch_host) and rcswitch_host != '127.0.0.1':
			#check connection to remote host and accept fingerprint
			try:
				# following line shall raise an error in case connection is not possible. 
				user = subprocess.check_output(shlex.split('sshpass -p {} ssh -o StrictHostKeyChecking=no {}@{} grep {} /etc/passwd'.format(rcswitch_password, rcswitch_user, rcswitch_host, rcswitch_user)), stderr=DEVNULL).decode('utf8')[0:len(rcswitch_user)]
				# check  if rc switch is installed at the specified path on remote host
				fileStat = subprocess.check_output(shlex.split('sshpass -p {} ssh {}@{} stat -c %a {}'.format(rcswitch_password, rcswitch_user, rcswitch_host, self.rcswitch_dir)), stderr=DEVNULL).decode('utf8')
				self.rcswitch_dir = ('sshpass -p {} ssh {}@{} {}'.format(rcswitch_password, rcswitch_user, rcswitch_host, self.rcswitch_dir))
				self.logger.info('RCswitch: Using {} as host.'.format(rcswitch_host))
			except subprocess.CalledProcessError as e:
				self.setupOK = False
				# give user hint where the problem is located
				try:
					if (user == rcswitch_user):
						self.logger.error('RCswitch: send file of RCswitch not found at {} on {}. Check if RCswitch is installed correctly at specifed path on {}. System returned: {}'.format(self.rcswitch_dir, rcswitch_host, rcswitch_host, e))
					else:
						self.logger.error('RCswitch: send file of RCswitch not found at {} on {}. Additional problem with user authentication possible. System returned: {}'.format(self.rcswitch_dir, rcswitch_host, e))
				except UnboundLocalError as e:
					self.logger.error('RCswitch: Cannot connect to {}. Check rcswitch_host, rcswitch_user and rcswitch_password are set (correctly). Ensure SSH server is running on {}. System returned: {}'.format(rcswitch_host, rcswitch_host, e))
		else:
			# check if rc switch is installed at the specified path
			if not os.path.isfile('{}/send'.format(self.rcswitch_dir)):
				self.logger.error('RCswitch: send file of RCswitch not found at {} on localhost. Check path, if RCswitch is installed correctly on target, and correct format of v4 IP adress (in case rcswitch_host is defined).'.format(self.rcswitch_dir))
				self.setupOK = False
			else:
				self.logger.info('RCswitch: setup on localhost OK')
		
		# setup semaphore
		self.lock = threading.Lock()
		
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
		if self.has_iattr(item.conf, 'rc_code') and self.has_iattr(item.conf, 'rc_device') and self.setupOK: #if 'rc_device' in item.conf and 'rc_code' in item.conf and self.setupOK:
			# prepare parameters
			value = item()
			rcCode =self.get_iattr_value(item.conf, 'rc_code') 
			rcDevice =self.get_iattr_value(item.conf, 'rc_device')
		
			# avoid parallel access by use of semaphore
			self.lock.acquire()
			# sending commands
			if(rcDevice in self.mapping):#handling of device encoded with a,A,b,...
				subprocess.call(shlex.split('{}/send {} {} {}'.format(self.rcswitch_dir, rcCode, self.mapping[rcDevice], int(value))), stdout=DEVNULL, stderr=DEVNULL)
				self.logger.info('RC Switch: setting device {} with system code {} to {}'.format(rcDevice, rcCode, value))
			else:
				try:#handling of devices encoded with 1,2,3
					subprocess.call(shlex.split('{}/send {} {} {}'.format(self.rcswitch_dir, rcCode, int(rcDevice), int(value))), stdout=DEVNULL, stderr=DEVNULL)
					self.logger.info('RC Switch: setting device {} with system code {} to {}'.format(rcDevice, rcCode, value))
				except Exception as e:#invalid encoding of device
					self.logger.error('RC Switch: requesting invalid device {} with system code {} '.format(rcDevice, rcCode))
			time.sleep(min(self.sendDuration,10))# give the transmitter time to complete sending of the command (but not more than 10s)
			self.lock.release()