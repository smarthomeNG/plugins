import pytest

from lib.db import NO_CURSOR
from plugins.database import Database
from plugins.database.tests.base import TestDatabaseBase


class TestDatabaseSeries(TestDatabaseBase):
    SLICE1_START = 0
    SLICE1_END = SLICE1_START + 3600
    SLICE2_START = SLICE1_END
    SLICE2_END = SLICE2_START + 3600

    def test_series_range_no_log_returns_empty_list(self):
        """Selecting series with time range having no data in database (and
        not before or after start/end) no data points will be returned.
        """
        plugin = self.plugin()
        res = plugin._series('avg', start=self.t(0), end='7200', item='main.num')
        self.assertSeriesCount(0, res)
        self.assertSeries([], res)

    def test_series_now_no_log_now_returns_last_item_value_when_before_start(self):
        """When selecting series having not data in database, but the item
        last_change is before start date the series will contain 2 data points:
        start time with item value, end time with item value
        """
        plugin = self.plugin()
        item_change_ts = plugin._timestamp(self.sh.return_item('main.num').last_change())
        res = plugin._series('avg', start=self.t(0), end='now', item='main.num')
        self.assertSeriesCount(2, res)
        self.assertSeries(
            [
                (item_change_ts / TestDatabaseBase.TIME_FACTOR, 0.0),
                (res['series'][1][0] / TestDatabaseBase.TIME_FACTOR, 0.0),
            ],
            res,
        )

    def test_series_avg(self):
        """Test AVG selection with no aggregation and last value copied to end."""
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 10, 10), (11, 10, 20)])
        res = plugin._series('avg', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 10), (11, 20), (12, 20)], res)

    def test_series_avg_diff(self):
        """Test DIFF:AVG selection with no aggregation and last value copied to end."""
        plugin = self.plugin()
        self.create_log(
            plugin, 'main.num', [(1, 10, 10), (11, 10, 20), (21, 10, 30), (31, 10, 40), (41, 10, 50), (51, 10, 60)]
        )
        res = plugin._series('diff:avg', start=self.t(0), end=self.t(52), item='main.num')
        self.assertSeries([(11, 10.0), (21, 10.0), (31, 10.0), (41, 10.0), (51, 10.0)], res)

    def test_series_diff(self):
        """Test raw DIFF selection: change since the *chronologically* previous
        log entry, not the entry with the next-lower value.

        Values are deliberately non-monotonic (10, 20, 15, 25) so a LAG()
        window ordered by val_num instead of time would pair different rows
        and produce a different (wrong) result.
        """
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 10, 10), (11, 10, 20), (21, 10, 15), (31, 10, 25)])
        res = plugin._series('diff', start=self.t(0), end=self.t(32), item='main.num')
        self.assertSeries([(1, None), (11, 10.0), (21, -5.0), (31, 10.0), (32, 10.0)], res)

    def test_series_differentiate(self):
        """Test DIFFERENTIATE selection: rate of change per hour, computed
        against the chronologically previous log entry.

        Same non-monotonic values as test_series_diff - an ORDER BY val_num
        window would produce different pairings (and thus different rates).
        """
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 10, 10), (11, 10, 20), (21, 10, 15), (31, 10, 25)])
        res = plugin._series('differentiate', start=self.t(0), end=self.t(32), item='main.num')
        self.assertSeries([(1, None), (11, 3600.0), (21, -1800.0), (31, 3600.0)], res)

    def test_series_differentiate_aggregates_multiple_rows_per_bucket(self):
        """Regression: 'diff'/'differentiate' used to mix a window function
        with an aggregate GROUP BY in one SELECT - errors outright under
        MySQL 8/5.7's default ONLY_FULL_GROUP_BY, and returns an
        undefined arbitrary single row's value per bucket under MariaDB's
        default (permissive) mode, verified against a real MariaDB
        target. Forces 4 rows into a single bucket (count=1) so a
        non-aggregated result would only reflect one arbitrary row's
        diff/rate, not the mathematically correct sum-of-diffs-over-the-
        bucket's-time-span used here.
        """
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 2, 10), (2, 3, 13), (3, 4, 11), (4, 5, 20)])
        res = plugin._series('differentiate', start=self.t(0), end=self.t(1000), item='main.num', count=1)
        # total change across the bucket (10 -> 13 -> 11 -> 20, net +10)
        # over the summed 3s of gaps between the 4 samples -> 10 / (3s/3600s) = 12000.0/h
        self.assertSeries([(1, 12000.0)], res)

    def test_series_min(self):
        """Test MIN selection with no aggregation and last value copied to end."""
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 10, 10), (11, 10, 20)])
        res = plugin._series('min', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 10), (11, 20), (12, 20)], res)

    def test_series_max(self):
        """Test MAX selection with no aggregation and last value copied to end."""
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 10, 10), (11, 10, 20)])
        res = plugin._series('max', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 10), (11, 20), (12, 20)], res)

    def test_series_sum(self):
        """Test SUM selection with no aggregation and last value copied to end."""
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 10, 10), (11, 10, 20)])
        res = plugin._series('sum', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 10), (11, 20), (12, 20)], res)

    def test_series_count(self):
        """Test COUNT selection with no aggregation and last value copied to end."""
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 10, 10), (11, 10, 20)])
        res = plugin._series('count', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 1), (11, 1), (12, 1)], res)

    def test_series_count_eq_10(self):
        """Test COUNT selection with no aggregation and last value copied to end."""
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 10, 10), (11, 10, 20)])
        res = plugin._series('count=10', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 1), (11, 0), (12, 0)], res)

    def test_series_count_gt_10(self):
        """Test COUNT selection with no aggregation and last value copied to end."""
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 10, 10), (11, 10, 20)])
        res = plugin._series('count>10', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 0), (11, 1), (12, 1)], res)

    def test_series_count_lt_20(self):
        """Test COUNT selection with no aggregation and last value copied to end."""
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 10, 10), (11, 10, 20)])
        res = plugin._series('count<20', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 1), (11, 0), (12, 0)], res)

    def test_series_val(self):
        """Test VAL selection with no aggregation and last value copied to end."""
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(1, 10, 10), (11, 10, 20)])
        res = plugin._series('sum', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 10), (11, 20), (12, 20)], res)

    def test_series_avg_aggregation(self):
        """Test AVG selection with aggregation and last value copied to end."""
        values = self.log_slice(
            0,
            1,
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
        )
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', values)
        res = plugin._series('avg', start=self.t(10), end=self.t(50), item='main.num', count=5)
        self.assertSeries([(10, 75.0), (16, 25.0), (24, 80.0), (32, 45.0), (40, 45.0), (48, 96.67), (50, 96.67)], res)

    def test_series_min_aggregation(self):
        """Test MIN selection with aggregation and last value copied to end."""
        values = self.log_slice(
            0,
            1,
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
        )
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', values)
        res = plugin._series('min', start=self.t(10), end=self.t(50), item='main.num', count=5)
        self.assertSeries([(10, 50.0), (16, 10.0), (24, 50.0), (32, 10.0), (40, 10.0), (48, 90.0), (50, 90.0)], res)

    def test_series_max_aggregation(self):
        """Test MIN selection with aggregation and last value copied to end."""
        values = self.log_slice(
            0,
            1,
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
        )
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', values)
        res = plugin._series('max', start=self.t(10), end=self.t(50), item='main.num', count=5)
        self.assertSeries([(10, 100.0), (16, 40.0), (24, 100.0), (32, 80.0), (40, 80.0), (48, 100.0), (50, 100.0)], res)

    def test_series_sum_aggregation(self):
        """Test SUM selection with aggregation and last value copied to end."""
        values = self.log_slice(
            0,
            1,
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
        )
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', values)
        res = plugin._series('sum', start=self.t(10), end=self.t(50), item='main.num', count=5)
        self.assertSeries(
            [(10, 550.0), (16, 200.0), (24, 640.0), (32, 360.0), (40, 360.0), (48, 290.0), (50, 290.0)], res
        )

    def test_series_raw_aggregation(self):
        """Test RAW selection with aggregation and last value copied to end."""
        values = self.log_slice(
            0, 1, self.log_slice_values_delta(10, 100, 10), self.log_slice_values_delta(100, 10, -10)
        )
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', values)
        res = plugin._series('raw', start=self.t(10), end=self.t(50), item='main.num', count=5)
        self.assertSeries(
            [
                (10, 100.0),
                (10, 100.0),
                (11, 90.0),
                (12, 80.0),
                (13, 70.0),
                (14, 60.0),
                (15, 50.0),
                (16, 40.0),
                (17, 30.0),
                (18, 20.0),
                (19, 10.0),
                (50, 10.0),
            ],
            res,
        )

    @pytest.mark.skip(reason='series does not return last value currently')
    def test_series_returns_last_value_outside_range(self):
        """Return last value instead of given"""
        values = self.log_slice(
            0,
            1,
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
            self.log_slice_values_delta(10, 100, 10),
            self.log_slice_values_delta(100, 10, -10),
        )
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', values)
        self.dump_log(plugin, 'main.num')
        res = plugin._series('avg', start=self.t(60), end=self.t(70), item='main.num', count=5)
        self.assertSeries([(60, 10.0), (70, 10.0)], res)

    def test_series_bucket_grouping_is_portable_floor_not_round(self):
        # GROUP BY ROUND(time / :step) buckets differently per backend:
        # sqlite's integer '/' floors, MariaDB's decimal '/' + ROUND()
        # rounds half-up, shifting every bucket edge by step/2 between
        # backends. (time - (time % :step)) partitions identically to
        # sqlite's historical floor behavior and is exact integer math on
        # both.
        from unittest import mock

        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(0, 1, 10), (1, 2, 20)])
        captured = {}
        orig_fetchall = plugin._fetchall

        def spy(query, params=None, cur=NO_CURSOR):
            captured['query'] = query
            return orig_fetchall(query, params, cur=cur)

        with mock.patch.object(plugin, '_fetchall', side_effect=spy):
            res = plugin._series('avg', start=self.t(0), end=self.t(2), item='main.num', count=2)

        self.assertNotIn('ROUND(time / :step)', captured['query'])
        self.assertIn('GROUP BY (time - (time % :step))', captured['query'])
        self.assertTrue(res['series'], 'series must still aggregate normally with the portable grouping')
