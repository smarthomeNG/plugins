#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019 Thomas Hengsberg <thomas@thomash.eu>
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

from lib.model.smartplugin import *
from lib.item import Items
from .webif import WebInterface
import binascii
import json

from .robot import Robot


class Neato(SmartPlugin):
    PLUGIN_VERSION = '1.6.9'
    robot = 'None'

    def __init__(self, sh):
        """
        Initalizes the plugin.

        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.robot = Robot(self.get_parameter_value("account_email"), self.get_parameter_value("account_pass"), self.get_parameter_value("robot_vendor"), token=self.get_parameter_value("token"))
        self._sh = sh
        self._cycle = 60
        self.logger.debug("Init completed.")
        self.init_webinterface(WebInterface)
        self._items = {}
        return

    def numberRobots(self):
        return self.robot.numberRobots()

    def backendOnline(self):
        return self.robot._backendOnline

    def accountEmail(self):
        return self.get_parameter_value("account_email")

    def clientIDHash(self):
        return self.robot.clientIDHash()

    def setClientIDHash(self, hash):
        return self.robot.setClientIDHash(hash)

    def run(self):
        self.logger.debug("Run method called")
        self.scheduler_add('poll_device', self.poll_device, prio=5, cycle=self._cycle)
        self.alive = True

    def stop(self):
        self.scheduler_remove('poll_device')
        self.logger.debug("Stop method called")
        self.alive = False

    def parse_item(self, item):
        
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the neato_attribute and adds it to an internal array

        :param item: The item to process.
        """
        if self.get_iattr_value(item.conf, 'neato_attribute'):
            if not self.get_iattr_value(item.conf, 'neato_attribute') in self._items:
                self._items[self.get_iattr_value(item.conf, 'neato_attribute')] = []
            self._items[self.get_iattr_value(item.conf, 'neato_attribute')].append(item)

        # Register items for event handling via smarthomeNG core. Needed for sending control actions:
        # Command items can be changed outside the plugin context:
        if self.get_iattr_value(item.conf, 'neato_attribute') == 'command':
            return self.update_item
        elif self.get_iattr_value(item.conf, 'neato_attribute') == 'is_schedule_enabled':
            return self.update_item
        elif self.get_iattr_value(item.conf, 'neato_attribute') == 'clean_room':
            return self.update_item



    def parse_logic(self, logic):
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        self.logger.debug("Update neato item: Caller: {0}, pluginname: {1}".format(caller,self.get_shortname() ))
        if caller != self.get_shortname():
            val_to_command = {
                61: 'start',
                62: 'stop',
                63: 'pause',
                64: 'resume',
                65: 'findme',
                66: 'sendToBase',
                67: 'enableSchedule',
                68: 'disableSchedule',
                69: 'dismiss_current_alert'}

            if self.get_iattr_value(item.conf, 'neato_attribute') == 'command':
                if item._value in val_to_command:
                    self.robot.robot_command(val_to_command[item._value])
                else:
                    self.logger.warning("Update item: {}, item has no command equivalent for value '{}'".format(item.id(),item() ))

            elif self.get_iattr_value(item.conf, 'neato_attribute') == 'is_schedule_enabled':
                if item._value == True:
                    self.robot.robot_command("enableSchedule")
                    self.logger.debug("enabling neato scheduler")
                else:
                    self.robot.robot_command("disableSchedule")
                    self.logger.debug("disabling neato scheduler")
            elif self.get_iattr_value(item.conf, 'neato_attribute') == 'clean_room':
                self.robot.robot_command("start", item._value, None)
                #self.robot.robot_command("start", item._value, '2020-03-09T07:52:21Z')
            pass

    def start_robot(self):
        response = self.robot.robot_command("start")
        return self.check_command_response(response)

    def start_robot(self, boundary_id=None, map_id=None):
        response = self.robot.robot_command("start", boundary_id, map_id)
        return self.check_command_response(response)

    def get_known_mapId(self):
        self.logger.info(f"MapID is {self.robot.mapId}")
        return self.robot.mapId

    # returns boundaryIds (clean zones) for given mapID
    # returns True on success and False otherwise
    def get_map_boundaries(self, map_id=None):
        response = self.robot.robot_command("getMapBoundaries", map_id)
        return self.check_command_response(response)

    def dismiss_current_alert(self):
        response = self.robot.robot_command("dismiss_current_alert")
        return self.check_command_response(response)

    # enable cleaning schedule
    # returns True on success and False otherwise
    def enable_schedule(self):
        response = self.robot.robot_command("enableSchedule")
        return self.check_command_response(response)

    def disable_schedule(self):
        response = self.robot.robot_command("disableSchedule")
        return self.check_command_response(response)

    def check_command_response(self, response):
        if not response:
            return False
        responseJson = response.json()
        if 'result' in responseJson:
            if str(responseJson['result']) == 'ok':
                return True
            else:
                return False
        else:
            return False

    def poll_device(self):
        returnValue = self.robot.update_robot()

        if returnValue == 'error':
            return

        for attribute, matchStringItems in self._items.items():

            if not self.alive:
                return

            #self.logger.warning('DEBUG: attribute: {0}, matchStringItems: {1}".format(attribute, matchStringItems))

            value = None

            if attribute == 'name':
                value = self.robot.name
            elif attribute == 'charge_percentage':
                value = str(self.robot.chargePercentage)
            elif attribute == 'is_docked':
                value = str(self.robot.isDocked)
            elif attribute == 'is_charging':
                value = self.robot.isCharging
            elif attribute == 'state':
                value = str(self.__get_state_string(self.robot.state))
            elif attribute == 'state_action':
                value = str(self.__get_state_action_string(self.robot.state_action))
            elif attribute == 'alert':
                value = str(self.robot.alert)
            elif attribute == 'is_schedule_enabled':
                value = self.robot.isScheduleEnabled 
            elif attribute == 'command_goToBaseAvailable':
                value = self.robot.dockHasBeenSeen
            elif attribute == 'command_startAvailable':
                value = self.robot.commandStartAvailable
            elif attribute == 'online_status':
                value = self.robot._backendOnline

            # if a value was found, store it to item
            if value is not None:
                for sameMatchStringItem in matchStringItems:
                    sameMatchStringItem(value, self.get_shortname() )
                    #self.logger.debug('_update: Value "{0}" written to item {1}'.format(value, sameMatchStringItem))

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


    # Oauth2 functions for new login feature with Vorwerk's myKobold APP
    
    # Generate 16 byte random hex hash as string:
    def generateRandomHash(self):
        hash = binascii.hexlify(os.urandom(16)).decode('utf8')
        self.robot.setClientIDHash(hash)
        return hash

    # Requesting authentication code to be send to email account:
    def request_oauth2_code(self, hash):
        success = self.robot.request_oauth2_code(hash)
        return success 

    # Requesting authentication token to be send to email account:
    def request_oauth2_token(self, code, hash):
        token = self.robot.request_oauth2_token(code, hash)
        return token



