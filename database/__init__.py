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
import re
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

from .constants import *
from .webif import WebInterface


class Database(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = '1.6.8'

    # SQL queries: {item} = item table name, {log} = log table name
    # time, item_id, val_str, val_num, val_bool, changed
    _setup = {
        '1': [
            "CREATE TABLE {log} (time BIGINT, item_id INTEGER, duration BIGINT, val_str TEXT, val_num REAL, val_bool BOOLEAN, changed BIGINT);",
            "DROP TABLE {log};"],
        '2': [
            "CREATE TABLE {item} (id INTEGER, name varchar(255), time BIGINT, val_str TEXT, val_num REAL, val_bool BOOLEAN, changed BIGINT);",
            "DROP TABLE {item};"],
        '3': ["CREATE UNIQUE INDEX {log}_{item}_id_time ON {log} (item_id, time);", "DROP INDEX {log}_{item}_id_time;"],
        '4': ["CREATE INDEX {log}_{item}_id_changed ON {log} (item_id, changed);",
              "DROP INDEX {log}_{item}_id_changed;"],
        '5': ["CREATE UNIQUE INDEX {item}_id ON {item} (id);", "DROP INDEX {item}_id;"],
        '6': ["CREATE INDEX {item}_name ON {item} (name);", "DROP INDEX {item}_name;"]
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
        self._prefix = self.get_parameter_value('prefix')
        if self._prefix is None:
            self._prefix = ''
        if self._prefix != '':
            self._prefix += '_'
        self._dump_cycle = self.get_parameter_value('cycle')
        self._removeold_cycle = self.get_parameter_value('removeold_cycle')
        if self._removeold_cycle == self._dump_cycle:
            self._removeold_cycle += 2
        self._precision = self.get_parameter_value('precision')
        self.count_logentries = self.get_parameter_value('count_logentries')
        self.max_delete_logentries = self.get_parameter_value('max_delete_logentries')
        self._default_maxage = float(self.get_parameter_value('default_maxage'))

        self._copy_database = self.get_parameter_value('copy_database')
        self._copy_database_name = self.get_parameter_value('copy_database_name')

        self.webif_pagelength = self.get_parameter_value('webif_pagelength')
        self._webdata = {}

        self._replace = {table: table if self._prefix == "" else self._prefix + table for table in ["log", "item"]}
        self._replace['item_columns'] = ", ".join(COL_ITEM)
        self._replace['log_columns'] = ", ".join(COL_LOG)
        self._buffer = {}
        self._buffer_lock = threading.Lock()
        self._dump_lock = threading.Lock()

        self.skipping_dump = False
        self._remove_older_skipped = False
        self.lock_remove_older = False

        self.orphanlist = []                    # list with item names of orphant database entries
        self._orphan_logcount = {}              # dict to store the number of log records for an orphan
        self.remove_orphan = False              # set to True to remove orphans during remove_older
        self.delete_orphan_chunk_size = 20000   # Delete x log entries for orphan items at a time
        self._handled_items = []                # items that have a 'database' attribute set
        self._items_with_maxage = []            # items that have a 'database_maxage' attribute set
        self._maxage_worklist = []              # work copy of self._items_with_maxage
        self._item_logcount = {}                # dict to store the number of log records for an item
        self._items_total_entries = 0           # total number of log entries
        self._items_still_counting = False      # total number of log entries

        self.cleanup_active = False

        self.last_connect_time  = 0     # mechanism for limiting db connection requests

        # Copy SQLite3 database file (if configured)
        if self._copy_database:
            self.copy_databasefile()

        # Setup db and test if connection is possible
        self._db = lib.db.Database(("" if self._prefix == ""  else self._prefix.capitalize()) + "Database", self.driver, self._connect)
        if self._db.api_initialized == False:
            # Error initializeng the database driver (e.g.: Python module for database driver not found)
            self.logger.error("Initialization of database API failed")
            self._init_complete = False
            return

        self._db_initialized = False
        if not self._initialize_db():
            #self._init_complete = False
            #return
            self.logger.debug("Init: DB could not be initialized")
            pass

        self.init_webinterface(WebInterface)
        return


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self._initialize_db()
        self.build_orphanlist(True)
        self._start_schedulers()
        self.alive = True


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False
        self._stop_schedulers()
        self._dump(True)
        self._db.close()


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
        if self.has_iattr(item.conf, 'database'):
            self._webdata.update({item.id(): {}})
            self._handled_items.append(item)
            if self.has_iattr(item.conf, 'database_maxage'):
                maxage = self.get_iattr_value(item.conf, 'database_maxage')
                if float(maxage) > 0:
                    #if self.get_iattr_value(item.conf, 'database') == 'init':
                    #    self.logger.warning(f"Item {item.id()} configured with database_maxage and init could lead to no values in DB for initialization.")

                    self._items_with_maxage.append(item)

            self.logger.debug(item.conf)
            self._buffer_insert(item, [])
            item.series = functools.partial(self._series, item=item.id())  # Zur Nutzung im Websocket Plugin
            item.db = functools.partial(self._single, item=item.id())      # Nie genutzt??? -> Doch
            item.dbplugin = self                                           # genutzt zum Zugriff auf die Plugin Instanz z.B. durch Logiken
            if self._db_initialized and self.get_iattr_value(item.conf, 'database').lower() == 'init':
                if not self._db.lock(5):
                    self.logger.error("Can not acquire lock for database to read value for item {}".format(item.id()))
                    return
                cur = self._db.cursor()
                cache = self.readItem(str(item.id()), cur=cur)
                if cache is not None:
                    try:
                        value = self._item_value_tuple_rev(item.type(), cache[COL_ITEM_VAL_STR:COL_ITEM_VAL_BOOL + 1])
                        last_change = self._datetime(cache[COL_ITEM_TIME])
                        prev_change = self._fetchone('SELECT MAX(time) from {log} WHERE item_id = :id',
                                                     {'id': cache[COL_ITEM_ID]}, cur=cur)
                        if (value is not None) and (prev_change is not None) and (prev_change[0] is not None):
                            # Add item specific debugging here:
                            #if item.id() == 'xyz':
                            #    self.logger.debug(f"Parse item: ItemID: {item.id()}: {value}, {self._datetime(prev_change[0])}, {last_change}")
                            self._webdata[item.id()].update({'last_change': last_change.isoformat()})
                            self._webdata[item.id()].update({'value': value})
                            self._webdata[item.id()].update({'type': item.property.type})
                            item.set(value, 'Database', source='DBInit', prev_change=self._datetime(prev_change[0]), last_change=last_change)
                        else:
                            self.logger.warning(f"Debug init for item {item.id()}: {value}, {prev_change}, {prev_change[0]}")
                        if value is not None and self.get_iattr_value(item.conf, 'database_acl') is not None and self.get_iattr_value(item.conf, 'database_acl').lower() == 'ro':
                            #self.logger.debug(f"DEBUG: Parse item, doing buffer insert for ItemID: {item.id()}: {value}, databse_acl {self.get_iattr_value(item.conf, 'database_acl').lower()}")
                            self._buffer_insert(item, [(self._timestamp(self.shtime.now()), None, value)])
                    except Exception as e:
                        self.logger.error("Reading cache value from database for {} failed: {}".format(item.id(), e))
                else:
                    self.logger.warning("Cache not available in database for item {}".format(item.id() ))
                cur.close()
                self._db.release()
            elif self.get_iattr_value(item.conf, 'database').lower() == 'init':
                self.logger.warning("Db not initialized. Cannot read database value for item {}".format(item.id()))
            else:
                self._webdata[item.id()].update({'value': item.property.value})
                self._webdata[item.id()].update({'type': item.property.type})

            return self.update_item
        else:
            return None


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        #if 'xxx' in logic.conf:
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
        #if item.property.path.startswith('test.'):
        #if item.id() == 'xyz':
        #    self.logger.warning(f"Debug: updateItem, ItemID: {item.id()}: {item()}, {caller}, {dest}")
        #    debug_item = True

        #Determine if item is read/write or read-only:
        if self.has_iattr(item.conf, 'database_acl'):
            acl = self.get_iattr_value(item.conf, 'database_acl').lower()
            self.logger.debug("item '{}', database_acl = {}".format(item,  acl))
        else:
            acl = 'rw'

        if acl == 'rw':
            start = self._timestamp(item.prev_change())
            end = self._timestamp(item.last_change())
            if end - start < 0:
                self.logger.warning("Negative duration: start: {0}, end {1}, prevChange: {2}, lastChange: {3}, item: {4}".format(start , end, item.prev_change(), item.last_change(), item ))

            # Determine, if DB buffer has a valid "last" value:
            if len(self._buffer[item]) == 0 or self._buffer[item][-1][1] is not None:
                last = None
            else:
                last = self._buffer[item][-1]

            if debug_item:
                self.logger.warning(f"Debug: last {last}, len buffer_item {len(self._buffer[item])}, buffer_item {self._buffer[item]}")

            # Update the DB buffer:
            if last:
                # Step 1a): Alter current value with updated duration:
                if debug_item:
                    self.logger.warning(f"Debug 1a): Rewriting valid last value, start: {last[0]}, duration: {end - start}, value: {last[2]} to item '{item}'.")
                self._buffer[item][-1] = (last[0], end - start, last[2])
            else:
		# Step 1b): Append new value with none duration

                #If item is configured to be initialized via database init (see database: init in item.yaml), do not update previous value if the latter qual to the regular initial_value.
                # This is because configuring database: init aims at avoiding the regular item initial value to appear inside the DB:
                if self.get_iattr_value(item.conf, 'database').lower() == 'init' and item.property.prev_change_by =='Init:Initial_Value':
                    if debug_item:
                        self.logger.warning(f"Debug 1b): Do not append previous value as it was set by Initial_Value")
                else:
                    if debug_item:
                        self.logger.warning(f"Debug 1b): Appending prev_value: start: {start}, duration: {end-start}, prev_value: {item.prev_value()} to item '{item}'")
                    self._buffer[item].append((start, end - start, item.prev_value()))

            # Step 2: Add current value with duration "none" to DB buffer. This entry is "none" because the duration cannot be determined yet as it's duration has not finished
            if debug_item:
                self.logger.warning(f"Debug 2): Appending current value: start {end}, value {item()} to item '{item}'")

            self._buffer[item].append((end, None, item()))
        else:
            self.logger.debug("Not writing item '{}' value because database_acl = {}".format(item,  acl))


    def _start_schedulers(self):
        """
        Start jobs that maintain buffer and database
        """
        if self.count_logentries:
            self.scheduler_add('Count logs', self._count_logentries, cycle=6*3600, prio=6)
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
            self.logger.warning("Copying of database fie is only possible for SQLite3 databases")
            param_dict = {"copy_database": False}
            self.update_config_section(param_dict)
            return

        # get source and destination names
        try:
            database_name = self._connect[0]
            database_name = database_name[9:].strip()
        except:
            database_name = ''

        # copy the database file
        self.logger.warning( f"Starting to copy SQLite3 database file from {database_name} to {self._copy_database_name}")
        import shutil
        try:
            shutil.copy2(database_name, self._copy_database_name)
            self.logger.warning("Finished copying SQLite3 database file")
        except Exception as e:
            self.logger.Error( f"Error copying SQLite3 database file: {e}")

        param_dict = {"copy_database": False}
        self.update_config_section(param_dict)
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
            item_path = str(item.id())
        except:
            item_path = item
        try:
            id = self.readItem(item_path, cur=cur)
        except Exception as e:
            self.logger.warning(f"id(): No id found for item {item_path} - Exception {e}")
            id = None

        if id is None and create == True:
            id = [self.insertItem(item.id(), cur)]

        if (id is None) or (COL_ITEM_ID >= len(id)) :
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
            item_path = str(item.id())
        except:
            item_path = item
        try:
            row = self.readItem(item_path, cur=None)
        except Exception as e:
            self.logger.warning(f"db_itemtype: No id found for item {item_path} - Exception {e}")
            row = None

        if (row is None) or (COL_ITEM_ID >= len(row)) :
            return None

        id = int(row[COL_ITEM_ID])
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
        :param cur: A database cursor object if available (optional)

        :return: id of the item within the database
        :rtype: int | None
        """

        try:
            item_path = str(item.id())
        except:
            item_path = item
        try:
            row = self.readItem(item_path, cur=None)
        except Exception as e:
            self.logger.warning(f"db_lastchange: No id found for item {item_path} - Exception {e}")
            row = None

        if (row is None) or (COL_ITEM_ID >= len(row)):
            return None

        id = int(row[COL_ITEM_ID])
        last_change = row[COL_ITEM_TIME]
        return self._datetime(last_change)


    def db(self):
        """
        Returns the low-level database object

        This is a public function of the plugin

        :return: Database object
        :rtype: object
        """
        return self._db


    def dump(self, dumpfile, id=None, time=None, time_start=None, time_end=None, changed=None, changed_start=None,
             changed_end=None, cur=None):
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
        self.logger.info("Starting file dump to {} ...".format(dumpfile))

        item_ids = self.readItems(cur=cur) if id is None else [self.readItem(id, cur=cur)]

        s = ';'
        h = ['item_id', 'item_name', 'time', 'duration', 'val_str', 'val_num', 'val_bool', 'changed', 'time_date',
             'changed_date']
        f = open(dumpfile, 'w')
        f.write(s.join(h) + "\n")
        for item in item_ids:
            self.logger.debug("... dumping item {}/{}".format(item[1], item[0]))

            rows = self.readLogs(item[0], time=time, time_start=time_start, time_end=time_end, changed=changed,
                                 changed_start=changed_start, changed_end=changed_end, cur=cur)

            for row in rows:
                cols = []
                for key in [COL_ITEM_ID, COL_ITEM_NAME]:
                    cols.append(item[key])
                for key in [COL_LOG_TIME, COL_LOG_DURATION, COL_LOG_VAL_STR, COL_LOG_VAL_NUM, COL_LOG_VAL_BOOL,
                            COL_LOG_CHANGED]:
                    cols.append(row[key])
                for key in [COL_ITEM_ID, COL_LOG_CHANGED]:
                    cols.append('' if row[key] is None else datetime.datetime.fromtimestamp(row[key] / 1000.0))
                cols = map(lambda col: '' if col is None else col, cols)
                cols = map(lambda col: str(col) if not '"' in str(col) else col.replace('"', '\\"'), cols)
                f.write(s.join(cols) + "\n")
        f.close()
        self.logger.info("File dump completed ({} items) ...".format(len(item_ids)))
        return


    def sqlite_dump(self, dumpfile):

        if self.driver.lower() != 'sqlite3':
            self.logger.warning("SQL dump is only possible for sqlite3 databases")
            return False

        self.logger.info(f"Starting SQL file dump of the sqlite3 database to {dumpfile} ...")

        with open(dumpfile, 'w') as f:
            for line in self._db._conn.iterdump():
                f.write(f"{line}\n")

        self.logger.info("SQL file dump of sqlite3 database completed")
        return True


    def insertItem(self, name, cur=None):
        """
        Create database item record for given database ID

        This is a public function of the plugin

        :param name: name of item to create a record for
        :param cur: A database cursor object if available (optional)

        :return: ID within the database
        :rtype: int
        """
        id = self._fetchone("SELECT MAX(id) FROM {item};", cur=cur)
        self._execute(self._prepare("INSERT INTO {item}(id, name) VALUES(:id, :name);"),
                      {'id': 1 if id[0] == None else id[0] + 1, 'name': name}, cur=cur)
        id = self._fetchone("SELECT id FROM {item} where name = :name;", {'name': name}, cur=cur)
        return int(id[0])


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
        params = {'id': id, 'time': time, 'changed': changed}
        params.update(self._item_value_tuple(it, val))
        self._execute(self._prepare(
            "UPDATE {item} SET time = :time, val_str = :val_str, val_num = :val_num, val_bool = :val_bool, changed = :changed WHERE id = :id;"),
            params, cur=cur)


    def readItem(self, id, cur=None):
        """

        This is a public function of the plugin

        :param id: Id of the item within the database
        :param cur: A database cursor object if available (optional)

        :return: Data for the selected item
        """
        params = {'id': id}
        if type(id) == str:
            return self._fetchone("SELECT {item_columns} from {item} WHERE name = :id;", params, cur=cur)
        return self._fetchone("SELECT {item_columns} from {item} WHERE id = :id;", params, cur=cur)


    def readItems(self, cur=None):
        """
        Read database item records

        This is a public function of the plugin

        :param cur: A database cursor object if available (optional)

        :return: selected items
        """
        return self._fetchall("SELECT {item_columns} from {item};", cur=cur)


    def readItemCount(self, cur=None):
        """
        Read database log count for given database ID

        This is a public function of the plugin

        :param cur: A database cursor object if available (optional)

        :return: Number of log records for the database ID
        """
        if self._db.connected():
            params = {}
            return self._fetchall("SELECT count(*) FROM {item};", params, cur=cur)[0][0]
        return '-'


    def deleteItem(self, id, cur=None):
        """
        Delete database item record for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to delete the record for
        :param cur: A database cursor object if available (optional)
        """
        params = {'id': id}
        self.deleteLog(id, cur=cur)
        self._execute(self._prepare("DELETE FROM {item} WHERE id = :id;"), params, cur=cur)


    def insertLog(self, id, time, duration=0, val=None, it=None, changed=None, cur=None):
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
        """
        params = {'id': id, 'time': time, 'changed': changed, 'duration': duration}
        params.update(self._item_value_tuple(it, val))
        self._execute(self._prepare(
            "INSERT INTO {log}(item_id, time, val_str, val_num, val_bool, duration, changed) VALUES (:id,:time,:val_str,:val_num,:val_bool,:duration,:changed);"),
            params, cur=cur)
        return


    def updateLog(self, id, time, duration=0, val=None, it=None, changed=None, cur=None):
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
        """
        params = {'id': id, 'time': time, 'changed': changed, 'duration': duration}
        params.update(self._item_value_tuple(it, val))
        self._execute(self._prepare(
            "UPDATE {log} SET duration = :duration, val_str = :val_str, val_num = :val_num, val_bool = :val_bool, changed = :changed WHERE item_id = :id AND time = :time;"),
            params, cur=cur)
        return


    def readLog(self, id, time, cur=None):
        """
        Read database log record for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to read the record for
        :param time: Time for the given value
        :param cur: A database cursor object if available (optional)

        :return: Log record for the database ID
        """
        params = {'id': id, 'time': time}
        return self._fetchall("SELECT {log_columns} FROM {log} WHERE item_id = :id AND time = :time;", params, cur=cur)


    def readLogs(self, id, time=None, time_start=None, time_end=None, changed=None, changed_start=None,
                 changed_end=None, cur=None):
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
        condition, params = self._slice_condition(id, time=time, time_start=time_start, time_end=time_end,
                                                  changed=changed, changed_start=changed_start, changed_end=changed_end)
        return self._fetchall("SELECT {log_columns} FROM {log} WHERE " + condition, params, cur=cur)


    def readOldestLog(self, id, cur=None):
        """
        Read the time of oldest log record for given database ID

        This is a public function of the plugin

        :param id: Database ID of item to read the record for
        :param cur: A database cursor object if available (optional)

        :return: Time of oldest log record for the database ID
        """
        params = {'id': id}
        return self._fetchall("SELECT min(time) FROM {log} WHERE item_id = :id;", params, cur=cur)[0][0]


    def readLatestLog(self, id, time=None, cur=None):
        """
        Read the time of latest log record for given database ID and if time given up to this time

        This is a public function of the plugin

        :param id: Database ID of item to read the record for
        :param time: a maximum timestamp for the given value
        :param cur: A database cursor object if available (optional)

        :return: Log record for the database ID
        """
        if time is None:
            params = {'id': id}
            return self._fetchall("SELECT max(time) FROM {log} WHERE item_id = :id;", params, cur=cur)[0][0]
        else:
            params = {'id': id, 'time': time}
            return self._fetchall("SELECT max(time) FROM {log} WHERE item_id = :id AND time <= :time", params, cur=cur)[0][0]


    def readTotalLogCount(self, id=None, time_start=None, time_end=None, cur=None):
        """
        Read database log count for the hole database

        :param id:
        :param time_start:
        :param time_end:
        :param cur:

        :return: Number of log records
        """
        params = {'id': id, 'time_start': time_start, 'time_end': time_end}
        result = self._fetchall("SELECT count(*) FROM {log};", params, cur=cur)
        if result == []:
            return 0
        return result[0][0]


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
            result = self._fetchall("SELECT count(*) FROM {log} WHERE item_id = :id;", params, cur=cur)
        elif time_start is None:
            result = self._fetchall("SELECT count(*) FROM {log} WHERE item_id = :id AND time <= :time_end;", params, cur=cur)
        elif time_end is None:
            result = self._fetchall("SELECT count(*) FROM {log} WHERE item_id = :id AND time >= :time_start;", params, cur=cur)
        else:
            result = self._fetchall("SELECT count(*) FROM {log} WHERE item_id = :id AND time >= :time_start AND time <= :time_end;", params, cur=cur)
        if result == []:
            return 0
        if result is None:
            return 0
        try:
            return result[0][0]
        except Exception as e:
            self.logger.error("readLogCount: result={} - Exception: {}".format(result, e))
        return 0


    def deleteLog(self, id, time=None, time_start=None, time_end=None, changed=None, changed_start=None,
                  changed_end=None, cur=None, with_commit=True):
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
        condition, params = self._slice_condition(id, time=time, time_start=time_start, time_end=time_end,
                                                  changed=changed, changed_start=changed_start, changed_end=changed_end)
        try:
            self._execute(self._prepare("DELETE FROM {log} WHERE " + condition), params, cur=cur)
            if with_commit:
                self._db.commit()
        except Exception as e:
            self.logger.error("Exception in function deleteLog: {}".format(e))
            self._db.rollback()

        try:
            self._item_logcount[id] = self.readLogCount(id)
        except Exception as e:
            self.logger.error("Exception in function deleteLog during readLogCount: {}".format(e))

        return


    def build_orphanlist(self, log_activity=False):
        """
        Create a list of database entries which have no corresponding item in the item tree

        called by run() once on start

        :return:
        """
        if log_activity:
            self.logger.info("build_orphan_list: Started")
        self.orphanitemlist = []
        self.orphanlist = []

        items = [item.id() for item in self._buffer]
        cur = self._db.cursor()
        try:
            for item in self.readItems(cur=cur):
                if item[COL_ITEM_NAME] not in items:
                    if log_activity:
                        self.logger.info(f"- Found data for item w/o database attribute: {item[COL_ITEM_NAME]}")
                    self.orphanitemlist.append(item)
                    self.orphanlist.append(item[COL_ITEM_NAME])
        except Exception as e:
            self.logger.error("Database build_orphan_list failed: {}".format(e))
        cur.close()
        self._count_orphanlogentries()
        if log_activity:
            self.logger.info("build_orphan_list: Finished")

        return


    def _count_orphanlogentries(self):
        """
        count number of log entries for all items in database

        to be called by eval syntax checker
        """
        self.logger.info("_count_orphanlogentries: # orphan items = {}".format(len(self.orphanlist)))
        self._items_total_entries = 0
        for item in self.orphanlist:
            item_id = self.id(item, create=False)
            logcount = self.readLogCount(item_id)
            logcount_str = f"{logcount:,}".replace(',','.')
            self.logger.info(f"Orphan {item} (id={item_id}): {logcount_str} entries")
            self._orphan_logcount[item_id] = logcount

        return


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
            self.logger.info(f"_delete_orphan: Item {item_path} has no log entries")
            cur = self._db.cursor()
            self._execute(self._prepare("DELETE FROM {item} WHERE id = :id;"), {'id': item_id}, cur=cur)
            self.logger.info(f"_delete_orphan: Deleted item entry for {item_path}")
            cur.close()
            return True

        cur = self._db.cursor()
        self._execute(self._prepare("DELETE FROM {log} WHERE item_id = :id ORDER BY time ASC LIMIT :maxrecords;"), {'id': item_id, 'maxrecords': self.delete_orphan_chunk_size}, cur=cur)
        delete_orphan_chunk_size_str = f"{self.delete_orphan_chunk_size:,}".replace(',', '.')
        self.logger.info(f"_delete_orphan: Deleted (up to) {delete_orphan_chunk_size_str} log entries for Item {item_path}")
        cur.close()

        return False


    def remove_orphan_items(self):
        """
        Delete item and logdata of items that have no correspondance in itemtree
        """
        if len(self.orphanlist) == 0:
            self.build_orphanlist()

        item = self.orphanlist.pop(0)
        if not self._delete_orphan(item):
            self.orphanlist.append(item)

        if len(self.orphanlist) == 0:
            self.remove_orphan = False
            self.logger.info("remove_orphan_items: Database cleanup finished")

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
        self.logger.info("Database cleanup started (removal of entries without defined item)")
        return


    def _slice_condition(self, id, time=None, time_start=None, time_end=None, changed=None,
                         changed_start=None, changed_end=None):
        params = {
            'id': id,
            'time': time, 'time_flag': 1 if time == None else 0,
            'time_start': time_start, 'time_start_flag': 1 if time_start == None else 0,
            'time_end': time_end, 'time_end_flag': 1 if time_end == None else 0,
            'changed': changed, 'changed_flag': 1 if changed == None else 0,
            'changed_start': changed_start, 'changed_start_flag': 1 if changed_start == None else 0,
            'changed_end': changed_end, 'changed_end_flag': 1 if changed_end == None else 0
        }

        condition = "(item_id = :id                                      ) AND " + \
                    "(time    = :time          OR 1 = :time_flag         ) AND " + \
                    "(time    > :time_start    OR 1 = :time_start_flag   ) AND " + \
                    "(time    < :time_end      OR 1 = :time_end_flag     ) AND " + \
                    "(changed = :changed       OR 1 = :changed_flag      ) AND " + \
                    "(changed > :changed_start OR 1 = :changed_start_flag) AND " + \
                    "(changed < :changed_end   OR 1 = :changed_end_flag  );    "
        return (condition, params)


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
        #self.logger.warning("_series: item={}, func={}, start={}, end={}, count={}".format(item, func, start, end, count))
        init = not update
        if sid is None:
            sid = item + '|' + func + '|' + str(start) + '|' + str(end) + '|' + str(count)
        func, expression = self._expression(func)
        queries = {
            'avg': 'MIN(time), ' + self._precision_query('AVG(val_num * duration) / AVG(duration)'),
            'avg.order': 'ORDER BY time ASC',
            'integrate': 'MIN(time), SUM(val_num * duration)',
            'differentiate': 'MIN(time), (val_num - LAG(val_num,1, -1)) / duration',
            'count': 'MIN(time), SUM(CASE WHEN val_num{op}{value} THEN 1 ELSE 0 END)'.format(**expression['params']),
            'countall': 'MIN(time), COUNT(*)',
            'min': 'MIN(time), MIN(val_num)',
            'max': 'MIN(time), MAX(val_num)',
            'on': 'MIN(time), ' + self._precision_query('SUM(val_bool * duration) / SUM(duration)'),
            'on.order': 'ORDER BY time ASC',
            'sum': 'MIN(time), SUM(val_num)',
            'raw': 'time, val_num',
            'raw.order': 'ORDER BY time ASC',
            'raw.group': ''
        }
        if func not in queries:
            raise NotImplementedError

        order = '' if func + '.order' not in queries else queries[func + '.order']
        group = 'GROUP BY ROUND(time / :step)' if func + '.group' not in queries else queries[func + '.group']
        logs = self._fetch_log(item, queries[func], start, end, step=step, count=count, group=group, order=order)
        tuples = logs['tuples']
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
            'cmd': 'series', 'series': tuples, 'sid': sid,
            'params': {'update': True, 'item': item, 'func': func, 'start': logs['iend'], 'end': end,
                       'step': logs['step'], 'sid': sid},
            'update': self.shtime.now() + datetime.timedelta(seconds=int(logs['step'] / 1000))
        }
        #self.logger.warning("_series: result={}".format(result))
        return result


    def _single(self, func, start, end='now', item=None):
        """
        As far as it has been checked, this method is never called.
        It is attached to the item object but no other plugin is known that calls this method.

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
            'differentiate': 'val_num - LAG(val_num) / duration',
            'count': 'SUM(CASE WHEN val_num{op}{value} THEN 1 ELSE 0 END)'.format(**expression['params']),
            'countall': 'COUNT(*)',
            'min': 'MIN(val_num)',
            'max': 'MAX(val_num)',
            'on': self._precision_query('SUM(val_bool * duration) / SUM(duration)'),
            'sum': 'SUM(val_num)',
            'raw': 'val_num',
            'raw.order': 'ORDER BY time DESC',
            'raw.group': ''
        }
        if func not in queries:
            self.logger.warning("Unknown export function: {0}".format(func))
            return
        order = '' if func + '.order' not in queries else queries[func + '.order']
        logs = self._fetch_log(item, queries[func], start, end, order=order)
        if logs['tuples'] is None:
            return
        return logs['tuples'][0][0]


    def _expression(self, func):
        expression = {'params': {'op': '!=', 'value': '0'}, 'finalizer': None}
        if ':' in func:
            expression['finalizer'] = func[:func.index(":")]
            func = func[func.index(":") + 1:]
        if func == 'count' or func.startswith('count'):
            parts = re.match('(count)((<>|!=|<|=|>)(\d+))?', func)
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

        if self._buffer[_item] != []:
            self._dump(items=[_item])

        params = {'id': id, 'time_start': istart, 'time_end': iend, 'inow': inow, 'step': step}
        duration_now = "COALESCE(duration, :inow - time)"

        # Duration calculation (S=Start, E=End):
        duration = (
            "("
            #    ----------|<--------------------------->|---------->
            # 1. Duration for items within the given start/end range
            #    -----------------[S]======[E]---------------------->
            "COALESCE(duration * (time >= :time_start) * (time + duration <= :time_end), 0) + "
            # 2. Duration for items partially before start but ends after start
            #    -----[S]======[E]---------------------------------->
            "COALESCE(duration / duration * (time + duration - :time_start) * (time < :time_start) * (time + duration >= :time_start), 0) + "
            #    ----------------------------------[S]======[E]----->
            # 3. Duration for items partially after end but starts before end
            "COALESCE(duration_now / duration_now * (:time_end - time) * (time + duration_now >= :time_end), 0)"
            ")"
        )

        # Replace duration fields with calculated durations from previous
        # generated expressions to include all three cases.
        columns = columns.replace('duration', duration)

        # Create base query including the replaced columns
        query = (
                "SELECT " + columns + " FROM {log} WHERE "
                                      "item_id = :id AND "
                                      "time >= (SELECT COALESCE(MAX(time), 0) FROM {log} WHERE item_id = :id AND time < :time_start) AND "
                                      "time <= :time_end AND "
                                      "time + duration_now > (SELECT COALESCE(MAX(time), 0) FROM {log} WHERE item_id = :id AND time < :time_start) "
                                      "" + group + " " + order
        )

        # Replace duration_now with value from start time til current time to
        # get a duration value referring to the current timestamp - if required.
        query = query.replace('duration_now', duration_now)

        logs = self._fetchall(query, params)

        return {
            'tuples': logs,
            'item': _item,
            'istart': istart,
            'iend': iend,
            'step': step,
            'count': count
        }


    def _parse_ts(self, dts):
        """
        Parse a duration-timestamp in the form '1w 2y 3h 1d 39i 15s' and return the duration in seconds as
        an integer value

        :return:
        """
        ts = self._timestamp(self.shtime.now())
        try:
            return min(ts, int(dts))    # rts, if dts is an integer value, return now, if dts is a timestamp in th future
        except:
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
        except:
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
        except:
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
        if self._dump_lock.acquire(timeout=60) == False:
            self.logger.notice('Skipping dump, since an other database operation running! Data is buffered and dumped later.')
            self.skipping_dump = True
            return

        self.logger.debug('Starting dump')

        if self.skipping_dump:
            self.logger.notice('Dumping buffered data from skipped dump(s).')
            self.skipping_dump = False

        if not self._initialize_db():
            self._dump_lock.release()
            return

        if items == None:
            # No item given on method call -> dump content of the buffer
            self._buffer_lock.acquire()
            items = list(self._buffer.keys())
            self._buffer_lock.release()

        for item in items:
            tuples = self._buffer_remove(item)

            if len(tuples) or finalize:

                # Test connectivity
                if self._db.verify(5) == 0:
                    self._buffer_insert(item, tuples)
                    self.logger.error("Connection not recovered, skipping dump");
                    self._dump_lock.release()
                    return

                # Can't lock, restore data
                if not self._db.lock(300):
                    self._buffer_insert(item, tuples)
                    if finalize:
                        self.logger.error(
                            "Can't dump {} items due to fail to acquire lock!".format(len(self._buffer)))
                    else:
                        self.logger.error(
                            "Can't dump {} items due to fail to acquire lock - will try on next dump".format(
                                len(self._buffer)))
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
                        self._webdata[item.id()].update({'value': val})
                        self._webdata[item.id()].update({'type': item.property.type})
                    except Exception as e:
                        self.logger.warning("Problem webdata value update {}: {}".format(item.id(), e))

                    # When finalizing (e.g. plugin shutdown) add current value to item and log
                    if finalize:

                        # When plugin is shutdown, by default, every registered item is rewritten into the DB no matter
                        # if it has been changed or not. This behavior is not wanted for items that are rarely updated
                        # because these database entries would lead indicate item updates that in reality aren't really there.
                        # Therefore, if item attribute database_write_on_shutdown is set to False, no double entries are written
                        # to the database and only the last entry is updated.

                        #self.logger.debug(f"DEBUG _dump: Finalizing item {item} with value {val}")
                        if self.get_iattr_value(item.conf, 'database_write_on_shutdown') == False:
                            self.logger.debug(f"DEBUG _dump: Blocking rewrite to DB for item {item} with value {val}")

                            #if item.id() == 'xyz':
                            #    self.logger.warning(f"DEBUG _dump: update debug item with start {start}, val {val}, changed {changed}")

                            _update = (start, val, changed)

                        else:
                            # Perform item update and rewrite current value to database:
                            _update = (end, val, changed)

                            current = (start, end - start, val)
                            tuples.append(current)

                    else:
                        # only perform DB item update for regular dumps (not at plugin shutdown)
                        _update = (start, val, changed)

                    cur = self._db.cursor()
                    id = self.id(item, cur=cur)

                    # Dump tuples
                    self.logger.debug('Dumping {}/{} with {} values'.format(item.id(), id, len(tuples)))

                    for t in tuples:
                        if len(self.readLog(id, t[0], cur)):
                            self.updateLog(id, t[0], t[1], t[2], item.type(), changed, cur)
                        else:
                            self.insertLog(id, t[0], t[1], t[2], item.type(), changed, cur)

                    self.updateItem(id, _update[0], None, _update[1], item.type(), _update[2], cur)

                    cur.close()
                    cur = None

                    self._db.commit()
                except Exception as e:
                    self.logger.warning("Problem dumping {}: {}".format(item.id(), e))
                    try:
                        self._db.rollback()
                    except Exception as er:
                        self._buffer_insert(item, tuples)
                        self.logger.warning("Error rolling back: {}".format(er))
                finally:
                    if cur is not None:
                        cur.close()
                self._db.release()
        self.logger.debug('Dump completed')
        self._dump_lock.release()


    def _buffer_insert(self, item, tuples):
        self._buffer_lock.acquire()
        if item in self._buffer:
            self._buffer[item] = tuples + self._buffer[item]
        else:
            self._buffer[item] = tuples
        self._buffer_lock.release()
        return tuples


    def _buffer_remove(self, item):
        self._buffer_lock.acquire()
        tuples = self._buffer[item]
        self._buffer[item] = self._buffer[item][len(tuples):]
        self._buffer_lock.release()
        return tuples


    # ------------------------------------------
    #    Database maintenance stuff
    # ------------------------------------------

    def remove_older_than_maxage(self):
        """
        Remove log entries older than maxage of an item

        Called by scheduler
        """
        if self.lock_remove_older:
            if not self._remove_older_skipped:
                self.logger.info("remove_older_than_maxage task is manually locked")
                self._remove_older_skipped = True
            return

        if not self._db.connected():
            self.logger.warning("remove_older_than_maxage skipped because db is not connected")
            return False

        # prevent creation of more than one thread
        current_thread = threading.current_thread()
        current_thread_name = current_thread.name
        for t in threading.enumerate():
            if t is current_thread:
                continue
            if t.name == current_thread_name:
                if not self._remove_older_skipped:
                    self.logger.info("remove_older_than_maxage skipped because a thread with this task is already running")
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
            self.logger.info(f"remove_older_: Worklist filled with {len(self._items_with_maxage)} items")

        item = self._maxage_worklist.pop(0)
        itempath = item.property.path

        try:
            item_id = self.id(item, create=False)
        except:
            if item_id is None:
                self.logger.info(f"remove_older_: no id for item {itempath}")
            else:
                self.logger.critical(f"remove_older_: no id for item {itempath}")
            return

        # it might well be that introducing database_maxage to a very old SmartHomeNG installation will try to start
        # a deletion of thousands of logentries. This might take days with SQLite if so.
        # so strategies might be
        # a) delete only records for one day
        # b) to just delete a limited number of log entries
        time_end = self.get_maxage_ts(item)
        timestamp_end = self._timestamp(time_end)

        # if delete would also remove the last logged value for the item then there might be no chance for
        # ``database: init`` to retrieve the latest value.
        remaining = 1
        if self.get_iattr_value(item.conf, 'database').lower() == 'init':
            # find out if there are still log entries after deletion of the logs
            remaining = self.readLogCount(item_id, time_start=self._timestamp( time_end + datetime.timedelta(microseconds=1)))
            # remaining can be larger than self._item_logcount[item_id], it depends on the rate of database updates
            #self.logger.info(f"remove_older_: {itempath} has attribute init with {self._item_logcount[item_id]} log entries and will have {remaining} log entries after deletion")

        if remaining <= 0:
            # no log entries will be there after deletion, need to go back in time for the latest logentry
            new_must_keep_timestamp = self.readLatestLog(item_id, timestamp_end)
            if new_must_keep_timestamp is None:
                return
            new_must_keep_time = self._datetime(new_must_keep_timestamp)
            self.logger.info(f"remove_older_: {itempath} no remaining log entry between {time_end} and now, thus can not remove log entries older than maxage, latest log is {new_must_keep_time}")
            time_end = new_must_keep_time + datetime.timedelta(microseconds=-1)
            timestamp_end = self._timestamp( time_end )

        count_log_records_to_delete = self.readLogCount(item_id, time_end=self._timestamp( time_end))
        count_log_records_to_delete_str = f"{count_log_records_to_delete:,}".replace(',','.')
        max_delete_logentries_str = f"{self.max_delete_logentries:,}".replace(',','.')
        time_end_str = time_end.strftime("%d.%m.%Y - %H:%M")
        self.logger.debug(f"remove_older_: {itempath} remove older than {time_end_str} - {count_log_records_to_delete_str} records to delete")

        # prevent to many deletions with strategy b)
        # assumption is made that logentries are evenly distributed over time
        # there will be actually be some more or less deletions than given in self.max_delete_logentries
        # since only a linear approximation over time and counts is used, but it should do the trick
        # to prevent from database lockups after setting database_maxage to old/ancient items
        if count_log_records_to_delete > self.max_delete_logentries:
            time_start_deletion = time.time()
            cur = self._db.cursor()
            self._execute(self._prepare("DELETE FROM {log} WHERE item_id = :id ORDER BY time ASC LIMIT :maxrecords;"), {'id': item_id, 'maxrecords': self.max_delete_logentries}, cur=cur)
            cur.close()
            time_used_for_deletion = time.time() - time_start_deletion
            self.logger.info(f"remove_older_: {itempath} deleted {max_delete_logentries_str} of {count_log_records_to_delete_str} log entries - took {time_used_for_deletion:.2f} seconds, averaging {100*time_used_for_deletion/self.max_delete_logentries:.4f} seconds per 100 entries")

            # Re-Add item to worklist, since there are more records to be deleted
            self._maxage_worklist.append(item)

        elif count_log_records_to_delete:
            time_start_deletion = time.time()
            self.deleteLog(item_id, time_end=timestamp_end, with_commit=False)
            time_used_for_deletion = time.time() - time_start_deletion
            time_end_str = time_end.strftime("%d.%m.%Y - %H:%M")
            self.logger.info(f"remove_older_: {itempath} deleted {count_log_records_to_delete_str} log entries until {time_end_str} took {time_used_for_deletion:.2f} seconds, averaging {100*time_used_for_deletion/count_log_records_to_delete:.4f} seconds per 100 entries")

        # update the logCount for the item
        logcount = self.readLogCount(item_id)
        self._item_logcount[item_id] = logcount
        self._webdata[item.id()].update({'logcount': logcount})

        return

    def get_maxage_ts(self, item):
        """
        Get the actual maxage-timestamp for a given item

        :param item:

        :return:
        """
        if self.has_iattr(item.conf, 'database_maxage'):
            maxage = self.get_iattr_value(item.conf, 'database_maxage')
        elif self._default_maxage > 0:
            maxage = self._default_maxage

        if maxage:
            dt = self.shtime.now()
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            dt = dt - datetime.timedelta(float(maxage))
            return dt
        return None


    def _count_logentries(self):
        """
        count number of log entries for all items in database

        called by scheduler once on start
        """
        self.logger.info("_count_logentries: # handled items = {}".format(len(self._handled_items)))
        self._items_still_counting = True
        self._items_total_entries = 0
        for item in self._handled_items:
            item_id = self.id(item, create=False)
            logcount = self.readLogCount(item_id)
            self._item_logcount[item_id] = logcount
            self._items_total_entries += logcount
            self._webdata[item.id()].update({'logcount': logcount})
            #self._webdata[item.id()].update({'logcount': f"{logcount:,}".replace(',', '.')})

        self._items_still_counting = False
        return


    # ------------------------------------------
    #    Database specific stuff
    # ------------------------------------------

    def _initialize_db(self):
        try:
            if not self._db.connected():
                # limit connection requests to 20 seconds.
                current_time = time.time()
                time_delta_last_connect = current_time - self.last_connect_time
                self.logger.debug("DEBUG: delta {0}".format(time_delta_last_connect))
                if (time_delta_last_connect >  20):
                    self.last_connect_time = time.time()
                    self._db.connect()
                else:
                    self.logger.error("Database reconnect supressed: Delta time: {0}".format(time_delta_last_connect))
                    return False

            if not self._db_initialized:
                self._db.setup(
                    {i: [self._prepare(query[0]), self._prepare(query[1])] for i, query in self._setup.items()})
                self._db_initialized = True
        except Exception as e:
            self.logger.critical("Database: Initialization failed: {}".format(e))
            if self.driver.lower() == 'sqlite3':
                self._sh.restart('SmartHomeNG (Database plugin stalled)')
                exit(0)
            else:
                return False

        return True


    def _prepare(self, query):
        return query.format(**self._replace)


    def _execute(self, query, params, cur=None):
        self._query(self._db.execute, query, params, cur)


    def _fetchone(self, query, params={}, cur=None):
        tuples = self._query(self._db.fetchone, query, params, cur)
        return tuples


    def _fetchall(self, query, params={}, cur=None):
        tuples = self._query(self._db.fetchall, query, params, cur)
        return None if tuples is None else list(tuples)


    def _query(self, func, query, params, cur=None):
        if not self._initialize_db():
            return None
        if cur is None:
            if self._db.verify(5) == 0:
                self.logger.error("Database: Connection not recovered")
                return None
            if not self._db.lock(300):
                self.logger.error("Database: Can't query due to fail to acquire lock")
                return None
        query = self._prepare(query)
        query_readable = re.sub(r':([a-z_]+)', r'{\1}', query).format(**params)
        tuples = None
        try:
            tuples = func(self._prepare(query), params, cur=cur)
        except Exception as e:
            self.logger.error("Database: Error for query {}: {}".format(query_readable, e))
            raise e
        finally:
            if cur is None:
                self._db.release()
        self.logger.debug("Database: Fetch {}: {}".format(query_readable, tuples))
        return tuples


    # ------------------------------------------
    #    conversion routines
    # ------------------------------------------

    def _item_value_tuple(self, item_type, item_val):
        """
        Convert item type and value to tuple for database

        :param item_type:
        :param item_val:
        :return:
        """
        if item_type == 'num':
            val_str = None
            val_num = float(item_val)
            val_bool = int(bool(item_val))
        elif item_type == 'bool':
            val_str = None
            val_num = float(item_val)
            val_bool = int(bool(item_val))
        else:
            val_str = str(item_val)
            val_num = None
            val_bool = int(bool(item_val))

        return {'val_str': val_str, 'val_num': val_num, 'val_bool': val_bool}


    def _item_value_tuple_rev(self, item_type, item_val_tuple):
        """
        Convert tuple to item value

        :param item_type:
        :param item_val_tuple:
        :return:
        """
        if item_type == 'num':
            return None if item_val_tuple[1] is None else float(item_val_tuple[1])
        elif item_type == 'bool':
            return None if item_val_tuple[2] is None else bool(int(item_val_tuple[2]))
        else:
            return None if item_val_tuple[0] is None else str(item_val_tuple[0])


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
        #self.logger.debug("Debug timestamp {0}, val {1}, epoche timestamp {2}, micrsec {3}".format(dt, val, time.mktime(dt.timetuple()), dt.microsecond) )
        return val


    def _seconds(self, ms):
        """
        Get seconds (rounded) from milliseconds

        :param dt:
        :return:
        """
        if ms:
            return round(ms/1000, 1)
        else:
            return ms

    def _len(self, l):
        return len(l)
