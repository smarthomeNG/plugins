#!/usr/bin/env python3
"""Tests for plugins.database.utils — pure functions, no SmartHomeNG required."""

import datetime
import unittest

from plugins.database.utils import (
    encode_value,
    decode_value,
    to_timestamp,
    from_timestamp,
    apply_table_names,
    build_where_clause,
)
from plugins.database.constants import QUALITY_VALID, QUALITY_NO_DATA


class TestEncodeValue(unittest.TestCase):
    def test_num_encodes_to_val_num(self):
        r = encode_value('num', 3.14)
        self.assertAlmostEqual(r['val_num'], 3.14)
        self.assertIsNone(r['val_str'])
        self.assertEqual(r['val_bool'], 1)

    def test_bool_true(self):
        r = encode_value('bool', True)
        self.assertEqual(r['val_num'], 1.0)
        self.assertIsNone(r['val_str'])
        self.assertEqual(r['val_bool'], 1)

    def test_bool_false(self):
        r = encode_value('bool', False)
        self.assertEqual(r['val_num'], 0.0)
        self.assertEqual(r['val_bool'], 0)

    def test_str_encodes_to_val_str(self):
        r = encode_value('str', 'hello')
        self.assertEqual(r['val_str'], 'hello')
        self.assertIsNone(r['val_num'])
        self.assertEqual(r['val_bool'], 1)

    def test_none_value_all_null(self):
        """None value (QUALITY_NO_DATA) must produce all-NULL columns."""
        r = encode_value('num', None)
        self.assertIsNone(r['val_str'])
        self.assertIsNone(r['val_num'])
        self.assertIsNone(r['val_bool'])

    def test_none_value_independent_of_type(self):
        for t in ('num', 'bool', 'str', 'list', 'dict'):
            with self.subTest(item_type=t):
                r = encode_value(t, None)
                self.assertIsNone(r['val_str'])
                self.assertIsNone(r['val_num'])
                self.assertIsNone(r['val_bool'])


class TestDecodeValue(unittest.TestCase):
    def test_num_roundtrip(self):
        enc = encode_value('num', 42.5)
        self.assertAlmostEqual(decode_value('num', **enc), 42.5)

    def test_bool_roundtrip(self):
        for v in (True, False):
            enc = encode_value('bool', v)
            self.assertEqual(decode_value('bool', **enc), v)

    def test_str_roundtrip(self):
        enc = encode_value('str', 'test')
        self.assertEqual(decode_value('str', **enc), 'test')

    def test_none_value_returns_none(self):
        """All-NULL columns (QUALITY_NO_DATA row) must decode back to None."""
        enc = encode_value('num', None)
        self.assertIsNone(decode_value('num', **enc))


class TestTimestampConversion(unittest.TestCase):
    def test_roundtrip_millisecond_precision(self):
        dt = datetime.datetime(2023, 6, 15, 12, 0, 0, 500_000)
        ts = to_timestamp(dt)
        self.assertEqual(ts % 1000, 500)  # 500ms preserved

    def test_from_timestamp_epoch_zero(self):
        dt = from_timestamp(0)
        self.assertEqual(dt.year, 1970)


class TestApplyTableNames(unittest.TestCase):
    TABLE_NAMES = {'log': 'my_log', 'item': 'my_item', 'item_columns': 'id,name', 'log_columns': 'time,item_id'}

    def test_replaces_log(self):
        sql = apply_table_names('SELECT * FROM {log}', self.TABLE_NAMES)
        self.assertIn('my_log', sql)
        self.assertNotIn('{log}', sql)

    def test_replaces_item(self):
        sql = apply_table_names('SELECT {item_columns} FROM {item}', self.TABLE_NAMES)
        self.assertIn('my_item', sql)
        self.assertIn('id,name', sql)


class TestBuildWhereClause(unittest.TestCase):
    def test_item_id_only(self):
        where, params = build_where_clause(42)
        self.assertEqual(where, 'item_id = :item_id')
        self.assertEqual(params['item_id'], 42)

    def test_with_time_range(self):
        where, params = build_where_clause(1, time_start=1000, time_end=2000)
        self.assertIn('time > :time_start', where)
        self.assertIn('time < :time_end', where)
        self.assertEqual(params['time_start'], 1000)
        self.assertEqual(params['time_end'], 2000)

    def test_no_spurious_clauses(self):
        """Only item_id clause when no optional args are given."""
        where, params = build_where_clause(5)
        self.assertNotIn('time', where)
        self.assertNotIn('changed', where)

    def test_exact_time(self):
        where, params = build_where_clause(1, time=500)
        self.assertIn('time = :time', where)
        self.assertEqual(params['time'], 500)


class TestBufferEntry(unittest.TestCase):
    def test_default_quality_is_valid(self):
        from plugins.database.constants import BufferEntry

        e = BufferEntry(time=1000, duration=None, value=42.0)
        self.assertEqual(e.quality, QUALITY_VALID)

    def test_no_data_quality(self):
        from plugins.database.constants import BufferEntry

        e = BufferEntry(time=1000, duration=None, value=None, quality=QUALITY_NO_DATA)
        self.assertEqual(e.quality, QUALITY_NO_DATA)
        self.assertIsNone(e.value)

    def test_named_field_access(self):
        from plugins.database.constants import BufferEntry

        e = BufferEntry(time=100, duration=50, value='x')
        self.assertEqual(e.time, 100)
        self.assertEqual(e.duration, 50)
        self.assertEqual(e.value, 'x')

    def test_replace_duration(self):
        from plugins.database.constants import BufferEntry

        e = BufferEntry(time=100, duration=None, value=3.0)
        closed = e._replace(duration=500)
        self.assertEqual(closed.duration, 500)
        self.assertEqual(closed.time, 100)  # unchanged


if __name__ == '__main__':
    unittest.main(verbosity=2)
