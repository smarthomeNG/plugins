#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2023-      Martin Sinn                         m.sinn@gmx.de
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


# ----------------------------------------------------
#    Class for handling notifications ofB&O devices
# ----------------------------------------------------

import json
import requests
import threading
import logging

class beo_notifications():

    ip = None
    friendlyName = None
    state = '?'

    device_dict = None

    progress = {}
    source = {}
    playing = {}
    volume = {}
    swupdate = {}

    _r = None


    def __init__(self, ip=None, device_dict=None, beodevices=None, logger=None, logger_name=None):

        if logger is None and logger_name is None:
            self.logger = logging.getLogger(__name__)
        elif logger_name is not None:
            self.logger = logging.getLogger(logger_name)
        else:
            self.logger = logger

        self.device_dict = device_dict
        if device_dict is not None:
            ip = device_dict['device']['ip']

        if ip is None:
            self.logger.error(f"No ip address specified for Beolink device")
            return

        self.ip = ip
        self.friendlyName =  ip
        if device_dict is not None:
            self.friendlyName = device_dict['device'].get('FriendlyName', ip)

        self.lock = threading.Lock()
        self.log_notification( msg=f"--- New instance of class beo_notifications ---", level='dbghigh')


    def log_notification(self, notification=None, msg=None, handled=True, level=None):

        msg_time = ""
        if notification is None:
            log_msg = f"{msg_time}{self.friendlyName:13}{msg}"
        else:
            #msg_time =f"{notification['timestamp'].split('T')[1].split('.')[0]} "
            if msg is None:
                msg = notification['type']
                if not handled:
                    msg = f"({msg}): kind={notification['kind']}"
                elif level is None:
                    level = 'dbghigh'
                msg = f"{msg}: data={notification['data']}"
            else:
                msg = f"{notification['type']}: {msg}"

            log_msg = f"{msg_time}{self.friendlyName:13}{msg}"

        try:
            if level is None:
                self.logger.info(log_msg)
            elif level.lower() == 'dbghigh':
                self.logger.dbgmed( log_msg )
            elif level.lower() == 'dbgmed':
                self.logger.dbgmed( log_msg )
            elif level.lower() == 'dbglow':
                self.logger.dbglow(log_msg)
            elif level.lower() == 'debug':
                self.logger.debug(log_msg)
            elif level.lower() == 'info':
                self.logger.info(log_msg)
            elif level.lower() == 'warning':
                self.logger.warning(log_msg)
            else:
                log_msg = log_msg + ', level=' + level.lower()
                self.logger.info( log_msg )
        except:
            self.logger.warning(log_msg)

    def notification_playing_net_radio(self, notification):

        data = notification['data']
        self.playing['name'] = data['name']
        self.playing['genre'] = data['genre']
        self.playing['liveDescription'] = data['liveDescription']

        self.log_notification(notification, msg=f"name={self.playing['name']}, genre={self.playing['genre']}, liveDescription={self.playing['liveDescription']}" )


    def process_notification(self, line):

        try:
            line_dict = json.loads(line)
        except Exception as e:
            self.logger.exception(f"process_notification: Exception 1 {e}")
            #print(f"Fehler: {e}")
            return

        try:
            if self.ip != self.device_dict['device'].get('ip', None):
                self.log_notification(msg=f"WRONG DEVICE - self.ip={self.ip}, device_dict ip={self.device_dict['device'].get('ip', None)}", level='warning')
        except Exception as e:
            self.logger.exception(f"process_notification: Exception 2 {e}")
        notification = line_dict['notification']
        notification_type = notification['type']
        data = notification['data']

        if self.device_dict.get('content', None) is None:
            self.device_dict['content'] = {}

        # process notification types
        if notification_type == 'PROGRESS_INFORMATION':
            changed = False
            data = notification['data']
            if data['state'] != self.progress.get('state', ''):
                if self.device_dict is not None:
                    self.device_dict['content']['state'] = data['state']
                self.progress['state'] = data['state']
                changed = True
            if data.get('playQueueItemId', None) is None:
                self.progress['playQueueItemId'] = ''
                if self.device_dict is not None:
                    self.device_dict['content']['playQueueItemId'] = ''
                changed = True
            elif data['playQueueItemId'] != self.progress.get('playQueueItemId', ''):
                self.progress['playQueueItemId'] = data['playQueueItemId']
                if self.device_dict is not None:
                    self.device_dict['content']['playQueueItemId'] = data['playQueueItemId']
                changed = True

            if changed:
                self.log_notification(notification)

        elif notification_type == 'SOURCE':
            experience = data.get('primaryExperience', None)
            if experience is not None:
                self.source['state'] = experience['state']
                self.source['friendlyName'] = experience['source']['friendlyName']
                self.source['deviceFriendlyName'] = experience['source']['product']['friendlyName']
                self.friendlyName = self.source['deviceFriendlyName']
                self.logger.info(f"{self.ip}: SOURCE friendlyName={self.source['deviceFriendlyName']} - data={data}")
                self.logger.info(f"{self.ip}:  - self.device_dict={self.device_dict}")
                self.source['type'] = experience['source']['sourceType']['type']
                self.source['category'] = experience['source']['category']
                self.source['inUse'] = experience['source']['inUse']
                # self.source['profile'] = experience['source']['profile']
                self.source['linkable'] = experience['source']['linkable']
                # self.source['contentProtection'] = experience['source']['contentProtection']
                if self.device_dict is not None:
                    self.device_dict['content']['state'] = experience['state']
                    self.device_dict['device']['FriendlyName'] = experience['source']['product']['friendlyName']
                    if self.device_dict.get('source', None) is None:
                        self.device_dict['source'] = {}
                    self.device_dict['source']['friendlyName'] = experience['source']['friendlyName']
                    self.device_dict['source']['type'] = experience['source']['sourceType']['type']
                    self.device_dict['source']['category'] = experience['source']['category']
                    self.device_dict['source']['inUse'] = experience['source']['inUse']
                    # self.device_dict['source']['profile'] = experience['source']['profile']
                    self.device_dict['source']['linkable'] = experience['source']['linkable']

                self.log_notification(notification)
                #self.log_notification(notification, msg=f"source={self.source}")
            else:
                self.log_notification(notification)

        elif notification_type == 'NOW_PLAYING_NET_RADIO':
            self.playing['name'] = data['name']
            self.playing['genre'] = data['genre']
            self.playing['liveDescription'] = data['liveDescription']
            if self.device_dict is not None:
                self.device_dict['content']['channel_name'] = data['name']
                self.device_dict['content']['genre'] = data['genre']
                self.device_dict['content']['title'] = data['liveDescription']

            self.log_notification(notification, msg=f"name={self.playing['name']}, genre={self.playing['genre']}, liveDescription={self.playing['liveDescription']}" )

        elif notification_type == 'NUMBER_AND_NAME':
            if self.device_dict is not None:
                self.device_dict['content']['channel_number'] = data['number']
                self.device_dict['content']['channel_name'] = data['name']
                dvb = data.get('dvb', None)
                if dvb:
                    self.device_dict['source']['tuner'] = data['dvb'].get('tuner', '')
            self.log_notification(notification )

        elif notification_type == 'VOLUME':
            self.volume['level'] = data['speaker']['level']
            self.volume['muted'] = data['speaker']['muted']
            self.volume['min'] = data['speaker']['range']['minimum']
            self.volume['max'] = data['speaker']['range']['maximum']
            if self.device_dict is not None:
                if self.device_dict.get('volume', None) is None:
                    self.device_dict['volume'] = {}
                self.device_dict['volume']['level'] = data['speaker']['level']
                self.device_dict['volume']['muted'] = data['speaker']['muted']
                self.device_dict['volume']['minimum'] = data['speaker']['range']['minimum']
                self.device_dict['volume']['maximum'] = data['speaker']['range']['maximum']

            self.log_notification( notification )

        # elif notification_type == 'SOFTWARE_UPDATE_STATE':
        #     self.swupdate = {}
        #     self.swupdate['state'] = data['state']
        #     if data.get('error', None) is not None:
        #         self.swupdate['updstate'] = data['error']['state']
        #         self.swupdate['code'] = data['error']['code']
        #         self.swupdate['text'] = data['error']['text']
        #
        #     self.log_notification(notification, msg=f"state={self.swupdate.get('state', '')}, updstate={self.swupdate.get('updstate', '')}" )

        elif notification_type in('KEYBOARD', 'TRACKPAD', 'SOFTWARE_UPDATE_STATE'):
            self.log_notification(notification, handled=False, level='dbghigh')

        else:
            self.log_notification(notification, handled=False)


    def open_stream(self):

        self.log_notification(msg=f"_CONNECT_: Opening connection to {self.ip}...", level='dbghigh' )
        try:
            self._r = requests.get(f"http://{self.ip}:8080/BeoZone/Notifications", stream=True)
        except Exception as e:
            self.log_notification(msg=f"Exception while opening: {e}", level='dbglow')
            if self.state != 'off':
                self.log_notification(msg=f"_CONNECT_: Device ist offline", level='dbghigh')
            self.state = 'off'
            self._r = None
            return

        if self._r.encoding is None:
            self._r.encoding = 'utf-8'
        self.state = 'on'
        self.log_notification(msg=f"_CONNECT_: Connection opened", level='dbghigh' )

        self.lines = self._r.iter_lines(decode_unicode=True)
        return


    def close_stream(self):

        if self._r is not None:
            loop = True
            while loop:
                line = next(self.lines, 'OFFLINE')
                if line == 'OFFLINE':
                    line = None
                if line:
                    self.process_notification(line)
                else:
                    loop = False

            self._r.close()
        return


    def process_stream(self):


        if not self.lock.acquire(blocking=False):
            self.log_notification(msg=f"Skipping, process_stream() is locked", level='debug')
            return

        if self._r is None:
            self.open_stream()
            if self._r is None:
                self.log_notification(msg=f"process_stream() unlocked because stream could not be opened", level='dbglow')
                self.lock.release()
                return

        try:
            loop = True
            while loop:
                line = next(self.lines, 'OFFLINE')
                if line == 'OFFLINE':
                    line = None
                    self._r = None
                    self.log_notification(msg=f"_LOOP_: Device ging offline", level='dbghigh')
                    self.log_notification(msg=f"process_stream() unlocked (offline)", level='dbglow')
                    self.lock.release()
                    return

                if line:
                    self.process_notification(line)
                else:
                    loop = False
        except Exception as e:
            self.log_notification(msg=f"process_stream: Exception {e}")

        self.log_notification(msg=f"process_stream() unlocked", level='debug')
        self.lock.release()

