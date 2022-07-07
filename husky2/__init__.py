#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      <AUTHOR>                                  <EMAIL>
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
import asyncio
from datetime import datetime
import time
import json

from lib.module import Modules
from lib.model.smartplugin import *
from lib.item import Items

import cherrypy
import aioautomower


class Husky2(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = '2.0.0'  # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release

    ITEM_INFO = "husky_info"
    ITEM_CONTROL = "husky_control"
    ITEM_STATE = "husky_state"

    VALID_INFOS = ['name', 'id', 'serial', 'model']
    VALID_STATES = ['message', 'state', 'activity', 'mode', 'errormessage', 'batterypercent', 'connection', 'longitude',
                    'latitude']
    VALID_COMMANDS = ['starttime', 'park', 'starttime', 'pause', 'parkpermanent', 'parktime', 'parknext', 'resume',
                      'cuttingheight', 'headlight']

    MOWERERROR = {
        0: {'msg': 'No error'},
        1: {'msg': 'Outside working area'},
        2: {'msg': 'No loop signal'},
        3: {'msg': 'Wrong loop signal'},
        4: {'msg': 'Loop sensor problem, front'},
        5: {'msg': 'Loop sensor problem, rear'},
        6: {'msg': 'Loop sensor problem, left'},
        7: {'msg': 'Loop sensor problem, right'},
        8: {'msg': 'Wrong PIN code'},
        9: {'msg': 'Trapped'},
        10: {'msg': 'Upside down'},
        11: {'msg': 'Low battery'},
        12: {'msg': 'Empty battery'},
        13: {'msg': 'No drive'},
        14: {'msg': 'Mower lifted'},
        15: {'msg': 'Lifted'},
        16: {'msg': 'Stuck in charging station'},
        17: {'msg': 'Charging station blocked'},
        18: {'msg': 'Collision sensor problem, rear'},
        19: {'msg': 'Collision sensor problem, front'},
        20: {'msg': 'Wheel motor blocked, right'},
        21: {'msg': 'Wheel motor blocked, left'},
        22: {'msg': 'Wheel drive problem, right'},
        23: {'msg': 'Wheel drive problem, left'},
        24: {'msg': 'Cutting system blocked'},
        25: {'msg': 'Cutting system blocked'},
        26: {'msg': 'Invalid sub-device combination'},
        27: {'msg': 'Settings restored'},
        28: {'msg': 'Memory circuit problem'},
        29: {'msg': 'Slope too steep'},
        30: {'msg': 'Charging system problem'},
        31: {'msg': 'STOP button problem'},
        32: {'msg': 'Tilt sensor problem'},
        33: {'msg': 'Mower tilted'},
        34: {'msg': 'Cutting stopped - slope too steep'},
        35: {'msg': 'Wheel motor overloaded, right'},
        36: {'msg': 'Wheel motor overloaded, left'},
        37: {'msg': 'Charging current too high'},
        38: {'msg': 'Electronic problem'},
        39: {'msg': 'Cutting motor problem'},
        40: {'msg': 'Limited cutting height range'},
        41: {'msg': 'Unexpected cutting height adj'},
        42: {'msg': 'Limited cutting height range'},
        43: {'msg': 'Cutting height problem, drive'},
        44: {'msg': 'Cutting height problem, curr'},
        45: {'msg': 'Cutting height problem, dir'},
        46: {'msg': 'Cutting height blocked'},
        47: {'msg': 'Cutting height problem'},
        48: {'msg': 'No response from charger'},
        49: {'msg': 'Ultrasonic problem'},
        50: {'msg': 'Guide 1 not found'},
        51: {'msg': 'Guide 2 not found'},
        52: {'msg': 'Guide 3 not found'},
        53: {'msg': 'GPS navigation problem'},
        54: {'msg': 'Weak GPS signal'},
        55: {'msg': 'Difficult finding home'},
        56: {'msg': 'Guide calibration accomplished'},
        57: {'msg': 'Guide calibration failed'},
        58: {'msg': 'Temporary battery problem'},
        59: {'msg': 'Temporary battery problem'},
        60: {'msg': 'Temporary battery problem'},
        61: {'msg': 'Temporary battery problem'},
        62: {'msg': 'Temporary battery problem'},
        63: {'msg': 'Temporary battery problem'},
        64: {'msg': 'Temporary battery problem'},
        65: {'msg': 'Temporary battery problem'},
        66: {'msg': 'Battery problem'},
        67: {'msg': 'Battery problem'},
        68: {'msg': 'Temporary battery problem'},
        69: {'msg': 'Alarm! Mower switched off'},
        70: {'msg': 'Alarm! Mower stopped'},
        71: {'msg': 'Alarm! Mower lifted'},
        72: {'msg': 'Alarm! Mower tilted'},
        73: {'msg': 'Alarm! Mower in motion'},
        74: {'msg': 'Alarm! Outside geofence'},
        75: {'msg': 'Connection changed'},
        76: {'msg': 'Connection NOT changed'},
        77: {'msg': 'Com board not available'},
        78: {'msg': 'Slipped - Mower has Slipped. Situation not solved with moving pattern'},
        79: {'msg': 'Invalid battery combination - Invalid combination of different battery types.'},
        80: {'msg': 'Cutting system imbalance'},
        81: {'msg': 'Safety function faulty'},
        82: {'msg': 'Wheel motor blocked, rear right'},
        83: {'msg': 'Wheel motor blocked, rear left'},
        84: {'msg': 'Wheel drive problem, rear right'},
        85: {'msg': 'Wheel drive problem, rear left'},
        86: {'msg': 'Wheel motor overloaded, rear right'},
        87: {'msg': 'Wheel motor overloaded, rear left'},
        88: {'msg': 'Angular sensor problem'},
        89: {'msg': 'Invalid system configuration'},
        90: {'msg': 'No power in charging station'},
        91: {'msg': 'Switch cord problem'},
        92: {'msg': 'Work area not valid'},
        93: {'msg': 'No accurate position from satellites'},
        94: {'msg': 'Reference station communication problem'},
        95: {'msg': 'Folding sensor activated'},
        96: {'msg': 'Right brush motor overloaded'},
        97: {'msg': 'Left brush motor overloaded'},
        98: {'msg': 'Ultrasonic Sensor 1 defect'},
        99: {'msg': 'Ultrasonic Sensor 2 defect'},
        100: {'msg': 'Ultrasonic Sensor 3 defect'},
        101: {'msg': 'Ultrasonic Sensor 4 defect'},
        102: {'msg': 'Cutting drive motor 1 defect'},
        103: {'msg': 'Cutting drive motor 2 defect'},
        104: {'msg': 'Cutting drive motor 3 defect'},
        105: {'msg': 'Lift Sensor defect'},
        106: {'msg': 'Collision sensor defect'},
        107: {'msg': 'Docking sensor defect'},
        108: {'msg': 'Folding cutting deck sensor defect'},
        109: {'msg': 'Loop sensor defect'},
        110: {'msg': 'Collision sensor error'},
        111: {'msg': 'No confirmed position'},
        112: {'msg': 'Cutting system major imbalance'},
        113: {'msg': 'Complex working area'},
        114: {'msg': 'Too high discharge current'},
        115: {'msg': 'Too high internal current'},
        116: {'msg': 'High charging power loss'},
        117: {'msg': 'High internal power loss'},
        118: {'msg': 'Charging system problem'},
        119: {'msg': 'Zone generator problem'},
        120: {'msg': 'Internal voltage error'},
        121: {'msg': 'High internal temerature'},
        122: {'msg': 'CAN error'},
        123: {'msg': 'Destination not reachable'}
    }

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

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.userid = self.get_parameter_value('userid')
        self.password = self.get_parameter_value('password')
        self.apikey = self.get_parameter_value('apikey')
        self.instance = self.get_parameter_value('device')
        self.historylength = int(self.get_parameter_value('historylength'))

        self.token = None
        self.tokenExp = 0

        self.mowerCount = 0
        self.mowerId = None
        self.mowerName = None
        self.mowerModel = None
        self.mowerSerial = None

        self.mowerTimestamp = LengthList(self.historylength, 0)
        self.mowerActivity = LengthList(self.historylength, '')
        self.mowerConnection = LengthList(self.historylength, False)
        self.mowerBatterypercent = LengthList(self.historylength, -1)
        self.mowerErrormsg = LengthList(self.historylength, '')
        self.mowerLongitude = LengthList(self.historylength, 0.0)
        self.mowerLatitude = LengthList(self.historylength, 0.0)

        self.message = 'Ok'

        # Initialization code goes here

        self._items_info = {}
        self._items_control = {}
        self._items_state = {}

        self.asyncLoop = None
        self.apiSession = None

        # On initialization error use:
        #   self._init_complete = False
        #   return

        # if plugin should start even without web interface
        self.init_webinterface()
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True

        self.runworker = True
        asyncio.run(self.worker())
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.runworker = False

        if self.asyncLoop:
            tsk = self.asyncLoop.create_task(self.destroy())
            tsk.add_done_callback(lambda t: self.stopfinished())
        else:
            self.logger.warning("No Eventloop")
            asyncio.run(self.destroy())
            self.alive = False

    def stopfinished(self):
        self.logger.debug("Finished destroy ")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """

        if self.has_iattr(item.conf, self.ITEM_INFO):
            self.logger.debug("parse INFO item: {}".format(item))

            value = self.get_iattr_value(item.conf, self.ITEM_INFO).lower()
            if value in self.VALID_INFOS:
                self.logger.debug("adding valid info item {0} to wachlist {1}={2} ".format(item, self.ITEM_INFO,
                                                                                           item.conf[
                                                                                               self.ITEM_INFO]))
                if value not in self._items_info:
                    self._items_info[value] = [item]
                else:
                    self._items_info[value].append(item)
                return self.update_item
            else:
                self.logger.error("info '{0}' invalid, use one of {1}".format(value, self.VALID_INFOS))

        if self.has_iattr(item.conf, self.ITEM_CONTROL):
            self.logger.debug("parse CONTROL item: {}".format(item))

            value = self.get_iattr_value(item.conf, self.ITEM_CONTROL).lower()
            if value in self.VALID_COMMANDS:
                self.logger.debug("adding valid command item {0} to wachlist {1}={2} ".format(item, self.ITEM_CONTROL,
                                                                                              item.conf[
                                                                                                  self.ITEM_CONTROL]))
                if value not in self._items_control:
                    self._items_control[value] = [item]
                else:
                    self._items_control[value].append(item)
                return self.update_item
            else:
                self.logger.error("command '{0}' invalid, use one of {1}".format(value, self.VALID_COMMANDS))

        if self.has_iattr(item.conf, self.ITEM_STATE):
            self.logger.debug("parse STATE item: {}".format(item))

            value = self.get_iattr_value(item.conf, self.ITEM_STATE).lower()
            if value in self.VALID_STATES:
                self.logger.debug("adding valid state item {0} to wachlist {1}={2} ".format(item, self.ITEM_STATE,
                                                                                            item.conf[self.ITEM_STATE]))
                if value not in self._items_state:
                    self._items_state[value] = [item]
                else:
                    self._items_state[value].append(item)
                return self.update_item
            else:
                self.logger.error("value '{0}' invalid, use one of {1}".format(value, self.VALID_STATES))

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            item_value = "{0}".format(item())
            self.logger.info(
                "Update item: {0}, item has been changed outside this plugin to value={1}".format(item.id(),
                                                                                                  item_value))
            if self.has_iattr(item.conf, self.ITEM_CONTROL):
                self.logger.debug(
                    "update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item,
                                                                                                               caller,
                                                                                                               source,
                                                                                                               dest))
                cmd = self.get_iattr_value(item.conf, self.ITEM_CONTROL).lower()

                self.sendCmd(cmd, item())

                # if control item is a bool type reset it to False after sending cmd
                if item.property.type == 'bool':
                    item(0, self.get_shortname())

    def sendCmd(self, cmd, value=-1):
        self.writeToStatusItem(self.translate("Sending command") + ": " + cmd)

        if self.asyncLoop:
            tsk = self.asyncLoop.create_task(self.send_worker(cmd, value))
            tsk.add_done_callback(lambda t: self.writeToStatusItem("Ok"))
        else:
            self.logger.warning("No Eventloop")

    def writeToStatusItem(self, txt):
        self.message = txt
        if 'message' in self._items_state:
            for item in self._items_state['message']:
                item(txt, self.get_shortname())

    def data_callback(self, status):
        """
        Callback for data updates of the device
        """

        if self.mowerId is None:
            return

        self.mowerCount = len(status['data'])

        data = None
        for mow in status['data']:
            if mow['id'] == self.mowerId:
                data = mow
                break

        if data is None:
            return

        if self.mowerTimestamp.get_last() >= data['attributes']['metadata']['statusTimestamp']:
            self.logger.debug("Data callback: Old Timestamp, not updating Items")
            return

        self.mowerTimestamp.push(data['attributes']['metadata']['statusTimestamp'])
        self.logger.debug("Data callback: " + json.dumps(data))

        self.mowerLongitude.push(data['attributes']['positions'][0]['longitude'])
        if 'longitude' in self._items_state:
            for item in self._items_state['longitude']:
                item(self.mowerLongitude.get_last(), self.get_shortname())
        self.mowerLatitude.push(data['attributes']['positions'][0]['latitude'])
        if 'latitude' in self._items_state:
            for item in self._items_state['latitude']:
                item(self.mowerLatitude.get_last(), self.get_shortname())
        self.mowerBatterypercent.push(data['attributes']['battery']['batteryPercent'])
        if 'batterypercent' in self._items_state:
            for item in self._items_state['batterypercent']:
                item(self.mowerBatterypercent.get_last(), self.get_shortname())
        errorcode = data['attributes']['mower']['errorCode']
        if errorcode in self.MOWERERROR:
            self.mowerErrormsg.push(self.translate(self.MOWERERROR[errorcode]['msg']))
        else:
            self.mowerErrormsg.push(self.translate('Unknown error code') + ": " + str(errorcode))
        if 'errormessage' in self._items_state:
            for item in self._items_state['errormessage']:
                item(self.mowerErrormsg.get_last(), self.get_shortname())
        self.mowerActivity.push(data['attributes']['mower']['activity'])
        if 'activity' in self._items_state:
            for item in self._items_state['activity']:
                item(self.translate(self.mowerActivity.get_last()), self.get_shortname())
        if 'state' in self._items_state:
            for item in self._items_state['state']:
                item(self.translate(data['attributes']['mower']['state']), self.get_shortname())
        if 'mode' in self._items_state:
            for item in self._items_state['mode']:
                item(self.translate(data['attributes']['mower']['mode']), self.get_shortname())
        self.mowerConnection.push(data['attributes']['metadata']['connected'])
        if 'connection' in self._items_state:
            for item in self._items_state['connection']:
                item(self.mowerConnection.get_last(), self.get_shortname())

        # settings
        if 'cuttingHeight' in data['attributes']:
            if 'cuttingheight' in self._items_control:
                for item in self._items_control['cuttingheight']:
                    item(data['attributes']['cuttingHeight'], self.get_shortname())
        else:
            if 'cuttingheight' in self._items_control:
                for item in self._items_control['cuttingheight']:
                    item(data['attributes']['settings']['cuttingHeight'], self.get_shortname())
        if 'headlight' in data['attributes']:
            if 'headlight' in self._items_control:
                for item in self._items_control['headlight']:
                    item(data['attributes']['headlight']['mode'], self.get_shortname())
        else:
            if 'headlight' in self._items_control:
                for item in self._items_control['headlight']:
                    item(data['attributes']['settings']['headlight']['mode'], self.get_shortname())

    def token_callback(self, token):
        """
        Callback for token updates of the api
        """

        self.token = token['access_token']
        self.tokenExp = token['expires_in']

        self.logger.debug("Token callback: " + json.dumps(token))

    async def worker(self):
        self.apiSession = aioautomower.AutomowerSession(self.apikey, token=None)

        self.asyncLoop = asyncio.get_event_loop()

        self.apiSession.register_data_callback(self.data_callback, schedule_immediately=True)
        self.apiSession.register_token_callback(self.token_callback, schedule_immediately=True)

        # Login to get a token and connect to the api
        await self.apiSession.login(self.userid, self.password)
        self.logger.debug(f"Logged in successfully as {self.userid}")

        await self.apiSession.connect()
        self.logger.debug("Connected successfully")

        # List data of all mowers
        status_all = await self.apiSession.get_status()
        self.logger.debug(f"Found {len(status_all['data'])} mower")

        self.mowerCount = len(status_all['data'])

        # Select desired mower
        for mow in status_all['data']:
            if mow['attributes']['system']['name'] == self.instance or mow['id'] == self.instance:
                self.mowerId = mow['id']
                self.mowerName = mow['attributes']['system']['name']
                self.mowerModel = mow['attributes']['system']['model']
                self.mowerSerial = mow['attributes']['system']['serialNumber']
                break

        # If desired mower is not available pick the first one
        if self.mowerId is None or self.mowerName is None:
            self.mowerId = status_all['data'][0]['id']
            self.mowerName = status_all['data'][0]['attributes']['system']['name']
            self.mowerModel = status_all['data'][0]['attributes']['system']['model']
            self.mowerSerial = status_all['data'][0]['attributes']['system']['serialNumber']

        self.logger.debug(f"Selected mower {self.mowerName} with id {self.mowerId}")

        if 'name' in self._items_info:
            for item in self._items_info['name']:
                item(self.mowerName, self.get_shortname())
        if 'id' in self._items_info:
            for item in self._items_info['id']:
                item(self.mowerId, self.get_shortname())
        if 'serial' in self._items_info:
            for item in self._items_info['serial']:
                item(self.mowerSerial, self.get_shortname())
        if 'model' in self._items_info:
            for item in self._items_info['model']:
                item(self.mowerModel, self.get_shortname())

        self.data_callback(status_all)

        while self.runworker:
            await asyncio.sleep(0.1)

        await self.apiSession.invalidate_token()
        self.logger.debug("Invalidated Token")
        await self.apiSession.close()
        self.logger.debug("Closed Session")

    async def destroy(self):
        asyncio.set_event_loop(self.asyncLoop)

        await self.apiSession.invalidate_token()
        self.logger.debug("Invalidated Token")
        await self.apiSession.close()
        self.logger.debug("Closed Session")

    async def send_worker(self, cmd, value):
        commands = {
            # Actions
            'startime': {'payload': '{"data": {"type": "Start", "attributes": {"duration": ' + str(int(value)) + '}}}',
                         'type': 'actions'},
            'pause': {'payload': '{"data": {"type": "Pause"}}', 'type': 'actions'},
            'parkpermanent': {'payload': '{"data": {"type": "ParkUntilFurtherNotice"}}', 'type': 'actions'},
            'parktime': {'payload': '{"data": {"type": "Park", "attributes": {"duration": ' + str(int(value)) + '}}}',
                         'type': 'actions'},
            'parknext': {'payload': '{"data": {"type": "ParkUntilNextSchedule"}}', 'type': 'actions'},
            'resume': {'payload': '{"data": {"type": "ResumeSchedule"}}', 'type': 'actions'},
            # Settings
            'cuttingheight': {
                'payload': '{"data": {"type": "settings", "attributes": {"cuttingHeight": ' + str(int(value)) + '}}}',
                'type': 'settings'},
            'headlightalwayson': {
                'payload': '{"data": {"type": "settings", "attributes": {"headlight": {"mode": "ALWAYS_ON"}}}}',
                'type': 'settings'},
            'headlightalwaysoff': {
                'payload': '{"data": {"type": "settings", "attributes": {"headlight": {"mode": "ALWAYS_OFF"}}}}',
                'type': 'settings'},
            'headlighteveningonly': {
                'payload': '{"data": {"type": "settings", "attributes": {"headlight": {"mode": "EVENING_ONLY"}}}}',
                'type': 'settings'},
            'headlighteveningnight': {
                'payload': '{"data": {"type": "settings", "attributes": {"headlight": {"mode": "EVENING_AND_NIGHT"}}}}',
                'type': 'settings'},
            'headLight': {'payload': '{"data": {"type": "settings", "attributes": {"headlight": {"mode": "' + str(
                value) + '"}}}}', 'type': 'settings'}
        }

        if cmd in commands:
            await self.apiSession.action(self.mowerId, commands[cmd]['payload'], commands[cmd]['type'])
            newstatus = await self.apiSession.get_status()
            self.data_callback(newstatus)
        else:
            self.logger.error("available commands: {}".format(commands.keys()))

    # ------------------------------------------
    #    Webinterface methods of the plugin
    # ------------------------------------------

    def get_mower_id(self):
        return self.mowerId

    def get_mower_name(self):
        return self.mowerName

    def get_mower_model_name(self):
        return self.mowerModel

    def get_mower_serial(self):
        return self.mowerSerial

    # get last Data
    def getLastActivity(self):
        return self.mowerActivity.get_last()

    def getLastConnection(self):
        return self.mowerConnection.get_last()

    def getLastBatterypercent(self):
        return self.mowerBatterypercent.get_last()

    def getLastErrormsg(self):
        return self.mowerErrormsg.get_last()

    def getLastLongitude(self):
        return self.mowerLongitude.get_last()

    def getLastLatitude(self):
        return self.mowerLatitude.get_last()

    def getLastCoordinates(self):
        maxpoints = 50
        lat = self.mowerLatitude.get_list()
        lon = self.mowerLongitude.get_list()

        if len(lat) < maxpoints:
            maxpoints = len(lat)
        if len(lon) < maxpoints:
            maxpoints = len(lon)

        coord = []
        for i in range(maxpoints):
            coord.append([lon[i], lat[i]])
        return coord

    # get entire historical Data
    def getTimestamps(self):
        stamps = []
        for data in self.mowerTimestamp.get_list():
            stamps.append(datetime.fromtimestamp(data / 1000.0).strftime("%d.%m.%Y %H:%M:%S"))
        return stamps

    def getActivities(self):
        return self.mowerActivity.get_list()

    def getBatterypercents(self):
        return self.mowerBatterypercent.get_list()

    def getLongitudes(self):
        return self.mowerLongitude.get_list()

    def getLatitudes(self):
        return self.mowerLatitude.get_list()

    def getTimedeltas(self):
        deltas = []
        now = time.time()
        for data in self.mowerTimestamp.get_list():
            min = int((now - (data / 1000.0)) / 60.0)
            sec = int((now - (data / 1000.0)) % 60.0)
            deltas.append(f"{min}:{sec}")
        return deltas

    def getErrormessages(self):
        return self.mowerErrormsg.get_list()

    def getToken(self):
        return self.token

    def getTokenExp(self):
        return self.tokenExp

    def getUserId(self):
        return self.userid

    def getApiKey(self):
        return self.apikey

    def getMessage(self):
        return self.message

    # webinterface init method
    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Not initializing the web interface")
            return False

        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface")
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True


# ------------------------------------------
#    Webinterface class of the plugin
# ------------------------------------------

class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')

        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, device_count=self.plugin.mowerCount, items_control=self.plugin._items_control,
                           items_state=self.plugin._items_state)

    @cherrypy.expose
    def mower_park(self):
        self.plugin.sendCmd('parkpermanent')

    @cherrypy.expose
    def mower_start(self):
        self.plugin.sendCmd('resume')

    @cherrypy.expose
    def mower_stop(self):
        self.plugin.sendCmd('pause')


# ------------------------------------------
#    Utils of the plugin
# ------------------------------------------

class LengthList(object):
    def __init__(self, maxLength, default=0):
        self.maxLength = maxLength
        self.default = default
        self.list = []

    def __len__(self):
        return len(self.list)

    def __getitem__(self, index):
        return self.list[index]

    def push(self, data):
        if len(self.list) == self.maxLength:
            self.list.pop(0)
        self.list.append(data)

    def get_list(self):
        return self.list

    def get_last(self):
        if len(self.list) > 0:
            return self.list[-1]
        else:
            return self.default

    def get_first(self):
        if len(self.list) > 0:
            return self.list[0]
        else:
            return self.default
