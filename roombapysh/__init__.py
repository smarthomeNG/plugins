#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2011 KNX-User-Forum e.V.            http://knx-user-forum.de/
#########################################################################
#  This file is part of SmartHome.py.    http://mknx.github.io/smarthome/
#
#  SmartHome.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

# This plugin is based on:
# https://github.com/pschmitt/roombapy
# The Roomba object provides following status:
# myroomba.roomba_connected, myroomba.error_code, myroomba.error_message, myroomba.client_error


import logging
import time
from lib.model.smartplugin import SmartPlugin
from lib.item import Items
import sys

sys.path.append("/usr/local/smarthome/plugins/roombapysh/roombapy/")
from roombapy import RoombaFactory


class ROOMBAPY(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.0.0"

    myroomba = None
    pluginStatus = 'not initialized'

    def __init__(self, sh):
        super().__init__()
        self._address = self.get_parameter_value("address")
        self._blid = self.get_parameter_value("blid")
        self._roombaPassword = self.get_parameter_value("roombaPassword")
        self._cycle = int(self.get_parameter_value("cycle"))

        self._status_items = {}

        self.myroomba = RoombaFactory.create_roomba(self._address, self._blid, self._roombaPassword, True)
        self.logger.debug('IP:{}, BLID:{}, PW:{}'.format(self._address, self._blid, self._roombaPassword))
        if self.myroomba is None:
            self.logger.error('Cannot create MyRoomba Object')
            self.pluginStatus = 'no MyRoomba object'
        else:
            self.pluginStatus = 'initialized'

    def parse_logic(self, logic):
        pass

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'roombapysh'):
            item_type = self.get_iattr_value(item.conf, 'roombapysh')
            self._status_items[item_type] = item
            self.logger.debug('found item {} with function {}'.format(item, item_type))
            if item_type in ['start', 'pause', 'resume', 'stop', 'dock', 'evac', 'reset', 'locate',
                             'connect']:  # List of valid commands
                return self.update_item

    def run(self):
        if self.myroomba is not None:
            self.get_status()
            self.alive = True

    def stop(self):
        if self.myroomba.roomba_connected:
            self.disconnect_roomba()
        self.alive = False

    def connect_roomba(self):
        if not self.myroomba.roomba_connected:
            try:
                self.myroomba.connect()
            except:
                self.get_status()
                self._status_items['connect']('false', __name__)
            finally:
                self.scheduler_add('get_status', self.get_status, prio=5, cycle=self._cycle, offset=2)

    def disconnect_roomba(self):
        if self.myroomba.roomba_connected:
            self.myroomba.disconnect()
            if self.scheduler_get('get_status') is not None:
                self.scheduler_remove('get_status')
            time.sleep(2)
            self.get_status()

    def __call__(self):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        # One of the items with a command of the item list in parse_item was changed
        # ['start','pause','resume','stop','dock','evac','reset','locate','connect']
        # Pass any other value than 'connect' to the roombapy library for execution

        if caller != __name__ and self.alive:
            self.logger.debug('item_update {} '.format(item))
            if self.get_iattr_value(item.conf, 'roombapysh') == "connect":
                if item() is True:
                    self.connect_roomba()
                else:
                    self.disconnect_roomba()
            else:
                if item() is True:
                    self.send_command(self.get_iattr_value(item.conf, 'roombapysh'))

    def get_status(self):
        if self.alive:
            status = self.myroomba.master_state

            for status_item in self._status_items:
                # states reported by roomba status message
                # ----------------------------------------
                if status_item == "name":
                    try:
                        self._status_items[status_item](status['state']['reported']['name'], __name__)
                    except:
                        pass
                # Batterie-Info
                elif status_item == "bat_cCount":
                    try:
                        self._status_items[status_item](status['state']['reported']['batInfo']['cCount'], __name__)
                    except:
                        pass
                elif status_item == "status_batterie":
                    try:
                        self._status_items[status_item](status['state']['reported']['batPct'], __name__)
                    except:
                        pass
                # Summenwerte über die gesamte Lebenszeit aus bbrun
                elif status_item == "run_nCliffs":
                    try:
                        self._status_items[status_item](status['state']['reported']['bbrun']['nCliffsF'], __name__)
                    except:
                        pass
                elif status_item == "run_nPanics":
                    try:
                        self._status_items[status_item](status['state']['reported']['bbrun']['nPanics'], __name__)
                    except:
                        pass
                elif status_item == "run_time":
                    try:
                        self._status_items[status_item](str(status['state']['reported']['bbrun']['hr']) + ':' + str(
                            status['state']['reported']['bbrun']['min']), __name__)
                    except:
                        pass
                elif status_item == "run_nScrubs":
                    try:
                        self._status_items[status_item](status['state']['reported']['bbrun']['nScrubs'], __name__)
                    except:
                        pass
                # Missionsanzahl aus bbmssn
                elif status_item == "mission_total":
                    try:
                        self._status_items[status_item](status['state']['reported']['bbmssn']['nMssn'], __name__)
                    except:
                        pass
                elif status_item == "mission_OK":
                    try:
                        self._status_items[status_item](status['state']['reported']['bbmssn']['nMssnOK'], __name__)
                    except:
                        pass
                elif status_item == "mission_err":
                    try:
                        self._status_items[status_item](status['state']['reported']['bbmssn']['nMssnF'], __name__)
                    except:
                        pass
                # aktueller Missions-Status
                elif status_item == "MissionStatus_cycle":
                    try:
                        self._status_items[status_item](status['state']['reported']['cleanMissionStatus']['cycle'],
                                                        __name__)
                    except:
                        pass
                elif status_item == "MissionStatus_phase":
                    try:
                        self._status_items[status_item](status['state']['reported']['cleanMissionStatus']['phase'],
                                                        __name__)
                    except:
                        pass
                elif status_item == "MissionStatus_error":
                    try:
                        self._status_items[status_item](status['state']['reported']['cleanMissionStatus']['error'],
                                                        __name__)
                    except:
                        pass
                elif status_item == "MissionStatus_startTime":
                    try:
                        self._status_items[status_item](
                            status['state']['reported']['cleanMissionStatus']['mssnStrtTm'] * 1000, __name__)
                    except:
                        pass
                elif status_item == "MissionStatus_expireTime":
                    try:
                        self._status_items[status_item](
                            status['state']['reported']['cleanMissionStatus']['expireTm'] * 1000, __name__)
                    except:
                        pass
                elif status_item == "MissionStatus_initiator":
                    try:
                        self._status_items[status_item](status['state']['reported']['cleanMissionStatus']['initiator'],
                                                        __name__)
                    except:
                        pass
                elif status_item == "MissionStatus_runTime":
                    self._status_items[status_item](
                        time.strftime('%H:%M:%S', time.gmtime(time.mktime(time.localtime(time.time())) -
                                                             status['state'][
                                                                 'reported'][
                                                                 'cleanMissionStatus'][
                                                                 'mssnStrtTm'])),
                        __name__)

                    try:
                        if self._status_items['status']() != 4:  # Roomba is not running
                            self._status_items[status_item]('', __name__)
                        else:
                            self._status_items[status_item](
                                time.strftime('%H:%M:%S', time.gmtime(time.mktime(time.localtime(time.time())) -
                                                                     status['state'][
                                                                         'reported'][
                                                                         'cleanMissionStatus'][
                                                                         'mssnStrtTm'])),
                                __name__)
                    except:
                        pass
                # Last Command
                elif status_item == "lastCommand_command":
                    try:
                        self._status_items[status_item](status['state']['reported']['lastCommand']['command'], __name__)
                    except:
                        pass
                elif status_item == "lastCommand_time":
                    try:
                        self._status_items[status_item](status['state']['reported']['lastCommand']['time'] * 1000,
                                                        __name__)
                    except:
                        pass
                elif status_item == "lastCommand_initiator":
                    try:
                        self._status_items[status_item](status['state']['reported']['lastCommand']['initiator'],
                                                        __name__)
                    except:
                        pass
                # Sonstiger allgemeiner Status
                elif status_item == "dock_known":
                    try:
                        self._status_items[status_item](status['state']['reported']['dock']['known'], __name__)
                    except:
                        pass
                elif status_item == "bin_present":
                    try:
                        self._status_items[status_item](status['state']['reported']['bin']['present'], __name__)
                    except:
                        pass
                elif status_item == "bin_full":
                    try:
                        self._status_items[status_item](status['state']['reported']['bin']['full'], __name__)
                    except:
                        pass
                # states reported from roombapy
                # -----------------------------
                if status_item == "connected":
                    self._status_items[status_item](self.myroomba.roomba_connected, __name__)
                if status_item == "error_code":
                    self._status_items[status_item](self.myroomba.error_code, __name__)
                if status_item == "error_message":
                    self._status_items[status_item](self.myroomba.error_message, __name__)
                if status_item == "mission_state":
                    self._status_items[status_item](self.myroomba.current_state, __name__)
                if status_item == "client_error":
                    if self.myroomba.roomba_connected:
                        self._status_items[status_item]('OK', __name__)
                    elif self.myroomba.client_error is None:
                        self._status_items[status_item]('getrennt', __name__)
                    else:
                        self._status_items[status_item](self.myroomba.client_error, __name__)
                if status_item == "status":  # overall status: 0=not connected, 1=unknown, 2=charging, 3=charging (full), 4=running, 5=pause/stop, 6=going to dock, 7=error
                    try:
                        _mission_phase = status['state']['reported']['cleanMissionStatus']['phase']
                    except:
                        _mission_phase = 'unknown'
                    try:
                        _battery_state = status['state']['reported']['batPct']
                    except:
                        _battery_state = 0
                    try:
                        _bin_full = status['state']['reported']['bin']['full']
                    except:
                        _bin_full = False
                    if not self.myroomba.roomba_connected:
                        self._status_items[status_item](0, __name__)
                    elif (not self.myroomba.error_code == 0) or _bin_full:
                        self._status_items[status_item](7, __name__)
                    elif _mission_phase == 'charge':
                        if _battery_state < 99:
                            self._status_items[status_item](2, __name__)
                        else:
                            self._status_items[status_item](3, __name__)
                    elif _mission_phase == 'run':
                        self._status_items[status_item](4, __name__)
                    elif _mission_phase == 'stop':
                        self._status_items[status_item](5, __name__)
                    elif _mission_phase == 'hmUsrDock':
                        self._status_items[status_item](6, __name__)
                    else:
                        self._status_items[status_item](1, __name__)
            self.logger.debug('Status update')

    def send_command(self, command):
        if self.myroomba is not None:
            self.myroomba.send_command(command)
            self.logger.debug('send command: {} to Roomba'.format(command))

