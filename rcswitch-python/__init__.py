#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022      Frank Häfele                  mail@frankhaefele.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.8 and
#  upwards.
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
from lib.item import Items
from .cRcSocketSwitch import cRcSocketSwitch
import time
import threading


class rcSwitch_python(SmartPlugin):

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
		self._gpio = int(self.get_parameter_value('rcswitch_gpio'))
		self._send_duration = float(self.get_parameter_value('rcswitch_sendDuration'))
		# setup semaphore
		self.lock = threading.Lock()
		
		# On initialization error use:
		#   self._init_complete = False
		#   return

		# if plugin should start even without web interface
		#self.init_webinterface(WebInterface)
		# if plugin should not start without web interface
		# if not self.init_webinterface():
		#     self._init_complete = False
		return
		
	def run(self):
		self.logger.debug("Run method called")
		self.alive = True

	def stop(self):
		self.logger.debug("Stop method called")
		self.alive = False

	def parse_item(self, item):
		# generate warnings for incomplete configured itemns
		if self.has_iattr(item.conf, 'rc_SystemCode'):
			if self.has_iattr(item.conf, 'rc_ButtonCode'):
				return self.update_item
			else:
				self.logger.warning('Warning: attribute rc_ButtonCode for {} missing. Item will be ignored by rcSwitch_python plugin'.format(item))
				return None
		elif 'rc_ButtonCode' in item.conf: 
			self.logger.warning('Warning: attribute rc_SystemCode for {} missing. Item will be ignored by RCswitch plugin'.format(item))
			return None
		else:
			return None


	def update_item(self, item, caller=None, source=None, dest=None):
		# send commands to devices
		# if 'rc_ButtonCode' in item.conf and 'rc_SystemCode' in item.conf and self.setupOK:
		if self.alive and caller != self.get_shortname(): 
			if self.has_iattr(item.conf, 'rc_SystemCode') and self.has_iattr(item.conf, 'rc_ButtonCode'):
				self.logger.info(f"update_item was called with item {item.property.path} from caller {caller}, source {source} and dest {dest}")
				# prepare parameters
				value = int(item())
				SystemCode = self.get_iattr_value(item.conf, 'rc_SystemCode') 
				ButtonCode = self.get_iattr_value(item.conf, 'rc_ButtonCode')
				values = (SystemCode, ButtonCode, value)
			
				# avoid parallel access by use of semaphore
				self.lock.acquire()
				# sending commands
				try:
					# create Brennenstuhl RCS1000N object 
					obj = cRcSocketSwitch.RCS1000N(self._gpio)
					# prepare and send values
					obj.send(*values)
				except Exception as err:
					self.logger.error('Error: during instantiation of object or during send to device: {}'.format(err))
				else:
					self.logger.info('Info: setting Device {} with SystemCode {} to {}'.format(ButtonCode, SystemCode, value))
				finally:
					# give the transmitter time to complete sending of the command (but not more than 10s)
					time.sleep(min(self._send_duration, 10))
					self.lock.release()