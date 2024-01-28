#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022      Frank Häfele                  mail@frankhaefele.de
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

from lib.model.smartplugin import SmartPlugin
from .webif import WebInterface
from lib.item import Items
from .cRcSocketSwitch import cRcSocketSwitch
import time
import threading


class RCS1000N(SmartPlugin):

	ALLOW_MULTIINSTANCE = False
	PLUGIN_VERSION = "1.0.0"

	def __init__(self, sh):
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
		# Initialization code goes here
		# internal member variables
		self._gpio = int(self.get_parameter_value('rcs1000n_gpio'))
		self._send_duration = float(self.get_parameter_value('rcs1000n_sendDuration'))
		# create threading.Lock() obj 
		self._lock = threading.Lock()
		
		# On initialization error use:
		#   self._init_complete = False
		#   return
		
		# if plugin should start even without web interface
		self.init_webinterface(WebInterface)
		# if plugin should not start without web interface
		# if not self.init_webinterface():
		#     self._init_complete = False
		return None
		
	def run(self):
		self.logger.debug("Run method called")
		self.alive = True

	def stop(self):
		self.logger.debug("Stop method called")
		self.alive = False

	def parse_item(self, item):
		# generate warnings for incomplete configured itemns
		if self.has_iattr(item.conf, 'rcs_SystemCode'):
			# do a sanity check for rcs_SystemCode
			systemcode_ok = cRcSocketSwitch.RCS1000N.sanity_check_Systemcode(self.get_iattr_value(item.conf, 'rcs_SystemCode'))
			if self.has_iattr(item.conf, 'rcs_ButtonCode'):
				# do a sanity check for rcs_ButtonCode
				buttoncode_ok = cRcSocketSwitch.RCS1000N.sanity_check_Buttoncode(self.get_iattr_value(item.conf, 'rcs_ButtonCode'))
				if systemcode_ok and buttoncode_ok:
					return self.update_item
				else:
					self.logger.warning('Warning: Item {} is NOT correctly configured!. Item will be ignored by rcSwitch_python plugin'.format(item.id()))
			else:
				self.logger.warning('Warning: attribute <rcs_ButtonCode> for {} missing. Item will be ignored by rcSwitch_python plugin'.format(item.id()))
				return None
		elif self.has_iattr(item.conf, 'rcs_ButtonCode'): 
			self.logger.warning('Warning: attribute <rcs_SystemCode> for {} missing. Item will be ignored by RCswitch plugin'.format(item.id()))
			return None
		else:
			return None


	def update_item(self, item, caller=None, source=None, dest=None):
		# send commands to devices
		# if 'rcs_ButtonCode' in item.conf and 'rcs_SystemCode' in item.conf and self.setupOK:
		if self.alive and caller != self.get_shortname():

		# if SystemCode and Buttoncode used
			if self.has_iattr(item.conf, 'rcs_SystemCode') and self.has_iattr(item.conf, 'rcs_ButtonCode'):
				SystemCode = self.get_iattr_value(item.conf, 'rcs_SystemCode')
				ButtonCode = self.get_iattr_value(item.conf, 'rcs_ButtonCode')

			self.logger.info(f"update_item was called with item {item.id()} from caller {caller}, source {source} and dest {dest}")
			# prepare parameters
			value = int(item())
			values = (SystemCode, ButtonCode, value)
			
			# sending commands and avoid parallel access by threading.Lock()
			with self._lock:
				try:
					# create Brennenstuhl RCS1000N object 
					obj = cRcSocketSwitch.RCS1000N(self._gpio)
				except Exception as err:
					self.logger.error('Error: during instantiation of object: {}'.format(err))
				else:
					# prepare and send values
					obj.send(*values)
					self.logger.info('Info: setting Device {} with SystemCode {} to {}'.format(ButtonCode, SystemCode, value))
				finally:
					# give the transmitter time to complete sending of the command (but not more than 10s)
					time.sleep(min(self._send_duration, 10))
