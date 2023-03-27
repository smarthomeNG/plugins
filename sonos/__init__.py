#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-       pfischi, aschwith, sisamiwe                    #
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

import io
import os
import logging
import re
import socketserver
import subprocess
import threading
import time
import sys
import requests

from requests.utils import quote
from collections import OrderedDict
from http.server import HTTPServer, BaseHTTPRequestHandler
from queue import Empty
from urllib.parse import unquote

from . import utils

from .soco import *
from .soco.exceptions import SoCoUPnPException
from .soco.music_services import MusicService
from .soco.data_structures import to_didl_string, DidlItem, DidlMusicTrack
from .soco.events import event_listener
from .soco.music_services.data_structures import get_class
from .soco.snapshot import Snapshot
from .soco.xml import XML
from .soco.plugins.sharelink import ShareLinkPlugin

import xmltodict
from tinytag import TinyTag
from gtts import gTTS

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface

_create_speaker_lock = threading.Lock()                         # make speaker object creation thread-safe
sonos_speaker = {}                                              # dict to hold all speaker information with soco objects

# Planned Enhancement
######################
# ToDo: Itemattribute einführen, dass immer mit dem abgespielten Inhalt gefüllt wird
# ToDo: Methode implementieren, die TTS auf allen verfügbaren Speakern abspielt  "play_tts_all" / PartyMode
# ToDo: Operating on All Speakers: Using _all_ as Speaker name


