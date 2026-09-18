import sqlite3

from plugins.database.tests.base import TestDatabaseBase


class TestConvertLegacyItemSchema(TestDatabaseBase):
    def _make_legacy(self, plugin, rows):
        """Replaces the item table with a plain, non-key id column and
        seeds *rows* with explicit ids, via a raw connection to the same
        file."""
        conn = sqlite3.connect(self._db_file.name)
        conn.execute('DROP INDEX IF EXISTS item_id;')
        conn.execute('DROP INDEX IF EXISTS item_name;')
        conn.execute('DROP TABLE item;')
        conn.execute(
            'CREATE TABLE item (id INTEGER, name varchar(255), time BIGINT,'
            ' val_str TEXT, val_num REAL, val_bool BOOLEAN, changed BIGINT);'
        )
        # migrations 5/6 create these unconditionally, on every driver, including legacy tables.
        conn.execute('CREATE UNIQUE INDEX item_id ON item (id);')
        conn.execute('CREATE INDEX item_name ON item (name);')
        for item_id, name in rows:
            conn.execute(
                'INSERT INTO item (id, name, time, val_str, val_num, val_bool, changed)'
                ' VALUES (?, ?, 1000, NULL, 1.0, 0, 1000);',
                (item_id, name),
            )
        conn.commit()
        conn.close()
        plugin._item_store._id_autoincrement = None

    def test_needs_conversion_false_on_a_fresh_install(self):
        plugin = self.plugin()
        self.assertFalse(plugin.item_table_needs_conversion())

    def test_needs_conversion_true_for_legacy_schema(self):
        plugin = self.plugin()
        self._make_legacy(plugin, [(1, 'legacy.one')])
        self.assertTrue(plugin.item_table_needs_conversion())

    def test_convert_returns_none_when_nothing_to_convert(self):
        plugin = self.plugin()
        self.assertIsNone(plugin.convert_legacy_item_schema())

    def test_convert_fixes_detection_and_preserves_existing_rows(self):
        plugin = self.plugin()
        self._make_legacy(plugin, [(1, 'legacy.one'), (2, 'legacy.two')])

        backup_name = plugin.convert_legacy_item_schema()

        self.assertIsNotNone(backup_name)
        self.assertFalse(plugin.item_table_needs_conversion())
        self.assertEqual(1, plugin.id('legacy.one', create=False))
        self.assertEqual(2, plugin.id('legacy.two', create=False))

    def test_convert_keeps_the_old_table_as_a_backup(self):
        plugin = self.plugin()
        self._make_legacy(plugin, [(1, 'legacy.one')])

        backup_name = plugin.convert_legacy_item_schema()

        conn = sqlite3.connect(self._db_file.name)
        rows = conn.execute(f'SELECT id, name FROM {backup_name};').fetchall()
        conn.close()
        self.assertEqual([(1, 'legacy.one')], rows)

    def test_new_item_gets_a_real_id_after_conversion(self):
        plugin = self.plugin()
        self._make_legacy(plugin, [(1, 'legacy.one')])
        plugin.convert_legacy_item_schema()

        new_id = plugin.insertItem('brand.new')

        row = plugin.readItem('brand.new')
        self.assertIsNotNone(row)
        self.assertEqual(new_id, row[0], "the row's own id column must equal what insertItem() returned")
