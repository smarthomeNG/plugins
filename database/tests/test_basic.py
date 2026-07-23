import inspect
import os
import datetime
import tempfile
import pytest
from unittest import mock

from plugins.database import Database
from plugins.database.constants import BufferEntry
from plugins.database.tests.base import TestDatabaseBase


class TestDatabaseBasic(TestDatabaseBase):
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

    def test_dump_empty(self):
        name = self.create_tmpfile()
        plugin = self.plugin()
        plugin.dump(name)
        self.assertEqual(
            'item_id;item_name;time;duration;val_str;val_num;val_bool;changed;time_date;changed_date\n',
            self.read_tmpfile(name),
        )

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

    def test_initialize_db_maint_throttle_logs_correct_delta(self):
        # Regression: the maintenance-connection reconnect-throttle branch
        # referenced time_delta_last_connect (the main connection's delta,
        # only assigned when the main connection itself needed reconnecting)
        # instead of the just-computed time_delta_last_maint_connect. With
        # the main connection already up - so that variable is never
        # assigned in this call at all - this raised NameError instead of
        # logging the (wrong) number.
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

    def test_fetchone_fetchall_do_not_use_mutable_default_params(self):
        plugin = self.plugin()
        for name in ('_fetchone', '_fetchall'):
            default = inspect.signature(getattr(plugin, name)).parameters['params'].default
            self.assertIsNone(default, f'{name} params default should be None, not a shared mutable {default!r}')

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

    def test_remove_orphan_items_survives_stale_maintenance_connection(self):
        # Regression for smarthomeNG/plugins#1004: a hiccup on the dedicated
        # maintenance connection (_db_maint), independent from the main _db
        # connection (e.g. a brief backup-induced DB outage), currently
        # crashes orphan cleanup outright. _delete_orphan() drives a raw
        # cursor from _db_maint straight into _execute(..., cur=cur); passing
        # an explicit cursor makes _query() skip its verify()/reconnect
        # branch entirely, and the resulting DBAPI error is re-raised with no
        # try/except anywhere up the call chain - matching the uncaught
        # "pymysql.err.InterfaceError: (0, '')" loop reported in the issue.
        # It must instead be logged and the item requeued for the next cycle.
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
