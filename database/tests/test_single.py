import decimal
from unittest import mock

from plugins.database import Database
from plugins.database.constants import QUALITY_INVALID, QUALITY_NO_DATA
from plugins.database.tests.base import TestDatabaseBase


class TestDatabaseSingleQualityFilter(TestDatabaseBase):
    """A no-data gap row (val_quality=QUALITY_NO_DATA) must be fully
    excluded from time-weighted aggregations - not just its value (which
    NULL-propagation already skips) but its duration too, since letting the
    gap's duration count in the denominator while its value is dropped from
    the numerator silently skews the result."""

    def test_avg_excludes_gap_entirely_inside_window(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=self.t(0), duration=self.t(2), val=10, it='num')
        plugin.insertLog(id, time=self.t(2), duration=self.t(1), val=None, it='num', quality=QUALITY_NO_DATA)
        plugin.insertLog(id, time=self.t(3), duration=self.t(2), val=20, it='num')

        # end=6, not 5: a row ending exactly *on* time_end hits a separate,
        # pre-existing double-counting bug in the duration formula (case1's
        # time+duration<=time_end and case3's time+duration>=time_end both
        # match when a row's end exactly equals time_end) - out of scope
        # for the quality filter under test here.
        res = plugin._single('avg', start=self.t(0), end=self.t(6), item='main.num')

        # Correct time-weighted avg of 10 (dur=2) and 20 (dur=2), gap excluded entirely: 15
        self.assertSingle(15, res)

    def test_avg_excludes_gap_at_start_boundary(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        # Gap starts before the query window and is the "carry-over" row
        # picked up by the time < time_start lookback subquery.
        plugin.insertLog(id, time=self.t(1), duration=self.t(4), val=None, it='num', quality=QUALITY_NO_DATA)
        plugin.insertLog(id, time=self.t(5), duration=self.t(1), val=20, it='num')

        res = plugin._single('avg', start=self.t(2), end=self.t(6), item='main.num')

        # Only the valid row (20, dur=1) should count; the gap's clipped
        # in-window duration must not appear in the denominator either.
        self.assertSingle(20, res)

    def test_avg_excludes_gap_at_end_boundary(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=self.t(0), duration=self.t(3), val=10, it='num')
        # Gap starts inside the window but extends well past its end.
        plugin.insertLog(id, time=self.t(3), duration=self.t(17), val=None, it='num', quality=QUALITY_NO_DATA)

        res = plugin._single('avg', start=self.t(0), end=self.t(4), item='main.num')

        # Only the valid row (10, dur=3) should count.
        self.assertSingle(10, res)


class TestDatabaseSingleInvalidQualityFilter(TestDatabaseBase):
    """A manually invalidated row (val_quality=QUALITY_INVALID) must be
    excluded from aggregations exactly like a QUALITY_NO_DATA gap - the
    exclusion filter matches on val_quality alone, so this must hold even
    though (unlike a gap) the row still carries a real, non-NULL value."""

    def test_avg_excludes_invalidated_row_despite_preserved_value(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=self.t(0), duration=self.t(2), val=10, it='num')
        # Value is preserved (unlike a QUALITY_NO_DATA gap), not None -
        # only the quality flag marks it as excluded.
        plugin.insertLog(id, time=self.t(2), duration=self.t(1), val=999, it='num', quality=QUALITY_INVALID)
        plugin.insertLog(id, time=self.t(3), duration=self.t(2), val=20, it='num')

        res = plugin._single('avg', start=self.t(0), end=self.t(6), item='main.num')

        # Same math as the QUALITY_NO_DATA case: 15, not skewed by the 999.
        self.assertSingle(15, res)


class TestDatabaseSingle(TestDatabaseBase):
    def test_single_no_log_returns_none(self):
        plugin = self.plugin()
        res = plugin._single('avg', start=0, item='main.num')
        self.assertIsNone(res)

    def test_single_raw_no_log_returns_none(self):
        # Regression: every other func here is an ungrouped SQL aggregate,
        # which always returns exactly one (NULL) row even with no matching
        # data - 'raw' has no aggregate and no GROUP BY, so an empty range
        # genuinely returns zero rows, and logs['tuples'][0][0] raised
        # IndexError instead of reporting "no data" like every other func.
        plugin = self.plugin()
        res = plugin._single('raw', start=0, item='main.num')
        self.assertIsNone(res)

    def test_single_avg(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 20)])
        self.dump_log(plugin, 'main.num')
        res = plugin._single('avg', start=self.t(0), end='now', item='main.num')
        self.assertSingle(15, res)

    def test_single_min(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 20)])
        res = plugin._single('min', start=self.t(0), end='now', item='main.num')
        self.assertSingle(10, res)

    def test_single_max(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 20)])
        res = plugin._single('max', start=self.t(0), end='now', item='main.num')
        self.assertSingle(20, res)

    def test_single_sum(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 20)])
        res = plugin._single('sum', start=self.t(0), end='now', item='main.num')
        self.assertSingle(30, res)

    def test_single_count(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 20)])
        res = plugin._single('count', start=self.t(0), end='now', item='main.num')
        self.assertSingle(2, res)

    def test_single_count_eq_10(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 20)])
        res = plugin._single('count=10', start=self.t(0), end='now', item='main.num')
        self.assertSingle(1, res)

    def test_single_count_gt_10(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 20)])
        res = plugin._single('count>10', start=self.t(0), end='now', item='main.num')
        self.assertSingle(1, res)

    def test_single_count_lt_20(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 20)])
        res = plugin._single('count<20', start=self.t(0), end='now', item='main.num')
        self.assertSingle(1, res)

    def test_single_raw(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 20)])
        res = plugin._single('raw', start=self.t(0), end='now', item='main.num')
        self.assertSingle(20, res)

    def test_single_on(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 20)])
        res = plugin._single('on', start=0, end='now', item='main.num')
        self.assertSingle(1, res)

    def test_single_coerces_mariadb_decimal_to_float(self):
        # Regression: MariaDB/MySQL return decimal.Decimal (not float) for
        # SUM()/AVG() over exact-numeric columns - 'on''s SUM(val_bool *
        # duration) is exactly this case (val_bool and duration are both
        # integer-typed columns; sqlite, used by this test fixture, never
        # returns Decimal at all, so this simulates a real driver's return
        # value directly). Decimal doesn't mix with the plain floats
        # _series() injects elsewhere (e.g. float(item()) boundary
        # values), so an uncoerced Decimal risks a TypeError there, and a
        # bare Decimal returned to a logic doing arithmetic on it.
        plugin = self.plugin()
        with mock.patch.object(plugin, '_fetchall', return_value=[(decimal.Decimal('0.5'),)]):
            res = plugin._single('on', start=0, end='now', item='main.num')
        self.assertIsInstance(res, float)
        self.assertEqual(0.5, res)

    def test_single_returns_last_value_outside_range(self):
        """When selecting single value and the database contains one last
        value return it
        """
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 20), (3, None, 30)])
        self.dump_log(plugin, 'main.num')
        res = plugin._single('avg', start=self.t(2), end=self.t(4), item='main.num')
        self.assertSingle(25, res)
