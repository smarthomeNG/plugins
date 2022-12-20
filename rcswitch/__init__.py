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
from socket import gethostname
import time
import threading
import subprocess
import os
from subprocess import DEVNULL
import shlex

class RCswitch(SmartPlugin):

	ALLOW_MULTIINSTANCE = False
	PLUGIN_VERSION = "2.0.0"

	def __init__(self, smarthome, rcswitch_dir = '/usr/local/bin/python/rcSwitch-python', rcswitch_sendDuration = '0.5', rcswitch_host = None, rcswitch_user = None, rcswitch_password = None):
		self.logger = logging.getLogger(__name__)
		self._sh = smarthome
		
		# internal member variables
		self._setupOK = False
		self._cmd_interpreter = "python3"
		self._switch_cmd = "/switchSocket.py"
		self._remote_user = None
		self._fileStat = None
		self._ssh_pass = None
		self._cmd_str = ""
		
		
		# format path: cut possible '/' at end of rcswitch_dir parameter
		if rcswitch_dir[len(rcswitch_dir)-1] == '/':
			self._rcswitch_dir = rcswitch_dir[0:len(rcswitch_dir)-1]
		else:
			self._rcswitch_dir = rcswitch_dir

		# Check optional Parameters: check sendDuration
		try:
			self.sendDuration = float(rcswitch_sendDuration)
		except Exception as e:
			self.sendDuration = float(0.5)
			self.logger.warning('RCswitch: Argument {} for rcswitch_sendDuration is not a valid number. Using default value instead.'.format(rcswitch_sendDuration))
		
		# Handle host, check if anything is defined in rcswitch_host parameter and if is valid hostname or valid IPv4 adress
		if (rcswitch_host and (self.is_hostname(rcswitch_host) or self.is_ipv4(rcswitch_host))):
			# then check if user defined its own local host -> error
			if ((rcswitch_host == gethostname()) or (rcswitch_host == '127.0.0.1')):
				self.logger.error('RCswitch: rcswitch_host is defined as your own machine, not the remote address! Please check the parameter rcswitch_host, >>{}<< it seems to be not correct!'.format(rcswitch_host))

			# check connection to remote host and accept fingerprint
			try:
				# following line shall raise an error in case connection is not possible.
				# check on the remote machine if the user <rcswitch_user> exists
				self._remote_user = subprocess.check_output(shlex.split('sshpass -p {} ssh -o StrictHostKeyChecking=no {}@{} grep {} /etc/passwd'.format(rcswitch_password, rcswitch_user, rcswitch_host, rcswitch_user)), stderr=DEVNULL).decode('utf8')[0:len(rcswitch_user)]
				# check if rc switch is installed at the specified path on remote host
				self._fileStat = subprocess.check_output(shlex.split('sshpass -p {} ssh {}@{} stat -c %a {}'.format(rcswitch_password, rcswitch_user, rcswitch_host, self._rcswitch_dir)), stderr=DEVNULL).decode('utf8')
				# create remote access variables
				self._ssh_pass = ('sshpass -p {} ssh {}@{}'.format(rcswitch_password, rcswitch_user, rcswitch_host))
			except subprocess.CalledProcessError as e:
				self._setupOK = False
				# give user hint where the problem is located
				try:
					self.logger.info("RC-Switch User: {}".format(rcswitch_user))
					if (self._remote_user == rcswitch_user):
						self.logger.error('RCswitch: send file of RCswitch not found at {} on {}. Check if RCswitch is installed correctly at specifed path on {}. System returned: {}'.format(self._rcswitch_dir, rcswitch_host, rcswitch_host, e))
					else:
						self.logger.error('RCswitch: send file of RCswitch not found at {} on {}. Additional problem with USER authentication possible. System returned: {}'.format(self._rcswitch_dir, rcswitch_host, e))
				except UnboundLocalError as e:
					self.logger.error('RCswitch: Cannot connect to {}. Check rcswitch_host, rcswitch_user and rcswitch_password are set (correctly). Ensure SSH server is running on {}. System returned: {}'.format(rcswitch_host, rcswitch_host, e))
		else:
			# check if rc switch is installed at the specified path
			if not os.path.isfile('{}{}'.format(self._rcswitch_dir, self._switch_cmd)):
				self.logger.error('RCswitch: send file of RCswitch not found at {} on localhost. Check path, if RCswitch is installed correctly on target, and correct format of v4 IP adress (in case rcswitch_host is defined).'.format(self._rcswitch_dir))
				self._setupOK = False
			else:
				self.logger.info('RCswitch: setup on localhost OK!\n\n')
				# output of remote control variables
		self.logger.info("Remote file stats:      {}".format(self._fileStat))
		self.logger.info("Remote User:            {}".format(self._remote_user))
		self.logger.info('Remote Host:            {}'.format(rcswitch_host))
		self.logger.info("ssh pass command:       {}".format(self._ssh_pass))
		self.logger.info("RC Switch directory:    {}".format(self._rcswitch_dir))
		self.logger.info("Interpreter:            {}".format(self._cmd_interpreter))
		
		# build the command string
		if self._ssh_pass == None:
			self._cmd_str = "{} {}{}".format(self._cmd_interpreter, self._rcswitch_dir, self._switch_cmd)
			self.logger.info("Switch command:         {} {}{} <SystemCode> <ButtonCode> <status>\n\n".format(self._cmd_interpreter, self._rcswitch_dir, self._switch_cmd))
		else:
			self._cmd_str = "{} {} {}{}".format(self._ssh_pass, self._cmd_interpreter, self._rcswitch_dir, self._switch_cmd)
			self.logger.info("Switch command:         {} {} {}{} <SystemCode> <ButtonCode> <status>\n\n".format(self._ssh_pass, self._cmd_interpreter, self._rcswitch_dir, self._switch_cmd))
		# then setup is ok
		self._setupOK = True
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
		# if 'rc_device' in item.conf and 'rc_code' in item.conf and self.setupOK:
		if self.has_iattr(item.conf, 'rc_code') and self.has_iattr(item.conf, 'rc_device') and self._setupOK:
			# prepare parameters
			value = int(item())
			rcCode = self.get_iattr_value(item.conf, 'rc_code') 
			rcDevice = self.get_iattr_value(item.conf, 'rc_device')
		
			# avoid parallel access by use of semaphore
			self.lock.acquire()
			# sending commands
			try:
				cmd_str = shlex.split('{} {} {} {}'.format(self._cmd_str, rcCode, rcDevice, value))
				self.logger.info('cmd_str: {}\n'.format(cmd_str))
				subprocess.call(cmd_str, stdout=DEVNULL, stderr=DEVNULL)
				self.logger.info('RC Switch: setting Device {} with SystemCode {} to {}'.format(rcDevice, rcCode, value))
			# invalid encoding of device
			except Exception as e: 
				self.logger.error('RC Switch: requesting invalid Device {} with SystemCode {} '.format(rcDevice, rcCode))
			time.sleep(min(self.sendDuration,10))# give the transmitter time to complete sending of the command (but not more than 10s)
			self.lock.release()