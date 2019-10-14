#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019 Thomas Hengsberg <thomas@thomash.eu>
#########################################################################
#  This file is part of SmartHomeNG.   
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
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

from lib.model.smartplugin import *

from .robot import Robot


class Neato(SmartPlugin):
    PLUGIN_VERSION = '1.6.0'
    robot = 'None'
    _items = []

    def __init__(self, sh, *args, **kwargs):
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.robot = Robot(self.get_parameter_value("account_email"), self.get_parameter_value("account_pass"))
        self.robot.update_robot()
        self._cycle = 20
        return

    def run(self):
        self.logger.debug("Run method called")
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)
        self.alive = True

    def stop(self):
        self.logger.debug("Stop method called")
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'neato_command'):
            return self.update_item

        if self.has_iattr(item.conf, 'neato_name'):
            item.property.value = self.robot.name
            self._items.append(item)

        if self.has_iattr(item.conf, 'neato_chargepercentage'):
            item.property.value = str(self.robot.chargePercentage)
            self._items.append(item)

        if self.has_iattr(item.conf, 'neato_isdocked'):
            item.property.value = self.robot.isDocked
            self._items.append(item)

        if self.has_iattr(item.conf, 'neato_state'):
            item.property.value = self.__get_state_string(self.robot.state)
            self._items.append(item)

        if self.has_iattr(item.conf, 'neato_state_action'):
            item.property.value = self.__get_state_action_string(self.robot.state_action)
            self._items.append(item)

    def parse_logic(self, logic):
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != self.get_shortname():
            val_to_command = {
                61: 'start',
                62: 'stop',
                63: 'pause',
                64: 'resume',
                65: 'findme'}

            if self.has_iattr(item.conf, 'neato_command'):
                if item._value in val_to_command:
                    self.robot.robot_command(val_to_command[item._value])
                else:
                    self.logger.warning("Update item: {}, item has no command equivalent for value '{}'".format(item.id(),item() ))

            pass

    def poll_device(self):
        self.robot.update_robot()
        for item in self._items:
            if self.has_iattr(item.conf, 'neato_name'):
                value = self.robot.name
                item(value)

            if self.has_iattr(item.conf, 'neato_chargepercentage'):
                value = str(self.robot.chargePercentage)
                item(value)

            if self.has_iattr(item.conf, 'neato_isdocked'):
                value = self.robot.isDocked
                item(value)

            if self.has_iattr(item.conf, 'neato_state'):
                value = str(self.__get_state_string(self.robot.state))
                item(value)

            if self.has_iattr(item.conf, 'neato_state_action'):
                value = str(self.__get_state_action_string(self.robot.state_action))
                item(value)

        pass

    def __get_state_string(self,state):
        if state == '0':
            return 'invalid'
        elif  state == '1':
            return 'idle'
        elif state == '2':
            return 'busy'
        elif state == '3':
            return 'paused'
        elif state == '4':
            return 'error'

    def __get_state_action_string(self,state_action):
        if state_action == '0':
            return 'invalid'
        elif  state_action == '1':
            return 'House Cleaning'
        elif state_action == '2':
            return 'Spot Cleaning'
        elif state_action == '3':
            return 'Manual Cleaning'
        elif state_action == '4':
            return 'Docking'
        elif state_action == '5':
            return 'User Menu Active'
        elif state_action == '6':
            return 'Suspended Cleaning'
        elif state_action == '7':
            return 'Updating'
        elif state_action == '8':
            return 'Copying Logs'
        elif state_action == '9':
            return 'Recovering Location'
        elif state_action == '10':
            return 'IEC test'
        elif state_action == '11':
            return 'Map cleaning'
        elif state_action == '12':
            return 'Exploring map (creating a persistent map)'
        elif state_action == '13':
            return 'Acquiring Persistent Map IDs'
        elif state_action == '14':
            return 'Creating & Uploading Map'
        elif state_action == '15':
            return 'Suspended Exploration'




