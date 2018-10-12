#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#  Copyright 2016- Christian Strassburg               c.strassburg@gmx.de
#  Copyright 2017- Serge Wagener                     serge@wagener.family
#  Copyright 2017- Bernd Meiners                    Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.py.  
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  SmartHomeNG.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

# dict for statistic functions:
# stats_pa = { ga1 : { 'read' : n-read,
#                      'write' : n-write,
#                      'response' : n-response,
#                      'last_read' : datetime,
#                      'last_write' : datetime,
#                      'last_response' : datetime },
#              ga2 : {...} }

import logging
import threading
import struct
import binascii
import random
import time

import lib.connection
from lib.model.smartplugin import SmartPlugin
from datetime import timedelta
from . import dpts

# types from knxd\src\include\eibtypes.h
KNXD_OPEN_GROUPCON  = 38     # 0x26
KNXD_GROUP_PACKET   = 39     # 0x27 ‭
KNXD_CACHE_ENABLE   = 112    # 0x70 
KNXD_CACHE_DISABLE  = 113    # 0x71
KNXD_CACHE_READ     = 116    # 0x74 

KNXD_CACHEREAD_DELAY  = 0.35
KNXD_CACHEREAD_DELAY  = 0.0

KNXREAD = 0x00
KNXRESP = 0x40
KNXWRITE = 0x80

# deprecated due to the new smartplugin model
# KNX_INSTANCE = 'knx_instance'     # which instance of plugin to use for a given item (deprecated!)
KNX_DPT      = 'knx_dpt'          # data point type
KNX_STATUS   = 'knx_status'       # status
KNX_SEND     = 'knx_send'         # send changes within SmartHomeNG to this ga
KNX_REPLY    = 'knx_reply'        # answer read requests from knx with item value from SmartHomeNG
KNX_CACHE    = 'knx_cache'        # get item from knx_cache
KNX_INIT     = 'knx_init'         # query knx upon init
KNX_LISTEN   = 'knx_listen'       # write or response from knx will change the value of this item
KNX_POLL     = 'knx_poll'         # query (poll) a ga on knx in regular intervals

KNX_DTP      = 'knx_dtp'          # often misspelled argument in config files, instead should be knx_dpt

ITEM = 'item'
ITEMS = 'items'
LOGIC = 'logic'
LOGICS = 'logics'
DPT='dpt'

