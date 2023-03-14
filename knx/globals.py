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

""" Global definitions of constants and functions for KNX plugin """

KNXD_CACHEREAD_DELAY  = 0.35
KNXD_CACHEREAD_DELAY  = 0.0

KNX_DATA_MASK =     0b00111111 # 0x3f up to 6 bits form data content
KNX_FLAG_MASK =     0b11000000 # 0xC0
FLAG_KNXREAD =      0b00000000 # 0x00
FLAG_KNXRESPONSE =  0b01000000 # 0x40
FLAG_KNXWRITE =     0b10000000 # 0x80
FLAG_RESERVED =     0b11000000 # 0xC0 none of the above flags, one need to examine the previous byte for lowest two bits then

# attribute keywords
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
DPT = 'dpt'
