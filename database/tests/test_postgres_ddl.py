#!/usr/bin/env python3
"""Tests for _setup()'s PostgreSQL/TimescaleDB (psycopg2/psycopg) DDL branch -
the schema differences from sqlite3/MySQL: SERIAL vs. AUTO_INCREMENT vs. bare
INTEGER PRIMARY KEY, ALTER COLUMN ... TYPE vs. MODIFY, DROP INDEX without an
ON clause, and SMALLINT vs. TINYINT (PostgreSQL has no TINYINT type).
"""

import types
from unittest import mock

from plugins.database.tests.base import TestDatabaseBase


class TestPostgresSetupDDL(TestDatabaseBase):
    def _psycopg_plugin(self, **overrides):
        # Fake driver, not a real psycopg2 install - CI has no such package.
        # _setup's branch only inspects self.driver (a plain string), not
        # the imported module, so the fake's actual shape doesn't matter
        # beyond satisfying Database.__init__'s import + paramstyle checks.
        fake_driver = types.SimpleNamespace(paramstyle='pyformat', __name__='psycopg2')
        with mock.patch('lib.db.importlib.import_module', return_value=fake_driver):
            return self.plugin(driver='psycopg2', **overrides)

    def test_item_id_column_uses_serial(self):
        plugin = self._psycopg_plugin()
        self.assertIn('SERIAL PRIMARY KEY', plugin._setup['2'][0])

    def test_autoincrement_retrofit_is_a_noop(self):
        # SERIAL already has a sequence from creation - nothing to retrofit,
        # unlike MySQL's version-8 ALTER TABLE ... AUTO_INCREMENT step.
        plugin = self._psycopg_plugin()
        self.assertEqual('SELECT 1;', plugin._setup['8'][0])

    def test_name_widen_uses_alter_column_type_not_modify(self):
        plugin = self._psycopg_plugin()
        stmt = plugin._setup['9'][0]
        self.assertIn('ALTER COLUMN name TYPE', stmt)
        self.assertNotIn('MODIFY', stmt)

    def test_drop_index_has_no_on_table_clause(self):
        # MySQL's DROP INDEX ... ON {item} syntax is invalid on PostgreSQL,
        # which drops indexes by name alone.
        plugin = self._psycopg_plugin()
        stmt = plugin._setup['10'][0]
        self.assertIn('DROP INDEX {item}_name;', stmt)
        self.assertNotIn(' ON ', stmt)

    def test_recreate_index_has_no_prefix_length(self):
        # MySQL's name(191) prefix-length index works around an InnoDB
        # indexed-column byte limit that doesn't exist on PostgreSQL.
        plugin = self._psycopg_plugin()
        stmt = plugin._setup['11'][0]
        self.assertIn('(name)', stmt)
        self.assertNotIn('(name(', stmt)

    def test_val_quality_column_uses_smallint_not_tinyint(self):
        plugin = self._psycopg_plugin()
        stmt = plugin._setup['7'][0]
        self.assertIn('SMALLINT', stmt)
        self.assertNotIn('TINYINT', stmt)

    def test_val_quality_statement_still_carries_log_placeholder(self):
        # Regression: an early version of this branch called .format() on
        # the SQL string directly, which choked on the still-unresolved
        # {log} placeholder (KeyError) before _prepare() ever got to run -
        # broke for every driver, not just PostgreSQL.
        plugin = self._psycopg_plugin()
        stmt = plugin._setup['7'][0]
        self.assertIn('{log}', stmt)

    def test_val_bool_column_uses_smallint_not_boolean(self):
        # Regression: PostgreSQL's BOOLEAN is a real, strictly-typed column
        # that rejects an integer 0/1 outright - confirmed against a live
        # instance ("column val_bool is of type boolean but expression is
        # of type integer"). encode_value() always writes int(bool(value))
        # for every item type, never an actual Python bool, so every single
        # log/item write with a non-NULL value would fail against a
        # BOOLEAN-typed column on PostgreSQL specifically (sqlite3 is
        # dynamically typed and MySQL/MariaDB's BOOLEAN is just a
        # TINYINT(1) alias - neither of those enforce this).
        plugin = self._psycopg_plugin()
        log_stmt = plugin._setup['1'][0]
        item_stmt = plugin._setup['2'][0]
        self.assertIn('val_bool SMALLINT', log_stmt)
        self.assertIn('val_bool SMALLINT', item_stmt)
        self.assertNotIn('BOOLEAN', log_stmt)
        self.assertNotIn('BOOLEAN', item_stmt)

    def test_val_bool_statements_still_carry_table_placeholders(self):
        plugin = self._psycopg_plugin()
        self.assertIn('{log}', plugin._setup['1'][0])
        self.assertIn('{item}', plugin._setup['2'][0])

    def test_sqlite3_and_mysql_ddl_unaffected(self):
        # The three-way branch must not have disturbed the other two paths.
        sqlite_plugin = self.plugin()
        self.assertIn('id INTEGER PRIMARY KEY', sqlite_plugin._setup['2'][0])
        self.assertNotIn('SERIAL', sqlite_plugin._setup['2'][0])
        self.assertIn('val_bool BOOLEAN', sqlite_plugin._setup['1'][0])

        fake_mysql = types.SimpleNamespace(paramstyle='pyformat', __name__='pymysql')
        with mock.patch('lib.db.importlib.import_module', return_value=fake_mysql):
            mysql_plugin = self.plugin(driver='pymysql')
        self.assertIn('AUTO_INCREMENT', mysql_plugin._setup['2'][0])
        self.assertIn('TINYINT', mysql_plugin._setup['7'][0])
        self.assertIn('val_bool BOOLEAN', mysql_plugin._setup['1'][0])
