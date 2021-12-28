#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#  Copyright 2021 Bernd Meiners                     Bernd.Meiners@mail.de
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
#  along with SmartHomeNG.  If not, see <http://www.gnu.org/licenses/>.
#########################################################################


"""The types from knxd\src\include\eibtypes.h are partially defined here and encapsulated in KNXD namespace"""

class KNXD():
    INVALID_REQUEST            = 0     # 0x0000
    CONNECTION_INUSE           = 1     # 0x0001
    PROCESSING_ERROR           = 2     # 0x0002
    CLOSED                     = 3     # 0x0003
    RESET_CONNECTION           = 4     # 0x0004

    OPEN_BUSMONITOR            = 16    # 0x0010
    OPEN_BUSMONITOR_TEXT       = 17    # 0x0011
    OPEN_VBUSMONITOR           = 18    # 0x0012
    OPEN_VBUSMONITOR_TEXT      = 19    # 0x0013
    BUSMONITOR_PACKET          = 20    # 0x0014
    BUSMONITOR_PACKET_TS       = 21    # 0x0015
    OPEN_BUSMONITOR_TS         = 22    # 0x0016
    OPEN_VBUSMONITOR_TS        = 23    # 0x0017  

    OPEN_T_CONNECTION          = 32    # 0x0020
    OPEN_T_INDIVIDUAL          = 33    # 0x0021
    OPEN_T_GROUP               = 34    # 0x0022
    OPEN_T_BROADCAST           = 35    # 0x0023
    OPEN_T_TPDU                = 36    # 0x0024
    APDU_PACKET                = 37    # 0x0025
    OPEN_GROUPCON              = 38    # 0x0026
    GROUP_PACKET               = 39    # 0x0027

    PROG_MODE                  = 48    # 0x0030
    MASK_VERSION               = 49    # 0x0031
    M_INDIVIDUAL_ADDRESS_READ  = 50    # 0x0032

    M_INDIVIDUAL_ADDRESS_WRITE = 64    # 0x0040
    ERROR_ADDR_EXISTS          = 65    # 0x0041
    ERROR_MORE_DEVICE          = 66    # 0x0042
    ERROR_TIMEOUT              = 67    # 0x0043
    ERROR_VERIFY               = 68    # 0x0044
    # management connections
    MC_INDIVIDUAL              = 73    # 0x0049
    MC_CONNECTION              = 80    # 0x0050
    MC_READ                    = 81    # 0x0051
    MC_WRITE                   = 82    # 0x0052
    MC_PROP_READ               = 83    # 0x0053
    MC_PROP_WRITE              = 84    # 0x0054
    MC_PEI_TYPE                = 85    # 0x0055
    MC_ADC_READ                = 86    # 0x0056
    MC_AUTHORIZE               = 87    # 0x0057
    MC_KEY_WRITE               = 88    # 0x0058
    MC_MASK_VERSION            = 89    # 0x0059
    MC_RESTART                 = 90    # 0x005a
    MC_WRITE_NOVERIFY          = 91    # 0x005b
    MC_PROG_MODE               = 98    # 0x0060
    MC_PROP_DESC               = 99    # 0x0061
    MC_PROP_SCAN               = 100   # 0x0062
    LOAD_IMAGE                 = 101   # 0x0063

    # cache related
    CACHE_ENABLE               = 112   # 0x0070
    CACHE_DISABLE              = 113   # 0x0071
    CACHE_CLEAR                = 114   # 0x0072
    CACHE_REMOVE               = 115   # 0x0073
    CACHE_READ                 = 116   # 0x0074
    CACHE_READ_NOWAIT          = 117   # 0x0075
    CACHE_LAST_UPDATES         = 118   # 0x0076
    CACHE_LAST_UPDATES_2       = 119   # 0x0077    

    MessageDescriptions = {
        0  : 'INVALID_REQUEST',
        1  : 'CONNECTION_INUSE',
        2  : 'PROCESSING_ERROR',
        3  : 'CLOSED',
        4  : 'RESET_CONNECTION',
        16 : 'OPEN_BUSMONITOR',
        17 : 'OPEN_BUSMONITOR_TEXT',
        18 : 'OPEN_VBUSMONITOR',
        19 : 'OPEN_VBUSMONITOR_TEXT',
        20 : 'BUSMONITOR_PACKET',
        21 : 'BUSMONITOR_PACKET_TS',
        22 : 'OPEN_BUSMONITOR_TS',
        23 : 'OPEN_VBUSMONITOR_TS',
        32 : 'OPEN_T_CONNECTION',
        33 : 'OPEN_T_INDIVIDUAL',
        34 : 'OPEN_T_GROUP',
        35 : 'OPEN_T_BROADCAST',
        36 : 'OPEN_T_TPDU',
        37 : 'APDU_PACKET',
        38 : 'OPEN_GROUPCON',
        39 : 'GROUP_PACKET',
        48 : 'PROG_MODE',
        49 : 'MASK_VERSION',
        50 : 'M_INDIVIDUAL_ADDRESS_READ',
        64 : 'M_INDIVIDUAL_ADDRESS_WRITE',
        65 : 'ERROR_ADDR_EXISTS',
        66 : 'ERROR_MORE_DEVICE',
        67 : 'ERROR_TIMEOUT',
        68 : 'ERROR_VERIFY',
        73 : 'MC_INDIVIDUAL',
        80 : 'MC_CONNECTION',
        81 : 'MC_READ',
        82 : 'MC_WRITE',
        83 : 'MC_PROP_READ',
        84 : 'MC_PROP_WRITE',
        85 : 'MC_PEI_TYPE',
        86 : 'MC_ADC_READ',
        87 : 'MC_AUTHORIZE',
        88 : 'MC_KEY_WRITE',
        89 : 'MC_MASK_VERSION',
        90 : 'MC_RESTART',
        91 : 'MC_WRITE_NOVERIFY',
        98 : 'MC_PROG_MODE',
        99 : 'MC_PROP_DESC',
        100: 'MC_PROP_SCAN',
        101: 'LOAD_IMAGE',
        112: 'CACHE_ENABLE',
        113: 'CACHE_DISABLE',
        114: 'CACHE_CLEAR',
        115: 'CACHE_REMOVE',
        116: 'CACHE_READ',
        117: 'CACHE_READ_NOWAIT',
        118: 'CACHE_LAST_UPDATES',
        119: 'CACHE_LAST_UPDATES_2',
    }