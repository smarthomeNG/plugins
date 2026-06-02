#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  database plugin — pure utility functions (no class state, fully testable)
#########################################################################

"""
Utility functions for the database plugin.

All functions in this module are stateless pure functions with no
dependency on SmartHomeNG internals beyond the standard library.
They are importable and testable in complete isolation.
"""

import datetime
import time as _time

from .constants import QUALITY_NO_DATA


# ──────────────────────────────────────────────────────────────────────────────
# Value encoding / decoding
# ──────────────────────────────────────────────────────────────────────────────

def encode_value(item_type: str, value) -> dict:
    """Convert an item value to its three database column representation.

    The log and item tables store values across three columns to support
    multiple item types in a single schema:

    +----------+---------+----------+
    | col      | num/bool| str      |
    +==========+=========+==========+
    | val_str  |  NULL   | str(val) |
    +----------+---------+----------+
    | val_num  | float(v)|   NULL   |
    +----------+---------+----------+
    | val_bool | int(v)  | int(v)   |
    +----------+---------+----------+

    When ``value`` is ``None`` (used exclusively for
    :data:`~constants.QUALITY_NO_DATA` entries) all three columns are
    returned as ``None``.

    :param item_type: SmartHomeNG item type string — one of ``'num'``,
                      ``'bool'``, or any other value (treated as str).
    :param value:     The item value to encode, or ``None`` for a no-data entry.
    :returns:         Dict with keys ``val_str``, ``val_num``, ``val_bool``.
    :rtype:           dict
    """
    if value is None:
        return {'val_str': None, 'val_num': None, 'val_bool': None}

    if item_type in ('num', 'bool'):
        return {
            'val_str':  None,
            'val_num':  float(value),
            'val_bool': int(bool(value)),
        }
    # str and all other types
    return {
        'val_str':  str(value),
        'val_num':  None,
        'val_bool': int(bool(value)),
    }


def decode_value(item_type: str, val_str, val_num, val_bool):
    """Reconstruct an item value from the three database columns.

    Returns ``None`` when the expected column is ``NULL`` — which indicates
    either that no value was stored yet for this item or that the entry has
    quality :data:`~constants.QUALITY_NO_DATA`.

    :param item_type: SmartHomeNG item type (``'num'``, ``'bool'``, or str).
    :param val_str:   Value of the ``val_str`` database column.
    :param val_num:   Value of the ``val_num`` database column.
    :param val_bool:  Value of the ``val_bool`` database column.
    :returns:         The decoded Python value, or ``None``.
    """
    if item_type == 'num':
        return None if val_num is None else float(val_num)
    if item_type == 'bool':
        return None if val_bool is None else bool(int(val_bool))
    # str and others
    return None if val_str is None else str(val_str)


# ──────────────────────────────────────────────────────────────────────────────
# Timestamp conversion
# ──────────────────────────────────────────────────────────────────────────────

def to_timestamp(dt: datetime.datetime) -> int:
    """Convert a :class:`datetime.datetime` to a millisecond-epoch integer.

    All timestamps in the database are stored as milliseconds since the
    Unix epoch (UTC).

    :param dt: A timezone-aware or naive datetime object.
    :returns:  Integer milliseconds since epoch.
    :rtype:    int
    """
    return int(_time.mktime(dt.timetuple())) * 1000 + int(dt.microsecond / 1000)


def from_timestamp(ts: int, tzinfo=None) -> datetime.datetime:
    """Convert a millisecond-epoch integer back to a :class:`datetime.datetime`.

    :param ts:     Milliseconds since Unix epoch.
    :param tzinfo: Timezone to apply (e.g. ``shtime.tzinfo()``).  If ``None``
                   the system local timezone is used.
    :returns:      Corresponding datetime object.
    :rtype:        datetime.datetime
    """
    return datetime.datetime.fromtimestamp(ts / 1000, tzinfo)


# ──────────────────────────────────────────────────────────────────────────────
# SQL helpers
# ──────────────────────────────────────────────────────────────────────────────

def apply_table_names(query: str, table_names: dict) -> str:
    """Substitute ``{log}``, ``{item}`` and related placeholders in a SQL query.

    :param query:       SQL string containing ``{log}``, ``{item}``,
                        ``{log_columns}``, ``{item_columns}`` placeholders.
    :param table_names: Mapping produced by the plugin (e.g.
                        ``{'log': 'my_log', 'item': 'my_item', ...}``).
    :returns:           SQL string with all placeholders replaced.
    :rtype:             str
    """
    return query.format(**table_names)


def build_where_clause(
    item_id: int,
    *,
    time=None,
    time_start=None,
    time_end=None,
    changed=None,
    changed_start=None,
    changed_end=None,
) -> tuple:
    """Build a parameterised SQL WHERE clause from optional filter criteria.

    Replaces the previous ``_slice_condition`` flag-trick, which passed
    ``1 = :flag`` to bypass conditions when parameters were ``None``.  The
    explicit approach used here is easier to understand, and lets the query
    planner use indexes correctly.

    :param item_id:       Database item ID (always required).
    :param time:          Exact timestamp match (optional).
    :param time_start:    Inclusive lower bound on ``time`` (optional).
    :param time_end:      Inclusive upper bound on ``time`` (optional).
    :param changed:       Exact ``changed`` timestamp match (optional).
    :param changed_start: Lower bound on ``changed`` (optional).
    :param changed_end:   Upper bound on ``changed`` (optional).
    :returns:             ``(where_sql, params_dict)`` tuple ready for use in
                          a parameterised query.
    :rtype:               tuple[str, dict]
    """
    clauses = ['item_id = :item_id']
    params: dict = {'item_id': item_id}

    if time is not None:
        clauses.append('time = :time')
        params['time'] = time
    if time_start is not None:
        clauses.append('time > :time_start')
        params['time_start'] = time_start
    if time_end is not None:
        clauses.append('time < :time_end')
        params['time_end'] = time_end
    if changed is not None:
        clauses.append('changed = :changed')
        params['changed'] = changed
    if changed_start is not None:
        clauses.append('changed > :changed_start')
        params['changed_start'] = changed_start
    if changed_end is not None:
        clauses.append('changed < :changed_end')
        params['changed_end'] = changed_end

    return ' AND '.join(clauses), params
