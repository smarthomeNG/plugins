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

import copy
import logging
import re
import os
import datetime
import functools
import time
import threading

import lib.db

from lib.shtime import Shtime
from lib.item import Items
from lib.utils import Utils

from lib.model.smartplugin import SmartPlugin
from lib.module import Modules

from .buffer import BufferManager
from .constants import (
    COL_ITEM,
    COL_ITEM_ID,
    COL_ITEM_NAME,
    COL_ITEM_TIME,
    COL_ITEM_VAL_BOOL,
    COL_ITEM_VAL_NUM,
    COL_ITEM_VAL_STR,
    COL_LOG,
    COL_LOG_CHANGED,
    COL_LOG_DURATION,
    COL_LOG_TIME,
    COL_LOG_VAL_BOOL,
    COL_LOG_VAL_NUM,
    COL_LOG_VAL_STR,
    BufferEntry,
    QUALITY_NO_DATA,
    QUALITY_VALID,
)
from .store import ItemStore, LogStore
from .webif import WebInterface


class Database(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = '1.6.15'

    # SQL queries: {item} = item table name, {log} = log table name
    # time, item_id, val_str, val_num, val_bool, changed
    _setup = {
        '1': [
            'CREATE TABLE {log} (time BIGINT, item_id INTEGER, duration BIGINT, val_str TEXT, val_num REAL, val_bool BOOLEAN, changed BIGINT);',
            'DROP TABLE {log};',
        ],
        '2': [
            # id declared as INTEGER PRIMARY KEY so the DB handles auto-increment;
            # avoids the previous MAX(id)+1 race condition on multi-connection setups.
            'CREATE TABLE {item} (id INTEGER PRIMARY KEY, name varchar(255), time BIGINT, val_str TEXT, val_num REAL, val_bool BOOLEAN, changed BIGINT);',
            'DROP TABLE {item};',
        ],
        '3': ['CREATE UNIQUE INDEX {log}_{item}_id_time ON {log} (item_id, time);', 'DROP INDEX {log}_{item}_id_time;'],
        '4': [
            'CREATE INDEX {log}_{item}_id_changed ON {log} (item_id, changed);',
            'DROP INDEX {log}_{item}_id_changed;',
        ],
        '5': ['CREATE UNIQUE INDEX {item}_id ON {item} (id);', 'DROP INDEX {item}_id;'],
        '6': ['CREATE INDEX {item}_name ON {item} (name);', 'DROP INDEX {item}_name;'],
        '7': [
            # Add data-quality column to the log table.
            # 0 (default) = normal valid measurement.
            # 1 = QUALITY_NO_DATA: data source was unavailable; all val_* columns NULL.
            # Existing rows implicitly have quality=0 via the DEFAULT clause.
            'ALTER TABLE {log} ADD COLUMN val_quality TINYINT DEFAULT 0;',
            '/* val_quality column cannot be removed via ALTER TABLE on SQLite <3.35 */',
        ],
    }

    # database_maxage_action: value expressions, one scalar per compaction
    # interval. Deliberately mirrors (not DRY-shares) the fragments in
    # _single()'s `queries` dict - reusing the exact same SQL text without
    # refactoring _single()/_series() themselves, to avoid touching the
    # already-working on-demand query path while adding this feature.
    # 'diff'/'count' are intentionally left out for now ('diff' has two
    # conflicting meanings between _single/_series; parameterised 'count'
    # would need database_maxage_action to carry an expression, not just a
    # bare function name). 'first'/'last' are handled separately below
    # (_MAXAGE_EDGE_ACTIONS) - they pick a raw stored value rather than
    # computing a scalar over val_num/val_bool, so str-typed items can be
    # compacted too (nothing else here works for str).
    _MAXAGE_AGGREGATE_EXPR = {
        'avg': 'AVG(val_num * duration) / AVG(duration)',
        'sum': 'SUM(val_num)',
        'min': 'MIN(val_num)',
        'max': 'MAX(val_num)',
        'integrate': 'SUM(val_num * duration)',
        'on': 'SUM(val_bool * duration) / SUM(duration)',
        'countall': 'COUNT(*)',
    }

    # 'first'/'last': keep the oldest/newest raw value in the interval as-is
    # (via LogStore.edge_value's ORDER BY ... LIMIT 1), instead of computing
    # anything over it. Maps action name -> SQL ORDER BY direction.
    _MAXAGE_EDGE_ACTIONS = {'first': 'ASC', 'last': 'DESC'}

    # item types each database_maxage_action is valid for. None = any type.
    # Grounded in utils.encode_value(): val_num is populated for 'num' and
    # 'bool' (bool encodes as float(value)); val_bool is populated for
    # 'bool' *and* 'str' (string truthiness) - hence 'on' works for str/bool
    # but avg/sum/min/max/integrate (which read val_num) do not work for str.
    # first/last just read back whatever encode_value() already stored, so
    # they work for every type, str included.
    _MAXAGE_ACTION_VALID_TYPES = {
        'avg': ('num', 'bool'),
        'sum': ('num', 'bool'),
        'min': ('num', 'bool'),
        'max': ('num', 'bool'),
        'integrate': ('num', 'bool'),
        'on': ('bool', 'str'),
        'countall': None,
        'first': None,
        'last': None,
    }

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin or MqttPlugin)
        super().__init__()

        self.shtime = Shtime.get_instance()
        self.items = Items.get_instance()

        # parameters: driver, connect, prefix="", cycle=60, precision=2
        self.driver = self.get_parameter_value('driver')
        self._connect = self.get_parameter_value('connect')  # list of connection parameters
        self._connect = self._resolve_sqlite_database_path(self._connect)
        self._prefix = self.get_parameter_value('prefix')
        if self._prefix is None:
            self._prefix = ''
        if self._prefix != '':
            self._prefix += '_'
        self._dump_cycle = self.get_parameter_value('cycle')
        self._removeold_cycle = self.get_parameter_value('removeold_cycle')
        # Guard against None (e.g. in test environments where get_parameter_value
        # returns None), and ensure the two scheduler cycles are not identical so
        # they don't compete for the same scheduler slot.
        if self._removeold_cycle is not None and self._removeold_cycle == self._dump_cycle:
            self._removeold_cycle += 2
        self._precision = self.get_parameter_value('precision')
        self._time_precision = self.get_parameter_value('time_precision')
        self.count_logentries = self.get_parameter_value('count_logentries')
        self.max_delete_logentries = self.get_parameter_value('max_delete_logentries')
        self.max_reassign_logentries = self.get_parameter_value('max_reassign_logentries')
        self._default_maxage = float(self.get_parameter_value('default_maxage') or 0)
        self._default_maxage_action = self.get_parameter_value('default_maxage_action') or 'delete'
        self._default_maxage_interval = self.get_parameter_value('default_maxage_interval') or '24h'
        self.max_aggregate_intervals = self.get_parameter_value('max_aggregate_intervals')

        self._copy_database = self.get_parameter_value('copy_database')
        self._copy_database_name = self.get_parameter_value('copy_database_name')

        self._webdata = {}

        self._replace = {table: table if self._prefix == '' else self._prefix + table for table in ['log', 'item']}
        self._replace['item_columns'] = ', '.join(COL_ITEM)
        # val_quality column added in schema v7; include in log column list
        self._replace['log_columns'] = ', '.join(COL_LOG + ('val_quality',))
        self._buffer_mgr = BufferManager()
        self._dump_lock = threading.Lock()

        self.skipping_dump = False
        self._remove_older_skipped = False
        self.lock_remove_older = False

        self.orphanlist = []  # list with item names of orphant database entries
        self._orphan_logcount = {}  # dict to store the number of log records for an orphan
        self.remove_orphan = False  # set to True to remove orphans during remove_older
        self.delete_orphan_chunk_size = 20000  # Delete x log entries for orphan items at a time
        self._handled_items = []  # items that have a 'database' attribute set
        self._items_with_maxage = []  # items that have a 'database_maxage' attribute set
        self._maxage_worklist = []  # work copy of self._items_with_maxage
        self._item_logcount = {}  # dict to store the number of log records for an item
        self._items_total_entries = 0  # total number of log entries
        self._items_still_counting = False  # total number of log entries

        self.cleanup_active = False

        self.last_connect_time = 0  # mechanism for limiting db connection requests
        self.last_maint_connect_time = 0  # mechanism for limiting db maintenance connection requests

        # Copy SQLite3 database file (if configured)
        if self._copy_database:
            self.copy_databasefile()

        # Setup db and test if connection is possible
        self._db = lib.db.Database(
            ('' if self._prefix == '' else self._prefix.capitalize()) + 'Database', self.driver, self._connect
        )
        if not self._db.api_initialized:
            # Error initializeng the database driver (e.g.: Python module for database driver not found)
            self.logger.error('Initialization of database API failed')
            self._init_complete = False
            return

        self._item_store = ItemStore(self._db, self._replace, self.logger)
        self._log_store = LogStore(self._db, self._replace, self.logger)

        # Setup db maintenance connection and test if connection is possible
        self._db_maint = lib.db.Database(
            ('' if self._prefix == '' else self._prefix.capitalize()) + 'Database', self.driver, self._connect
        )
        if not self._db_maint.api_initialized:
            # Error initializeng the database driver (e.g.: Python module for database driver not found)
            self.logger.error('Initialization of database API failed for maintenance connection')
            self._init_complete = False
            return

        self._db_initialized = False
        self._db_maint_initialized = False
        if not self._initialize_db():
            # self._init_complete = False
            # return
            self.logger.debug('Init: DB could not be initialized')
            pass

        self.init_webinterface(WebInterface)
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug('Run method called')
        self._initialize_db()
        self.build_orphanlist(True)
        self._start_schedulers()
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug('Stop method called')
        self.alive = False
        self._stop_schedulers()
        self._dump(True)
        self._db.close()
        self._db_maint.close()

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
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
        if self.has_iattr(item.conf, 'database') and self.get_iattr_value(item.conf, 'database') not in ['no', 'false']:
            self._webdata.update({item.property.path: {}})
            self._handled_items.append(item)
            if self.has_iattr(item.conf, 'database_maxage'):
                maxage = self.get_iattr_value(item.conf, 'database_maxage')
                try:
                    maxage_valid = float(maxage) > 0
                except (TypeError, ValueError):
                    self.logger.warning(
                        f"Item {item.property.path}: database_maxage value '{maxage}' is not a number, ignoring"
                    )
                    maxage_valid = False
                if maxage_valid:
                    # if self.get_iattr_value(item.conf, 'database') == 'init':
                    #    self.logger.warning(f"Item {item.property.path} configured with database_maxage and init could lead to no values in DB for initialization.")

                    self._items_with_maxage.append(item)

            if self.has_iattr(item.conf, 'database_maxage_action'):
                action = self.get_iattr_value(item.conf, 'database_maxage_action').lower()
                valid_types = self._MAXAGE_ACTION_VALID_TYPES.get(action)
                if valid_types is not None and item.type() not in valid_types:
                    self.logger.error(
                        f"Item {item.property.path}: database_maxage_action '{action}' is not valid for "
                        f"item type '{item.type()}' (valid: {', '.join(valid_types)}) - falling back to 'delete'"
                    )

            self.logger.debug(item.conf)
            self._buffer_mgr.register(item)
            item.series = functools.partial(self._series, item=item.property.path)  # Zur Nutzung im Websocket Plugin
            item.db = functools.partial(
                self._single, item=item.property.path
            )  # Zur Nutzung ueber Funktionen in Logiken
            item.dbplugin = self  # genutzt zum Zugriff auf die Plugin Instanz z.B. durch Logiken

            # Inject db_mark_invalid / db_mark_valid so data-source plugins can
            # signal connectivity loss without changing the item's Python value.
            item.db_mark_invalid = functools.partial(self._mark_item_invalid, item)
            item.db_mark_valid = functools.partial(self._mark_item_valid, item)
            if self._db_initialized and self.get_iattr_value(item.conf, 'database').lower() == 'init':
                if not self._db.lock(5):
                    self.logger.error(
                        'Can not acquire lock for database to read value for item {}'.format(item.property.path)
                    )
                    return
                cur = self._db.cursor()
                cache = self.readItem(str(item.property.path), cur=cur)
                if cache is not None:
                    try:
                        value = self._item_value_tuple_rev(item.type(), cache[COL_ITEM_VAL_STR : COL_ITEM_VAL_BOOL + 1])
                        last_change = self._datetime(cache[COL_ITEM_TIME])
                        prev_change = self._fetchone(
                            'SELECT MAX(time) from {log} WHERE item_id = :id', {'id': cache[COL_ITEM_ID]}, cur=cur
                        )
                        if (value is not None) and (prev_change is not None) and (prev_change[0] is not None):
                            # Add item specific debugging here:
                            # if item.property.path == 'xyz':
                            #    self.logger.debug(f"Parse item: ItemID: {item.property.path}: {value}, {self._datetime(prev_change[0])}, {last_change}")
                            self._webdata[item.property.path].update({'last_change': last_change.isoformat()})
                            self._webdata[item.property.path].update({'value': value})
                            self._webdata[item.property.path].update({'type': item.property.type})
                            item.set(
                                value,
                                'Database',
                                source='DBInit',
                                prev_change=self._datetime(prev_change[0]),
                                last_change=last_change,
                            )
                        else:
                            self.logger.warning(
                                f'Debug init for item {item.property.path}: {value}, {prev_change}, {prev_change[0]}'
                            )
                        if (
                            value is not None
                            and self.get_iattr_value(item.conf, 'database_acl') is not None
                            and self.get_iattr_value(item.conf, 'database_acl').lower() == 'ro'
                        ):
                            # self.logger.debug(f"DEBUG: Parse item, doing buffer insert for ItemID: {item.property.path}: {value}, databse_acl {self.get_iattr_value(item.conf, 'database_acl').lower()}")
                            self._buffer_mgr.push(
                                item, BufferEntry(time=self._timestamp(self.shtime.now()), duration=None, value=value)
                            )
                    except Exception as e:
                        self.logger.error(
                            'Reading cache value from database for {} failed: {}'.format(item.property.path, e)
                        )
                else:
                    self.logger.notice(f'No cached value available in database for item {item.property.path}')
                cur.close()
                self._db.release()
            elif self.get_iattr_value(item.conf, 'database').lower() == 'init':
                self.logger.warning(
                    'Db not initialized. Cannot read database value for item {}'.format(item.property.path)
                )
            else:
                self._webdata[item.property.path].update({'value': item.property.value})
                self._webdata[item.property.path].update({'type': item.property.type})

            return self.update_item
        else:
            return None

    def remove_item(self, item):
        """
        Clean up plugin-internal bookkeeping for *item* before it's deleted —
        mirrors what parse_item() set up. Called by Items.remove_item() via the
        PLUGIN_REMOVE_ITEM hook (e.g. when admin-UI item editing recreates the
        item under the hood, or on an ordinary item delete).

        Flushes any pending buffered datapoints for *item* to the database
        first (_dump with finalize=True), so editing/deleting an item never
        silently drops not-yet-written log entries. Database *rows* for the
        item's path are untouched — id() looks them up by path, so a future
        recreate at the same path naturally finds and reuses the same row.
        This only clears the in-memory Item-object references the plugin
        itself holds.

        :param item: Item instance being removed
        :type item: object
        :return: True if this item had database-plugin state to clean up
        :rtype: bool
        """
        found = item.property.path in self._webdata
        if not found:
            return False

        self._dump(finalize=True, items=[item])
        self._buffer_mgr.deregister(item)

        self._webdata.pop(item.property.path, None)
        try:
            self._handled_items.remove(item)
        except ValueError:
            pass
        try:
            self._items_with_maxage.remove(item)
        except ValueError:
            pass

        return True

    def rename_item(self, item, old_path, new_path):
        """
        Re-key plugin-internal bookkeeping for an item that was renamed in
        place (same object, only its path changed — see
        Items.rename_item(), called via the PLUGIN_RENAME_ITEM hook).

        Unlike remove_item()/parse_item(), this does NOT flush/drop the
        item's data — it migrates it. ``item.db``/``item.series`` are
        functools.partial objects that capture the path as a frozen
        keyword argument at parse_item() time (see parse_item() above);
        they're refreshed here so calling them after a rename queries
        under the new path, not a stale, now-meaningless old one. The old
        path's database row is an "orphan" (no in-memory item points at
        it any more) the moment _webdata is re-keyed — reassign_orphaned_id()
        merges its log history into the new path's row and deletes it,
        rather than leaving it to be discovered later by build_orphanlist().

        :param item: The renamed item (same object, unchanged identity)
        :param old_path: The item's path before the rename
        :param new_path: The item's path after the rename
        :type old_path: str
        :type new_path: str

        :return: True if this item had database-plugin state to migrate
        :rtype: bool
        """
        if old_path not in self._webdata:
            return False

        self._webdata[new_path] = self._webdata.pop(old_path)
        item.series = functools.partial(self._series, item=new_path)
        item.db = functools.partial(self._single, item=new_path)

        old_id = self.id(old_path, create=False)
        # id()'s create=True path always inserts via item.property.path,
        # not the string it was passed — item.property.path already
        # equals new_path here (Items.rename_item() mutates the path
        # before calling this hook), so pass the item, not the string.
        new_id = self.id(item, create=True)
        if old_id is not None and old_id != new_id:
            # id(create=True) never commits its own insert (a pre-existing
            # gap — insertItem() just executes, never commits). Without an
            # explicit commit here, that uncommitted write on self._db
            # blocks reassign_orphaned_id()'s very first read, since it
            # uses the separate self._db_maint connection, and SQLite
            # allows only one writer's transaction to be open at a time.
            self._db.commit()
            self.reassign_orphaned_id(old_id, new_id)

        return True

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        # if 'xxx' in logic.conf:
        #    # self.function(logic['name'])
        #    pass
        return

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

        debug_item = False

        # Uncomment to enable item specific debugging:
        # if item.property.path.startswith('test.'):
        # if item.property.path == 'xyz':
        #    self.logger.warning(f"Debug: updateItem, ItemID: {item.property.path}: {item()}, {caller}, {dest}")
        #    debug_item = True

        # Determine if item is read/write or read-only:
        if self.has_iattr(item.conf, 'database_acl'):
            acl = self.get_iattr_value(item.conf, 'database_acl').lower()
            self.logger.debug("item '{}', database_acl = {}".format(item, acl))
        else:
            acl = 'rw'

        if acl == 'rw':
            start = self._timestamp(item.prev_change())
            end = self._timestamp(item.last_change())
            if end - start < 0:
                self.logger.warning(
                    'Negative duration clamped to 0: start: {0}, end {1}, prevChange: {2}, lastChange: {3}, item: {4}'.format(
                        start, end, item.prev_change(), item.last_change(), item
                    )
                )
                end = start  # clamp — negative duration must not be stored

            # ── Gap detection ────────────────────────────────────────────────
            # If db_mark_invalid() was called previously and the open buffer
            # entry is a no-data gap (quality=QUALITY_NO_DATA), this new valid
            # measurement implicitly re-validates the item.  We must NOT use
            # the standard step-1a duration formula here because that computes
            #   end - item.prev_change()
            # which reaches back to the last Python-value change *before* the
            # gap started, making the gap duration appear longer than it really
            # was.  Instead the gap is closed using its own start timestamp
            # (BufferManager.close_open() computes end_ts - entry's own time).
            last = self._buffer_mgr.last_entry(item)
            in_gap = last is not None and last.duration is None and last.quality == QUALITY_NO_DATA
            if in_gap:
                self._buffer_mgr.close_open(item, end)
                self.logger.info(
                    f"update_item: implicit re-validation for '{item.property.path}' "
                    f'— no-data gap closed (duration {self._seconds(end - last.time)} s)'
                )
                # Skip step 1b: there is no meaningful prev_value to record
                # during a gap period.  Go straight to step 2.
                self._buffer_mgr.push(item, BufferEntry(time=end, duration=None, value=item()))
                return

            # ── Normal path ──────────────────────────────────────────────────
            # Determine, if DB buffer has a valid open "last" value:
            has_open_valid = last is not None and last.duration is None

            if debug_item:
                self.logger.warning(f'Debug: last {last}, pending {self._buffer_mgr.pending_count(item)}')

            # Update the DB buffer:
            if has_open_valid:
                # Step 1a): Alter current value with updated duration:
                if debug_item:
                    self.logger.warning(
                        f"Debug 1a): Rewriting valid last value, start: {last.time}, duration: {end - start}, value: {last.value} to item '{item}'."
                    )
                self._buffer_mgr.set_last_duration(item, end - start)
            else:
                # Step 1b): Append new value with none duration

                # If item is configured to be initialized via database init (see database: init in item.yaml), do not update previous value if the latter qual to the regular initial_value.
                # This is because configuring database: init aims at avoiding the regular item initial value to appear inside the DB:
                if (
                    self.get_iattr_value(item.conf, 'database').lower() == 'init'
                    and item.property.prev_change_by == 'Init:Initial_Value'
                ):
                    if debug_item:
                        self.logger.warning('Debug 1b): Do not append previous value as it was set by Initial_Value')
                else:
                    if debug_item:
                        self.logger.warning(
                            f"Debug 1b): Appending prev_value: start: {start}, duration: {end - start}, prev_value: {item.prev_value()} to item '{item}'"
                        )
                    self._buffer_mgr.push(item, BufferEntry(time=start, duration=end - start, value=item.prev_value()))

            # Step 2: Add current value with duration "none" to DB buffer. This entry is "none" because the duration cannot be determined yet as it's duration has not finished
            if debug_item:
                self.logger.warning(f"Debug 2): Appending current value: start {end}, value {item()} to item '{item}'")

            self._buffer_mgr.push(item, BufferEntry(time=end, duration=None, value=item()))
        else:
            self.logger.debug("Not writing item '{}' value because database_acl = {}".format(item, acl))

    def _mark_item_invalid(self, item, caller=None, source=None):
        """Open a no-data gap in the database log for *item*.

        Call this when a data source loses connectivity.  The item's Python
        value is **not** changed; only the database log is affected.  The gap
        entry is stored with ``val_quality=QUALITY_NO_DATA`` and all value
        columns ``NULL``.  Its duration remains open until
        :meth:`_mark_item_valid` is called or a new value arrives.

        This method is injected onto every registered item as
        ``item.db_mark_invalid(caller, source)`` by :meth:`parse_item`.

        :param item:   SmartHomeNG item object.
        :param caller: Optional caller identifier (for logging).
        :param source: Optional source identifier (for logging).
        """
        start_ts = self._timestamp(self.shtime.now())
        self.logger.info(
            f"db_mark_invalid: opening no-data gap for '{item.property.path}'"
            + (f' (caller={caller})' if caller else '')
        )
        # BufferManager.push_invalid() closes any currently-open valid entry
        # and appends the open-ended no-data entry in one call.
        self._buffer_mgr.push_invalid(item, start_ts)

    def _mark_item_valid(self, item, caller=None, source=None):
        """Close an open no-data gap for *item*.

        Call this when a data source regains connectivity.  The open gap
        entry's duration is back-filled.  The next call to :meth:`update_item`
        will push a new valid value entry as usual.

        This method is injected onto every registered item as
        ``item.db_mark_valid(caller, source)`` by :meth:`parse_item`.

        :param item:   SmartHomeNG item object.
        :param caller: Optional caller identifier (for logging).
        :param source: Optional source identifier (for logging).
        """
        last = self._buffer_mgr.last_entry(item)
        if last is None or last.duration is not None or last.quality != QUALITY_NO_DATA:
            return  # no open gap — nothing to close
        end_ts = self._timestamp(self.shtime.now())
        self.logger.info(
            f"db_mark_valid: closing no-data gap for '{item.property.path}'" + (f' (caller={caller})' if caller else '')
        )
        self._buffer_mgr.close_open(item, end_ts)

    def _start_schedulers(self):
        """
        Start jobs that maintain buffer and database
        """
        if self.count_logentries:
            self.scheduler_add('Count logs', self._count_logentries, cycle=6 * 3600, prio=6)
        self.scheduler_add('Buffer dump', self._dump, cycle=self._dump_cycle, prio=5)
        if len(self._items_with_maxage) > 0:
            # self.scheduler_add('Remove old', self.remove_older_than_maxage, cycle=91, prio=6)
            self.scheduler_add('Remove old', self.remove_older_than_maxage, cycle=self._removeold_cycle, prio=7)
        return

    def _stop_schedulers(self):
        """
        Stop jobs that maintain buffer and database
        """
        if len(self._items_with_maxage) > 0:
            self.scheduler_remove('Remove old')
        self.scheduler_remove('Buffer dump')
        if self.count_logentries:
            self.scheduler_remove('Count logs')
        return

    # ------------------------------------------------------
    #    Database specific public functions of the plugin
    # ------------------------------------------------------

    def copy_databasefile(self):
        """
        For SQLite3 databases only: Copy the databasefile before it is opened

        This can be used to make a backup or to use the copy for a VACUUM

        :return:
        """
        if not self.driver.lower() == 'sqlite3':
            self.logger.warning('Copying of database fie is only possible for SQLite3 databases')
            param_dict = {'copy_database': False}
            self.update_config_section(param_dict)
            return

        # get source and destination names
        try:
            database_name = next((s for s in self._connect if s.startswith('database:')), '')
            database_name = database_name[9:].strip()
        except Exception:
            database_name = ''

        # copy the database file
        self.logger.info(f'Starting to copy SQLite3 database file from {database_name} to {self._copy_database_name}')
        import shutil

        try:
            shutil.copy2(database_name, self._copy_database_name)
            self.logger.info('Finished copying SQLite3 database file')
        except Exception as e:
            self.logger.error(f'Error copying SQLite3 database file: {e}')

        # param_dict = {"copy_database": False}
        # self.update_config_section(param_dict)
        return

    def id(self, item, create=True, cur=None):
        """
        Returns the ID of the given item

        This is a public function of the plugin

        :param item: Item to get the ID for
        :param create: If True, the item is created within the database if it does not exist
        :param cur: A database cursor object if available (optional)

        :return: id of the item within the database
        :rtype: int | None
        """

        try:
            item_path = str(item.property.path)
        except AttributeError:
            item_path = item
        try:
            id = self.readItem(item_path, cur=cur)
        except Exception as e:
            self.logger.warning(f'id(): No id found for item {item_path} - Exception {e}')
            id = None

        if id is None and create:
            id = [self.insertItem(item.property.path, cur)]

        if (id is None) or (COL_ITEM_ID >= len(id)) or (id[COL_ITEM_ID] is None):
            return None
        return int(id[COL_ITEM_ID])

    def db_itemtype(self, item):
        """
        Returns the itemtype of the given item, determined from the item-table of the database

        This is a public function of the plugin

        :param item: Item to get the ID for

        :return: id of the item within the database
        :rtype: int | None
        """

        try:
            item_path = str(item.property.path)
        except AttributeError:
            item_path = item
        try:
            row = self.readItem(item_path, cur=None)
        except Exception as e:
            self.logger.warning(f'db_itemtype: No id found for item {item_path} - Exception {e}')
            row = None

        if (row is None) or (COL_ITEM_ID >= len(row)):
            return None

        strval = row[COL_ITEM_VAL_STR]
        numval = row[COL_ITEM_VAL_NUM]
        boolval = row[COL_ITEM_VAL_BOOL]

        if (strval is not None) and (numval is None):
            return 'str'

        if (strval is None) and (numval is not None):
            if float(numval) != int(boolval):
                return 'num'
            return 'num, bool'

        return 'unbekannt'

    def db_lastchange(self, item):
        """
        Returns the itemtype of the given item, determined from the item-table of the database

        This is a public function of the plugin

        :param item: Item to get the ID for

        :return: id of the item within the database
        :rtype: int | None
        """

        try:
            item_path = str(item.property.path)
        except AttributeError:
            item_path = item
        try:
            row = self.readItem(item_path, cur=None)
        except Exception as e:
            self.logger.warning(f'db_lastchange: No id found for item {item_path} - Exception {e}')
            row = None

        if (row is None) or (COL_ITEM_ID >= len(row)):
            return None

        last_change = row[COL_ITEM_TIME]
        if last_change is None:
            return None
        return self._datetime(last_change)

    def db(self):
        """
        Returns the low-level database object

        This is a public function of the plugin

        :return: Database object
        :rtype: object
        """
        return self._db

    def dump(
        self,
        dumpfile,
        id=None,
        time=None,
        time_start=None,
        time_end=None,
        changed=None,
        changed_start=None,
        changed_end=None,
        cur=None,
    ):
        """
        Creates a database dump for given criterias in csv format

        This is a public function of the plugin

        :param dumpfile: Name of the file to dump to
        :param id: If given, item_id to restrict dump to (optional)
        :param time: If given, time to restrict dump to (optional)
        :param time_start: If given, start time to restrict dump to (optional)
        :param time_end: If given, end time to restrict dump to (optional)
        :param changed: Restrict dump to given time of change (optional)
        :param changed_start: Restrict dump to given start time of changes (optional)
        :param changed_end: Restrict dump to given end time of changes (optional)
        :param cur: A database cursor object if available (optional)
        """
        self.logger.info('Starting file dump to {} ...'.format(dumpfile))

        item_ids = self.readItems(cur=cur) if id is None else [self.readItem(id, cur=cur)]

        s = ';'
        h = [
            'item_id',
            'item_name',
            'time',
            'duration',
            'val_str',
            'val_num',
            'val_bool',
            'changed',
            'time_date',
            'changed_date',
        ]
        f = open(dumpfile, 'w')
        f.write(s.join(h) + '\n')
        for item in item_ids:
            self.logger.debug('... dumping item {}/{}'.format(item[1], item[0]))

            rows = self.readLogs(
                item[0],
                time=time,
                time_start=time_start,
                time_end=time_end,
                changed=changed,
                changed_start=changed_start,
                changed_end=changed_end,
                cur=cur,
            )

            for row in rows:
                cols = []
                for key in [COL_ITEM_ID, COL_ITEM_NAME]:
                    cols.append(item[key])
                for key in [
                    COL_LOG_TIME,
                    COL_LOG_DURATION,
                    COL_LOG_VAL_STR,
                    COL_LOG_VAL_NUM,
                    COL_LOG_VAL_BOOL,
                    COL_LOG_CHANGED,
                ]:
                    cols.append(row[key])
                for key in [COL_ITEM_ID, COL_LOG_CHANGED]:
                    cols.append('' if row[key] is None else datetime.datetime.fromtimestamp(row[key] / 1000.0))
                cols = map(lambda col: '' if col is None else col, cols)
                cols = map(lambda col: str(col) if '"' not in str(col) else col.replace('"', '\\"'), cols)
                f.write(s.join(cols) + '\n')
        f.close()
        self.logger.info('File dump completed ({} items) ...'.format(len(item_ids)))
        return

    def sqlite_dump(self, dumpfile):

        if self.driver.lower() != 'sqlite3':
            self.logger.warning('SQL dump is only possible for sqlite3 databases')
            return False

        self.logger.info(f'Starting SQL file dump of the sqlite3 database to {dumpfile} ...')

        with open(dumpfile, 'w') as f:
            for line in self._db._conn.iterdump():
                f.write(f'{line}\n')

        self.logger.info('SQL file dump of sqlite3 database completed')
        return True

    def insertItem(self, name, cur=None):
        """
        Create database item record for given item name.

        Uses the cursor's own ``lastrowid`` right after the INSERT rather
        than a follow-up ``SELECT id ... WHERE name=:name``. The database
        connection is shared across threads (``check_same_thread:0``), so a
        concurrent caller (e.g. a websocket admin series request running on
        another thread) could interleave between the INSERT and that
        lookup and cause it to miss, leaving the item permanently id-less.
        ``lastrowid`` is scoped to this cursor and immune to that race.

        This is a public function of the plugin.

        :param name: Full item path to create a record for.
        :param cur:  Optional cursor for transaction batching.
        :return:     The new integer item ID.
        :rtype:      int
        """
        return self._item_store.insert(name, cur=cur)

    def updateItem(self, id, time, duration=0, val=None, it=None, changed=None, cur=None):
        """
        Update database item record for given database ID

        This is a public function of the plugin

        :param id: Id of the item within the database
        :param time: Time for the given value
        :param duration: Time duration for the given value
        :param val: The value to write to the database
        :param it: The item type of the value ('str', 'num', 'bool')
        :param changed: Time of change
        :param cur: A database cursor object if available (optional)
        """
        self._item_store.update(id, time, val, it, changed, cur=cur)

    def readItem(self, id, cur=None):
        """

        This is a public function of the plugin

        :param id: Id of the item within the database
        :param cur: A database cursor object if available (optional)

        :return: Data for the selected item
        """
        return self._item_store.find(id, cur=cur)

    def readItems(self, cur=None):
        """
        Read database item records

        This is a public function of the plugin

        :param cur: A database cursor object if available (optional)

        :return: selected items
        """
        return self._item_store.find_all(cur=cur)

    def readItemCount(self, cur=None):
        """
        Read database log count for given database ID

        This is a public function of the plugin

        :param cur: A database cursor object if available (optional)

        :return: Number of log records for the database ID
        """
        return self._item_store.count(cur=cur)

    def deleteItem(self, id, cur=None):
        """
        Delete database item record for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to delete the record for
        :param cur: A database cursor object if available (optional)
        """
        self._item_store.delete(id, cur=cur)

    def insertLog(self, id, time, duration=0, val=None, it=None, changed=None, cur=None, quality=QUALITY_VALID):
        """
        Create database log record for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to create a record for
        :param time: Time for the given value
        :param duration: Time duration for the given value
        :param val: The value to write to the database
        :param it: The item type of the value ('str', 'num', 'bool')
        :param changed: Time of change
        :param cur: A database cursor object if available (optional)
        :param quality: Data-quality flag (QUALITY_VALID by default, QUALITY_NO_DATA for a gap row)
        """
        entry = BufferEntry(time=time, duration=duration, value=val, quality=quality)
        self._log_store.insert(id, entry, it, changed, cur=cur)

    def updateLog(self, id, time, duration=0, val=None, it=None, changed=None, cur=None, quality=QUALITY_VALID):
        """
        Update database log record for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to update the record for
        :param time: Time for the given value
        :param duration: Time duration for the given value
        :param val: The value to write to the database
        :param it: The item type of the value ('str', 'num', 'bool')
        :param changed: Time of change
        :param cur: A database cursor object if available (optional)
        :param quality: Data-quality flag (QUALITY_VALID by default, QUALITY_NO_DATA for a gap row)
        """
        entry = BufferEntry(time=time, duration=duration, value=val, quality=quality)
        self._log_store.update(id, entry, it, changed, cur=cur)

    def readLog(self, id, time, cur=None):
        """
        Read database log record for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to read the record for
        :param time: Time for the given value
        :param cur: A database cursor object if available (optional)

        :return: Log record for the database ID
        """
        return self._log_store.find(id, time, cur=cur)

    def readLogs(
        self,
        id,
        time=None,
        time_start=None,
        time_end=None,
        changed=None,
        changed_start=None,
        changed_end=None,
        cur=None,
    ):
        """
        Read database log records for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to read the records for
        :param time: Restrict reading of records to given time (optional)
        :param time_start: Restrict reading of records to given start time (optional)
        :param time_end: Restrict reading of records to given end time (optional)
        :param changed: Restrict reading of records to given change time (optional)
        :param changed_start: Restrict reading of records to given start time of changes (optional)
        :param changed_end: Restrict reading of records to given end time of changes (optional)
        :param cur: A database cursor object if available (optional)

        :return: log records
        """
        return self._log_store.find_range(
            id,
            time=time,
            time_start=time_start,
            time_end=time_end,
            changed=changed,
            changed_start=changed_start,
            changed_end=changed_end,
            cur=cur,
        )

    def readOldestLog(self, id, cur=None):
        """
        Read the time of oldest log record for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to read the record for
        :param cur: A database cursor object if available (optional)

        :return: Time of oldest log record for the database ID
        """
        return self._log_store.oldest_time(id, cur=cur)

    def readLatestLog(self, id, time=None, cur=None):
        """
        Read the time of latest log record for given database ID and if time given up to this time

        This is a public function of the plugin

        :param id: Database ID of item to read the record for
        :param time: a maximum timestamp for the given value
        :param cur: A database cursor object if available (optional)

        :return: Log record for the database ID
        """
        return self._log_store.latest_time(id, before=time, cur=cur)

    def readTotalLogCount(self, cur=None):
        """
        Return the total number of log rows across all items.

        Previously accepted ``id``, ``time_start``, ``time_end`` parameters
        that were silently ignored; the signature is corrected here.

        This is a public function of the plugin.

        :param cur: Optional cursor.
        :return:    Total log row count.
        :rtype:     int
        """
        return self._log_store.count_all(cur=cur)

    def readLogCount(self, id, time_start=None, time_end=None, cur=None):
        """
        Read database log count for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to read the record for
        :param cur: A database cursor object if available (optional)

        :return: Number of log records for the database ID
        """
        params = {'id': id, 'time_start': time_start, 'time_end': time_end}
        if time_start is None and time_end is None:
            result = self._fetchall('SELECT count(*) FROM {log} WHERE item_id = :id;', params, cur=cur)
        elif time_start is None:
            result = self._fetchall(
                'SELECT count(*) FROM {log} WHERE item_id = :id AND time <= :time_end;', params, cur=cur
            )
        elif time_end is None:
            result = self._fetchall(
                'SELECT count(*) FROM {log} WHERE item_id = :id AND time >= :time_start;', params, cur=cur
            )
        else:
            result = self._fetchall(
                'SELECT count(*) FROM {log} WHERE item_id = :id AND time >= :time_start AND time <= :time_end;',
                params,
                cur=cur,
            )
        if result == []:
            return 0
        if result is None:
            return 0
        try:
            return result[0][0]
        except Exception as e:
            self.logger.error('readLogCount: result={} - Exception: {}'.format(result, e))
        return 0

    def deleteLog(
        self,
        id,
        time=None,
        time_start=None,
        time_end=None,
        changed=None,
        changed_start=None,
        changed_end=None,
        cur=None,
        with_commit=True,
    ):
        """
        Delete database log records for given item (database ID)

        This is a public function of the plugin

        :param id: Database ID of item to delete the records for
        :param time: Restrict deletion of records to given time (optional)
        :param time_start: Restrict deletion of records to given start time (optional)
        :param time_end: Restrict deletion of records to given end time (optional)
        :param changed: Restrict deletion of records to given change time (optional)
        :param changed_start: Restrict deletion of records to given start time of changes (optional)
        :param changed_end: Restrict deletion of records to given end time of changes (optional)
        :param cur: A database cursor object if available (optional)
        :return:
        """
        self._log_store.delete_range(
            id,
            time=time,
            time_start=time_start,
            time_end=time_end,
            changed=changed,
            changed_start=changed_start,
            changed_end=changed_end,
            cur=cur,
            commit=with_commit,
        )

        try:
            self._item_logcount[id] = self.readLogCount(id)
        except Exception as e:
            self.logger.error('Exception in function deleteLog during readLogCount: {}'.format(e))

        return

    def build_orphanlist(self, log_activity=False):
        """
        Create a list of database entries which have no corresponding item in the item tree

        called by run() once on start

        :return:
        """
        if log_activity:
            self.logger.info('build_orphan_list: Started')
        self.orphanitemlist = []
        self.orphanlist = []

        items = [item.property.path for item in self._buffer_mgr.items()]
        try:
            cur = self._db_maint.cursor()
        except Exception as e:
            self.logger.error('Database build_orphan_list failed obtaining cursor: {}'.format(e))
        else:
            try:
                return_list = self.readItems(cur=cur)
                if return_list:
                    for item in return_list:
                        if item[COL_ITEM_NAME] not in items:
                            if log_activity:
                                self.logger.info(f'- Found data for item w/o database attribute: {item[COL_ITEM_NAME]}')
                            self.orphanitemlist.append(item)
                            self.orphanlist.append(item[COL_ITEM_NAME])
            except Exception as e:
                self.logger.error('Database build_orphan_list failed: {}'.format(e))

            try:
                if cur:
                    cur.close()
            except Exception as e:
                self.logger.error('Database build_orphan_list failed closing cursor: {}'.format(e))

        self._count_orphanlogentries()
        if log_activity:
            self.logger.info('build_orphan_list: Finished')

        return

    def _count_orphanlogentries(self):
        """
        count number of log entries for all items in database

        to be called by eval syntax checker
        """
        self.logger.info('_count_orphanlogentries: # orphan items = {}'.format(len(self.orphanlist)))
        self._items_total_entries = 0
        for item in self.orphanlist:
            item_id = self.id(item, create=False)
            if item_id is None:
                self.logger.warning(f'_count_orphanlogentries: No valid id found for orphan item {item} - skipping')
                continue
            logcount = self.readLogCount(item_id)
            logcount_str = f'{logcount:,}'.replace(',', '.')
            self.logger.info(f'Orphan {item} (id={item_id}): {logcount_str} entries')
            self._orphan_logcount[item_id] = logcount

        return

    def reassign_orphaned_id(self, orphan_id, to):
        """
        Reassign values from orphaned item ID to given item ID

        :param orphan_id: item id of the orphaned item
        :param to: item id of the target item
        :type orphan_id: int
        :type to: int
        """
        log_info = self.logger.info  # warning  # info
        log_debug = self.logger.debug  # error  # debug
        try:
            log_info(f'reassigning orphaned data from (old) id {orphan_id} to (new) id {to}')
            cur = self._db_maint.cursor()
            count = self.readLogCount(orphan_id, cur=cur)
            log_debug(f'found {count} entries to reassign, reassigning {self.max_reassign_logentries} at once')

            while count > 0:
                log_debug(f'reassigning {min(count, self.max_reassign_logentries)} log entries')
                self._execute(
                    self._prepare(
                        'UPDATE {log} SET item_id = :newid WHERE rowid IN '
                        '(SELECT rowid FROM {log} WHERE item_id = :orphanid LIMIT :limit);'
                    ),
                    {'newid': to, 'orphanid': orphan_id, 'limit': self.max_reassign_logentries},
                    cur=cur,
                )
                count -= self.max_reassign_logentries

            self._execute(self._prepare('DELETE FROM {item} WHERE id = :orphanid;'), {'orphanid': orphan_id}, cur=cur)
            log_info(f'reassigned orphaned id {orphan_id} to new id {to}')
            cur.close()
            self._db_maint.commit()
            log_debug('rebuilding orphan list')
            self.build_orphanlist()
        except Exception as e:
            self.logger.error(f'error on reassigning id {orphan_id} to {to}: {e}')
            return e

    def _delete_orphan(self, item_path):
        """
        Delete orphan item or logentries it

        :param item_path: path_name of the (orphan) item to work on
        :param limit: Maximum log entries to delete

        :return: True, if item was deleted; False if only logentries were deleted
        """
        item_id = self.id(item_path, create=False)
        logcount = self.readLogCount(item_id)
        if logcount == 0:
            self.logger.info(f'_delete_orphan: Item {item_path} has no log entries')
            cur = self._db_maint.cursor()
            try:
                self._execute(self._prepare('DELETE FROM {item} WHERE id = :id;'), {'id': item_id}, cur=cur)
            finally:
                if cur is not None:
                    cur.close()
            self.logger.info(f'_delete_orphan: Deleted item entry for {item_path}')
            self._db_maint.commit()
            return True

        cur = self._db_maint.cursor()
        try:
            self._execute(
                self._prepare('DELETE FROM {log} WHERE item_id = :id LIMIT :maxrecords;'),
                {'id': item_id, 'maxrecords': self.delete_orphan_chunk_size},
                cur=cur,
            )
        finally:
            if cur is not None:
                cur.close()
        delete_orphan_chunk_size_str = f'{self.delete_orphan_chunk_size:,}'.replace(',', '.')
        self.logger.info(
            f'_delete_orphan: Deleted (up to) {delete_orphan_chunk_size_str} log entries for Item {item_path}'
        )
        self._db_maint.commit()

        return False

    def remove_orphan_items(self):
        """
        Delete item and logdata of items that have no correspondance in itemtree
        """
        if len(self.orphanlist) == 0:
            self.build_orphanlist()

        item = self.orphanlist.pop(0)
        try:
            deleted = self._delete_orphan(item)
        except Exception as e:
            # e.g. the maintenance connection (_db_maint) went stale independently
            # of the main connection (see smarthomeNG/plugins#1004) - keep the item
            # queued and retry on the next cycle instead of crashing the scheduler task.
            self.logger.warning(f'remove_orphan_items: Deletion of orphan {item} failed, will retry: {e}')
            self.orphanlist.append(item)
            return

        if not deleted:
            self.orphanlist.append(item)

        if len(self.orphanlist) == 0:
            self.remove_orphan = False
            self.logger.info('remove_orphan_items: Database cleanup finished')

        return

    def cleanup(self):
        """
        Cleanup database
        deletes item/log records in the database if the corresponding item does not exist any more

        This is a public function of the plugin

        :return:
        """
        self.remove_orphan = True
        self.cleanup_active = True
        self.logger.info('Database cleanup started (removal of entries without defined item)')
        return

    # ------------------------------------------------------
    #    Database specific stuff to support websocket/visu
    # ------------------------------------------------------

    def _series(self, func, start, end='now', count=100, ratio=1, update=False, step=None, sid=None, item=None):
        """
        This method is called (via the item object) from the websocket plugin,
        when a data series for an item is requested for the visu

        It returns the data structure in the form needed by the websocket plugin to directly
        return it to the visu

        :param func:
        :param start:
        :param end:
        :param count:
        :param ratio:
        :param update:
        :param step:
        :param sid:
        :param item:

        :return: data structure in the form needed by the websocket plugin return it to the visu
        """
        # self.logger.debug("_series: item={}, func={}, start={}, end={}, count={}".format(item, func, start, end, count))
        init = not update
        if sid is None:
            sid = item + '|' + func + '|' + str(start) + '|' + str(end) + '|' + str(count)
        func, expression = self._expression(func)
        queries = {
            'avg': self._time_precision_query('MIN(time)')
            + ', '
            + self._precision_query('AVG(val_num * duration) / AVG(duration)'),
            'avg.order': 'ORDER BY time ASC',
            'integrate': self._time_precision_query('MIN(time)') + ', SUM(val_num * duration)',
            'diff': self._time_precision_query('MIN(time)') + ', (val_num - LAG(val_num,1) OVER (ORDER BY val_num))',
            'duration': self._time_precision_query('MIN(time)') + ', duration',
            # differentiate (d/dt) is scaled to match the conversion from d/dt (kWh) = kWh: time is in ms, val_num in kWh, therefore scale by 1000ms and 3600s/h to obtain the result in kW:
            'differentiate': self._time_precision_query('MIN(time)')
            + ', (val_num - LAG(val_num,1) OVER (ORDER BY val_num)) / ( (time - LAG(time,1) OVER (ORDER BY val_num)) / (3600 * 1000) )',
            'count': self._time_precision_query('MIN(time)')
            + ', SUM(CASE WHEN val_num{op}{value} THEN 1 ELSE 0 END)'.format(**expression['params']),
            'countall': self._time_precision_query('MIN(time)') + ', COUNT(*)',
            'min': self._time_precision_query('MIN(time)') + ', MIN(val_num)',
            'max': self._time_precision_query('MIN(time)') + ', MAX(val_num)',
            'on': self._time_precision_query('MIN(time)')
            + ', '
            + self._precision_query('SUM(val_bool * duration) / SUM(duration)'),
            'on.order': 'ORDER BY time ASC',
            'sum': self._time_precision_query('MIN(time)') + ', SUM(val_num)',
            'raw': self._time_precision_query('time') + ', val_num',
            'raw.order': 'ORDER BY time ASC',
            'raw.group': '',
        }
        if func not in queries:
            raise NotImplementedError

        order = '' if func + '.order' not in queries else queries[func + '.order']
        group = 'GROUP BY ROUND(time / :step)' if func + '.group' not in queries else queries[func + '.group']
        logs = self._fetch_log(item, queries[func], start, end, step=step, count=count, group=group, order=order)
        tuples = logs['tuples']

        # Append tuples by addition values (not for func differentiate)
        if func != 'differentiate':
            if tuples:
                if logs['istart'] > tuples[0][0]:
                    tuples[0] = (logs['istart'], tuples[0][1])
                if end != 'now':
                    tuples.append((logs['iend'], tuples[-1][1]))
            else:
                tuples = []
            item_change = self._timestamp(logs['item'].last_change())
            if item_change < logs['iend']:
                value = float(logs['item']())
                if item_change < logs['istart']:
                    tuples.append((logs['istart'], value))
                elif init:
                    tuples.append((item_change, value))
                if init:
                    tuples.append((logs['iend'], value))

        if expression['finalizer']:
            tuples = self._finalize(expression['finalizer'], tuples)

        result = {
            'cmd': 'series',
            'series': tuples,
            'sid': sid,
            'params': {
                'update': True,
                'item': item,
                'func': func,
                'start': logs['iend'],
                'end': end,
                'step': logs['step'],
                'sid': sid,
            },
            'update': self.shtime.now() + datetime.timedelta(seconds=int(logs['step'] / 1000)),
        }
        self.logger.dbgmed(
            f'_series: {sid=}, {step=}, update={result["update"]}, delta={int(logs["step"] / 1000)}, now={self.shtime.now()}'
        )
        # self.logger.debug("_series: result={}".format(result))

        return result

    def _single(self, func, start, end='now', item=None):
        """
        This function is not used by any other plugin but can be used in logics

        :param func:
        :param start:
        :param end:
        :param item:
        :return:
        """
        func, expression = self._expression(func)
        queries = {
            'avg': self._precision_query('AVG(val_num * duration) / AVG(duration)'),
            'integrate': 'SUM(val_num * duration)',
            'count': 'SUM(CASE WHEN val_num{op}{value} THEN 1 ELSE 0 END)'.format(**expression['params']),
            'countall': 'COUNT(*)',
            'min': 'MIN(val_num)',
            'max': 'MAX(val_num)',
            'diff': 'MAX(val_num) - MIN(val_num)',
            'on': self._precision_query('SUM(val_bool * duration) / SUM(duration)'),
            'sum': 'SUM(val_num)',
            'raw': 'val_num',
            'raw.order': 'ORDER BY time DESC',
            'raw.group': '',
        }
        if func not in queries:
            self.logger.warning('Unknown export function: {0}'.format(func))
            return
        order = '' if func + '.order' not in queries else queries[func + '.order']
        logs = self._fetch_log(item, queries[func], start, end, order=order)
        if logs['tuples'] is None:
            return
        return logs['tuples'][0][0]

    def _expression(self, func):
        expression = {'params': {'op': '!=', 'value': '0'}, 'finalizer': None}
        if ':' in func:
            expression['finalizer'] = func[: func.index(':')]
            func = func[func.index(':') + 1 :]
        if func == 'count' or func.startswith('count'):
            parts = re.match(r'(count)((<>|!=|<|=|>)(\d+))?', func)
            func = 'count'
            if parts and parts.group(3) is not None:
                expression['params']['op'] = parts.group(3)
            if parts and parts.group(4) is not None:
                expression['params']['value'] = parts.group(4)
        return func, expression

    def _finalize(self, func, tuples):
        if func == 'diff':
            final_tuples = []
            for i in range(1, len(tuples) - 1):
                final_tuples.append((tuples[i][0], tuples[i][1] - tuples[i - 1][1]))
            return final_tuples
        else:
            return tuples

    def _precision_query(self, query):
        if self._precision >= 0:
            return 'ROUND({}, {})'.format(query, self._precision)
        return query

    def _time_precision_query(self, query):
        if self._time_precision < 3:
            return 'ROUND({}, {})'.format(query, self._time_precision - 3)
        return query

    def _fetch_log(self, item, columns, start, end, step=None, count=100, group='', order=''):
        _item = self.items.return_item(item)

        istart = self._parse_ts(start)
        iend = self._parse_ts(end)
        inow = self._parse_ts('now')
        id = self.id(_item, create=False)

        if inow > iend:
            inow = iend

        if step is None:
            if count != 0:
                step = int((iend - istart) / int(count))
            else:
                step = iend - istart

        if self._buffer_mgr.pending_count(_item):
            self._dump(items=[_item])

        params = {'id': id, 'time_start': istart, 'time_end': iend, 'inow': inow, 'step': step}
        duration_now = 'COALESCE(duration, :inow - time)'

        # Duration calculation (S=Start, E=End):
        duration = (
            '('
            #    ----------|<--------------------------->|---------->
            # 1. Duration for items within the given start/end range
            #    -----------------[S]======[E]---------------------->
            'COALESCE(duration * (time >= :time_start) * (time + duration <= :time_end), 0) + '
            # 2. Duration for items partially before start but ends after start
            #    -----[S]======[E]---------------------------------->
            'COALESCE(duration / duration * (time + duration - :time_start) * (time < :time_start) * (time + duration >= :time_start), 0) + '
            #    ----------------------------------[S]======[E]----->
            # 3. Duration for items partially after end but starts before end
            'COALESCE(duration_now / duration_now * (:time_end - time) * (time + duration_now >= :time_end), 0)'
            ')'
        )

        # Replace duration fields with calculated durations from previous
        # generated expressions to include all three cases.
        columns = columns.replace('duration', duration)

        # Create base query including the replaced columns
        # val_quality != 0 rows (no-data gaps) are excluded entirely - not
        # just their value (NULL propagation already skips that in e.g.
        # AVG(val_num*duration)) but their duration too, since otherwise a
        # gap's duration would still count in a denominator like
        # AVG(duration) while its value silently drops out of the
        # numerator, skewing the result instead of the gap contributing
        # nothing as intended.
        query = (
            'SELECT ' + columns + ' FROM {log} WHERE '
            'item_id = :id AND '
            '(val_quality IS NULL OR val_quality = 0) AND '
            'time >= (SELECT COALESCE(MAX(time), 0) FROM {log} WHERE item_id = :id AND time < :time_start) AND '
            'time <= :time_end AND '
            'time + duration_now > (SELECT COALESCE(MAX(time), 0) FROM {log} WHERE item_id = :id AND time < :time_start) '
            '' + group + ' ' + order
        )

        # Replace duration_now with value from start time til current time to
        # get a duration value referring to the current timestamp - if required.
        query = query.replace('duration_now', duration_now)

        logs = self._fetchall(query, params)

        return {'tuples': logs, 'item': _item, 'istart': istart, 'iend': iend, 'step': step, 'count': count}

    def _parse_ts(self, dts):
        """
        Parse a duration-timestamp in the form '1w 2y 3h 1d 39i 15s' and return the duration in seconds as
        an integer value

        :return:
        """
        ts = self._timestamp(self.shtime.now())
        try:
            return min(ts, int(dts))  # rts, if dts is an integer value, return now, if dts is a timestamp in th future
        except (TypeError, ValueError):
            pass

        duration = 0
        if isinstance(dts, str):
            if dts == 'now':
                duration = 0
            else:
                for frame in dts.split(' '):
                    if frame != 'now':
                        duration += self._parse_single(frame)

        if duration < 0:
            duration = 0

        ts = ts - int(duration)
        return ts

    def _parse_single(self, frame):
        """
        Parse one frame of a duration-timestamp to a duration (in seconds)

        :param frame:
        :return:
        """
        second = 1000
        minute = 60 * 1000
        hour = 60 * minute
        day = 24 * hour
        week = 7 * day
        month = 30 * day
        year = 365 * day

        _frames = {'s': second, 'i': minute, 'h': hour, 'd': day, 'w': week, 'm': month, 'y': year}
        try:
            return int(frame)
        except (TypeError, ValueError):
            pass
        ts = self._timestamp(self.shtime.now())
        # if frame == 'now':
        #     fac = 0
        #     frame = 0
        if frame[-1] in _frames:
            fac = _frames[frame[-1]]
            frame = frame[:-1]
        else:
            # return parameter unchaned
            return frame
        try:
            ts = int(float(frame) * fac)
        except (TypeError, ValueError):
            self.logger.warning("Database: Unknown time frame '{0}'".format(frame))
        return ts

    # --------------------------------------------------------
    #    Database buffer routines (dump, insert and remove)
    # --------------------------------------------------------

    def _dump(self, finalize=False, items=None):
        """
        Dump data to database file

        This method is periodically called by the sheduler of SmartHomeNG

        :param finalize:
        :param items:
        :return:
        """
        if not self._dump_lock.acquire(timeout=60):
            self.logger.notice(
                'Skipping dump, since an other database operation running! Data is buffered and dumped later.'
            )
            self.skipping_dump = True
            return

        self.logger.debug('Starting dump')

        if self.skipping_dump:
            self.logger.notice('Dumping buffered data from skipped dump(s).')
            self.skipping_dump = False

        if not self._initialize_db():
            self._dump_lock.release()
            return

        if items is None:
            # No item given on method call -> dump content of the buffer
            items = self._buffer_mgr.items()

        for item in items:
            entries = self._buffer_mgr.pop_all(item)

            if len(entries) or finalize:
                # Test connectivity
                if self._db.verify(5) == 0:
                    self._buffer_mgr.restore(item, entries)
                    self.logger.error('Connection not recovered, skipping dump')
                    self._dump_lock.release()
                    return

                # Can't lock, restore data
                if not self._db.lock(300):
                    self._buffer_mgr.restore(item, entries)
                    if finalize:
                        self.logger.error(
                            "Can't dump {} items due to fail to acquire lock!".format(len(self._buffer_mgr.items()))
                        )
                    else:
                        self.logger.error(
                            "Can't dump {} items due to fail to acquire lock - will try on next dump".format(
                                len(self._buffer_mgr.items())
                            )
                        )
                    self._dump_lock.release()
                    return

                #                if self.has_iattr(item.conf, 'database_acl'):
                #                    acl = self.get_iattr_value(item.conf, 'database_acl').lower()
                #                    self.logger.info("_dump: Dumping item '{}', database_acl = {}".format(item, acl))

                cur = None
                try:
                    changed = self._timestamp(self.shtime.now())

                    # Get current values of item
                    start = self._timestamp(item.last_change())
                    end = changed
                    val = item()
                    try:
                        self._webdata[item.property.path].update({'value': val})
                        self._webdata[item.property.path].update({'type': item.property.type})
                    except Exception as e:
                        self.logger.warning('Problem webdata value update {}: {}'.format(item.property.path, e))

                    # When finalizing (e.g. plugin shutdown) add current value to item and log
                    if finalize:
                        # When plugin is shutdown, by default, every registered item is rewritten into the DB no matter
                        # if it has been changed or not. This behavior is not wanted for items that are rarely updated
                        # because these database entries would lead indicate item updates that in reality aren't really there.
                        # Therefore, if item attribute database_write_on_shutdown is set to False, no double entries are written
                        # to the database and only the last entry is updated.

                        # self.logger.debug(f"DEBUG _dump: Finalizing item {item} with value {val}")
                        if not self.get_iattr_value(item.conf, 'database_write_on_shutdown'):
                            self.logger.debug(f'DEBUG _dump: Blocking rewrite to DB for item {item} with value {val}')

                            # if item.property.path == 'xyz':
                            #    self.logger.warning(f"DEBUG _dump: update debug item with start {start}, val {val}, changed {changed}")

                            _update = (start, val, changed)

                        else:
                            # Perform item update and rewrite current value to database:
                            _update = (end, val, changed)

                            entries.append(BufferEntry(time=start, duration=end - start, value=val))

                    else:
                        # only perform DB item update for regular dumps (not at plugin shutdown)
                        _update = (start, val, changed)

                    cur = self._db.cursor()
                    id = self.id(item, cur=cur)

                    # Dump entries
                    self.logger.debug('Dumping {}/{} with {} values'.format(item.property.path, id, len(entries)))

                    for entry in entries:
                        self._log_store.upsert(id, entry, item.type(), changed, cur=cur)

                    self.updateItem(id, _update[0], None, _update[1], item.type(), _update[2], cur)

                    cur.close()
                    cur = None

                    self._db.commit()
                except Exception as e:
                    self.logger.warning('Problem dumping {}: {}'.format(item.property.path, e), exc_info=True)
                    self._buffer_mgr.restore(item, entries)
                    try:
                        self._db.rollback()
                    except Exception as er:
                        self.logger.warning('Error rolling back: {}'.format(er))
                finally:
                    if cur is not None:
                        cur.close()
                self._db.release()
        self.logger.debug('Dump completed')
        self._dump_lock.release()

    # ------------------------------------------
    #    Database maintenance stuff
    # ------------------------------------------

    def _maxage_action_for(self, item):
        """
        Resolve database_maxage_action for *item*, falling back to the
        plugin-level default_maxage_action when the item doesn't set its
        own. The item attribute deliberately has no schema default in
        plugin.yaml, so has_iattr() can distinguish "unset" from
        "explicitly delete" - mirrors the existing default_maxage pattern.

        Also the single enforcement point for the type-compatibility check
        (see _MAXAGE_ACTION_VALID_TYPES): an invalid action for this item's
        type always resolves to 'delete' here, regardless of whether
        parse_item()'s startup validation ran, so a bad config can never
        reach _compact_maxage() and run e.g. SUM(val_num) against a str
        item (val_num is always NULL there).

        :param item: item to resolve the action for
        :return: one of _MAXAGE_AGGREGATE_EXPR's or _MAXAGE_EDGE_ACTIONS' keys, or 'delete'
        """
        if self.has_iattr(item.conf, 'database_maxage_action'):
            action = self.get_iattr_value(item.conf, 'database_maxage_action').lower()
        else:
            action = self._default_maxage_action

        if action == 'delete':
            return 'delete'

        known = action in self._MAXAGE_AGGREGATE_EXPR or action in self._MAXAGE_EDGE_ACTIONS
        valid_types = self._MAXAGE_ACTION_VALID_TYPES.get(action)
        if not known or (valid_types is not None and item.type() not in valid_types):
            return 'delete'
        return action

    def _maxage_interval_seconds_for(self, item):
        """
        Resolve database_maxage_interval for *item* in seconds, falling
        back to the plugin-level default_maxage_interval. Same format as
        cycle/autotimer (lib.shtime.Shtime.to_seconds) - no 'd' (days)
        suffix supported.

        :param item: item to resolve the interval for
        :return: interval in seconds (int), never 0 or negative
        """
        if self.has_iattr(item.conf, 'database_maxage_interval'):
            interval = self.get_iattr_value(item.conf, 'database_maxage_interval')
        else:
            interval = self._default_maxage_interval

        seconds = self.shtime.to_seconds(interval, test=True)
        if not seconds or seconds <= 0:
            self.logger.warning(
                f"Item {item.property.path}: invalid database_maxage_interval '{interval}', using 86400s (24h)"
            )
            return 86400
        return int(seconds)

    def _compact_maxage(self, item, item_id, itempath, time_end, action):
        """
        Compact log entries older than maxage into one aggregate value per
        database_maxage_interval, instead of deleting them (called from
        remove_older_than_maxage() instead of the delete path when *action*
        is not 'delete').

        No persisted resume cursor is kept: the next interval to compact is
        always simply the oldest remaining raw data for this item
        (self._log_store.oldest_time - a cheap MIN(time) index seek).
        Compaction always proceeds oldest-first and only deletes an
        interval's raw rows in the same transaction as writing its
        aggregate, so this is self-healing across restarts/crashes by
        construction - there is no separate state file to get out of sync.

        Bounded by self.max_aggregate_intervals per call (the aggregate-mode
        analogue of max_delete_logentries' row-count bound - one interval's
        aggregate query can still cover an arbitrary number of raw rows for
        a hot item, so the bound here is on intervals, not rows).

        :param item: the item being compacted
        :param item_id: database id of item
        :param itempath: item.property.path, for logging
        :param time_end: datetime - the maxage cutoff; only intervals
            entirely older than this are touched
        :param action: resolved database_maxage_action (already validated
            via _maxage_action_for - never 'delete' here)
        """
        edge_order = self._MAXAGE_EDGE_ACTIONS.get(action)
        expr = None if edge_order else self._MAXAGE_AGGREGATE_EXPR[action]
        interval_ms = self._maxage_interval_seconds_for(item) * 1000
        cutoff_ms = self._timestamp(time_end)
        item_type = item.type()

        intervals_done = 0
        while intervals_done < self.max_aggregate_intervals:
            oldest = self._log_store.oldest_time(item_id)
            if oldest is None:
                break  # nothing left to compact

            interval_start = (oldest // interval_ms) * interval_ms
            interval_end = interval_start + interval_ms
            if interval_end > cutoff_ms:
                break  # this interval isn't entirely past the cutoff yet - leave it raw

            if edge_order:
                # 'first'/'last': keep the actual oldest/newest raw value as-is
                # (works for str too - encode_value/decode_value round-trip it
                # via val_str, unlike the val_num-based aggregate expressions).
                edge = self._log_store.edge_value(
                    item_id, edge_order, time_start=interval_start - 1, time_end=interval_end
                )
                value = self._item_value_tuple_rev(item_type, edge) if edge else None
            else:
                value = self._log_store.aggregate(item_id, expr, time_start=interval_start - 1, time_end=interval_end)

            cur = self._db.cursor()
            try:
                # delete before insert: interval_start is derived from the
                # oldest raw row's own timestamp, so a raw row can legally
                # sit at exactly that timestamp - inserting the aggregate
                # there first would collide with the (item_id, time) unique
                # constraint. Both statements still share one transaction,
                # so a crash between them can never leave a duplicate
                # aggregate behind on the next run's self-healing resume.
                self._log_store.delete_range(
                    item_id, time_start=interval_start - 1, time_end=interval_end, cur=cur, commit=False
                )
                if value is not None:
                    now_ms = self._timestamp(self.shtime.now())
                    entry = BufferEntry(time=interval_start, duration=interval_ms, value=value, quality=QUALITY_VALID)
                    self._log_store.insert(item_id, entry, item_type, now_ms, cur=cur)
                self._db.commit()
            finally:
                cur.close()

            intervals_done += 1

        if intervals_done:
            self.logger.info(
                f"remove_older_: {itempath} compacted {intervals_done} interval(s) using action='{action}'"
            )

        # more intervals might already be past the cutoff but weren't
        # reached this cycle (max_aggregate_intervals) - requeue like the
        # delete path does. If we stopped because the next interval isn't
        # past the cutoff yet, this correctly does not requeue.
        oldest = self._log_store.oldest_time(item_id)
        if oldest is not None and oldest + interval_ms <= cutoff_ms:
            self._maxage_worklist.append(item)

    def remove_older_than_maxage(self):
        """
        Remove log entries older than maxage of an item

        Called by scheduler
        """
        if self.lock_remove_older:
            if not self._remove_older_skipped:
                self.logger.info('remove_older_than_maxage task is manually locked')
                self._remove_older_skipped = True
            return

        if not self._db.connected():
            self.logger.warning('remove_older_than_maxage skipped because db is not connected')
            return False

        # prevent creation of more than one thread
        current_thread = threading.current_thread()
        current_thread_name = current_thread.name
        for t in threading.enumerate():
            if t is current_thread:
                continue
            if t.name == current_thread_name:
                if not self._remove_older_skipped:
                    self.logger.info(
                        'remove_older_than_maxage skipped because a thread with this task is already running'
                    )
                self._remove_older_skipped = True
                return

        self._remove_older_skipped = False

        if self.remove_orphan:
            self.remove_orphan_items()

        # go to work
        if self._maxage_worklist == []:
            # Fill work list, if it is empty
            if self._default_maxage == 0:
                self._maxage_worklist = [i for i in self._items_with_maxage]
            else:
                self._maxage_worklist = [i for i in self._handled_items]
            self.logger.info(f'remove_older_: Worklist filled with {len(self._maxage_worklist)} items')

        item = self._maxage_worklist.pop(0)
        itempath = item.property.path

        item_id = None  # initialise before try so the except clause can reference it safely
        try:
            item_id = self.id(item, create=False)
        except Exception:
            if item_id is None:
                self.logger.info(f'remove_older_: no id for item {itempath}')
            else:
                self.logger.critical(f'remove_older_: no id for item {itempath}')
            return

        # it might well be that introducing database_maxage to a very old SmartHomeNG installation will try to start
        # a deletion of thousands of logentries. This might take days with SQLite if so.
        # so strategies might be
        # a) delete only records for one day
        # b) to just delete a limited number of log entries
        time_end = self.get_maxage_ts(item)
        if time_end is None:
            # no usable maxage for this item (e.g. an invalid database_maxage
            # value, already logged by get_maxage_ts) - nothing to do
            return
        timestamp_end = self._timestamp(time_end)

        maxage_action = self._maxage_action_for(item)
        if maxage_action != 'delete':
            # compaction always replaces raw rows with an aggregate row in
            # the same transaction as deleting them, so the item's log can
            # never end up empty as a side effect - the database: init
            # last-value-preservation logic below is a delete-path-only
            # concern and doesn't apply here.
            self._compact_maxage(item, item_id, itempath, time_end, maxage_action)
            logcount = self.readLogCount(item_id)
            self._item_logcount[item_id] = logcount
            self._webdata[item.property.path].update({'logcount': logcount})
            return

        # if delete would also remove the last logged value for the item then there might be no chance for
        # ``database: init`` to retrieve the latest value.
        remaining = 1
        if self.get_iattr_value(item.conf, 'database').lower() == 'init':
            # find out if there are still log entries after deletion of the logs
            remaining = self.readLogCount(
                item_id, time_start=self._timestamp(time_end + datetime.timedelta(microseconds=1))
            )
            # remaining can be larger than self._item_logcount[item_id], it depends on the rate of database updates
            # self.logger.info(f"remove_older_: {itempath} has attribute init with {self._item_logcount[item_id]} log entries and will have {remaining} log entries after deletion")

        if remaining <= 0:
            # no log entries will be there after deletion, need to go back in time for the latest logentry
            new_must_keep_timestamp = self.readLatestLog(item_id, timestamp_end)
            if new_must_keep_timestamp is None:
                return
            new_must_keep_time = self._datetime(new_must_keep_timestamp)
            self.logger.info(
                f'remove_older_: {itempath} no remaining log entry between {time_end} and now, thus can not remove log entries older than maxage, latest log is {new_must_keep_time}'
            )
            time_end = new_must_keep_time + datetime.timedelta(microseconds=-1)
            timestamp_end = self._timestamp(time_end)

        count_log_records_to_delete = self.readLogCount(item_id, time_end=self._timestamp(time_end))
        count_log_records_to_delete_str = f'{count_log_records_to_delete:,}'.replace(',', '.')
        max_delete_logentries_str = f'{self.max_delete_logentries:,}'.replace(',', '.')
        time_end_str = time_end.strftime('%d.%m.%Y - %H:%M')
        self.logger.debug(
            f'remove_older_: {itempath} remove older than {time_end_str} - {count_log_records_to_delete_str} records to delete'
        )

        # prevent to many deletions with strategy b)
        # assumption is made that logentries are evenly distributed over time
        # there will be actually be some more or less deletions than given in self.max_delete_logentries
        # since only a linear approximation over time and counts is used, but it should do the trick
        # to prevent from database lockups after setting database_maxage to old/ancient items
        if count_log_records_to_delete > self.max_delete_logentries:
            time_start_deletion = time.time()
            cur = self._db.cursor()
            self._execute(
                self._prepare('DELETE FROM {log} WHERE item_id = :id ORDER BY time ASC LIMIT :maxrecords;'),
                {'id': item_id, 'maxrecords': self.max_delete_logentries},
                cur=cur,
            )
            cur.close()
            time_used_for_deletion = time.time() - time_start_deletion
            self.logger.info(
                f'remove_older_: {itempath} deleted {max_delete_logentries_str} of {count_log_records_to_delete_str} log entries - took {time_used_for_deletion:.2f} seconds, averaging {100 * time_used_for_deletion / self.max_delete_logentries:.4f} seconds per 100 entries'
            )

            # Re-Add item to worklist, since there are more records to be deleted
            self._maxage_worklist.append(item)

        elif count_log_records_to_delete:
            time_start_deletion = time.time()
            self.deleteLog(item_id, time_end=timestamp_end, with_commit=False)
            time_used_for_deletion = time.time() - time_start_deletion
            time_end_str = time_end.strftime('%d.%m.%Y - %H:%M')
            self.logger.info(
                f'remove_older_: {itempath} deleted {count_log_records_to_delete_str} log entries until {time_end_str} took {time_used_for_deletion:.2f} seconds, averaging {100 * time_used_for_deletion / count_log_records_to_delete:.4f} seconds per 100 entries'
            )

        # update the logCount for the item
        logcount = self.readLogCount(item_id)
        self._item_logcount[item_id] = logcount
        self._webdata[item.property.path].update({'logcount': logcount})

        return

    def get_maxage_ts(self, item):
        """
        Get the actual maxage-timestamp for a given item

        :param item:

        :return:
        """
        maxage = None
        if self.has_iattr(item.conf, 'database_maxage'):
            maxage = self.get_iattr_value(item.conf, 'database_maxage')
        elif self._default_maxage > 0:
            maxage = self._default_maxage

        if maxage:
            try:
                maxage = float(maxage)
            except (TypeError, ValueError):
                self.logger.warning(
                    f"Item {item.property.path}: database_maxage value '{maxage}' is not a number, ignoring"
                )
                return None
            if maxage > 0:
                dt = self.shtime.now()
                dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                dt = dt - datetime.timedelta(maxage)
                return dt
        return None

    def _count_logentries(self):
        """
        count number of log entries for all items in database

        called by scheduler once on start
        """
        self.logger.info('_count_logentries: # handled items = {}'.format(len(self._handled_items)))
        self._items_still_counting = True
        self._items_total_entries = 0
        for item in self._handled_items:
            item_id = self.id(item, create=False)
            logcount = self.readLogCount(item_id)
            self._item_logcount[item_id] = logcount
            self._items_total_entries += logcount
            self._webdata[item.property.path].update({'logcount': logcount})
            # self._webdata[item.property.path].update({'logcount': f"{logcount:,}".replace(',', '.')})

        self._items_still_counting = False
        return

    # ------------------------------------------
    #    Database specific stuff
    # ------------------------------------------

    def _resolve_sqlite_database_path(self, connect):
        """
        Rewrite a relative sqlite ``database:<path>`` connect entry to an
        absolute path anchored at SmartHomeNG's install directory.

        lib.db.Database.connect() hands the raw connect params straight to
        ``sqlite3.connect()``, which resolves a relative path against
        ``os.getcwd()`` *at call time* — not once, at startup. The very
        first connect happens early enough that cwd is still correct, but
        a later reconnect (_initialize_db(), e.g. triggered by
        Items.rename_item()'s STOP_ON_ITEM_CHANGE pause/resume cycle
        calling run() well after startup, the only other place in the
        codebase that calls plugin.run() again post-startup) re-resolves
        the same relative string against whatever cwd happens to be at
        that later moment. A mismatch there is exactly what caused a real
        incident: SmartHomeNG interpreting the resulting "unable to open
        database file" as a fatal error and shutting itself down (see
        _initialize_db()'s sqlite3-specific self._sh.restart() call).
        Resolving to an absolute path once, here, makes the later
        reconnect immune to cwd entirely.

        Only applies to the sqlite3 driver — for other DB-API drivers
        (e.g. pymysql) the ``database`` key names a schema, not a file.
        ``:memory:`` and already-absolute paths are left untouched.

        :param connect: Raw 'connect' parameter list from plugin.yaml
        :type connect: list

        :return: connect, with a relative sqlite database path resolved
                 to an absolute one
        :rtype: list
        """
        if self.driver.lower() != 'sqlite3' or not isinstance(connect, list):
            return connect

        resolved = []
        for entry in connect:
            key, sep, value = entry.partition(':')
            if sep and key.strip() == 'database' and value not in ('', ':memory:') and not os.path.isabs(value):
                entry = f'{key}:{os.path.join(self.get_sh().get_basedir(), value)}'
            resolved.append(entry)
        return resolved

    def _initialize_db(self):
        # initialize main db connection
        try:
            if not self._db.connected():
                # limit connection requests to 20 seconds.
                current_time = time.time()
                time_delta_last_connect = current_time - self.last_connect_time
                self.logger.debug('DEBUG: delta {0}'.format(time_delta_last_connect))
                if time_delta_last_connect > 20:
                    self.last_connect_time = time.time()
                    self._db.connect()
                else:
                    self.logger.info('Database reconnect supressed: Delta time: {0}'.format(time_delta_last_connect))
                    return False

            if not self._db_initialized:
                self._db.setup(
                    {i: [self._prepare(query[0]), self._prepare(query[1])] for i, query in self._setup.items()}
                )
                self._db_initialized = True
        except Exception as e:
            if self.driver.lower() == 'sqlite3':
                self.logger.critical(f'Database: Initialization failed: {e}')
                self.logger.error(f' - connection string={self._connect}')
                self.logger.error(f' - working directory={os.getcwd()}')
                self._sh.restart('SmartHomeNG (Database plugin stalled)')
                exit(0)
            else:
                self.logger.critical(f'Database: Initialization failed: {e}')
                return False

        # initialize db maintenance connection
        try:
            if not self._db_maint.connected():
                # limit connection requests to 20 seconds.
                current_time = time.time()
                time_delta_last_maint_connect = current_time - self.last_maint_connect_time
                self.logger.debug('DEBUG: delta {0}'.format(time_delta_last_maint_connect))
                if time_delta_last_maint_connect > 20:
                    self.last_maint_connect_time = time.time()
                    self._db_maint.connect()
                else:
                    self.logger.error(
                        'Database reconnect (maintenance connection) supressed: Delta time: {0}'.format(
                            time_delta_last_maint_connect
                        )
                    )
                    return False

            if not self._db_maint_initialized:
                self._db_maint.setup(
                    {i: [self._prepare(query[0]), self._prepare(query[1])] for i, query in self._setup.items()}
                )
                self._db_maint_initialized = True
        except Exception as e:
            self.logger.critical('Database: Initialization of maintenance connection failed: {}'.format(e))
            if self.driver.lower() == 'sqlite3':
                self._sh.restart('SmartHomeNG (Database plugin stalled)')
                exit(0)
            else:
                return False

        return True

    def _prepare(self, query):
        return query.format(**self._replace)

    def _execute(self, query, params, cur=None):
        return self._query(self._db.execute, query, params, cur)

    def _fetchone(self, query, params=None, cur=None):
        tuples = self._query(self._db.fetchone, query, params or {}, cur)
        return tuples

    def _fetchall(self, query, params=None, cur=None):
        tuples = self._query(self._db.fetchall, query, params or {}, cur)
        return None if tuples is None else list(tuples)

    def _query(self, func, query, params, cur=None):
        """Execute *func* with the prepared *query* and *params*.

        Handles connection verification and lock acquisition when no explicit
        cursor is provided.  Debug logging is only evaluated when DEBUG is
        actually enabled (avoids regex + format on every call).

        :param func:   One of ``self._db.execute``, ``.fetchone``, ``.fetchall``.
        :param query:  SQL with ``{log}``/``{item}`` placeholders and ``:name`` params.
        :param params: Parameter dict.
        :param cur:    Optional cursor; if given the caller owns lock + commit.
        :returns:      Query result or ``None`` on failure.
        """
        if not self._db_initialized:  # fast-path: avoid full init check on every query
            if not self._initialize_db():
                return None
        if cur is None:
            if self._db.verify(5) == 0:
                self.logger.error('Database: Connection not recovered')
                return None
            if not self._db.lock(300):
                self.logger.error("Database: Can't query due to fail to acquire lock")
                return None
        prepared = self._prepare(query)  # prepare once
        tuples = None
        try:
            tuples = func(prepared, params, cur=cur)
        except Exception as e:
            if self.logger.isEnabledFor(logging.DEBUG):
                query_readable = re.sub(r':([a-z_]+)', r'{\1}', prepared).format(**params)
                self.logger.error('Database: Error for query {}: {}'.format(query_readable, e))
            else:
                self.logger.error('Database: Query error: {}'.format(e))
            raise e
        finally:
            if cur is None:
                self._db.release()
        if self.logger.isEnabledFor(logging.DEBUG):
            query_readable = re.sub(r':([a-z_]+)', r'{\1}', prepared).format(**params)
            self.logger.debug('Database: Fetch {}: {}'.format(query_readable, tuples))
        return tuples

    # ------------------------------------------
    #    conversion routines
    # ------------------------------------------

    def _item_value_tuple(self, item_type, item_val):
        """Convert item type and value to the three database column dict.

        Delegates to :func:`~utils.encode_value`.  When ``item_val`` is
        ``None`` (used for ``QUALITY_NO_DATA`` entries) all three columns
        are returned as ``None``.

        :param item_type: SmartHomeNG item type string.
        :param item_val:  Item value, or ``None`` for a no-data entry.
        :return:          Dict with keys ``val_str``, ``val_num``, ``val_bool``.
        :rtype:           dict
        """
        from .utils import encode_value

        return encode_value(item_type, item_val)

    def _item_value_tuple_rev(self, item_type, item_val_tuple):
        """Reconstruct an item value from the three database column tuple.

        Delegates to :func:`~utils.decode_value`.  Returns ``None`` when
        the expected column is ``NULL`` (either no value stored yet or a
        ``QUALITY_NO_DATA`` row).

        :param item_type:      SmartHomeNG item type string.
        :param item_val_tuple: Tuple of ``(val_str, val_num, val_bool)``.
        :return:               Decoded Python value, or ``None``.
        """
        from .utils import decode_value

        return decode_value(item_type, item_val_tuple[0], item_val_tuple[1], item_val_tuple[2])

    def _datetime(self, ts):
        """
        Get datetime from timestamp

        :param ts:
        :return:
        """
        return datetime.datetime.fromtimestamp(ts / 1000, self.shtime.tzinfo())

    def _timestamp(self, dt):
        """
        Get timestamp from datetime

        :param dt: datetime
        :return: integer containing a timestamp
        """
        val = int(time.mktime(dt.timetuple())) * 1000 + int(dt.microsecond / 1000)
        # self.logger.debug("Debug timestamp {0}, val {1}, epoche timestamp {2}, micrsec {3}".format(dt, val, time.mktime(dt.timetuple()), dt.microsecond) )
        return val

    def _seconds(self, ms):
        """
        Get seconds (rounded) from milliseconds

        :param dt:
        :return:
        """
        if ms:
            return round(ms / 1000, 1)
        else:
            return ms

    def _len(self, lst):
        return len(lst)
