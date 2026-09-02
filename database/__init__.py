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

import csv
import decimal
import logging
import re
import os
import datetime
import functools
import time
import threading

import lib.db
from lib.db import NO_CURSOR

from lib.shtime import Shtime
from lib.item import Items

from lib.model.smartplugin import SmartPlugin

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
    QUALITY_INVALID,
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
    PLUGIN_VERSION = '1.7.0'

    # SQL queries: {item} = item table name, {log} = log table name
    # time, item_id, val_str, val_num, val_bool, changed
    @property
    def _setup(self):
        # id declared as INTEGER PRIMARY KEY so the DB handles auto-increment;
        # avoids the previous MAX(id)+1 race condition on multi-connection
        # setups. That's true as-is on SQLite (bare INTEGER PRIMARY KEY is
        # aliased to rowid, which auto-increments implicitly) but NOT on
        # MySQL/MariaDB, where it needs an explicit AUTO_INCREMENT - without
        # it, ItemStore.insert() fails with "Field 'id' doesn't have a
        # default value" under default strict SQL mode. version 2's CREATE
        # TABLE only runs for a schema that hasn't recorded it yet (fresh
        # installs); every existing MySQL/MariaDB install already has v2
        # applied without AUTO_INCREMENT, so version 8 below retrofits it
        # via ALTER TABLE - safe on a populated table, MySQL/MariaDB seeds
        # the auto-increment counter from the existing MAX(id).
        if self.driver.lower() == 'sqlite3':
            item_id_column = 'id INTEGER PRIMARY KEY'
            item_id_retrofit_autoincrement = 'SELECT 1;'  # no-op: already auto-increments
            name_widen, name_drop_index, name_recreate_index = 'SELECT 1;', 'SELECT 1;', 'SELECT 1;'
        else:
            item_id_column = 'id INTEGER PRIMARY KEY AUTO_INCREMENT'
            item_id_retrofit_autoincrement = 'ALTER TABLE {item} MODIFY id INTEGER NOT NULL AUTO_INCREMENT;'
            # SQLite enforces no varchar length and has no indexed-column
            # byte-length limit, so name varchar(255) never actually bounded
            # anything there - only MySQL/MariaDB truncate/error on longer
            # item paths under strict mode. Widen to varchar(1024) there;
            # can't just re-index the full (now longer) column afterwards -
            # InnoDB's indexed-column byte limit (767 bytes on old row
            # formats/charsets, 3072 on modern ones) makes a full-column
            # index on a 1024-char utf8mb4 column version-dependent. A
            # prefix index of 191 chars stays under the classic 767-byte
            # limit at any charset/row-format, and doesn't affect equality
            # lookup correctness (WHERE name = ... still checks the full
            # value; the prefix index only narrows candidate rows).
            # Split into three single-statement versions (9/10/11) because
            # setup() runs one execute() per version, and DB-API drivers
            # don't reliably support multiple ;-separated statements in one
            # execute() call.
            name_widen = 'ALTER TABLE {item} MODIFY name varchar(1024);'
            name_drop_index = 'DROP INDEX {item}_name ON {item};'
            name_recreate_index = 'CREATE INDEX {item}_name ON {item} (name(191));'
        return {
            '1': [
                'CREATE TABLE {log} (time BIGINT, item_id INTEGER, duration BIGINT, val_str TEXT, val_num REAL, val_bool BOOLEAN, changed BIGINT);',
                'DROP TABLE {log};',
            ],
            '2': [
                'CREATE TABLE {item} ('
                + item_id_column
                + ', name varchar(255), time BIGINT, val_str TEXT, val_num REAL, val_bool BOOLEAN, changed BIGINT);',
                'DROP TABLE {item};',
            ],
            '3': [
                'CREATE UNIQUE INDEX {log}_{item}_id_time ON {log} (item_id, time);',
                'DROP INDEX {log}_{item}_id_time;',
            ],
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
            '8': [
                item_id_retrofit_autoincrement,
                '/* AUTO_INCREMENT cannot be cleanly reverted without knowing whether it predates this migration */',
            ],
            '9': [
                name_widen,
                '/* rollback would need the original varchar(255) - not recorded, and sqlite has no length to restore */',
            ],
            '10': [name_drop_index, 'CREATE INDEX {item}_name ON {item} (name);'],
            '11': [name_recreate_index, 'DROP INDEX {item}_name;'],
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
        'duty_cycle': 'SUM(val_bool * duration) / SUM(duration)',
        'countall': 'COUNT(*)',
    }

    # 'first'/'last': keep the oldest/newest raw value in the interval as-is
    # (via LogStore.edge_value's ORDER BY ... LIMIT 1), instead of computing
    # anything over it. Maps action name -> SQL ORDER BY direction.
    _MAXAGE_EDGE_ACTIONS = {'first': 'ASC', 'last': 'DESC'}

    # item types each database_maxage_action is valid for. None = any type.
    # Grounded in utils.encode_value(): val_num is populated for 'num' and
    # 'bool' (bool encodes as float(value)), so avg/sum/min/max/integrate/
    # duty_cycle (which read val_num/val_bool) do not work for str -
    # duty_cycle would additionally store its float on-fraction back as the
    # item's string value. first/last just read back whatever encode_value()
    # already stored, so they work for every type, str included.
    _MAXAGE_ACTION_VALID_TYPES = {
        'avg': ('num', 'bool'),
        'sum': ('num', 'bool'),
        'min': ('num', 'bool'),
        'max': ('num', 'bool'),
        'integrate': ('num', 'bool'),
        'duty_cycle': ('bool',),
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
        self._sqlite_wal_mode = bool(self.get_parameter_value('sqlite_wal_mode'))
        if self._sqlite_wal_mode:
            if self.driver.lower() == 'sqlite3':
                self.logger.notice(
                    'Database: sqlite_wal_mode is enabled - switching the database file to WAL journal '
                    'mode. This is a one-way decision: WAL, once set, persists in the file itself across '
                    'restarts and is picked up by any future connection (including other tools) until '
                    'something explicitly switches it back - turning this parameter back off later does '
                    'not revert an already-converted file.'
                )
            else:
                self.logger.warning(
                    f"Database: sqlite_wal_mode is enabled but driver is '{self.driver}', not sqlite3 - ignored"
                )
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
        self._invalid_check_cycle = self.get_parameter_value('invalid_check_cycle')
        self._invalid_check_grace_time = self.get_parameter_value('invalid_check_grace_time')

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
        # True only once build_orphanlist() has actually completed against a
        # live connection - an empty orphanlist alone doesn't distinguish
        # "confirmed no orphans" from "couldn't check, DB wasn't connected".
        self._orphanlist_built = False
        self._orphan_logcount = {}  # dict to store the number of log records for an orphan
        self.remove_orphan = False  # set to True to remove orphans during remove_older
        self.delete_orphan_chunk_size = 20000  # Delete x log entries for orphan items at a time
        self._handled_items = []  # items that have a 'database' attribute set
        self._items_with_maxage = []  # items that have a 'database_maxage' attribute set
        self._maxage_worklist = []  # work copy of self._items_with_maxage
        self._items_with_invalid_after = {}  # item -> configured database_invalid_after, in seconds
        self._plugin_start_ts = None  # set in run() - startup grace gate for _check_invalid_items()
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
            ('' if self._prefix == '' else self._prefix.capitalize()) + 'Database',
            self.driver,
            self._connect,
            wal_mode=self._sqlite_wal_mode,
        )
        if not self._db.api_initialized:
            # Error initializeng the database driver (e.g.: Python module for database driver not found)
            self.logger.error('Initialization of database API failed')
            self._init_complete = False
            return

        if self.driver.lower() == 'sqlite3' and self._db._params.get('database') in (':memory:', ''):
            # This plugin always opens two independent connections (self._db
            # for regular access, self._db_maint below for maintenance) -
            # each is its own sqlite3.connect() call. A ':memory:' (or
            # blank, which sqlite3 treats the same way) database is private
            # to the connection that opened it; there is no shared-cache URI
            # here, so the two connections would silently become two
            # separate, disconnected empty databases - the maintenance
            # connection would never see anything written via self._db.
            self.logger.critical(
                "Database: driver 'sqlite3' with an in-memory database (':memory:' or blank) is not "
                'supported by this plugin - it uses two independent connections, and each in-memory '
                'SQLite connection is a private database invisible to the other. Configure a file path.'
            )
            self._init_complete = False
            return

        self._item_store = ItemStore(self._db, self._replace, self.logger)
        self._log_store = LogStore(self._db, self._replace, self.logger)

        # Setup db maintenance connection and test if connection is possible
        self._db_maint = lib.db.Database(
            ('' if self._prefix == '' else self._prefix.capitalize()) + 'Database',
            self.driver,
            self._connect,
            wal_mode=self._sqlite_wal_mode,
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
        self._plugin_start_ts = self._timestamp(self.shtime.now())
        if not self._initialize_db():
            # Not fatal - _dump()/id()/_query() all self-heal on their own
            # next call, same as everywhere else in this plugin. Logged
            # explicitly here (distinct from build_orphanlist()'s own
            # swallowed error below) so "started degraded, no DB yet" is
            # visible in the log rather than only inferable from a stray
            # error line above an otherwise-clean-looking startup.
            self.logger.warning('Database: not connected at startup - will keep retrying on the scheduled cycle')
        # alive=True right after the connection attempt (successful or not -
        # both self-heal) rather than after build_orphanlist()/
        # _start_schedulers(): those aren't connectivity checks, they're the
        # plugin already doing its job, and build_orphanlist() alone can
        # block for up to db_query_timeout (default 60s) inside
        # self._db_maint.transaction() if that connection is slow or
        # contended - "running" is read live from this flag (see
        # modules/admin/api_plugins.py), so leaving it False for that whole
        # window means the plugin looks down/unstarted while it has, in
        # fact, already started.
        self.alive = True
        # Retried from _dump() (self._orphanlist_built) if this attempt
        # fails - no separate retry loop needed here.
        self.build_orphanlist(True)
        self._start_schedulers()

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

            if self.has_iattr(item.conf, 'database_invalid_after'):
                self._register_invalid_after(item)

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
                # transaction() ensures the lock releases even if readItem()
                # below raises - a bare lock()/cursor() pair without
                # try/finally would wedge every future operation on this
                # connection (including shutdown) until process restart.
                # timeout=5 (not the 60s default) is deliberate - a per-item
                # read must not stall startup registration.
                try:
                    with self._db.transaction(timeout=5) as cur:
                        cache = self.readItem(str(item.property.path), cur=cur)
                        if cache is not None and cache[COL_ITEM_TIME] is not None:
                            try:
                                value = self._item_value_tuple_rev(
                                    item.type(), cache[COL_ITEM_VAL_STR : COL_ITEM_VAL_BOOL + 1]
                                )
                                last_change = self._datetime(cache[COL_ITEM_TIME])
                                prev_change = self._fetchone(
                                    'SELECT MAX(time) from {log} WHERE item_id = :id',
                                    {'id': cache[COL_ITEM_ID]},
                                    cur=cur,
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
                                        item,
                                        BufferEntry(
                                            time=self._timestamp(self.shtime.now()), duration=None, value=value
                                        ),
                                    )
                            except Exception as e:
                                self.logger.error(
                                    'Reading cache value from database for {} failed: {}'.format(item.property.path, e)
                                )
                        else:
                            self.logger.notice(f'No cached value available in database for item {item.property.path}')
                except TimeoutError:
                    self.logger.error(
                        'Can not acquire lock for database to read value for item {}{}'.format(
                            item.property.path, self._db.lock_holder_description()
                        )
                    )
                    return
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

            # ── Reactive database_invalid_after check ───────────────────────
            # last_update()/prev_update(), not last_change()/prev_change():
            # the former advance on every raw update regardless of whether
            # the value changed, the latter only on a genuine change (or
            # enforce_change) - see _register_invalid_after()'s warning about
            # enforce_updates. Runs before the gap-detection block below, so
            # a gap opened here - if this very call is the recovery - gets
            # picked up and closed by that same existing logic immediately.
            invalid_after_seconds = self._items_with_invalid_after.get(item)
            if invalid_after_seconds is not None:
                last_update_ts = self._timestamp(item.last_update())
                prev_update_ts = self._timestamp(item.prev_update())
                threshold_ms = invalid_after_seconds * 1000
                if last_update_ts - prev_update_ts > threshold_ms:
                    already_open_gap = self._buffer_mgr.last_entry(item)
                    already_open_gap = (
                        already_open_gap is not None
                        and already_open_gap.duration is None
                        and already_open_gap.quality == QUALITY_NO_DATA
                    )
                    if not already_open_gap:
                        # Provable, not guessed: confirmed silent from here on,
                        # so the item cannot still have held its old value past
                        # this point, regardless of when this update arrived.
                        self._mark_item_invalid(item, caller='database_invalid_after', at=prev_update_ts + threshold_ms)

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

    def _register_invalid_after(self, item):
        """Validate and register *item*'s database_invalid_after attribute.

        No plugin-level default/fallback exists for this value on purpose -
        unlike database_maxage, there's no value reasonable to apply to an
        item that didn't explicitly ask for it (see plugin.yaml).

        :param item: item with a database_invalid_after attribute set
        """
        interval = self.get_iattr_value(item.conf, 'database_invalid_after')
        seconds = self.shtime.to_seconds(interval, test=True)
        if not seconds or seconds <= 0:
            self.logger.warning(
                f"Item {item.property.path}: invalid database_invalid_after value '{interval}', ignoring"
            )
            return

        if self.has_iattr(item.conf, 'database_acl'):
            acl = self.get_iattr_value(item.conf, 'database_acl').lower()
        else:
            acl = 'rw'
        if acl != 'rw':
            self.logger.warning(
                f'Item {item.property.path}: database_invalid_after is not compatible with '
                f'database_acl: {acl}, ignoring'
            )
            return

        if not item.property.enforce_updates:
            self.logger.warning(
                f"Item {item.property.path}: database_invalid_after is set without 'enforce_updates' - "
                'a recovery to the same value stays undetected until the next periodic check '
                '(up to invalid_check_cycle + invalid_check_grace_time later); a recovery to a '
                'different value is still detected immediately.'
            )

        self._items_with_invalid_after[item] = seconds

    def _mark_item_invalid(self, item, caller=None, source=None, at=None):
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
        :param at:     Internal use only, not part of the public
                        ``db_mark_invalid()`` contract - backdates the gap's
                        start to a provable boundary (e.g. an item's own
                        computed staleness deadline) instead of "now". A
                        caller supplying this must be certain it's still
                        correct at the moment of the call; there is no
                        re-validation here.
        """
        start_ts = self._timestamp(self.shtime.now()) if at is None else at
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

    def _check_invalid_items(self):
        """Scheduled check for database_invalid_after items still silent right now.

        Complements the reactive check in :meth:`update_item`, which only
        fires when a *next* update eventually arrives - this is the only
        path that can catch an item that's still silent with no resolution
        in sight. Detection latency is bounded by invalid_check_cycle; the
        boundary written to the log is not - it's computed from the item's
        own last_update() plus its configured threshold, never wall-clock
        "now", so the recorded duration is accurate regardless of how late
        this check happens to run.
        """
        if self._plugin_start_ts is None:
            return
        now_ts = self._timestamp(self.shtime.now())
        grace_ms = self._invalid_check_grace_time * 1000
        for item, invalid_after_seconds in list(self._items_with_invalid_after.items()):
            threshold_ms = invalid_after_seconds * 1000
            if now_ts - self._plugin_start_ts < threshold_ms + grace_ms:
                # Startup grace: database: init's restore can leave
                # last_update() pointing at a (possibly very old) pre-restart
                # timestamp - give this item its own threshold plus
                # invalid_check_grace_time before ever judging it.
                continue
            last_update_ts = self._timestamp(item.last_update())
            if now_ts - last_update_ts <= threshold_ms:
                continue
            already_open_gap = self._buffer_mgr.last_entry(item)
            already_open_gap = (
                already_open_gap is not None
                and already_open_gap.duration is None
                and already_open_gap.quality == QUALITY_NO_DATA
            )
            if already_open_gap:
                continue
            self._mark_item_invalid(item, caller='database_invalid_after (scan)', at=last_update_ts + threshold_ms)

    def _start_schedulers(self):
        """
        Start jobs that maintain buffer and database
        """
        if self.count_logentries:
            self.scheduler_add('Count logs', self._count_logentries, cycle=6 * 3600, prio=6)
        self.scheduler_add('Buffer dump', self._dump, cycle=self._dump_cycle, prio=5)
        # default_maxage alone (with no item setting its own database_maxage)
        # still needs this scheduler - remove_older_than_maxage()'s worklist
        # fill already handles that case by falling back to _handled_items
        # (see its len(_maxage_worklist) == 0 branch), but registration here
        # was gated on _items_with_maxage only, so the scheduler was never
        # started at all and default_maxage was silently inert.
        if self._default_maxage > 0 or len(self._items_with_maxage) > 0:
            # self.scheduler_add('Remove old', self.remove_older_than_maxage, cycle=91, prio=6)
            self.scheduler_add('Remove old', self.remove_older_than_maxage, cycle=self._removeold_cycle, prio=7)
        if len(self._items_with_invalid_after) > 0:
            self.scheduler_add(
                'Check invalid items', self._check_invalid_items, cycle=self._invalid_check_cycle, prio=7
            )
        return

    def _stop_schedulers(self):
        """
        Stop jobs that maintain buffer and database
        """
        if self._default_maxage > 0 or len(self._items_with_maxage) > 0:
            self.scheduler_remove('Remove old')
        if len(self._items_with_invalid_after) > 0:
            self.scheduler_remove('Check invalid items')
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
        database_name = self._extract_connect_value(self._connect, 'database')

        # In WAL journal mode, recently committed data can still sit in a
        # separate -wal sidecar file rather than the main file - a plain
        # copy of just the main file would silently miss it. TRUNCATE folds
        # everything back and empties -wal, so the subsequent single-file
        # copy is complete. Not gated on sqlite_wal_mode: the FILE's actual
        # on-disk mode is what matters (it may have been set by an earlier
        # run of this plugin, or another tool), not the current config, and
        # this is a harmless no-op against a file that isn't in WAL mode.
        if database_name and os.path.exists(database_name):
            try:
                import sqlite3

                checkpoint_conn = sqlite3.connect(database_name)
                try:
                    checkpoint_conn.execute('PRAGMA wal_checkpoint(TRUNCATE);')
                finally:
                    checkpoint_conn.close()
            except Exception as e:
                self.logger.warning(f'Could not checkpoint SQLite3 database file before copying: {e}')

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

    def id(self, item, create=True, cur=NO_CURSOR):
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

        def _find_or_create(c):
            try:
                found = self.readItem(item_path, cur=c)
            except Exception as e:
                self._log_db_exception(
                    e, f'id(): No id found for item {item_path} - Exception {e}', fallback=self.logger.warning
                )
                found = None
            if found is None and create:
                found = [self.insertItem(item_path, c)]
            return found

        if cur is not NO_CURSOR:
            # caller already holds the lock for its own multi-statement
            # block (e.g. _dump()'s per-item transaction()) - use its
            # cursor directly, no locking of our own.
            id = _find_or_create(cur)
        else:
            # readItem()-then-insertItem() is a check-then-act sequence:
            # without holding the lock across both, two concurrent
            # callers can each see "not found" and both insert, creating
            # a duplicate row for the same item name. transaction() holds
            # the lock for the whole sequence and commits/rolls back
            # automatically - mirrors the same init/verify/lock/timeout
            # handling as _query().
            if not self._db_initialized and not self._initialize_db():
                return None
            # retry kept low - see Database.verify()'s docstring cost note;
            # id() already gets re-invoked by its own callers on failure.
            if self._db.verify(2) == 0:
                # verify() actively probed and failed to reconnect twice -
                # this *is* the connection-trouble case by construction, no
                # exception to classify: same INFO level as everywhere else
                # that condition is confirmed, not a real-bug ERROR.
                self.logger.info(
                    'Database: Connection not recovered ({}){}'.format(
                        self._db.last_verify_reason(), self._db.lock_holder_description()
                    )
                )
                return None
            try:
                with self._db.transaction() as tcur:
                    id = _find_or_create(tcur)
            except TimeoutError:
                self.logger.error(
                    "Database: Can't query due to fail to acquire lock{}".format(self._db.lock_holder_description())
                )
                return None
            except Exception as e:
                # insertItem() (the create=True path) isn't covered by
                # _find_or_create's own readItem-only try/except - a
                # connection failure there would otherwise escape uncaught.
                self._log_db_exception(e, f'id(): could not find/create id for item {item_path}: {e}')
                return None

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
            row = self.readItem(item_path)
        except Exception as e:
            self._log_db_exception(
                e, f'db_itemtype: No id found for item {item_path} - Exception {e}', fallback=self.logger.warning
            )
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
            row = self.readItem(item_path)
        except Exception as e:
            self._log_db_exception(
                e, f'db_lastchange: No id found for item {item_path} - Exception {e}', fallback=self.logger.warning
            )
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
        cur=NO_CURSOR,
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
        # newline='' + csv.writer: per Python's csv module docs, letting the
        # file object translate newlines itself (the default) can double up
        # line endings csv.writer already controls via lineterminator.
        # csv.writer also replaces the previous hand-rolled '"'-only escaping
        # (which left an embedded ';' or newline in a val_str value
        # unescaped, silently corrupting the row - a semicolon shifts every
        # later column, a newline splits one row into two) with proper
        # RFC 4180 quoting for any field containing the delimiter, a quote,
        # or a newline.
        f = open(dumpfile, 'w', newline='')
        try:
            self._dump_rows(f, s, h, item_ids, time, time_start, time_end, changed, changed_start, changed_end, cur)
        finally:
            # A failure partway through (e.g. connection loss mid-dump)
            # must not leak this handle - the exception itself still
            # propagates to the caller (webif's db_csvdump()) unchanged.
            f.close()

    def _dump_rows(self, f, s, h, item_ids, time, time_start, time_end, changed, changed_start, changed_end, cur):
        writer = csv.writer(f, delimiter=s, lineterminator='\n')
        writer.writerow(h)
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
                # time_date/changed_date: both derived from log-row columns
                # (COL_LOG_TIME, not COL_ITEM_ID - a log row's item_id and
                # time columns are unrelated values that only happened to
                # share the same tuple index (0) in both constants, masking
                # this for as long as nobody reordered either column list).
                for key in [COL_LOG_TIME, COL_LOG_CHANGED]:
                    cols.append('' if row[key] is None else datetime.datetime.fromtimestamp(row[key] / 1000.0))
                cols = ['' if col is None else col for col in cols]
                writer.writerow(cols)
        self.logger.info('File dump completed ({} items) ...'.format(len(item_ids)))

    def sqlite_dump(self, dumpfile):

        if self.driver.lower() != 'sqlite3':
            self.logger.warning('SQL dump is only possible for sqlite3 databases')
            return False

        self.logger.info(f'Starting SQL file dump of the sqlite3 database to {dumpfile} ...')

        # iterdump() reads directly off the raw sqlite3 connection, bypassing
        # every other access to self._db in this file (which all go through
        # self._db.transaction(), taking self._fdb_lock) - without the same
        # lock here, a concurrent write (e.g. a buffer flush) could
        # interleave with the dump and produce an inconsistent snapshot.
        # timeout=300 matches _dump()'s own transaction(timeout=300) for a
        # similarly long-running maintenance operation.
        if not self._db.lock(timeout=300):
            self.logger.error('sqlite_dump: could not acquire database lock within 300s, aborting dump')
            return False
        try:
            with open(dumpfile, 'w') as f:
                for line in self._db._conn.iterdump():
                    f.write(f'{line}\n')
        finally:
            self._db.release()

        self.logger.info('SQL file dump of sqlite3 database completed')
        return True

    def insertItem(self, name, cur=NO_CURSOR):
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

    def updateItem(self, id, time, duration=0, val=None, it=None, changed=None, cur=NO_CURSOR):
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

    def readItem(self, id, cur=NO_CURSOR):
        """

        This is a public function of the plugin

        :param id: Id of the item within the database
        :param cur: A database cursor object if available (optional)

        :return: Data for the selected item
        """
        return self._item_store.find(id, cur=cur)

    def readItems(self, cur=NO_CURSOR):
        """
        Read database item records

        This is a public function of the plugin

        :param cur: A database cursor object if available (optional)

        :return: selected items
        """
        return self._item_store.find_all(cur=cur)

    def readItemCount(self, cur=NO_CURSOR):
        """
        Read database log count for given database ID

        This is a public function of the plugin

        :param cur: A database cursor object if available (optional)

        :return: Number of log records for the database ID
        """
        return self._item_store.count(cur=cur)

    def deleteItem(self, id, cur=NO_CURSOR):
        """
        Delete database item record for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to delete the record for
        :param cur: A database cursor object if available (optional)
        """
        self._item_store.delete(id, cur=cur)

    def insertLog(self, id, time, duration=0, val=None, it=None, changed=None, cur=NO_CURSOR, quality=QUALITY_VALID):
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

    def updateLog(self, id, time, duration=0, val=None, it=None, changed=None, cur=NO_CURSOR, quality=QUALITY_VALID):
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

    def readLog(self, id, time, cur=NO_CURSOR):
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
        cur=NO_CURSOR,
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

    def readOldestLog(self, id, cur=NO_CURSOR):
        """
        Read the time of oldest log record for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to read the record for
        :param cur: A database cursor object if available (optional)

        :return: Time of oldest log record for the database ID
        """
        return self._log_store.oldest_time(id, cur=cur)

    def readLatestLog(self, id, time=None, cur=NO_CURSOR):
        """
        Read the time of latest log record for given database ID and if time given up to this time

        This is a public function of the plugin

        :param id: Database ID of item to read the record for
        :param time: a maximum timestamp for the given value
        :param cur: A database cursor object if available (optional)

        :return: Log record for the database ID
        """
        return self._log_store.latest_time(id, before=time, cur=cur)

    def readTotalLogCount(self, cur=NO_CURSOR):
        """
        Return the total number of log rows across all items.

        This is a public function of the plugin.

        :param cur: Optional cursor.
        :return:    Total log row count.
        :rtype:     int
        """
        return self._log_store.count_all(cur=cur)

    def readLogCount(self, id, time_start=None, time_end=None, cur=NO_CURSOR):
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
        cur=NO_CURSOR,
    ):
        """
        Delete database log records for given item (database ID)

        This is a public function of the plugin

        With no cur given, this acquires its own lock and commits via
        LogStore.delete_range() (see its docstring) - there is no longer
        a separate with_commit toggle, since a call with cur omitted that
        doesn't commit has nothing else guaranteed to flush it, and a
        passed-in cur being committed unilaterally would end the caller's
        own transaction early.

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
        try:
            self._log_store.delete_range(
                id,
                time=time,
                time_start=time_start,
                time_end=time_end,
                changed=changed,
                changed_start=changed_start,
                changed_end=changed_end,
                cur=cur,
            )
        except Exception as e:
            if cur is NO_CURSOR and self._db.is_connection_error(e):
                # We own the transaction end-to-end here (delete_range()
                # opens/rolls back its own transaction() when cur is omitted),
                # so swallowing is safe - same owns_cur contract as _query().
                # A caller-supplied cur means the caller owns the
                # transaction and needs to see this to roll back correctly.
                self.logger.info(f'deleteLog: {e}')
                return
            raise

        try:
            self._item_logcount[id] = self.readLogCount(id, cur=cur)
        except Exception as e:
            self._log_db_exception(e, 'Exception in function deleteLog during readLogCount: {}'.format(e))

        return

    def markLogInvalid(self, id, time=None, changed=None, cur=NO_CURSOR, with_commit=True):
        """
        Reversibly flag a database log record as invalid, preserving its value

        This is a public function of the plugin. Unlike deleteLog(), the row is
        kept - only its val_quality is set to QUALITY_INVALID, which excludes it
        from time-weighted aggregations (avg, sum, integrate, on, min, max) while
        leaving val_str/val_num/val_bool/duration untouched so the flag can be
        undone with markLogValid().

        :param id: Database ID of item to flag the record for
        :param time: Restrict flagging to given time (optional)
        :param changed: Restrict flagging to given change time (optional)
        :param cur: A database cursor object if available (optional)
        :return:
        """
        self._log_store.set_quality(id, QUALITY_INVALID, time=time, changed=changed, cur=cur, commit=with_commit)

    def markLogValid(self, id, time=None, changed=None, cur=NO_CURSOR, with_commit=True):
        """
        Undo markLogInvalid(): restore a database log record's val_quality to valid

        This is a public function of the plugin.

        :param id: Database ID of item to restore the record for
        :param time: Restrict restoring to given time (optional)
        :param changed: Restrict restoring to given change time (optional)
        :param cur: A database cursor object if available (optional)
        :return:
        """
        self._log_store.set_quality(id, QUALITY_VALID, time=time, changed=changed, cur=cur, commit=with_commit)

    def build_orphanlist(self, log_activity=False):
        """
        Create a list of database entries which have no corresponding item in the item tree

        Called once at run() and, if that attempt failed (no DB connection
        yet), retried once per _dump() cycle until it succeeds - see
        self._orphanlist_built.

        :return: True if the list was actually (re)built against a live
                 connection, False if the attempt failed (e.g. DB not
                 connected) - an empty self.orphanlist alone doesn't tell
                 the caller which of those happened.
        :rtype: bool
        """
        if log_activity:
            self.logger.info('build_orphan_list: Started')
        self.orphanitemlist = []
        self.orphanlist = []
        # cleared up front, not just left at its previous value: a failed
        # rebuild below wipes the list above regardless, so a stale True
        # here would let remove_orphan_items() mistake "rebuild just
        # failed" for "confirmed empty" on this attempt's now-empty list.
        self._orphanlist_built = False

        items = [item.property.path for item in self._buffer_mgr.items()]
        # transaction() serializes this against self._db_maint's other
        # users - the scheduler-driven maxage/orphan cleanup also runs on
        # this same connection.
        try:
            with self._db_maint.transaction() as cur:
                return_list = self.readItems(cur=cur)
                if return_list:
                    for item in return_list:
                        if item[COL_ITEM_NAME] not in items:
                            if log_activity:
                                self.logger.info(f'- Found data for item w/o database attribute: {item[COL_ITEM_NAME]}')
                            self.orphanitemlist.append(item)
                            self.orphanlist.append(item[COL_ITEM_NAME])
        except Exception as e:
            self._log_db_exception(e, 'Database build_orphan_list failed: {}'.format(e), db=self._db_maint)
            return False

        self._orphanlist_built = True
        self._count_orphanlogentries()
        if log_activity:
            self.logger.info('build_orphan_list: Finished')

        return True

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
        # transaction() serializes this against self._db_maint's other
        # users. One transaction per UPDATE chunk, not one around the whole
        # loop - the LIMIT batching exists to keep individual transactions
        # bounded, and a partially-reassigned state is safe to resume from
        # (remaining rows still carry orphan_id). The item row is only
        # deleted once every log row has moved.
        try:
            log_info(f'reassigning orphaned data from (old) id {orphan_id} to (new) id {to}')
            with self._db_maint.transaction() as cur:
                count = self.readLogCount(orphan_id, cur=cur)
            log_debug(f'found {count} entries to reassign, reassigning {self.max_reassign_logentries} at once')

            while count > 0:
                log_debug(f'reassigning {min(count, self.max_reassign_logentries)} log entries')
                with self._db_maint.transaction() as cur:
                    # (item_id, time)-matched, double-wrapped subquery, not
                    # rowid-based - same two reasons as the bulk-delete
                    # statements' fix (remove_older_than_maxage(),
                    # _delete_orphan()): {log} has no primary key so
                    # MySQL/MariaDB exposes no rowid for it, and MariaDB
                    # separately rejects LIMIT directly inside IN(subquery).
                    self._execute(
                        self._prepare(
                            'UPDATE {log} SET item_id = :newid WHERE item_id = :orphanid AND time IN '
                            '(SELECT time FROM (SELECT time FROM {log} WHERE item_id = :orphanid '
                            'LIMIT :limit) AS upd_batch);'
                        ),
                        {'newid': to, 'orphanid': orphan_id, 'limit': self.max_reassign_logentries},
                        cur=cur,
                    )
                count -= self.max_reassign_logentries

            with self._db_maint.transaction() as cur:
                self._execute(
                    self._prepare('DELETE FROM {item} WHERE id = :orphanid;'), {'orphanid': orphan_id}, cur=cur
                )
            log_info(f'reassigned orphaned id {orphan_id} to new id {to}')
            log_debug('rebuilding orphan list')
            self.build_orphanlist()
        except Exception as e:
            self._log_db_exception(e, f'error on reassigning id {orphan_id} to {to}: {e}', db=self._db_maint)
            return e

    def _delete_orphan(self, item_path):
        """
        Delete orphan item or logentries it

        :param item_path: path_name of the (orphan) item to work on
        :param limit: Maximum log entries to delete

        :return: True, if item was deleted; False if only logentries were deleted
        """
        # This method deliberately has no except of its own - a failure
        # propagates uncaught to remove_orphan_items()'s own try/except,
        # which logs it and requeues the item for the next cycle. Both
        # branches below use transaction() to serialize against
        # self._db_maint's other users while preserving that.
        item_id = self.id(item_path, create=False)
        logcount = self.readLogCount(item_id)
        if logcount == 0:
            self.logger.info(f'_delete_orphan: Item {item_path} has no log entries')
            with self._db_maint.transaction() as cur:
                self._execute(self._prepare('DELETE FROM {item} WHERE id = :id;'), {'id': item_id}, cur=cur)
            self.logger.info(f'_delete_orphan: Deleted item entry for {item_path}')
            return True

        with self._db_maint.transaction() as cur:
            # Not a bare DELETE...LIMIT (invalid SQLite syntax without a
            # non-default compile flag) or a rowid-subquery ({log} has no
            # primary key, and MySQL/MariaDB - unlike SQLite - has no
            # queryable row id for a table without one). Matches on
            # (item_id, time) instead, via the UNIQUE KEY
            # {log}_{item}_id_time already on this table (see _setup).
            # Double-wrapped, not single-wrap: MariaDB separately rejects
            # LIMIT directly inside an IN(subquery).
            self._execute(
                self._prepare(
                    'DELETE FROM {log} WHERE item_id = :id AND time IN (SELECT time FROM '
                    '(SELECT time FROM {log} WHERE item_id = :id LIMIT :maxrecords) AS del_batch);'
                ),
                {'id': item_id, 'maxrecords': self.delete_orphan_chunk_size},
                cur=cur,
            )
        delete_orphan_chunk_size_str = f'{self.delete_orphan_chunk_size:,}'.replace(',', '.')
        self.logger.info(
            f'_delete_orphan: Deleted (up to) {delete_orphan_chunk_size_str} log entries for Item {item_path}'
        )

        return False

    def remove_orphan_items(self):
        """
        Delete item and logdata of items that have no correspondance in itemtree
        """
        if len(self.orphanlist) == 0:
            self.build_orphanlist()

        if len(self.orphanlist) == 0:
            if not self._orphanlist_built:
                # build_orphanlist() just failed (e.g. DB not connected) -
                # an empty list here doesn't mean "confirmed no orphans".
                # Leave self.remove_orphan set so the next
                # remove_older_than_maxage() cycle retries this instead of
                # silently disabling cleanup over a connectivity hiccup.
                self.logger.warning('remove_orphan_items: could not check for orphans (DB not connected), will retry')
                return
            self.remove_orphan = False
            self.logger.info('remove_orphan_items: No orphans found, cleanup finished')
            return

        item = self.orphanlist.pop(0)
        try:
            deleted = self._delete_orphan(item)
        except Exception as e:
            # e.g. the maintenance connection (_db_maint) went stale independently
            # of the main connection (see smarthomeNG/plugins#1004) - keep the item
            # queued and retry on the next cycle instead of crashing the scheduler task.
            self._log_db_exception(
                e,
                f'remove_orphan_items: Deletion of orphan {item} failed, will retry: {e}',
                db=self._db_maint,
                fallback=self.logger.warning,
            )
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
        # 'diff'/'differentiate' need LAG(...) OVER (ORDER BY time) computed
        # per raw row before any GROUP BY - mixing a window function with an
        # aggregate GROUP BY in one SELECT (the previous approach) errors
        # outright under MySQL 8/5.7's default ONLY_FULL_GROUP_BY, and
        # returns an undefined arbitrary-row's LAG value per bucket on
        # MariaDB's default (permissive) mode - verified against a real
        # MariaDB target. This subquery computes the per-row diff/time-gap
        # first; the outer query then buckets by summing across rows in
        # each bucket, which telescopes correctly across bucket boundaries
        # (sum of consecutive diffs = last value - first value spanned).
        diff_window_table = (
            '(SELECT time, val_num, '
            '(val_num - LAG(val_num,1) OVER (ORDER BY time)) AS diffval, '
            '(time - LAG(time,1) OVER (ORDER BY time)) AS timegap '
            'FROM {log} WHERE ' + self._fetch_log_base_where() + ') w'
        )
        queries = {
            'avg': self._time_precision_query('MIN(time)')
            + ', '
            + self._precision_query('AVG(val_num * duration) / AVG(duration)'),
            'avg.order': 'ORDER BY time ASC',
            'integrate': self._time_precision_query('MIN(time)') + ', SUM(val_num * duration)',
            # SUM(diffval): total net change during the bucket. Rows with no
            # predecessor (diffval IS NULL - the very first row in range)
            # are ignored by SUM, same as they always were as a single
            # ungrouped row.
            'diff': self._time_precision_query('MIN(time)') + ', SUM(diffval)',
            'diff.table': diff_window_table,
            'duration': self._time_precision_query('MIN(time)') + ', duration',
            # differentiate (d/dt) is scaled to match the conversion from d/dt (kWh) = kWh: time is in ms, val_num in kWh, therefore scale by 1000ms and 3600s/h to obtain the result in kW:
            # total change over the bucket / total time spanned by the
            # bucket, in hours - the physically correct average rate over
            # an interval built from irregular samples (not an average of
            # per-row rates, which would over-weight short gaps). 3600.0
            # (not 3600): SUM(timegap) is an integer column - on SQLite,
            # dividing two integers is integer (floor) division, so any
            # bucket spanning under an hour would floor-divide to 0 and
            # then divide-by-zero to NULL; the float literal forces real
            # division. MariaDB/MySQL always do real division for '/'
            # regardless of operand type, so this was sqlite-only.
            'differentiate': self._time_precision_query('MIN(time)')
            + ', SUM(diffval) / (SUM(timegap) / (3600.0 * 1000))',
            'differentiate.table': diff_window_table,
            'count': self._time_precision_query('MIN(time)')
            + ', SUM(CASE WHEN val_num{op}{value} THEN 1 ELSE 0 END)'.format(**expression['params']),
            'countall': self._time_precision_query('MIN(time)') + ', COUNT(*)',
            'min': self._time_precision_query('MIN(time)') + ', MIN(val_num)',
            'max': self._time_precision_query('MIN(time)') + ', MAX(val_num)',
            'on': self._time_precision_query('MIN(time)')
            + ', '
            + self._precision_query('SUM(val_bool * duration) / SUM(duration)'),
            'on.order': 'ORDER BY time ASC',
            # 'duty_cycle': same query as 'on' under its more descriptive name - both accepted, kept in sync.
            'duty_cycle': self._time_precision_query('MIN(time)')
            + ', '
            + self._precision_query('SUM(val_bool * duration) / SUM(duration)'),
            'duty_cycle.order': 'ORDER BY time ASC',
            'sum': self._time_precision_query('MIN(time)') + ', SUM(val_num)',
            'raw': self._time_precision_query('time') + ', val_num',
            'raw.order': 'ORDER BY time ASC',
            'raw.group': '',
        }
        if func not in queries:
            raise NotImplementedError

        order = '' if func + '.order' not in queries else queries[func + '.order']
        # (time - (time % :step)), not ROUND(time / :step): sqlite's integer
        # '/' floors while MariaDB's decimal '/' + ROUND() rounds half-up,
        # so the same data bucketed differently per backend. The modulo form
        # is exact integer math on both and keeps sqlite's historical floor
        # partitioning.
        group = 'GROUP BY (time - (time % :step))' if func + '.group' not in queries else queries[func + '.group']
        table = queries.get(func + '.table')
        logs = self._fetch_log(
            item, queries[func], start, end, step=step, count=count, group=group, order=order, table=table
        )
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
            # 'duty_cycle': same query as 'on' under its more descriptive name - both accepted, kept in sync.
            'duty_cycle': self._precision_query('SUM(val_bool * duration) / SUM(duration)'),
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
        # Every func here except 'raw' is an ungrouped SQL aggregate
        # (MIN/MAX/SUM/...), which always returns exactly one row - a NULL
        # one if nothing matched, not zero rows. 'raw' has no aggregate and
        # no GROUP BY (see 'raw.group': ''), so an empty range genuinely
        # returns zero rows there - _fetchall() then returns [], not None,
        # so an `is None` check alone let logs['tuples'][0][0] raise
        # IndexError instead of reporting "no data" like every other func.
        if not logs['tuples']:
            return None
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

    def _fetch_log_base_where(self):
        """The WHERE clause shared by every _fetch_log() query: item/quality
        filtering plus the one-row-before-:time_start lookback that lets a
        row spanning into the requested range still contribute its
        duration. Factored out so a caller building its own subquery (e.g.
        _series()'s diff/differentiate window-function subquery) can apply
        the identical filter instead of duplicating it.
        """
        return (
            'item_id = :id AND '
            '(val_quality IS NULL OR val_quality = 0) AND '
            'time >= (SELECT COALESCE(MAX(time), 0) FROM {log} WHERE item_id = :id AND time < :time_start) AND '
            'time <= :time_end AND '
            'time + duration_now > (SELECT COALESCE(MAX(time), 0) FROM {log} WHERE item_id = :id AND time < :time_start)'
        )

    def _fetch_log(self, item, columns, start, end, step=None, count=100, group='', order='', table=None):
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
        base_where = self._fetch_log_base_where()
        if table is None:
            # Default shape: aggregate columns select directly off {log}.
            query = 'SELECT ' + columns + ' FROM {log} WHERE ' + base_where + ' ' + group + ' ' + order
        else:
            # table is a caller-built "(SELECT ... FROM {log} WHERE ...) alias"
            # subquery (e.g. one computing a window function per raw row) -
            # the caller is responsible for applying base_where itself inside
            # that subquery; columns/group/order here then operate on the
            # subquery's already-filtered, already-windowed output rows.
            query = 'SELECT ' + columns + ' FROM ' + table + ' ' + group + ' ' + order

        # Replace duration_now with value from start time til current time to
        # get a duration value referring to the current timestamp - if required.
        query = query.replace('duration_now', duration_now)

        logs = self._fetchall(query, params)
        if logs:
            # MariaDB/MySQL return Decimal (not float) for SUM()/AVG() over
            # exact-numeric columns - e.g. 'on''s SUM(val_bool * duration),
            # both integer-typed columns (val_num's own aggregates stay
            # DOUBLE/float, since it's an approximate-numeric column;
            # sqlite never returns Decimal at all). Decimal arithmetic
            # doesn't mix with float - _finalize()'s 'diff' subtracts
            # adjacent tuple values directly, and _series() injects plain
            # float boundary values via float(item()), so a Decimal row
            # next to a float one would raise TypeError. Coercing here, at
            # the single choke point both _series() and _single() read
            # through, avoids the driver-dependent type difference
            # entirely rather than patching each affected func downstream.
            logs = [tuple(float(v) if isinstance(v, decimal.Decimal) else v for v in row) for row in logs]

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

        if not self._orphanlist_built:
            # run()'s own attempt failed (DB wasn't connected yet at
            # startup) - retry here, piggybacked on this already-scheduled
            # cycle rather than a separate retry loop. Stops retrying the
            # moment it succeeds once (build_orphanlist() sets the flag).
            self.build_orphanlist()

        if items is None:
            # No item given on method call -> dump content of the buffer
            items = self._buffer_mgr.items()

        for item in items:
            entries = self._buffer_mgr.pop_all(item)

            if len(entries) or finalize:
                # Test connectivity - retry kept low, see Database.verify()'s
                # docstring cost note; the scheduler re-invokes _dump() on
                # its own cycle regardless, so a long internal retry here
                # only delays discovering that without changing the outcome.
                if self._db.verify(2) == 0:
                    self._buffer_mgr.restore(item, entries)
                    self.logger.notice(
                        'Connection not recovered ({}){} - dump skipped, data buffered for next cycle'.format(
                            self._db.last_verify_reason(), self._db.lock_holder_description()
                        )
                    )
                    self._dump_lock.release()
                    return

                #                if self.has_iattr(item.conf, 'database_acl'):
                #                    acl = self.get_iattr_value(item.conf, 'database_acl').lower()
                #                    self.logger.info("_dump: Dumping item '{}', database_acl = {}".format(item, acl))

                # On a lock timeout specifically, the whole method aborts
                # (restore the buffer, log, release self._dump_lock,
                # return) rather than just skipping this one item -
                # transaction() raises TimeoutError for exactly that case,
                # caught separately below from any other failure during
                # the actual dump work (logged, buffer restored, loop
                # continues to the next item). timeout=300 preserves the
                # original hardcoded value (still independent of
                # db_query_timeout - a separate, already-documented issue).
                try:
                    with self._db.transaction(timeout=300) as cur:
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
                            # default=True here mirrors plugin.yaml's documented
                            # default for this attribute - item parsing only
                            # applies plugin-declared item_attribute defaults to
                            # items that already set the attribute explicitly
                            # (see lib/item/item.py's per-item conf loop), never
                            # to items that omit it, so relying on get_iattr_value's
                            # own default=None here silently inverted the
                            # documented default to False for every item that
                            # doesn't set it.
                            if not self.get_iattr_value(item.conf, 'database_write_on_shutdown', True):
                                self.logger.debug(
                                    f'DEBUG _dump: Blocking rewrite to DB for item {item} with value {val}'
                                )

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

                        id = self.id(item, cur=cur)

                        # Dump entries
                        self.logger.debug('Dumping {}/{} with {} values'.format(item.property.path, id, len(entries)))

                        for entry in entries:
                            self._log_store.upsert(id, entry, item.type(), changed, cur=cur)

                        self.updateItem(id, _update[0], None, _update[1], item.type(), _update[2], cur)
                except TimeoutError:
                    self._buffer_mgr.restore(item, entries)
                    holder = self._db.lock_holder_description()
                    if finalize:
                        self.logger.error(
                            "Can't dump {} items due to fail to acquire lock!{}".format(
                                len(self._buffer_mgr.items()), holder
                            )
                        )
                    else:
                        self.logger.warning(
                            "Can't dump {} items due to fail to acquire lock - will try on next dump{}".format(
                                len(self._buffer_mgr.items()), holder
                            )
                        )
                    self._dump_lock.release()
                    return
                except Exception as e:
                    if self._db.is_connection_error(e):
                        # transaction() already logged this - no traceback needed.
                        self.logger.warning(f'Problem dumping {item.property.path}: {e} - will retry on next dump')
                    else:
                        self.logger.warning('Problem dumping {}: {}'.format(item.property.path, e), exc_info=True)
                    self._buffer_mgr.restore(item, entries)
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

        if action == 'on':
            # Legacy alias for 'duty_cycle' - kept for configs that already
            # quote it (unquoted 'on' is YAML bool True and never reaches
            # here as this string in the first place).
            action = 'duty_cycle'

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
        stalled = False
        connection_failed = False
        while intervals_done < self.max_aggregate_intervals:
            try:
                oldest = self._log_store.oldest_time(item_id)
            except Exception as e:
                # Same self-healing case as the transaction() except-block
                # below - a connection error reading oldest_time() itself
                # means nothing this cycle can proceed; requeue below rather
                # than trusting a follow-up oldest_time() call to succeed.
                self._log_db_exception(
                    e,
                    f'remove_older_: {itempath} could not read oldest log time, giving up this cycle: {e}',
                    exc_info=True,
                )
                connection_failed = True
                break
            if oldest is None:
                break  # nothing left to compact

            interval_start = (oldest // interval_ms) * interval_ms
            interval_end = interval_start + interval_ms
            if interval_end > cutoff_ms:
                break  # this interval isn't entirely past the cutoff yet - leave it raw

            # transaction() ensures a failure here (e.g. a protocol
            # desync/dropped connection mid-statement) triggers a rollback
            # before the lock releases - without it, self._conn's broken
            # state is left uncleaned for the next caller to inherit.
            # timeout=300 preserves the original hardcoded value (still
            # independent of db_query_timeout - a separate, already-
            # documented issue). The value read (edge/aggregate) happens
            # inside this same transaction(), not before it - _dump() runs
            # under a different lock (_dump_lock, not self._db._fdb_lock)
            # and could otherwise write a new row into this exact interval
            # between an earlier read and this delete, which would then be
            # deleted without ever having contributed to the value just
            # computed.
            try:
                with self._db.transaction(timeout=300) as cur:
                    # Cross-checked against item.last_change(), not the buffer (forgotten once
                    # flushed) - a crash orphan looks identical in storage but fails this check.
                    open_time = self._log_store.find_open(item_id, cur=cur)
                    open_in_interval = open_time is not None and interval_start <= open_time < interval_end
                    open_is_live = open_in_interval and self._timestamp(item.last_change()) == open_time

                    if edge_order:
                        # 'first'/'last': keep the actual oldest/newest raw
                        # value as-is (works for str too - encode_value/
                        # decode_value round-trip it via val_str, unlike the
                        # val_num-based aggregate expressions).
                        edge = self._log_store.edge_value(
                            item_id, edge_order, time_start=interval_start - 1, time_end=interval_end, cur=cur
                        )
                        value = self._item_value_tuple_rev(item_type, edge) if edge else None
                    elif open_is_live and action in ('avg', 'integrate', 'duty_cycle'):
                        # Clipped to interval_end, not "now" - a provable bound (still open, so
                        # certainly still this value then), same technique as _series()'s duration_now.
                        clipped_expr = expr.replace('duration', f'COALESCE(duration, {interval_end} - time)')
                        value = self._log_store.aggregate(
                            item_id, clipped_expr, time_start=interval_start - 1, time_end=interval_end, cur=cur
                        )
                    else:
                        value = self._log_store.aggregate(
                            item_id, expr, time_start=interval_start - 1, time_end=interval_end, cur=cur
                        )

                    if value is None:
                        # Valid rows may remain unrepresented (e.g. a crash orphan) - leave the
                        # interval raw rather than delete without writing anything; gap-only
                        # intervals are still cleaned up.
                        valid_rows = self._log_store.count(
                            item_id, time_start=interval_start - 1, time_end=interval_end, exclude_gaps=True, cur=cur
                        )
                        if valid_rows:
                            self.logger.warning(
                                f'remove_older_: {itempath} interval at {interval_start} has {valid_rows} '
                                f"valid rows but action '{action}' produced no value (all durations NULL?) - "
                                f'leaving interval raw'
                            )
                            stalled = True
                            break

                    # Re-anchor before delete: moving to interval_end makes the delete below
                    # (time < interval_end) naturally skip it - value/quality untouched.
                    if open_is_live:
                        self._log_store.reanchor_open(item_id, open_time, interval_end, cur=cur)

                    # delete before insert: interval_start is derived from
                    # the oldest raw row's own timestamp, so a raw row can
                    # legally sit at exactly that timestamp - inserting
                    # the aggregate there first would collide with the
                    # (item_id, time) unique constraint. Both statements
                    # still share one transaction, so a crash between them
                    # can never leave a duplicate aggregate behind on the
                    # next run's self-healing resume.
                    self._log_store.delete_range(item_id, time_start=interval_start - 1, time_end=interval_end, cur=cur)
                    if value is not None:
                        now_ms = self._timestamp(self.shtime.now())
                        entry = BufferEntry(
                            time=interval_start, duration=interval_ms, value=value, quality=QUALITY_VALID
                        )
                        self._log_store.insert(item_id, entry, item_type, now_ms, cur=cur)
            except TimeoutError:
                self.logger.info(
                    f'remove_older_: {itempath} could not acquire database lock, giving up this compaction cycle'
                    f'{self._db.lock_holder_description()}'
                )
                connection_failed = True
                break
            except Exception as e:
                # transaction() already rolled back and reset connection
                # state - the interval stays raw, exactly like the
                # TimeoutError case above, and the next cycle's oldest_time()
                # picks it back up unchanged. A connection error here is the
                # same self-healing case _dump() already handles quietly;
                # anything else is a real bug worth the loud ERROR - same
                # exc_info=True traceback _dump() already gives that case,
                # since this runs on every scheduler cycle just as often.
                self._log_db_exception(
                    e, f'remove_older_: {itempath} compaction failed, giving up this cycle: {e}', exc_info=True
                )
                connection_failed = True
                break

            intervals_done += 1

        if intervals_done:
            self.logger.info(
                f"remove_older_: {itempath} compacted {intervals_done} interval(s) using action='{action}'"
            )

        # more intervals might already be past the cutoff but weren't
        # reached this cycle (max_aggregate_intervals) - requeue like the
        # delete path does. If we stopped because the next interval isn't
        # past the cutoff yet, this correctly does not requeue. A stalled
        # interval (left raw above) blocks everything behind it - requeuing
        # would just spin on it within the same cycle.
        if connection_failed:
            # Can't reliably tell if there's more work without querying the
            # DB again, which is exactly what just failed - requeue
            # unconditionally so this item is retried next cycle rather
            # than waiting for the worklist to rotate all the way around.
            self._maxage_worklist.append(item)
        else:
            oldest = self._log_store.oldest_time(item_id)
            if not stalled and oldest is not None and oldest + interval_ms <= cutoff_ms:
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
            try:
                new_must_keep_timestamp = self.readLatestLog(item_id, timestamp_end)
            except Exception as e:
                # Can't safely proceed without this - deleting blind here
                # risks wiping an item's last remaining value. Requeue and
                # retry next cycle, same as every other connection-loss path
                # in this function.
                self._log_db_exception(
                    e,
                    f'remove_older_: {itempath} could not read latest log entry, retrying next cycle: {e}',
                    exc_info=True,
                )
                self._maxage_worklist.append(item)
                return
            if new_must_keep_timestamp is None:
                return
            new_must_keep_time = self._datetime(new_must_keep_timestamp)
            self.logger.info(
                f'remove_older_: {itempath} no remaining log entry between {time_end} and now, thus can not remove log entries older than maxage, latest log is {new_must_keep_time}'
            )
            time_end = new_must_keep_time + datetime.timedelta(microseconds=-1)
            timestamp_end = self._timestamp(time_end)

        # readLogCount's time_end is inclusive (time <= time_end) but
        # deleteLog()/delete_range's is exclusive (time < time_end) - the
        # "- 1" (timestamps are integer ms) makes this count match exactly
        # what the deletion below will remove; without it, a log entry
        # landing exactly on timestamp_end would be counted here but left
        # behind by the actual DELETE.
        count_log_records_to_delete = self.readLogCount(item_id, time_end=timestamp_end - 1)
        count_log_records_to_delete_str = f'{count_log_records_to_delete:,}'.replace(',', '.')
        max_delete_logentries_str = f'{self.max_delete_logentries:,}'.replace(',', '.')
        time_end_str = time_end.strftime('%d.%m.%Y - %H:%M')
        self.logger.debug(
            f'remove_older_: {itempath} remove older than {time_end_str} - {count_log_records_to_delete_str} records to delete'
        )

        if count_log_records_to_delete > self.max_delete_logentries:
            time_start_deletion = time.time()
            # transaction() commits this DELETE itself, rather than relying
            # on some unrelated later commit()
            # Not a bare DELETE...ORDER BY...LIMIT (invalid SQLite syntax
            # without a non-default compile flag) or a rowid-subquery (the
            # {log} table has no primary key, and MySQL/MariaDB - unlike
            # SQLite - has no queryable row id for a table without one).
            # Matches on (item_id, time) instead, via the UNIQUE KEY
            # Double-wrapped, not single-wrap: MariaDB separately rejects
            # LIMIT directly inside an IN(subquery).
            try:
                with self._db.transaction(timeout=300) as cur:
                    self._execute(
                        self._prepare(
                            'DELETE FROM {log} WHERE item_id = :id AND time IN (SELECT time FROM '
                            '(SELECT time FROM {log} WHERE item_id = :id ORDER BY time ASC LIMIT :maxrecords) '
                            'AS del_batch);'
                        ),
                        {'id': item_id, 'maxrecords': self.max_delete_logentries},
                        cur=cur,
                    )
            except TimeoutError:
                self.logger.info(
                    f'remove_older_: {itempath} could not acquire database lock for deletion, retrying next cycle'
                    f'{self._db.lock_holder_description()}'
                )
                self._maxage_worklist.append(item)
                return
            except Exception as e:
                # Same self-healing case as _compact_maxage()'s equivalent
                # except-block - requeue so this item's batch delete is
                # retried next cycle instead of waiting for the worklist to
                # rotate all the way around. Same exc_info=True convention
                # as that block too, for the same reason.
                self._log_db_exception(
                    e, f'remove_older_: {itempath} deletion failed, retrying next cycle: {e}', exc_info=True
                )
                self._maxage_worklist.append(item)
                return
            time_used_for_deletion = time.time() - time_start_deletion
            self.logger.info(
                f'remove_older_: {itempath} deleted {max_delete_logentries_str} of {count_log_records_to_delete_str} log entries - took {time_used_for_deletion:.2f} seconds, averaging {100 * time_used_for_deletion / self.max_delete_logentries:.4f} seconds per 100 entries'
            )

            # Re-Add item to worklist, since there are more records to be deleted
            self._maxage_worklist.append(item)

        elif count_log_records_to_delete:
            time_start_deletion = time.time()
            self.deleteLog(item_id, time_end=timestamp_end)
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
        ``os.getcwd()`` *at call time* — not once, at startup. Changing pwd
        during shng runtime can throw this off.

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

    def _extract_connect_value(self, connect, key):
        """Look up a single key's value from the 'connect' parameter.

        Mirrors lib.db.Database.__init__()'s own parsing rather than
        assuming one specific shape - connect may be a list of 'key:value'
        strings, a list of dict/OrderedDict entries (as the YAML loader
        produces), or a plain dict.

        :param connect: raw 'connect' parameter, in any of the above shapes
        :param key: key to look up (e.g. 'database')
        :return: the value as a string, or '' if not found
        """
        if isinstance(connect, dict):
            return str(connect.get(key, ''))
        if isinstance(connect, list) and connect:
            if isinstance(connect[0], dict):
                for item in connect:
                    if key in item:
                        return str(item[key])
            elif isinstance(connect[0], str):
                for entry in connect:
                    k, sep, value = entry.partition(':')
                    if sep and k.strip() == key:
                        return value.strip()
        return ''

    def _log_db_exception(self, e, msg, db=None, fallback=None, exc_info=False):
        """Log a caught database exception at a level matching its actual cause.

        A connection error (lost/refused/reset connection) is anticipated -
        logged at info. Anything else is a real bug, logged via `fallback`
        (default: error). `exc_info` attaches a traceback, but only for that
        unclassified case - a connection error's own message already says
        what happened.

        :param e: The caught exception.
        :param msg: Message to log.
        :param db: Database instance to classify against (default: self._db).
        :param fallback: Logger method for the non-connection-error case (default: self.logger.error).
        :param exc_info: Whether to attach a traceback for the non-connection-error case.
        """
        db = db or self._db
        is_conn_err = db.is_connection_error(e)
        level = self.logger.info if is_conn_err else (fallback or self.logger.error)
        level(msg, exc_info=exc_info and not is_conn_err)

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

    def _execute(self, query, params, cur=NO_CURSOR):
        return self._query(self._db.execute, query, params, cur)

    def _fetchone(self, query, params=None, cur=NO_CURSOR):
        tuples = self._query(self._db.fetchone, query, params or {}, cur)
        return tuples

    def _fetchall(self, query, params=None, cur=NO_CURSOR):
        tuples = self._query(self._db.fetchall, query, params or {}, cur)
        return None if tuples is None else list(tuples)

    def _query(self, func, query, params, cur=NO_CURSOR):
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
        owns_cur = cur is NO_CURSOR
        prepared = self._prepare(query)  # prepare once

        def _log_query_error(e):
            if self.logger.isEnabledFor(logging.DEBUG):
                query_readable = re.sub(r':([a-z_]+)', r'{\1}', prepared).format(**params)
                msg = 'Database: Error for query {}: {}'.format(query_readable, e)
            else:
                msg = 'Database: Query error: {}'.format(e)
            self._log_db_exception(e, msg)

        if owns_cur:
            # On lock timeout: log and return None, not an exception -
            # callers throughout this file treat a None result as
            # "query failed", not something to catch.
            # retry kept low - see Database.verify()'s docstring cost note.
            if self._db.verify(2) == 0:
                # Same reasoning as id()'s equivalent check: verify() failing
                # to reconnect after active probing IS the connection-trouble
                # case by construction, no exception to classify against.
                self.logger.info(
                    'Database: Connection not recovered ({}){}'.format(
                        self._db.last_verify_reason(), self._db.lock_holder_description()
                    )
                )
                return None
            try:
                with self._db.transaction() as tcur:
                    tuples = func(prepared, params, cur=tcur)
            except TimeoutError:
                self.logger.error(
                    "Database: Can't query due to fail to acquire lock{}".format(self._db.lock_holder_description())
                )
                return None
            except Exception as e:
                # We own this transaction end-to-end - transaction() already
                # rolled back and reset connection state before this
                # exception reached us, so returning None here (same as the
                # TimeoutError case above) is safe: nothing above us needed
                # this exception to trigger its own cleanup.
                _log_query_error(e)
                return None
        else:
            # Caller passed their own cur - they own the transaction and
            # need to see this exception, so THEIR transaction() block
            # rolls back correctly instead of committing over a dead
            # connection. Log then re-raise, don't swallow.
            try:
                tuples = func(prepared, params, cur=cur)
            except Exception as e:
                _log_query_error(e)
                raise e

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
