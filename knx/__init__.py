#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#  Copyright 2016- Christian Strassburg               c.strassburg@gmx.de
#  Copyright 2017- Serge Wagener                     serge@wagener.family
#  Copyright 2017-2022 Bernd Meiners                Bernd.Meiners@mail.de
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

import logging
import struct
import binascii
import random
import time
from datetime import timedelta
import pathlib

from lib.network import Tcp_client
from lib.utils import Utils
from lib.item import Items
from lib.model.smartplugin import SmartPlugin
from lib.shtime import Shtime

from . import dpts
from . import knxproj
from .knxd import KNXD
from .globals import *
from .webif import WebInterface


class KNX(SmartPlugin):

    PLUGIN_VERSION = "1.8.5"

    # tags actually used by the plugin are shown here
    # can be used later for backend item editing purposes, to check valid item attributes
    ITEM_TAG = [KNX_DPT, KNX_STATUS, KNX_SEND, KNX_REPLY, KNX_LISTEN, KNX_INIT, KNX_CACHE, KNX_POLL]
    ITEM_TAG_PLUS = [KNX_DTP]

    # provider for KNX service
    PROVIDER_KNXD =  'knxd'
    PROVIDER_KNXIP = 'IP Interface'
    PROVIDER_KNXMC = 'IP Router'

    def __init__(self, smarthome):
        self.provider = self.get_parameter_value('provider')
        self.host = self.get_parameter_value('host')
        self.port = self.get_parameter_value('port')
        self.loglevel_knxd_cache_problems = self.get_parameter_value('loglevel_knxd_cache_problems')

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        name = 'plugins.' + self.get_fullname()
        self._client = Tcp_client(name=name, host=self.host, port=self.port, binary=True, autoreconnect=True, connect_cycle=5, retry_cycle=30)
        self._client.set_callbacks(connected=self.handle_connect, data_received=self.parse_knxd_message)  # , disconnected=disconnected_callback, data_received=receive_callback

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("init knx")
        self.shtime = Shtime.get_instance()

        self.gal = {}                   # group addresses to listen to {DPT: dpt, ITEMS: [item 1, item 2, ..., item n], LOGICS: [ logic 1, logic 2, ..., logic n]}
        self.gar = {}                   # group addresses to reply if requested from knx, {DPT: dpt, ITEM: item, LOGIC: None}
        self._init_ga = []
        self._cache_ga = []             # group addresses which should be initalized by the knxd cache
        self._cache_ga_response_pending = []    # group adresses for which a read request was sent to knxd
        self._cache_ga_response_no_value = []   # group adresses for which a response from knxd did not provide a value

        self.time_ga = self.get_parameter_value('time_ga')
        self.date_ga = self.get_parameter_value('date_ga')
        self._send_time_do = self.get_parameter_value('send_time')
        self._bm_separatefile = False
        self._bm_format = "BM': {1} set {2} to {3}"
        self._startup_polling = {}

        # following needed for statistics
        self.enable_stats = self.get_parameter_value('enable_stats')
        self.stats_ga = {}              # statistics for used group addresses on the BUS
        self.stats_pa = {}              # statistics for used group addresses on the BUS
        self.stats_last_read = None     # last read request from KNX
        self.stats_last_write = None    # last write from KNX
        self.stats_last_response = None # last response from KNX
        self.stats_last_action = None   # the most recent action
        self._log_own_packets = self.get_parameter_value('log_own_packets')
        # following is for a special logger called busmonitor
        busmonitor = self.get_parameter_value('busmonitor')

        if busmonitor.lower() in ['on','true']:
            self._busmonitor = self.logger.info
        elif busmonitor.lower() in ['off', 'false']:
            self._busmonitor = self.logger.debug
        elif busmonitor.lower() == 'logger':
            self._bm_separatefile = True
            self._bm_format = "{0};{1};{2};{3}"
            self._busmonitor = logging.getLogger("knx_busmonitor").info
            self.logger.info(self.translate("Using busmonitor (L) = '{}'").format(busmonitor))
        else:
            self.logger.warning(self.translate("Invalid value '{}' configured for parameter 'busmonitor', using 'false'").format(busmonitor))
            self._busmonitor = self.logger.debug

        self.readonly = self.get_parameter_value('readonly')
        if self.readonly:
            self.logger.warning(self.translate("!!! KNX Plugin in READONLY mode !!!"))

        # extension to use knx project files from ETS5
        self.project_file_password = self.get_parameter_value( 'project_file_password')
        self.knxproj_ga = {}
        self.use_project_file = self.get_parameter_value('use_project_file')

        if self.use_project_file:
            # don't bother people without project files
            self.base_project_filename = "projectfile"
            self.projectpath = pathlib.Path(self.get_parameter_value('projectpath'))
            if self.projectpath.is_absolute():
                self.projectpath = self.projectpath / self.base_project_filename
                self.logger.warning(self.translate("Given path is absolute, using {}").format(self.projectpath))
            else:
                self.projectpath = pathlib.Path(self.get_sh().get_basedir()) / self.projectpath / self.base_project_filename
                self.logger.info(self.translate("Given path is relative, using {path}", {'path': self.projectpath} ))

            self._parse_projectfile()

        self.init_webinterface(WebInterface)
        return

    def _parse_projectfile(self):
        self._check_projectfile_destination()
        if self.projectpath.is_file():
            self.knxproj_ga = knxproj.parse_projectfile(self.projectpath, self.project_file_password)

    def _check_projectfile_destination(self):
        if not self.projectpath.exists():
            self.logger.warning(self.translate("File at given path {} does not exist").format(self.projectpath))
            if not self.projectpath.parent.exists():
                self.logger.warning(self.translate("try to create directory {}").format(self.projectpath.parent))
                try:
                    self.projectpath.parent.mkdir(parents=True, exist_ok=True)
                    self.logger.warning(self.translate("directory {} was created").format(self.projectpath.parent))
                except:
                    self.logger.warning(self.translate("could not create directory {}").format(self.projectpath.parent))

    def _send(self, data):
        if not self.alive:
            # do not send anything while plugin is not really running
            self.logger.warning(self.translate('send called while self.alive is False, will NOT send anything to KNX'))
            return

        if len(data) < 2 or len(data) > 0xffff:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(self.translate('Illegal data size: {}').format(repr(data)))
            return False
        # prepend data length for knxd
        send = bytearray(len(data).to_bytes(2, byteorder='big'))
        send.extend(data)
        self._client.send(send)

    def groupwrite(self, ga, payload, dpt, flag='write'):
        pkt = bytearray([0, KNXD.GROUP_PACKET])
        try:
            pkt.extend(self.encode(ga, 'ga'))
        except:
            self.logger.warning('groupwrite: ' + self.translate("problem encoding ga: {}").format(ga))
            return
        pkt.extend([0])
        try:
            pkt.extend(self.encode(payload, dpt))
        except:
            self.logger.warning(self.translate('problem encoding payload {} for dpt {}').format(payload,dpt))
            return
        if flag == 'write':
            flag = FLAG_KNXWRITE
        elif flag == 'response':
            flag = FLAG_KNXRESPONSE
        else:
            self.logger.warning(self.translate(
                "groupwrite telegram for {} with unknown flag: {}. Please choose beetween write and response.").format(
                    ga, flag))
            return
        pkt[5] = flag | pkt[5]
        if self.readonly:
            self.logger.info(self.translate("groupwrite telegram for: {} - Value: {} not sent. Plugin in READONLY mode.").format(ga, payload))
        elif not self.alive:
            self.logger.info(self.translate("groupwrite telegram for: {} - Value: {} not sent. Plugin not alive.").format(ga, payload))
        else:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(self.translate("groupwrite telegram for: {} - Value: {} sent.").format(ga, payload))
            self._send(pkt)

    def _cacheread(self, ga):
        pkt = bytearray([0, KNXD.CACHE_READ])
        try:
            pkt.extend(self.encode(ga, 'ga'))
        except:
            self.logger.warning("_cacheread: " + self.translate('problem encoding ga: {}').format(ga))
            return
        pkt.extend([0, 0])
        if not self.alive:
            self.logger.info(self.translate('not reading knxd cache for ga {} because plugin is not alive.').format(ga))
        else:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(self.translate('reading knxd cache for ga: {}').format(ga))
            self._send(pkt)

    def groupread(self, ga):
        pkt = bytearray([0, KNXD.GROUP_PACKET])
        try:
            pkt.extend(self.encode(ga, 'ga'))
        except:
            self.logger.warning("groupread: " + self.translate('problem encoding ga: {}').format(ga))
            return
        pkt.extend([0, FLAG_KNXREAD])
        if not self.alive:
            self.logger.info(self.translate('not reading knxd group for ga {} because plugin is not alive.').format(ga))
        else:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(self.translate('reading knxd group for ga: {}').format(ga))
            self._send(pkt)

    def _poll(self, **kwargs):
        if ITEM in kwargs:
            item = kwargs[ITEM]
        else:
            item = 'unknown item'
        if 'ga' in kwargs:
            self.groupread(kwargs['ga'])
        else:
            self.logger.warning(self.translate('problem polling {}, no known ga').format(item))

        if 'interval' in kwargs and 'ga' in kwargs:
            try:
                ga = kwargs['ga']
                interval = int(kwargs['interval'])
                next = self.shtime.now() + timedelta(seconds=interval)
                self.scheduler_add(f'KNX poll {item}', self._poll,
                                    value={'caller': self.get_shortname(),
                                    'instance': self.get_instance_name(),
                                    ITEM: item, 'ga': ga, 'interval': interval},
                                    next=next)
            except Exception as ex:
                self.logger.error(f"_poll function got an error {ex}")

    def _send_time(self):
        self.send_time(self.time_ga, self.date_ga)

    def send_time(self, time_ga=None, date_ga=None):
        now = self.shtime.now()
        if time_ga:
            self.groupwrite(time_ga, now, '10')
        if date_ga:
            self.groupwrite(date_ga, now.date(), '11')

    def handle_connect(self, client):
        """
        Callback function to set up internals after a connection to knxd was established

        :param client: the calling client for adaption purposes
        :type client: TCP_client
        """
        if not self.alive:
            self.logger.warning(self.translate('handle_connect called while self.alive is False'))

        # let the knxd use its group address cache
        enable_cache = bytearray([0, KNXD.CACHE_ENABLE])
        self._send(enable_cache)

        # set next kind of data to expect from connection
        self._isLength = True

        # if this is the first connect after init of plugin then read the
        # group addresses from knxd which have the knx_cache attribute
        if self._cache_ga != []:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(self.translate('reading knxd cache'))
            for ga in self._cache_ga:
                self._cache_ga_response_pending.append(ga)
            for ga in self._cache_ga:
                if ga != '':
                    self._cacheread(ga)
                    # wait a little to not overdrive the knxd unless there is a fix
                    time.sleep(KNXD_CACHEREAD_DELAY)
            self._cache_ga = []
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(self.translate('finished reading knxd cache'))

        # let knxd create a new group monitor and send the read requests
        # for all group addresses which have the knx_read  attribute
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(self.translate('enable group monitor'))

        init = bytearray([0, KNXD.OPEN_GROUPCON, 0, 0, 0])
        self._send(init)
        client.terminator = 2
        if self._init_ga != []:
            if client.connected():
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(self.translate('knxd init read for {} ga').format(len(self._init_ga)))
                for ga in self._init_ga:
                    self.groupread(ga)
                self._init_ga = []
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(self.translate('finished knxd init read'))

    def encode(self, data, dpt):
        return dpts.encode[str(dpt)](data)

    def decode(self, data, dpt):
        return dpts.decode[str(dpt)](data)

    def parse_knxd_message(self, client, data):
        """
        inspects a message from knxd (eibd)

        :param client: Tcp_client
        :param data: message from knxd as bytearray

        a message from knxd will have 4 extra bytes plus eventually the knx telegram payload
        2 byte length
        2 byte knxd message type   --> see eibtypes.h

        knx telegram then consists of least 6 bytes if valid

        The process consists of two steps:
        * At first the variable ``self._isLength`` is True and the length for the
          following knxd message plus eventual knx telegram is set to ``client.terminator``
        * then the next call to parse_knxd_message is awaited to contain
          the knxd message type in the first two bytes and then following eventually a knx telegram
        """
        if self._isLength:
            self._isLength = False
            try:
                # expecting an unsigned short integer:
                client.terminator = struct.unpack(">H", data)[0]
            except:
                self.logger.error(f"KNX[{self.get_instance_name()}]: problem unpacking length: {data}")
            return
        else:
            self._isLength = True
            client.terminator = 2

        # expecting the type of the following knxd telegram as an unsigned short integer
        knxd_msg_type = struct.unpack(">H", data[0:2])[0]

        # knxd
        if not knxd_msg_type in [KNXD.GROUP_PACKET, KNXD.CACHE_READ, KNXD.CACHE_READ_NOWAIT]:
            self.handle_other_knxd_messages(knxd_msg_type, data[2:])
            return

        knx_data = data[2:]

        # parse rest of data in assumption of a valid knx telegram
        """
        knx telegram consists of at least 6 bytes
            2 byte source as physical address
            2 byte destination as group address
            2 byte command/data
            n byte data optional, only indicated by length
        """

        # knxd will only deliver 4 bytes and no command/data payload when it is unable to provide a group address from cache.
        if len(knx_data) < 6:
            knx_data_str = binascii.hexlify(knx_data).decode()
            src = ""
            dst = ""
            try:
                src = self.decode(knx_data[0:2], 'pa')
                dst = self.decode(knx_data[2:4], 'ga')
            finally:
                self._cache_ga_response_no_value.append(dst)
                loglevel = logging.getLevelName(self.loglevel_knxd_cache_problems)
                if not isinstance( loglevel, int):
                  loglevel = logging.getLevelName(loglevel)
                self.logger.log(loglevel, f"{len(knx_data)} bytes [{knx_data_str}] from {src} for ga/pa {dst} is not enough data to parse")
            return

        # test if flags provide normal knx telegram data or if they are special
        if len(knx_data) >= 6 and (knx_data[4] & 0x03 or (knx_data[5] & KNX_FLAG_MASK) == FLAG_RESERVED):
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("Unknown Application Protocol Data Unit")
            return


        src = self.decode(knx_data[0:2], 'pa')
        dst = self.decode(knx_data[2:4], 'ga')

        flg = knx_data[5] & KNX_FLAG_MASK
        is_ga = knx_data[4] & 0b1000000
        if flg == FLAG_KNXWRITE:
            flg = 'write'
        elif flg == FLAG_KNXREAD:
            flg = 'read'
        elif flg == FLAG_KNXRESPONSE:
            flg = 'response'
        else:
            self.logger.warning("Unknown flag: {:02x} src: {} dest: {}".format(flg, src, dst))
            return

        if len(knx_data) == 6:
            payload = bytearray([knx_data[5] & KNX_DATA_MASK ]) # 0x3f
        else:
            payload = knx_data[6:]

        if len(payload) == 0:
            # this is an error!!!
            payloadstr = binascii.hexlify(payload).decode()
            msg = f"KNXD message {KNXD.MessageDescriptions[knxd_msg_type]} from {src} for GA {dst} received but payload {payloadstr} has not enough data"
            self.logger.warning(msg)
            return

        if self.enable_stats:
            # update statistics on used group addresses
            if dst not in self.stats_ga:
                self.stats_ga[dst] = {}

            if flg not in self.stats_ga[dst]:
                self.stats_ga[dst][flg] = 1
            else:
                self.stats_ga[dst][flg] = self.stats_ga[dst][flg] + 1
            self.stats_ga[dst]['last_' + flg] = self.shtime.now()

            # update statistics on used physical addresses
            if src not in self.stats_pa:
                self.stats_pa[src] = {}

            if flg not in self.stats_pa[src]:
                self.stats_pa[src][flg] = 1
            else:
                self.stats_pa[src][flg] = self.stats_pa[src][flg] + 1
            self.stats_pa[src]['last_' + flg] = self.shtime.now()

        # further inspect what to do next
        if flg == 'write' or flg == 'response':
            if dst not in self.gal:  # update item/logic
                self._busmonitor(self._bm_format.format(self.get_instance_name(), src, dst, binascii.hexlify(payload).decode()))
                return
            dpt = self.gal[dst][DPT]
            try:
                val = self.decode(payload, dpt)
            except Exception as e:
                self.logger.exception("Problem decoding frame from {} to {} with '{}' and DPT {}. Exception: {}".format(src, dst, binascii.hexlify(payload).decode(), dpt, e))
                return
            if val is not None:
                self._busmonitor(self._bm_format.format(self.get_instance_name(), src, dst, val))
                # print "in:  {0}".format(self.decode(payload, 'hex'))
                # out = ''
                # for i in self.encode(val, dpt):
                #    out += " {0:x}".format(i)
                # print "out:{0}".format(out)

                # remove all ga that came from a cache read request
                if knxd_msg_type == KNXD.CACHE_READ:
                    if dst in self._cache_ga_response_pending:
                        self._cache_ga_response_pending.remove(dst)
                way = "" if knxd_msg_type != KNXD.CACHE_READ else " (from knxd Cache)"
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("{} request from {} to {} with '{}' and DPT {}{}".format(flg, src, dst, binascii.hexlify(payload).decode(), dpt, way))
                src_wrk = self.get_instance_name()
                if src_wrk != '':
                    src_wrk += ':'
                src_wrk += src + ':ga=' + dst
                for item in self.gal[dst][ITEMS]:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug("Set Item '{}' to value '{}' caller='{}', source='{}', dest='{}'".format(item, val, self.get_shortname(), src, dst))
                    item(val, self.get_shortname(), src_wrk, dst)
                for logic in self.gal[dst][LOGICS]:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug("Trigger Logic '{}' from caller='{}', source='{}', value '{}', dest='{}'".format(logic, self.get_shortname(), src_wrk, val, dst))
                    logic.trigger(self.get_shortname(), src_wrk, val, dst)
            else:
                self.logger.warning("Wrong payload '{2}' for ga '{1}' with dpt '{0}'.".format(dpt, dst, binascii.hexlify(payload).decode()))
            if self.enable_stats:
                if flg == 'write':
                    self.stats_last_write = self.shtime.now()
                else:
                    self.stats_last_response = self.shtime.now()
        elif flg == 'read':
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("Device with physical address '{}' requests read for ga '{}'".format(src, dst))
            if self.enable_stats:
                self.stats_last_read = self.shtime.now()
            if dst in self.gar:  # read item
                if self.gar[dst][ITEM] is not None:
                    item = self.gar[dst][ITEM]
                    val = item()
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug("groupwrite value '{}' to ga '{}' as DPT '{}' as response".format(dst, val, self.get_iattr_value(item.conf,KNX_DPT)))
                    if self._log_own_packets is True:
                        self._busmonitor(self._bm_format.format(self.get_instance_name(), src, dst, val))
                    self.groupwrite(dst, val, self.get_iattr_value(item.conf,KNX_DPT), 'response')
                if self.gar[dst][LOGIC] is not None:
                    src_wrk = self.get_instance_name()
                    if src_wrk != '':
                        src_wrk += ':'
                    src_wrk += src + ':ga=' + dst
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug("Trigger Logic '{}' from caller='{}', source='{}', dest='{}'".format(self.gar[dst][LOGIC], self.get_shortname(), src_wrk, dst))
                    self.gar[dst][LOGIC].trigger(self.get_shortname(), src_wrk, None, dst)

    def handle_other_knxd_messages(self, knxd_msg_type, data):
        """to approach a two way communication we need to know more about the other messages"""
        if len(data) > 0:
            payloadstr = f" with data {binascii.hexlify(data).decode()}"
        else:
            payloadstr = " no further data"
        if knxd_msg_type in KNXD.MessageDescriptions:
            msg = f"KNXD message {KNXD.MessageDescriptions[knxd_msg_type]} received {payloadstr}"
        else:
            msg = f"KNXD message UNKNOWN received with data {payloadstr}"

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(msg)

    def run(self):
        """
        Run method for the plugin
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Plugin '{}': run method called".format(self.get_fullname()))
        self.alive = True
        self._client.connect()
        # moved from __init__() for proper restart behaviour
        for item in self._startup_polling:
            _ga = self._startup_polling[item].get('ga')
            _interval = self._startup_polling[item].get('interval')
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("KNX Startup Poll for item '{}': ga {}, interval {}".format(item, _ga, _interval))
            self._poll(**{ITEM: item, 'ga':_ga, 'interval':_interval})

        if self._send_time_do:
            self.scheduler_add('KNX[{0}] time'.format(self.get_instance_name()), self._send_time, prio=5, cycle=int(self._send_time_do))

    def stop(self):
        """
        Stop method for the plugin
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Plugin '{}': stop method called".format(self.get_fullname()))
        self.alive = False
        # added to effect better cleanup on stop
        if self.scheduler_get(f'KNX[{self.get_instance_name()}] time'):
            self.scheduler_remove(f'KNX[{self.get_instance_name()}] time')
        self._client.close()

    def parse_item(self, item):
        """
        Plugin parse_item method. Is called when the plugin is initialized.
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
        if self.has_iattr(item.conf, KNX_DTP):
            self.logger.error("Ignoring {}: please change knx_dtp to knx_dpt.".format(item))
            return None
        if self.has_iattr(item.conf, KNX_DPT):
            dpt = self.get_iattr_value(item.conf, KNX_DPT)
            if dpt not in dpts.decode:
                self.logger.warning("Ignoring {} unknown dpt: {}".format(item, dpt))
                return None
        elif self.has_iattr(item.conf, KNX_STATUS) or self.has_iattr(item.conf, KNX_SEND) or self.has_iattr(item.conf, KNX_REPLY) or self.has_iattr(item.conf, KNX_LISTEN) or self.has_iattr(item.conf, KNX_INIT) or self.has_iattr(item.conf, KNX_CACHE):
            self.logger.warning("Ignoring {}: please add knx_dpt.".format(item))
            return None
        else:
            return None
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Item {} is mapped to KNX Instance {}".format(item, self.get_instance_name()))

        if self.has_iattr(item.conf, KNX_LISTEN):
            knx_listen = self.get_iattr_value(item.conf, KNX_LISTEN)
            if isinstance(knx_listen, str):
                knx_listen = [knx_listen, ]
            for ga in knx_listen:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("{} listen on {}".format(item, ga))
                if ga not in self.gal:
                    self.gal[ga] = {DPT: dpt, ITEMS: [item], LOGICS: []}
                else:
                    if item not in self.gal[ga][ITEMS]:
                        self.gal[ga][ITEMS].append(item)

        if self.has_iattr(item.conf, KNX_INIT):
            ga = self.get_iattr_value(item.conf, KNX_INIT)
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("{} listen on and init with {}".format(item, ga))
            if Utils.get_type(ga) == 'list':
                self.logger.warning("{} Problem while doing knx_init: Multiple GA specified in item definition, using first GA ({}) for reading value".format(item.id(), ga))
                ga = ga[0]
            if ga not in self.gal:
                self.gal[ga] = {DPT: dpt, ITEMS: [item], LOGICS: []}
            else:
                if item not in self.gal[ga][ITEMS]:
                    self.gal[ga][ITEMS].append(item)
            self._init_ga.append(ga)

        if self.has_iattr(item.conf, KNX_CACHE):
            ga = self.get_iattr_value(item.conf, KNX_CACHE)
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("{} listen on and init with cache {}".format(item, ga))
            if Utils.get_type(ga) == 'list':
                self.logger.warning("{} Problem while reading KNX cache: Multiple GA specified in item definition, using first GA ({}) for reading cache".format(item.id(), ga))
                ga = ga[0]
            if ga not in self.gal:
                self.gal[ga] = {DPT: dpt, ITEMS: [item], LOGICS: []}
            else:
                if item not in self.gal[ga][ITEMS]:
                    self.gal[ga][ITEMS].append(item)
            if ga != '':
                self._cache_ga.append(ga)

        if self.has_iattr(item.conf, KNX_REPLY):
            knx_reply = self.get_iattr_value(item.conf, KNX_REPLY)
            if isinstance(knx_reply, str):
                knx_reply = [knx_reply, ]
            for ga in knx_reply:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("{} reply to {}".format(item, ga))
                if ga not in self.gar:
                    self.gar[ga] = {DPT: dpt, ITEM: item, LOGIC: None}
                else:
                    self.logger.warning("{} knx_reply ({}) already defined for {}".format(item.id(), ga, self.gar[ga][ITEM]))

        if self.has_iattr(item.conf, KNX_SEND):
            if isinstance(self.get_iattr_value(item.conf, KNX_SEND), str):
                self.set_attr_value(item.conf, KNX_SEND, [self.get_iattr_value(item.conf, KNX_SEND), ])

        if self.has_iattr(item.conf, KNX_STATUS):
            if isinstance(self.get_iattr_value(item.conf, KNX_STATUS), str):
                self.set_attr_value(item.conf, KNX_STATUS, [self.get_iattr_value(item.conf, KNX_STATUS), ])

        if self.has_iattr(item.conf, KNX_POLL):
            knx_poll = self.get_iattr_value(item.conf, KNX_POLL)
            if isinstance(knx_poll, str):
                knx_poll = [knx_poll, ]
            if len(knx_poll) == 2:
                poll_ga = knx_poll[0]
                poll_interval = float(knx_poll[1])

                self.logger.info(
                    "Item {} is polled on GA {} every {} seconds".format(item, poll_ga, poll_interval))
                randomwait = random.randrange(15)
                next = self.shtime.now() + timedelta(seconds=poll_interval + randomwait)
                self._startup_polling.update({item: {'ga': poll_ga, 'interval': poll_interval}})
                '''
                self._sh.scheduler.add(f'KNX poll {item}', self._poll,
                                       value={ITEM: item, 'ga': poll_ga, 'interval': poll_interval}, next=next)
                '''
            else:
                self.logger.warning("Ignoring knx_poll for item {}: We need two parameters, one for the GA and one for the polling interval.".format(item))
                pass

        if self.has_iattr(item.conf, KNX_STATUS) or self.has_iattr(item.conf, KNX_SEND):
            return self.update_item

        return None

    def parse_logic(self, logic):
        """
        Plugin parse_logic method
        """
        if KNX_DPT in logic.conf:
            dpt = logic.conf[KNX_DPT]
            if dpt not in dpts.decode:
                self.logger.warning("Ignoring {} unknown dpt: {}".format(logic, dpt))
                return None
        else:
            return None

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Logic {} is mapped to KNX Instance {}".format(logic, self.get_instance_name()))

        if KNX_LISTEN in logic.conf:
            knx_listen = logic.conf[KNX_LISTEN]
            if isinstance(knx_listen, str):
                knx_listen = [knx_listen, ]
            for ga in knx_listen:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("{} listen on {}".format(logic, ga))
                if ga not in self.gal:
                    self.gal[ga] = {DPT: dpt, ITEMS: [], LOGICS: [logic]}
                else:
                    self.gal[ga][LOGICS].append(logic)

        if KNX_REPLY in logic.conf:
            knx_reply = logic.conf[KNX_REPLY]
            if isinstance(knx_reply, str):
                knx_reply = [knx_reply, ]
            for ga in knx_reply:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("{} reply to {}".format(logic, ga))
                if ga in self.gar:
                    if self.gar[ga][LOGIC] is False:
                        obj = self.gar[ga][ITEM]
                    else:
                        obj = self.gar[ga][LOGIC]
                    self.logger.warning("{} knx_reply ({}) already defined for {}".format(logic, ga, obj))
                else:
                    self.gar[ga] = {DPT: dpt, ITEM: None, LOGIC: logic}

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
        if self.alive:
            if self.has_iattr(item.conf, KNX_SEND):
                if caller != self.get_shortname():
                    for ga in self.get_iattr_value(item.conf, KNX_SEND):
                        _value = item()
                        if self._log_own_packets is True:
                            self._busmonitor(self._bm_format.format(self.get_instance_name(), 'SEND', ga, _value))
                        self.groupwrite(ga, _value, self.get_iattr_value(item.conf, KNX_DPT))
            if self.has_iattr(item.conf, KNX_STATUS):
                for ga in self.get_iattr_value(item.conf, KNX_STATUS):  # send status update
                    if ga != dest:
                        _value = item()
                        if self._log_own_packets is True:
                            self._busmonitor(self._bm_format.format(self.get_instance_name(), 'STATUS', ga, _value))
                        self.groupwrite(ga, _value, self.get_iattr_value(item.conf, KNX_DPT))


# ------------------------------------------
#    Statistics functions for KNX
# ------------------------------------------

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
        ar = [self.stats_last_response, self.stats_last_write, self.stats_last_read]
        while None in ar:
            ar.remove(None)
        if ar == []:
            return None
        else:
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
