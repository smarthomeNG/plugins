#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 <AUTHOR>                                        <EMAIL>
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
#########################################################################
import json

import logging
import os
from time import sleep
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from lib.model.smartplugin import SmartPlugin
from plugins.intercom_2n.core import IPCam
import threading

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class Intercom2n(SmartPlugin):
    PLUGIN_VERSION = "1.3.0.1"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh, intercom_ip, ssl=False, auth_type=0, username=None, password=None):
        self._sh = sh
        self.is_stopped = False
        self.sid = None
        self._logger = logging.getLogger(__name__)
        self.event_timeout = 30
        self.ip_cam = IPCam(intercom_ip, ssl=ssl, auth_type=auth_type, user=username, password=password)

        # item dictionaries for events
        self.possible_events = [
            "KeyPressed",
            "KeyReleased",
            "InputChanged",
            "OutputChanged",
            "CardEntered",
            "CardHeld",
            "CallStateChanged",
            "AudioLoopTest",
            "CodeEntered",
            "DeviceState",
            "MotionDetected",
            "RegistrationStateChanged",
            "SwitchStateChanged",
            "NoiseDetected",
            "TamperSwitchActivated",
            "UnauthorizedDoorOpen",
            "DoorOpenTooLong",
            "LoginBlocked",
            "PairingStateChanged",
            "UserAuthenticated"
        ]
        self.registered_events = {}
        self.get_event_thread = threading.Thread(target=self.get_events)
        self.get_event_thread.setDaemon(True)

    def get_events(self):

        while True:
            try:
                if self.sid is None:
                    # subscribe to pull channel
                    # since the channel is extended automatically by accessing it with a pull requests,
                    # we just have to make sure, the subscription timeout value is a bit higher than the timeout value
                    data = json.loads(self.ip_cam.commands.log_subscribe(include='new', duration=self.event_timeout + 10))

                    if 'success' not in data:
                        raise Exception('Invalid subscription response: {err}'.format(err=data))
                    if not data['success']:
                        raise Exception('{err}'.format(err=data))

                    if 'id' in data['result']:
                        self.sid = data['result']['id']
                        self._logger.debug('2n: sid={id}'.format(id=self.sid))

                if self.sid is not None:
                    self.parse_event_data(self.ip_cam.commands.log_pull(self.sid, timeout=self.event_timeout+10))
                else:
                    raise Exception("no sid")
            except Exception as err:
                if self.is_stopped:
                    return
                self._logger.debug("2N:" + str(err))
                self.sid = None
                sec = 20
                self._logger.debug("2N: retrying in {sec} seconds".format(sec=sec))
                sleep(sec)

    def parse_event_data(self, raw_data):
        try:
            raw_data =json.loads(raw_data)
        except Exception:
            self._logger.warning("Unknown 2n_event: '{event}' not in dictionary format.".format(event=raw_data))
            return
        if 'success' not in raw_data:
            self._logger.warning("Unknown 2n_event: {event}".format(event=raw_data))
            return
        if not raw_data['success']:
            self._logger.error("2N error: {event}".format(event=raw_data))
            return
        data = raw_data['result']

        # data['events'] is a list of events
        if 'events' not in data:
            self._logger.warning("Unknown 2n_event: {event}".format(event=data))

        for event in data['events']:
            # key 'name' has to be in every valid event
            if 'event' not in event:
                self._logger.warning("Unhandled 2n_event '{event}'.".format(event=event))
                return
            event_name = event['event']

            if event_name not in self.registered_events:
                self._logger.warning(" 2n_event '{event}: not item registered".format(event=event))
                return

            # uncomment this to set the complete dict to the root item
            # in items.conf, add type = dict to root item
            # e.g.:
            # [CallState]
            #     type = dict
            #     event_2n = CallStateChanged
            #

            '''
            if 'root' in self.registered_events[event_name]:
                for item in self.registered_events[event_name]['root']:
                    item(event)
            '''

            # loop through event data and set their registered items
            if 'params' not in event:
                self._logger.warning("Unknown 2n_event '{event}'. Parameter section not found.".format(event=event))
                return

            for key, value in event['params'].items():
                if key in self.registered_events[event_name]:
                    for item in self.registered_events[event_name][key]:
                        item(value)

    def run(self):
        self._logger.debug("2N: run method called")
        self.get_event_thread.start()
        self.alive = True

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'event_2n'):
            event_name = \
                self.get_iattr_value(item.conf, 'event_2n')
            if event_name in self.possible_events:
                if event_name not in self.registered_events:
                    self.registered_events[event_name]['root'] = [item]
                else:
                    if 'root' not in self.registered_events[event_name]:
                        self.registered_events[event_name]['root'] = [item]
                    else:
                        self.registered_events[event_name]['root'].append(item)

        # look for child items
        if self.has_iattr(item.conf, 'event_data_2n'):
            event_data = self.get_iattr_value(item.conf, 'event_data_2n')
            # in order to match the item to a specific event data, we need a parent item with a proper
            # event name
            parent_item = item.return_parent()
            if parent_item is not None:
                if self.has_iattr(parent_item.conf, 'event_2n'):
                    event_name = self.get_iattr_value(parent_item.conf, 'event_2n')
                    if event_name in self.possible_events:
                        if event_name not in self.registered_events:
                            self.registered_events[event_name] = {}
                        if event_data not in self.registered_events[event_name]:
                            self.registered_events[event_name][event_data] = [item]
                        else:
                            self.registered_events[event_name][event_data].append(item)

        return self.update_item

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller == "2n_Intercom":
            return
        if item is None:
            return

        if self.has_iattr(item.conf, 'command_2n'):
            command = self.get_iattr_value(item.conf, 'command_2n').lower()
        else:
            return

        if command != 'execute':
            return

        if not self.to_bool(item()):
            return

        # we have a valid 'execute' item, now we want the parent item
        parent_item = item.return_parent()
        if parent_item is None or not self.has_iattr(parent_item.conf, 'command_2n'):
            return
        command = self.get_iattr_value(parent_item.conf, 'command_2n').lower()

        try:
            if command == 'system_info':
                parent_item(self.ip_cam.commands.system_info())
            elif command == 'system_status':
                parent_item(self.ip_cam.commands.system_status())
            elif command == 'system_restart':
                parent_item(self.ip_cam.commands.system_restart())
            elif command == 'firmware_upload':
                # check for child item firmware_filepath
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "firmware_file":
                        if os.path.exists(child_item()):
                            parent_item(self.ip_cam.commands.firmware_upload(child_item()))
            elif command == 'firmware_apply':
                parent_item(self.ip_cam.commands.firmware_apply())
            elif command == 'config_get':
                # check for child item config_file
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "config_file":
                        parent_item(self.ip_cam.commands.config_get(filename=child_item()))
                        break
            elif command == 'config_upload':
                # check for child item firmware_filepath
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "config_file":
                        if os.path.exists(child_item()):
                            parent_item(self.ip_cam.commands.config_upload(child_item()))
            elif command == 'factory_reset':
                parent_item(self.ip_cam.commands.factory_reset())
            elif command == 'switch_caps':
                parent_item(self.ip_cam.commands.switch_caps())
            elif command == 'switch_status':
                switch = None
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "switch":
                        switch = child_item()
                        break
                parent_item(self.ip_cam.commands.switch_status(switch))
            elif command == 'switch_control':
                switch = None
                action = None
                response = None
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "switch":
                        switch = child_item()
                    elif path == "action":
                        action = child_item()
                    elif path == "response":
                        response = child_item()
                    else:
                        continue
                parent_item(self.ip_cam.commands.switch_control(switch, action, response))
            elif command == 'io_caps':
                port = None
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "port":
                        port = child_item()
                        break
                parent_item(self.ip_cam.commands.io_caps(port))
            elif command == 'io_status':
                port = None
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "port":
                        port = child_item()
                        break
                parent_item(self.ip_cam.commands.io_status(port))
            elif command == 'io_control':
                port = None
                action = None
                response = None
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "port":
                        port = child_item()
                    elif path == "action":
                        action = child_item()
                    elif path == "response":
                        response = child_item()
                    else:
                        continue
                parent_item(self.ip_cam.commands.io_control(port, action, response))
            elif command == 'phone_status':
                account = None
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "account":
                        account = child_item()
                        break
                parent_item(self.ip_cam.commands.phone_status(account))
            elif command == 'call_status':
                    session = None
                    child_items = parent_item.return_children()
                    for child_item in  child_items:
                        path = child_item._name.replace(parent_item._name,'').lstrip('.')
                        if path == "session":
                            session = child_item()
                            break
                    parent_item(self.ip_cam.commands.call_status(session))
            elif command == 'call_dial':
                    number = None
                    child_items = parent_item.return_children()
                    for child_item in  child_items:
                        path = child_item._name.replace(parent_item._name,'').lstrip('.')
                        if path == "number":
                            number = child_item()
                            break
                    parent_item(self.ip_cam.commands.call_dial(number))
            elif command == 'call_answer':
                    session = None
                    child_items = parent_item.return_children()
                    for child_item in  child_items:
                        path = child_item._name.replace(parent_item._name,'').lstrip('.')
                        if path == "session":
                            session = child_item()
                            break
                    parent_item(self.ip_cam.commands.call_answer(session))
            elif command == 'call_hangup':
                    session = None
                    reason = None
                    child_items = parent_item.return_children()
                    for child_item in  child_items:
                        path = child_item._name.replace(parent_item._name,'').lstrip('.')
                        if path == "session":
                            session = child_item()
                        if path == "reason":
                            reason = child_item()
                    parent_item(self.ip_cam.commands.call_hangup(session, reason))
            elif command == 'camera_caps':
                parent_item(self.ip_cam.commands.camera_caps())
            elif command == 'camera_snapshot':
                snapshot_file = None
                width = None
                height = None
                source = None
                time = None
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "snapshot_file":
                        snapshot_file = child_item()
                    if path == "width":
                        width = child_item()
                    if path == "height":
                        height = child_item()
                    if path == "source":
                        source = child_item()
                    if path == "time":
                        time == child_item()
                parent_item(self.ip_cam.commands.camera_snapshot(width, height, snapshot_file, source, time))
            elif command == 'display_caps':
                parent_item(self.ip_cam.commands.display_caps())
            elif command == 'display_upload_image':
                gif_file = None
                display = None
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "gif_file":
                        gif_file = child_item()
                    if path == "display":
                        display = child_item()
                parent_item(self.ip_cam.commands.display_upload_image(display, gif_file))
            elif command == 'display_delete_image':
                    display = None
                    child_items = parent_item.return_children()
                    for child_item in  child_items:
                        path = child_item._name.replace(parent_item._name,'').lstrip('.')
                        if path == "display":
                            display = child_item()
                            break
                    parent_item(self.ip_cam.commands.display_delete_image(display))
            elif command == 'log_caps':
                parent_item(self.ip_cam.commands.log_caps())
            elif command == 'audio_test':
                parent_item(self.ip_cam.commands.audio_test())
            elif command == 'email_send':
                to = None
                width = None
                height = None
                subject = None
                body = None
                picture_count = None
                timespan = None
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "to":
                        to = child_item()
                    if path == "width":
                        width = child_item()
                    if path == "height":
                        height = child_item()
                    if path == "subject":
                        subject = child_item()
                    if path == "body":
                        body = child_item()
                    if path == "picture_count":
                        picture_count = child_item()
                    if path == "timespan":
                        timespan = child_item()
                parent_item(self.ip_cam.commands.email_send(to, subject, width, height, body, picture_count, timespan))
            elif command == 'pcap':
                pcap_file = None
                child_items = parent_item.return_children()
                for child_item in  child_items:
                    path = child_item._name.replace(parent_item._name,'').lstrip('.')
                    if path == "pcap_file":
                        pcap_file = child_item()
                        break
                parent_item(self.ip_cam.commands.pcap(pcap_file))
            elif command == 'pcap_restart':
                parent_item(self.ip_cam.commands.pcap_restart())
            elif command == 'pcap_stop':
                parent_item(self.ip_cam.commands.pcap_stop())
            else:
                pass
        except Exception as err:
            error_dic = {
                'success': False,
                'error': str(err)
            }
            parent_item(json.dumps(error_dic))
