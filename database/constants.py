#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
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

from typing import NamedTuple

# ──────────────────────────────────────────────────────────────────────────────
# Item table  ({prefix}item)
# Stores the *latest* value of every tracked item.
# ──────────────────────────────────────────────────────────────────────────────
COL_ITEM = ('id', 'name', 'time', 'val_str', 'val_num', 'val_bool', 'changed')
COL_ITEM_ID = 0
COL_ITEM_NAME = 1
COL_ITEM_TIME = 2
COL_ITEM_VAL_STR = 3
COL_ITEM_VAL_NUM = 4
COL_ITEM_VAL_BOL = 5  # NOTE: keep COL_ITEM_VAL_BOOL as alias for back-compat
COL_ITEM_VAL_BOOL = 5
COL_ITEM_CHANGED = 6

# ──────────────────────────────────────────────────────────────────────────────
# Log table  ({prefix}log)
# Stores every historical value together with how long it was active.
# ──────────────────────────────────────────────────────────────────────────────
COL_LOG = ('time', 'item_id', 'duration', 'val_str', 'val_num', 'val_bool', 'changed')
COL_LOG_TIME = 0
COL_LOG_ITEM_ID = 1
COL_LOG_DURATION = 2
COL_LOG_VAL_STR = 3
COL_LOG_VAL_NUM = 4
COL_LOG_VAL_BOOL = 5
COL_LOG_CHANGED = 6

# ──────────────────────────────────────────────────────────────────────────────
# Data-quality flags  (stored in the val_quality column added in schema v7)
# ──────────────────────────────────────────────────────────────────────────────
QUALITY_VALID = 0
"""Normal, measured value.  All pre-existing rows implicitly have this quality."""

QUALITY_NO_DATA = 1
"""Data source was unavailable during this period.
All val_* columns are NULL for such entries.
These rows are excluded from time-weighted aggregations (avg, sum, integrate,
on, min, max) and appear as gaps in raw/visualisation queries."""


# ──────────────────────────────────────────────────────────────────────────────
# Write buffer entry
# ──────────────────────────────────────────────────────────────────────────────
class BufferEntry(NamedTuple):
    """A single pending write for the log table, held in the in-memory buffer.

    Replaces the raw 3-tuple ``(time, duration, value)`` used previously.
    Adding `quality` as a field with a default value means all existing
    construction sites require no change (they produce quality=QUALITY_VALID
    automatically).

    :param time:     Start timestamp in milliseconds since epoch.
    :param duration: How long this value was active, in milliseconds.
                     ``None`` means the entry is still open (value currently
                     active; duration not yet known).
    :param value:    The item value.  ``None`` only when
                     ``quality == QUALITY_NO_DATA``.
    :param quality:  Data-quality flag.  ``QUALITY_VALID`` (0) for a normal
                     measurement, ``QUALITY_NO_DATA`` (1) for a gap caused by
                     source unavailability.
    """

    time: int
    duration: 'int | None'
    value: object
    quality: int = QUALITY_VALID
