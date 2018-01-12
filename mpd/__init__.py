#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2013 Marcus Popp                               marcus@popp.mx
#           2017 Nino Coric                        mail2n.coric@gmail.com
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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
import time
import datetime
import lib.connection
from lib.model.smartplugin import SmartPlugin

ITEM_TAG = ['mpd_status','mpd_songinfo','mpd_statistic','mpd_command', 'mpd_url', 
            'mpd_localplaylist', 'mpd_rawcommand', 'mpd_database']
class MPD(lib.connection.Client,SmartPlugin):

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.4.1"

    def __init__(self, sh, host, port=6600, cycle=2):
        self._sh = sh
        self.logger = logging.getLogger(__name__)
        self.instance = self.get_instance_name()
        self.host = host
        self.port = port
        self._cycle = int(cycle)

        lib.connection.Client.__init__(self, self.host, self.port, monitor=True)
        self.terminator = b'\n'
        self._cmd_lock = threading.Lock()
        self._reply_lock = threading.Condition()
        self._reply = {}

        self._status_items = {}
        self._currentsong_items = {}
        self._statistic_items = {}
        self.orphanItems = []
        self.lastWarnTime = None
        self.warnInterval = 3600 #warn once per hour for orphaned items if some exist
        self._internal_tems = { 'isPlaying' : False, 'isPaused' : False, 'isStopped' : False, 'isMuted' : False, 'lastVolume' : 20, 'currentName' : ''}
        self._mpd_statusRequests = ['volume','repeat','random','single','consume','playlist','playlistlength'
                                    ,'mixrampdb','state','song','songid','time','elapsed','bitrate','audio','nextsong'
                                    ,'nextsongid','duration','xfade','mixrampdelay','updating_db','error','playpause','mute']
        self._mpd_currentsongRequests = ['file','Last-Modified','Artist','Album','Title','Name','Track','Time','Pos','Id']
        self._mpd_statisticRequests = ['artists','albums','songs','uptime','db_playtime','db_update','playtime']
        #_mpd_playbackCommands and _mpd_playbackOptions are both handled as 'mpd_command'!
        self._mpd_playbackCommands = ['next','pause','play','playid','previous','seek','seekid','seekcur','stop','playpause','mute']
        self._mpd_playbackOptions = ['consume','crossfade','mixrampdb','mixrampdelay','random','repeat','setvol','single','replay_gain_mode']
        self._mpd_rawCommand = ['rawcommand']
        self._mpd_databaseCommands = ['update','rescan']

    def loggercmd(self, logstr, level):
        if not logstr:
            return
        else:
            logstr = 'MPD_' + self.instance + ': ' + logstr
        if level == 'i' or level == 'info':
            self.logger.info(logstr)
        elif level == 'w' or level == 'warning':
            self.logger.warning(logstr)
        elif level == 'd' or level == 'debug':
            self.logger.debug(logstr)
        elif level == 'e' or level == 'error':
            self.logger.error(logstr)
        else:
            self.logger.critical(logstr)

    def run(self):
        self.alive = True
        self._sh.scheduler.add('MPD', self.update_status, cycle=self._cycle)

    def stop(self):
        self.alive = False

    def handle_connect(self):
        self.loggercmd("handle_connect",'d')
        self.found_terminator = self.parse_reply

    def parse_reply(self, data):
        data = data.decode()
        self.loggercmd("parse_reply => {}".format(data),'d')
        if data.startswith('OK'):
            self._reply_lock.acquire()
            self._reply_lock.notify()
            self._reply_lock.release()
        elif data.startswith('ACK'):
            self.loggercmd(data,'e')
        else:
            key, sep, value = data.partition(': ')
            self._reply[key] = value

    def parse_item(self, item):
        #all status-related items here
        if self.get_iattr_value(item.conf, ITEM_TAG[0]) in self._mpd_statusRequests:
            key = (self.get_iattr_value(item.conf, ITEM_TAG[0]))
            self._status_items[key] = item
        if self.get_iattr_value(item.conf, ITEM_TAG[1]) in self._mpd_currentsongRequests:
            key = (self.get_iattr_value(item.conf, ITEM_TAG[1]))
            self._currentsong_items[key] = item
        if self.get_iattr_value(item.conf, ITEM_TAG[2]) in self._mpd_statisticRequests:
            key = (self.get_iattr_value(item.conf, ITEM_TAG[2]))
            self._statistic_items[key] = item
        #do not return after status-related items => they can be combined with command-related items
        #all command-related items here
        if self.get_iattr_value(item.conf, ITEM_TAG[3]) in self._mpd_playbackCommands \
          or self.get_iattr_value(item.conf, ITEM_TAG[3]) in self._mpd_playbackOptions \
          or self.get_iattr_value(item.conf, ITEM_TAG[4]) is not None \
          or self.get_iattr_value(item.conf, ITEM_TAG[5]) is not None \
          or self.get_iattr_value(item.conf, ITEM_TAG[6]) in self._mpd_rawCommand \
          or self.get_iattr_value(item.conf, ITEM_TAG[7]) in self._mpd_databaseCommands:
            self.loggercmd("callback assigned for item {}".format(item),'d')
            return self.update_item

    def update_status(self):
        #refresh all subscribed items
        warn = self.canWarnNow()
        self.update_statusitems(warn)
        self.update_currentsong(warn)
        self.update_statistic(warn)
        if warn:
            self.lastWarnTime = datetime.datetime.now()
            for warn in self.orphanItems:
                self.loggercmd(warn,'w')
            self.orphanItems = []

    def update_statusitems(self,warn):
        if not self.connected:
            if warn:
                self.loggercmd("update_status while not connected",'e')
            return
        if (len(self._status_items) <= 0):
            if warn:
                self.loggercmd("status: no items to refresh",'w')
            return
        self.loggercmd("requesting status",'d')
        status = self._send('status')
        self.refreshItems(self._status_items,status,warn)

    def update_currentsong(self,warn):
        if not self.connected:
            if warn:
                self.loggercmd("update_currentsong while not connected",'e')
            return
        if (len(self._currentsong_items) <= 0):
            if warn:
                self.loggercmd("currentsong: no items to refresh",'w')
            return
        self.loggercmd("requesting currentsong",'d')
        currentsong = self._send('currentsong')
        self.refreshItems(self._currentsong_items,currentsong,warn)

    def update_statistic(self,warn):
        if not self.connected:
            if warn:
                self.loggercmd("update_statistic while not connected",'e')
            return
        if (len(self._statistic_items) <= 0):
            if warn:
                self.loggercmd("statistic: no items to refresh",'w')
            return
        self.loggercmd("requesting statistic",'d')
        stats = self._send('stats')
        self.refreshItems(self._statistic_items,stats,warn)

    def refreshItems(self,subscribedItems,response,warn):
        #1. check response for the internal items and refresh them
        if 'state' in response:
            val = response['state']
            if val == 'play':
                self._internal_tems['isPlaying'] = True
                self._internal_tems['isPaused'] = False
                self._internal_tems['isStopped'] = False
            elif val == 'pause':
                self._internal_tems['isPlaying'] = False
                self._internal_tems['isPaused'] = True
                self._internal_tems['isStopped'] = False
            elif val == 'stop':
                self._internal_tems['isPlaying'] = False
                self._internal_tems['isPaused'] = False
                self._internal_tems['isStopped'] = True
            else:
                self.loggercmd("unknown state: {}".format(val),'e')
        if 'volume' in response:
            val = float(response['volume'])
            if val <= 0:
                self._internal_tems['isMuted'] = True
            else:
                self._internal_tems['isMuted'] = False
                self._internal_tems['lastVolume'] = val
        if 'Name' in response:
            val = response['Name']
            if val:
                self._internal_tems['currentName'] = val
        #2. check response for subscribed items and refresh them
        for key in subscribedItems:
            #update subscribed items (if value has changed) which exist directly in the response from MPD
            if key in response:
                val = response[key]
                item = subscribedItems[key]
                if item.type() == 'num':
                    try:
                        val = float(val)
                    except:
                        self.loggercmd("can't parse {} to float".format(val),'e')
                        continue
                elif item.type() == 'bool':
                    if val == '0':
                        val = False
                    elif val == '1':
                        val = True
                    else:
                        self.loggercmd("can't parse {} to bool".format(val),'e')
                        continue
                if item() != val:
                    self.loggercmd("update item {}, old value:{} type:{}, new value:{} type:{}".format(item,item(),item.type(),val,type(val)),'d')
                    self.setItemValue(item,val)
            #update subscribed items which do not exist in the response from MPD
            elif key == 'playpause':
                item = subscribedItems[key]
                val = self._internal_tems['isPlaying']
                if item() != val:
                    self.setItemValue(item,val)
            elif key == 'mute':
                item = subscribedItems[key]
                val = self._internal_tems['isMuted']
                if item() != val:
                    self.setItemValue(item,val)
            elif key == 'Artist':
                item = subscribedItems[key]
                val = self._internal_tems['currentName']
                if item() != val:
                    self.setItemValue(item,val)
            #do not reset these items when the tags are missing in the response from MPD
            #that happens while MPD switches the current track!
            elif key == 'volume' or \
              key == 'repeat' or \
              key == 'random':
                return
            else:
                if warn:
                    self.orphanItems.append("subscribed item \"{}\" not in response from MPD => consider unsubscribing this item".format(key))
                #reset orphaned items because MPD does not send some items when they are disabled e.g. mixrampdb, error,...
                #to keep these items consisitend in SHNG set them to "" or 0. Whenever MPD resends values the items will be refreshed in SHNG
                item = subscribedItems[key]
                self.setItemValue(item,None)

    def setItemValue(self,item,value):
        if item.type() == 'str':
            if value is None or not value:
                value = ''
            item(str(value), 'MPD')
        elif item.type() == 'num':
            if value is None:
                value = 0
            item(float(value), 'MPD')
        else:
            item(value, 'MPD')

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'MPD':
            self.loggercmd("update_item called for item {}".format(item),'d')
            #playbackCommands
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'next':
                self._send('next')
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'play':
                self._send("play {}".format(item()))
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'pause':
                self._send("pause {}".format(item()))
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'stop':
                self._send('stop')
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'playpause':
                if self._internal_tems['isPlaying']:
                    self._send("pause 1")
                elif self._internal_tems['isPaused']:
                    self._send("pause 0")
                elif self._internal_tems['isStopped']:
                    self._send("play")
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'playid':
                self._send("playid {}".format(item()))
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'previous':
                self._send("previous")
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'seek':
                val = item()
                if val:
                    pattern = re.compile("^\d+[ ]\d+$")
                    if pattern.match(val):
                        self._send("seek {}".format(val))
                        return
                self.loggercmd("ignoring invalid seek value",'w')
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'seekid':
                val = item()
                if val:
                    pattern = re.compile("^\d+[ ]\d+$")
                    if pattern.match(val):
                        self._send("seekid {}".format(val))
                        return
                self.loggercmd("ignoring invalid seekid value",'w')
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'seekcur':
                val = item()
                if val:
                    pattern = re.compile("^[+-]?\d+$")
                    if pattern.match(val):
                        self._send("seekcur {}".format(val))
                        return
                self.loggercmd("ignoring invalid seekcur value",'w')
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'mute': #own-defined item
                if self._internal_tems['lastVolume'] < 0: #can be -1 if MPD can't detect the current volume
                    self._internal_tems['lastVolume'] = 20
                self._send("setvol {}".format(int(self._internal_tems['lastVolume']) if self._internal_tems['isMuted'] else 0))
                return
            #playbackoptions
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'consume':
                self._send("consume {}".format(1 if item() else 0))
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'crossfade':
                self._send("crossfade {}".format(item()))
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'mixrampdb':
                self._send("mixrampdb {}".format(item()))
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'mixrampdelay':
                self._send("mixrampdelay {}".format(item()))
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'random':
                self._send("random {}".format(1 if item() else 0))
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'repeat':
                self._send("repeat {}".format(1 if item() else 0))
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'setvol':
                val = item()
                if val > 100:
                    self.loggercmd("invalid volume => value > 100 => set 100",'w')
                    val = 100
                elif val < 0:
                    self.loggercmd("invalid volume => value < 0 => set 0",'w')
                    val = 0
                self._send("setvol {}".format(val))
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'single':
                self._send("single {}".format(1 if item() else 0))
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[3]) == 'replay_gain_mode':
                val = item()
                if val in ['off','track','album','auto']:
                    self._send("replay_gain_mode {}".format(1 if item() else 0))
                else:
                    self.loggercmd("ignoring invalid value ({}) for replay_gain_mode".format(val),'w')
                    pass
                return
            #url
            if self.has_iattr(item.conf, ITEM_TAG[4]):
                self.play_url(item)
                return
            #localplaylist
            if self.has_iattr(item.conf, ITEM_TAG[5]):
                self.play_localplaylist(item)
                return
            #rawcommand
            if self.get_iattr_value(item.conf, ITEM_TAG[6]) == 'rawcommand':
                self._send(item())
                return
            #database
            if self.get_iattr_value(item.conf, ITEM_TAG[7]) == 'update':
                command = 'update'
                if item():
                    command = "{} {}".format(command,item())
                self._send(command)
                return
            if self.get_iattr_value(item.conf, ITEM_TAG[7]) == 'rescan':
                command = 'rescan'
                if item():
                    command = "{} {}".format(command,item())
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
            content = self._sh.tools.fetch_url(url, timeout=4)
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
        url = self.get_iattr_value(item.conf, ITEM_TAG[4])
        play = self._parse_url(url)
        if play == []:
            self.loggercmd("no url to add",'w')
            return
        self._send('clear', False)
        for url in play:
            self._send("add {}".format(url), False)
        self._send('play', False)

    def play_localplaylist(self, item):
        file = self.get_iattr_value(item.conf, ITEM_TAG[5])
        if file:
            self._send('clear', False)
            self._send('load {}'.format(file), False)
            self._send('play', False)
        else:
            self.loggercmd("no playlistname to send",'w')

    def _send(self, command, wait=True):
        self._cmd_lock.acquire()
        self._reply = {}
        self._reply_lock.acquire()
        self.loggercmd("send {} to MPD".format(command),'d')
        self.send((command + '\n').encode())
        if wait:
            self._reply_lock.wait(1)
        self._reply_lock.release()
        reply = self._reply
        self._reply = {}
        self._cmd_lock.release()
        return reply