class WebserviceHttpHandler(BaseHTTPRequestHandler):
    webroot = None

    def __init__(self, request, client_address, server):
        self.logger = logging.getLogger('Sonos-WebserviceHttpHandler')  # get a unique logger for the plugin and provide it internally
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
            raise Exception(f"Cannot determine mime-type for extension '{extension}'.")

        except Exception as e:
            self.logger.warning(f"Exception in _get_mime_type_by_filetype: {e}")
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
                self.send_error(406, 'File with unsupported media type : %s' % self.path)
                return

            client = f"{self.client_address[0]}:{self.client_address[1]}"
            self.logger.debug(f"Webservice: delivering file '{file_path}' to client ip {client}.")
            file = open(file_path, 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', sys.getsizeof(file))
            self.end_headers()
            self.wfile.write(file)
        except ConnectionResetError:
            self.logger.debug("Connection reset by partner")
        except IOError as ex:
            if ex.errno == errno.EPIPE:
                # EPIPE error
                self.logger.error(f"EPipe exception occurred while delivering file {file_path}")
                self.logger.error(f"Exception: {ex}")
            else:
                # Other error
                self.logger.error(f"Error delivering file {file_path}")
                self.logger.error(f"Exception: {ex}")
        except Exception as ex:
            self.logger.error(f"Error delivering file {file_path}")
            self.logger.error(f"do_GET: Exception: {ex}")
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
        self.thread = threading.Thread(target=self.server.serve_forever, name='SonosTTSServer')
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


def renew_error_callback(exception):  # events_twisted: failure
    msg = f'Error received on autorenew: {exception}'
    # Redundant, as the exception will be logged by the events module
    self.logger.error(msg)

    # ToDo possible improvement: Do not do periodic renew but do prober disposal on renew failure here instead. sub.renew(requested_timeout=10)


class SubscriptionHandler(object):
    def __init__(self, endpoint, service, logger, threadName):
        self._lock = threading.Lock()
        self._thread = None
        self._service = service
        self._endpoint = endpoint
        self._event = None
        self._signal = threading.Event()
        self.logger = logger
        self._threadName = threadName

    def subscribe(self):
        self.logger.dbglow(f"start subscribe for endpoint {self._endpoint}")
        if 'eventAvTransport' in self._threadName:
            self.logger.dbghigh(f"subscribe(): endpoint av envent detected. Enabling debugging logs")
            debug = 1
        else:
            debug = 0

        if debug:
            self.logger.dbghigh(f"subscribe(): start for endpoint {self._endpoint}")

        with self._lock:
            if debug:
                self.logger.dbghigh(f"subscribe(): clearing signal Event for endpoint {self._endpoint}")
            self._signal.clear()
            
            # Check if signal was cleared correctly:
            if self._signal.is_set():
                self.logger.error(f"subscribe(): Event could not be cleared correctly for service {self._service}")
            else:
                self.logger.dbghigh(f"subscribe(): Event cleared successfully. Thread can be started for service {self._service}")

            try:
                self._event = self._service.subscribe(auto_renew=False)
                # No benefits of automatic renew could be observed. 
                # self._event = self._service.subscribe(auto_renew=True)

            except Exception as e:
                self.logger.error(f"Exception in subscribe(): {e}")
            if self._event:
                if debug:
                    self.logger.dbghigh(f"subscribe(): event valid, starting new thread for endpoint {self._endpoint}")

                try:
                    self._event.auto_renew_fail = renew_error_callback
                    self._thread = threading.Thread(target=self._endpoint, name=self._threadName, args=(self,))
                    self._thread.setDaemon(True)
                    self._thread.start()
                    self.logger.debug(f"start subscribe finished successfully")
                    if not self._thread.is_alive(): 
                        self.logger.error("Critical error in subscribe method: Thread could not be startet and is not alive.")
                    else:
                        if debug:
                            self.logger.dbghigh(f"Debug subscribe: Thread startet successfully for service {self._service}")

                except Exception as e:
                    self.logger.error(f"Exception in subscribe() at point b: {e}")

            else:
                self.logger.error(f"subscribe(): Error in subscribe for endpoint {self._endpoint}: self._event not valid")
        if debug:
            self.logger.dbghigh(f"subscribe() {self._endpoint}: lock released. Self._service is {self._service}")

    def unsubscribe(self):
        self.logger.dbglow(f"unsubscribe(): start for endpoint {self._endpoint}")
        if 'eventAvTransport' in self._threadName:
            self.logger.dbghigh(f"unsubscribe: endpoint av envent detected. Enabling debugging logs")
            debug = 1
        else:
            debug = 0
        if debug:
            self.logger.dbghigh(f"unsubscribe(): start for endpoint {self._endpoint}")

        with self._lock:
            if self._event:
                # try to unsubscribe first
                try:
                    self._event.unsubscribe()
                except Exception as e:
                    self.logger.warning(f"Exception in unsubscribe(): {e}")
                self._signal.set()
                if self._thread:
                    self.logger.dbglow("Preparing to terminate thread")
                    if debug:
                        self.logger.dbghigh(f"unsubscribe(): Preparing to terminate thread for endpoint {self._endpoint}")
                    self._thread.join(2)
                    if debug:
                        self.logger.dbghigh(f"unsubscribe(): Thread joined for endpoint {self._endpoint}")

                    if not self._thread.is_alive(): 
                        self.logger.dbglow("Thread killed for enpoint {self._endpoint}")
                        if debug:
                            self.logger.dbghigh(f"Thread killed for endpoint {self._endpoint}")

                    else:
                        self.logger.error("unsubscibe(): Error, thread is still alive")
                    self._thread = None
                self.logger.info(f"Event {self._endpoint} unsubscribed and thread terminated")
                if debug:
                    self.logger.dbghigh(f"unsubscribe(): Event {self._endpoint} unsubscribed and thread terminated")
            else:
                if debug: 
                    self.logger.warning(f"unsubscribe(): {self._endpoint}: self._event not valid")
        if debug:
            self.logger.dbghigh(f"unsubscribe(): {self._endpoint}: lock released")


    @property
    def eventSignalIsSet(self):
        if self._signal:
            return self._signal.is_set()
        return False

    @property
    def subscriptionThreadIsActive(self):
        if self._thread:
            return self._thread.is_alive()
        return False

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
    def is_subscribed(self):
        if self._event:
            return self._event.is_subscribed
        return False


class Speaker(object):
    def __init__(self, uid, logger, plugin_shortname):
        self.logger = logger
        self.plugin_shortname = plugin_shortname
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
        self.buttons_enabled_items = []
        self._buttons_enabled = False
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
        self.sonos_favorites_items = []
        self.favorite_radio_stations_items = []
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
            item(self.uid, self.plugin_shortname)

    @property
    def soco(self):
        return self._soco

    @soco.setter
    def soco(self, value):
        if self._soco != value:
            self._soco = value
            self._is_coordinator = self._soco.is_coordinator
            self.coordinator = self.soco.group.coordinator.uid.lower()
            self.uid = self.soco.uid.lower()
            self.household_id = self.soco.household_id

            # self.logger.debug(f"uid: {self.uid}: soco set to {value}")
            if self._soco:
                self.render_subscription = \
                    SubscriptionHandler(endpoint=self._rendering_control_event, service=self._soco.renderingControl,
                                        logger=self.logger, threadName=f"sonos_{self.uid}_eventRenderingControl")
                self.av_subscription = \
                    SubscriptionHandler(endpoint=self._av_transport_event, service=self._soco.avTransport,
                                        logger=self.logger, threadName=f"sonos_{self.uid}_eventAvTransport")
                self.system_subscription = \
                    SubscriptionHandler(endpoint=self._system_properties_event, service=self._soco.systemProperties,
                                        logger=self.logger, threadName=f"sonos_{self.uid}_eventSystemProperties")
                self.zone_subscription = \
                    SubscriptionHandler(endpoint=self._zone_topology_event, service=self._soco.zoneGroupTopology,
                                        logger=self.logger, threadName=f"sonos_{self.uid}_eventZoneTopology")
                self.alarm_subscription = \
                    SubscriptionHandler(endpoint=self._alarm_event, service=self._soco.alarmClock,
                                        logger=self.logger, threadName=f"sonos_{self.uid}_eventAlarmEvent")
                self.device_subscription = \
                    SubscriptionHandler(endpoint=self._device_properties_event, service=self._soco.deviceProperties,
                                        logger=self.logger, threadName=f"sonos_{self.uid}_eventDeviceProperties")

                # just to have a list for disposing all events
                self._events = [
                    self.av_subscription,
                    self.render_subscription,
                    self.system_subscription,
                    self.zone_subscription,
                    self.alarm_subscription,
                    self.device_subscription
                ]

    def dispose(self):
        """
        clean-up all things here
        """
        self.logger.debug(f"{self.uid}: disposing")

        if not self._soco:
            return

        for subscription in self._events:
            try:
                subscription.unsubscribe()
            except Exception as error:
                self.logger.warning(f"Exception in dispose(): {error}")
                continue

        self._soco = None

    def subscribe_base_events(self):
        if not self._soco:
            self.logger.error("Error in subscribe_base_events: self._soco not valid.")
            return
        self.logger.debug("Start subscribe base event fct")
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

        # Important note:
        # av event is not subscribed here because it has special handling in function zone group event. 
        pass
        

    def refresh_static_properties(self) -> None:
        """
        This function is called by the plugins discover function. This is typically called every 180sec.
        We're using this cycle to update some properties that are not updated by events
        """
        if not self._check_property():
            return

        # do this only for the coordinator, don't stress the network
        if self.is_coordinator:
            if self.snooze > 0:
                self.snooze = self.get_snooze()
        self.status_light = self.get_status_light()
        self.buttons_enabled = self.get_buttons_enabled()
        self.sonos_playlists()
        self.sonos_favorites()
        self.favorite_radio_stations()

    def check_subscriptions(self) -> None:

        self.logger.debug("Start check_subscriptions fct")

        self.zone_subscription.unsubscribe()
        self.zone_subscription.subscribe()

        self.system_subscription.unsubscribe()
        self.system_subscription.subscribe()

        self.alarm_subscription.unsubscribe()
        self.alarm_subscription.subscribe()

        self.render_subscription.unsubscribe()
        self.render_subscription.subscribe()

        self.av_subscription.unsubscribe()
        self.av_subscription.subscribe()

        # sometimes a discover fails --> coordinator is empty --> resubscribe zone topology event
        self.zone_subscription.unsubscribe()
        self.zone_subscription.subscribe()

        self.logger.debug(f"{self.uid}: Event subscriptions done")

    # Event Handler routines ###########################################################################################

    def _rendering_control_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        Rendering Control event handling
        :param sub_handler: SubscriptionHandler for the rendering control event
        """
        try:
            self.logger.debug(f"{self.uid}: rendering control event handler active")
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
                    self.logger.debug(f"rendering_control_event: {self.uid}: event variables: {event.variables}")
                    sub_handler.event.events.task_done()
                    del event
                except Empty:
                    pass
        except Exception as ex:
            self.logger.error(f"_rendering_control_event: Error {ex} occurred.")

    def _alarm_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        AlarmClock event handling
        :param sub_handler: SubscriptionHandler for the alarm event
        """
        try:
            self.logger.debug(f"{self.uid}: alarm clock event handler active")
            while not sub_handler.signal.wait(1):
                try:
                    event = sub_handler.event.events.get(timeout=0.5)
                    # self.logger.debug(f"Sonos alarms: {self.uid}: event variables: {event.variables}")
                    sub_handler.event.events.task_done()
                    del event
                except Empty:
                    pass
        except Exception as ex:
            self.logger.error(f"_alarm_event: Error {ex} occurred.")

    def _system_properties_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        System properties event handling
        :param sub_handler: SubscriptionHandler for the system properties event
        """
        try:
            self.logger.debug(f"{self.uid}: system properties event handler active")
            while not sub_handler.signal.wait(1):
                try:
                    event = sub_handler.event.events.get(timeout=0.5)
                    # self.logger.debug(f"Sonos props: {self.uid}: event variables: {event.variables}")
                    sub_handler.event.events.task_done()
                    del event
                except Empty:
                    pass
        except Exception as ex:
            self.logger.error(f"_system_properties_event: Error {ex} occurred.")

    def _device_properties_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        Device properties event handling
        :param sub_handler: SubscriptionHandler for the device properties event
        """
        try:
            self.logger.debug(f"{self.uid}: device properties event handler active")
            while not sub_handler.signal.wait(1):
                try:
                    event = sub_handler.event.events.get(timeout=0.5)
                    if 'zone_name' in event.variables:
                        if event.variables['zone_name']:
                            self.player_name = event.variables['zone_name']
                        else:
                            self.player_name = "unknown"
                    sub_handler.event.events.task_done()
                    del event
                except Empty:
                    pass
        except Exception as ex:
            self.logger.error(f"_device_properties_event: Error {ex} occurred.")

    def _zone_topology_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        Zone topology event handling
        :param sub_handler: SubscriptionHandler for the zone topology event
        """
        try:
            self.logger.debug(f"{self.uid}: topology event handler active")
            while not sub_handler.signal.wait(1):
                try:
                    event = sub_handler.event.events.get(timeout=0.5)
                    if 'zone_group_state' in event.variables:
                        tree = XML.fromstring(event.variables['zone_group_state'].encode('utf-8'))
                        # find group where our uid is located
                        for group_element in tree.find('ZoneGroups').findall('ZoneGroup'):
                            coordinator_uid = group_element.attrib['Coordinator'].lower()
                            zone_group_member = []
                            uid_found = False
                            for member_element in group_element.findall('ZoneGroupMember'):
                                member_uid = member_element.attrib['UUID'].lower()
                                _initialize_speaker(member_uid, self.logger, self.plugin_shortname)
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
                                self.buttons_enabled = self.get_buttons_enabled()
                                self.sonos_playlists()
                                self.sonos_favorites()
                                self.favorite_radio_stations()

                    sub_handler.event.events.task_done()
                    del event
                except Empty:
                    pass
        except Exception as ex:
            self.logger.error(f"_zone_topology_event: Error {ex} occurred.")

    def _av_transport_event(self, sub_handler: SubscriptionHandler) -> None:
        """
        AV event handling
        :param sub_handler: SubscriptionHandler for the av transport event
        """
        if sub_handler is None:
            self.logger.error(f"_av_transport_event: SubscriptionHandler is None.")

        self.logger.dbghigh(f"_av_transport_event: {self.uid}: av transport event handler active.")
        while not sub_handler.signal.wait(1):
            self.logger.dbgmed(f"_av_transport_event: {self.uid}: start try")

            try:
                event = sub_handler.event.events.get(timeout=0.5)
            except Empty:
                #self.logger.dbglow(f"av_transport_event: got empty exception, which is normal")
                pass
            except Exception as e:
                self.logger.error(f"_av_tranport_event: Exception during events.get(): {e}")
            else:

                self.logger.dbghigh(f"_av_transport_event: {self.uid}: received event")

                # set streaming type
                try:
                    is_playing_line_in = self.soco.is_playing_line_in
                    is_playing_tv = self.soco.is_playing_tv
                    is_playing_radio = self.soco.is_playing_radio
                except Exception as e:
                    self.logger.error(f"_av_tranport_event: Exception during soco.get functions: {e}")
                else:
                    if is_playing_line_in:
                        self.streamtype = "line_in"
                    elif is_playing_tv:
                        self.streamtype = "tv"
                    elif is_playing_radio:
                        self.streamtype = "radio"
                    else:
                        self.streamtype = "music"

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
                        if isinstance(radio_metadata, str):
                            radio_station = radio_metadata[radio_metadata.find('<dc:title>') + 10:radio_metadata.find('</dc:title>')]
                        elif hasattr(radio_metadata, 'title'):
                            radio_station = str(radio_metadata.title)
                        else:
                            radio_station = ""
                        self.radio_station = radio_station
                else:
                    self.radio_station = ''
    
                sub_handler.event.events.task_done()
                del event
                self.logger.dbghigh(f"av_transport_event() for {self.uid}: task_done()")

        self.logger.dbghigh(f"av_transport_event(): {self.uid}: while loop terminated.")

    def _check_property(self):
        if not self.is_initialized:
            self.logger.warning(f"Speaker '{self.uid}' is not initialized.")
            return False
        if not self.coordinator:
            self.logger.warning(f"Speaker '{self.uid}': coordinator is empty")
            return False
        if self.coordinator not in sonos_speaker:
            self.logger.warning(f"{self.uid}: coordinator '{self.coordinator}' is not a valid speaker.")
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
            self.logger.warning(f"{self.uid}: value={value} for setter _zone_group_members must be type of list.")
            return
        self._zone_group = value
        # set zone_group_members (string representation)
        members = []
        for member in self._zone_group:
            if member.uid != '':
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
            item(self.is_initialized, self.plugin_shortname)

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
            item(self.player_name, self.plugin_shortname)

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
            item(self.household_id, self.plugin_shortname)

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
            item(self.night_mode, self.plugin_shortname)

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
            self.logger.warning(f"set_night_mode: can't set night mode for {self.uid}. Not supported. Error {ex}")
            return False

    @property
    def buttons_enabled(self) -> bool:
        """
        Returns the current buttons enabled setting of the speaker.
        :return: True or False
        """
        return self._buttons_enabled

    @buttons_enabled.setter
    def buttons_enabled(self, buttons_enabled: bool) -> None:
        """
        Setter for buttons_enabled (internal)
        :param buttons_enabled: True or False
        :rtype: None
        :return: None
        """
        if self._buttons_enabled == buttons_enabled:
            return
        self._buttons_enabled = buttons_enabled
        for item in self.buttons_enabled_items:
            item(self.buttons_enabled, self.plugin_shortname)

    def set_buttons_enabled(self, buttons_enabled: bool) -> bool:
        """
        Calls the SoCo functionality buttons_enabled to set this setting to the speaker. This mode is not available for non-visible speakers (e.g. stereo slaves).
        :rtype: bool
        :param buttons_enabled: True or False
        :return: 'True' if success, 'False' otherwise
        """
        try:
            self.soco.buttons_enabled = buttons_enabled
            self.buttons_enabled = buttons_enabled
            return True
        except Exception as ex:
            self.logger.warning(f"set_buttons_enabled: Can't set buttons enabled state for {self.uid}. Not supported. Error {ex} occurred.")
            return False

    def get_buttons_enabled(self) -> bool:
        """
        Calls the SoCo function to get the buttons enabled status of the speaker.
        :rtype: bool
        :return: 'True' for buttons enabled, 'False' for buttons disabled
        """
        try:
            return self.soco.buttons_enabled
        except Exception as ex:
            self.logger.error(f"get_buttons_enabled: Error {ex} occurred.")
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
            item(self.dialog_mode, self.plugin_shortname)

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
            self.logger.warning(f"set_dialog_mode: Can't set dialog mode for {self.uid}. Not supported. Error {ex} occurred.")
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
            item(self.loudness, self.plugin_shortname)

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
            self.logger.error(f"set_loudness: Error {ex} occurred.")
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
            item(self.treble, self.plugin_shortname)

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
                raise Exception('Treble has to be an integer between -10 and 10.')
            if group_command:
                for member in self.zone_group_members:
                    sonos_speaker[member].soco.treble = treble
                    sonos_speaker[member].treble = treble
            else:
                self.soco.treble = treble
                self.treble = treble
            return True
        except Exception as ex:
            self.logger.error(f"set_treble: Error {ex} occurred.")
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
            item(self.bass, self.plugin_shortname)

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
                raise Exception('Bass has to be an integer between -10 and 10.')
            if group_command:
                for member in self.zone_group_members:
                    sonos_speaker[member].soco.bass = bass
                    sonos_speaker[member].bass = bass
            else:
                self.soco.bass = bass
                self.bass = bass
            return True
        except Exception as ex:
            self.logger.error(f"set_bass: Error {ex} occurred.")
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
            item(self.volume, self.plugin_shortname)

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
                # raise Exception('Volume has to be an integer between 0 and 100.')

            if self._check_max_volume_exceeded(volume, max_volume):
                self.logger.debug(f"Volume to set [{volume}] exceeds max volume [{max_volume}].")
                volume = max_volume

            if group_command:
                for member in self.zone_group_members:
                    if member != '':
                        self.logger.debug(f"set_volume: Setting {member} to volume {volume}")
                        sonos_speaker[member].soco.volume = volume
                        sonos_speaker[member].volume = volume
            else:
                self.soco.volume = volume
                self.volume = volume
            return True
        except Exception as ex:
            self.logger.error(f"set_volume: Error {ex} occurred.")
            return False

    def switch_to_tv(self) -> bool:
        """
        Switch the playbar speaker's input to TV. Only supported by Sonos Playbar yet.
        :return: 'True' to switch the playbar speaker's input to TV, otherwise 'False' (error, e.g unsupported model)
        """
        try:
            return self.soco.switch_to_tv()
        except Exception as ex:
            self.logger.warning(f"switch_to_tv: Can't switch {self.uid} to TV. Not supported. Error {ex} occurred.")
            return False

    def switch_to_line_in(self) -> bool:
        """
        Switches the audio input to line-in. Only for supported speaker, e.g. Sonos Play5
        :return: 'True' to switch to line-in, otherwise 'False' (error, e.g unsupported model)
        """
        try:
            return self.soco.switch_to_line_in()
        except Exception as ex:
            self.logger.warning(f"switch_to_line_in: : Can't switch {self.uid} to line-in. Not supported. Error {ex} occurred.")
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
            item(self.status_light, self.plugin_shortname)

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
            self.logger.debug(f"set_status_light: Error {ex} occurred.")
            return False

    def get_status_light(self) -> bool:
        """
        Calls the SoCo function to get the LED status of the speaker.
        :rtype: bool
        :return: 'True' for Led on, 'False' for Led off or Exception
        """
        try:
            return self.soco.status_light
        except Exception as ex:
            self.logger.error(f"get_status_light: Error {ex} occurred.")
            return False

    def get_reboot_count(self) -> int:
        """
        Calls the SoCo function to get the number of reboots.
        :rtype: int
        :return: number of reboots
        """
        try:
            return self.soco.boot_seqnum
        except Exception as ex:
            self.logger.error(f"get_reboot_count: Error {ex} occurred.")
            return 0

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
            item(self.coordinator, self.plugin_shortname)

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
            self.logger.error(f"zone_group_members: {self.uid}: value={value} for setter zone_group_members must be type of list.")
            return
        self._members = value

        for item in self.zone_group_members_items:
            item(self.zone_group_members, self.plugin_shortname)

        # if we are the coordinator: un-register av events for slave speakers
        # re-init subscriptions for the master

        if self.is_coordinator:
            for member in self._zone_group_members:
                self.logger.dbglow(f"****zone_group_members: {member=}")
                if member is not self:
                    try:
                        self.logger.dbghigh(f"zone_group_members(): Unsubscribe av event for uid '{self.uid}' in fct zone_group_members")
                        member.av_subscription.unsubscribe()
                    except Exception as e:
                        self.logger.warning(f"Unsubscribe av event for uid '{self.uid}' in fct zone_group_members caused error {e}")
                        pass
                else:
                    # Register AV event for coordinator speakers: 
                    #self.logger.dbglow(f"Un/Subscribe av event for uid '{self.uid}' in fct zone_group_members")

                    active = member.av_subscription.subscriptionThreadIsActive
                    is_subscribed = member.av_subscription.is_subscribed
                    self.logger.dbghigh(f"zone_group_members(): Subscribe av event for uid '{self.uid}': Status before measure: AV Thread is {active}, subscription is {is_subscribed}, Eventflag: {member.av_subscription.eventSignalIsSet}")

                    if active == False:
                        self.logger.dbghigh(f"zone_group_members: Subscribe av event for uid '{self.uid}' because thread is not active")
                        #member.av_subscription.unsubscribe()
                        #
                        # Workaround:
                        # member.av_subscription.update_endpoint(endpoint=self._av_transport_event)
                        member.av_subscription.subscribe()
                        self.logger.dbghigh(f"zone_group_members: Subscribe av event for uid '{self.uid}': Status after measure: AV thread is {member.av_subscription.subscriptionThreadIsActive}, subscription {member.av_subscription.is_subscribed}, Eventflag: {member.av_subscription.eventSignalIsSet}")
                    

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

        if self.is_coordinator:
            for member in self.zone_group_members:
                for item in sonos_speaker[member].streamtype_items:
                    item(self.streamtype, self.plugin_shortname)

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

        # coordinator call / update all items
        if self.is_coordinator:
            for member in self.zone_group_members:
                for item in sonos_speaker[member].track_uri_items:
                    item(self.track_uri, self.plugin_shortname)
        # slave call, update just the slave
        else:
            for item in self.track_uri_items:
                item(self.track_uri, self.plugin_shortname)

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
                item(value, self.plugin_shortname)

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
                item(value, self.plugin_shortname)

    def set_pause(self) -> bool:
        """
        Calls the SoCo pause method and pauses the current track.
        :return: True, if successful, otherwise False.
        """
        if not self._check_property():
            return False
        try:
            ret = sonos_speaker[self.coordinator].soco.pause()
        except Exception as e:
            self.logger.warning(f"Exception during set_pause: {e}")
            return False
        else:
            if not ret:
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
                item(value, self.plugin_shortname)

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
            except Exception:
                self.logger.debug(f"{self.uid}: can't go to next track. Maybe the end of the playlist reached?")

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
            except Exception:
                self.logger.debug(f"{self.uid}: can't go back to the previously played track. Already the first track in the playlist?")

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
                item(value, self.plugin_shortname)

    def set_mute(self, value: bool, group_command: bool = True) -> bool:
        """
        Calls the SoCo mute method and mutes / unmutes the speaker.
        :param value: True for mute, False for unmute
        :param group_command: Should the mute command be set to all speaker of the group? Default: True
        :return: True, if successful, otherwise False.
        """
        self.logger.debug(f"set_mute: self.coordinator: {self.coordinator}, check_property: {self._check_property()}")
        try:
            if not self._check_property():
                return False            

            if group_command:
                for member in self.zone_group_members:
                    sonos_speaker[member].soco.mute = value
            else:
                sonos_speaker[self.coordinator].soco.mute = value

            return True
        except Exception as ex:
            self.logger.error(f"set_mute: Error {ex} occurred.")
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
                item(cross_fade, self.plugin_shortname)

    def set_cross_fade(self, cross_fade: bool) -> bool:
        """
        Calls the SoCo cross_fade method and sets the cross-fade setting for the speaker.
        :param cross_fade: 'True' for cross_fade on, 'False' for cross_fade off
        :return: True, if successful, otherwise False.
        """
        try:
            if not self._check_property():
                return False
            sonos_speaker[self.coordinator].soco.cross_fade = cross_fade
            return True
        except Exception as ex:
            self.logger.error(f"set_cross_fade: Error {ex} occurred.")
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
                item(snooze, self.plugin_shortname)

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
            self.logger.error(f"set_snooze: Error {ex} occurred.")
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
            self.logger.error(f"get_snooze: Error {ex} occurred.")
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
                item(play_mode, self.plugin_shortname)

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
            self.logger.error(f"set_play_mode: Error {ex} occurred.")
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
            item(self._is_coordinator, self.plugin_shortname)

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
                item(current_track, self.plugin_shortname)

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
                item(number_of_tracks, self.plugin_shortname)

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
                item(self.current_track_duration, self.plugin_shortname)

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
                item(self.current_transport_actions, self.plugin_shortname)

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
                item(self.current_valid_play_modes, self.plugin_shortname)

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
                item(self.track_artist, self.plugin_shortname)

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
                item(self.track_title, self.plugin_shortname)

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
                item(self.track_album, self.plugin_shortname)

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
                item(self.track_album_art, self.plugin_shortname)

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
                item(self.radio_station, self.plugin_shortname)

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
                item(self.radio_show, self.plugin_shortname)

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
                item(self.stream_content, self.plugin_shortname)

    def play_tunein(self, station_name: str, start: bool = True) -> None:
        """
        Plays a radio station from TuneIn by a given radio name. If more than one radio station are found,
        the first result will be played.
        :param station_name: radio station name
        :param start: Start playing after setting the radio stream? Default: True
        :return: None
        """

        if not self._check_property():
            return

        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_tunein(station_name, start)
        else:
            result, msg = self._play_radio(station_name=station_name, music_service='TuneIn', start=start)
            if not result:
                self.logger.warning(msg)
                return False
            return True

    def play_sonos_radio(self, station_name: str, start: bool = True) -> None:
        """
        Plays a radio station from Sonos Radio by a given radio name. If more than one radio station are found,
        the first result will be played.
        :param station_name: radio station name
        :param start: Start playing after setting the radio stream? Default: True
        :return: None
        """

        if not self._check_property():
            return

        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_sonos_radio(station_name, start)
        else:
            result, msg = self._play_radio(station_name=station_name, music_service='Sonos Radio', start=start)
            if not result:
                self.logger.warning(msg)
                return False
            return True
    

    def _play_radio(self, station_name: str, music_service: str = 'TuneIn', start: bool = True) -> tuple:
        """
        Plays a radio station by a given radio name at a given music service. If more than one radio station are found,
        the first result will be played.
        :param music_service: music service name Default: TuneIn
        :param station_name: radio station name
        :param start: Start playing after setting the radio stream? Default: True
        :return: None
        """

        meta_template = """
                        <DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/"
                            xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"
                            xmlns:r="urn:schemas-rinconnetworks-com:metadata-1-0/"
                            xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">
                            <item id="R:0/0/0" parentID="R:0/0" restricted="true">
                                <dc:title>{title}</dc:title>
                                <upnp:albumArtURI>{station_logo}</upnp:albumArtURI>
                                <upnp:class>object.item.audioItem.audioBroadcast</upnp:class>
                                <desc id="cdudn" nameSpace="urn:schemas-rinconnetworks-com:metadata-1-0/">
                                    {service}
                                </desc>
                            </item>
                        </DIDL-Lite>' 
                        """

        # get all music services
        all_music_services_names = MusicService.get_all_music_services_names()

        # check if given music service is available
        if music_service not in all_music_services_names:
            return False, f"Requested Music Service '{music_service}' not available"

        # get music service instance
        music_service = MusicService(music_service)

        # adapt station_name for optimal search results
        if " " in station_name:
            station_name_for_search = station_name.split(" ", 1)[0]
        elif station_name[-1].isdigit():
            station_name_for_search = station_name[:-1]
        else:
            station_name_for_search = station_name

        # do search
        search_result = music_service.search(category='stations', term=station_name_for_search, index=0, count=100)

        # get station object from search result
        the_station = None
        # Strict match
        for station in search_result:
            if station_name in station.title:
                self.logger.info(f"Strict match '{station.title}' found")
                the_station = station
                break

        # Fuzzy match
        if not the_station:
            station_name = station_name.lower()
            for station in search_result:
                if station_name in station.title.lower():
                    self.logger.info(f"Fuzzy match '{station.title}' found")
                    the_station = station
                    break

        # Very fuzzy match // handle StationNames ending on digit and add space in front
        if not the_station:
            last_char = len(station_name) - 1
            if station_name[last_char].isdigit():
                station_name = f"{station_name[0:last_char]} {station_name[last_char:]}"
                for station in search_result:
                    if station_name in station.title.lower():
                        self.logger.info(f"Very fuzzy match '{station.title}' found")
                        the_station = station
                        break

        if not the_station:
            return False, f"No match for requested radio station {station_name}. Check spaces in station name"

        uri = music_service.get_media_uri(the_station.id)

        station_logo = the_station.stream_metadata.logo
        if "%" in station_logo:
            station_logo = unquote(station_logo)
        if station_logo.startswith('https://sali.sonos.radio'):
            station_logo = station_logo.split("image=")[1].split("&partnerId")[0]

        metadata = meta_template.format(title=the_station.title, service=the_station.desc, station_logo=station_logo)

        self.logger.info(f"Trying 'play_uri()': URI={uri}, Metadata={metadata}")
        self.soco.play_uri(uri=uri, meta=metadata, title=the_station.title, start=start, force_radio=True)
        return True, ""


    def play_sharelink(self, url: str, start: bool = True) -> None:
        """
        Plays a sharelink from a given url
        :param start: Start playing after setting the url? Default: True
        :param url: url to be played
        :return: None
        """
        if not self._check_property():
            return

        if not self.is_coordinator:
            try:
                device = sonos_speaker[self.coordinator]
                share_link = ShareLinkPlugin(device)

                if not share_link.is_share_link(url):
                    self.logger.warning(f"Url: {url} is not a valid share link")
                    return False

                queue_position = share_link.add_share_link_to_queue(url)
                sonos_speaker[self.coordinator].play_from_queue(index=queue_position)
            except SoCoUPnPException as ex:
                self.logger.warning(f"Exception in play_from_queue() a): {ex}")
                return
        else:
            try:
                device = self.soco
                share_link = ShareLinkPlugin(device)

                if not share_link.is_share_link(url):
                    self.logger.warning(f"Url: {url} is not a valid share link")
                    return False

                queue_position = share_link.add_share_link_to_queue(url)
                self.soco.play_from_queue(index=queue_position)
            except SoCoUPnPException as ex:
                self.logger.warning(f"Exception in play_sharelink() b): {ex}")
                return

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
            self.logger.warning(f"Cannot join ... no speaker found with uid {uid}.")
            return
        speaker_to_join = sonos_speaker[uid]
        self.logger.debug(f'Joining [{uid}] to [uid: {speaker_to_join.uid}, master: {speaker_to_join.coordinator}]')
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
        Gets all Sonos playlist and put result to items.
        """
        try:
            playlists = self.soco.get_sonos_playlists()
        except Exception as e:
            self.logger.info(f"Error during soco.get_sonos_playlists(): {e}")
            return

        self.logger.debug(f"sonos_playlists: {playlists=}")

        sonos_playlist_list = []
        for value in playlists:
            sonos_playlist_list.append(value.title)
        for item in self.sonos_playlists_items:
            item(sonos_playlist_list, self.plugin_shortname)

    def sonos_favorites(self) -> None:
        """
        Gets all Sonos favorites.
        """
        try:
            favorites = self.soco.music_library.get_sonos_favorites(complete_result=True)
        except Exception as e:
            self.logger.info(f"Error during soco.music_library.get_sonos_favorites(): {e}")
            return
        self.logger.debug(f"sonos_favorites: {favorites=}")

        sonos_favorite_list = []
        for favorite in favorites:
            sonos_favorite_list.append(favorite.title)
        for item in self.sonos_favorites_items:
            item(sonos_favorite_list, self.plugin_shortname)

    def favorite_radio_stations(self) -> None:
        """
        Gets all Sonos favorites radio stations items.
        """
        try:
            radio_stations = self.soco.music_library.get_favorite_radio_stations()
        except Exception as e:
            self.logger.info(f"Error during soco.music_library.get_favorite_radio_stations(): {e}")
            return
        self.logger.debug(f"favorite_radio_stations: {radio_stations=}")

        favorite_radio_station_list = []
        for favorite in radio_stations:
            favorite_radio_station_list.append(favorite.title)
        for item in self.favorite_radio_stations_items:
            item(favorite_radio_station_list, self.plugin_shortname)

    def _play_snippet(self, file_path: str, webservice_url: str, volume: int = -1, duration_offset: float = 0, fade_in: bool = False) -> None:
        self.logger.debug(f"_play_snippet with volume {volume}")

        # Already done in method which called this one
        # if not self._check_property():
        #     return

        if not os.path.isfile(file_path):
            self.logger.error(f"Cannot find snipped file {file_path}")
            return

        # Check if stop() is part of currently supported transport actions.
        # For example, stop() is not available when the speaker is in TV mode.
        currentActions = self.current_transport_actions
        self.logger.debug(f"play_snippet: checking transport actions: {currentActions}")

        with self._snippet_queue_lock:
            snap = None
            volumes = {}
            # save all volumes from zone_member
            for member in self.zone_group_members:
                if member != '':
                    volumes[member] = sonos_speaker[member].volume

            tag = TinyTag.get(file_path)
            self.logger.debug(f"tag-duration {tag.duration}, duration_offset {duration_offset}")
            if not tag.duration:
                self.logger.error("TinyTag duration is none.")
            else:
                duration = round(tag.duration) + duration_offset
                self.logger.debug(f"TTS track duration: {duration}s, TTS track duration offset: {duration_offset}s")
                file_name = quote(os.path.split(file_path)[1])
                snippet_url = f"{webservice_url}/{file_name}"

                # was GoogleTTS the last track? do not snapshot
                last_station = self.radio_station.lower()
                if last_station != "snippet":
                    snap = Snapshot(self.soco)
                    snap.snapshot()

                time.sleep(0.5)
                if 'Stop' in currentActions:
                    self.set_stop()
                if volume == -1:
                    self.logger.debug(f"_play_snippet, volume is -1, reset to {self.volume}")
                    volume = self.volume

                self.set_volume(volume, group_command=True)
                self.soco.play_uri(snippet_url, title="snippet")
                time.sleep(duration)
                if 'Stop' in currentActions:
                    self.set_stop()

                # Restore the Sonos device back to its previous state
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

    def play_snippet(self, audio_file, local_webservice_path_snippet: str, webservice_url: str, volume: int = -1, duration_offset: float = 0, fade_in=False) -> None:
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_snippet(audio_file, local_webservice_path_snippet, webservice_url, volume, duration_offset, fade_in)
        else:
            file_path = os.path.join(local_webservice_path_snippet, audio_file)

            if not os.path.exists(file_path):
                self.logger.error(f"Snippet file '{file_path}' does not exists.")
                return
            self._play_snippet(file_path, webservice_url, volume, duration_offset, fade_in)

    def play_tts(self, tts: str, tts_language: str, local_webservice_path: str, webservice_url: str, volume: int = -1, duration_offset: float = 0, fade_in=False) -> None:
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_tts(tts, tts_language, local_webservice_path, webservice_url, volume, duration_offset, fade_in)
        else:
            file_path = utils.get_tts_local_file_path(local_webservice_path, tts, tts_language)

            # only do a tts call if file not exists
            if not os.path.exists(file_path):
                tts = gTTS(tts, lang=tts_language)
                try:
                    tts.save(file_path)
                except Exception as ex:
                    self.logger.error(f"Could not obtain TTS file from Google. Error: {ex}")
                    return
            else:
                self.logger.debug(f"File {file_path} already exists. No TTS request necessary.")
            self._play_snippet(file_path, webservice_url, volume, duration_offset, fade_in)

    def load_sonos_playlist(self, name: str, start: bool = False, clear_queue: bool = False, track: int = 0) -> None:
        """
        Loads a Sonos playlist.
        :param track: The index of the track to start play from. First item in the queue is 0.
        :param name: playlist name
        :param start: Should the speaker start playing after loading the playlist?
        :param clear_queue: 'True' to clear the queue before loading the new playlist, 'False' otherwise.
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
                    self.logger.warning("A valid playlist name must be provided.")
                    return
                playlist = self.soco.get_sonos_playlist_by_attr('title', name)
                if playlist:
                    if clear_queue:
                        self.soco.clear_queue()
                    self.soco.add_to_queue(playlist)
                    try:
                        track = int(track)
                    except TypeError:
                        self.logger.warning("Could not cast track [{track}] to 'int'.")
                        return
                    try:
                        self.soco.play_from_queue(track, start)
                    except SoCoUPnPException as ex:
                        self.logger.warning(f"Exception in play_from_queue(): {ex}")
                        return
                    # bug here? no event, we have to trigger it manually
                    if start:
                        self.play = True
            except Exception:
                self.logger.warning(f"load_sonos_playlist: No Sonos playlist found with title '{name}'.")

    def _play_favorite(self, favorite_title: str = None, favorite_number: int = None) -> tuple:
        """Core of the play_favorite action, but doesn't exit on failure"""

        favorites = self.soco.music_library.get_sonos_favorites(complete_result=True)

        if favorite_number is not None:
            err_msg = f"Favorite number must be integer between 1 and {len(favorites)}"
            try:
                favorite_number = int(favorite_number)
            except ValueError:
                return False, err_msg
            if not 0 < favorite_number <= len(favorites):
                return False, err_msg

            # List must be sorted by title to match the output of 'list_favorites'
            favorites.sort(key=lambda x: x.title)
            the_fav = favorites[favorite_number - 1]
            self.logger.info(f"Favorite number {favorite_number} is '{the_fav.title}'")

        else:
            the_fav = None
            # Strict match
            for f in favorites:
                if favorite_title == f.title:
                    self.logger.info(f"Strict match '{f.title}' found")
                    the_fav = f
                    break

            # Fuzzy match
            if not the_fav:
                favorite_title = favorite_title.lower()
                for f in favorites:
                    if favorite_title in f.title.lower():
                        self.logger.info(f"Fuzzy match '{f.title}' found")
                        the_fav = f
                        break

        if the_fav:
            # play_uri works for some favorites
            try:
                uri = the_fav.get_uri()
                metadata = the_fav.resource_meta_data
                self.logger.info(f"Trying 'play_uri()': URI={uri}, Metadata={metadata}")
                self.soco.play_uri(uri=uri, meta=metadata)
                return True, ""
            except Exception as e:
                e1 = e

            # Other favorites will be added to the queue, then played
            try:
                self.logger.info("Trying 'add_to_queue()'")
                index = self.soco.add_to_queue(the_fav, as_next=True)
                self.soco.play_from_queue(index, start=True)
                return True, ""
            except Exception as e2:
                msg = f"1: {e1} | 2: {e2}"
                return False, msg
        msg = f"Favorite '{favorite_title}' not found"
        return False, msg

    def play_favorite_title(self, favorite_title: str) -> bool:
        """
        Play Sonos favorite by title
        :param favorite_title:
        :return:
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_favorite_title(favorite_title)
        else:
            self.logger.info(f"Playing favorite {favorite_title}")
            result, msg = self._play_favorite(favorite_title=favorite_title)
            if not result:
                self.logger.warning(msg)
                return False
            return True

    def play_favorite_number(self, favorite_number: int) -> bool:
        """
        Play Sonos favorite by list index
        :param favorite_number:
        :return:
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_favorite_number(favorite_number)
        else:
            self.logger.info(f"Playing favorite number {favorite_number}")
            result, msg = self._play_favorite(favorite_number=favorite_number)
            if not result:
                self.logger.warning(msg)
                return False
            return True

    def _play_favorite_radio(self, station_title: str = None, station_number: int = None, preset: int = 0, limit: int = 99) -> tuple:
        """Core of the play_favorite_radio action, but doesn't exit on failure"""

        stations = self.soco.music_library.get_favorite_radio_stations(preset, limit)

        # get station_title by station_number
        if station_number is not None:
            err_msg = f"Favorite station number must be integer between 1 and {len(stations)}"
            try:
                station_number = int(station_number)
            except ValueError:
                return False, err_msg
            if not 0 < station_number <= len(stations):
                return False, err_msg

            # List must be sorted by title to match the output of 'list_favorites'
            station_titles = sorted([s.title for s in stations])
            self.logger.info(f"Sorted station titles are: {station_titles}")

            station_title = station_titles[station_number - 1]
            self.logger.info(f"Requested station is '{station_title}'")

        # get station object
        the_fav = None
        # Strict match
        for f in stations:
            if station_title == f.title:
                self.logger.info(f"Strict match '{f.title}' found")
                the_fav = f
                break

        # Fuzzy match
        station_title = station_title.lower()
        if not the_fav:
            for f in stations:
                if station_title in f.title.lower():
                    self.logger.info(f"Fuzzy match '{f.title}' found")
                    the_fav = f
                    break

        # set to play
        if the_fav:
            uri = the_fav.get_uri()
            meta_template = """
                            <DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/"
                                xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"
                                xmlns:r="urn:schemas-rinconnetworks-com:metadata-1-0/"
                                xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">
                                <item id="R:0/0/0" parentID="R:0/0" restricted="true">
                                    <dc:title>{title}</dc:title>
                                    <upnp:class>object.item.audioItem.audioBroadcast</upnp:class>
                                    <desc id="cdudn" nameSpace="urn:schemas-rinconnetworks-com:metadata-1-0/">
                                        {service}
                                    </desc>
                                </item>
                            </DIDL-Lite>' 
                            """
            tunein_service = "SA_RINCON65031_"
            uri = uri.replace("&", "&amp;")
            metadata = meta_template.format(title=the_fav.title, service=tunein_service)
            self.logger.info(f"Trying 'play_uri()': URI={uri}, Metadata={metadata}")
            self.soco.play_uri(uri=uri, meta=metadata)
            return True, ""

        msg = f"Favorite Radio Station '{station_title}' not found"
        return False, msg

    def play_favorite_radio_number(self, station_number: int) -> bool:
        """
        Play Sonos radio favorite by list index
        :param station_number:
        :return:
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_favorite_radio_number(station_number)
        else:
            self.logger.info(f"Playing favorite station number {station_number}")
            result, msg = self._play_favorite_radio(station_number=station_number)
            if not result:
                self.logger.warning(msg)
                return False
            return True

    def play_favorite_radio_title(self, station_title: str) -> bool:
        """
        Play Sonos favorite radio station by title
        :param station_title:
        :return:
        """
        if not self._check_property():
            return
        if not self.is_coordinator:
            sonos_speaker[self.coordinator].play_favorite_radio_title(station_title)
        else:
            self.logger.info(f"Playing radio favorite {station_title}")
            result, msg = self._play_favorite_radio(station_title=station_title)
            if not result:
                self.logger.warning(msg)
                return False
            return True


class Sonos(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff
    """
    PLUGIN_VERSION = "1.8.2"

    def __init__(self, sh):
        """Initializes the plugin."""

        # call init code of parent class (SmartPlugin)
        super().__init__()

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        try:
            self._tts = self.get_parameter_value("tts")
            self._snippet_duration_offset = float(self.get_parameter_value("snippet_duration_offset"))
            self._discover_cycle = self.get_parameter_value("discover_cycle")
            self.webif_pagelength = self.get_parameter_value('webif_pagelength')
            local_webservice_path = self.get_parameter_value("local_webservice_path")
            local_webservice_path_snippet = self.get_parameter_value("local_webservice_path_snippet")
            webservice_ip = self.get_parameter_value("webservice_ip")
            webservice_port = self.get_parameter_value("webservice_port")
            speaker_ips = self.get_parameter_value("speaker_ips")
        except KeyError as e:
            self.logger.critical(f"Plugin '{self.get_shortname()}': Inconsistent plugin (invalid metadata definition: {e} not defined)")
            self._init_complete = False
            return

        # define further properties
        self.zero_zone = False              # sometimes a discovery scan fails, so try it two times; we need to save the state
        self._sonos_dpt3_step = 2           # default value for dpt3 volume step (step(s) per time period)
        self._sonos_dpt3_time = 1           # default value for dpt3 volume time (time period per step in seconds)
        self.SoCo_nr_speakers = 0           # number of discovered online speaker / zones
        self._uid_lookup_levels = 4         # iterations of return_parent() on lookup for item uid
        self._speaker_ips = []              # list of fixed speaker ips
        self.zones = {}                     # dict to hold zone information via soco objects
        self.item_list = []                 # list of all items, used by / linked to that plugin
        self.alive = False                  # plugin alive property
        self.webservice = None              # webservice thread
        
        # handle fixed speaker ips
        if speaker_ips:
            self.logger.debug("User-defined speaker IPs set. Auto-discover disabled.")
            self._speaker_ips = self._parse_speaker_ips(speaker_ips)

        # init TTS
        if self._tts:
            if self._init_tts(webservice_ip, webservice_port, local_webservice_path, local_webservice_path_snippet):
                self.logger.info(f"TTS successfully enabled")
            else:
                self.logger.info(f"TTS initialisation failed.")
                
        # read SoCo version:
        self.SoCo_version = self.get_soco_version()
        self.logger.info(f"Loading SoCo version {self.SoCo_version}.")

        # configure log level of SoCo modules:
        self._set_soco_logger('WARNING')
        
        # init webinterface
        self.init_webinterface(WebInterface)
        return

    def run(self):
        self.logger.debug("Run method called")
        
        # do initial speaker discovery and set scheduler
        self._discover()
        self.scheduler_add("sonos_discover_scheduler", self._discover, prio=3, cron=None, cycle=self._discover_cycle, value=None, offset=None, next=None)

        # set plugin to alive
        self.alive = True

    def stop(self):
        self.logger.debug("Stop method called")
        
        if self.webservice:
            self.webservice.stop() 
        
        if self.scheduler_get('sonos_discover_scheduler'):
            self.scheduler_remove('sonos_discover_scheduler')
        
        for uid, speaker in sonos_speaker.items():
            speaker.dispose()
        
        event_listener.stop()
        
        self.alive = False

    def parse_item(self, item: Items) -> object:
        """
        Parses an item
        :param item: item to parse
        :return: update function or None
        """
        uid = None

        if self.has_iattr(item.conf, 'sonos_recv') or self.has_iattr(item.conf, 'sonos_send'):
            self.logger.debug(f"parse item: {item.id()}")
            # get uid from parent item
            uid = self._resolve_uid(item)
            if not uid:
                self.logger.error(f"No uid found for {item.id()}.")
                return

        if self.has_iattr(item.conf, 'sonos_recv'):
            # create Speaker instance if not exists
            _initialize_speaker(uid, self.logger, self.get_shortname())

            # to make code smaller, map sonos_cmd value to the Speaker property by name
            item_attribute = self.get_iattr_value(item.conf, 'sonos_recv')
            list_name = f"{item_attribute}_items"
            try:
                attr = getattr(sonos_speaker[uid], list_name)
                self.logger.debug(f"Adding item {item.id()} to {uid}: list {list_name}")
                attr.append(item)
                if item not in self.item_list:
                    self.item_list.append(item)
            except Exception:
                self.logger.warning(f"No item list available for sonos_cmd '{item_attribute}'.")

        if self.has_iattr(item.conf, 'sonos_send'):
            self.logger.debug(f"Item {item.id()} registered to 'sonos_send' commands.")
            if item not in self.item_list:
                self.item_list.append(item)
            return self.update_item

        # some special handling for dpt3 volume
        if self.has_iattr(item.conf, 'sonos_attrib'):
            if self.get_iattr_value(item.conf, 'sonos_attrib') != 'vol_dpt3':
                if item not in self.item_list:
                    self.item_list.append(item)
                return

            # check, if a volume parent item exists
            parent_item = item.return_parent()

            if parent_item is not None:
                if self.has_iattr(parent_item.conf, 'sonos_recv'):
                    if self.get_iattr_value(parent_item.conf, 'sonos_recv').lower() != 'volume':
                        self.logger.warning("volume_dpt3 item has no volume parent item. Ignoring!")
                else:
                    self.logger.warning("volume_dpt3 item has no volume parent item. Ignoring!")
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
                self.logger.warning("volume_dpt3 item has no helper item. Ignoring!")
                return

            item.conf['helper'] = child_helper

            if not self.has_iattr(item.conf, 'sonos_dpt3_step'):
                item.conf['sonos_dpt3_step'] = self._sonos_dpt3_step
                self.logger.debug(f"No sonos_dpt3_step defined, using default value {self._sonos_dpt3_step}.")

            if not self.has_iattr(item.conf, 'sonos_dpt3_time'):
                item.conf['sonos_dpt3_time'] = self._sonos_dpt3_time
                self.logger.debug(f"No sonos_dpt3_time defined, using default value {self._sonos_dpt3_time}.")

            if item not in self.item_list:
                self.item_list.append(item)
            return self._handle_dpt3

    def _handle_dpt3(self, item, caller=None, source=None, dest=None):
        if caller != self.get_shortname():
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

    def _check_webservice_ip(self, webservice_ip: str) -> bool:
        if not webservice_ip == '' and not webservice_ip == '0.0.0.0':
            if self.is_ip(webservice_ip):
                self._webservice_ip = webservice_ip
            else:
                self.logger.error(f"Your webservice_ip parameter is invalid. '{webservice_ip}' is not a valid ip address. Disabling TTS.")
                return False
        else:
            auto_ip = utils.get_local_ip_address()
            if auto_ip == '0.0.0.0':
                self.logger.error("Automatic detection of local IP not successful.")
                return False
            self._webservice_ip = auto_ip
            self.logger.debug(f"Webservice IP is not specified. Using auto IP instead ({self._webservice_ip}).")
        
        return True
        
    def _check_webservice_port(self, webservice_port: int) -> bool:
        if utils.is_valid_port(str(webservice_port)):
            self._webservice_port = int(webservice_port)
            if not utils.is_open_port(self._webservice_port):
                self.logger.error(f"Your chosen webservice port '{self._webservice_port}' is already in use. TTS disabled!")
                return False
        else:
            self.logger.error(f"Your webservice_port parameter is invalid. '{webservice_port}' is not within port range 1024-65535. TTS disabled!")
            return False
            
        return True

    def _check_local_webservice_path(self, local_webservice_path: str) -> bool:
    
        # if path is not given, raise error log and disable TTS
        if local_webservice_path == '':
            self.logger.warning(f"Mandatory path for local webserver for TTS not given in Plugin parameters. TTS disabled!")
            return False
    
        # if path is given, check avilability, create and check access rights
        try:
            os.makedirs(local_webservice_path, exist_ok=True)
        except OSError:
            self.logger.warning(f"Could not create local webserver path '{local_webservice_path}'. Wrong permissions? TTS disabled!")
            return False
        else:
            if os.path.exists(local_webservice_path):
                self.logger.debug(f"Local webservice path set to '{local_webservice_path}'")
            else:
                self.logger.warning(f"Local webservice path '{local_webservice_path}' for TTS not exists. TTS disabled!")
                return False

            if os.access(local_webservice_path, os.W_OK):
                self.logger.debug(f"Write permissions ok for tts on path {local_webservice_path}")
                self._local_webservice_path = local_webservice_path
            else:
                self.logger.warning(f"Local webservice path '{local_webservice_path}' is not writeable for current user. TTS disabled!")
                return False
        
        return True
        
    def _check_local_webservice_path_snippet(self, local_webservice_path_snippet: str) -> bool:
        
        # if path is not given, set local_webservice_path_snippet to _local_webservice_path
        if local_webservice_path_snippet == '':
            self._local_webservice_path_snippet = self._local_webservice_path
            return True
        
        # if path is given, check avilability, create and check access rights
        try:
            os.makedirs(local_webservice_path_snippet, exist_ok=True)
        except OSError:
            self.logger.warning(f"Could not create local webserver path for snippets '{local_webservice_path_snippet}'. Wrong permissions? TTS disabled!")
            return False
        else:
            if os.path.exists(local_webservice_path_snippet):
                self.logger.debug(f"Local webservice path for snippets set to '{local_webservice_path_snippet}'")
            else:
                self.logger.warning(f"Local webservice path for snippets '{local_webservice_path_snippet}' for TTS not exists. TTS disabled!")
                return False

            if os.access(local_webservice_path_snippet, os.W_OK):
                self.logger.debug(f"Write permissions ok for tts on path {local_webservice_path_snippet}")
                self._local_webservice_path_snippet = local_webservice_path_snippet
            else:
                self.logger.warning(f"Local webservice path for snippets '{local_webservice_path_snippet}' is not writeable for current user. TTS disabled!")
                return False
        
        return True
      
    def _get_free_diskspace(self) -> None:
        """
        get free diskspace and put it to logger
        :return:
        """

        free_diskspace = utils.get_free_diskspace(self._local_webservice_path)
        human_readable_diskspace = utils.file_size(free_diskspace)
        self.logger.debug(f"Free diskspace: {human_readable_diskspace}")
        
    def _init_webservice(self) -> None:
        """
        Init the Webservice-Server
        :return:
        """

        self._webservice_url = f"http://{self._webservice_ip}:{self._webservice_port}"
        self.logger.debug(f"Starting webservice for TTS on {self._webservice_url}")
        self.webservice = SimpleHttpServer(self._webservice_ip,
                                           self._webservice_port,
                                           self._local_webservice_path,
                                           self._local_webservice_path_snippet)
        self.logger.debug(f"Webservice init done with: ip={self._webservice_ip}, port={self._webservice_port}, path={self._local_webservice_path}, snippet_path={self._local_webservice_path_snippet}")
        self.webservice.start()
        
    def _init_tts(self, webservice_ip: str, webservice_port: int, local_webservice_path: str, local_webservice_path_snippet: str) -> bool:
        """
        Init the TTS service
        :param webservice_ip:
        :param webservice_port:
        :param local_webservice_path:
        :param local_webservice_path_snippet:
        :return:
        """
        # Check local webservice settings
        if not (self._check_webservice_ip(webservice_ip) and
                self._check_webservice_port(webservice_port) and
                self._check_local_webservice_path(local_webservice_path) and
                self._check_local_webservice_path_snippet(local_webservice_path_snippet)):
            self.logger.warning(f"Local webservice settings not correct. TTS disabled.")
            return False
            
        # Check diskspace
        self._get_free_diskspace()
        
        # Init webservice
        self._init_webservice()
        
        return True

    def _parse_speaker_ips(self, speaker_ips: list) -> list:
        """
        check user specified sonos speaker ips
        """
        
        for ip in speaker_ips:
            if self.is_ip(ip):
                self._speaker_ips.append(ip)
            else:
                self.logger.warning(f"Invalid Sonos speaker ip '{ip}'. Ignoring.")
        # return unique items in list
        return utils.unique_list(self._speaker_ips)


    def debug_speaker(self, uid):
        self.logger.warning(f"debug_speaker: Starting function for uid {uid}")
        #sonos_speaker[uid].set_stop()
        self.logger.warning(f"debug_speaker: check sonos_speaker[uid].av.subscription: {sonos_speaker[uid].av_subscription}")
        # Event objekt is not callable:
        #sonos_speaker[uid]._av_transport_event(sonos_speaker[uid].av_subscription) 
        self.logger.warning(f"debug_speaker: av_subscription: thread active {sonos_speaker[uid].av_subscription.subscriptionThreadIsActive}, eventSignal: {sonos_speaker[uid].av_subscription.eventSignalIsSet}")


    def get_soco_version(self) -> str:
        """
        Get version of used Soco and return it
        """
        
        try:
            src = io.open('plugins/sonos/soco/__init__.py', encoding='utf-8').read()
            metadata = dict(re.findall("__([a-z]+)__ = \"([^\"]+)\"", src))
        except Exception as e:
            self.logger.warning(f"Version of used Soco module not available. Exception: {e}")
            self.logger.warning(f"DEBUG get socoversion: Current dir: {os.getcwd()}")
            return ''
        else:
            soco_version = metadata['version']
            return soco_version

    def _set_soco_logger(self, level: str = 'WARNING') -> None:
        """
        set all soco loggers to given level
        """
        
        level = level.upper()
        log_level = logging.getLevelName(level)
        
        logging.getLogger('plugins.sonos.soco.events_base').setLevel(log_level)
        logging.getLogger('plugins.sonos.soco.events').setLevel(log_level)
        logging.getLogger('plugins.sonos.soco.discovery').setLevel(log_level)
        logging.getLogger('plugins.sonos.soco.services').setLevel(log_level)
        
        self.logger.info(f"Set all SoCo loglevel to {level}")

    def parse_logic(self, logic):
        pass

    def update_item(self, item: Items, caller: object, source: object, dest: object) -> None:
        """
        Write items values
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        
        if self.alive and caller != self.get_fullname():
            if self.has_iattr(item.conf, 'sonos_send'):
                uid = self._resolve_uid(item)
                command = self.get_iattr_value(item.conf, "sonos_send").lower()

                if command == "play":
                    sonos_speaker[uid].set_play() if item() else sonos_speaker[uid].set_pause()
                elif command == "stop":
                    sonos_speaker[uid].set_stop() if item() else sonos_speaker[uid].set_play()
                elif command == "pause":
                    sonos_speaker[uid].set_pause() if item() else sonos_speaker[uid].set_play()
                elif command == "mute":
                    sonos_speaker[uid].set_mute(item())
                elif command == "status_light":
                    sonos_speaker[uid].set_status_light(item())
                elif command == "volume":
                    group_command = self._resolve_group_command(item)
                    max_volume = self._resolve_max_volume_command(item)
                    sonos_speaker[uid].set_volume(item(), group_command, max_volume)
                elif command == "bass":
                    group_command = self._resolve_group_command(item)
                    sonos_speaker[uid].set_bass(item(), group_command)
                elif command == "treble":
                    group_command = self._resolve_group_command(item)
                    sonos_speaker[uid].set_treble(item(), group_command)
                elif command == "loudness":
                    group_command = self._resolve_group_command(item)
                    sonos_speaker[uid].set_loudness(item(), group_command)
                elif command == "night_mode":
                    sonos_speaker[uid].set_night_mode(item())
                elif command == "buttons_enabled":
                    sonos_speaker[uid].set_buttons_enabled(item())
                elif command == "dialog_mode":
                    sonos_speaker[uid].set_dialog_mode(item())
                elif command == "cross_fade":
                    sonos_speaker[uid].set_cross_fade(item())
                elif command == "snooze":
                    sonos_speaker[uid].set_snooze(item())
                elif command == "play_mode":
                    sonos_speaker[uid].set_play_mode(item())
                elif command == "next":
                    sonos_speaker[uid].set_next(item())
                elif command == "previous":
                    sonos_speaker[uid].set_previous(item())
                elif command == "switch_linein":
                    sonos_speaker[uid].switch_to_line_in() if item() else None
                elif command == "switch_tv":
                    sonos_speaker[uid].switch_to_tv() if item() else None
                elif command == "play_tunein":
                    start = self._resolve_child_command_bool(item, 'start_after')
                    sonos_speaker[uid].play_tunein(item(), start)
                elif command == "play_url":
                    start = self._resolve_child_command_bool(item, 'start_after')
                    sonos_speaker[uid].play_url(item(), start)
                elif command == "play_sharelink":
                    start = self._resolve_child_command_bool(item, 'start_after')
                    sonos_speaker[uid].play_sharelink(item(), start)
                elif command == "join":
                    sonos_speaker[uid].join(item())
                elif command == "unjoin":
                    start = self._resolve_child_command_bool(item, 'start_after')
                    sonos_speaker[uid].unjoin(item(), start)
                elif command == 'load_sonos_playlist':
                    start = self._resolve_child_command_bool(item, 'start_after')
                    clear_queue = self._resolve_child_command_bool(item, 'clear_queue')
                    track = self._resolve_child_command_int(item, 'start_track')
                    sonos_speaker[uid].load_sonos_playlist(item(), start, clear_queue, track)

                elif command == 'play_tts':
                    if item() == "":
                        self.logger.error("No item value when executing 'play_tts' command")
                        return
                    language = self._resolve_child_command_str(item, 'tts_language', 'de')
                    volume = self._resolve_child_command_int(item, 'tts_volume', -1)
                    fade_in = self._resolve_child_command_bool(item, 'tts_fade_in')
                    sonos_speaker[uid].play_tts(item(), language, self._local_webservice_path, self._webservice_url, volume, self._snippet_duration_offset, fade_in)

                elif command == 'play_snippet':
                    if item() == "":
                        self.logger.error("No item value when executing 'play_snippet' command")
                        return
                    volume = self._resolve_child_command_int(item, 'snippet_volume', -1)
                    self.logger.debug(f"play_snippet on uid {uid} with volume {volume}")
                    fade_in = self._resolve_child_command_bool(item, 'snippet_fade_in')
                    sonos_speaker[uid].play_snippet(item(), self._local_webservice_path_snippet, self._webservice_url, volume, self._snippet_duration_offset, fade_in)

                elif command == 'play_favorite_title':
                    if item() == "":
                        self.logger.error("No item value when executing 'play_favorite_title' command")
                        return
                    sonos_speaker[uid].play_favorite_title(item())

                elif command == 'play_favorite_number':
                    if item() == "":
                        self.logger.error("No item value when executing 'play_favorite_number' command")
                        return
                    sonos_speaker[uid].play_favorite_number(item())

                elif command == 'play_favorite_radio_number':
                    if item() == "":
                        self.logger.error("No item value when executing 'play_favorite_radio_number' command")
                        return
                    sonos_speaker[uid].play_favorite_radio_number(item())

                elif command == 'play_favorite_radio_title':
                    if item() == "":
                        self.logger.error("No item value when executing 'play_favorite_radio_title' command")
                        return
                    sonos_speaker[uid].play_favorite_radio_title(item())

                elif command == "play_sonos_radio":
                    start = self._resolve_child_command_bool(item, 'start_after')
                    sonos_speaker[uid].play_sonos_radio(item(), start)

    def _resolve_child_command_str(self, item: Items, child_command: str, default_value: str = "") -> str:
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

    def _resolve_child_command_bool(self, item: Items, child_command: str) -> bool:
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

    def _resolve_child_command_int(self, item: Items, child_command: str, default_value: int = 0) -> int:
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
        except Exception:
            self.logger.warning(f"Could not cast value [{child()}] to 'int', using default value '0'")
            return default_value

    def _resolve_group_command(self, item: Items) -> bool:
        """
        Resolves a group_command child for an item
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

    def _resolve_max_volume_command(self, item: Items) -> int:
        """
        Resolves a max_volume_command child for an item
        :param item:
        :return:
        """

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
                        self.logger.error(f":_resolve_max_volume_command: Error {ex} occurred.")
                        return -1
        return -1

    def _resolve_uid(self, item: Items) -> str:
        """
        Get UID of device from item.conf
        """

        uid = ''

        lookup_item = item
        for i in range(self._uid_lookup_levels):
            uid = self.get_iattr_value(lookup_item.conf, 'sonos_uid')
            if uid is not None:
                uid = uid.lower()
                break
            else:
                lookup_item = lookup_item.return_parent()
                if lookup_item is None:
                    break

        if uid == '':
            self.logger.warning(f"Could not resolve sonos_uid for item {item.id()}")

        return uid

    def _discover(self, force: bool = False) -> None:
        """
        Discover Sonos speaker in the network. If the plugin parameter 'speaker_ips' has IP addresses, no discover package is sent over the network.
        :rtype: None
        """

        self.logger.debug("Start discover function")

        online_speaker_count = 0
        handled_speaker = {}
        zones = []
        
        # Create Soco objects if IPs are given, otherwise discover speakers and create Soco objects
        if self._speaker_ips and not force:
            for ip in self._speaker_ips:
                zones.append(SoCo(ip))
        else:
            try:
                zones = soco.discover(timeout=5)
            except Exception as e:
                self.logger.error(f"Exception during soco discover function: {e}")
                return

        self.zones = zones

        if zones is None: 
            self.logger.debug("Discovery could not be executed.")
            return 

        # 1. attempt: don't touch our speaker, return and wait for next interval
        # 2. attempt: ok, no speaker found, go on
        if not zones:
            if not self.zero_zone:
                self.logger.debug("No speaker found (1. attempt), ignoring speaker handling.")
                self.zero_zone = True
                return
            self.logger.debug("No speaker found.")
        self.zero_zone = False

        for zone in zones:
            # Trying to extract Speaker ID (UID). Skip speaker otherwise:
            try:
                uid = zone.uid
            except requests.ConnectionError as e:
                self.logger.info(f"Exception requests connection error in zone.uid for speaker {zone.ip_address}: {e}")
                uid = None
            except requests.Timeout as e:
                self.logger.warning(f"Exception requests timeout in zone.uid for speaker {zone.ip_address}: {e}")
                uid = None
            except Exception as e:
                self.logger.warning(f"Exception in zone.uid for speaker {zone.ip_address}: {e}")
                uid = None
                continue

            if uid is None:
                self.logger.debug(f"Zone has no valid uid. Cannot handle speaker {zone.ip_address}")
                continue

            uid = uid.lower()

            if self._is_speaker_up(uid, zone.ip_address):
                self.logger.dbglow(f"Speaker found: {zone.ip_address}, {uid}")
                online_speaker_count = online_speaker_count + 1 
                if uid in sonos_speaker:
                    try:
                        zone_compare = sonos_speaker[uid].soco
                    except Exception as e:
                        self.logger.warning(f"Exception in discover -> sonos_speaker[uid].soco: {e}")
                    else:
                        if zone is not zone_compare:
                            self.logger.dbghigh(f"zone is not in speaker list, yet. Adding and subscribing zone {zone}.")
                            sonos_speaker[uid].soco = zone
                            sonos_speaker[uid].subscribe_base_events()
                        else:
                            self.logger.dbglow(f"SoCo instance {zone} already initiated, skipping.")
                            # The following check subscriptions functions triggers an unsubscribe/subscribe. However, this causes
                            # a massive memory leak increasing with every check_subscription call.
                            # self.logger.debug("checking subscriptions")
                            # sonos_speaker[uid].check_subscriptions()
                else:
                    self.logger.warning(f"Initializing new speaker with uid={uid} and ip={zone.ip_address}")
                    _initialize_speaker(uid, self.logger, self.get_shortname())
                    sonos_speaker[uid].soco = zone

                sonos_speaker[uid].is_initialized = True
                sonos_speaker[uid].refresh_static_properties()

            else:
                # Speaker is not online. Disposing...
                if sonos_speaker[uid].soco is not None:
                    self.logger.dbghigh(f"Disposing offline speaker: {zone.ip_address}, {uid}")
                    sonos_speaker[uid].dispose()
                else:
                    self.logger.info(f"Ignoring offline speaker: {zone.ip_address}, {uid}")

                sonos_speaker[uid].is_initialized = False

            if uid in sonos_speaker:
                self.logger.dbglow(f"setting {zone.ip_address}, uid {uid} to handled speaker")
                handled_speaker[uid] = sonos_speaker[uid]
            else:
                self.logger.debug(f"ip {zone.ip_address}, uid {uid} is not in sonos_speaker")

        # dispose every speaker that was not found
        for uid in set(sonos_speaker.keys()) - set(handled_speaker.keys()):
            if sonos_speaker[uid].soco is not None:
                self.logger.warning(f"Removing/disposing undiscovered speaker: {sonos_speaker[uid].ip_address}, {uid}")
                sonos_speaker[uid].dispose()

        # Extract number of online speakers:
        self.SoCo_nr_speakers = online_speaker_count 

    def _is_speaker_up(self, uid: str, ip_address: str) -> bool:
        """
        Check if speaker is available via Ping
        Note: don't trust the discover function, offline speakers can be cached, we try to ping the speaker
        
        :param uid:
        :param ip_address:
        :return:
        """

        self.logger.debug(f"Pinging speaker {uid} with ip {ip_address}")
        try:
            proc_result = subprocess.run(['ping', '-i', '0.2', '-c', '2', ip_address],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
            return True
        except subprocess.CalledProcessError:
            self.logger.debug(f"Ping {ip_address} process finished with return code {proc_result.returncode}")
            return False
        except subprocess.TimeoutExpired:
            self.logger.debug(f"Ping {ip_address} process timed out")
            return False     

    def _get_zone_name_from_uid(self, uid: str) -> str:
        """
        Return zone/speaker name per uid
        """

        for zone in self.zones:
            if zone._uid.lower() == uid.lower():
                return zone._player_name

    @property
    def sonos_speaker(self):
        """
        Returns sonos_speaker dict
        """
        return sonos_speaker

    @property
    def log_level(self):
        """
        Returns current logging level
        """
        return self.logger.getEffectiveLevel()


def _initialize_speaker(uid: str, logger: logging, plugin_shortname: str) -> None:
    """
    Create a Speaker object by a given uuid
    :param uid: uid of the speaker
    :param logger: logger instance
    """
    # The method _initialize_speaker is called for every unknown sonos speaker identified by the discovery function
    # Moreover, it is called for every sonos attribute having the sonos_recv attribute to initialize those speakers even
    # if they have not been discovered yet by the sonos discovery function.
    with _create_speaker_lock:
        if uid not in sonos_speaker:
            sonos_speaker[uid] = Speaker(uid=uid, logger=logger, plugin_shortname=plugin_shortname)
