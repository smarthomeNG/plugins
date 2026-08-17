"""
Tests for Database._resolve_sqlite_database_path() — resolves a relative
sqlite 'database:<path>' connect entry to an absolute path anchored at
SmartHomeNG's install directory, so a later reconnect (e.g. triggered by
Items.rename_item()'s STOP_ON_ITEM_CHANGE pause/resume cycle calling run()
well after startup) isn't at the mercy of the process's current working
directory at that later moment — sqlite3.connect() resolves a relative
path against os.getcwd() at call time, not once at startup.
"""

import os

from plugins.database.tests.base import TestDatabaseBase


class TestResolveSqliteDatabasePath(TestDatabaseBase):
    def test_relative_database_path_resolved_to_absolute(self):
        plugin = self.plugin()

        resolved = plugin._resolve_sqlite_database_path(['database:./var/db/smarthomeng.db', 'check_same_thread:0'])

        expected = os.path.join(plugin.get_sh().get_basedir(), './var/db/smarthomeng.db')
        self.assertEqual(resolved[0], f'database:{expected}')
        self.assertTrue(os.path.isabs(resolved[0].partition(':')[2]))

    def test_other_connect_entries_are_left_untouched(self):
        plugin = self.plugin()

        resolved = plugin._resolve_sqlite_database_path(['database:./var/db/smarthomeng.db', 'check_same_thread:0'])

        self.assertEqual(resolved[1], 'check_same_thread:0')

    def test_already_absolute_database_path_is_untouched(self):
        plugin = self.plugin()

        resolved = plugin._resolve_sqlite_database_path(['database:/abs/path/smarthomeng.db'])

        self.assertEqual(resolved, ['database:/abs/path/smarthomeng.db'])

    def test_in_memory_database_is_untouched(self):
        plugin = self.plugin()

        resolved = plugin._resolve_sqlite_database_path(['database::memory:'])

        self.assertEqual(resolved, ['database::memory:'])

    def test_non_sqlite_driver_leaves_connect_untouched(self):
        plugin = self.plugin()
        plugin.driver = 'pymysql'

        resolved = plugin._resolve_sqlite_database_path(['database:./relative/should/not/be/touched'])

        self.assertEqual(resolved, ['database:./relative/should/not/be/touched'])

    def test_non_list_connect_is_returned_unchanged(self):
        plugin = self.plugin()

        connect = {'database': './var/db/smarthomeng.db'}
        resolved = plugin._resolve_sqlite_database_path(connect)

        self.assertIs(resolved, connect)
