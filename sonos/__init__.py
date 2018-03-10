#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 pfischi                                               #
#########################################################################
#  This file is part of SmartHomeNG.   
#
#  Sonos plugin to run with SmartHomeNG version 1.3
#  upwards.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3
#  of the License, or
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

import os
import logging
import re
import socketserver
import subprocess
import threading
from collections import OrderedDict
from http.server import HTTPServer, BaseHTTPRequestHandler
from queue import Empty
import sys
from urllib.parse import unquote
import requests
import xmltodict
from requests.utils import quote
from tinytag import TinyTag
from plugins.sonos.soco.exceptions import SoCoUPnPException
from plugins.sonos.soco.music_services import MusicService
from lib.item import Item
from plugins.sonos.soco import *
from lib.model.smartplugin import SmartPlugin
from plugins.sonos.soco.data_structures import to_didl_string, DidlItem, DidlMusicTrack
from plugins.sonos.soco.events import event_listener
from plugins.sonos.soco.music_services.data_structures import get_class
from plugins.sonos.soco.snapshot import Snapshot
from plugins.sonos.soco.xml import XML
import time

from plugins.sonos.tts import gTTS
from plugins.sonos.utils import file_size, get_tts_local_file_path, get_free_diskspace, get_folder_size

_create_speaker_lock = threading.Lock()  # make speaker object creation thread-safe
sonos_speaker = {}