class KNX(lib.connection.Client,SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.3.4"


    # tags actually used by the plugin are shown here
    # can be used later for backend item editing purposes, to check valid item attributes
    ITEM_TAG = [KNX_DPT, KNX_STATUS, KNX_SEND, KNX_REPLY, KNX_LISTEN, KNX_INIT, KNX_CACHE, KNX_POLL]
    ITEM_TAG_PLUS = [KNX_DTP]

    def __init__(self, smarthome, time_ga=None, date_ga=None, send_time=False, busmonitor=False, host='127.0.0.1',
                 port=6720, readonly=False, instance='default', enable_stats = True):
        lib.connection.Client.__init__(self, host, port, monitor=True)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("init knx")        
        self._sh = smarthome
        self.gal = {}                   # group addresses to listen to {DPT: dpt, ITEMS: [item 1, item 2, ..., item n], LOGICS: [ logic 1, logic 2, ..., logic n]}
        self.gar = {}                   # group addresses to reply if requested from knx, {DPT: dpt, ITEM: item, LOGIC: None}
        self._init_ga = []
        self._cache_ga = []             # group addresses which should be initalized by the knxd cache
        self._cache_ga_response_pending = []
        self.time_ga = time_ga
        self.date_ga = date_ga
        self._instance = instance
        self._lock = threading.Lock()
        self._bm_separatefile = False
        self._bm_format= "KNX[{0}]: {1} set {2} to {3}"
        # following needed for statistics
        self.enable_stats = enable_stats
        self.stats_ga = {}              # statistics for used group addresses on the BUS
        self.stats_pa = {}              # statistics for used group addresses on the BUS
        self.stats_last_read = None     # last read request from KNX
        self.stats_last_write = None    # last write from KNX
        self.stats_last_response = None # last response from KNX
        self.stats_last_action = None   # the newes

        if self.to_bool(busmonitor,default=busmonitor):
            self._busmonitor = self.logger.info
        else:
            self._busmonitor = self.logger.debug

            # write bus messages in a separate logger
            if isinstance(busmonitor, str):
                if busmonitor.lower() in ['logger']:
                    self._bm_separatefile = True
                    self._bm_format = "{0};{1};{2};{3}"
                    self._busmonitor = logging.getLogger("knx_busmonitor").info

        if send_time:
            self._sh.scheduler.add('KNX[{0}] time'.format(self.get_instance_name()), self._send_time, prio=5, cycle=int(send_time))

        readonly = self.to_bool(readonly)
        if readonly: 
            self.logger.warning("!!! KNX Plugin in READONLY mode !!! ")
        self.readonly = readonly

    #### just here until the smartplugin base class is fixed: Unfortunately it does not set it's name if ALLOW_MULTIINSTANCE is False
    def get_instance_name(self):
        """
            return instance name of the plugin
            :rtype: str
        """
        return self._instance

    def _send(self, data):
        if len(data) < 2 or len(data) > 0xffff:
            self.logger.debug('KNX[{0}]: Illegal data size: {1}'.format(self.get_instance_name(), repr(data)))
            return False
        # prepend data length
        send = bytearray(len(data).to_bytes(2, byteorder='big'))
        send.extend(data)
        self.send(send)

    def groupwrite(self, ga, payload, dpt, flag='write'):
        pkt = bytearray([0, KNXD_GROUP_PACKET])
        try:
            pkt.extend(self.encode(ga, 'ga'))
        except:
            self.logger.warning('KNX[{0}]: problem encoding ga: {1}'.format(self.get_instance_name(), ga))
            return
        pkt.extend([0])
        pkt.extend(self.encode(payload, dpt))
        if flag == 'write':
            flag = KNXWRITE
        elif flag == 'response':
            flag = KNXRESP
        else:
            self.logger.warning(
                "KNX[{0}]: groupwrite telegram for {1} with unknown flag: {2}. Please choose beetween write and response.".format(
                    self.get_instance_name(), ga, flag))
            return
        pkt[5] = flag | pkt[5]
        if self.readonly:
            self.logger.info("KNX[{2}]: groupwrite telegram for: {0} - Value: {1} not send. Plugin in READONLY mode. ".format(ga,payload,self.get_instance_name()))
        else:
            self._send(pkt)

    def _cacheread(self, ga):
        pkt = bytearray([0, KNXD_CACHE_READ])
        try:
            pkt.extend(self.encode(ga, 'ga'))
        except:
            self.logger.warning('KNX[{0}]: problem encoding ga: {1}'.format(self.get_instance_name(), ga))
            return
        pkt.extend([0, 0])
        self.logger.debug('KNX[{0}]: reading knxd cache for ga: {1}'.format(self.get_instance_name(), ga))
        self._send(pkt)

    def groupread(self, ga):
        pkt = bytearray([0, KNXD_GROUP_PACKET])
        try:
            pkt.extend(self.encode(ga, 'ga'))
        except:
            self.logger.warning('KNX[{0}]: problem encoding ga: {1}'.format(self.get_instance_name(), ga))
            return
        pkt.extend([0, KNXREAD])
        self._send(pkt)

    def _poll(self, **kwargs):
        if ITEM in kwargs:
            item = kwargs[ITEM]
        else:
            item = 'unknown item'

        if 'ga' in kwargs:
            self.groupread(kwargs['ga'])
        else:
            self.logger.warning('KNX[{0}]: problem polling {1}, no known ga'.format(self.get_instance_name(), item))

        if 'interval' in kwargs and 'ga' in kwargs:
            ga = kwargs['ga']
            interval = int(kwargs['interval'])
            next = self._sh.now() + timedelta(seconds=interval)
            self._sh.scheduler.add('KNX poll {}'.format(item), self._poll,
                                   value={'instance': self.get_instance_name(), ITEM: item, 'ga': ga, 'interval': interval},
                                   next=next)

    def _send_time(self):
        self.send_time(self.time_ga, self.date_ga)

    def send_time(self, time_ga=None, date_ga=None):
        now = self._sh.now()
        if time_ga:
            self.groupwrite(time_ga, now, '10')
        if date_ga:
            self.groupwrite(date_ga, now.date(), '11')

    def handle_connect(self):
        self.discard_buffers()
        enable_cache = bytearray([0, KNXD_CACHE_ENABLE])
        self._send(enable_cache)
        self.found_terminator = self.parse_length
        if self._cache_ga != []:
            if self.connected:
                self.logger.debug('KNX[{0}]: reading knxd cache'.format(self.get_instance_name()))
                for ga in self._cache_ga:
                    self._cache_ga_response_pending.append(ga)
                for ga in self._cache_ga:
                    self._cacheread(ga)
                    # wait a little to not overdrive the knxd unless there is a fix
                    time.sleep(KNXD_CACHEREAD_DELAY)
                self._cache_ga = []
                self.logger.debug('KNX[{0}]: finished reading knxd cache'.format(self.get_instance_name()))

        self.logger.debug('KNX[{0}]: enable group monitor'.format(self.get_instance_name()))
        init = bytearray([0, KNXD_OPEN_GROUPCON, 0, 0, 0])
        self._send(init)
        self.terminator = 2
        if self._init_ga != []:
            if self.connected:
                self.logger.debug('KNX[{0}]: knxd init read for {1} ga'.format(self.get_instance_name(),len(self._init_ga)))
                for ga in self._init_ga:
                    self.groupread(ga)
                self._init_ga = []
                self.logger.debug('KNX[{0}]: finished knxd init read'.format(self.get_instance_name()))

#   def collect_incoming_data(self, data):
#       print('#  bin   h  d')
#       for i in data:
#           print("{0:08b} {0:02x} {0:02d}".format(i))
#       self.buffer.extend(data)

    def parse_length(self, length):
        # self.found_terminator is introduced in lib/connection.py
        self.found_terminator = self.parse_telegram
        try:
            self.terminator = struct.unpack(">H", length)[0]
        except:
            self.logger.error("KNX[{0}]: problem unpacking length: {1}".format(self.get_instance_name(), length))
            self.close()

    def encode(self, data, dpt):
        return dpts.encode[str(dpt)](data)

    def decode(self, data, dpt):
        return dpts.decode[str(dpt)](data)

    def parse_telegram(self, data):
        """
        inspects a received eibd/knxd compatible telegram
        
        :param data: expected is a bytearray with
            2 byte type   --> see eibtypes.h
            2 byte source as physical address
            2 byte destination as group address
            2 byte command/data
            n byte data

        """
        # self.found_terminator is introduced in lib/connection.py
        self.found_terminator = self.parse_length  # reset parser and terminator
        self.terminator = 2
        typ = struct.unpack(">H", data[0:2])[0]
        if (typ != KNXD_GROUP_PACKET and typ != KNXD_CACHE_READ) or len(data) < 8:
            # self.logger.debug("Ignore telegram.")
            return
        if (data[6] & 0x03 or (data[7] & 0xC0) == 0xC0):
            self.logger.debug("KNX[{0}]: Unknown APDU".format(self.get_instance_name()))
            return
        src = self.decode(data[2:4], 'pa')
        dst = self.decode(data[4:6], 'ga')
        flg = data[7] & 0xC0
        if flg == KNXWRITE:
            flg = 'write'
        elif flg == KNXREAD:
            flg = 'read'
        elif flg == KNXRESP:
            flg = 'response'
        else:
            self.logger.warning("KNX[{0}]: Unknown flag: {1:02x} src: {2} dest: {3}".format(self.get_instance_name(), flg, src, dst))
            return
        if len(data) == 8:
            payload = bytearray([data[7] & 0x3f])
        else:
            payload = data[8:]

        if self.enable_stats:
            # update statistics on used group addresses
            if not dst in self.stats_ga:
                self.stats_ga[dst] = {}

            if not flg in self.stats_ga[dst]:
                self.stats_ga[dst][flg] = 1
            else:
                self.stats_ga[dst][flg] = self.stats_ga[dst][flg] + 1

            # update statistics on used group addresses
            if not src in self.stats_pa:
                self.stats_pa[src] = {}

            if not flg in self.stats_pa[src]:
                self.stats_pa[src][flg] = 1
            else:
                self.stats_pa[src][flg] = self.stats_pa[src][flg] + 1

        # further inspect what to do next
        if flg == 'write' or flg == 'response':
            if dst not in self.gal:  # update item/logic
                self._busmonitor(self._bm_format.format(self.get_instance_name(), src, dst, binascii.hexlify(payload).decode()))
                return
            dpt = self.gal[dst][DPT]
            try:
                val = self.decode(payload, dpt)
            except Exception as e:
                self.logger.exception("KNX[{0}]: Problem decoding frame from {1} to {2} with '{3}' and DPT {4}. Exception: {5}".format(self.get_instance_name(), src, dst, binascii.hexlify(payload).decode(), dpt, e))
                return
            if val is not None:
                self._busmonitor(self._bm_format.format(self.get_instance_name(), src, dst, val))
                #print "in:  {0}".format(self.decode(payload, 'hex'))
                #out = ''
                #for i in self.encode(val, dpt):
                #    out += " {0:x}".format(i)
                #print "out:{0}".format(out)

                # remove all ga that came from a cache read request
                if typ == KNXD_CACHE_READ:
                    if dst in self._cache_ga_response_pending:
                        self._cache_ga_response_pending.remove(dst)
                way = "" if typ != KNXD_CACHE_READ else " (from knxd Cache)"
                self.logger.debug("KNX[{0}]: {5} request from {1} to {2} with '{3}' and DPT {4}{6}".format(self.get_instance_name(), src, dst, binascii.hexlify(payload).decode(), dpt, flg, way))
                for item in self.gal[dst][ITEMS]:
                    item(val, 'KNX', src, dst)
                for logic in self.gal[dst][LOGICS]:
                    logic.trigger('KNX', src, val, dst)
            else:
                self.logger.warning("KNX[{0}]: Wrong payload '{3}' for ga '{2}' with dpt '{1}'.".format(self.get_instance_name(), dpt, dst, binascii.hexlify(payload).decode()))
            if self.enable_stats:
                if flg == 'write':
                    self.stats_last_write = self._sh.now()
                else:
                    self.stats_last_response = self._sh.now()
        elif flg == 'read':
            self.logger.debug("KNX[{0}]: {1} read {2}".format(self.get_instance_name(), src, dst))
            if self.enable_stats:
                self.stats_last_read = self._sh.now()
            if dst in self.gar:  # read item
                if self.gar[dst][ITEM] is not None:
                    item = self.gar[dst][ITEM]
                    self.groupwrite(dst, item(), self.get_iattr_value(item.conf,KNX_DPT), 'response')
                if self.gar[dst][LOGIC] is not None:
                    self.gar[dst][LOGIC].trigger('KNX', src, None, dst)

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False
        self.handle_close()

    def parse_item(self, item):
        """
        examines item attributes to see if action is needed by change of the item via SmartHomeNG
        :param item: a dictionary with item attributes
        :return: a callback function to be called then item is to be changed
        """
        if self.has_iattr(item.conf, KNX_DTP):
            self.logger.error("KNX[{0}]: Ignoring {1}: please change knx_dtp to knx_dpt.".format(self.get_instance_name(), item))
            return None
        if self.has_iattr(item.conf, KNX_DPT):
            dpt = self.get_iattr_value( item.conf, KNX_DPT)
            if dpt not in dpts.decode:
                self.logger.warning("KNX[{0}]: Ignoring {1} unknown dpt: {2}".format(self.get_instance_name(), item, dpt))
                return None
        elif self.has_iattr(item.conf, KNX_STATUS) or self.has_iattr(item.conf, KNX_SEND) or self.has_iattr(item.conf, KNX_REPLY) or self.has_iattr(item.conf, KNX_LISTEN) or self.has_iattr(item.conf, KNX_INIT) or self.has_iattr( item.conf, KNX_CACHE):
            self.logger.warning(
                "KNX[{0}]: Ignoring {1}: please add knx_dpt.".format(self.get_instance_name(), item))
            return None
        else:
            return None
        # todo:
        # cleanup here
        # following deleted because multi instance was changed
        #if self.has_iattr(item.conf, self.KNX_INSTANCE):
        #    if not item.conf[self.KNX_INSTANCE] == self.instance:
        #        return None
        #else:
        #    if not self.instance == 'default':
        #        return None
        self.logger.debug("KNX[{1}]: Item {0} is mapped to KNX Instance {1}".format(item, self.get_instance_name()))

        if self.has_iattr(item.conf, KNX_LISTEN):
            knx_listen = self.get_iattr_value(item.conf, KNX_LISTEN)
            if isinstance(knx_listen, str):
                knx_listen = [knx_listen, ]
            for ga in knx_listen:
                self.logger.debug("KNX[{0}]: {1} listen on {2}".format(self.get_instance_name(), item, ga))
                if not ga in self.gal:
                    self.gal[ga] = {DPT: dpt, ITEMS: [item], LOGICS: []}
                else:
                    if not item in self.gal[ga][ITEMS]:
                        self.gal[ga][ITEMS].append(item)

        if self.has_iattr(item.conf, KNX_INIT):
            ga = self.get_iattr_value(item.conf, KNX_INIT)
            self.logger.debug("KNX[{0}]: {1} listen on and init with {2}".format(self.get_instance_name(), item, ga))
            if not ga in self.gal:
                self.gal[ga] = {DPT: dpt, ITEMS: [item], LOGICS: []}
            else:
                if not item in self.gal[ga][ITEMS]:
                    self.gal[ga][ITEMS].append(item)
            self._init_ga.append(ga)

        if self.has_iattr(item.conf, KNX_CACHE):
            ga = self.get_iattr_value(item.conf, KNX_CACHE)
            self.logger.debug("KNX[{0}]: {1} listen on and init with cache {2}".format(self.get_instance_name(), item, ga))
            if not ga in self.gal:
                self.gal[ga] = {DPT: dpt, ITEMS: [item], LOGICS: []}
            else:
                if not item in self.gal[ga][ITEMS]:
                    self.gal[ga][ITEMS].append(item)
            self._cache_ga.append(ga)

        if self.has_iattr(item.conf, KNX_REPLY):
            knx_reply = self.get_iattr_value(item.conf, KNX_REPLY)
            if isinstance(knx_reply, str):
                knx_reply = [knx_reply, ]
            for ga in knx_reply:
                self.logger.debug("KNX[{0}]: {1} reply to {2}".format(self.get_instance_name(), item, ga))
                if ga not in self.gar:
                    self.gar[ga] = {DPT: dpt, ITEM: item, LOGIC: None}
                else:
                    self.logger.warning(
                        "KNX[{0}]: {1} knx_reply ({2}) already defined for {3}".format(self.get_instance_name(), item.id(), ga,
                                                                                       self.gar[ga][ITEM]))

        if self.has_iattr(item.conf, KNX_SEND):
            if isinstance(self.get_iattr_value(item.conf, KNX_SEND), str):
                self.set_attr_value(item.conf, KNX_SEND, [self.get_iattr_value(item.conf, KNX_SEND), ])
                #item.conf['knx_send'] = [self.get_iattr_value(item.conf,'knx_send'), ]

        if self.has_iattr(item.conf, KNX_STATUS):
            if isinstance(self.get_iattr_value(item.conf, KNX_STATUS), str):
                self.set_attr_value(item.conf, KNX_STATUS, [self.get_iattr_value(item.conf, KNX_STATUS), ])
                #item.conf['knx_status'] = [self.get_iattr_value(item.conf,'knx_status'), ]

        if self.has_iattr(item.conf, KNX_STATUS) or self.has_iattr(item.conf, KNX_SEND):
            return self.update_item

        if self.has_iattr(item.conf, KNX_POLL):
            knx_poll = self.get_iattr_value(item.conf, KNX_POLL)
            if isinstance(knx_poll, str):
                knx_poll = [knx_poll, ]
            if len(knx_poll) == 2:
                poll_ga = knx_poll[0]
                poll_interval = knx_poll[1]

                self.logger.info(
                    "KNX[{0}]: Item {1} is polled on GA {2} every {3} seconds".format(self.get_instance_name(), item, poll_ga,
                                                                                      poll_interval))
                randomwait = random.randrange(15)
                next = self._sh.now() + timedelta(seconds=poll_interval + randomwait)
                self._sh.scheduler.add('KNX poll {}'.format(item), self._poll,
                                       value={ITEM: item, 'ga': poll_ga, 'interval': poll_interval}, next=next)
            else:
                self.logger.warning(
                    "KNX[{0}]: Ignoring knx_poll for item {1}: We need two parameters, one for the GA and one for the polling interval.".format(
                        self.get_instance_name(), item))
                pass

        return None

    def parse_logic(self, logic):
        if KNX_DPT in logic.conf:
            dpt = logic.conf[KNX_DPT]
            if dpt not in dpts.decode:
                self.logger.warning("KNX[{0}]: Ignoring {1} unknown dpt: {2}".format(self.get_instance_name(), logic, dpt))
                return None
        else:
            return None

        #if self.has_iattr(logic.conf,'knx_instance'):
        #    if not logic.conf['knx_instance'] == self.get_instance_name():
        #        return None
        #else:
        #    if not self.get_instance_name() == 'default':
        #        return None
        self.logger.debug("KNX[{1}]: Logic {0} is mapped to KNX Instance {1}".format(logic, self.get_instance_name()))

        if KNX_LISTEN in logic.conf:
            knx_listen = logic.conf[KNX_LISTEN]
            if isinstance(knx_listen, str):
                knx_listen = [knx_listen, ]
            for ga in knx_listen:
                self.logger.debug("KNX[{0}]: {1} listen on {2}".format(self.get_instance_name(), logic, ga))
                if not ga in self.gal:
                    self.gal[ga] = {DPT: dpt, ITEMS: [], LOGICS: [logic]}
                else:
                    self.gal[ga][LOGICS].append(logic)

        if KNX_REPLY in logic.conf:
            knx_reply = logic.conf[KNX_REPLY]
            if isinstance(knx_reply, str):
                knx_reply = [knx_reply, ]
            for ga in knx_reply:
                self.logger.debug("KNX[{0}]: {1} reply to {2}".format(self.get_instance_name(), logic, ga))
                if ga in self.gar:
                    if self.gar[ga][LOGIC] is False:
                        obj = self.gar[ga][ITEM]
                    else:
                        obj = self.gar[ga][LOGIC]
                    self.logger.warning("KNX[{0}]: {1} knx_reply ({2}) already defined for {3}".format(self.get_instance_name(), logic, ga, obj))
                else:
                    self.gar[ga] = {DPT: dpt, ITEM: None, LOGIC: logic}

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        decides what to do with an updates item value
        :param item: the item with its attributes
        :param caller: a hint to the originator of the values change
        """
        if self.has_iattr(item.conf, KNX_SEND):
            if caller != 'KNX':
                for ga in self.get_iattr_value(item.conf, KNX_SEND):
                    self.groupwrite(ga, item(), self.get_iattr_value(item.conf, KNX_DPT))
        if self.has_iattr(item.conf, KNX_STATUS):
            for ga in self.get_iattr_value(item.conf, KNX_STATUS):  # send status update
                if ga != dest:
                    self.groupwrite(ga, item(), self.get_iattr_value(item.conf, KNX_DPT))

    """
    The statistics functions were introduced to watch what is happening on the KNX.
    Mainly it is recorded which physical device sends data by write or response or requests data
    by read operation.
    Whenever such a telegram is received, it is recorded 
    - which physical device sended the request (originator)
    - which kind of request (read, write, response)
    - target group address affected
    - a counter for the specific kind of request (read, write, response) is increased.
    
    With an additional logic these statistics can be requested from the plugin and examined for
    - unknown group addresses which are not known to either ETS or to SmartHomeNG
    - unknown physical addresses which are new and unexpected
    - adresses that do not react upon requests
    - adresses that can't satisfy cache requests
    """
    def enable_stats(self):
        """
        Enables the tracking of KNX telegrams during runtime of SmartHomeNG
        """
        self.enable_stats = True

    def disable_stats(self):
        """
        Disables the tracking of KNX telegrams during runtime of SmartHomeNG
        It might be a good idea to clear your stats afterwards with clear_stats()
        """
        self.enable_stats = False

    def clear_stats(self):
        """
        clear all statistic values
        """
        self.clear_stats_ga()
        self.clear_stats_pa()

    def clear_stats_ga(self):
        """
        clear statistic values for group addresses
        """
        if len(self.stats_ga):
            for ga in self.stats_ga:
                self.stats_ga[ga] = {}

    def clear_stats_pa(self):
        """
        clear statistic values for physical addresses
        """
        if len(self.stats_pa):
            for ga in self.stats_pa:
                self.stats_pa[ga] = {}

    def get_stats_ga(self):
        """
        returns a dict with following structure
        ```
        stats_ga = { ga1 : { 'read' : n-read,               # counter of read requests from KNX
                             'write' : n-write,             # counter of write operations from KNX
                             'response' : n-response,       # counter of response operations from KNX
                             'last_read' : datetime,        # the respective datetime object of read,
                             'last_write' : datetime,       # write
                             'last_response' : datetime },  # and response
                     ga2 : {...} }
        ```
        :return: dict
        """
        return self.stats_ga

    def get_stats_pa(self):
        """
        returns a dict with following structure
        ```
        stats_pa = { pa1 : { 'read' : n-read,               # counter of read requests from KNX
                             'write' : n-write,             # counter of write operations from KNX
                             'response' : n-response,       # counter of response operations from KNX
                             'last_read' : datetime,        # the respective datetime object of read,
                             'last_write' : datetime,       # write
                             'last_response' : datetime },  # and response
                     pa2 : {...} }
        ```
        :return: dict
        """
        return self.stats_pa

    def get_stats_last_read(self):
        """
        return the time of the last read request on KNX
        :return: datetime of last time read
        """
        return self.stats_last_read

    def get_stats_last_write(self):
        """
        return the time of the last write request on KNX
        :return: datetime of last time write
        """
        return self.stats_last_write

    def get_stats_last_response(self):
        """
        return the time of the last response on KNX
        :return: datetime of last response write
        """
        return self.stats_last_response

    def get_stats_last_action(self):
        """
        gives back the last point in time when a telegram from KNX arrived
        :return: datetime of last time
        """
        ar = [ self.stats_last_response, self.stats_last_write, self.stats_last_read ]
        while None in ar:
            ar.remove(None)
        return max(ar)

    def get_unsatisfied_cache_read_ga(self):
        """
        At start all items that have a knx_cache attribute will be queried to knxd
        it could however happen, that not all of these queries are satisfied with a response,
        either of a knx failure, an internatl knxd problem or absent devices
        So ideally no reminding ga should be left after a delay time of startup
        :return: list of group addresses that did not receive a cache read response
        """
        return self._cache_ga_response_pending


