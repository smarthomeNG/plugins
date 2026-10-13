import csv
import inspect
import os
import datetime
import tempfile
import threading
import pytest
from unittest import mock

from lib.db import DatabaseSetupError
from plugins.database import Database
from plugins.database.constants import BufferEntry
from plugins.database.tests.base import TestDatabaseBase


class TestDatabaseBasic(TestDatabaseBase):
    def test_init_fails_cleanly_for_sqlite_memory_database(self):
        # The plugin opens two independent connections (self._db,
        # self._db_maint), each its own sqlite3.connect() call - a ':memory:'
        # database is private to the connection that opened it (no
        # shared-cache URI is used here), so the two would become two
        # separate, disconnected empty databases. base.py's plugin() fixture
        # works around this by using a temp file instead (see its comment);
        # this asserts the plugin itself refuses the configuration outright.
        self.plugin()  # sets up self.sh / registers test items / Database._parameters
        Database._parameters['connect'] = {'database': ':memory:'}

        plugin = Database.__new__(Database)
        plugin._set_sh(self.sh)
        plugin.__init__(self.sh)

        self.assertFalse(getattr(plugin, '_init_complete', True))
        self.assertFalse(
            hasattr(plugin, '_item_store'), 'init must stop before wiring up stores that assume a working db'
        )

    def test_db_itemtype_returns_none_not_crash_when_disconnected(self):
        # db_itemtype()/db_lastchange() both call readItem(cur=None), which
        # hits Database.fetchone()'s never-connected sentinel path. That
        # sentinel must be None, not '' - `row is None` must catch it
        # directly, not rely on the len(row)==0 branch of
        # `COL_ITEM_ID >= len(row)` happening to still return None.
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        plugin._db._conn = None  # simulate disconnected, no reconnect attempt

        self.assertIsNone(plugin.db_itemtype(item))

    def test_id_not_creating_items(self):
        plugin = self.plugin()
        self.assertIsNone(plugin.id(self.sh.return_item('main.num'), False))
        self.assertIsNone(plugin.id(self.sh.return_item('main.str'), False))
        self.assertIsNone(plugin.id(self.sh.return_item('main.bool'), False))

    def test_id_creating_items(self):
        plugin = self.plugin()
        self.assertEqual(1, plugin.id(self.sh.return_item('main.num'), True))
        self.assertEqual(2, plugin.id(self.sh.return_item('main.str'), True))
        self.assertEqual(3, plugin.id(self.sh.return_item('main.bool'), True))

    def test_id_creating_from_bare_path_string(self):
        # id() falls back to using the raw argument as the item path (via
        # the AttributeError branch) when it's a plain string rather than
        # an item object - the create-if-missing branch must use that
        # already-computed item_path fallback, not call
        # self.insertItem(item.property.path, ...) unconditionally
        # (AttributeError for a bare string, which has no .property).
        plugin = self.plugin()
        self.assertEqual(1, plugin.id('some.new.path', True))
        self.assertEqual(1, plugin.id('some.new.path', False))

    def test_setup_item_ddl_uses_auto_increment_for_non_sqlite_driver(self):
        """
        CREATE TABLE {item}'s id column must be AUTO_INCREMENT on
        MySQL/MariaDB, not bare 'id INTEGER PRIMARY KEY' (which only
        auto-increments on SQLite, aliased to rowid) - otherwise the very
        first ItemStore.insert() against a fresh install fails outright
        under default strict SQL mode (see Database._setup's docstring
        comment). Fixture always uses sqlite3, so this only checks the DDL
        string the property builds for each driver, not a live MySQL
        connection.
        """
        plugin = self.plugin()
        self.assertIn('id INTEGER PRIMARY KEY,', plugin._setup['2'][0])
        self.assertNotIn('AUTO_INCREMENT', plugin._setup['2'][0])

    def test_setup_version_8_retrofits_auto_increment_for_existing_mysql_installs(self):
        # Regression: version 2's CREATE TABLE only runs for a schema that
        # hasn't recorded it yet - every already-existing MySQL/MariaDB
        # install has v2 applied without AUTO_INCREMENT and never re-runs
        # it. Version 8 retrofits it via ALTER TABLE, which setup() DOES
        # run for any install below that version, sqlite included (has to
        # stay a no-op there since the column already auto-increments).
        plugin = self.plugin()
        self.assertNotIn('AUTO_INCREMENT', plugin._setup['8'][0])
        self.assertNotIn('ALTER TABLE', plugin._setup['8'][0])

        plugin.driver = 'pymysql'
        self.assertIn('AUTO_INCREMENT', plugin._setup['8'][0])
        self.assertIn('ALTER TABLE', plugin._setup['8'][0])
        self.assertIn('id INTEGER PRIMARY KEY AUTO_INCREMENT,', plugin._setup['2'][0])

    def test_setup_versions_9_to_11_widen_name_column_for_non_sqlite_driver(self):
        # Regression: name varchar(255) never actually bounded anything on
        # SQLite (no length enforcement there), but a MySQL/MariaDB install
        # under strict mode rejects/truncates any item path over 255 chars.
        # Split into 3 single-statement versions (setup() runs one
        # execute() per version; DB-API drivers don't reliably support
        # several ;-separated statements in one call): widen the column,
        # drop the old full-column index, recreate it as a name(191) prefix
        # index - a prefix index doesn't affect WHERE name = ... lookup
        # correctness, and 191 chars stays under InnoDB's classic 767-byte
        # indexed-column limit regardless of charset/row-format. Verified
        # end-to-end (all three statements, plus storing/reading back a
        # 300+ char name) against a real MariaDB target.
        plugin = self.plugin()
        for v in ('9', '10', '11'):
            self.assertEqual('SELECT 1;', plugin._setup[v][0], f'sqlite3 driver: version {v} must be a no-op')

        plugin.driver = 'pymysql'
        self.assertIn('varchar(1024)', plugin._setup['9'][0])
        self.assertIn('DROP INDEX {item}_name ON {item}', plugin._setup['10'][0])
        self.assertIn('name(191)', plugin._setup['11'][0])

    def test_id_concurrent_create_no_duplicate(self):
        """
        id(create=True) is a check-then-act sequence (readItem, then
        insertItem if not found). Without holding the lock across both,
        two concurrent callers can each see "not found" and both insert,
        creating two rows for the same item name. Fire many threads at the
        same not-yet-existing item and confirm exactly one row is created
        and every thread agrees on its id.
        """
        plugin = self.plugin()
        item = self.sh.return_item('main.num')

        results = []
        num_threads = 4
        barrier = threading.Barrier(num_threads)

        def worker():
            barrier.wait()
            results.append(plugin.id(item, True))

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(num_threads, len(results))
        self.assertEqual({results[0]}, set(results), 'all callers must agree on the same id')

        rows = [row for row in plugin.readItems() if row[1] == item.property.path]
        self.assertEqual(1, len(rows), 'exactly one row must exist for the item, no duplicates')

    def test_insertItem_creating_item(self):
        plugin = self.plugin()
        self.assertEqual(1, plugin.insertItem('manually.inserted'))

    def test_readItem_reads_unknown_as_none(self):
        plugin = self.plugin()
        res = plugin.readItem(1)
        self.assertIsNone(res)

    def test_readItem_returns_existing_item(self):
        plugin = self.plugin()
        res = plugin.readItem(plugin.insertItem('manually.inserted'))
        self.assertEqual(1, res[0])
        self.assertEqual('manually.inserted', res[1])

    def test_updateItem(self):
        plugin = self.plugin()
        id = plugin.insertItem('manually.inserted')
        plugin.updateItem(id, time=0, val='test', it='str')
        res = plugin.readItem(id)
        self.assertEqual(id, res[0])
        self.assertEqual(0, res[2])
        self.assertEqual('test', res[3])

    def test_deleteItem(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        plugin.deleteItem(plugin.id(item, True))
        self.assertIsNone(plugin.id(item, False))

    def test_readItems(self):
        plugin = self.plugin()
        self.create_item(plugin, 'main.num')
        self.create_item(plugin, 'main.str')
        self.create_item(plugin, 'main.bool')
        res = plugin.readItems()
        self.assertEqual(3, len(res))
        self.assertEqual('main.num', res[0][1])
        self.assertEqual('main.str', res[1][1])
        self.assertEqual('main.bool', res[2][1])

    def test_readLog_empty_result(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        res = plugin.readLog(id, time=0)
        self.assertEqual(0, len(res))

    def test_insertLog_num(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        res = plugin.readLog(id, time=0)
        self.assertEqual(1, len(res))
        self.assertEqual(0, res[0][0])
        self.assertEqual(3600, res[0][2])
        self.assertEqual(None, res[0][3])
        self.assertEqual(10, res[0][4])
        self.assertEqual(1, res[0][5])

    def test_updateLog(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        plugin.updateLog(id, time=0, duration=7200, val=20, it='num')
        res = plugin.readLog(id, time=0)
        self.assertEqual(1, len(res))
        self.assertEqual(0, res[0][0])
        self.assertEqual(7200, res[0][2])
        self.assertEqual(None, res[0][3])
        self.assertEqual(20, res[0][4])
        self.assertEqual(1, res[0][5])

    def test_insertLog_defaults_to_valid_quality(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        res = plugin.readLog(id, time=0)
        self.assertEqual(0, res[0][7])  # val_quality column, QUALITY_VALID

    def test_insertLog_accepts_explicit_quality(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=None, it='num', quality=1)
        res = plugin.readLog(id, time=0)
        self.assertEqual(1, res[0][7])  # val_quality column, QUALITY_NO_DATA
        self.assertIsNone(res[0][4])  # val_num stays NULL for a no-data row

    def test_updateLog_accepts_explicit_quality(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        plugin.updateLog(id, time=0, duration=3600, val=None, it='num', quality=1)
        res = plugin.readLog(id, time=0)
        self.assertEqual(1, res[0][7])

    def test_readItemCount_returns_int_when_not_connected(self):
        plugin = self.plugin()
        plugin._db.close()
        self.assertEqual(0, plugin.readItemCount())

    def test_deleteLog(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        plugin.deleteLog(id, time=0)
        res = plugin.readLog(id, time=0)
        self.assertEqual(0, len(res))

    def test_deleteLog_with_explicit_cursor_updates_logcount(self):
        # deleteLog()'s internal logcount refresh must run on the caller's
        # cursor when one is passed - a cur=None readLogCount() from inside
        # the caller's transaction() block hits lock()'s same-thread
        # reentrancy guard, so the refresh silently failed (error logged,
        # count never updated) on every explicit-cursor call.
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')

        with plugin._db.transaction() as cur:
            plugin.deleteLog(id, time=0, cur=cur)

        self.assertEqual(0, plugin._item_logcount[id])

    def test_readLogCount_time_end_boundary_matches_deleteLog(self):
        # readLogCount's time_end is inclusive (time <= time_end);
        # deleteLog()/delete_range's is exclusive (time < time_end). A row
        # landing exactly on time_end must be counted by readLogCount()
        # consistently with what deleteLog() actually removes at the same
        # time_end, or a "count then delete" caller
        # (remove_older_than_maxage) over-reports how many rows it removed.
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=1000, duration=1000, val=1.0, it='num')
        plugin.insertLog(id, time=2000, duration=1000, val=2.0, it='num')  # exactly on the boundary below

        count_at_boundary = plugin.readLogCount(id, time_end=2000)
        self.assertEqual(2, count_at_boundary, 'time_end is inclusive for readLogCount')

        # the fix used by remove_older_than_maxage(): shift by 1ms (integer
        # timestamps) to predict exactly what deleteLog() with the same
        # time_end will actually remove
        predicted = plugin.readLogCount(id, time_end=2000 - 1)
        self.assertEqual(1, predicted)

        plugin.deleteLog(id, time_end=2000)
        remaining = plugin.readLogCount(id)
        self.assertEqual(1, remaining, 'time_end is exclusive for deleteLog - the boundary row survives')
        self.assertEqual(2 - predicted, remaining, 'predicted removal count must match what deleteLog actually removed')

    def test_markLogInvalid_preserves_value(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')

        plugin.markLogInvalid(id, time=0)

        res = plugin.readLog(id, time=0)
        self.assertEqual(1, len(res))  # row still exists, unlike deleteLog
        self.assertEqual(2, res[0][7])  # val_quality column, QUALITY_INVALID
        self.assertEqual(10, res[0][4])  # val_num preserved
        self.assertEqual(3600, res[0][2])  # duration preserved

    def test_markLogValid_restores_previously_invalidated_row(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        plugin.markLogInvalid(id, time=0)

        plugin.markLogValid(id, time=0)

        res = plugin.readLog(id, time=0)
        self.assertEqual(0, res[0][7])  # val_quality column, QUALITY_VALID
        self.assertEqual(10, res[0][4])  # val_num still intact

    def test_readLogs(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        plugin.insertLog(id, time=3600, duration=7200, val=20, it='num')
        plugin.insertLog(id, time=7200, duration=3600, val=15, it='num')
        res = plugin.readLogs(id)
        self.assertEqual(3, len(res))
        self.assertEqual(0, res[0][0])
        self.assertEqual(3600, res[0][2])
        self.assertEqual(None, res[0][3])
        self.assertEqual(10, res[0][4])
        self.assertEqual(1, res[0][5])
        self.assertEqual(3600, res[1][0])
        self.assertEqual(7200, res[1][2])
        self.assertEqual(None, res[1][3])
        self.assertEqual(20, res[1][4])
        self.assertEqual(1, res[1][5])
        self.assertEqual(7200, res[2][0])
        self.assertEqual(3600, res[2][2])
        self.assertEqual(None, res[2][3])
        self.assertEqual(15, res[2][4])
        self.assertEqual(1, res[2][5])

    def test_parse_item(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        plugin.parse_item(item)
        self.assertEqual(0, item())

    def test_parse_item_releases_lock_even_if_readitem_raises(self):
        # This block must lock()/cursor() inside a try/finally - if
        # readItem() raises, self._db's lock must still be released, or
        # every future operation on this connection (including shutdown)
        # wedges until process restart.
        plugin = self.plugin()
        item = self.sh.return_item('main.num')

        def failing_readitem(*a, **kw):
            raise RuntimeError('simulated readItem failure')

        with mock.patch.object(plugin, 'readItem', side_effect=failing_readitem):
            with self.assertRaises(RuntimeError):
                plugin.parse_item(item)

        self.assertTrue(plugin._db.lock(0), '_fdb_lock left held after parse_item() propagated an exception')
        plugin._db.release()

    def test_parse_item_with_registered_but_never_logged_item(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.create_item(plugin, item.id())

        with self.assertRaises(AssertionError):
            with self.assertLogs(plugin.logger, level='ERROR'):
                plugin.parse_item(item)

        self.assertEqual(0, item())

    @pytest.mark.skip(reason='test for pending implementation')
    def test_parse_item_reads_cache(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        id = self.create_item(plugin, item.id())
        plugin.updateItem(id, time=7200, val='42', it='num', changed=7200)
        plugin.insertLog(id, time=3600, duration=3600, val='20', it='num', changed=3600)
        plugin.parse_item(item)
        self.assertEqual(42, item())
        self.assertEqual('1970-01-01T00:00:03.600000+00:00', item.prev_change().isoformat())
        self.assertEqual('1970-01-01T00:00:07.200000+00:00', item.last_change().isoformat())

    def test_update_item_without_item(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        item(10)
        plugin.update_item(item)

    def test_update_item_noop_when_not_alive(self):
        # Matches this codebase's own convention (buderus/denon/smarttv/
        # luxtronic2/... all gate update_item() on self.alive) - the
        # plugin must not react to item updates at all while stopped or
        # marked broken (see _mark_db_broken()), not just fail safely
        # further down the call chain.
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        plugin.alive = False
        item(42)
        plugin.update_item(item)
        self.assertEqual([], plugin._buffer_mgr.pop_all(item))

    def test_precision_query_casts_before_rounding(self):
        # Regression: a bare ROUND(expr, precision) has no PostgreSQL
        # overload for double precision (only ROUND(numeric, integer)),
        # and AVG()/SUM() over real/bigint columns (avg/on/duty_cycle's
        # queries) produce double precision there - confirmed live against
        # a real TimescaleDB instance (2026-09-03), independent of native
        # mode entirely. DECIMAL, not NUMERIC - MariaDB rejects NUMERIC as
        # a CAST target, confirmed live against real MariaDB too.
        plugin = self.plugin()
        stmt = plugin._precision_query('AVG(val_num * duration) / AVG(duration)')
        self.assertIn('CAST(AVG(val_num * duration) / AVG(duration) AS DECIMAL(30,10))', stmt)
        self.assertIn('ROUND(', stmt)

    def test_precision_query_result_is_correct_end_to_end(self):
        # Not just string-shape - the cast must not change the actual value.
        plugin = self.plugin()
        stmt = plugin._precision_query('1.23456 * 2')
        (result,) = plugin._db.fetchone(f'SELECT {stmt};')
        self.assertEqual(2.47, float(result))

    @pytest.mark.skip(reason='test for pending implementation')
    def test_update_item_with_cache(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        id = self.create_item(plugin, item.id())
        plugin.updateItem(id, time=7200, val='42', it='num', changed=7200)
        plugin.insertLog(id, time=3600, duration=3600, val='20', it='num', changed=3600)
        plugin.parse_item(item)
        plugin.update_item(item)
        self.assertEqual(42, item())
        self.assertEqual('1970-01-01T00:00:03.600000+00:00', item.prev_change().isoformat())
        self.assertEqual('1970-01-01T00:00:07.200000+00:00', item.last_change().isoformat())

    def test_sqlite_dump_holds_lock_for_the_whole_iterdump(self):
        # sqlite_dump() must acquire self._fdb_lock (via
        # self._db.transaction(), which every other multi-statement access
        # to self._db in this file goes through) before iterating
        # self._db._conn.iterdump(), not bypass it directly - a concurrent
        # write (e.g. a buffer flush) could otherwise interleave with the
        # dump and produce an inconsistent snapshot. Spies on
        # lock()/release() to confirm the dump acquires the lock before
        # iterdump() and releases it after.
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        name = self.create_tmpfile()

        calls = []
        orig_lock = plugin._db.lock
        orig_release = plugin._db.release

        def spy_lock(*a, **kw):
            calls.append('lock')
            return orig_lock(*a, **kw)

        def spy_release(*a, **kw):
            calls.append('release')
            return orig_release(*a, **kw)

        plugin._db.lock = spy_lock
        plugin._db.release = spy_release
        try:
            self.assertTrue(plugin.sqlite_dump(name))
        finally:
            plugin._db.lock = orig_lock
            plugin._db.release = orig_release

        self.assertEqual(['lock', 'release'], calls)
        self.assertIn('main.num', self.read_tmpfile(name))

    def test_sqlite_dump_aborts_cleanly_when_lock_unavailable(self):
        plugin = self.plugin()
        name = self.create_tmpfile()

        with mock.patch.object(plugin._db, 'lock', return_value=False):
            self.assertFalse(plugin.sqlite_dump(name))

        self.assertEqual('', self.read_tmpfile(name), 'must not write a partial/empty dump file when locking fails')

    def test_dump_empty(self):
        name = self.create_tmpfile()
        plugin = self.plugin()
        plugin.dump(name)
        self.assertEqual(
            'item_id;item_name;time;duration;val_str;val_num;val_bool;changed;time_date;changed_date\n',
            self.read_tmpfile(name),
        )

    def test_dump_escapes_semicolon_and_newline_in_val_str(self):
        # dump()'s CSV escaping must handle the ';' delimiter and embedded
        # newlines in val_str, not just embedded '"' - an unescaped ';'
        # shifts every later column in that row, and an unescaped newline
        # splits one logical row into two lines. csv.writer's default
        # quoting handles both correctly.
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.str')
        tricky_value = 'a;b\nc'
        plugin.insertLog(id, time=0, duration=3600, val=tricky_value, it='str', changed=0)
        name = self.create_tmpfile()
        plugin.dump(name)

        with open(name, newline='') as f:
            rows = list(csv.reader(f, delimiter=';'))
        self.assertEqual(2, len(rows), 'the embedded newline must not split the data row into two csv rows')
        header, data_row = rows
        self.assertEqual(tricky_value, data_row[header.index('val_str')])

    @pytest.mark.skip(reason='test for pending implementation')
    def test_dump_log(self):
        self.maxDiff = None
        name = self.create_tmpfile()
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num', changed=0)
        plugin.insertLog(id, time=3600, duration=3600, val=20, it='num', changed=3600)
        plugin.insertLog(id, time=7200, duration=3600, val=15, it='num', changed=7200)
        plugin.insertLog(id, time=10800, duration=3600, val=10, it='num', changed=10800)
        plugin.dump(name)
        self.assertLines(
            'item_id;item_name;time;duration;val_str;val_num;val_bool;changed;time_date;changed_date\n'
            '1;main.num;0;3600;;10.0;1;0;1970-01-01 00:00:00;1970-01-01 00:00:00\n'
            '1;main.num;3600;3600;;20.0;1;3600;1970-01-01 00:00:03.600000;1970-01-01 00:00:03.600000\n'
            '1;main.num;7200;3600;;15.0;1;7200;1970-01-01 00:00:07.200000;1970-01-01 00:00:07.200000\n'
            '1;main.num;10800;3600;;10.0;1;10800;1970-01-01 00:00:10.800000;1970-01-01 00:00:10.800000\n',
            self.read_tmpfile(name),
        )

    @pytest.mark.skip(reason='test for pending implementation')
    def test_dump_log_partial_time(self):
        name = self.create_tmpfile()
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num', changed=0)
        plugin.insertLog(id, time=3600, duration=3600, val=20, it='num', changed=3600)
        plugin.insertLog(id, time=7200, duration=3600, val=15, it='num', changed=7200)
        plugin.insertLog(id, time=10800, duration=3600, val=10, it='num', changed=10800)
        plugin.dump(name, time=3600)
        self.assertLines(
            'item_id;item_name;time;duration;val_str;val_num;val_bool;changed;time_date;changed_date\n'
            '1;main.num;3600;3600;;20.0;1;3600;1970-01-01 00:00:03.600000;1970-01-01 00:00:03.600000\n',
            self.read_tmpfile(name),
        )

    def test_dump_log_partial_time_range(self):
        name = self.create_tmpfile()
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num', changed=0)
        plugin.insertLog(id, time=3600, duration=3600, val=20, it='num', changed=3600)
        plugin.insertLog(id, time=7200, duration=3600, val=15, it='num', changed=7200)
        plugin.insertLog(id, time=10800, duration=3600, val=10, it='num', changed=10800)
        plugin.dump(name, time_start=3600, time_end=7200)
        self.assertLines(
            'item_id;item_name;time;duration;val_str;val_num;val_bool;changed;time_date;changed_date\n'
            '1;main.num;3600;3600;;20.0;1;3600;1970-01-01 00:00:03.600000;1970-01-01 00:00:03.600000\n'
            '1;main.num;7200;3600;;15.0;1;7200;1970-01-01 00:00:07.200000;1970-01-01 00:00:07.200000\n',
            self.read_tmpfile(name),
        )

    @pytest.mark.skip(reason='test for pending implementation')
    def test_dump_log_partial_changed(self):
        name = self.create_tmpfile()
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num', changed=0)
        plugin.insertLog(id, time=3600, duration=3600, val=20, it='num', changed=3600)
        plugin.insertLog(id, time=7200, duration=3600, val=15, it='num', changed=7200)
        plugin.insertLog(id, time=10800, duration=3600, val=10, it='num', changed=10800)
        plugin.dump(name, changed=3600)
        self.assertLines(
            'item_id;item_name;time;duration;val_str;val_num;val_bool;changed;time_date;changed_date\n'
            '1;main.num;3600;3600;;20.0;1;3600;1970-01-01 00:00:03.600000;1970-01-01 00:00:03.600000\n',
            self.read_tmpfile(name),
        )

    def test_dump_log_partial_changed_range(self):
        name = self.create_tmpfile()
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num', changed=0)
        plugin.insertLog(id, time=3600, duration=3600, val=20, it='num', changed=3600)
        plugin.insertLog(id, time=7200, duration=3600, val=15, it='num', changed=7200)
        plugin.insertLog(id, time=10800, duration=3600, val=10, it='num', changed=10800)
        plugin.dump(name, changed_start=3600, changed_end=7200)
        self.assertLines(
            'item_id;item_name;time;duration;val_str;val_num;val_bool;changed;time_date;changed_date\n'
            '1;main.num;3600;3600;;20.0;1;3600;1970-01-01 00:00:03.600000;1970-01-01 00:00:03.600000\n'
            '1;main.num;7200;3600;;15.0;1;7200;1970-01-01 00:00:07.200000;1970-01-01 00:00:07.200000\n',
            self.read_tmpfile(name),
        )

    def test_dump_restores_buffer_on_write_failure(self):
        # If writing a buffered entry to the DB fails and rollback() itself
        # succeeds (the common case), the entry must be restored to the
        # in-memory buffer for a later retry - not silently discarded.
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        id = self.create_item(plugin, 'main.num')
        pending = [BufferEntry(1000, 500, 42.0), BufferEntry(1500, None, 43.0)]
        plugin._buffer_mgr.restore(item, list(pending))

        with mock.patch.object(plugin._log_store, 'upsert', side_effect=RuntimeError('simulated write failure')):
            plugin._dump(items=[item])

        self.assertEqual(pending, plugin._buffer_mgr.pop_all(item))
        self.assertEqual(0, plugin.readLogCount(id))

        # Retry with the fault removed: the restored data must now be written.
        plugin._buffer_mgr.restore(item, list(pending))
        plugin._dump(items=[item])
        self.assertEqual(2, plugin.readLogCount(id))
        self.assertEqual([], plugin._buffer_mgr.pop_all(item))

    def test_dump_finalize_rewrites_by_default_when_attribute_unset(self):
        # Regression: plugin.yaml documents database_write_on_shutdown's
        # default as True, but item parsing never injects a plugin-declared
        # item_attribute default into an item's conf when the item omits
        # the attribute entirely (lib/item/item.py's per-item conf loop
        # only converts attributes already present; the metadata default is
        # only ever used inside a "value failed to convert" warning
        # message, never assigned back). get_iattr_value() without its own
        # default= therefore returned None for main.num (which sets no
        # database_write_on_shutdown attribute at all), silently inverting
        # the documented True default to False.
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        id = self.create_item(plugin, 'main.num')
        self.assertNotIn('database_write_on_shutdown', item.conf)

        plugin._dump(items=[item], finalize=True)

        self.assertEqual(1, plugin.readLogCount(id), 'default (attribute unset) must still rewrite on shutdown')

    def test_dump_finalize_honours_explicit_write_on_shutdown_false(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        item.conf['database_write_on_shutdown'] = False
        id = self.create_item(plugin, 'main.num')

        plugin._dump(items=[item], finalize=True)

        self.assertEqual(0, plugin.readLogCount(id), 'explicit False must still block the shutdown rewrite')

    def test_dump_lock_timeout_aborts_whole_method_not_just_one_item(self):
        # A lock-acquisition timeout (transaction() raising TimeoutError)
        # must abort the entire _dump() call - not just skip the failing
        # item and continue, unlike an ordinary mid-transaction failure
        # (see test_dump_restores_buffer_on_write_failure). Matches the
        # original self._db.lock(300) check's behaviour: restore the
        # buffer, log, release self._dump_lock, return immediately.
        plugin = self.plugin()
        item1 = self.sh.return_item('main.num')
        item2 = self.sh.return_item('main.str')
        id1 = self.create_item(plugin, 'main.num')
        id2 = self.create_item(plugin, 'main.str')
        pending1 = [BufferEntry(1000, 500, 42.0)]
        pending2 = [BufferEntry(1000, 500, 'x')]
        plugin._buffer_mgr.restore(item1, list(pending1))
        plugin._buffer_mgr.restore(item2, list(pending2))

        # verify() mocked directly - it has its own retry/delay loop that
        # would make this test slow and would exercise its own "not
        # recovered" abort path instead of transaction()'s.
        with mock.patch.object(plugin._db, 'verify', return_value=1):
            with mock.patch.object(plugin._db, 'lock', return_value=False):
                plugin._dump(items=[item1, item2])  # must not raise

        # item1 (the one being processed when the lock failed) restored...
        self.assertEqual(pending1, plugin._buffer_mgr.pop_all(item1))
        # ...and item2 never even attempted - the whole call aborted.
        self.assertEqual(pending2, plugin._buffer_mgr.pop_all(item2))
        self.assertEqual(0, plugin.readLogCount(id1))
        self.assertEqual(0, plugin.readLogCount(id2))

        # self._dump_lock must have been released, not left held - a
        # subsequent dump must be able to proceed normally.
        plugin._buffer_mgr.restore(item1, list(pending1))
        plugin._dump(items=[item1])
        self.assertEqual(1, plugin.readLogCount(id1))

    def test_initialize_db_maint_throttle_logs_correct_delta(self):
        # The maintenance-connection reconnect-throttle branch must
        # reference time_delta_last_maint_connect (the just-computed
        # value), not time_delta_last_connect (the main connection's delta,
        # only assigned when the main connection itself needs reconnecting)
        # - with the main connection already up, that variable is never
        # assigned in this call at all.
        plugin = self.plugin()
        self.assertTrue(plugin._db.connected())
        plugin._db_maint._connected = False

        with mock.patch('plugins.database.time.time', return_value=1000.0):
            plugin.last_maint_connect_time = 995.0  # delta = 5, within the 20s throttle window
            with self.assertLogs(level='ERROR') as logs:
                result = plugin._initialize_db()

        self.assertFalse(result)
        [message] = logs.output
        self.assertIn('Delta time: 5.0', message)

    def test_initialize_db_stops_plugin_activity_on_setup_error(self):
        # DatabaseSetupError is permanent (see its docstring) - the plugin
        # must stop its own recurring work rather than keep polling a
        # schema it already knows is broken.
        plugin = self.plugin()
        plugin._db_initialized = False
        with mock.patch.object(plugin._db, 'setup', side_effect=DatabaseSetupError('simulated permanent failure')):
            with mock.patch.object(plugin, '_stop_schedulers') as stop_schedulers:
                with self.assertLogs(level='CRITICAL'):
                    result = plugin._initialize_db()

        self.assertFalse(result)
        self.assertTrue(plugin._db_broken)
        self.assertFalse(plugin.alive)
        stop_schedulers.assert_called_once()

    def test_initialize_db_short_circuits_once_broken_without_touching_setup_again(self):
        plugin = self.plugin()
        plugin._db_broken = True
        with mock.patch.object(plugin._db, 'setup') as setup:
            result = plugin._initialize_db()

        self.assertFalse(result)
        setup.assert_not_called()

    def test_fetchone_fetchall_do_not_use_mutable_default_params(self):
        plugin = self.plugin()
        for name in ('_fetchone', '_fetchall'):
            default = inspect.signature(getattr(plugin, name)).parameters['params'].default
            self.assertIsNone(default, f'{name} params default should be None, not a shared mutable {default!r}')

    def test_query_own_cur_lock_timeout_returns_none_not_raises(self):
        # _query() migrated its owns_cur path to self._db.transaction(),
        # which raises TimeoutError on a failed lock acquisition - a
        # different signal than the original self._db.lock(300) check it
        # replaced (that just logged and returned None). Every caller
        # throughout this file treats a None result as "query failed",
        # not something to catch - preserve that contract explicitly:
        # transaction()'s TimeoutError must be translated back to None
        # here, never left to propagate.
        # Calls plugin._fetchall() directly, not a higher-level method like
        # readLogCount() - several of those convert _query()'s None into
        # their own default (e.g. readLogCount() returns 0 for a None
        # result), which would mask the exact contract under test here.
        plugin = self.plugin()
        item_id = self.create_item(plugin, 'main.num')
        plugin._db.commit()

        # verify() mocked directly (not exercised via a real failing
        # lock()) - it has its own retry/delay loop that would make this
        # test slow and would exercise verify()'s own "not recovered"
        # return-None path instead of transaction()'s.
        with mock.patch.object(plugin._db, 'verify', return_value=1):
            with mock.patch.object(plugin._db, 'lock', return_value=False):
                result = plugin._fetchall('SELECT count(*) FROM {log} WHERE item_id = :id;', {'id': item_id})

        self.assertIsNone(result, '_query() must return None on lock timeout, not raise')

    def test_cleanup_empty(self):
        plugin = self.plugin()
        plugin.cleanup()
        items = plugin.readItems()
        self.assertEqual(0, len(items))

    def test_cleanup(self):
        plugin = self.plugin()
        self.create_item(plugin, 'main.num')
        self.create_item(plugin, 'main.nodb')
        # cleanup() only sets flags for the scheduler; drive the orphan-removal
        # loop directly so the test doesn't depend on a running scheduler.
        #
        # Explicit commit required: insertItem() writes to _db but does not
        # call commit().  The plugin maintains two separate SQLite connections
        # (_db for normal I/O, _db_maint for maintenance tasks).  SQLite
        # transaction isolation means _db_maint cannot see data that is still
        # in an open transaction on _db, so build_orphanlist() would return an
        # empty list and remove_orphan_items() would crash with IndexError.
        # In production the scheduler calls _dump() → _db.commit() before
        # remove_older_than_maxage() ever runs; here we replicate that.
        plugin._db.commit()
        plugin.cleanup()
        plugin.build_orphanlist()
        while plugin.remove_orphan:
            plugin.remove_orphan_items()
        items = plugin.readItems()
        self.assertEqual(1, len(items))
        self.assertEqual('main.num', items[0][1])

    def test_delete_orphan_bulk_delete_removes_chunk_of_log_rows(self):
        # 'DELETE FROM {log} WHERE item_id = :id LIMIT :maxrecords' (no
        # ORDER BY, but still a bare LIMIT on a top-level DELETE) is not
        # valid SQLite syntax without the non-default
        # SQLITE_ENABLE_UPDATE_DELETE_LIMIT compile flag - same class of
        # constraint as remove_older_than_maxage()'s bulk-delete branch
        # (see test_maxage_action.py). Must use a rowid-subquery instead.
        # Exercises the real SQL - not mocked - and checks the chunk size
        # is actually respected: some rows deleted, some left (item stays
        # orphaned, to be finished next cycle).
        plugin = self.plugin()
        plugin.delete_orphan_chunk_size = 2
        item_id = self.create_item(plugin, 'main.nodb')
        for i in range(4):
            plugin.insertLog(item_id, time=i * 1000, duration=1000, val=float(i), it='num')
        plugin._db.commit()
        plugin.cleanup()
        plugin.build_orphanlist()
        self.assertIn('main.nodb', plugin.orphanlist)

        plugin.remove_orphan_items()

        self.assertEqual(2, plugin.readLogCount(item_id), 'must delete exactly one chunk (2 rows), not all/none')
        self.assertIn('main.nodb', plugin.orphanlist, 'item must remain orphaned - more log rows still need deleting')

    def test_remove_orphan_items_survives_stale_maintenance_connection(self):
        # A hiccup on the dedicated maintenance connection (_db_maint),
        # independent from the main _db connection (e.g. a brief
        # backup-induced DB outage), must not crash orphan cleanup
        # outright. _delete_orphan() drives a raw cursor from _db_maint
        # straight into _execute(..., cur=cur); passing an explicit cursor
        # makes _query() skip its verify()/reconnect branch entirely, so a
        # DBAPI error there must be caught, not left to propagate uncaught
        # up the call chain. It must instead be logged and the item
        # requeued for the next cycle.
        plugin = self.plugin()
        self.create_item(plugin, 'main.num')
        self.create_item(plugin, 'main.nodb')
        plugin._db.commit()
        plugin.cleanup()
        plugin.build_orphanlist()
        self.assertTrue(plugin.remove_orphan)
        self.assertIn('main.nodb', plugin.orphanlist)

        class _BrokenCursor:
            def execute(self, *a, **kw):
                raise RuntimeError('simulated stale maintenance-connection error')

        with mock.patch.object(plugin._db_maint, 'cursor', return_value=_BrokenCursor()):
            with self.assertLogs(level='ERROR'):
                plugin.remove_orphan_items()  # must not raise

        # item must survive for a retry on the next cycle, not vanish silently
        self.assertIn('main.nodb', plugin.orphanlist)