class WebserviceHttpHandler(BaseHTTPRequestHandler):
    webroot = None

    def __init__(self, request, client_address, server):
        self._logger = logging.getLogger('sonos')  # get a unique logger for the plugin and provide it internally
        super().__init__(request, client_address, server)

    def _get_mime_type_by_filetype(self, file_path):
        try:
            mapping = {
                "audio/aac": "aac",
                "audio/mp4": "mp4",
                "audio/mpeg": "mp3",
                "audio/ogg": "ogg",
                "audio/wav": "wav",
            }

            filename, extension = os.path.splitext(file_path)
            extension = extension.strip('.').lower()

            for mime_type, key in mapping.items():
                if extension == key:
                    return mime_type
            raise Exception("Could not found mime-type for extension '{ext}'.".format(ext=extension))

        except Exception as err:
            self._logger.warning(err)
            return None

    def do_GET(self):
        try:
            if WebserviceHttpHandler.webroot is None:
                self.send_error(404, 'Service Not Enabled')
                return

            file_name = unquote(self.path)
            # prevent path traversal
            file_name = os.path.normpath('/' + file_name).lstrip('/')

            # search file in snippet and tts folder
            file_path = os.path.join(WebserviceHttpHandler.snippet_folder, file_name)
            if not os.path.exists(file_path):
                file_path = os.path.join(WebserviceHttpHandler.webroot, file_name)
                if not os.path.exists(file_path):
                    self.send_error(404, 'File Not Found: %s' % self.path)
                    return

            # get registered mime-type
            mime_type = self._get_mime_type_by_filetype(file_path)

            if mime_type is None:
                self.send_error(406, 'File With Unsupported Media-Type : %s' % self.path)
                return

            client = "{ip}:{port}".format(ip=self.client_address[0], port=self.client_address[1])
            self._logger.debug("Webservice: delivering file '{path}' to client ip {client}.".format(path=file_path,
                                                                                                    client=client))
            file = open(file_path, 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', sys.getsizeof(file))
            self.end_headers()
            self.wfile.write(file)
        except Exception as ex:
            self._logger.error("Error delivering file {file}".format(file=file_path))
            self._logger.error(ex)
        finally:
            self.connection.close()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    allow_reuse_address = True

    def shutdown(self):
        self.socket.close()
        HTTPServer.shutdown(self)


class SimpleHttpServer:
    def __init__(self, ip, port, tts_folder, snippet_folder):
        self.server = ThreadedHTTPServer((ip, port), WebserviceHttpHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        WebserviceHttpHandler.webroot = tts_folder
        WebserviceHttpHandler.snippet_folder = snippet_folder

    def start(self):
        self.thread.start()

    def waitForThread(self):
        self.thread.join()

    def stop(self):
        self.server.shutdown()
        self.waitForThread()


class SubscriptionHandler(object):
    def __init__(self, endpoint, service, logger):
        self._lock = threading.Lock()
        self._thread = None
        self._service = service
        self._endpoint = endpoint
        self._event = None
        self._signal = None
        self._logger = logger

    def subscribe(self):
        with self._lock:
            self._signal = threading.Event()
            try:
                self._event = self._service.subscribe(auto_renew=True)
            except Exception as err:
                self._logger.warning("Sonos: {err}".format(err=err))
            if self._event:
                self._thread = threading.Thread(target=self._endpoint, args=(self,))
                self._thread.start()

    def unsubscribe(self):
        with self._lock:
            if self._event:
                # try to unsubscribe first
                try:
                    self._event.unsubscribe()
                except Exception as err:
                    self._logger.warning("Sonos: {err}".format(err=err))
                self._signal.set()

    @property
    def signal(self):
        return self._signal

    @property
    def service(self):
        return self._service

    @property
    def event(self):
        return self._event

    @property
    def service(self):
        return self._service

    @property
    def is_subscribed(self):
        if self._event:
            return self._event.is_subscribed
        return False


class Speaker(object):
    def __init__(self, uid, logger):
        self._logger = logger
        self.uid_items = []
        self._uid = ""
        self._soco = None
        self._events = None
        self._zone_group = []
        self.zone_group_members_items = []
        self._members = []
        self.play_items = []
        self._play = False
        self.pause_items = []
        self._pause = False
        self.stop_items = []
        self._stop = False
        self._mute = False
        self.mute_items = []
        self._status_light = False
        self.status_light_items = []
        self._is_coordinator = None
        self.is_coordinator_items = []
        self.coordinator_items = []
        self._coordinator = ""
        self._volume = 0
        self.volume_items = []
        self.bass_items = []
        self._bass = 0
        self.treble_items = []
        self._treble = 0
        self.loudness_items = []
        self._loudness = False
        self.night_mode_items = []
        self._night_mode = False
        self.dialog_mode_items = []
        self._dialog_mode = False
        self.cross_fade_items = []
        self._cross_fade = False
        self.snooze_items = []
        self._snooze = 0
        self._play_mode = ''
        self.play_mode_items = []
        self._player_name = ''
        self.player_name_items = []
        self._household_id = ''
        self.household_id_items = []
        self._track_uri = ''
        self.track_uri_items = []
        self._streamtype = ''
        self.streamtype_items = []
        self._current_track = 0
        self.current_track_items = []
        self._number_of_tracks = 0
        self.number_of_tracks_items = []
        self._current_track_duration = ""
        self.current_track_duration_items = []
        self._current_transport_actions = ""
        self.current_transport_actions_items = []
        self._current_valid_play_modes = ""
        self.current_valid_play_modes_items = []
        self._track_artist = ""
        self.track_artist_items = []
        self._track_title = ""
        self.track_title_items = []
        self._track_album = ""
        self.track_album_items = []
        self._track_album_art = ""
        self.track_album_art_items = []
        self._radio_station = ""
        self.radio_station_items = []
        self._radio_show = ""
        self.radio_show_items = []
        self._stream_content = ""
        self.stream_content_items = []
        self.sonos_playlists_items = []
        self._is_initialized = False
        self.is_initialized_items = []
        self._snippet_queue_lock = threading.Lock()
        self.av_subscription = None
        self.render_subscription = None
        self.system_subscription = None
        self.zone_subscription = None
        self.alarm_subscription = None
        self.device_subscription = None

    @property
    def uid(self):
        return self._uid

    @uid.setter
    def uid(self, value):
        self._uid = value
        for item in self.uid_items:
            item(self.uid, 'Sonos')

    @property
    def soco(self):
        return self._soco

    @soco.setter
    def soco(self, value):
        if self._soco != value:
            self._soco = value
            self._logger.debug("Sonos: {uid}: soco set to {value}".format(uid=self.uid, value=value))
            if self._soco:
                self.render_subscription = \
                    SubscriptionHandler(endpoint=self._rendering_control_event, service=self._soco.renderingControl,
                                        logger=self._logger)
                self.av_subscription = \
                    SubscriptionHandler(endpoint=self._av_transport_event, service=self._soco.avTransport,
                                        logger=self._logger)
                self.system_subscription = \
                    SubscriptionHandler(endpoint=self._system_properties_event, service=self._soco.systemProperties,
                                        logger=self._logger)
                self.zone_subscription = \
                    SubscriptionHandler(endpoint=self._zone_topology_event, service=self._soco.zoneGroupTopology,
                                        logger=self._logger)
                self.alarm_subscription = \
                    SubscriptionHandler(endpoint=self._alarm_event, service=self._soco.alarmClock,
                                        logger=self._logger)
                self.device_subscription = \
                    SubscriptionHandler(endpoint=self._device_properties_event, service=self._soco.deviceProperties,
                                        logger=self._logger)

                # just to have a list for disposing all events
                self._events = [
                    self.av_subscription,
                    self.render_subscription,
                    self.system_subscription,
                    self.zone_subscription,
                    self.alarm_subscription,
                    self.device_subscription
                ]
                self._is_coordinator = self._soco.is_coordinator
                self.uid = self.soco.uid.lower()
                self.household_id = self.soco.household_id

    def dispose(self):
        """
        clean-up all things here
        """
        self._logger.debug("Sonos: {uid}: disposing".format(uid=self.uid))

        if not self._soco:
            return

        for subscription in self._events:
            try:
                subscription.unsubscribe()
            except Exception as error:
                self._logger.warning("Sonos: {error}".format(error=error))
                continue

        self._soco = None

    def subscribe_base_events(self):
        if not self._soco:
            return
        self.zone_subscription.unsubscribe()
        self.zone_subscription.subscribe()

        self.system_subscription.unsubscribe()
        self.system_subscription.subscribe()

        self.device_subscription.unsubscribe()
        self.device_subscription.subscribe()

        self.alarm_subscription.unsubscribe()
        self.alarm_subscription.subscribe()

        self.render_subscription.unsubscribe()
        self.render_subscription.subscribe()

    def refresh_static_properties(self) -> None:
        """
        This function is called by the plugins discover function. This is typically called every 180sec.
        We're using this cycle to update some properties that are not updated by events
        """
        if not self._check_property():
            return

        # do this only for the coordinator, don't tress the network
        if self.is_coordinator:
            if self.snooze > 0:
                self.snooze = self.get_snooze()
        self.status_light = self.get_status_light()
        self.sonos_playlists()

    def check_subscriptions(self) -> None:
        """
        Do some subscription checks. If a subscription ist not active, we're trying to re-subscribe.
        """
        subs_ok = True
        zone_subscribed = False

        # check topology, system, alarm event for all speaker:
        #if not self.zone_subscription.is_subscribed:
        #    subs_ok = False
        self.zone_subscription.unsubscribe()
        self.zone_subscription.subscribe()
        #    zone_subscribed = True
        #if not self.system_subscription.is_subscribed:
        #    subs_ok = False
        self.system_subscription.unsubscribe()
        self.system_subscription.subscribe()
        #if not self.alarm_subscription.is_subscribed:
        #   subs_ok = False
        self.alarm_subscription.unsubscribe()
        self.alarm_subscription.subscribe()
        #if not self.render_subscription.is_subscribed:
        subs_ok = False
        self.render_subscription.unsubscribe()
        self.render_subscription.subscribe()

        #if self.is_coordinator:
        #    if not self.av_subscription.is_subscribed:
        #        subs_ok = False
        self.av_subscription.unsubscribe()
        self.av_subscription.subscribe()

        # sometimes a discover fails --> coordinator is empty --> resubscribe zone topology event
        #if not zone_subscribed:
        #if not self.coordinator:
        #subs_ok = False
        self.zone_subscription.unsubscribe()
        self.zone_subscription.subscribe()

        #if subs_ok:
        self._logger.debug("Sonos: {uid}: Event subscriptions ok".format(uid=self.uid))

    # Event Handler routines ###########################################################################################

    def _rendering_control_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        Rendering Control event handling
        :param sub_handler: SubscriptionHandler for the rendering control event
        """
        try:
            self._logger.debug("Sonos: {uid}: rendering control event handler active".format(uid=self.uid))
            while not sub_handler.signal.wait(1):
                try:
                    event = sub_handler.event.events.get(timeout=0.5)
                    if 'mute' in event.variables:
                        self.mute = int(event.variables['mute']['Master'])
                    if 'volume' in event.variables:
                        volume = int(event.variables['volume']['Master'])
                        self.volume = volume
                    if 'bass' in event.variables:
                        self.bass = int(event.variables['bass'])
                    if 'loudness' in event.variables:
                        self.loudness = int(event.variables['loudness']['Master'])
                    if 'night_mode' in event.variables:
                        self.night_mode = event.variables['night_mode']
                    if 'dialog_mode' in event.variables:
                        self.dialog_mode = event.variables['dialog_mode']
                    sub_handler.event.events.task_done()
                except Empty:
                    pass
        except Exception as ex:
            self._logger.error(ex)

    def _alarm_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        AlarmClock event handling
        :param sub_handler: SubscriptionHandler for the alarm event
        """
        try:
            self._logger.debug("Sonos: {uid}: alarm clock event handler active".format(uid=self.uid))
            while not sub_handler.signal.wait(1):
                try:
                    event = sub_handler.event.events.get(timeout=0.5)
                    sub_handler.event.events.task_done()
                except Empty:
                    pass
        except Exception as ex:
            self._logger.error(ex)

    def _system_properties_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        System properties event handling
        :param sub_handler: SubscriptionHandler for the system properties event
        """
        try:
            self._logger.debug("Sonos: {uid}: system properties event handler active".format(uid=self.uid))
            while not sub_handler.signal.wait(1):
                try:
                    event = sub_handler.event.events.get(timeout=0.5)
                    sub_handler.event.events.task_done()
                except Empty:
                    pass
        except Exception as ex:
            self._logger.error(ex)

    def _device_properties_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        Device properties event handling
        :param sub_handler: SubscriptionHandler for the device properties event
        """
        try:
            self._logger.debug("Sonos: {uid}: device properties event handler active".format(uid=self.uid))
            while not sub_handler.signal.wait(1):
                try:
                    event = sub_handler.event.events.get(timeout=0.5)
                    if 'zone_name' in event.variables:
                        self.player_name = event.variables['zone_name']
                    sub_handler.event.events.task_done()
                except Empty:
                    pass
        except Exception as ex:
            self._logger.error(ex)

    def _zone_topology_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        Zone topology event handling
        :param sub_handler: SubscriptionHandler for the zone topology event
        """
        try:
            self._logger.debug("Sonos: {uid}: topology event handler active".format(uid=self.uid))
            while not sub_handler.signal.wait(1):
                try:
                    event = sub_handler.event.events.get(timeout=0.5)
                    if 'zone_group_state' in event.variables:
                        tree = XML.fromstring(event.variables['zone_group_state'].encode('utf-8'))
                        # find group where our uid is located
                        for group_element in tree.findall('ZoneGroup'):
                            coordinator_uid = group_element.attrib['Coordinator'].lower()
                            zone_group_member = []
                            uid_found = False
                            for member_element in group_element.findall('ZoneGroupMember'):
                                member_uid = member_element.attrib['UUID'].lower()
                                _initialize_speaker(member_uid, self._logger)
                                zone_group_member.append(sonos_speaker[member_uid])
                                if member_uid == self._uid:
                                    uid_found = True
                            if uid_found:
                                # set coordinator
                                self.coordinator = coordinator_uid
                                if coordinator_uid == self._uid:
                                    self.is_coordinator = True
                                else:
                                    self.is_coordinator = False
                                # set member
                                self._zone_group_members = zone_group_member

                                # get some other properties
                                self.status_light = self.get_status_light()
                                self.sonos_playlists()

                    sub_handler.event.events.task_done()
                except Empty:
                    pass
        except Exception as ex:
            self._logger.error(ex)

    def _av_transport_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        AV event handling
        :param sub_handler: SubscriptionHandler for the av transport event
        """
        try:
            self._logger.debug("Sonos: {uid}: av transport event handler active".format(uid=self.uid))
            while not sub_handler.signal.wait(1):
                try:
                    event = sub_handler.event.events.get(timeout=0.5)

                    if 'transport_state' in event.variables:
                        transport_state = event.variables['transport_state']
                        if transport_state:
                            self.handle_transport_state(transport_state)
                    if 'current_crossfade_mode' in event.variables:
                        self.cross_fade = bool(event.variables['current_crossfade_mode'])
                    if 'sleep_timer_generation' in event.variables:
                        if int(event.variables['sleep_timer_generation']) > 0:
                            self.snooze = self.get_snooze()
                        else:
                            self.snooze = 0
                    if 'current_play_mode' in event.variables:
                        self.play_mode = event.variables['current_play_mode']
                    if 'current_track_uri' in event.variables:
                        track_uri = event.variables['current_track_uri']
                        if re.match(r'^x-rincon:RINCON_', track_uri) is not None:
                            # slave call, set uri to the coordinator track uri
                            if self._check_property():
                                self.track_uri = sonos_speaker[self.coordinator].track_uri
                            else:
                                self.track_uri = ''
                        else:
                            self.track_uri = track_uri
                        # empty track is a trigger to reset some other props
                        if not self.track_uri:
                            self.track_artist = ''
                            self.track_album = ''
                            self.track_album_art = ''
                            self.track_title = ''
                            self.radio_show = ''
                            self.radio_station = ''

                    if 'current_track' in event.variables:
                        self.current_track = event.variables['current_track']
                    else:
                        self.current_track = 0
                    if 'number_of_tracks' in event.variables:
                        self.number_of_tracks = event.variables['number_of_tracks']
                    else:
                        self.number_of_tracks = 0
                    if 'current_track_duration' in event.variables:
                        self.current_track_duration = event.variables['current_track_duration']
                    else:
                        self.current_track_duration = ''

                    # don't do an else here: these value won't always be updated
                    if 'current_transport_actions' in event.variables:
                        self.current_transport_actions = event.variables['current_transport_actions']
                    if 'current_valid_play_modes' in event.variables:
                        self.current_valid_play_modes = event.variables['current_valid_play_modes']

                    if 'current_track_meta_data' in event.variables:
                        if event.variables['current_track_meta_data']:
                            # we have some different data structures, handle it
                            if isinstance(event.variables['current_track_meta_data'], DidlMusicTrack):
                                metadata = event.variables['current_track_meta_data'].__dict__
                            elif isinstance(event.variables['current_track_meta_data'], DidlItem):
                                metadata = event.variables['current_track_meta_data'].__dict__
                            else:
                                metadata = event.variables['current_track_meta_data'].metadata
                            if 'creator' in metadata:
                                self.track_artist = metadata['creator']
                            else:
                                self.track_artist = ''
                            if 'title' in metadata:
                                # ignore x-sonos-api-stream: radio played, title seems wrong
                                if re.match(r"^x-sonosapi-stream:", metadata['title']) is None:
                                    self.track_title = metadata['title']
                            else:
                                self.track_title = ''
                            if 'album' in metadata:
                                self.track_album = metadata['album']
                            else:
                                self.track_album = ''
                            if 'album_art_uri' in metadata:
                                cover_url = metadata['album_art_uri']
                                if not cover_url.startswith(('http:', 'https:')):
                                    self.track_album_art = 'http://' + self.soco.ip_address + ':1400' + cover_url
                                else:
                                    self.track_album_art = cover_url
                            else:
                                self.track_album_art = ''

                            if 'stream_content' in metadata:
                                stream_content = metadata['stream_content'].title()
                                if not stream_content.lower() in \
                                        ['zpstr_buffering', 'zpstr_connecting', 'x-sonosapi-stream']:
                                    self.stream_content = stream_content
                                else:
                                    self.stream_content = ""
                            else:
                                self.stream_content = ''
                            if 'radio_show' in metadata:
                                radio_show = metadata['radio_show']
                                if radio_show:
                                    radio_show = radio_show.split(',p', 1)
                                    if len(radio_show) > 1:
                                        self.radio_show = radio_show[0]
                                else:
                                    self.radio_show = ''
                            else:
                                self.radio_show = ''

                    if self.streamtype == 'radio':
                        # we need the title from 'enqueued_transport_uri_meta_data'
                        if 'enqueued_transport_uri_meta_data' in event.variables:
                            radio_metadata = event.variables['enqueued_transport_uri_meta_data']
                            if hasattr(radio_metadata, 'title'):
                                if self.streamtype == 'radio':
                                    self.radio_station = str(radio_metadata.title)
                    else:
                        self.radio_station = ''

                    sub_handler.event.events.task_done()
                except Empty:
                    pass
        except Exception as ex:
            self._logger.error(ex)

    def _check_property(self):
        if not self.is_initialized:
            self._logger.warning("Sonos: {uid}: speaker is not initialized.".format(uid=self.uid))
            return False
        if not self.coordinator:
            self._logger.warning("Sonos: {uid}: coordinator is empty".format(uid=self.uid))
            return False
        if self.coordinator not in sonos_speaker:
            self._logger.warning("Sonos: {uid}: coordinator '{coordinator}' is not a valid speaker.".format
                                 (uid=self.uid, coordinator=self.coordinator))
            return False
        return True

    def handle_transport_state(self, transport_state):
        if transport_state.lower() == "stopped":
            self.stop = True
            self.play = False
            self.pause = False
        if transport_state.lower() == "paused_playback":
            self.stop = False
            self.play = False
            self.pause = True
        if transport_state.lower() == "playing":
            self.stop = False
            self.play = True
            self.pause = False

    # Properties #######################################################################################################

    # Internal #########################################################################################################

    @property
    def _zone_group_members(self):
        return self._zone_group

    @_zone_group_members.setter
    def _zone_group_members(self, value):
        if not isinstance(value, list):
            self._logger.warning("Sonos: {uid}: value [{value]] for setter _zone_group_members must be type of list."
                                 .format(uid=self.uid, value=value))
            return
        self._zone_group = value
        # set zone_group_members (string representation)
        members = []
        for member in self._zone_group:
            members.append(member.uid)
        self.zone_group_members = members

    # External #########################################################################################################

    @property
    def is_initialized(self) -> bool:
        """
        Is the speaker fully initialized?
        :rtype: bool
        :return: True, if the speaker is initialized, False otherwise.
        """
        return self._is_initialized

    @is_initialized.setter
    def is_initialized(self, is_initialized: bool) -> None:
        """
        setter for is_initialized.
        :param is_initialized: True, if the speaker is initialized, False otherwise.
        :return: None
        :rtype: None
        """
        if self._is_initialized == is_initialized:
            return
        self._is_initialized = is_initialized
        for item in self.is_initialized_items:
            item(self.is_initialized, 'Sonos')

    @property
    def player_name(self) -> str:
        """
        Returns the play name.
        :rtype: str
        """
        return self._player_name

    @player_name.setter
    def player_name(self, player_name: str) -> None:
        """
        Sets the play name (only internal).
        :param player_name: player name
        :return: None
        """
        if self._player_name == player_name:
            return
        self._player_name = player_name
        for item in self.player_name_items:
            item(self.player_name, 'Sonos')

    @property
    def household_id(self) -> str:
        """
        Returns the household id of the speaker.
        :rtype: str
        """
        return self._household_id

    @household_id.setter
    def household_id(self, household_id: str) -> None:
        """
        Sets the household id (only internal).
        :param household_id: household id
        :return: None
        """
        if self._household_id == household_id:
            return
        self._household_id = household_id
        for item in self.household_id_items:
            item(self.household_id, 'Sonos')

    @property
    def night_mode(self) -> bool:
        """
        Returns the current night_mode setting of the speaker.
        :return: True or False
        """
        return self._night_mode

    @night_mode.setter
    def night_mode(self, night_mode: bool) -> None:
        """
        Setter for night_mode (internal)
        :param night_mode: True or False
        :rtype: None
        :return: None
        """
        if self._night_mode == night_mode:
            return
        self._night_mode = night_mode
        for item in self.night_mode_items:
            item(self.night_mode, 'Sonos')

    def set_night_mode(self, night_mode: bool) -> bool:
        """
        Calls the SoCo functionality night_mode to set this setting to the speaker. This mode is currently not supported
        by all speakers (e.g. supported by Playbar).
        :rtype: bool
        :param night_mode: True or False
        :return: 'True' if success, 'False' otherwise
        """
        try:
            self.soco.night_mode = night_mode
            self.night_mode = night_mode
            return True
        except Exception as ex:
            self._logger.warning("Sonos: {uid}: can't set night mode. Not supported.".format(uid=self.uid))
            return False

    @property
    def dialog_mode(self) -> bool:
        """
        Returns the current dialog_mode setting of the speaker.
        :return: True or False
        """
        return self._dialog_mode

    @dialog_mode.setter
    def dialog_mode(self, dialog_mode: bool) -> None:
        """
        Setter for dialog_mode (internal)
        :param dialog_mode: True or False
        :rtype: None
        :return: None
        """
        if self._dialog_mode == dialog_mode:
            return
        self._dialog_mode = dialog_mode
        for item in self.dialog_mode_items:
            item(self.dialog_mode, 'Sonos')

    def set_dialog_mode(self, dialog_mode: bool) -> bool:
        """
        Calls the SoCo functionality dialog_mode to set this setting to the speaker. This mode is currently not
        supported by all speakers (e.g. supported by Playbar).
        :rtype: bool
        :param dialog_mode: True or False
        :return: 'True' if success, 'False' otherwise
        """
        try:
            self.soco.dialog_mode = dialog_mode
            self.dialog_mode = dialog_mode
            return True
        except Exception as ex:
            self._logger.warning("Sonos: {uid}: can't set dialog mode. Not supported.".format(uid=self.uid))
            return False

    @property
    def loudness(self) -> bool:
        """
        Returns the current loudness setting of the speaker.
        :return: True or False
        """
        return self._loudness

    @loudness.setter
    def loudness(self, loudness: bool) -> None:
        """
        Setter for loudnes (internal)
        :param loudness: True or False
        :rtype: None
        :return: None
        """
        if self._loudness == loudness:
            return
        self._loudness = loudness
        for item in self.loudness_items:
            item(self.loudness, 'Sonos')

    def set_loudness(self, loudness: bool, group_command: bool = False) -> bool:
        """
        Calls the SoCo functionality loudness to set this setting to the speaker.
        :rtype: bool
        :param loudness: True or False
        :param group_command: Should the loudness value set to all speaker of the group? Default: False
        :return: 'True' if success, 'False' otherwise
        """
        try:
            if group_command:
                for member in self.zone_group_members:
                    sonos_speaker[member].soco.loudness = loudness
                    sonos_speaker[member].loudness = loudness
            else:
                self.soco.loudness = loudness
                self.loudness = loudness
            return True
        except Exception as ex:
            self._logger.error(ex)
            return False

    @property
    def treble(self) -> int:
        """
        Returns the current treble setting of the speaker.
        :return: value between -10 and 10 (0 is the default setting)
        """
        return self._treble

    @treble.setter
    def treble(self, treble: int) -> None:
        """
        Setter for treble (internal)
        :param treble: integer between -10 and 10 (0 is the default setting)
        :rtype: None
        :return: None
        """
        if self._treble == treble:
            return
        self._treble = treble
        for item in self.treble_items:
            item(self.treble, 'Sonos')

    def set_treble(self, treble: int, group_command: bool = False) -> bool:
        """
        Calls the SoCo functionality treble to set this setting to the speaker.
        :rtype: bool
        :param treble: Integer between -10 and 10 (0 default).
        :param group_command: Should the treble vale  set to all speaker of the group? Default: False
        :return: 'True' if success, 'False' otherwise
        """
        try:
            # check value
            if treble not in range(-10, 11, 1):
                raise Exception('Sonos: Treble has to be an integer between -10 and 10.')
            if group_command:
                for member in self.zone_group_members:
                    sonos_speaker[member].soco.treble = treble
                    sonos_speaker[member].treble = treble
            else:
                self.soco.treble = treble
                self.treble = treble
            return True
        except Exception as ex:
            self._logger.error(ex)
            return False

    @property
    def bass(self) -> int:
        """
        Returns the actual bass setting of the speaker.
        :return: value between -10 and 10 (0 is the default setting)
        """
        return self._bass

    @bass.setter
    def bass(self, bass: int) -> None:
        """
        Setter for bass (internal)
        :param bass: integer between -10 and 10 (0 is the default setting)
        :rtype: None
        :return: None
        """
        if self._bass == bass:
            return
        self._bass = bass
        for item in self.bass_items:
            item(self.bass, 'Sonos')

    def set_bass(self, bass: int, group_command: bool = False) -> bool:
        """
        Calls the SoCo functionality bass to set this setting to the speaker.
        :rtype: bool
        :param bass: Integer between -10 and 10 (0 default).
        :param group_command: Should the bass set to all speaker of the group? Default: False
        :return: 'True' if success, 'False' otherwise
        """
        try:
            # check value
            if bass not in range(-10, 11, 1):
                raise Exception('Sonos: Bass has to be an integer between -10 and 10.')
            if group_command:
                for member in self.zone_group_members:
                    sonos_speaker[member].soco.bass = bass
                    sonos_speaker[member].bass = bass
            else:
                self.soco.bass = bass
                self.bass = bass
            return True
        except Exception as ex:
            self._logger.error(ex)
            return False

    @property
    def volume(self) -> int:
        """
        Return the current volume level of the speaker
        :rtype: int
        :return: volume
        """
        return self._volume

    @volume.setter
    def volume(self, value: int) -> None:
        """
        volume setter (internal)
        :param value: volume level within range of 0-100
        :rtype: None
        :return: None
        """
        if self._volume == value:
            return
        self._volume = value

        for item in self.volume_items:
            item(self.volume, 'Sonos')

    def _check_max_volume_exceeded(self, volume: int, max_volume: int) -> bool:
        """
        Checks if the volume exceeds a maximum volume value.
        :param volume: volme
        :param max_volume: maximum volume
        :return: 'True' if volume exceeds maximum volume, 'False# otherwise.
        """
        volume = int(volume)
        if max_volume > -1:
            if volume >= max_volume:
                return True
        return False

    def set_volume(self, volume: int, group_command: bool = False, max_volume: int = -1) -> bool:
        """
        Calls the SoCo function for setting the volume level of the speaker.
        :param max_volume: Maximum volume between 0 - 100. If -1, no maximum volume is set.
        :param volume: volume level within range 0-100
        :param group_command: bool values that indicates whether the volume level should be set for all speakers in the
         group or just for the current speaker. Default: False
        :return: 'True' if success, 'False' otherwise
        :rtype: bool
        """
        try:
            # check volume range
            if volume < 0 or volume > 100:
                return
                # don ot raise error here polluting the log file
                # dpt3 handling can trigger negative values
                # raise Exception('Sonos: Volume has to be an integer between 0 and 100.')

            if self._check_max_volume_exceeded(volume, max_volume):
                self._logger.debug("Sonos: Volume to set [{volume}] exceeds max volume [{max_volume}].".format(
                    volume=volume, max_volume=max_volume
                ))
                volume = max_volume

            if group_command:
                for member in self.zone_group_members:
                    sonos_speaker[member].soco.volume = volume
                    sonos_speaker[member].volume = volume
            else:
                self.soco.volume = volume
                self.volume = volume
            return True
        except Exception as ex:
            self._logger.error(ex)
            return False

    def switch_to_tv(self) -> bool:
        """
        Switch the playbar speaker's input to TV. Only supported by Sonos Playbar yet.
        :return: 'True' to switch the playbar speaker's input to TV, otherwise 'False' (error, e.g unsupported model)
        """
        try:
            return self.soco.switch_to_tv()
        except Exception as ex:
            self._logger.warning("Sonos: {uid}: can't switch to TV. Not supported.".format(uid=self.uid))
            return False

    def switch_to_line_in(self) -> bool:
        """
        Switches the audio input to line-in. Only for supported speaker, e.g. Sonos Play5
        :return: 'True' to switch to line-in, otherwise 'False' (error, e.g unsupported model)
        """
        try:
            return self.soco.switch_to_line_in()
        except Exception as ex:
            self._logger.warning("Sonos: {uid}: can't switch to line-in. Not supported.".format(uid=self.uid))
            return False

    @property
    def status_light(self) -> bool:
        """
        Returns the current status-light status.
        :return: 'True' led on, otherwise led off
        """
        return self._status_light

    @status_light.setter
    def status_light(self, value: bool) -> None:
        """
        status_light setter (internal)
        :param value: 'True' or 'False' to indicate the status-light status
        :return: None
        """
        if self._status_light == value:
            return
        self._status_light = value
        for item in self.status_light_items:
            item(self.status_light, 'Sonos')

    def set_status_light(self, value: bool) -> bool:
        """
        Calls the SoCo function to set the status-light on or off
        :param value: 'True' led on, otherwise led off
        :return: True, if successful, otherwise False.
        """
        try:
            self.soco.status_light = value
            return True
        except Exception as ex:
            self._logger.debug(ex)
            return False

    def get_status_light(self) -> bool:
        """
        Calls the SoCo function to get the led of the speaker.
        :rtype: bool
        :return: 'True' for Led on, 'False' for Led off or Exception
        """
        try:
            return self.soco.status_light
        except Exception as ex:
            self._logger.error(ex)
            return False

    @property
    def coordinator(self) -> str:
        """
        Coordinator uuid
        :rtype: str
        :return: uuid of group coordinator
        """
        return self._coordinator

    @coordinator.setter
    def coordinator(self, value: str) -> None:
        """
        coordinator setter (internal)
        :param value: str with uuid of the coordinator
        """
        self._coordinator = value
        for item in self.coordinator_items:
            item(self.coordinator, 'Sonos')

    @property
    def zone_group_members(self) -> list:
        """
        Return a list of all uids in the group (str)
        :return: list with uids of the current group
        """
        return self._members

    @zone_group_members.setter
    def zone_group_members(self, value: list) -> None:
        """
        zone_group_members setter. Here we do some important event handling based on the current zone group.
        :param value: list with uids to set as group members
        """
        if not isinstance(value, list):
            self._logger.warning("Sonos: {uid}: value [{value]] for setter zone_group_members must be type of list."
                                 .format(uid=self.uid, value=value))
            return
        self._members = value

        for item in self.zone_group_members_items:
            item(self.zone_group_members, 'Sonos')

        # if we are the coordinator: un-register av events for slave speakers
        # re-init subscriptions for the master

        if self.is_coordinator:
            for member in self._zone_group_members:
                if member is not self:
                    member.av_subscription.unsubscribe()
                else:
                    member.av_subscription.unsubscribe()
                    member.av_subscription.subscribe()

    @property
    def streamtype(self) -> str:
        """
        Returns the current streamtype. Possible value are: 'music', 'radio', 'tv', 'line-in'. This property always
        returns the group coordinator value regardless on which speaker this function was called.
        :return: streamtype
        """
        return self._streamtype

    @streamtype.setter
    def streamtype(self, streamtype: str) -> None:
        """
        Sets the streamtype. (internal). Possible value are: 'music', 'radio', 'tv', 'line-in'.
        :param streamtype: streamtype
        :return: None
        """
        if self.streamtype == streamtype:
            return
        self._streamtype = streamtype

        for item in self.streamtype_items:
            item(streamtype, 'Sonos')

    @property
    def track_uri(self) -> str:
        """
        Returns the uri of currently played track. This property always returns the group coordinator value regardless
        on which speaker this function was called.
        :return: track uri
        """
        if self.coordinator:
            return self._track_uri
        if not self._check_property():
            return ''
        return sonos_speaker[self.coordinator].track_uri

    @track_uri.setter
    def track_uri(self, track_uri: str) -> None:
        """
        Sets the track uri. (internal). This method can be called by slaves too. We need some extra work here
        :param track_uri: track uri
        :return: None
        """
        if not self._check_property():
            return
        if track_uri == self._track_uri:
            return
        self._track_uri = track_uri

        if re.match(r"^x-sonos-htastream:", self.track_uri) is not None:
            streamtype = 'tv'
        elif re.match(r"^x-rincon-stream:", self.track_uri) is not None:
            streamtype = 'line-in'
        elif re.match(r"^x-rincon-mp3radio:", self.track_uri) is not None:
            streamtype = 'radio'
        else:
            # aac, wma etc possible for audio; everything except x- should be radio
            if re.match(r'^x-', self.track_uri) is not None:
                streamtype = 'music'
            else:
                streamtype = 'radio'
        # coordinator call / update all items
        if self.is_coordinator:
            for member in self.zone_group_members:
                sonos_speaker[member].streamtype = streamtype
                for item in sonos_speaker[member].track_uri_items:
                    item(self.track_uri, 'Sonos')
        # slave call, update just the slave
        else:
            self.streamtype = streamtype
            for item in self.track_uri_items:
                item(self.track_uri, 'Sonos')

    @property
    def play(self) -> bool:
        """
        Returns the current play status. This property always returns the group coordinator value regardless on which
        speaker this function was called.
        :return: play status
        """
        if self.coordinator:
            return self._play
        if not self._check_property():
            return False
        return sonos_speaker[self.coordinator].play

    @play.setter
    def play(self, value: bool) -> None:
        """
        Sets the play status. (internal)
        :param value: play status
        :return: None
        """
        if not self._check_property():
            return
        if sonos_speaker[self.coordinator].play == value:
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play = value
        self._play = value
        for member in self.zone_group_members:
            for item in sonos_speaker[member].play_items:
                item(value, 'Sonos')

    def set_play(self) -> bool:
        """
        Calls the SoCo play method and starts playing the current track.
        :return: True, if successful, otherwise False.
        """
        if not self._check_property():
            return False
        if not sonos_speaker[self.coordinator].soco.play():
            return False
        sonos_speaker[self.coordinator].play = True
        sonos_speaker[self.coordinator].pause = False
        sonos_speaker[self.coordinator].stop = False
        return True

    @property
    def pause(self):
        """
        Returns the current pause status. This property always returns the group coordinator value regardless on which
        speaker this function was called.
        :return: pause status
        """
        if self.is_coordinator:
            return self._pause
        if not self._check_property():
            return False
        return sonos_speaker[self.coordinator].pause

    @pause.setter
    def pause(self, value: bool) -> None:
        """
        Sets the pause status. (internal)
        :param value: pause status
        :return: None
        """
        if not self._check_property():
            return
        if sonos_speaker[self.coordinator].pause == value:
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].pause = value
        self._pause = value
        for member in self.zone_group_members:
            for item in sonos_speaker[member].pause_items:
                item(value, 'Sonos')

    def set_pause(self) -> bool:
        """
        Calls the SoCo pause method and pauses the current track.
        :return: True, if successful, otherwise False.
        """
        if not self._check_property():
            return False
        if not sonos_speaker[self.coordinator].soco.pause():
            return False
        sonos_speaker[self.coordinator].pause = True
        sonos_speaker[self.coordinator].play = False
        sonos_speaker[self.coordinator].stop = False
        return True

    @property
    def stop(self):
        """
        Returns the current stop status. This property always returns the group coordinator value regardless on which
        speaker this function was called.
        :return: stop status
        """
        if self.is_coordinator:
            return self._stop
        if not self._check_property():
            return False
        return sonos_speaker[self.coordinator].stop

    @stop.setter
    def stop(self, value: bool) -> None:
        """
        Sets the stop status. (internal)
        :param value: stop status
        :return: None
        """
        if not self._check_property():
            return
        if sonos_speaker[self.coordinator].stop == value:
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].stop = value
        self._stop = value
        for member in self.zone_group_members:
            for item in sonos_speaker[member].stop_items:
                item(value, 'Sonos')

    def set_stop(self) -> bool:
        """
        Calls the SoCo stop method and stops the current track.
        :return: True, if successful, otherwise False.
        """
        if not self._check_property():
            return False
        if not sonos_speaker[self.coordinator].soco.stop():
            return False
        sonos_speaker[self.coordinator].stop = True
        sonos_speaker[self.coordinator].play = False
        sonos_speaker[self.coordinator].pause = False

    def set_next(self, next_track: bool) -> None:
        """
        Go to the next track. This command will always be triggered on the coordinator.
        :rtype: None
        :param next_track: 'True' for next, all other value have no effects.
        """
        if not self._check_property():
            return
        if next_track:
            try:
                sonos_speaker[self.coordinator].soco.next()
            except:
                self._logger.debug("Sonos: {uid}: can't go to next track. Maybe the end of the playlist "
                                   "reached?".format(uid=self.uid))

    def set_previous(self, previous: bool) -> None:
        """
        Go back to the previously played track. This command will always be triggered on the coordinator.
        :rtype: None
        :param previous: 'True' for previous track, all other value have no effects.
        """
        if not self._check_property():
            return
        if previous:
            try:
                sonos_speaker[self.coordinator].soco.previous()
            except:
                self._logger.debug("Sonos: {uid}: can't go back to the previously played track. Already the first "
                                   "track in the playlist?".format(uid=self.uid))

    @property
    def mute(self) -> bool:
        """
        Returns the current mute status. This property always returns the group coordinator value regardless on which
        speaker this function was called.
        :return: mute status
        """
        if self.is_coordinator:
            return self._mute
        if not self._check_property():
            return False
        return sonos_speaker[self.coordinator].mute

    @mute.setter
    def mute(self, value: bool) -> None:
        """
        Sets the mute status. (internal)
        :param value: mute status
        """
        if not self._check_property():
            return
        if sonos_speaker[self.coordinator].mute == value:
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].mute = value
        self._mute = value
        for member in self.zone_group_members:
            for item in sonos_speaker[member].mute_items:
                item(value, 'Sonos')

    def set_mute(self, value: bool) -> bool:
        """
        Calls the SoCo mute method and mutes /un-mutes the speaker.
        :param value: True for mute, False for un-mute
        :return: True, if successful, otherwise False.
        """
        try:
            if not self._check_property():
                return False
            sonos_speaker[self.coordinator].soco.mute = value
            return True
        except Exception as ex:
            self._logger.error(ex)
            return False

    @property
    def cross_fade(self) -> bool:
        """
        Returns the current cross_fade status. This property always returns the group coordinator value regardless
        on which speaker this function was called.
        :return: cross_fade status
        """
        if self.is_coordinator:
            return self._cross_fade
        if not self._check_property():
            return False
        return sonos_speaker[self.coordinator].cross_fade

    @cross_fade.setter
    def cross_fade(self, cross_fade: bool) -> None:
        """
        Sets the cross_fade status. (internal)
        :param cross_fade: cross_fade status
        """
        if not self._check_property():
            return
        if sonos_speaker[self.coordinator].cross_fade == cross_fade:
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].cross_fade = cross_fade
        self._cross_fade = cross_fade
        for member in self.zone_group_members:
            for item in sonos_speaker[member].cross_fade_items:
                item(cross_fade, 'Sonos')

    def set_cross_fade(self, cross_fade: bool) -> bool:
        """
        Calls the SoCo cross_fade method and sets the  cross fade setting for the speaker.
        :param cross_fade: 'True' for cross_fade on, 'False' for cross_fade off
        :return: True, if successful, otherwise False.
        """
        try:
            if not self._check_property():
                return False
            sonos_speaker[self.coordinator].soco.cross_fade = cross_fade
            return True
        except Exception as ex:
            self._logger.error(ex)
            return False

    @property
    def snooze(self) -> int:
        """
        Returns the time left before the speaker enters the snooze mode. If None, the snooze mode is deactivated.
        :rtype: int
        """
        if self.is_coordinator:
            return self._snooze
        if not self._check_property():
            return False
        return sonos_speaker[self.coordinator].snooze

    @snooze.setter
    def snooze(self, snooze: int) -> None:
        """
        Snooze setter. Sets the time in seconds before the speaker entering the snooze mode.
        :rtype: None
        :param snooze: time in seconds. The maximum value is 86399, set snooze to None and the timer will be
        deactivated.
        """
        if not self._check_property():
            return
        if sonos_speaker[self.coordinator].snooze == snooze:
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].snooze = snooze
        self._snooze = snooze
        for member in self.zone_group_members:
            for item in sonos_speaker[member].snooze_items:
                item(snooze, 'Sonos')

    def set_snooze(self, snooze: int) -> bool:
        """
        Call the SoCo function set_sleep_timer to set the time in seconds before the speaker entering the snooze mode.
        :rtype: 'True' if success, 'False' otherwise
        :param snooze: time in seconds. The maximum value is 86399, set snooze to None and the timer will be
        deactivated.
        """
        try:
            if not self._check_property():
                return False
            sonos_speaker[self.coordinator].soco.set_sleep_timer(snooze)
            return True
        except Exception as ex:
            self._logger.error(ex)
            return False

    def get_snooze(self) -> int:
        """
        Returns the time left before the speaker enters the snooze mode. This function calls actively the speaker.
        Use it wisely.
        :rtype: int
        :return: time in seconds, 0 if no timer is active
        """
        try:
            if not self._check_property():
                return 0
            return sonos_speaker[self.coordinator].soco.get_sleep_timer()
        except Exception as ex:
            self._logger.error(ex)
            return 0

    @property
    def play_mode(self) -> str:
        """
        Returns the current play mode status. This property always returns the group coordinator value regardless
        on which speaker this function was called.
        :rtype: str
        :return: play mode status ('NORMAL', 'REPEAT_ALL', 'SHUFFLE', 'SHUFFLE_NOREPEAT')
        """
        if self.is_coordinator:
            return self._play_mode
        if not self._check_property():
            return ''
        return sonos_speaker[self.coordinator].play_mode

    @play_mode.setter
    def play_mode(self, play_mode: str) -> None:
        """
        Sets the play mode. (internal). Aloowd values are:  'NORMAL', 'REPEAT_ALL', 'SHUFFLE', 'SHUFFLE_NOREPEAT'
        :param play_mode: play mode
        """
        if not self._check_property():
            return
        if sonos_speaker[self.coordinator].play_mode == play_mode:
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_mode = play_mode
        self._play_mode = play_mode
        for member in self.zone_group_members:
            for item in sonos_speaker[member].play_mode_items:
                item(play_mode, 'Sonos')

    def set_play_mode(self, play_mode: str) -> bool:
        """
        Calls the SoCo play_mode method and sets the play mode for the speaker.
        :param play_mode:  allowed value are 'NORMAL', 'REPEAT_ALL', 'SHUFFLE', 'SHUFFLE_NOREPEAT'
        :return: True, if successful, otherwise False.
        """
        try:
            if not self._check_property():
                return False
            sonos_speaker[self.coordinator].soco.play_mode = play_mode
            return True
        except Exception as ex:
            self._logger.error(ex)
            return False

    @property
    def is_coordinator(self) -> bool:
        """
        Is the speaker the coordinator of the group?
        :return: Returns 'True' if the speaker is the coordinator of the group, otherwise 'False'.
        """
        return self._is_coordinator

    @is_coordinator.setter
    def is_coordinator(self, value: bool) -> None:
        """
        is_coordinator setter
        :param value: 'True' to indicate that the speker is the coordiantor of the group, otherwise 'False'
        """
        self._is_coordinator = value
        for item in self.is_coordinator_items:
            item(self._is_coordinator, 'Sonos')

    @property
    def current_track(self) -> int:
        """
        Returns the current track position. This property always returns the group coordinator value regardless on which
        speaker this function was called.
        :return: current track position
        """
        if self.coordinator:
            return self._current_track
        if not self._check_property():
            return False
        return sonos_speaker[self.coordinator].current_track

    @current_track.setter
    def current_track(self, current_track: int) -> None:
        """
        Sets the current track position. (internal)
        :param current_track: current track
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].current_track = current_track
        self._current_track = current_track
        for member in self.zone_group_members:
            for item in sonos_speaker[member].current_track_items:
                item(current_track, 'Sonos')

    @property
    def number_of_tracks(self) -> int:
        """
        Returns the number of tracks in the queue. This property always returns the group coordinator value regardless
        on which speaker this function was called.
        :return: number of tracks
        """
        if self.coordinator:
            return self._number_of_tracks
        if not self._check_property():
            return False
        return sonos_speaker[self.coordinator].number_of_tracks

    @number_of_tracks.setter
    def number_of_tracks(self, number_of_tracks: int) -> None:
        """
        Sets the number of tracks. (internal)
        :param number_of_tracks: number of tracks
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].number_of_tracks = number_of_tracks
        self._number_of_tracks = number_of_tracks
        for member in self.zone_group_members:
            for item in sonos_speaker[member].number_of_tracks_items:
                item(number_of_tracks, 'Sonos')

    @property
    def current_track_duration(self) -> str:
        """
        Returns the current track duration. This property always returns the group coordinator value regardless
        on which speaker this function was called.
        :return: current track duration
        """
        if self.coordinator:
            return self._current_track_duration
        if not self._check_property():
            return ''
        return sonos_speaker[self.coordinator].current_track_duration

    @current_track_duration.setter
    def current_track_duration(self, current_track_duration: str) -> None:
        """
        Sets the current track duration. (internal)
        :param current_track_duration: track duration in HH:mm:ss
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].current_track_duration = current_track_duration
        self._current_track_duration = current_track_duration
        for member in self.zone_group_members:
            for item in sonos_speaker[member].current_track_duration_items:
                item(self.current_track_duration, 'Sonos')

    @property
    def current_transport_actions(self) -> str:
        """
        Returns the transport actions. Values could be 'Set', 'Stop', 'Pause', 'Play', 'X_DLNA_SeekTime', 'Next',
        'Previous', 'X_DLNA_SeekTrackNr'. This property always returns the group coordinator value regardless
        on which speaker this function was called.
        :return: One or mor of these items delimited by ',' and one space: 'Set', 'Stop', 'Pause', 'Play',
        'X_DLNA_SeekTime', 'Next', 'Previous', 'X_DLNA_SeekTrackNr'
        """
        if self.coordinator:
            return self._current_transport_actions
        if not self._check_property():
            return ''
        return sonos_speaker[self.coordinator].current_transport_actions

    @current_transport_actions.setter
    def current_transport_actions(self, current_transport_actions: str) -> None:
        """
        Sets the current transport actions. (internal)
        :param current_transport_actions: One or mor of these items delimited by ',' and one space: 'Set', 'Stop',
        'Pause', 'Play', 'X_DLNA_SeekTime', 'Next', 'Previous', 'X_DLNA_SeekTrackNr'
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].current_transport_actions = current_transport_actions
        self._current_transport_actions = current_transport_actions
        for member in self.zone_group_members:
            for item in sonos_speaker[member].current_transport_actions_items:
                item(self.current_transport_actions, 'Sonos')

    @property
    def current_valid_play_modes(self) -> str:
        """
        Returns all valid playmodes for the track.
        :return: all possible play modes for the current track
        """
        if self.coordinator:
            return self._current_valid_play_modes
        if not self._check_property():
            return ''
        return sonos_speaker[self.coordinator].current_valid_play_modes

    @current_valid_play_modes.setter
    def current_valid_play_modes(self, current_valid_play_modes: str) -> None:
        """
        Sets the current valid play modes. (internal)
        :param current_valid_play_modes: possible play modes, e.g. SHUFFLE, REPEAT, REPEATONE, CROSSFADE
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].current_valid_play_modes = current_valid_play_modes
        self._current_valid_play_modes = current_valid_play_modes
        for member in self.zone_group_members:
            for item in sonos_speaker[member].current_valid_play_modes_items:
                item(self.current_valid_play_modes, 'Sonos')

    @property
    def track_artist(self) -> str:
        """
        Returns the artist for the track.
        :return: track artist
        """
        if self.coordinator:
            return self._track_artist
        if not self._check_property():
            return ''
        return sonos_speaker[self.coordinator].track_artist

    @track_artist.setter
    def track_artist(self, track_artist: str) -> None:
        """
        Sets the current track artist. (internal)
        :param track_artist: track artist
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].track_artist = track_artist
        self._track_artist = track_artist
        for member in self.zone_group_members:
            for item in sonos_speaker[member].track_artist_items:
                item(self.track_artist, 'Sonos')

    @property
    def track_title(self) -> str:
        """
        Returns the title for the track.
        :return: track title
        """
        if self.coordinator:
            return self._track_title
        if not self._check_property():
            return ''
        return sonos_speaker[self.coordinator].track_title

    @track_title.setter
    def track_title(self, track_title: str) -> None:
        """
        Sets the current track title. (internal)
        :param track_title: track title
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].track_title = track_title
        self._track_title = track_title
        for member in self.zone_group_members:
            for item in sonos_speaker[member].track_title_items:
                item(self.track_title, 'Sonos')

    @property
    def track_album(self) -> str:
        """
        Returns the album for the track.
        :return: track album
        """
        if self.coordinator:
            return self._track_album
        if not self._check_property():
            return ''
        return sonos_speaker[self.coordinator].track_album

    @track_album.setter
    def track_album(self, track_album: str) -> None:
        """
        Sets the current track album. (internal)
        :param track_album: track album
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].track_album = track_album
            return
        self._track_album = track_album
        for member in self.zone_group_members:
            for item in sonos_speaker[member].track_album_items:
                item(self.track_album, 'Sonos')

    @property
    def track_album_art(self) -> str:
        """
        Returns the album cover url for the track.
        :return: track album cover url
        """
        if self.coordinator:
            return self._track_album_art
        if not self._check_property():
            return ''
        return sonos_speaker[self.coordinator].track_album_art

    @track_album_art.setter
    def track_album_art(self, track_album_art: str) -> None:
        """
        Sets the current track album cover url. (internal)
        :param track_album_art: track album cover url
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].track_album_art = track_album_art
            return
        self._track_album_art = track_album_art
        for member in self.zone_group_members:
            for item in sonos_speaker[member].track_album_art_items:
                item(self.track_album_art, 'Sonos')

    @property
    def radio_station(self) -> str:
        """
        Returns the radio station title
        :return: radio station
        """
        if not self._check_property():
            return ''
        if self.coordinator:
            return self._radio_station
        return sonos_speaker[self.coordinator].radio_station

    @radio_station.setter
    def radio_station(self, radio_station: str) -> None:
        """
        Sets the current radio_station. (internal)
        :param radio_station: radio_station
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].radio_station = radio_station
            return
        self._radio_station = radio_station
        for member in self.zone_group_members:
            for item in sonos_speaker[member].radio_station_items:
                item(self.radio_station, 'Sonos')

    @property
    def radio_show(self) -> str:
        """
        Returns the radio show title
        :return: radio show
        """
        if self.coordinator:
            return self._radio_show
        if not self._check_property():
            return ''
        return sonos_speaker[self.coordinator].radio_show

    @radio_show.setter
    def radio_show(self, radio_show: str) -> None:
        """
        Sets the current radio show title. (internal)
        :param radio_show: radio show title
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].radio_show = radio_show
            return
        self._radio_show = radio_show
        for member in self.zone_group_members:
            for item in sonos_speaker[member].radio_show_items:
                item(self.radio_show, 'Sonos')

    @property
    def stream_content(self) -> str:
        """
        Returns the stream content
        :return: stream content
        """
        if self.coordinator:
            return self._stream_content
        if not self._check_property():
            return ''
        return sonos_speaker[self.coordinator].stream_content

    @stream_content.setter
    def stream_content(self, stream_content: str) -> None:
        """
        Sets the current stream content. (internal)
        :param stream_content: stream content
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].stream_content = stream_content
            return
        self._stream_content = stream_content
        for member in self.zone_group_members:
            for item in sonos_speaker[member].stream_content_items:
                item(self.stream_content, 'Sonos')

    def play_tunein(self, station_name: str, start: bool = True) -> None:
        """
        Plays a radio station by a given radio name. If more than one radio station are found, the first result will be
        played.
        :param station_name: radio station name
        :param start: Start playing after setting the radio stream? Default: True
        :return: None
        """

        # ------------------------------------------------------------------------------------------------------------ #

        # This code here is a quick workaround for issue https://github.com/SoCo/SoCo/issues/557 and will be fixed
        # if a patch is applied.

        # ------------------------------------------------------------------------------------------------------------ #

        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_tunein(station_name, start)
        else:

            data = '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Header><credentials ' \
                   'xmlns="http://www.sonos.com/Services/1.1"><deviceId>anon</deviceId>' \
                   '<deviceProvider>Sonos</deviceProvider></credentials></s:Header><s:Body>' \
                   '<search xmlns="http://www.sonos.com/Services/1.1"><id>search:station</id><term>{search}</term>' \
                   '<index>0</index><count>100</count></search></s:Body></s:Envelope>'.format(
                search=station_name)

            headers = {
                "SOAPACTION": "http://www.sonos.com/Services/1.1#search",
                "USER-AGENT": "Linux UPnP/1.0 Sonos/40.5-49250 (WDCR:Microsoft Windows NT 10.0.16299)",
                "CONTENT-TYPE": 'text/xml; charset="utf-8"'
            }

            response = requests.post("http://legato.radiotime.com/Radio.asmx", data=data.encode("utf-8"),
                                     headers=headers)
            schema = XML.fromstring(response.content)
            body = schema.find("{http://schemas.xmlsoap.org/soap/envelope/}Body")[0]

            response = list(xmltodict.parse(XML.tostring(body), process_namespaces=True,
                                            namespaces={'http://www.sonos.com/Services/1.1': None}).values())[0]

            items = []
            # The result to be parsed is in either searchResult or getMetadataResult
            if 'searchResult' in response:
                response = response['searchResult']
            elif 'getMetadataResult' in response:
                response = response['getMetadataResult']
            else:
                raise ValueError('"response" should contain either the key '
                                 '"searchResult" or "getMetadataResult"')

            for result_type in ('mediaCollection', 'mediaMetadata'):
                # Upper case the first letter (used for the class_key)
                result_type_proper = result_type[0].upper() + result_type[1:]
                raw_items = response.get(result_type, [])
                # If there is only 1 result, it is not put in an array
                if isinstance(raw_items, OrderedDict):
                    raw_items = [raw_items]

                for raw_item in raw_items:
                    # Form the class_key, which is a unique string for this type,
                    # formed by concatenating the result type with the item type. Turns
                    # into e.g: MediaMetadataTrack
                    class_key = result_type_proper + raw_item['itemType'].title()
                    cls = get_class(class_key)
                    from plugins.sonos.soco.music_services import Account
                    items.append(
                        cls.from_music_service(MusicService(service_name='TuneIn', account=Account()), raw_item))

            if not items:
                exit(0)

            item_id = items[0].metadata['id']
            sid = 254  # hard-coded TuneIn service id ?
            sn = 0
            meta = to_didl_string(items[0])

            uri = "x-sonosapi-stream:{0}?sid={1}&sn={2}".format(item_id, sid, sn)

            self.soco.avTransport.SetAVTransportURI([('InstanceID', 0),
                                                     ('CurrentURI', uri), ('CurrentURIMetaData', meta)])
            if start:
                self.soco.play()

    def play_url(self, url: str, start: bool = True) -> None:
        """
        Plays a track from a given url
        :param start: Start playing after setting the url? Default: True
        :param url: url to be played
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_url(url, start)
        else:
            self.soco.play_uri(url, start=start)

    def join(self, uid: str) -> None:
        """
        Joins a speaker to an exiting group.
        :rtype: None
        :param uid: UID of any speaker of the group to join
        :return: None
        """
        if not self._check_property():
            return
        uid = uid.lower()
        if uid not in sonos_speaker:
            self._logger.warning("Sonos: Cannot join ... no speaker found with uid {uid}.".format(uid=uid))
            return
        speaker_to_join = sonos_speaker[uid]
        self._logger.debug(
            'Sonos: Joining [{uid}] to [uid: {to_join}, master: {master}]'.format(
                uid=uid, to_join=speaker_to_join.uid, master=speaker_to_join.coordinator))
        self.soco.join(sonos_speaker[speaker_to_join.coordinator].soco)

    def unjoin(self, unjoin: bool, start: bool = False) -> None:
        """
        Unjoins a speaker from a group.
        :rtype: None
        :param unjoin: 'True' for unjoin
        :param start: Should the speaker start playing after the unjoin command?
        """
        if not self._check_property():
            return
        if unjoin:
            self.soco.unjoin()
            if start:
                time.sleep(2)
                self.set_play()

    def sonos_playlists(self) -> None:
        """
        Gets all Sonos playlist items.
        """
        playlists = self.soco.get_sonos_playlists()
        p_l = []
        for value in playlists:
            p_l.append(value.title)
        for item in self.sonos_playlists_items:
            item(p_l, 'Sonos')

    def _play_snippet(self, file_path: str, webservice_url: str, volume: int = -1, fade_in=False) -> None:
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator]._play_snippet(file_path, webservice_url, volume, fade_in)
        else:
            with self._snippet_queue_lock:
                snap = None
                volumes = {}
                # save all volumes from zone_member
                for member in self.zone_group_members:
                    volumes[member] = sonos_speaker[member].volume

                tag = TinyTag.get(file_path)
                duration = int(round(tag.duration)) + 0.4
                self._logger.debug("Sonos: TTS track duration: {duration}s".format(duration=duration))
                file_name = quote(os.path.split(file_path)[1])
                snippet_url = "{url}/{file}".format(url=webservice_url, file=file_name)

                # was GoogleTTS the last track? do not snapshot
                last_station = self.radio_station.lower()
                if last_station != "snippet":
                    snap = Snapshot(self.soco)
                    snap.snapshot()

                time.sleep(0.5)
                self.set_stop()
                if volume == -1:
                    volume = self.volume

                self.set_volume(volume, True)
                self.soco.play_uri(snippet_url, title="snippet")
                time.sleep(duration)
                self.set_stop()

                # Restore the Sonos device back to it's previous state
                if last_station != "snippet":
                    if snap is not None:
                        snap.restore()
                else:
                    self.radio_station = ""
                for member in self.zone_group_members:
                    if member in volumes:
                        if fade_in:
                            vol_to_ramp = volumes[member]
                            sonos_speaker[member].soco.volume = 0
                            sonos_speaker[member].soco.renderingControl.RampToVolume(
                                [('InstanceID', 0), ('Channel', 'Master'),
                                 ('RampType', 'SLEEP_TIMER_RAMP_TYPE'),
                                 ('DesiredVolume', vol_to_ramp),
                                 ('ResetVolumeAfter', False), ('ProgramURI', '')])
                        else:
                            sonos_speaker[member].set_volume(volumes[member], group_command=False)

    def play_snippet(self, audio_file, local_webservice_path_snippet: str, webservice_url: str, volume: int = -1,
                     fade_in=False) -> None:
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_tts(audio_file, local_webservice_path_snippet, webservice_url, volume,
                                                     fade_in)
        else:
            if "tinytag" not in sys.modules:
                self._logger.error("Sonos: TinyTag module not installed. Please install the module with 'sudo pip3 "
                                   "install tinytag'.")
                return
            file_path = os.path.join(local_webservice_path_snippet, audio_file)

            if not os.path.exists(file_path):
                self._logger.error("Sonos: Snippet file '{file_path}' does not exists.".format(file_path=file_path))
                return
            self._play_snippet(file_path, webservice_url, volume, fade_in)

    def play_tts(self, tts: str, tts_language: str, local_webservice_path: str, webservice_url: str, volume: int = -1,
                 fade_in=False) -> None:
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_tts(tts, tts_language, local_webservice_path, webservice_url,
                                                     volume, fade_in)
        else:
            if "tinytag" not in sys.modules:
                self._logger.error("Sonos: TinyTag module not installed. Please install the module with 'sudo pip3 "
                                   "install tinytag'.")
                return
            file_path = get_tts_local_file_path(local_webservice_path, tts, tts_language)

            # only do a tts call if file not exists
            if not os.path.exists(file_path):
                tts = gTTS(tts, self._logger, tts_language)
                try:
                    tts.save(file_path)
                except Exception as err:
                    self._logger.error("Sonos: Could not obtain TTS file from Google. Error: {ex}".format(ex=err))
                    return
            else:
                self._logger.debug("Sonos: File {file} already exists. No TTS request necessary.".format(
                    file=file_path))
            self._play_snippet(file_path, webservice_url, volume, fade_in)

    def load_sonos_playlist(self, name: str, start: bool = False, clear_queue: bool = False, track: int = 0) -> None:
        """
        Loads a Sonos playlist.
        :param track: The index of the track to start play from. First item in the queue is 0.
        :param name: playlist name
        :param start: Should the speaker start playing after loading the playlist?
        :param clear_queue: 'True' to clearthe queue before loading the new playlist, 'False' otherwise.
        :rtype: None
        :return: None
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].load_sonos_playlist(name, start, clear_queue, track)
        else:
            try:
                if not name:
                    self._logger.warning("Sonos: A valid playlist name must be provided.")
                    return
                playlist = self.soco.get_sonos_playlist_by_attr('title', name)
                if playlist:
                    if clear_queue:
                        self.soco.clear_queue()
                    self.soco.add_to_queue(playlist)
                    try:
                        track = int(track)
                    except TypeError:
                        self._logger.warning("Sonos: Could not cast track [{track}] to 'int'.")
                        return
                    try:
                        self.soco.play_from_queue(track, start)
                    except SoCoUPnPException as ex:
                        self._logger.warning("Sonos: {ex}".format(ex=ex))
                        return
                    # bug here? no event, we have to trigger it manually
                    if start:
                        self.play = True
            except Exception as ex:
                self._logger.warning("Sonos: No Sonos playlist found with title '{title}'.".format(title=name))


