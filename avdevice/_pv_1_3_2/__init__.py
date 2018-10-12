#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 <Onkel Andy>					  <onkelandy@hotmail.com>
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Plugin to control AV Devices via TCP and/or RS232
#  Tested with Pioneer AV Receivers.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	 See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import logging
from lib.model.smartplugin import SmartPlugin
from itertools import groupby
import io
import time
import re
import errno
import serial
import socket
from .AVDeviceInit import Init

VERBOSE1 = logging.DEBUG - 1
VERBOSE2 = logging.DEBUG - 2
logging.addLevelName(logging.DEBUG - 1, 'VERBOSE1')
logging.addLevelName(logging.DEBUG - 2, 'VERBOSE2')


class AVDevice(SmartPlugin):
	ALLOW_MULTIINSTANCE = True
	PLUGIN_VERSION = "1.3.2"

	def __init__(self, smarthome,
				 model='',
				 ignoreresponse='RGB,RGC,RGD,GBH,GHH,VTA,AUA,AUB',
				 errorresponse='E02,E04,E06',
				 forcebuffer='GEH01020, GEH04022, GEH05024',
				 inputignoredisplay='',
				 dependson_item='',
				 dependson_value=True,
				 rs232_port='',
				 rs232_baudrate=9600,
				 rs232_timeout=0.1,
				 tcp_ip='',
				 tcp_port=23,
				 tcp_timeout=1,
				 resetonerror=False,
				 depend0_power0=False,
				 depend0_volume0=False,
				 sendretries=10,
				 resendwait=1.0,
				 reconnectretries=13,
				 secondstokeep=50,
				 responsebuffer='5',
				 autoreconnect=False):
		self.logger = logging.getLogger(__name__)
		self._sh = smarthome
		self.alive = False
		self._name = self.get_instance_name()
		self._serialwrapper = None
		self._serial = None
		self._tcpsocket = None
		self._functions = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
		self._items = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
		self._query_zonecommands = {'zone0': [], 'zone1': [], 'zone2': [], 'zone3': [], 'zone4': []}
		self._items_speakers = {'zone1': {}, 'zone2': {}, 'zone3': {}}
		self._send_commands = []
		self._keep_commands = {}
		self._query_commands = []
		self._power_commands = []
		self._response_commands = {}
		self._number_of_zones = 0
		self._trigger_reconnect = True
		self._reconnect_counter = 0
		self._resend_counter = 0
		self._resend_on_empty_counter = 0
		self._sendingcommand = 'done'
		self._special_commands = {}
		self._is_connected = []
		self._parsinginput = []

		try:
			self._model = self.get_parameter_value('model')
			self._resend_wait = float(self.get_parameter_value('resendwait'))
			self._secondstokeep = int(self.get_parameter_value('secondstokeep'))
			self._auto_reconnect = self.get_parameter_value('autoreconnect')
			self._resend_retries = int(self.get_parameter_value('sendretries'))
			self._reconnect_retries = int(self.get_parameter_value('reconnectretries'))
			ignoreresponse = self.get_parameter_value('ignoreresponse')
			errorresponse = self.get_parameter_value('errorresponse')
			forcebuffer = self.get_parameter_value('forcebuffer')
			inputignoredisplay = self.get_parameter_value('inputignoredisplay')
			resetonerror = self.get_parameter_value('resetonerror')
			responsebuffer = self.get_parameter_value('responsebuffer')
			depend0_power0 = self.get_parameter_value('depend0_power0')
			depend0_volume0 = self.get_parameter_value('depend0_volume0')
			dependson_item = self.get_parameter_value('dependson_item')
			dependson_value = self.get_parameter_value('dependson_value')
			tcp_ip = self.get_parameter_value('tcp_ip')
			tcp_port = self.get_parameter_value('tcp_port')
			tcp_timeout = self.get_parameter_value('tcp_timeout')
			rs232_port = self.get_parameter_value('rs232_port')
			rs232_baudrate = self.get_parameter_value('rs232_baudrate')
			rs232_timeout = self.get_parameter_value('rs232_timeout')
		except:
			self._model = model
			self._resend_wait = float(resendwait)
			self._secondstokeep = int(secondstokeep)
			self._auto_reconnect = autoreconnect
			self._resend_retries = int(sendretries)
			self._reconnect_retries = int(reconnectretries)

		# Initializing all variables
		self.logger.debug("Initializing {}: Resendwait: {}. Seconds to keep: {}.".format(self._name, self._resend_wait, self._secondstokeep))
		self.init = Init(self._sh, self._name, self._model, self._items)
		self._rs232, self._baud, self._timeout = self.init._process_variables([rs232_port, rs232_baudrate, rs232_timeout], 'rs232')
		self._tcp, self._port, self._tcp_timeout = self.init._process_variables([tcp_ip, tcp_port, tcp_timeout], 'tcp')
		self._dependson, self._dependson_value, self._depend0_power0, self._depend0_volume0 = self.init._process_variables([dependson_item, dependson_value, depend0_power0, depend0_volume0], 'dependson')

		self._response_buffer = self.init._process_variables(responsebuffer, 'responsebuffer')
		self._reset_onerror = self.init._process_variables(resetonerror, 'resetonerror')
		self._ignore_response, self._error_response, self._force_buffer, self._ignoredisplay = self.init._process_variables([ignoreresponse, errorresponse, forcebuffer, inputignoredisplay], 'responses')

	# Non-blocking wait function
	def _wait(self, time_lapse):
		time_start = time.time()
		time_end = (time_start + time_lapse)

		while time_end > time.time():
			pass

	# Resetting items when send command failed
	def _resetitem(self):
		try:
			resetting = None
			try:
				response = self._sendingcommand.split(",")[2].split("|")
				sendcommand = self._sendingcommand
				self.logger.debug("Resetting {}: Searching for suiting command for sendingcommand response: {}.".format(self._name, response))
			except Exception as e:
				response = self._send_commands[0].split(",")[2].split("|")
				sendcommand = self._send_commands[0]
				self.logger.log(VERBOSE1, "Resetting {}: Cannot find Sendingcommand. Using first Command in queue: {}. Message: {}".format(self._name, response, e))
			sorted_response_commands = sorted(self._response_commands, key=len, reverse=True)
			for key in sorted_response_commands:
				self.logger.log(VERBOSE2, "Resetting {}: Trying to reset Item. Comparing: {} with {}".format(self._name, key, response))
				for resp in response:
					for entry in self._response_commands[key]:
						try:
							if resp.startswith(key, 0, entry[1]):
								valuetype = sendcommand.split(',')
								try:
									valuetype[3:] = [','.join(valuetype[3:])]
									testvalue = valuetype[3]
								except Exception:
									testvalue = ''
								self.logger.log(VERBOSE1, "Resetting {}: Comparing value {} with type {} and expected type {}.".format(
									self._name, entry, testvalue, entry[7]))
								if testvalue == entry[7]:
									keyfound = entry
									self.logger.log(VERBOSE1, "Resetting {}: Found correct entry: {}".format(self._name, keyfound))
									break
								else:
									keyfound = ''
							else:
								keyfound = ''
						except Exception as err:
							keyfound = ''
							self.logger.debug("Resetting {}: Problem comparing response: {}. Error: {}".format(self._name, resp, err))
				if not keyfound == '':
					self.logger.debug("Resetting {}: Entry: {}".format(self._name, keyfound))
					zone = keyfound[5]
					previousvalue = self._items[zone][keyfound[4]]['Value']
					for item in keyfound[3]:
						self.logger.info("Resetting {}: Resetting Item {} to {}".format(
							self._name, item, previousvalue))
						item(previousvalue, 'AVDevice', self._tcp)
					if key in self._special_commands['Speakers']['Command']:
						for speaker in self._items_speakers[zone]:
							previousvalue = self._items_speakers[zone][speaker]['Value']
							for item in self._items_speakers[zone][speaker]['Item']:
								item(previousvalue, 'AVDevice', self._tcp)
								self.logger.info("Resetting {}: Resetting additional speaker item {} to value {}".format(
									self._name, item, previousvalue))
					resetting = keyfound[3]
					return resetting
			self._trigger_reconnect = False
			self.logger.debug("Resetting {}: Deleted first entry of Send Commands. They are now: {}".format(
				self._name, self._send_commands))
			return resetting

		except Exception as err:
			self.logger.error(
				"Resetting {}: Problem resetting Item. Error: {}".format(self._name, err))
			return 'ERROR'

	# Resetting items if no connection available
	def _resetondisconnect(self, caller):
		if self._depend0_volume0 is True or self._depend0_power0 is True:
			self.logger.debug('Resetting {}: Starting to reset on disconnect. Called by {}'.format(self._name, caller))
			try:
				for zone in self._items:
					if 'power' in self._items[zone].keys() and self._depend0_power0 is True:
						self._items[zone]['power']['Value'] = 0
						for singleitem in self._items[zone]['power']['Item']:
							singleitem(0, 'AVDevice', self._tcp)
							self.logger.log(VERBOSE1, 'Resetting {}: Power to 0 for item {}'.format(self._name, singleitem))
					if 'speakers' in self._items[zone].keys() and self._depend0_power0 is True:
						self._items[zone]['speakers']['Value'] = 0
						for item in self._items_speakers[zone].keys():
							self._items_speakers[zone][item]['Value'] = 0
							for singleitem in self._items_speakers[zone][item]['Item']:
								singleitem(0, 'AVDevice', self._tcp)
								self.logger.log(VERBOSE1, 'Resetting {}: Speakers to 0 for item {}'.format(self._name, singleitem))
						for singleitem in self._items[zone]['speakers']['Item']:
							singleitem(0, 'AVDevice', self._tcp)
							self.logger.log(VERBOSE1, 'Resetting {}: Speakers to 0 for item {}'.format(self._name, singleitem))
					if 'volume' in self._items[zone].keys() and self._depend0_volume0 is True:
						self._items[zone]['volume']['Value'] = 0
						for singleitem in self._items[zone]['volume']['Item']:
							singleitem(0, 'AVDevice', self._tcp)
							self.logger.log(VERBOSE1, 'Resetting {}: Volume to 0 for item {}'.format(self._name, singleitem))
				self.logger.debug('Resetting {}: Done.'.format(self._name))
			except Exception as err:
				self.logger.warning('Resetting {}: Problem resetting Item. Error: {}'.format(self._name, err))
		else:
			self.logger.log(VERBOSE1, 'Resetting {}: Not resetting on disconnect because this feature is disabled in the plugin config.'.format(self._name))

	# Converting received values to bool, string or int to compare the responses with the expected response
	def _convertvalue(self, receivedvalue, expectedtype, invert):
		self.logger.debug("Converting Values {}: Received Value is: {} with expected type {}. Invert: {}".format(self._name, receivedvalue, expectedtype, invert))
		if 'bool' in expectedtype and not receivedvalue == '':
			try:
				if invert is True:
					if (int(receivedvalue) == 1 and len(str(receivedvalue)) <= 1):
						receivedvalue = False
					elif (int(receivedvalue) == 0 and len(str(receivedvalue)) <= 1):
						receivedvalue = True
					self.logger.log(VERBOSE1, "Converting Values {}: Receivedvalue {} reversed".format(self._name, receivedvalue))
				else:
					if (int(receivedvalue) == 1 and len(str(receivedvalue)) <= 1):
						receivedvalue = True
						self.logger.log(VERBOSE1, "Converting Values {}: Receivedvalue {} converted to bool.".format(self._name, receivedvalue))
					elif (int(receivedvalue) == 0 and len(str(receivedvalue)) <= 1):
						receivedvalue = False
						self.logger.log(VERBOSE1, "Converting Values {}: Receivedvalue {} converted to bool.".format(self._name, receivedvalue))
			except Exception as err:
				self.logger.log(VERBOSE2, "Converting Values {}: Receivedvalue {} not converted further. Message: {}.".format(self._name, receivedvalue, err))
				pass
		if 'bool' in expectedtype:
			try:
				if int(receivedvalue) == 1 and len(str(receivedvalue)) <= 1:
					receivedvalue = True
				elif int(receivedvalue) == 0 and len(str(receivedvalue)) <= 1:
					receivedvalue = False
			except Exception:
				pass
		if 'int' in expectedtype:
			try:
				if str(receivedvalue).lower() == 'on':
					receivedvalue = 1
				elif str(receivedvalue).lower() == 'off' or str(receivedvalue).lower() == 'standby':
					receivedvalue = 0
			except Exception:
				pass
		elif not (('bool' in expectedtype and 'int' in expectedtype) or ('str' in expectedtype and 'bool' in expectedtype)):
			try:
				if str(receivedvalue).lower() == 'on':
					receivedvalue = True
				elif str(receivedvalue).lower() == 'off' or str(receivedvalue).lower() == 'standby':
					receivedvalue = False
			except Exception:
				pass
		try:
			receivedvalue = eval(receivedvalue.lstrip('0'))
		except Exception:
			try:
				receivedvalue = eval(receivedvalue)
			except Exception:
				pass
		try:
			receivedvalue = float(receivedvalue) if '.' in receivedvalue else int(receivedvalue)
		except Exception:
			pass
		self.logger.debug("Converting Values {}: Received Value is now: {} with type {}.".format(self._name, receivedvalue, type(receivedvalue)))
		return receivedvalue

	# Store actual value to a temporary dict for resetting purposes
	def _write_itemsdict(self, data):
		try:
			self.logger.debug("Storing Values {}: Starting to store value for data {} in dictionary.".format(self._name, data))
			sorted_response_commands = sorted(self._response_commands, key=len, reverse=True)
			updated = 0
			for command in sorted_response_commands:
				self.logger.log(VERBOSE2, "Storing Values {}: Comparing command {}.".format(self._name, command))
				if data == command:
					self.logger.debug("Storing Values {}: Response is identical to expected response. Skipping Storing: {}".format(self._name, data))
					break
				for entry in self._response_commands[command]:
					self.logger.log(VERBOSE2, "Storing Values {}: Comparing entry {}.".format(self._name, entry))
					if entry[1] == entry[2]:
						commandstart = 0
						commandend = entry[2]
					else:
						commandstart = entry[0]
						commandend = entry[0] + entry[1]

					valuestart = entry[2]
					valueend = entry[2] + entry[0]
					function = entry[4]
					expectedtype = entry[7]

					if data[commandstart:commandend] == command:
						zone = entry[5]
						value = receivedvalue = data[valuestart:valueend]
						invert = True if entry[6].lower() in ['1', 'true', 'yes', 'on'] else False
						receivedvalue = self._convertvalue(value, expectedtype, invert)

						if isinstance(receivedvalue, eval(expectedtype)):
							self._items[zone][function]['Value'] = receivedvalue
							self.logger.debug("Storing Values {}: Found writeable dict key: {}. Zone: {}. Value {} with type {}. Function: {}.".format(self._name, command, zone, receivedvalue, expectedtype, function))
							updated = 1
							return self._items[zone][function], receivedvalue, expectedtype
							break
						else:
							self.logger.debug("Storing Values {}: Found writeable dict key: {} with type {}, but received value {} is type {}. Not writing value!".format(self._name, command, expectedtype, receivedvalue, type(receivedvalue)))
						if updated == 1:
							self.logger.log(VERBOSE1, "Storing Values {}: Stored all relevant items from function {}. step 1".format(self._name, function))
							break
					if updated == 1:
						self.logger.log(VERBOSE1, "Storing Values {}: Stored all relevant items from function {}. step 2".format(self._name, function))
						break
				if updated == 1:
					self.logger.log(VERBOSE1, "Storing Values {}: Stored all relevant items from function {}. step 3".format(self._name, function))
					break
		except Exception as err:
			self.logger.error("Storing Values {}: Problems creating items dictionary. Error: {}".format(self._name, err))
		finally:
			self.logger.log(VERBOSE1, "Storing Values {}: Finished. Send Commands: {}".format(self._name, self._send_commands))
			if updated == 1:
				return self._items[zone][function], receivedvalue, expectedtype
			else:
				return 'empty', 'empty', 'empty'

	# Finding relevant items for the plugin based on the avdevice keyword
	def parse_item(self, item):
		if self._tcp is not None or self._rs232 is not None:
			if self.has_iattr(item.conf, 'avdevice'):
				info = self.get_iattr_value(item.conf, 'avdevice')
				if (info is None):
					return None
				else:
					self._items['zone0'][info] = {'Item': [item], 'Value': item()}
					return self.update_item
			elif self.has_iattr(item.conf, 'avdevice_zone0'):
				info = self.get_iattr_value(item.conf, 'avdevice_zone0')
				if (info is None):
					return None
				else:
					self._items['zone0'][info] = {'Item': [item], 'Value': item()}
					return self.update_item
			elif self.has_iattr(item.conf, 'avdevice_zone1'):
				info = self.get_iattr_value(item.conf, 'avdevice_zone1')
				if (info is None):
					return None
				else:
					self._items['zone1'][info] = {'Item': [item], 'Value': item()}
					return self.update_item
			elif self.has_iattr(item.conf, 'avdevice_zone2'):
				info = self.get_iattr_value(item.conf, 'avdevice_zone2')
				if (info is None):
					return None
				else:
					self._items['zone2'][info] = {'Item': [item], 'Value': item()}
					return self.update_item
			elif self.has_iattr(item.conf, 'avdevice_zone3'):
				info = self.get_iattr_value(item.conf, 'avdevice_zone3')
				if (info is None):
					return None
				else:
					self._items['zone3'][info] = {'Item': [item], 'Value': item()}
					return self.update_item
			elif self.has_iattr(item.conf, 'avdevice_zone4'):
				info = self.get_iattr_value(item.conf, 'avdevice_zone4')
				if (info is None):
					return None
				else:
					self._items_['zone4'][info] = {'Item': [item], 'Value': item()}
					return self.update_item
			elif self.has_iattr(item.conf, 'avdevice_zone1_speakers'):
				info = self.get_iattr_value(item.conf, 'avdevice_zone1_speakers')
				if (info is None):
					return None
				else:
					self._items_speakers['zone1'][info] = {'Item': [item], 'Value': item()}
					return self.update_item
			elif self.has_iattr(item.conf, 'avdevice_zone2_speakers'):
				info = self.get_iattr_value(item.conf, 'avdevice_zone2_speakers')
				if (info is None):
					return None
				else:
					self._items_speakers['zone2'][info] = {'Item': [item], 'Value': item()}
					return self.update_item
			elif self.has_iattr(item.conf, 'avdevice_zone3_speakers'):
				info = self.get_iattr_value(item.conf, 'avdevice_zone3_speakers')
				if (info is None):
					return None
				else:
					self._items_speakers['zone3'][info] = {'Item': [item], 'Value': item()}
					return self.update_item
			elif str(item) == self._dependson:
				self._items['zone0']['dependson'] = {'Item': self._dependson, 'Value': self._dependson_value}
				self.logger.debug("Initializing {}: Dependson Item found: {}".format(self._name, item, self._dependson))
				return self.update_item
			else:
				return None
				self.logger.warning(
					"Parsing Items {}: No items parsed".format(self._name))

	# Processing the response from the AV device, dealing with buffers, etc.
	def _processing_response(self, socket):
		try:
			buffer = ''
			bufferlist = []
			tidy = lambda c: re.sub(
				r'(^\s*[\r\n]+|^\s*\Z)|(\s*\Z|\s*[\r\n]+)',
				lambda m: '\r\n' if m.lastindex == 2 else '',
				c)
			try:
				if self._rs232 and (socket == self._serialwrapper or socket == self._serial):
					if socket == self._serial:
						buffer = socket.readline().decode('utf-8')
					else:
						buffer = socket.read()
				if self._tcp and socket == self._tcpsocket:
					buffer = socket.recv(4096).decode('utf-8')
				buffering = False
				buffer = tidy(buffer)
				if not buffer == '' and (self._response_buffer is not False or self._response_buffer is not 0):
					buffering = True
				elif buffer == '' and not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup':
					self._resend_on_empty_counter += 1
					self._wait(0.1)
					sending = self._send(self._sendingcommand, 'responseprocess')
					self.logger.log(VERBOSE1, "Processing Response {}: Received empty response while sending command: {}. Return from send is {}. Retry: {}".format(self._name, self._sendingcommand, sending, self._resend_counter))
					if self._resend_on_empty_counter >= 2:
						self.logger.debug("Processing Response {}: Stop resending command {} and sending back error.".format(self._name, self._sendingcommand))
						self._resend_on_empty_counter = 0
						yield 'ERROR'

			except Exception as err:
				buffering = False
				try:
					if not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup' and not (self._sendingcommand.split(",")[2] == '' or self._sendingcommand.split(",")[2] == ' ' or self._sendingcommand.split(",")[2] == 'none'):
						buffering = True
						self.logger.log(VERBOSE1, "Processing Response {}: Error reading.. Error: {}. Sending Command: {}. RS232: {}, Host: {}, Socket: {}".format(self._name, err, self._sendingcommand, self._rs232, self._tcp, socket))
						if self._rs232 and (socket == self._serialwrapper or socket == self._serial):
							self.logger.log(VERBOSE1, "Processing Response {}: Problems buffering RS232 response. Error: {}. Increasing timeout temporarily.".format(self._name, err))
							self._wait(1)
							socket.timeout = 2
							sending = self._send(self._sendingcommand, 'getresponse')
							if socket == self._serial:
								buffer = socket.readline().decode('utf-8')
							else:
								buffer = socket.read()
							socket.timeout = 0.3
							self.logger.log(VERBOSE1, "Processing Response {}: Error reading.. Return from send is {}. Error: {}".format(self._name, sending, err))
						if self._tcp and socket == self._tcpsocket:
							self.logger.log(VERBOSE1, "Processing Response {}: Problems buffering TCP response. Error: {}. Increasing timeout temporarily.".format(self._name, err))
							self._wait(1)
							socket.settimeout(self._tcp_timeout * 3)
							sending = self._send(self._sendingcommand, 'getresponse')
							self.logger.debug("Processing Response {}: Error reading.. Return from send is {}. Error: {}".format(self._name, sending, err))
							buffer = socket.recv(4096).decode('utf-8')
							socket.settimeout(self._tcp_timeout)
				except Exception as err:
					buffering = False
					self.logger.error("Processing Response {}: Connection error. Error: {} Resend Counter: {}. Resend Max: {}".format(
						self._name, err, self._resend_counter, self._resend_retries))
					yield 'ERROR'

			while buffering:
				if '\r\n' in buffer:
					self.logger.log(VERBOSE2, "Processing Response {}: Buffer before removing duplicates: {}".format(self._name, re.sub('[\r\n]', ' ', buffer)))
					# remove duplicates
					buffer = '\r\n'.join(sorted(set(buffer.split('\r\n')), key=buffer.split('\r\n').index))
					(line, buffer) = buffer.split("\r\n", 1)
					self.logger.log(VERBOSE2, "Processing Response {}: \r\nBuffer: {} Line: {}. Response buffer: {}, force buffer: {}".format(self._name, buffer, line, self._response_buffer, self._force_buffer))
					if not ('' in self._force_buffer and len(self._force_buffer) == 1) and (self._response_buffer is False or self._response_buffer == 0):
						if not re.sub('[ ]', '', buffer) == '' and not re.sub('[ ]', '', line) == '':
							bufferlist = []
							for buf in self._force_buffer:
								try:
									if buf in buffer and not buf.startswith(tuple(self._ignore_response)) and '' not in self._ignore_response:
										start = buffer.index(buf)
										self.logger.log(VERBOSE2, "Processing Response {}: Testing forcebuffer {}. Bufferlist: {}. Start: {}".format(self._name, buf, bufferlist, start))
										if not buffer.find('\r\n', start) == -1:
											end = buffer.index('\r\n', start)
											if not buffer[start:end] in bufferlist and not buffer[start:end] in line:
												bufferlist.append(buffer[start:end])
										else:
											if not buffer[start:] in bufferlist and not buffer[start:] in line:
												bufferlist.append(buffer[start:])
										self.logger.debug("Processing Response {}: Forcebuffer {} FOUND in buffer. Bufferlist: {}. Buffer: {}".format(
											self._name, buf, bufferlist, buffer))
								except Exception as err:
									self.logger.warning("Processing Response {}: Problems while buffering. Error: {}".format(self._name, err))
							if bufferlist:
								buffer = '\r\n'.join(bufferlist)
								buffer = tidy(buffer)
							else:
								self.logger.log(VERBOSE2, "Processing Response {}: No forced buffer found.".format(self._name))
					# Delete consecutive duplicates
					# buffer = '\r\n'.join([x[0] for x in groupby(buffer.split('\r\n'))])

					if '{}\r\n'.format(line) == buffer:
						buffer = ''
						self.logger.log(VERBOSE1, "Processing Response {}: Clearing buffer because it's the same as Line: {}".format(self._name, line))
					line = re.sub('[\\n\\r]', '', line).strip()
					if not line.startswith(tuple(self._response_commands)) and line not in self._error_response:
						self.logger.log(VERBOSE1, "Processing Response {}: Response {} is not in possible responses for items. Sending Command: {}".format(self._name, line, self._sendingcommand))
					elif line in self._error_response and '' not in self._error_response:
						self.logger.debug("Processing Response {}: Response {} is in Error responses.".format(self._name, line))
						yield "{}".format(line)
					elif line.startswith(tuple(self._ignore_response)) and '' not in self._ignore_response:
						try:
							compare = self._send_commands[0].split(",")[2].split("|")
							for comp in compare:
								if line.startswith(comp):
									keyfound = True
								else:
									keyfound = False
							if keyfound is True:
								self.logger.log(VERBOSE1, "ERROR Processing Response {}: Sending Command: {} Keep command {}".format(self._name, self._send_commands, self._keep_commands))
								for entry in self._keep_commands:
									if self._send_commands[0] in self._keep_commands.get(entry):
										self._keep_commands.pop(entry)
										self.logger.log(VERBOSE1, "ERROR Processing Response {}: Removed Keep command {} from {} because command sent successfully".format(
											self._name, entry, self._keep_commands))
										break
								self._send_commands.pop(0)
								self._sendingcommand = 'done'
								self.logger.debug("Processing Response {}: Response {} is same as expected {} and defined as response to be ignored. Removing command from send list. It is now: {}. Ignore responses are: {}".format(
									self._name, line, compare, self._send_commands, self._ignore_response))
								sending = self._send('command', 'commandremoval')
						except Exception as err:
							self.logger.log(VERBOSE2, "Processing Response {}: Response {} is ignored. Command list is now: {}. Message: {}".format(self._name, line, self._send_commands, err))
					elif not line.startswith(tuple(self._ignore_response)) and line.startswith(self._special_commands['Display']['Command']) and \
							self._response_buffer is not False and '' not in self._ignore_response and not self._special_commands['Display']['Command'] == '':
						self.logger.log(VERBOSE1, "Processing Response {}: Detected Display info {}. buffer: \r\n{}".format(self._name, line, buffer))
						buffering = False
						buffer += '\r\n{}\r\n'.format(line)
						buffer = tidy(buffer)
						self.logger.log(VERBOSE1, "Processing Response {}: Append Display info {} to buffer: \r\n{}".format(self._name, line, buffer))
					else:
						if self._response_buffer is False and not buffer.startswith(tuple(self._force_buffer)) and '' not in self._force_buffer:
							buffering = False
							self.logger.log(VERBOSE1, "Processing Response {}: Clearing buffer: {}".format(self._name, buffer))
							buffer = '\r\n'
						self.logger.log(VERBOSE1, "Processing Response {}: Sending back line: {}. Display Command: {}".format(
							self._name, line, self._special_commands['Display']['Command']))
						yield "{}".format(line)
				else:
					try:
						if self._rs232 and (socket == self._serialwrapper or socket == self._serial):
							if socket == self._serial:
								more = socket.readline().decode('utf-8')
							else:
								more = socket.read()
						if self._tcp and socket == self._tcp:
							more = socket.recv(4096).decode('utf-8')
						morelist = more.split("\r\n")
						if buffer.find('\r\n') == -1 and len(buffer) > 0:
							buffer += '\r\n'
						buffer += '\r\n'.join([x[0] for x in groupby(morelist)])
					except Exception as err:
						buffering = False
					finally:
						buffering = False
						self.logger.log(VERBOSE1, "Processing Response {}: Buffering false.".format(self._name))

			if not buffer == '\r\n' and self._response_buffer is True or type(self._response_buffer) is int:
				buffer = tidy(buffer)
				bufferlist = buffer.split('\r\n')
				# Removing everything except last x lines
				maximum = abs(self._response_buffer) if type(self._response_buffer) is int else 11
				multiplier = 1 if self._response_buffer >= 0 else -1
				while '' in bufferlist:
					bufferlist.remove('')
				newbuffer = []
				for buf in bufferlist:
					if not buf.startswith(tuple(self._ignore_response)) and '' not in self._ignore_response and buf.startswith(tuple(self._response_commands)):
						newbuffer.append(buf)
				bufferlist = newbuffer[-1 * max(min(len(newbuffer), maximum), 0):]

				if len(bufferlist) > 1:
					self.logger.log(VERBOSE1, "Bufferlist after: {}".format(bufferlist))
				buffering = False
				for buf in bufferlist:
					if not re.sub('[ ]', '', buf) == '' and not buf.startswith(tuple(self._ignore_response)) and '' not in self._ignore_response:
						self.logger.log(VERBOSE1, "Processing Response {}: Sending back {} from buffer because Responsebuffer is activated.".format(self._name, buf))
						self._wait(0.2)
						yield buf

			elif not buffer == '\r\n':
				buffer = tidy(buffer)
				bufferlist = buffer.split('\r\n')
				# Removing everything except last x lines
				maximum = abs(self._response_buffer) if type(self._response_buffer) is int else 11
				multiplier = 1 if self._response_buffer >= 0 else -1
				bufferlist = bufferlist[multiplier * max(min(len(bufferlist), maximum), 0):]
				buffering = False
				for buf in bufferlist:
					if not re.sub('[ ]', '', buf) == '' and not buf.startswith(tuple(self._ignore_response)) and '' not in self._ignore_response:
						self.logger.debug("Processing Response {}: Sending back {} from filtered buffer: {}.".format(self._name, buf, buffer))
						self._wait(0.2)
						yield buf
		except Exception as err:
			self.logger.error("Processing Response {}: Problems occured. Message: {}".format(self._name, err))

	# Run function
	def run(self):
		if self._tcp is None and self._rs232 is None:
			self.logger.error("Initializing {}: Neither IP address nor RS232 port given. Not running.".format(self._name))
		else:
			self._functions, self._number_of_zones = self.init._read_commandfile()
			self._items = self.init._addstatusupdate()
			self._response_commands, self._special_commands = self.init._create_responsecommands()
			self._power_commands = self.init._create_powercommands()
			self._query_commands, self._query_zonecommands = self.init._create_querycommands()
			self.logger.log(VERBOSE1, "Initializing {}: Functions: {}, Number of Zones: {}".format(self._name, self._functions, self._number_of_zones))
			self.logger.log(VERBOSE1, "Initializing {}: Responsecommands: {}.".format(self._name, self._response_commands))
			self.logger.log(VERBOSE1, "Initializing {}: Special Commands: {}".format(self._name, self._special_commands))
			self.logger.log(VERBOSE1, "Initializing {}: Powercommands: {}".format(self._name, self._power_commands))
			self.logger.log(VERBOSE1, "Initializing {}: Querycommands: {}, Query Zone: {}".format(self._name, self._query_commands, self._query_zonecommands))
			self.logger.log(VERBOSE1, "Initializing {}: Items: {}".format(self._name, self._items))
			self.logger.log(VERBOSE1, "Initializing {}: Speaker Items: {}".format(self._name, self._items_speakers))
			self.logger.log(VERBOSE1, "Initializing {}: done".format(self._name))

			try:
				try:
					self._dependson = self._sh.return_item(self._dependson)
					self.logger.debug("Initializing {}: Dependson Item: {}.".format(self._name, self._dependson))
				except Exception:
					self._dependson = None
					self.logger.warning("Initializing {}: Dependson Item {} is no valid item.".format(self._name, self._dependson))
				self.logger.debug("Initializing {}: Running".format(self._name))
				self.alive = True
				if 'statusupdate' not in self._items['zone0'].keys():
					self._items['zone0']['statusupdate'] = {'Item': ['self._statusupdate'], 'Value': False}
					self.logger.debug("Initializing {}: No statusupdate Item set, creating dummy item.".format(self._name))
			except Exception as err:
				self.logger.error("Initializing {}: Problem running and creating items. Error: {}".format(self._name, err))
			finally:
				if self._tcp is not None or self._rs232 is not None:
					self.connect('run')

	# Triggering TCP or RS232 connection schedulers
	def connect(self, trigger):
		self._trigger_reconnect = True
		if self._is_connected == []:
			self._parsinginput = []
			self._is_connected.append('Connecting')
		self.logger.log(VERBOSE1, "Connecting {}: Starting to connect. Triggered by {}. Current Connections: {}".format(self._name, trigger, self._is_connected))
		try:
			dependsvalue = self._dependson()
			if dependsvalue == self._dependson_value:
				depending = False
			else:
				depending = True
				self._is_connected = []
				self._parsinginput = []
			self.logger.debug("Connecting {}: Connection depends on {}. It's value is {}, has to be {}. Connections are {}".format(self._name, self._dependson, dependsvalue, self._dependson_value, self._is_connected))
		except Exception as e:
			depending = False
			self.logger.log(VERBOSE1, "Connecting {}: Depending is false. Message: {}".format(self._name, e))
		finally:
			if depending is False:
				if self._tcp is not None and 'TCP' not in self._is_connected:
					self.logger.log(VERBOSE1, "Connecting {}: Starting TCP scheduler".format(self._name))
					self._sh.scheduler.add('avdevice-tcp-reconnect', self.connect_tcp, cycle=7)
					self._sh.scheduler.change('avdevice-tcp-reconnect', active=True)
					self._sh.scheduler.trigger('avdevice-tcp-reconnect')
					self._trigger_reconnect = False
				if self._rs232 is not None and 'Serial' not in self._is_connected:
					self.logger.log(VERBOSE1, "Connecting {}: Starting RS232 scheduler".format(self._name))
					self._sh.scheduler.add('avdevice-serial-reconnect', self.connect_serial, cycle=7)
					self._sh.scheduler.change('avdevice-serial-reconnect', active=True)
					self._sh.scheduler.trigger('avdevice-serial-reconnect')
					self._trigger_reconnect = False

	# Connect to TCP IP
	def connect_tcp(self):
		try:
			if self._tcp is not None and 'TCP' not in self._is_connected:
				self.logger.log(VERBOSE1, "Connecting TCP {}: Starting to connect to {}.".format(self._name, self._tcp))
				self._tcpsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				self._tcpsocket.setblocking(0)
				self._tcpsocket.settimeout(6)
				self._tcpsocket.connect(('{}'.format(self._tcp), int(self._port)))
				self._tcpsocket.settimeout(self._tcp_timeout)
				self._is_connected.append('TCP')
				try:
					self._is_connected.remove('Connecting')
				except Exception:
					pass
				self.logger.info("Connecting TCP {}: Connected to {}:{}".format(
					self._name, self._tcp, self._port))

		except Exception as err:
			if 'TCP' in self._is_connected:
				self._is_connected.remove('TCP')
			self.logger.warning("Connecting TCP {}: Could not connect to {}:{}. Error:{}. Counter: {}/{}".format(
				self._name, self._tcp, self._port, err, self._reconnect_counter, self._reconnect_retries))

		finally:
			if ('TCP' not in self._is_connected and self._tcp is not None) and str(self._auto_reconnect).lower() in ['1', 'yes', 'true', 'on']:
				self._trigger_reconnect = False
				self.logger.warning("Connecting TCP {}: Reconnecting. Command list while connecting: {}.".format(
					self._name, self._send_commands))
			elif ('TCP' in self._is_connected and self._tcp is not None) or self._reconnect_counter >= self._reconnect_retries:
				self._sh.scheduler.change('avdevice-tcp-reconnect', active=False)
				self._reconnect_counter = 0
				self._trigger_reconnect = True
				self._addkeepcommands('connect_tcp', 'all')
				self.logger.debug("Connecting TCP {}: Deactivating reconnect scheduler. Command list while connecting: {}. Keep Commands: {}".format(
					self._name, self._send_commands, self._keep_commands))
			self._reconnect_counter += 1
			if 'TCP' in self._is_connected:
				self.logger.debug("Connecting TCP {}: TCP is connected.".format(self._name))
				if self._parsinginput == []:
					self.logger.debug("Connecting TCP {}: Starting Parse Input.".format(self._name))
					self._parse_input_init('tcpconnect')

	# Connect to RS232
	def connect_serial(self):
		try:
			if self._rs232 is not None and 'Serial' not in self._is_connected:
				ser = serial.serial_for_url('{}'.format(self._rs232), baudrate=int(self._baud), timeout=float(self._timeout), write_timeout=float(self._timeout))
				i = 0
				try:
					command = self._power_commands[0].split(',')[1]
					self.logger.debug("Connecting Serial {}: Starting to connect to {} with init command {}.".format(self._name, self._rs232, command))
				except Exception as err:
					self.logger.warning("Connecting Serial {}: No power commands found. Please check your config files!".format(self._name))
					command = '?P'
				while ser.in_waiting == 0:
					i += 1
					self._wait(1)
					ser.write(bytes('{}\r'.format(command), 'utf-8'))
					buffer = bytes()
					buffer = ser.read().decode('utf-8')
					self.logger.log(VERBOSE1, "Connecting Serial {}:  Buffer: {}. Reconnecting Retry: {}.".format(self._name, buffer, i))
					if i >= 4:
						ser.close()
						self.logger.log(VERBOSE1, "Connecting Serial {}:  Ran through several retries.".format(self._name))
						break
				if ser.isOpen():
					self._serialwrapper = io.TextIOWrapper(io.BufferedRWPair(ser, ser), newline='\r\n', encoding='utf-8', line_buffering=True, write_through=True)
					self._serialwrapper.timeout = 0.1
					self._serial = ser
					self._trigger_reconnect = False
					if 'Serial' not in self._is_connected:
						self._is_connected.append('Serial')
					try:
						self._is_connected.remove('Connecting')
					except Exception:
						pass
					self.logger.info("Connecting Serial {}: Connected to {} with baudrate {}.".format(
						self._name, ser, self._baud))
				else:
					self.logger.warning("Connecting Serial {}: Serial port is not open. Connection status: {}. Reconnect Counter: {}".format(self._name, self._is_connected, self._reconnect_counter))
		except Exception as err:
			if 'Serial' in self._is_connected:
				self._is_connected.remove('Serial')
			self.logger.warning("Connecting Serial {}: Could not connect to {}, baudrate {}. Error:{}, Counter: {}/{}".format(
				self._name, self._rs232, self._baud, err, self._reconnect_counter, self._reconnect_retries))

		finally:
			if ('Serial' not in self._is_connected and self._rs232 is not None) and str(self._auto_reconnect).lower() in ['1', 'yes', 'true', 'on']:
				self._trigger_reconnect = False
				self.logger.log(VERBOSE1, "Connecting Serial {}: Activating reconnect scheduler. Command list while connecting: {}.".format(
					self._name, self._send_commands))
			elif ('Serial' in self._is_connected and self._rs232 is not None) or self._reconnect_counter >= self._reconnect_retries:
				self._sh.scheduler.change('avdevice-serial-reconnect', active=False)
				self._reconnect_counter = 0
				self._trigger_reconnect = True
				self._addkeepcommands('connect_serial', 'all')
				self.logger.debug("Connecting Serial {}: Deactivating reconnect scheduler. Command list while connecting: {}. Keep commands: {}".format(
					self._name, self._send_commands, self._keep_commands))
			self._reconnect_counter += 1
			if 'Serial' in self._is_connected:
				self.logger.debug("Connecting Serial {}: Serial is connected.".format(self._name))
				if self._parsinginput == []:
					self.logger.debug("Connecting Serial {}: Starting Parse Input.".format(self._name))
					self._parse_input_init('serialconnect')

	# Updating Status even if no statusupdate is defined in device text file
	def _statusupdate(self, value, trigger, caller):
		self.logger.debug("Statusupdate {}: Value: {}. Trigger from {}. Caller: {}".format(self._name, value, trigger, caller))
		self.update_item('statusupdate', 'Init')

	# Adding Keep Commands to Send Commands
	def _addkeepcommands(self, trigger, zone):
		self.logger.log(VERBOSE1, "Keep Commands {}: Trigger from {} for zone {}. Send Commands: {}".format(self._name, trigger, zone, self._send_commands))
		keeptemp = []
		for zeit in self._keep_commands:
			keeping = False
			if time.time() - zeit <= self._secondstokeep and not self._keep_commands[zeit] in keeptemp:
				try:
				    for item in self._query_zonecommands['{}'.format(zone)]:
					    if item.split(',')[1] == self._keep_commands[zeit].split(',')[1]:
						    keeping = True
				except:
				    self.logger.log(VERBOSE2, "Keep Commands {}: Zone is set to all.".format(self._name))
				if zone == 'all' or keeping == True or trigger == 'powercommand':
					keeping = True
					keeptemp.append(self._keep_commands[zeit])
			self.logger.debug("Keep Commands {}: Age {}s of command {}. Secondstokeep: {}. Keeping command: {}".format(
				self._name.lower(), int(time.time() - zeit), self._keep_commands[zeit], self._secondstokeep, keeping))
		self._send_commands = self._send_commands + list(set(keeptemp))
		seen = set()
		self._send_commands = [x for x in self._send_commands if x not in seen and not seen.add(x)]
		self._keep_commands = {}
		keeptemp = []

	# Parsing the response and comparing it with expected response
	def _parse_input_init(self, trigger):
		if not self._is_connected == [] and not self._is_connected == ['Connecting']:
			self._parsinginput.append(trigger)
		else:
			self._parsinginput = []
		self.logger.log(VERBOSE1, "Parsing Input {}: Init Triggerd by these functions so far: {}".format(self._name, self._parsinginput))
		if trigger == 'tcpconnect' or trigger == 'serialconnect':
			try:
				eval(self._items['zone0']['statusupdate']['Item'][0])(1, 'Init', self._tcp)
				self.logger.debug("Parsing Input {}: Updated Item after connection: {} with value 1. Commandlist: {}".format(
					self._name, self._items['zone0']['statusupdate']['Item'][0], self._send_commands))
			except Exception:
				try:
					self._items['zone0']['statusupdate']['Item'][0](1, 'Init', self._tcp)
					self.logger.debug("Parsing Input {}: Updated Item after connection: {} with value 1. Commandlist: {}".format(
						self._name, self._items['zone0']['statusupdate']['Item'][0], self._send_commands))
				except Exception as err:
					self.logger.log(VERBOSE1, "Parsing Input {}: No statusupdate defined, not querying status after {}. Message: {}".format(self._name, trigger, err))
		if len(self._parsinginput) == 1:
			self._parse_input(trigger)

	# Parsing the response and comparing it with expected response
	def _parse_input(self, trigger):
		self.logger.log(VERBOSE1, "Parsing Input {}: Triggerd by {}".format(self._name, trigger))
		def _duplicateindex(seq,item):
			start_at = -1
			locs = []
			while True:
				try:
					loc = seq.index(item,start_at+1)
				except ValueError:
					break
				else:
					locs.append(loc)
					start_at = loc
			return locs

		while self.alive and not self._parsinginput == [] and not self._is_connected == [] and not self._is_connected == ['Connecting']:
			connectionproblem = False
			if not self._sendingcommand == '' and not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup':
				self.logger.log(VERBOSE1, "Parsing Input {}: Starting to parse input. Alive: {}. Connected: {}. Parsinginput: {}. Sendcommand: {}".format(
					self._name, self.alive, self._is_connected, self._parsinginput, self._sendingcommand))
			to_send = 'command'
			try:
				data = 'waiting'
				databuffer = []
				if 'Serial' in self._is_connected:
					try:
						databuffer = self._processing_response(self._serialwrapper)
					except Exception as err:
						self.logger.error("Parsing Input {}: Problem receiving Serial data {}.".format(self._name, err))
				elif 'TCP' in self._is_connected:
					try:
						databuffer = self._processing_response(self._tcpsocket)
					except Exception as err:
						self.logger.error("Parsing Input {}: Problem receiving TCP data {}.".format(self._name, err))
				for data in databuffer:
					data = data.strip()
					if data == '' and not self._sendingcommand == '' and not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup':
						self.logger.log(VERBOSE1, "Parsing Input {}: Problem with empty response.".format(self._name))
					if data == 'ERROR' and not self._sendingcommand == 'gaveup' and not self._sendingcommand == 'done':
						if self._resend_counter >= self._resend_retries:
							self.logger.warning("Parsing Input {}: Giving up Sending {} and removing from list. Received Data: {}. Original Commandlist: {}".format(
								self._name, self._sendingcommand, data, self._send_commands))
							self._resend_counter = 0
							self.logger.log(VERBOSE1, "Parsing Input {}: Resetting Resend Counter because maximum retries exceeded.".format(self._name))
							# Resetting Item if Send not successful
							if self._reset_onerror is True:
								self._resetitem()
							try:
								if self._send_commands[0] not in self._query_commands and not self._send_commands[0] in self._special_commands['Display']['Command']:
									self._keep_commands[time.time()] = self._send_commands[0]
									self.logger.debug("Parsing Input {}: Removing item from send command, storing in keep commands: {}.".format(self._name, self._keep_commands))
								elif self._send_commands[0] in self._query_commands:
									self.logger.warning("Parsing Input {}: Giving up {}, because no answer received 1.".format(self._name, self._sendingcommand))
								self._send_commands.pop(0)
								if not self._send_commands == []:
									sending = self._send('command', 'parseinput')
									self.logger.log(VERBOSE1, "Parsing Input {}: Command List is now: {}. Sending return is {}.".format(
										self._name, self._send_commands, sending))
							except Exception as err:
								self.logger.debug("Parsing Input {}: Nothing to remove from Send Command List. Error: {}".format(self._name, err))
							self._sendingcommand = 'gaveup'
							if self._trigger_reconnect is True:
								self.logger.log(VERBOSE1, "Parsing Input {}: Trying to connect while parsing item".format(self._name))
								self.connect('parse_input')


					sorted_response_commands = sorted(self._response_commands, key=len, reverse=True)
					self.logger.debug("Parsing Input {}: Response: {}.".format(self._name, data))
					if not self._send_commands == []:
						expectedresponse = []
						try:
							for response in self._send_commands:
								if not response.split(",")[2] == '':
									expectedresponse.append(response.split(",")[2])
							self.logger.debug("Parsing Input {}: Expected response while parsing: {}.".format(self._name, expectedresponse))
						except Exception as err:
							self.logger.error("Parsing Input {}: Problems creating expected response list. Error: {}".format(self._name, err))
						self.logger.log(VERBOSE1, "Parsing Input {}: Parsing input while waiting for response {}.".format(self._name, expectedresponse))
						try:
							to_send = 'command'
							updatedcommands = []
							runthrough = []
							if not expectedresponse == []:
								for expected in expectedresponse:
									if expected not in runthrough:
										runthrough.append(expected)
										found = []
										expectedlist = expected.split("|")
										try:
											for expectedpart in expectedlist:
												try:
													datalength = self._response_commands[expectedpart][0][1]
													if data[:datalength].startswith(expectedpart) and len(data[:datalength]) == len(expectedpart):
														found.append(expectedpart)
														self.logger.log(VERBOSE1, "Parsing Input {}: Expected response edited: {}.".format(self._name, found))
												except Exception as err:
													found.append(expectedpart)
													self.logger.log(VERBOSE1, "Parsing Input {}: Expected response edited: {}. Message: {}".format(self._name, found, err))
										except Exception as err:
											found.append(expected)
											self.logger.debug("Parsing Input {}: Expected response after exception: {}. Problem: {}".format(self._name, found, err))
										try:
											valuetype = 'empty'
											if data.startswith(tuple(found)):
												entry, value, valuetype = self._write_itemsdict(data)
												self._sendingcommand = 'done'
												self._resend_counter = 0
												self.logger.log(VERBOSE1, "Parsing Input {}: Resetting Resend Counter because data is same as expected.".format(self._name))
												self.logger.log(VERBOSE1, "Parsing Input {}: Data {} found in {}. Entry: {}, Value: {}. Expected Type: {}".format(self._name, data, found, entry, value, valuetype))
											elif expectedlist[0] == '' or expectedlist[0] == ' ' or expectedlist[0] == 'none':
												self._sendingcommand = 'done'
												self._resend_counter = 0
												self.logger.log(VERBOSE1, "Parsing Input {}: No response expected. Resend Counter reset.".format(self._name))
											elif expectedlist[0].lower() == 'string':
												value = data
												self.logger.log(VERBOSE1, "Parsing Input {}: String found and testing... ".format(self._name))
												if value.startswith(tuple(self._response_commands.keys())):
													self.logger.log(
														VERBOSE1, "Parsing Input {}: Found string but ignored because it is a legit response for another command.".format(self._name))
												else:
													entry, value, valuetype = self._write_itemsdict(data)
													self.logger.debug("Parsing Input {}: String FOUND. Written to dict: {}. Resend Counter reset.".format(self._name, entry))
													self._sendingcommand = 'done'
													self._resend_counter = 0

											expectedindices = _duplicateindex(expectedresponse, expected)
											for expectedindex in expectedindices:
												if self._send_commands[expectedindex] not in updatedcommands:
													expectedtype = self._send_commands[expectedindex].split(',')
													try:
														expectedtype[3:] = [','.join(expectedtype[3:])]
														testvalue = expectedtype[3]
													except Exception:
														testvalue = ''
													if not valuetype == testvalue:
														updatedcommands.append(self._send_commands[expectedindex])
														self.logger.log(VERBOSE2, "Parsing Input {}: Test Value {} of {} is not same as Valuetype: {}. Adding to Sendcommands again.".format(
															self._name, testvalue, self._send_commands[expectedindex], valuetype))
													else:
														self.logger.log(VERBOSE1, "Parsing Input {}: Test Value {} of {} is same as Valuetype: {}. Not adding to Sendcommands again.".format(
															self._name, testvalue, self._send_commands[expectedindex], valuetype))
										except Exception as err:
											self.logger.log(VERBOSE1, "Parsing Input {}: Write to dict problems: {}".format(self._name, err))

								self.logger.log(VERBOSE2, "Parsing Input {}: Updated Command list {}.".format(self._name, updatedcommands))
							self._send_commands = updatedcommands
							self.logger.log(VERBOSE1, "Parsing Input {}: Sendcommands: {}. Sendingcommand: {}".format(self._name, self._send_commands, self._sendingcommand))
							if not self._send_commands == [] and not self._sendingcommand == 'done':
								self._resend_counter += 1
								try:
									dependsvalue = self._dependson()
									self.logger.debug("Parsing Input {}: Parsing depends on {}. It's value is {}, has to be {}.".format(self._name, self._dependson, dependsvalue, self._dependson_value))
									if dependsvalue == self._dependson_value:
										depending = False
									else:
										depending = True
										if self._depend0_volume0 is True or self._depend0_power0 is True:
											self._resetondisconnect('parseinput')
								except Exception as err:
									depending = False
									self.logger.log(VERBOSE1, "Parsing Input {}: Depending is false. Message {}.".format(self._name, err))
								if self._resend_counter >= self._resend_retries:
									self._resend_counter = 0
									self.logger.log(VERBOSE1, "Parsing Input {}: Resetting Resend Counter because maximum retries exceeded.".format(self._name))
									if not self._send_commands[0] in self._query_commands and not self._send_commands == []:
										self._sendingcommand = self._send_commands[0]
										self.logger.warning("Parsing Input {}: Going to reset item {}.".format(self._name, self._sendingcommand))
										self._resetitem()
									temp_sendcommand = self._sendingcommand
									self._sendingcommand = 'gaveup'
									if data == 'ERROR':
										connectionproblem = True
									else:
										connectionproblem = False

									if self._send_commands[0] not in self._query_commands and not self._send_commands[0] in self._special_commands['Display']['Command']:
										self._keep_commands[time.time()] = self._send_commands[0]
										self.logger.debug("Parsing Input {}: Removing item from send command, storing in keep commands: {}.".format(self._name, self._keep_commands))
									elif self._send_commands[0] in self._query_commands:
										self.logger.warning("Parsing Input {}: Giving up {}, because no answer received.".format(self._name, temp_sendcommand))
									self._send_commands.pop(0)
									self.logger.log(VERBOSE1, "Parsing Input {}: Send commands are now: {}".format(self._name, self._send_commands))
								elif depending is True:
									self._resend_counter = 0
									self.logger.log(VERBOSE1, "Parsing Input {}: Resetting Resend Counter because dependency not fulfilled.".format(self._name))
									try:
										if not self._send_commands[0] in self._query_commands and not self._send_commands == []:
											self._sendingcommand = self._send_commands[0]
											self.logger.warning("Parsing Input {}: Reset item {} because dependency not fulfilled.".format(self._name, self._sendingcommand))
											self._resetitem()
										self._sendingcommand = 'gaveup'
										if self._send_commands[0] not in self._query_commands and not self._send_commands[0] in self._special_commands['Display']['Command'] and not self._sendingcommand == 'gaveup':
											self._keep_commands[time.time()] = self._send_commands[0]
											self.logger.debug("Parsing Input {}: Removing item from send command, storing in keep commands: {}.".format(self._name, self._keep_commands))
										elif self._send_commands[0] in self._query_commands:
											self.logger.debug("Parsing Input {}: Giving	 up {}, because no answer received.".format(self._name, self._sendingcommand))
										self._send_commands.pop(0)
										self.logger.log(VERBOSE1, "Parsing Input {}: Keepcommands: {}. Sendcommands: {}".format(
											self._name, self._keep_commands, self._send_commands))
									except Exception as err:
										self.logger.log(VERBOSE1, "Parsing Input {}: Nothing to reset as send commands is empty: {}. Message: {}".format(self._name, self._send_commands, err))
								if not self._sendingcommand == 'gaveup':
									to_send = 'query' if (self._resend_counter % 2 == 1 and not self._send_commands[0].split(',')[1] == '') else 'command'
									self.logger.debug("Parsing Input {}: Requesting {} from {} because response was {}. Resend Counter: {}".format(
										self._name, to_send, self._send_commands[0], data, self._resend_counter))
									self._wait(self._resend_wait)
						except Exception as err:
							self.logger.warning("Parsing Input {}: Problems with checking for expected response. Error: {}".format(self._name, err))

					updated = 0
					if not data == 'ERROR' and data not in self._error_response:
						self.logger.log(VERBOSE1, "Parsing Input {}: Starting to compare values for data {}.".format(self._name, data))
						for key in sorted_response_commands:
							self.logger.log(VERBOSE2, "Parsing Input {}: Starting to compare values for data {} with key: {}.".format(self._name, data, key))
							if data == key:
								tempcommands = []
								for entry in self._send_commands:
									if key not in entry:
										tempcommands.append(entry)
								self._send_commands = tempcommands
								if self._sendingcommand not in self._send_commands and not self._send_commands == []:
									self._sendingcommand = self._send_commands[0]
								self.logger.debug("Parsing Input {}: Response is identical to expected response. Cleaned Send Commands: {}".format(self._name, self._send_commands))
								break
							else:
								for entry in self._response_commands[key]:
									commandlength = entry[1]
									valuelength = entry[0]
									item = entry[3]
									expectedtype = entry[7]
									index = data.find(key)
									self.logger.log(VERBOSE2, "Parsing Input {}: Entry: {}, Valuelength: {}, Expected Type: {}. ".format(
										self._name, entry, valuelength, expectedtype))
									if not index == -1:
										sametype = False
										inputcommands = self._special_commands['Input']['Command']
										function = entry[4]
										zone = entry[5]
										if data.startswith(self._special_commands['Display']['Command']) and not self._special_commands['Display']['Command'] == '':
											self.logger.debug("Parsing Input {}: Displaycommand found in response {}.".format(self._name, data))
											try:
												content = data[2:][:28]
												self.logger.log(VERBOSE1, "AVDevice {}: Display Data {}. Item: {}".format(self._name, content, item))
												tempvalue = "".join(
													list(map(lambda i: chr(int(content[2 * i:][: 2], 0x10)), range(14)))).strip()
												receivedvalue = re.sub(r'^[^A-Z0-9]*', '', tempvalue)
												self.logger.debug("AVDevice {}: Display Output {}".format(self._name, receivedvalue))
											except Exception as err:
												self.logger.warning("AVDevice {}: Problems getting display info. Error: {}".format(self._name, err))

										elif data.startswith(tuple(self._special_commands['Nowplaying']['Command'])) and not self._special_commands['Nowplaying']['Command'] == '':
											self.logger.debug("AVDevice {}: Now playing info found in response {}.".format(self._name, data))
											try:
												m = re.search('"(.+?)"', data)
												if m:
													receivedvalue = m.group(1)
												else:
													receivedvalue = ''
											except Exception as err:
												self.logger.debug("AVDevice {}: Problems reading Now Playing info. Error:{}".format(self._name, err))
										elif data.startswith(tuple(self._special_commands['Speakers']['Command'])) and not self._special_commands['Speakers']['Command'] == '':
											self.logger.debug("AVDevice {}: Speakers info found in response {}. Command: {}".format(
												self._name, data, self._special_commands['Speakers']['Command']))
											receivedvalue = self._convertvalue(data[index + commandlength:index + commandlength + valuelength], expectedtype, False)
											try:
												for speakercommand in self._special_commands['Speakers']['Command']:
													for zone in self._items_speakers:
														for speakerlist in self._items_speakers[zone]:
															speakerAB = sum(map(int, self._items_speakers[zone].keys()))
															self.logger.debug("AVDevice {}: Received value: {}. Speaker {}. SpeakerAB: {}".format(
																self._name, receivedvalue, speakerlist, speakerAB))
															if receivedvalue == int(speakerlist) or receivedvalue == speakerAB:
																for speaker in self._items_speakers[zone][speakerlist]['Item']:
																	self.logger.info("AVDevice {}: Speaker {} is on.".format(self._name, speaker))
																	speaker(1, 'AVDevice', self._tcp)
															else:
																for speaker in self._items_speakers[zone][speakerlist]['Item']:
																	self.logger.info("AVDevice {}: Speaker {} is off.".format(self._name, speaker))
																	speaker(0, 'AVDevice', self._tcp)

											except Exception as err:
												self.logger.warning("AVDevice {}: Problems reading Speakers info. Error:{}".format(self._name, err))
										else:
											value = receivedvalue = data[index + commandlength:index + commandlength + valuelength]
											self.logger.log(VERBOSE1, "Parsing Input {}: Neither Display nor Now Playing in response. receivedvalue: {}.".format(
												self._name, receivedvalue))

											invert = True if entry[6].lower() in ['1', 'true', 'yes', 'on'] else False
											receivedvalue = self._convertvalue(value, expectedtype, invert)

										if isinstance(receivedvalue, eval(expectedtype)):
											sametype = True
										else:
											sametype = False

										if sametype is False:
											self.logger.log(VERBOSE1, "Parsing Input {}: Receivedvalue {} does not match type {} - ignoring it.".format(self._name, receivedvalue, expectedtype))
										else:
											self.logger.log(VERBOSE1, "Parsing Input {}: Receivedvalue {} does match type {} - going on.".format(self._name, receivedvalue, expectedtype))
											if data.startswith(tuple(inputcommands)) and receivedvalue in self._ignoredisplay and '' not in self. _ignoredisplay:
												for i in range(0, len(inputcommands)):
													if data.startswith(inputcommands[i]):
														self._special_commands['Input']['Ignore'][i] = 1
												if self._special_commands['Display']['Command'] not in self._ignore_response and not self._special_commands['Display']['Command'] == '' and '' not in self._ignore_response:
													self._ignore_response.append(self._special_commands['Display']['Command'])
												self.logger.error("Parsing Input {}: Data {} has value in ignoredisplay {}. Ignorecommands are now: {}. Display Ignore is {}. Input Ignore is {}".format(self._name, data, self._ignoredisplay, self._ignore_response, self._special_commands['Display']['Ignore'], self._special_commands['Input']['Ignore']))
											elif data.startswith(tuple(inputcommands)) and receivedvalue not in self._ignoredisplay and '' not in self. _ignoredisplay:
												for i in range(0, len(inputcommands)):
													if data.startswith(inputcommands[i]):
														self._special_commands['Input']['Ignore'][i] = 0
												self.logger.log(VERBOSE2, "Parsing Input {}: Data {} has NO value in ignoredisplay {}. Ignorecommands are now: {}. Display Ignore is {}. Input Ignore is {}".format(self._name, data, self._ignoredisplay, self._ignore_response, self._special_commands['Display']['Ignore'], self._special_commands['Input']['Ignore']))
												if self._special_commands['Display']['Ignore'] == 0 and 1 not in self._special_commands['Input']['Ignore']:
													while self._special_commands['Display']['Command'] in self._ignore_response:
														self._ignore_response.remove(self._special_commands['Display']['Command'])
													self.logger.log(VERBOSE2, "Parsing Input {}: Removing {} from ignore.".format(self._name, self._special_commands['Display']['Command']))
											value = receivedvalue
											self.logger.debug("Parsing Input {}: Found key {} in response at position {} with value {}.".format(
												self._name, key, index, value))

											for entry in self._keep_commands:
												self.logger.log(VERBOSE1, "Parsing Input {}: Testing Keep Command entry {}".format(
													self._name, entry,	self._keep_commands.get(entry)))
												if data in self._keep_commands.get(entry).split(",")[2].split("|"):
													self.logger.debug("Parsing Input {}: Removing {} from Keep Commands {} because corresponding value received.".format(
														self._name, entry, self._keep_commands.get(entry), self._keep_commands))
													self._keep_commands.pop(entry)
													break
											if function in self._items[zone].keys():
												self._items[zone][function]['Value'] = value
												self.logger.log(VERBOSE1, "Parsing Input {}: Updated Item dict {}".format(self._name, self._items[zone][function]))

											for singleitem in item:
												singleitem(value, 'AVDevice', self._tcp)
												self.logger.debug("Parsing Input {}: Updating Item {} with {} Value: {}.".format(
													self._name, singleitem, expectedtype, value))
												updated = 1
												self._wait(0.15)

											if updated == 1:
												self.logger.log(VERBOSE1, "Parsing Input {}: Updated all relevant items from item {}. step 1".format(self._name, item))
												break
										if updated == 1:
											self.logger.log(VERBOSE1, "Parsing Input {}: Updated all relevant items from {}. step 2".format(self._name, item))
											break
									elif key.lower() == 'string':
										value = data
										if value.startswith(tuple(sorted_response_commands)):
											self.logger.log(VERBOSE1, "Parsing Input {}: Found string for Item {} with Value {} but ignored because it is a legit response for another command.".format(
												self._name, item, value))
											pass
										else:
											for singleitem in item:
												singleitem(value, 'AVDevice', self._tcp)
												self._wait(0.15)
												self.logger.debug("Parsing Input {}: Updating item {} with value {}".format(self._name, singleitem, value))
											break
									if updated == 1:
										self.logger.log(VERBOSE1, "Parsing Input {}: Updated all relevant items from {}. step 3".format(self._name, item))
										break
							if updated == 1:
								self.logger.log(VERBOSE1, "Parsing Input {}: Updated all relevant items from {}. step 4".format(self._name, item))
								break
						if self._send_commands == []:
						    self._sendingcommand = 'done'
						self.logger.log(VERBOSE1, "Parsing Input {}: Finished. Send Commands: {}, sending Command: {}. Data: {}".format(
						    self._name, self._send_commands, self._sendingcommand, data))
			except Exception as err:
				self.logger.error("Parsing Input {}: Problems parsing input. Error: {}".format(self._name, err))
			finally:
				if not self._send_commands == [] and data == 'waiting':
					self.logger.log(VERBOSE2, "Parsing Input {}: Waiting for response..".format(self._name))
				if not self._send_commands == [] and not data == 'waiting':
					reorderlist = []
					index = 0
					for command in self._send_commands:
						if command in self._query_commands:
							reorderlist.append(command)
						elif command in self._power_commands:
							self.logger.log(VERBOSE1, "Parsing Input {}: Ordering power command {} to first position.".format(self._name, command))
							reorderlist.insert(0, command)
							index += 1
						else:
							reorderlist.insert(index, command)
							index += 1
					self._send_commands = reorderlist
					self.logger.debug('Parsing Input {}: Newly sorted send commands at end of parsing: {}'.format(self._name, self._send_commands))
					if self._is_connected == []:
						for command in self._send_commands:
							self.logger.log(VERBOSE1, "Parsing Input {}: Going to reset in the end because connection is lost: {}.".format(self._name, command))
							if command not in self._query_commands and command not in self._special_commands['Display']['Command'] and not self._sendingcommand == 'gaveup':
								self._keep_commands[time.time()] = self._sendingcommand = command
								self.logger.debug("Parsing Input {}: Removing item {} from send command because not connected, storing in keep commands: {}.".format(
									self._name, command, self._keep_commands))
							self._resetitem()
							self._send_commands.pop(0)
							self.logger.debug('Parsing Input {}: First entry from send_commands removed. Send commands are now: {}'.format(
								self._name, self._send_commands))
					else:
						sending = self._send('{}'.format(to_send), 'parseinput_final')
						self.logger.log(VERBOSE1, "Parsing Input {}: Sending again because list is not empty yet. Sending return is {}.".format(
							self._name, sending))
					if 'Serial' in self._is_connected and connectionproblem is True:
						self._is_connected.remove('Serial')
						try:
							self._is_connected.remove('Connecting')
						except Exception:
							pass
						self._trigger_reconnect = True
					if 'TCP' in self._is_connected and connectionproblem is True:
						self._is_connected.remove('TCP')
						try:
							self._is_connected.remove('Connecting')
						except Exception:
							pass
						self._trigger_reconnect = True
					if self._trigger_reconnect is True and self._is_connected == []:
						self.logger.log(VERBOSE1, "Parsing Input {}: Trying to connect while parsing item".format(self._name))
						self.connect('parse_dataerror')



	# Updating items based on value changes via Visu, CLI, etc.
	def update_item(self, item, caller=None, source=None, dest=None):
		if self.alive:
			if caller != 'AVDevice':
				try:
					emptycommand = False
					depending = True
					self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Starting to update item {}. Caller: {}, Source: {}. Destination: {}. Reconnectrigger is {}".format(
						self._name.lower(), item, caller, source, dest, self._trigger_reconnect))
					# connect if necessary
					if self._trigger_reconnect is True:
						self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Trying to connect while updating item".format(self._name.lower()))
						self.connect('update_item')
					self.logger.debug("Updating Item for avdevice_{}: {} trying to update {}".format(
						self._name.lower(), caller, item))
					if item == self._dependson:
						try:
							dependsvalue = self._dependson()
							if dependsvalue == self._dependson_value:
								depending = False
							else:
								depending = True
						except Exception as e:
							depending = False
						if depending is False:
							try:
								eval(self._items['zone0']['statusupdate']['Item'][0])(1, 'Depending', self._rs232)
								self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Depend value is same as set up, statusupdate starting {}.".format(
									self._name.lower(), self._items['zone0']['statusupdate']['Item'][0]))
							except Exception:
								try:
									self._items['zone0']['statusupdate']['Item'][0](1, 'Depending', self._rs232)
									self.logger.debug("Updating Item for avdevice_{}: Updated Item after connection: {} with value 1. Commandlist: {}".format(
										self._name, self._items['zone0']['statusupdate']['Item'][0], self._send_commands))
								except Exception as err:
									self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: No statusupdate defined, not querying status after {}. Message: {}".format(self._name, caller, err))
						elif depending is True:
							self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Depend value is false. No update of items.".format(self._name.lower()))
							if self._depend0_volume0 is True or self._depend0_power0 is True:
								self._resetondisconnect('updateitem')
					if depending is True:
						for zone in range(0, self._number_of_zones + 1):
							command = ''
							letsgo = False
							try:
								if self.has_iattr(item.conf, 'avdevice'):
									command = self.get_iattr_value(item.conf, 'avdevice')
									zoneX = True
								elif self.has_iattr(item.conf, 'avdevice_zone{}_speakers'.format(zone)):
									command = 'speakers'
									zoneX = True
									self.logger.debug("Updating Item for avdevice_{}: Command is {}. Zone is {}".format(self._name.lower(), command, zone))
								else:
									zoneX = False
							except Exception:
								zoneX = False
							try:
								if self.has_iattr(item.conf, 'avdevice_zone{}'.format(zone)) or zoneX is True:
									letsgo = True
							except Exception:
								if item == 'statusupdate' and zone == 0:
									letsgo = True
								else:
									letsgo = False
							if letsgo is True:
								value = item()
								if zoneX is False:
									try:
										command = self.get_iattr_value(item.conf, 'avdevice_zone{}'.format(zone))
										value = item()
									except Exception:
										command = 'statusupdate'
										value = True
								command_on = '{} on'.format(command)
								command_off = '{} off'.format(command)
								command_set = '{} set'.format(command)
								command_increase = '{} increase'.format(command)
								command_decrease = '{} decrease'.format(command)
								updating = True
								sending = True

								try:
									if command is None:
										command = '{} on'.format(command)
									if command is None or command == 'None on':
										command = '{} off'.format(command)
									if command is None or command == 'None off':
										command = '{} set'.format(command)
									if command is None or command == 'None set':
										command = '{} increase'.format(command)
									if command is None or command == 'None increase':
										command = '{} decrease'.format(command)
									if self._functions['zone{}'.format(zone)][command][2] == '':
										emptycommand = True
										if not self._is_connected == []:
											self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Function is empty. Sending nothing. Command: {} Item: {}".format(
												self._name.lower(), command, item))
										if command == 'statusupdate':
											try:
												checkvalue = item()
											except Exception:
												checkvalue = True
											if (checkvalue is True or caller == 'Init') and not self._special_commands['Display']['Ignore'] >= 5:
												if not self._is_connected == []:
													self._addkeepcommands('statusupdate', 'all')
												for query in self._query_commands:
													if query not in self._send_commands:
														self._send_commands.append(query)
												self._reconnect_counter = 0
												self._trigger_reconnect = True
												if not self._is_connected == []:
													self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Updating status. Sendcommands: {}. Reconnecttrigger: {}. Display Ignore: {}".format(self._name.lower(), self._send_commands, self._trigger_reconnect, self._special_commands['Display']['Ignore']))
											elif checkvalue is False and not self._special_commands['Display']['Ignore'] >= 5:
												try:
													dependsvalue = self._dependson()
													self.logger.debug("Updating Item for avdevice_{}: Connection depends on {}. It's value is {}, has to be {}. Connections are {}".format(self._name.lower(), self._dependson, dependsvalue, self._dependson_value, self._is_connected))
													if dependsvalue == self._dependson_value:
														depending = False
													else:
														depending = True
												except Exception as e:
													depending = False
													self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Depending is false. Message: {}".format(self._name.lower(), e))
												if depending is True or self._is_connected == [] or self._is_connected == ['Connecting'] and (self._depend0_volume0 is True or self._depend0_power0 is True):
													self._resetondisconnect('statusupdate')
											elif self._special_commands['Display']['Ignore'] >= 5:
												sending = False

										updating = False

									elif self._functions['zone{}'.format(zone)][command][5].lower() == 'r':
										self.logger.warning("Updating Item for avdevice_{}: Function is read only. Not updating. Command: {}".format(
											self._name.lower(), command))
										updating = False
										# Re-query Item to update value
										commandinfo = self._functions['zone{}'.format(zone)][command]
										self._send_commands.append('{},{},{},{}'.format(commandinfo[2], commandinfo[3], commandinfo[4], commandinfo[8]))

								except Exception as err:
									self.logger.log(VERBOSE2, "Updating Item for avdevice_{}: Command {} is a standard command. Message: {}".format(
										self._name.lower(), command, err))

								if updating is True:
									self.logger.debug("Updating Item for avdevice_{}: {} set {} to {} for {} in zone {}".format(
										self._name.lower(), caller, command, value, item, zone))
									self._trigger_reconnect = True
									setting = False
									if command in self._functions['zone{}'.format(zone)]:
										commandinfo = self._functions['zone{}'.format(zone)][command]
										appendcommand = '{},{},{},{}'.format(commandinfo[2], commandinfo[3], commandinfo[4], commandinfo[8])
										if appendcommand in self._send_commands:
											self.logger.debug("Updating Item for avdevice_{}: Command {} already in Commandlist. Ignoring.".format(
												self._name.lower(), appendcommand))
										else:
											self.logger.debug("Updating Item for avdevice_{}: Updating Zone {} Commands {} for {}".format(
												self._name.lower(), zone, self._send_commands, item))
											self._send_commands.append(appendcommand)
									elif command_increase in self._functions['zone{}'.format(zone)]:
										commandinfo = self._functions['zone{}'.format(zone)][command_increase]
										appendcommand = '{},{},{},{}'.format(commandinfo[2], commandinfo[3], commandinfo[4], commandinfo[8])
										if appendcommand in self._send_commands:
											self.logger.debug("Updating Item for avdevice_{}: Increase Command {} already in Commandlist. Ignoring.".format(
												self._name.lower(), appendcommand))
										else:
											self.logger.debug("Updating Item for avdevice_{}: Updating Zone {} Command Increase {} for {}".format(
												self._name.lower(), zone, self._send_commands, item))
											self._send_commands.append(appendcommand)
									elif command_decrease in self._functions['zone{}'.format(zone)]:
										commandinfo = self._functions['zone{}'.format(zone)][command_decrease]
										appendcommand = '{},{},{},{}'.format(commandinfo[2], commandinfo[3], commandinfo[4], commandinfo[8])
										if appendcommand in self._send_commands:
											self.logger.debug("Updating Item for avdevice_{}: Decrease Command {} already in Commandlist. Ignoring.".format(
												self._name.lower(), appendcommand))
										else:
											self._send_commands.append(appendcommand)
											self.logger.debug("Updating Item for avdevice_{}: Updating Zone {} Command Decrease {} for {}".format(
												self._name.lower(), zone, self._send_commands, item))
									elif command_on in self._functions['zone{}'.format(zone)] and isinstance(value, bool) and value == 1:
										commandinfo = self._functions['zone{}'.format(zone)][command_on]
										reverseinfo = self._functions['zone{}'.format(zone)][command_off]
										try:
											replacedcommand = commandinfo[4].replace('**', 'ON')
											appendcommand = '{},{},{},{}'.format(commandinfo[2], commandinfo[3], replacedcommand, commandinfo[8])
											replacedreverse = reverseinfo[4].replace('***', 'OFF')
											reversecommand = '{},{},{},{}'.format(reverseinfo[2], reverseinfo[3], replacedreverse, commandinfo[8])
											if commandinfo[6].lower() in ['1', 'true', 'yes', 'on']:
												replacedvalue = '0'
												reversevalue = '1'
											else:
												replacedvalue = '1'
												reversevalue = '0'
											replacedcommand = replacedcommand.replace('*', replacedvalue)
											reversecommand = reversecommand.replace('*', reversevalue)
											appendcommand = '{},{},{},{}'.format(commandinfo[2], commandinfo[3], replacedcommand, commandinfo[8])
										except Exception as err:
											self.logger.debug("Updating Item for avdevice_{}: Problems replacing *: {}".format(
												self._name.lower(), err))
										self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Appendcommand on: {}, Send Commands: {}".format(
											self._name.lower(), appendcommand, self._send_commands))
										if appendcommand in self._send_commands:
											self.logger.debug("Updating Item for avdevice_{}: Command On {} already in Commandlist {}. Ignoring.".format(
												self._name.lower(), appendcommand, self._send_commands))
										elif reversecommand in self._send_commands:
											self.logger.debug("Updating Item for avdevice_{}: Command Off {} already in Commandlist {}. Replacing with Command On {}.".format(
												self._name.lower(), reversecommand, self._send_commands, appendcommand))
											self._send_commands[self._send_commands.index(reversecommand)] = self._sendingcommand = appendcommand
											self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: New Commandlist {}.".format(
												self._name.lower(), self._send_commands))
											self._resend_counter = 0
											self.logger.log(VERBOSE1, "Parsing Input {}: Resetting Resend Counter due to new command.".format(self._name))
										else:
											self._send_commands.append(appendcommand)
											self._sendingcommand = appendcommand
											self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Update Zone {} Command On {} for {}".format(
												self._name.lower(), zone, commandinfo[2], item))
											if command_on == 'power on':
												self._addkeepcommands('powercommand', 'zone{}'.format(zone))
												self.logger.debug("Updating Item for avdevice_{}: Command Power On for zone: {}. Appending relevant query commands: {}".format(
													self._name.lower(), zone, self._query_zonecommands['zone{}'.format(zone)]))
												for query in self._query_zonecommands['zone{}'.format(zone)]:
													if query not in self._send_commands:
														self._send_commands.append(query)

									elif command_off in self._functions['zone{}'.format(zone)] and isinstance(value, bool) and value == 0:
										commandinfo = self._functions['zone{}'.format(zone)][command_off]
										reverseinfo = self._functions['zone{}'.format(zone)][command_on]
										try:
											replacedcommand = commandinfo[4].replace('*******', 'STANDBY')
											replacedcommand = replacedcommand.replace('***', 'OFF')
											appendcommand = '{},{},{},{}'.format(commandinfo[2], commandinfo[3], replacedcommand, commandinfo[8])
											replacedreverse = reverseinfo[4].replace('**', 'ON')
											reversecommand = '{},{},{},{}'.format(reverseinfo[2], reverseinfo[3], replacedreverse, commandinfo[8])
											if commandinfo[6].lower() in ['1', 'true', 'yes', 'on']:
												replacedvalue = '1'
												reversevalue = '0'
											else:
												replacedvalue = '0'
												reversevalue = '1'
											replacedcommand = replacedcommand.replace('*', replacedvalue)
											reversecommand = reversecommand.replace('*', reversevalue)
											appendcommand = '{},{},{},{}'.format(commandinfo[2], commandinfo[3], replacedcommand, commandinfo[8])
											self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: replacedcommand: {} appendcommand: {}, replacedreverse: {}, reversecommand {}".format(self._name.lower(), replacedcommand, appendcommand, replacedreverse, reversecommand))
										except Exception as err:
											self.logger.debug("Updating Item for avdevice_{}: Problems replacing *: {}".format(
												self._name.lower(), err))
										self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Appendcommand off: {}. Reversecommand: {} Send Commands: {}".format(
											self._name.lower(), appendcommand, reversecommand, self._send_commands))
										if appendcommand in self._send_commands:
											self.logger.debug("Updating Item for avdevice_{}: Command Off {} already in Commandlist {}. Ignoring.".format(
												self._name.lower(), appendcommand, self._send_commands))
										elif reversecommand in self._send_commands:
											self.logger.debug("Updating Item for avdevice_{}: Command On {} already in Commandlist {}. Replacing with Command Off {}.".format(
												self._name.lower(), reversecommand, self._send_commands, appendcommand))
											self._send_commands[self._send_commands.index(reversecommand)] = self._sendingcommand = appendcommand
											self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: New Commandlist {}.".format(
												self._name.lower(), self._send_commands))
											self._resend_counter = 0
											self.logger.log(VERBOSE1, "Parsing Input {}: Resetting Resend Counter due to new command.".format(self._name))
										else:
											self._send_commands.append(appendcommand)
											self._sendingcommand = appendcommand
											self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Update Zone {} Command Off {} for {}".format(
												self._name.lower(), zone, commandinfo[2], item))
									elif command_set in self._functions['zone{}'.format(zone)]:
										commandinfo = self._functions['zone{}'.format(zone)][command_set]
										if value == 0 and 'bool' in commandinfo[8]:
											setting = True
											value = 'OFF'
											try:
												command_re = re.sub('\*+', '{}'.format(value), commandinfo[2])
												response = re.sub('\*+', '{}'.format(value), commandinfo[4])
											except Exception:
												command_re = commandinfo[2]
												response = commandinfo[4]
											self.logger.debug("Updating Item for avdevice_{}: Value 0 is converted to OFF. command_re: {}, response: {}".format(self._name.lower(), command_re, response))

										elif (isinstance(value, int) and 'int' in commandinfo[8]) or (isinstance(value, float) and 'float' in commandinfo[8]):
											setting = True
											try:
												value = max(min(value, int(commandinfo[7])), 0)
												self.logger.debug("Updating Item for avdevice_{}: value limited to {}.".format(
													self._name.lower(), commandinfo[7]))
											except Exception:
												self.logger.debug(
													"Updating Item for avdevice_{}: Value limited to specific number of digits".format(self._name.lower()))
											if commandinfo[2].count('*') > 1:
												anzahl = commandinfo[2].count('*')
												self.logger.log(
													VERBOSE1, "Updating Item for avdevice_{}: Value has to be {} digits.".format(self._name.lower(), anzahl))
												value = max(min(value, int(re.sub('[^0-9]', '', re.sub('\*', '9', commandinfo[2])))), 0)
												command_re = re.sub(r'(\*)\1+', '{0:0{1}d}'.format(value, anzahl), commandinfo[2])
												response = re.sub(r'(\*)\1+', '{0:0{1}d}'.format(value, anzahl), commandinfo[4])
											elif commandinfo[2].count('*') == 1:
												if command.lower().startswith('speakers'):
													currentvalue = int(self._items['zone{}'.format(zone)]['speakers']['Item'][0]())
													multiply = -1 if item() == 0 else 1
													multiply = 0 if (currentvalue == 0 and item() == 0) else multiply
													value = abs(int(self.get_iattr_value(item.conf, 'avdevice_zone{}_speakers'.format(zone))))
													powercommands = self._functions['zone{}'.format(zone)]['power on']
													self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Speaker {} current value is {}. Item: {} with value {}. Multiply: {}. Value: {}".format(self._name.lower(), self._items['zone{}'.format(zone)]['speakers']['Item'][0], currentvalue, item, item(), multiply, value))
													if not currentvalue == value or multiply == -1:
														value = currentvalue + (value * multiply)
													if value > 0:
														if powercommands[6].lower() in ['1', 'true', 'yes', 'on']:
															replacedvalue = '0'
														else:
															replacedvalue = '1'
														self._send_commands.insert(0, '{},{},{},{}'.format(
															powercommands[2], powercommands[3], powercommands[4].replace('*', replacedvalue), powercommands[8]))
														self._sendingcommand = '{},{},{},{}'.format(
															powercommands[2], powercommands[3], powercommands[4].replace('*', replacedvalue), powercommands[8])
														self.logger.debug("Updating Item for avdevice_{}: Turning power on. powercommands is: {}".format(self._name.lower(), powercommands))

												else:
													value = max(min(value, 9), 0)
												command_re = commandinfo[2].replace('*', '{0:01d}'.format(value))
												response = commandinfo[4].replace('*', '{0:01d}'.format(value))
												self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Value has to be 1 digit. Value is {}".format(self._name.lower(), value))

											elif commandinfo[2].count('*') == 0:
												self.logger.error("Updating Item for avdevice_{}: Set command {} does not have any placeholder *.".format(self._name.lower(), commandinfo))

										elif isinstance(value, str) and 'str' in commandinfo[8]:
											setting = True
											value = value.upper()
											self.logger.debug("Updating Item for avdevice_{}: Value has to be string. Value is {}".format(self._name.lower(), value))
											try:
												command_re = commandinfo[2].replace('*', '{}'.format(value), 1)
												command_re = command_re.replace('*', '')
												response = commandinfo[4].replace('*', '{}'.format(value), 1)
												response = response.replace('*', '')
											except Exception:
												command_re = commandinfo[2]
												response = commandinfo[4]
										else:
											setting = False

									else:
										self.logger.error("Updating Item for avdevice_{}: Command {} not in text file!".format(
											self._name.lower(), command))
										updating = False

									if not self._send_commands == [] and setting is True:
										appending = True
										setting = False
										for sendcommand in self._send_commands:
											self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Testing send command: {}".format(self._name.lower(), sendcommand))
											if commandinfo[3] in sendcommand:
												valuetype = sendcommand.split(',')
												try:
													valuetype[3:] = [','.join(valuetype[3:])]
													testvalue = valuetype[3]
												except Exception:
													testvalue = ''
												if testvalue == commandinfo[8]:
													self._sendingcommand = '{},{},{},{}'.format(command_re, commandinfo[3], response, commandinfo[8])
													self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Command Set {} already in Commandlist {}. Value type: {}, expected type: {}. Replaced. Sendingcommand: {}".format(self._name.lower(), command, self._send_commands, type(value), commandinfo[8], self._sendingcommand))
													self._send_commands[self._send_commands.index(sendcommand)] = '{},{},{},{}'.format(command_re, commandinfo[3], response, commandinfo[8])
													self._resend_counter = 0
													appending = False
													self.logger.log(VERBOSE1, "Parsing Input {}: Resetting Resend Counter due to replaced command.".format(self._name))
													break
												else:
													self.logger.log(VERBOSE2, "Updating Item for avdevice_{}: Command Set {} already in Commandlist {} but value is not same type. Continue...".format(
														self._name.lower(), command, self._send_commands))
										if appending is True:
											self._send_commands.append('{},{},{},{}'.format(command_re, commandinfo[3], response, commandinfo[8]))
											self._sendingcommand = '{},{},{},{}'.format(command_re, commandinfo[3], response, commandinfo[8])
											self._resend_counter = 0
											self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Resetting Resend Counter because appending new set command.".format(self._name))
											self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Update Zone {} Command Set {} for {}. Command: {}".format(
												self._name.lower(), zone, commandinfo[2], item, command_re))
									elif setting is True:
										self._send_commands.append('{},{},{},{}'.format(command_re, commandinfo[3], response, commandinfo[8]))
										self._resend_counter = 0
										self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Resetting Resend Counter because adding new set command.".format(self._name))
										self.logger.debug("Updating Item for avdevice_{}: Update Zone {} Command Set, adding to empty Commandlist {} for {}. Command: {}".format(
											self._name.lower(), zone, self._send_commands, item, command_re))

				except Exception as err:
					self.logger.error("Updating Item for avdevice_{}: Problem updating item. Error: {}. Does the item exist?".format(
						self._name.lower(), err))
				finally:
					if not self._send_commands == []:
						reorderlist = []
						index = 0
						for command in self._send_commands:
							if command in self._query_commands:
								reorderlist.append(command)
							else:
								reorderlist.insert(index, command)
								index += 1
						self._send_commands = reorderlist
						self._sendingcommand = self._send_commands[0]

					try:
						if not self._is_connected == [] and not self._send_commands == [] and not self._is_connected == ['Connecting']:
							self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Updating item. Command list is {}. Sendingcommand: {}. ".format(
								self._name.lower(), self._send_commands, self._sendingcommand))
							sending = self._send('command', 'updateitem')

							self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Updating item. Command list is {}. Return from send is {}".format(
								self._name.lower(), self._send_commands, sending))

						if self._reset_onerror is True and emptycommand is False and not self._send_commands == [] and not self._sendingcommand == 'done' and self._is_connected == []:
							if not self._send_commands[0].split(',')[0] == self._send_commands[0].split(',')[1]:
								self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Sending command {}. Starting to reset".format(self._name.lower(), self._sendingcommand))
								resetting = self._resetitem()
							else:
								resetting = ''
							befehle = []
							for eintrag in self._send_commands:
								befehle.append(eintrag.split(',')[0])
							try:
								index = self._send_commands.index(self._sendingcommand)
							except Exception:
								index = befehle.index(self._sendingcommand)
								self.logger.log(VERBOSE1, "Updating Item for avdevice_{}: Sending command {} not in Sendcommands {} list, but found in {}".format(self._name.lower(), self._sendingcommand, self._send_commands, befehle))
							if self._send_commands[index] not in self._query_commands and not self._send_commands[index] in self._special_commands['Display']['Command']:
								self._keep_commands[time.time()] = self._send_commands[index]
							self._send_commands.pop(index)
							if self._depend0_volume0 is True or self._depend0_power0 is True:
								self._resetondisconnect('update_end')
							if resetting == '':
								self.logger.debug("Updating Item for avdevice_{}: Connection error while trying to query info.".format(self._name.lower()))
							else:
								self.logger.info("Updating Item for avdevice_{}: Connection error. Resetting Item {}. Keepcommands: {}. Sendcommands: {} Sendingcommand: {}".format(
									self._name.lower(), resetting, self._keep_commands, self._send_commands, self._sendingcommand))
							self._sendingcommand = 'done'

					except Exception as err:
						if not self._is_connected == []:
							self.logger.warning("Updating Item for avdevice_{}: Problem sending command. It is most likely not in the text file! Error: {}".format(self._name.lower(), err))
						else:
							self.logger.warning(
								"Updating Item for avdevice_{}: Problem sending command - not connected! Error: {}".format(self._name.lower(), err))

	# Sending commands to the device
	def _send(self, command, caller):
		self.logger.log(VERBOSE1, "Sending {}: Sending function called by: {}. Command: {}.".format(self._name, caller, command))
		try:
			if not self._send_commands == []:
				if command == 'command':
					to_send = self._send_commands[0].split(",")[0]
				elif command == 'query':
					to_send = self._send_commands[0].split(",")[1]
				else:
					to_send = command
					command = 'Resendcommand'
				commandlist = to_send.split("|")
				self.logger.log(VERBOSE1, "Sending {}: Starting to send {} {} from list {}. Caller: {}.".format(self._name, command, to_send, self._send_commands, caller))
				try:
					self._sendingcommand = self._send_commands[0]
				except Exception:
					self._sendingcommand = to_send
				response = self._send_commands[0].split(",")[2].split("|")
				if self._parsinginput == []:
					self.logger.log(VERBOSE1, "Sending {}: Starting Parse Input. Expected response: {}".format(self._name, response))
					self._parse_input_init('sending')

				for resp in response:
					if resp in self._special_commands['Display']['Command']:
						keyfound = True
					else:
						keyfound = False
				if self._send_commands[0] in self._query_commands and len(self._send_commands) > 1 and keyfound is not True and self._special_commands['Display']['Ignore'] < 5:
					self._special_commands['Display']['Ignore'] = self._special_commands['Display']['Ignore'] + 5
					if self._special_commands['Display']['Command'] not in self._ignore_response and '' not in self._ignore_response and not self._special_commands['Display']['Command'] == '':
						self._ignore_response.append(self._special_commands['Display']['Command'])
					self.logger.log(VERBOSE2, "Sending {}: Querycommand. Command: {}. Querycommand: {}, Display Ignore: {}, Input Ignore: {}".format(
						self._name, self._send_commands[0], self._query_commands, self._special_commands['Display']['Ignore'], self._special_commands['Input']['Ignore']))

				elif self._send_commands[0] not in self._query_commands or len(self._send_commands) <= 1 or keyfound is True:
					if self._special_commands['Display']['Ignore'] >= 5:
						self._special_commands['Display']['Ignore'] = self._special_commands['Display']['Ignore'] - 5
					if self._special_commands['Display']['Ignore'] == 0 and 1 not in self._special_commands['Input']['Ignore']:
						while self._special_commands['Display']['Command'] in self._ignore_response:
							self._ignore_response.remove(self._special_commands['Display']['Command'])
						self.logger.log(VERBOSE1, "Sending {}: Removing {} from ignore. Ignored responses are now: {}".format(self._name, self._special_commands['Display']['Command'], self._ignore_response))

				if self._trigger_reconnect is True:
					self.logger.log(VERBOSE1, "Sending {}: Trying to connect while sending command".format(self._name))
					self.connect('send')
				cmd = 0
				for multicommand in commandlist:
					cmd += 1
					if self._rs232 is not None:
						# result = self._serial.write(bytes('{}\r'.format(multicommand), 'utf-8'))
						result = self._serialwrapper.write(u'{}\r'.format(multicommand))
						self._serialwrapper.flush()
						self.logger.debug("Sending Serial {}: {} was sent {} from Multicommand-List {}. Returns {}. Sending command: {}".format(self._name, command, multicommand, commandlist, result, self._sendingcommand))
						self._wait(0.2)
						return result

					elif self._tcp is not None:
						result = self._tcpsocket.send(bytes('{}\r'.format(multicommand), 'utf-8'))
						self.logger.debug("Sending TCP {}: {} was sent {} from Multicommand-List {}. Returns {}".format(self._name, command, multicommand, commandlist, result))
						self._wait(0.2)
						return result

					else:
						self.logger.error("Sending {}: Neither IP address nor Serial device definition found".format(self._name))
		except IOError as err:
			if err.errno == 32:
				self.logger.warning(
					"Sending {}: Problem sending multicommand {}, not connected. Message: {}".format(self._name, self._send_commands[0], err))
				try:
					self._tcpsocket.shutdown(2)
					self._tcpsocket.close()
					self.logger.debug("Sending {}: TCP socket closed".format(self._name))
				except Exception:
					self.logger.log(VERBOSE1, "Sending {}: No TCP socket to close.".format(self._name))
				try:
					self._is_connected.remove('TCP')
					self._is_connected.remove('Connecting')
					self.logger.log(VERBOSE1, "Sending {}: reconnect TCP started.".format(self._name))
					self.connect('send_IOError_TCP')

				except Exception:
					self.logger.debug("Sending {}: Cannot reconnect TCP.".format(self._name))
				try:
					self._serialwrapper.close()
					self.logger.debug("Sending {}: Serial socket closed".format(self._name))
				except Exception:
					self.logger.log(VERBOSE1, "Sending {}: No Serial socket to close.".format(self._name))
				try:
					self._is_connected.remove('Serial')
					self._is_connected.remove('Connecting')
					self.logger.log(VERBOSE1, "Sending {}: reconnect Serial started.".format(self._name))
					self.connect('send_IOError_RS232')
				except Exception:
					self.logger.debug("Sending {}: Cannot reconnect Serial.".format(self._name))

		except Exception as err:
			try:
				self.logger.warning("Sending {}: Problem sending multicommand {}. Message: {}".format(self._name, self._send_commands[0], err))
			except Exception:
				self.logger.warning("Sending {}: Problem sending multicommand {}. Message: {}".format(self._name, self._send_commands, err))

	# Stopping function when SmarthomeNG is stopped
	def stop(self):
		self.alive = False
		self._sh.scheduler.change('avdevice-tcp-reconnect', active=False)
		self._sh.scheduler.remove('avdevice-tcp-reconnect')
		self._sh.scheduler.change('avdevice-serial-reconnect', active=False)
		self._sh.scheduler.remove('avdevice-serial-reconnect')

		try:
			self._tcpsocket.shutdown(2)
			self._tcpsocket.close()
			self.logger.debug("Stopping {}: closed".format(self._name))
		except Exception:
			self.logger.log(VERBOSE1, "Stopping {}: No TCP socket to close.".format(self._name))
		try:
			self._serialwrapper.close()
		except Exception:
			self.logger.log(VERBOSE1, "Stopping {}: No Serial socket to close.".format(self._name))


if __name__ == '__main__':
	logging.basicConfig(
		level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
	PluginClassName(AVDevice).run()
