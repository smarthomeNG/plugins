#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2013 Marcus Popp                               marcus@popp.mx
#           2017 Nino Coric                        mail2n.coric@gmail.com
#           2020,2022 Bernd Meiners                 Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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

import logging
import threading
import re
import datetime

from lib.model.smartplugin import SmartPlugin
from lib.item import Items
from lib.network import Tcp_client

from .webif import WebInterface

class MPD(SmartPlugin):

    PLUGIN_VERSION = "1.6.1"
    STATUS        = 'mpd_status'
    SONGINFO      = 'mpd_songinfo'
    STATISTIC     = 'mpd_statistic'
    COMMAND       = 'mpd_command'
    URL           = 'mpd_url'
    LOCALPLAYLIST = 'mpd_localplaylist'
    RAWCOMMAND    = 'mpd_rawcommand'
    DATABASE      = 'mpd_database'
    # use e.g. as MPD.STATUS to keep in namespace

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If the sh object is needed at all, the method self.get_sh() should be used to get it.
        There should be almost no need for a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.logger.debug(f"init {__name__}")
        self._init_complete = False

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.instance = self.get_instance_name()

        self.host = self.get_parameter_value('host')
        self.port = self.get_parameter_value('port')
        self._cycle = self.get_parameter_value('cycle')

        name = 'plugins.' + self.get_fullname()
        self._client = Tcp_client(name=name, host=self.host, port=self.port, binary=False, autoreconnect=True, connect_cycle=5, retry_cycle=30, timeout=20)
        self._client.set_callbacks(connected=self.handle_connect, data_received=self.parse_reply)
        self._cmd_lock = threading.Lock()
        self._reply_lock = threading.Condition()
        self._reply = {}

        self._status_items = {}
        self._currentsong_items = {}
        self._statistic_items = {}
        self.orphanItems = []
        self.lastWarnTime = None
        self.warnInterval = 3600  # warn once per hour for orphaned items if some exist
        self._internal_Items = {'isPlaying': False, 'isPaused': False, 'isStopped': False, 'isMuted': False, 'lastVolume': 20, 'currentName': ''}
        self._mpd_statusRequests = ['volume', 'repeat', 'random', 'single', 'consume', 'playlist', 'playlistlength',
                                    'mixrampdb', 'state', 'song', 'songid', 'time', 'elapsed', 'bitrate', 'audio', 'nextsong',
                                    'nextsongid', 'duration', 'xfade', 'mixrampdelay', 'updating_db', 'error', 'playpause', 'mute']
        self._mpd_currentsongRequests = ['file', 'Last-Modified', 'Artist', 'Album', 'Title', 'Name', 'Track', 'Time', 'Pos', 'Id']
        self._mpd_statisticRequests = ['artists', 'albums', 'songs', 'uptime', 'db_playtime', 'db_update', 'playtime']
        # _mpd_playbackCommands and _mpd_playbackOptions are both handled as 'mpd_command'!
        self._mpd_playbackCommands = ['next', 'pause', 'play', 'playid', 'previous', 'seek', 'seekid', 'seekcur', 'stop', 'playpause', 'mute']
        self._mpd_playbackOptions = ['consume', 'crossfade', 'mixrampdb', 'mixrampdelay', 'random', 'repeat', 'setvol', 'single', 'replay_gain_mode']
        self._mpd_rawCommand = ['rawcommand']
        self._mpd_databaseCommands = ['update', 'rescan']

        self.init_webinterface(WebInterface)

        self.logger.debug("init done")
        self._init_complete = True

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        if self._client.connect():
            self.logger.debug(f'successfully connected to {self.host}:{self.port} within run method')
        else:
            self.logger.error(f'Connection to {self.host}:{self.port} not possible. Plugin deactivated.')
            return

        self.alive = True
        self.scheduler_add('update_status', self.update_status, cycle=self._cycle)

        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        self.alive = False
        # added to effect better cleanup on stop
        if self.scheduler_get('update_status'):
            self.scheduler_remove('update_status')
        try:
            self._client.close()
        except:
            pass

    def handle_connect(self, client):
        self.logger.debug("handle_connect")
        ### self.found_terminator = self.parse_reply

    def parse_reply(self, client, data):
        """
        called when data is received from mpd

        :param data: contains raw data
        :type data: string
        """
        # According to https://mpd.readthedocs.io/en/latest/protocol.html all data is encoded in UTF-8
        # but it could be that there is binary data included, prepended by "binary: <size>\n"
        data = data.decode()
        self.logger.debug(f"parse_reply => {data}")
        if data.startswith('OK'):
            self._reply_lock.acquire()
            self._reply_lock.notify()
            self._reply_lock.release()
        elif data.startswith('ACK'):
            self.logger.error(data)
        else:
            lines = data.splitlines()
            for line in lines:
                key, sep, value = line.partition(': ')
                self._reply[key] = value

    def parse_item(self, item):
        """
        Called upon plugin initialization
        :param item: The item to process.
        """

        # all status-related items here
        if self.get_iattr_value(item.conf, MPD.STATUS) in self._mpd_statusRequests:
            key = (self.get_iattr_value(item.conf, MPD.STATUS))
            self._status_items[key] = item
        if self.get_iattr_value(item.conf, MPD.SONGINFO) in self._mpd_currentsongRequests:
            key = (self.get_iattr_value(item.conf, MPD.SONGINFO))
            self._currentsong_items[key] = item
        if self.get_iattr_value(item.conf, MPD.STATISTIC) in self._mpd_statisticRequests:
            key = (self.get_iattr_value(item.conf, MPD.STATISTIC))
            self._statistic_items[key] = item

        # do not return after status-related items => they can be combined with command-related items
        # all command-related items here
        if self.get_iattr_value(item.conf, MPD.COMMAND) in self._mpd_playbackCommands \
                or self.get_iattr_value(item.conf, MPD.COMMAND) in self._mpd_playbackOptions \
                or self.get_iattr_value(item.conf, MPD.URL) is not None \
                or self.get_iattr_value(item.conf, MPD.LOCALPLAYLIST) is not None \
                or self.get_iattr_value(item.conf, MPD.RAWCOMMAND) in self._mpd_rawCommand \
                or self.get_iattr_value(item.conf, MPD.DATABASE) in self._mpd_databaseCommands:

            self.logger.debug(f"callback assigned for item {item}")
            return self.update_item

    def update_status(self):
        # refresh all subscribed items
        warn = self.canWarnNow()
        self.update_statusitems(warn)
        self.update_currentsong(warn)
        self.update_statistic(warn)
        if warn:
            self.lastWarnTime = datetime.datetime.now()
            for warn in self.orphanItems:
                self.logger.warning(warn)
            self.orphanItems = []

    def update_statusitems(self, warn):
        if not self._client.connected():
            if warn:
                self.logger.error("update_status while not connected")
            return
        if (len(self._status_items) <= 0):
            if warn:
                self.logger.warning("status: no items to refresh")
            return
        self.logger.debug("requesting status")
        status = self._send('status')
        self.refreshItems(self._status_items, status, warn)

    def update_currentsong(self, warn):
        if not self._client.connected():
            if warn:
                self.logger.error("update_currentsong while not connected")
            return
        if (len(self._currentsong_items) <= 0):
            if warn:
                self.logger.warning("currentsong: no items to refresh")
            return
        self.logger.debug("requesting currentsong")
        currentsong = self._send('currentsong')
        self.refreshItems(self._currentsong_items, currentsong, warn)

    def update_statistic(self, warn):
        if not self._client.connected():
            if warn:
                self.logger.error("update_statistic while not connected")
            return
        if (len(self._statistic_items) <= 0):
            if warn:
                self.logger.warning("statistic: no items to refresh")
            return
        self.logger.debug("requesting statistic")
        stats = self._send('stats')
        self.refreshItems(self._statistic_items, stats, warn)

    def refreshItems(self, subscribedItems, response, warn):
        if not self.alive:
            return
        # 1. check response for the internal items and refresh them
        if 'state' in response:
            val = response['state']
            if val == 'play':
                self._internal_Items['isPlaying'] = True
                self._internal_Items['isPaused'] = False
                self._internal_Items['isStopped'] = False
            elif val == 'pause':
                self._internal_Items['isPlaying'] = False
                self._internal_Items['isPaused'] = True
                self._internal_Items['isStopped'] = False
            elif val == 'stop':
                self._internal_Items['isPlaying'] = False
                self._internal_Items['isPaused'] = False
                self._internal_Items['isStopped'] = True
            else:
                self.logger.error(f"unknown state: {val}")
        if 'volume' in response:
            val = float(response['volume'])
            if val <= 0:
                self._internal_Items['isMuted'] = True
            else:
                self._internal_Items['isMuted'] = False
                self._internal_Items['lastVolume'] = val
        if 'Name' in response:
            val = response['Name']
            if val:
                self._internal_Items['currentName'] = val

        # 2. check response for subscribed items and refresh them
        for key in subscribedItems:
            # update subscribed items (if value has changed) which exist directly in the response from MPD
            if key in response:
                val = response[key]
                item = subscribedItems[key]
                if item.type() == 'num':
                    try:
                        val = float(val)
                    except:
                        self.logger.error(f"can't parse {val} to float")
                        continue
                elif item.type() == 'bool':
                    if val == '0':
                        val = False
                    elif val == '1':
                        val = True
                    else:
                        self.logger.error("can't parse {val} to bool")
                        continue
                if item() != val:
                    self.logger.debug(f"update item {item}, old value: {item()} type:{item.type()}, new value: {val} type: {type(val)}")
                    self.setItemValue(item, val)
            # update subscribed items which do not exist in the response from MPD
            elif key == 'playpause':
                item = subscribedItems[key]
                val = self._internal_Items['isPlaying']
                if item() != val:
                    self.setItemValue(item, val)
            elif key == 'mute':
                item = subscribedItems[key]
                val = self._internal_Items['isMuted']
                if item() != val:
                    self.setItemValue(item, val)
            elif key == 'Artist':
                item = subscribedItems[key]
                val = self._internal_Items['currentName']
                if item() != val:
                    self.setItemValue(item, val)
            # do not reset these items when the tags are missing in the response from MPD
            # that happens while MPD switches the current track!
            elif key in ('volume', 'repeat', 'random'):
                return
            else:
                if warn:
                    self.orphanItems.append(f'subscribed item "{key}" not in response from MPD => consider unsubscribing this item')
                # reset orphaned items because MPD does not send some items when they are disabled e.g. mixrampdb, error,...
                # to keep these items consistent in SHNG set them to "" or 0.
                # Whenever MPD resends values the items will be refreshed in SHNG
                item = subscribedItems[key]
                self.setItemValue(item, None)

    def setItemValue(self, item, value):
        """
        Sets an Items value according to its type

        :param item: Item 
        :param value: a new value to set, will be automatically casted for an appropriate type
        """
        if item.type() == 'str':
            if value is None or not value:
                value = ''
            item(str(value), self.get_shortname())
        elif item.type() == 'num':
            if value is None:
                value = 0
            item(float(value), self.get_shortname())
        else:
            item(value, self.get_shortname())

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Called when an Item changes within SmartHomeNG

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if not self.alive:
            return False

        if self.alive and caller != self.get_shortname():
            self.logger.debug(f"update_item called for item {item}")

            # only investigate on a command
            if self.has_iattr( item.conf, MPD.COMMAND):
                # playbackCommands
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'next':
                    self._send('next')
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'play':
                    self._send("play {}".format(item()))
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'pause':
                    self._send("pause {}".format(item()))
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'stop':
                    self._send('stop')
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'playpause':
                    if self._internal_Items['isPlaying']:
                        self._send("pause 1")
                    elif self._internal_Items['isPaused']:
                        self._send("pause 0")
                    elif self._internal_Items['isStopped']:
                        self._send("play")
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'playid':
                    self._send("playid {}".format(item()))
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'previous':
                    self._send("previous")
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'seek':
                    val = item()
                    if val:
                        pattern = re.compile('^\d+[ ]\d+$')
                        if pattern.match(val):
                            self._send("seek {}".format(val))
                            return
                    self.logger.warning("ignoring invalid seek value")
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'seekid':
                    val = item()
                    if val:
                        pattern = re.compile('^\d+[ ]\d+$')
                        if pattern.match(val):
                            self._send("seekid {}".format(val))
                            return
                    self.logger.warning("ignoring invalid seekid value")
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'seekcur':
                    val = item()
                    if val:
                        pattern = re.compile('^[+-]?\d+$')
                        if pattern.match(val):
                            self._send("seekcur {}".format(val))
                            return
                    self.logger.warning("ignoring invalid seekcur value")
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'mute':  # own-defined item
                    if self._internal_Items['lastVolume'] < 0:   # can be -1 if MPD can't detect the current volume
                        self._internal_Items['lastVolume'] = 20
                    self._send("setvol {}".format(int(self._internal_Items['lastVolume']) if self._internal_Items['isMuted'] else 0))
                    return
                # playbackoptions
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'consume':
                    self._send("consume {}".format(1 if item() else 0))
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'crossfade':
                    self._send("crossfade {}".format(item()))
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'mixrampdb':
                    self._send("mixrampdb {}".format(item()))
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'mixrampdelay':
                    self._send("mixrampdelay {}".format(item()))
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'random':
                    self._send("random {}".format(1 if item() else 0))
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'repeat':
                    self._send("repeat {}".format(1 if item() else 0))
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'setvol':
                    val = item()
                    if val > 100:
                        self.logger.warning("invalid volume => value > 100 => set 100")
                        val = 100
                    elif val < 0:
                        self.logger.warning("invalid volume => value < 0 => set 0")
                        val = 0
                    self._send("setvol {}".format(val))
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'single':
                    self._send("single {}".format(1 if item() else 0))
                    return
                if self.get_iattr_value(item.conf, MPD.COMMAND) == 'replay_gain_mode':
                    val = item()
                    if val in ['off', 'track', 'album', 'auto']:
                        self._send("replay_gain_mode {}".format(1 if item() else 0))
                    else:
                        self.logger.warning(f"ignoring invalid value ({val}) for replay_gain_mode")
                        pass
                    return
            # url
            if self.has_iattr(item.conf, MPD.URL):
                self.play_url(item)
                return

            # localplaylist
            if self.has_iattr(item.conf, MPD.LOCALPLAYLIST):
                self.play_localplaylist(item)
                return

            # rawcommand
            if self.get_iattr_value(item.conf, MPD.RAWCOMMAND) == 'rawcommand':
                self._send(item())
                return
            # database

            if self.get_iattr_value(item.conf, MPD.DATABASE) == 'update':
                command = 'update'
                if item():
                    command = "{} {}".format(command, item())
                self._send(command)
                return

            if self.get_iattr_value(item.conf, MPD.DATABASE) == 'rescan':
                command = 'rescan'
                if item():
                    command = "{} {}".format(command, item())
                self._send(command)
                return

    def canWarnNow(self):
        if self.lastWarnTime is None:
            return True
        if self.lastWarnTime + datetime.timedelta(seconds=self.warnInterval) \
                <= datetime.datetime.now():
            return True
        return False

    def _parse_url(self, url):
        name, sep, ext = url.rpartition('.')
        ext = ext.lower()
        play = []
        if ext in ('m3u', 'pls'):
            content = self.get_sh().tools.fetch_url(url, timeout=4)
            if content is False:
                return play
            content = content.decode()
            if ext == 'pls':
                for line in content.splitlines():
                    if line.startswith('File'):
                        num, tmp, url = line.partition('=')
                        play.append(url)
            else:
                for line in content.splitlines():
                    if line.startswith('http://'):
                        play.append(line)
        else:
            play.append(url)
        return play

    def play_url(self, item):
        url = self.get_iattr_value(item.conf, MPD.URL)
        play = self._parse_url(url)
        if play == []:
            self.logger.warning("no url to add")
            return
        self._send('clear', False)
        for url in play:
            self._send("add {}".format(url), False)
        self._send('play', False)

    def play_localplaylist(self, item):
        file = self.get_iattr_value(item.conf, MPD.LOCALPLAYLIST)
        if file:
            self._send('clear', False)
            self._send('load {}'.format(file), False)
            self._send('play', False)
        else:
            self.logger.warning("no playlistname to send")

    def _send(self, command, wait=True):
        if not self.alive:
            self.logger.error('Trying to send data but plugin is not running')
            return None

        with self._cmd_lock:
            self._reply = {}
            with self._reply_lock:
                self.logger.debug(f"send {command} to MPD")
                self._client.send((command + '\n').encode())
                if wait:
                    self.logger.debug(f"waiting for reply")
                    self._reply_lock.wait(1)
                    self.logger.debug(f"waiting for reply done")
            reply = self._reply
            self._reply = {}

        return reply