class Sonos(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.4.6"

    def __init__(self, sh, tts=False, local_webservice_path=None, local_webservice_path_snippet=None,
                 discover_cycle="120", webservice_ip=None, webservice_port=23500, speaker_ips=None, **kwargs):
        super().__init__(**kwargs)
        self._sh = sh
        self._logger = logging.getLogger('sonos')  # get a unique logger for the plugin and provide it internally
        self.zero_zone = False  # sometime a discovery scan fails, so try it two times; we need to save the state
        self._sonos_dpt3_step = 2  # default value for dpt3 volume step (step(s) per time period)
        self._sonos_dpt3_time = 1  # default value for dpt3 volume time (time period per step in seconds)
        self._tts = self.to_bool(tts, default=False)
        self._local_webservice_path = local_webservice_path

        # see documentation: if no exclusive snippet path is set, we use the global one
        if local_webservice_path_snippet is None:
            self._local_webservice_path_snippet = self._local_webservice_path
        else:
            self._local_webservice_path_snippet = local_webservice_path_snippet

        get_param_func = getattr(self, "get_parameter_value", None)
        if callable(get_param_func):
            speaker_ips = self.get_parameter_value("speaker_ips")
        else:
            speaker_ips = re.findall(r'[0-9]+(?:\.[0-9]+){3}', speaker_ips)

        self._speaker_ips = []
        if speaker_ips:
            self._logger.debug("Sonos: User-defined speaker IPs set. Auto-discover disabled.")
        # check user specified sonos speaker ips
        if speaker_ips:
            for ip in speaker_ips:
                if self.is_ip(ip):
                    self._speaker_ips.append(ip)
                else:
                    self._logger.warning("Sonos: Invalid Sonos speaker ip '{ip}'. Ignoring.".format(ip=ip))

        # unique items in list
        self._speaker_ips = utils.unique_list(self._speaker_ips)
        auto_ip = utils.get_local_ip_address()

        if webservice_ip is not None:
            if self.is_ip(webservice_ip):
                self._webservice_ip = webservice_ip
            else:
                self._logger.error("Sonos: Your webservice_ip parameter is invalid. '{ip}' is not a vaild ip address. "
                                   "Disabling TTS.".format(ip=webservice_ip))
                self._tts = False
        else:
            self._webservice_ip = auto_ip

        if utils.is_valid_port(str(webservice_port)):
            self._webservice_port = int(webservice_port)
            if not utils.is_open_port(self._webservice_port):
                self._logger.error("Sonos: Your chosen webservice port {port} is already in use. "
                                   "TTS disabled!".format(port=self._webservice_port))
                self._tts = False
        else:
            self._logger.error("Sonos: Your webservice_port parameter is invalid. '{port}' is not within port range "
                               "1024-65535. TTS disabled!".format(port=webservice_port))
            self._tts = False

        discover_cycle_default = 120

        if self._tts:
            if self._local_webservice_path_snippet:
                # we just need an existing path with read rights, this can be done by the user while shNG is running
                # just throw some warnings
                if not os.path.exists(self._local_webservice_path_snippet):
                    self._logger.warning("Sonos: Local webservice snippet path was set to '{path}' but doesn't "
                                         "exists".format(path=self._local_webservice_path_snippet))
                if not os.access(self._local_webservice_path_snippet, os.R_OK):
                    self._logger.warning("Sonos: Local webservice snippet path '{path}' is not readable.".format(
                        path=self._local_webservice_path_snippet))

            if self._local_webservice_path:
                # check access rights
                try:
                    os.makedirs(self._local_webservice_path, exist_ok=True)
                    if os.path.exists(self._local_webservice_path):
                        self._logger.debug("Sonos: Local webservice path set to '{path}'".format(
                            path=self._local_webservice_path))
                        if os.access(self._local_webservice_path, os.W_OK):
                            self._logger.debug("Sonos: Write permissions ok for tts on path {path}".format(
                                path=self._local_webservice_path))

                            free_diskspace = get_free_diskspace(self._local_webservice_path)
                            human_readable_diskspace = file_size(free_diskspace)
                            self._logger.debug("Sonos: Free diskspace: {disk}".format(disk=human_readable_diskspace))

                            self._webservice_url = "http://{ip}:{port}".format(ip=self._webservice_ip,
                                                                               port=self._webservice_port)
                            self._logger.debug("Sonos: Starting webservice for TTS on {url}".format(
                                url=self._webservice_url))
                            self.webservice = SimpleHttpServer(self._webservice_ip,
                                                               self._webservice_port,
                                                               self._local_webservice_path,
                                                               self._local_webservice_path_snippet)
                            self.webservice.start()
                        else:
                            self._logger.warning(
                                "Sonos: Local webservice path '{path}' is not writeable for current user. "
                                "TTS disabled!".format(path=self._local_webservice_path))
                    else:
                        self._logger.warning("Sonos: Local webservice path '{path}' for TTS not exists. "
                                             "TTS disabled!".format(path=self._local_webservice_path))
                except OSError:
                    self._logger.warning("Sonos: Could not create local webserver path '{path}'. Wrong permissions? "
                                         "TTS disabled!".format(path=self._local_webservice_path))
            else:
                self._logger.debug("Sonos: Local webservice path for TTS has to be set. TTS disabled!")
        else:
            self._logger.debug("Sonos: TTS disabled")
        try:
            self._discover_cycle = int(discover_cycle)
        except:
            self._logger.error("Sonos: Parameter 'discover_cycle' [{val}] invalid, must be int.".format(
                val=discover_cycle
            ))
            self._discover_cycle = discover_cycle_default

        self._logger.info("Sonos: Setting discover cycle to {val} seconds.".format(val=self._discover_cycle))

    def run(self):
        self._logger.debug("Sonos: run method called")
        self._sh.scheduler.add("sonos_discover_scheduler", self._discover, prio=3, cron=None,
                               cycle=self._discover_cycle, value=None, offset=None, next=None)
        self.alive = True

    def stop(self):
        self._logger.debug("Sonos: stop method called")
        for uid, speaker in sonos_speaker.items():
            speaker.dispose()
        event_listener.stop()
        self.alive = False

    def parse_item(self, item: Item) -> object:
        """
        Parses an item
        :param item: item to parse
        :return: update function or None
        """
        uid = None

        if self.has_iattr(item.conf, 'sonos_recv') or self.has_iattr(item.conf, 'sonos_send'):
            self._logger.debug("parse item: {0}".format(item))
            # get uid from parent item
            uid = self._resolve_uid(item)
            if not uid:
                self._logger.error("Sonos: No uid found for {item}.".format(item=item))
                return

        if self.has_iattr(item.conf, 'sonos_recv'):
            # create Speaker instance if not exists
            _initialize_speaker(uid, self._logger)

            # to make code smaller, map sonos_cmd value to the Speaker property by name
            item_name = self.get_iattr_value(item.conf, 'sonos_recv')
            try:
                list_name = '{item_name}_items'.format(item_name=item_name)
                attr = getattr(sonos_speaker[uid], list_name)
                self._logger.debug(
                    "Sonos: Adding item {item} to {uid}: list {list}".format(item=item, uid=uid, list=list_name))
                attr.append(item)
            except:
                self.logger.warning("Sonos: No item list available for sonos_cmd '{item_name}'."
                                    .format(item_name=item_name))

        if self.has_iattr(item.conf, 'sonos_send'):
            self._logger.debug("Sonos: {item} registered to send Sonos commands.".format(item=item))
            return self.update_item

        # some special handling for dpt3 volume

        if self.has_iattr(item.conf, 'sonos_attrib'):
            if self.get_iattr_value(item.conf, 'sonos_attrib') != 'vol_dpt3':
                return

            # check, if a volume parent item exists
            parent_item = item.return_parent()

            if parent_item is not None:
                if self.has_iattr(parent_item.conf, 'sonos_recv'):
                    if self.get_iattr_value(parent_item.conf, 'sonos_recv').lower() != 'volume':
                        self._logger.warning("Sonos: volume_dpt3 item has no volume parent item. Ignoring!")
                else:
                    self._logger.warning("Sonos: volume_dpt3 item has no volume parent item. Ignoring!")
                    return

            item.conf['volume_parent'] = parent_item

            # make sure there is a child helper item
            child_helper = None
            for child in item.return_children():
                if self.has_iattr(child.conf, 'sonos_attrib'):
                    if self.get_iattr_value(child.conf, 'sonos_attrib').lower() == 'dpt3_helper':
                        child_helper = child
                        break

            if child_helper is None:
                self._logger.warning("Sonos: volume_dpt3 item has no helper item. Ignoring!")
                return

            item.conf['helper'] = child_helper

            if not self.has_iattr(item.conf, 'sonos_dpt3_step'):
                item.conf['sonos_dpt3_step'] = self._sonos_dpt3_step
                self._logger.debug("Sonos: No sonos_dpt3_step defined, using default value {step}.".
                                   format(step=self._sonos_dpt3_step))

            if not self.has_iattr(item.conf, 'sonos_dpt3_time'):
                item.conf['sonos_dpt3_time'] = self._sonos_dpt3_time
                self._logger.debug("Sonos: no sonos_dpt3_time defined, using default value {time}.".
                                   format(time=self._sonos_dpt3_time))

            return self._handle_dpt3

    def _handle_dpt3(self, item, caller=None, source=None, dest=None):
        if caller != 'Sonos':
            volume_item = self.get_iattr_value(item.conf, 'volume_parent')
            volume_helper = self.get_iattr_value(item.conf, 'helper')
            vol_max = self._resolve_max_volume_command(item)

            if vol_max < 0:
                vol_max = 100

            current_volume = int(volume_item())
            if current_volume < 0:
                current_volume = 0
            if current_volume > 100:
                current_volume = 100

            volume_helper(current_volume)
            vol_step = int(item.conf['sonos_dpt3_step'])
            vol_time = int(item.conf['sonos_dpt3_time'])

            if item()[1] == 1:
                if item()[0] == 1:
                    # up
                    volume_helper.fade(vol_max, vol_step, vol_time)
                else:
                    # down
                    volume_helper.fade(0 - vol_step, vol_step, vol_time)
            else:
                volume_helper(int(volume_helper() + 1))
                volume_helper(int(volume_helper() - 1))

    def parse_logic(self, logic):
        pass

    def update_item(self, item: Item, caller: object = str, source: object = str, dest: object = str) -> None:
        """
        Write items values
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if caller != 'Sonos':
            if self.has_iattr(item.conf, 'sonos_send'):
                # get uid from parent item
                uid = self._resolve_uid(item)
                if not uid:
                    self._logger.error("Sonos: No uid found for {item}.".format(item=item))
                    return

                command = self.get_iattr_value(item.conf, "sonos_send").lower()

                if command == "play":
                    if item():
                        sonos_speaker[uid].set_play()
                    else:
                        sonos_speaker[uid].set_pause()
                if command == "stop":
                    if item():
                        sonos_speaker[uid].set_stop()
                    else:
                        sonos_speaker[uid].set_play()
                if command == "pause":
                    if item():
                        sonos_speaker[uid].set_pause()
                    else:
                        sonos_speaker[uid].set_play()
                if command == "mute":
                    sonos_speaker[uid].set_mute(item())
                if command == "status_light":
                    sonos_speaker[uid].set_status_light(item())
                if command == "volume":
                    group_command = self._resolve_group_command(item)
                    max_volume = self._resolve_max_volume_command(item)
                    sonos_speaker[uid].set_volume(item(), group_command, max_volume)
                if command == "bass":
                    group_command = self._resolve_group_command(item)
                    sonos_speaker[uid].set_bass(item(), group_command)
                if command == "treble":
                    group_command = self._resolve_group_command(item)
                    sonos_speaker[uid].set_treble(item(), group_command)
                if command == "loudness":
                    group_command = self._resolve_group_command(item)
                    sonos_speaker[uid].set_loudness(item(), group_command)
                if command == "night_mode":
                    sonos_speaker[uid].set_night_mode(item())
                if command == "dialog_mode":
                    sonos_speaker[uid].set_dialog_mode(item())
                if command == "cross_fade":
                    sonos_speaker[uid].set_cross_fade(item())
                if command == "snooze":
                    sonos_speaker[uid].set_snooze(item())
                if command == "play_mode":
                    sonos_speaker[uid].set_play_mode(item())
                if command == "next":
                    sonos_speaker[uid].set_next(item())
                if command == "previous":
                    sonos_speaker[uid].set_previous(item())
                if command == "switch_linein":
                    if item():
                        sonos_speaker[uid].switch_to_line_in()
                if command == "switch_tv":
                    if item():
                        sonos_speaker[uid].switch_to_tv()
                if command == "play_tunein":
                    start = self._resolve_child_command_bool(item, 'start_after')
                    sonos_speaker[uid].play_tunein(item(), start)
                if command == "play_url":
                    start = self._resolve_child_command_bool(item, 'start_after')
                    sonos_speaker[uid].play_url(item(), start)
                if command == "join":
                    sonos_speaker[uid].join(item())
                if command == "unjoin":
                    start = self._resolve_child_command_bool(item, 'start_after')
                    sonos_speaker[uid].unjoin(item(), start)
                if command == 'load_sonos_playlist':
                    start = self._resolve_child_command_bool(item, 'start_after')
                    clear_queue = self._resolve_child_command_bool(item, 'clear_queue')
                    track = self._resolve_child_command_int(item, 'start_track')
                    sonos_speaker[uid].load_sonos_playlist(item(), start, clear_queue, track)
                if command == 'play_tts':
                    if item() == "":
                        return
                    language = self._resolve_child_command_str(item, 'tts_language', 'de')
                    volume = self._resolve_child_command_int(item, 'tts_volume', -1)
                    fade_in = self._resolve_child_command_bool(item, 'tts_fade_in')
                    sonos_speaker[uid].play_tts(item(), language, self._local_webservice_path, self._webservice_url,
                                                volume, fade_in)
                if command == 'play_snippet':
                    if item() == "":
                        return
                    volume = self._resolve_child_command_int(item, 'snippet_volume', -1)
                    fade_in = self._resolve_child_command_bool(item, 'snippet_fade_in')
                    sonos_speaker[uid].play_snippet(item(), self._local_webservice_path_snippet, self._webservice_url, volume,
                                                    fade_in)

    def _resolve_child_command_str(self, item: Item, child_command, default_value="") -> str:
        """
        Resolves a child command of type str for an item
        :type child_command: The sonos_attrib name for the child
        :type default_value: the default value, if the child not exists or an error occurred
        :param item: The item for which a child item is to be searched
        :rtype: str
        :return: String value of the child item or the given default value.
        """
        for child in item.return_children():
            if self.has_iattr(child.conf, 'sonos_attrib'):
                if self.get_iattr_value(child.conf, 'sonos_attrib') == child_command:
                    if child() == "":
                        return default_value
                    return child()
        return default_value

    def _resolve_child_command_bool(self, item: Item, child_command) -> bool:
        """
        Resolves a child command of type bool for an item
        :type child_command: The sonos_attrib name for the child
        :param item: The item for which a child item is to be searched
        :rtype: bool
        :return: 'True' or 'False'
        """
        for child in item.return_children():
            if self.has_iattr(child.conf, 'sonos_attrib'):
                if self.get_iattr_value(child.conf, 'sonos_attrib') == child_command:
                    return child()
        return False

    def _resolve_child_command_int(self, item: Item, child_command, default_value=0) -> int:
        """
        Resolves a child command of type int for an item
        :type default_value: the default value, if the child not exists or an error occurred
        :type child_command: The sonos_attrib name for the child
        :param item: The item for which a child item is to be searched
        :rtype: int
        :return: value as int or if no item was found the given default value
        """
        try:
            for child in item.return_children():
                if self.has_iattr(child.conf, 'sonos_attrib'):
                    if self.get_iattr_value(child.conf, 'sonos_attrib') == child_command:
                        return int(child())
            return default_value
        except:
            self._logger.warning("Sonos: Could not cast value [{val}] to 'int', using default value '0'")
            return default_value

    def _resolve_group_command(self, item: Item) -> bool:
        """
        Resolves a group_command child for an item
        :rtype: bool
        :param item: The item for which a child item is to be searched
        :return: 'True' or 'False' (whether the command should execute as a group command or not)
        """
        # special handling for dpt_volume
        if self.get_iattr_value(item.conf, 'sonos_attrib') == 'vol_dpt3':
            group_item = self.get_iattr_value(item.conf, 'volume_parent')
        else:
            group_item = item

        for child in group_item.return_children():
            if self.has_iattr(child.conf, 'sonos_attrib'):
                if self.get_iattr_value(child.conf, 'sonos_attrib') == "group":
                    return child()
        return False

    def _resolve_max_volume_command(self, item: Item) -> int:

        if self.get_iattr_value(item.conf, 'sonos_attrib') == 'vol_dpt3':
            volume_item = self.get_iattr_value(item.conf, 'volume_parent')
        else:
            volume_item = item

        for child in volume_item.return_children():
            if self.has_iattr(child.conf, 'sonos_attrib'):
                if self.get_iattr_value(child.conf, 'sonos_attrib') == "max_volume":
                    try:
                        return int(child())
                    except Exception as ex:
                        self._logger.error(ex)
                        return -1
        return -1

    def _resolve_uid(self, item: Item) -> str:
        """
        Tries to find the uuid (typically the parent item) of an item
        :rtype: str
        :param item: item to search for the uuid
        :return: the speakers uuid
        """
        parent_item = None
        # some special handling for dpt3 helper item
        if self.has_iattr(item.conf, 'sonos_attrib'):
            if self.get_iattr_value(item.conf, 'sonos_attrib').lower() == 'dpt3_helper':
                parent_item = item.return_parent().return_parent().return_parent()
        else:
            parent_item = item.return_parent()

        if parent_item is not None:
            if self.has_iattr(parent_item.conf, 'sonos_uid'):
                return self.get_iattr_value(parent_item.conf, 'sonos_uid').lower()

        self._logger.warning("Sonos: could not resolve sonos_uid for item {item}".format(item=item))
        return ''

    def _discover(self) -> None:
        """
        Discover Sonos speaker in the network. If the plugin parameter 'speaker_ips' has IP addresses, no discover
        package is sent over the network.
        :rtype: None
        """
        handled_speaker = {}

        zones = []
        if self._speaker_ips:
            for ip in self._speaker_ips:
                zones.append(SoCo(ip))
        else:
            zones = soco.discover(timeout=5)

        # 1. attempt: don't touch our speaker, return and wait for next interval
        # 2. attempt: ok, no speaker found, go on
        if not zones:
            if not self.zero_zone:
                self._logger.debug("Sonos: No speaker found (1. attempt), ignoring speaker handling.")
                self.zero_zone = True
                return
            self._logger.debug("Sonos: No speaker found.")
        self.zero_zone = False

        for zone in zones:
            if zone.uid is None:
                is_up = False
            else:
                uid = zone.uid.lower()
                # don't trust the discover function, offline speakers can be cached
                # we try to ping the speaker
                with open(os.devnull, 'w') as DEVNULL:
                    try:
                        subprocess.check_call(['ping', '-i', '0.2', '-c', '2', zone.ip_address],
                                              stdout=DEVNULL, stderr=DEVNULL, timeout=1)
                        is_up = True
                    except subprocess.CalledProcessError:
                        is_up = False
                    except subprocess.TimeoutExpired:
                        is_up = False

            if is_up:
                self._logger.debug("Sonos: Speaker found: {zone}, {uid}".format(zone=zone.ip_address, uid=uid))
                if uid in sonos_speaker:
                    if zone is not sonos_speaker[uid].soco:
                        sonos_speaker[uid].soco = zone
                        sonos_speaker[uid].subscribe_base_events()
                    else:
                        self._logger.debug("Sonos: SoCo instance already initiated, skipping.")
                        self._logger.debug("Sonos: checking subscriptions")
                        sonos_speaker[uid].check_subscriptions()

                else:
                    _initialize_speaker(uid, self._logger)

                sonos_speaker[uid].is_initialized = True
                sonos_speaker[uid].refresh_static_properties()

            else:
                if sonos_speaker[uid].soco is not None:
                    self._logger.debug(
                        "Sonos: Disposing offline speaker: {zone}, {uid}".format(zone=zone.ip_address, uid=uid))
                    sonos_speaker[uid].dispose()
                else:
                    self._logger.debug(
                        "Sonos: Ignoring offline speaker: {zone}, {uid}".format(zone=zone.ip_address, uid=uid))

                sonos_speaker[uid].is_initialized = False

            if uid in sonos_speaker:
                handled_speaker[uid] = sonos_speaker[uid]

        # dispose every speaker that was not found
        for uid in set(sonos_speaker.keys()) - set(handled_speaker.keys()):
            if sonos_speaker[uid].soco is not None:
                self._logger.debug(
                    "Sonos: Removing undiscovered speaker: {zone}, {uid}".format(zone=zone.ip_address, uid=uid))
                sonos_speaker[uid].dispose()


def _initialize_speaker(uid: str, logger: logging) -> None:
    """
    Create a Speaker object by a given uuid
    :param uid: uid of the speaker
    :param logger: logger instance
    """
    with _create_speaker_lock:
        if uid not in sonos_speaker:
            sonos_speaker[uid] = Speaker(uid=uid, logger=logger)
