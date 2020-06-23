#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
#  Based on ideas of sqlite plugin by Marcus Popp marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG.
#
#  database plugin to run with SmartHomeNG version 1.7 and upwards.
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

# Constants for item table
COL_ITEM = ('id', 'name', 'time', 'val_str', 'val_num', 'val_bool', 'changed')
COL_ITEM_ID = 0
COL_ITEM_NAME = 1
COL_ITEM_TIME = 2
COL_ITEM_VAL_STR = 3
COL_ITEM_VAL_NUM = 4
COL_ITEM_VAL_BOOL = 5
COL_ITEM_CHANGED = 6

# Constants for log table
COL_LOG = ('time', 'item_id', 'duration', 'val_str', 'val_num', 'val_bool', 'changed')
COL_LOG_TIME = 0
COL_LOG_ITEM_ID = 1
COL_LOG_DURATION = 2
COL_LOG_VAL_STR = 3
COL_LOG_VAL_NUM = 4
COL_LOG_VAL_BOOL = 5
COL_LOG_CHANGED = 6

