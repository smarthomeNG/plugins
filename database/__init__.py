#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2016-     Oliver Hinckel                   github@ollisnet.de
# Based on ideas of sqlite plugin, provided by Marcus Popp marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG
#  https://github.com/smarthomeNG/smarthome
#  http://knx-user-forum.de/
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

import re
import logging
import datetime
import functools
import time
import threading
import lib.db

from lib.model.smartplugin import SmartPlugin

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

class Database(SmartPlugin):

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = '1.3.0'

    # SQL queries: {item} = item table name, {log} = log table name
    # time, item_id, val_str, val_num, val_bool, changed
    _setup = {
      '1' : ["CREATE TABLE {log} (time BIGINT, item_id INTEGER, duration BIGINT, val_str TEXT, val_num REAL, val_bool BOOLEAN, changed BIGINT);", "DROP TABLE {log};"],
      '2' : ["CREATE TABLE {item} (id INTEGER, name varchar(255), time BIGINT, val_str TEXT, val_num REAL, val_bool BOOLEAN, changed BIGINT);", "DROP TABLE {item};"],
      '3' : ["CREATE UNIQUE INDEX {log}_{item}_id_time ON {log} (item_id, time);", "DROP INDEX {log}_{item}_id_time;"],
      '4' : ["CREATE INDEX {log}_{item}_id_changed ON {log} (item_id, changed);", "DROP INDEX {log}_{item}_id_changed;"],
      '5' : ["CREATE UNIQUE INDEX {item}_id ON {item} (id);", "DROP INDEX {item}_id;"],
      '6' : ["CREATE INDEX {item}_name ON {item} (name);", "DROP INDEX {item}_name;"]
    }

    def __init__(self, smarthome, driver, connect, prefix="", cycle=60):
        self._sh = smarthome
        self.logger = logging.getLogger(__name__)
        self._dump_cycle = int(cycle)
        self._name = self.get_instance_name()
        self._replace = {table: table if prefix == "" else prefix + "_" + table for table in ["log", "item"]}
        self._replace['item_columns'] = ", ".join(COL_ITEM)
        self._replace['log_columns'] = ", ".join(COL_LOG)
        self._buffer = {}
        self._buffer_lock = threading.Lock()
        self._dump_lock = threading.Lock()

        self._db = lib.db.Database(("" if prefix == "" else prefix.capitalize() + "_") + "Database", driver, connect)
        self._db.connect()
        self._db.setup({i: [self._prepare(query[0]), self._prepare(query[1])] for i, query in self._setup.items()})

        smarthome.scheduler.add('Database dump ' + self._name + ("" if prefix == "" else " [" + prefix + "]"), self._dump, cycle=self._dump_cycle, prio=5)

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'database'):
            self._buffer_insert(item, [])
            item.series = functools.partial(self._series, item=item.id())
            item.db = functools.partial(self._single, item=item.id())
            item.dbplugin = self

            if self.get_iattr_value(item.conf, 'database') == 'init':
                if not self._db.lock(5):
                    self.logger.error("Can not acquire lock for database to read value for item {}".format(item.id()))
                    return
                cur = self._db.cursor()
                try:
                    cache = self.readItem(str(item.id()), cur=cur)
                    if cache is not None:
                        value = self._item_value_tuple_rev(item.type(), cache[COL_ITEM_VAL_STR:COL_ITEM_VAL_BOOL+1])
                        last_change = self._datetime(cache[COL_ITEM_TIME])
                        last_change_ts = self._timestamp(last_change)
                        prev_change = self._fetchone('SELECT MAX(time) from {log} WHERE item_id = :id', {'id':cache[COL_ITEM_ID]}, cur=cur)
                        if value is not None and prev_change is not None:
                            item.set(value, 'Database', prev_change=self._datetime(prev_change[0]), last_change=last_change)
                        self._buffer_insert(item, [(last_change_ts, None, value)])
                except Exception as e:
                    self.logger.error("Reading cache value from database for {} failed: {}".format(item.id(), e))
                cur.close()
                self._db.release()
            return self.update_item
        else:
            return None

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False
        self._dump(True)
        self._db.close()

    def update_item(self, item, caller=None, source=None, dest=None):
        acl = 'rw' if not self.has_iattr(item.conf, 'database_acl') else self.get_iattr_value(item.conf, 'database_acl')
        if acl is 'rw':
            start = self._timestamp(item.prev_change())
            end = self._timestamp(item.last_change())
            last = None if len(self._buffer[item]) == 0 or self._buffer[item][-1][1] is not None else self._buffer[item][-1]
            if last:  # update current value with duration
                self._buffer[item][-1] = (last[0], end - start, last[2])
            else:     # append new value with none duration
                self._buffer[item].append((start, end - start, item.prev_value()))

            # add current value with None duration
            self._buffer[item].append((end, None, item()))

    def dump(self, dumpfile, id = None, time = None, time_start = None, time_end = None, changed = None, changed_start = None, changed_end = None, cur = None):
        self.logger.info("Starting file dump to {} ...".format(dumpfile))

        item_ids = self.readItems(cur=cur) if id is None else [self.readItem(id, cur=cur)]

        s = ';'
        h = ['item_id', 'item_name', 'time', 'duration', 'val_str', 'val_num', 'val_bool', 'changed', 'time_date', 'changed_date']
        f = open(dumpfile, 'w')
        f.write(s.join(h) + "\n")
        for item in item_ids:
            self.logger.debug("... dumping item {}/{}".format(item[1], item[0]))

            rows = self.readLogs(item[0], time=time, time_start=time_start, time_end=time_end, changed=changed, changed_start=changed_start, changed_end=changed_end, cur=cur)

            for row in rows:
                cols = []
                for key in [COL_ITEM_ID, COL_ITEM_NAME]:
                    cols.append(item[key])
                for key in [COL_LOG_TIME, COL_LOG_DURATION, COL_LOG_VAL_STR, COL_LOG_VAL_NUM, COL_LOG_VAL_BOOL, COL_LOG_CHANGED]:
                    cols.append(row[key])
                for key in [COL_ITEM_ID, COL_LOG_CHANGED]:
                  cols.append('' if row[key] is None else datetime.datetime.fromtimestamp(row[key]/1000.0))
                cols = map(lambda col: '' if col is None else col, cols)
                cols = map(lambda col: str(col) if not '"' in str(col) else col.replace('"', '\\"'), cols)
                f.write(s.join(cols) + "\n")
        f.close()
        self.logger.info("File dump completed ({} items) ...".format(len(item_ids)))

    def cleanup(self):
        items = [item.id() for item in self._buffer]
        if not self._db.lock(60):
            self.logger.error("Can not acquire lock for database cleanup")
            return
        cur = self._db.cursor()
        try:
            for item in self.readItems(cur=cur):
                if item[COL_ITEM_NAME] not in items:
                    self.deleteItem(item[COL_ITEM_ID], cur=cur)
        except Exception as e:
            self.logger.error("Database cleanup failed: {}".format(e))
        cur.close()
        self._db.release()

    def id(self, item, create=True, cur=None):
        id = self.readItem(str(item.id()), cur=cur)

        if id == None and create == True:
            id = [self.insertItem(item.id(), cur)]

        return None if id == None else int(id[COL_ITEM_ID])

    def insertItem(self, name, cur=None):
        id = self._fetchone("SELECT MAX(id) FROM {item};", cur=cur)
        self._execute(self._prepare("INSERT INTO {item}(id, name) VALUES(:id, :name);"), {'id':1 if id[0] == None else id[0]+1, 'name':name}, cur=cur)
        id = self._fetchone("SELECT id FROM {item} where name = :name;", {'name':name}, cur=cur)
        return int(id[0])

    def updateItem(self, id, time, duration=0, val=None, it=None, changed=None, cur=None):
        params = {'id':id, 'time':time, 'changed':changed}
        params.update(self._item_value_tuple(it, val))
        self._execute(self._prepare("UPDATE {item} SET time = :time, val_str = :val_str, val_num = :val_num, val_bool = :val_bool, changed = :changed WHERE id = :id;"), params, cur=cur)

    def readItem(self, id, cur=None):
        params = {'id':id}
        if type(id) == str:
            return self._fetchone("SELECT {item_columns} from {item} WHERE name = :id;", params, cur=cur)
        return self._fetchone("SELECT {item_columns} from {item} WHERE id = :id;", params, cur=cur)

    def readItems(self, cur=None):
        return self._fetchall("SELECT {item_columns} from {item};", cur=cur)

    def deleteItem(self, id, cur=None):
        params = {'id':id}
        self.deleteLog(id, cur=cur)
        self._execute(self._prepare("DELETE FROM {item} WHERE id = :id;"), params, cur=cur)

    def insertLog(self, id, time, duration=0, val=None, it=None, changed=None, cur=None):
        params = {'id':id, 'time':time, 'changed':changed, 'duration':duration}
        params.update(self._item_value_tuple(it, val))
        self._execute(self._prepare("INSERT INTO {log}(item_id, time, val_str, val_num, val_bool, duration, changed) VALUES (:id,:time,:val_str,:val_num,:val_bool,:duration,:changed);"), params, cur=cur)

    def updateLog(self, id, time, duration=0, val=None, it=None, changed=None, cur=None):
        params = {'id':id, 'time':time, 'changed':changed, 'duration':duration}
        params.update(self._item_value_tuple(it, val))
        self._execute(self._prepare("UPDATE {log} SET duration = :duration, val_str = :val_str, val_num = :val_num, val_bool = :val_bool, changed = :changed WHERE item_id = :id AND time = :time;"), params, cur=cur)

    def readLog(self, id, time, cur = None):
        params = {'id':id, 'time':time}
        return self._fetchall("SELECT {log_columns} FROM {log} WHERE item_id = :id AND time = :time;", params, cur=cur)

    def readLogs(self, id, time = None, time_start = None, time_end = None, changed = None, changed_start = None, changed_end = None, cur = None):
        condition, params = self._slice_condition(id, time=time, time_start=time_start, time_end=time_end, changed=changed, changed_start=changed_start, changed_end=changed_end)
        return self._fetchall("SELECT {log_columns} FROM {log} WHERE " + condition, params, cur=cur)

    def deleteLog(self, id, time = None, time_start = None, time_end = None, changed = None, changed_start = None, changed_end = None, cur = None):
        condition, params = self._slice_condition(id, time=time, time_start=time_start, time_end=time_end, changed=changed, changed_start=changed_start, changed_end=changed_end)
        self._execute(self._prepare("DELETE FROM {log} WHERE " + condition), params, cur=cur)

    def _slice_condition(self, id, time = None, time_start = None, time_end = None, changed = None, changed_start = None, changed_end = None):
        params = {
          'id'            : id,
          'time'          : time,          'time_flag'          : 1 if time          == None else 0,
          'time_start'    : time_start,    'time_start_flag'    : 1 if time_start    == None else 0,
          'time_end'      : time_end,      'time_end_flag'      : 1 if time_end      == None else 0,
          'changed'       : changed,       'changed_flag'       : 1 if changed       == None else 0,
          'changed_start' : changed_start, 'changed_start_flag' : 1 if changed_start == None else 0,
          'changed_end'   : changed_end,   'changed_end_flag'   : 1 if changed_end   == None else 0
        }

        condition = "(item_id = :id                                      ) AND " + \
                    "(time    = :time          OR 1 = :time_flag         ) AND " + \
                    "(time    > :time_start    OR 1 = :time_start_flag   ) AND " + \
                    "(time    < :time_end      OR 1 = :time_end_flag     ) AND " + \
                    "(changed = :changed       OR 1 = :changed_flag      ) AND " + \
                    "(changed > :changed_start OR 1 = :changed_start_flag) AND " + \
                    "(changed < :changed_end   OR 1 = :changed_end_flag  );    "
        return (condition, params)

    def db(self):
        return self._db

    def _item_value_tuple(self, item_type, item_val):
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

        return {'val_str':val_str, 'val_num':val_num, 'val_bool':val_bool}

    def _item_value_tuple_rev(self, item_type, item_val_tuple):
        if item_type == 'num':
           return None if item_val_tuple[1] is None else float(item_val_tuple[1])
        elif item_type == 'bool':
           return None if item_val_tuple[2] is None else bool(int(item_val_tuple[2]))
        else:
           return None if item_val_tuple[0] is None else str(item_val_tuple[0])

    def _datetime(self, ts):
        return datetime.datetime.fromtimestamp(ts / 1000, self._sh.tzinfo())

    def _prepare(self, query):
        return query.format(**self._replace)

    def _dump(self, finalize=False, items=None):
        if self._dump_lock.acquire(timeout=60) == False:
            self.logger.warning('Skipping dump, since other dump running!')
            return

        self.logger.debug('Starting dump')

        if items == None:
            self._buffer_lock.acquire()
            items = list(self._buffer.keys())
            self._buffer_lock.release()

        for item in items:
            tuples = self._buffer_remove(item)

            if len(tuples) or finalize:

                # Test connectivity
                if self._db.verify(5) == 0:
                    self._buffer_insert(item, tuples)
                    self.logger.error("Database: Connection not recovered, skipping dump");
                    self._dump_lock.release()
                    return

                # Can't lock, restore data
                if not self._db.lock(300):
                    self._buffer_insert(item, tuples)
                    if finalize:
                        self.logger.error("Database: can't dump {} items due to fail to acquire lock!".format(len(self._buffer)))
                    else:
                        self.logger.error("Database: can't dump {} items due to fail to acquire lock - will try on next dump".format(len(self._buffer)))
                    self._dump_lock.release()
                    return

                cur = None
                try:
                    changed = self._timestamp(self._sh.now())

                    # Get current values of item
                    start = self._timestamp(item.last_change())
                    end = changed
                    val = item()

                    # When finalizing (e.g. plugin shutdown) add current value to item and log
                    if finalize:
                        _update = (end, val, changed)

                        current = (start, end - start, val)
                        tuples.append(current)

                    else:
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
                    self.logger.warning("Database: problem updating {}: {}".format(item.id(), e))
                    self._db.rollback()
                finally:
                    if cur is not None:
                        cur.close()
                self._db.release()
        self.logger.debug('Dump completed')
        self._dump_lock.release()

    def _buffer_remove(self, item):
        self._buffer_lock.acquire()
        tuples = self._buffer[item]
        self._buffer[item] = self._buffer[item][len(tuples):]
        self._buffer_lock.release()
        return tuples

    def _buffer_insert(self, item, tuples):
        self._buffer_lock.acquire()
        if item in self._buffer:
            self._buffer[item] = tuples + self._buffer[item]
        else:
            self._buffer[item] = tuples
        self._buffer_lock.release()
        return tuples

    def _expression(self, func):
        expression = {'params' : {'op':'!=', 'value':'0'}, 'finalizer' : None}
        if ':' in func:
            expression['finalizer'] = func[:func.index(":")]
            func = func[func.index(":")+1:]
        if func is 'count' or func.startswith('count'):
            parts = re.match('(count)((<>|!=|<|=|>)(\d+))?', func)
            func = 'count'
            self.logger.debug(parts)
            self.logger.debug(parts.groups())
            self.logger.debug(parts.group(3))
            self.logger.debug(parts.group(4))
            if parts and parts.group(3) is not None:
                expression['params']['op'] = parts.group(3)
            if parts and parts.group(4) is not None:
                expression['params']['value'] = parts.group(4)
        return func, expression

    def _finalize(self, func, tuples):
        if func == 'diff':
            final_tuples = []
            for i in range(1, len(tuples)-1):
                final_tuples.append((tuples[i][0], tuples[i][1] - tuples[i-1][1]))
            return final_tuples
        else:
            return tuples

    def _series(self, func, start, end='now', count=100, ratio=1, update=False, step=None, sid=None, item=None):
        init = not update
        if sid is None:
            sid = item + '|' + func + '|' + str(start) + '|' + str(end)  + '|' + str(count)
        func, expression = self._expression(func)
        queries = {
            'avg' : 'MIN(time), ROUND(AVG(val_num * duration) / AVG(duration), 2)',
            'avg.order' : 'ORDER BY time ASC',
            'count' : 'MIN(time), SUM(CASE WHEN val_num{op}{value} THEN 1 ELSE 0 END)'.format(**expression['params']),
            'min' : 'MIN(time), MIN(val_num)',
            'max' : 'MIN(time), MAX(val_num)',
            'on'  : 'MIN(time), ROUND(SUM(val_bool * duration) / SUM(duration), 2)',
            'on.order' : 'ORDER BY time ASC',
            'sum' : 'MIN(time), SUM(val_num)',
            'raw' : 'time, val_num',
            'raw.order' : 'ORDER BY time ASC',
            'raw.group' : ''
        }
        if func not in queries:
            raise NotImplementedError

        order = '' if func+'.order' not in queries else queries[func+'.order']
        group = 'GROUP BY ROUND(time / :step)' if func+'.group' not in queries else queries[func+'.group']
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

        return {
            'cmd': 'series', 'series': tuples, 'sid': sid,
            'params' : {'update': True, 'item': item, 'func': func, 'start': logs['iend'], 'end': end, 'step': logs['step'], 'sid': sid},
            'update' : self._sh.now() + datetime.timedelta(seconds=int(logs['step'] / 1000))
        }

    def _single(self, func, start, end='now', item=None):
        func, expression = self._expression(func)
        queries = {
            'avg' : 'ROUND(AVG(val_num * duration) / AVG(duration), 2)',
            'count' : 'SUM(CASE WHEN val_num{op}{value} THEN 1 ELSE 0 END)'.format(**expression['params']),
            'min' : 'MIN(val_num)',
            'max' : 'MAX(val_num)',
            'on'  : 'ROUND(SUM(val_bool * duration) / SUM(duration), 2)',
            'sum' : 'SUM(val_num)',
            'raw' : 'val_num',
            'raw.order' : 'ORDER BY time DESC',
            'raw.group' : ''
        }
        if func not in queries:
            self.logger.warning("Unknown export function: {0}".format(func))
            return
        order = '' if func+'.order' not in queries else queries[func+'.order']
        logs = self._fetch_log(item, queries[func], start, end, order=order)
        if logs['tuples'] is None:
            return
        return logs['tuples'][0][0]

    def _fetch_log(self, item, columns, start, end, step=None, count=100, group='', order=''):
        _item = self._sh.return_item(item)

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

        params = {'id':id, 'time_start':istart, 'time_end':iend, 'inow':inow, 'step':step}
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
            'tuples' : logs,
            'item'   : _item,
            'istart' : istart,
            'iend'   : iend,
            'step'   : step,
            'count'  : count
        }

    def _fetchone(self, query, params={}, cur=None):
        tuples = self._query(self._db.fetchone, query, params, cur)
        return tuples

    def _fetchall(self, query, params={}, cur=None):
        tuples = self._query(self._db.fetchall, query, params, cur)
        return None if tuples is None else list(tuples)

    def _execute(self, query, params, cur=None):
        self._query(self._db.execute, query, params, cur)

    def _query(self, func, query, params, cur=None):
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
            self.logger.warning("Database: Running query {}: {}".format(query_readable, e))
        if cur is None:
            self._db.release()
        self.logger.debug("Fetch {}: {}".format(query_readable, tuples))
        return tuples

    def _parse_ts(self, frame):
        minute = 60 * 1000
        hour = 60 * minute
        day = 24 * hour
        week = 7 * day
        month = 30 * day
        year = 365 * day

        _frames = {'i': minute, 'h': hour, 'd': day, 'w': week, 'm': month, 'y': year}
        try:
            return int(frame)
        except:
            pass
        ts = self._timestamp(self._sh.now())
        if frame == 'now':
            fac = 0
            frame = 0
        elif frame[-1] in _frames:
            fac = _frames[frame[-1]]
            frame = frame[:-1]
        else:
            return frame
        try:
            ts = ts - int(float(frame) * fac)
        except:
            self.logger.warning("Database: Unknown time frame '{0}'".format(frame))
        return ts

    def _timestamp(self, dt):
        return int(time.mktime(dt.timetuple())) * 1000 + int(dt.microsecond / 1000)
