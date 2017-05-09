
from plugins.database import Database
from plugins.database.tests.base import TestDatabaseBase

class TestDatabaseSeries(TestDatabaseBase):

    SLICE1_START = 0
    SLICE1_END   = SLICE1_START + 3600
    SLICE2_START = SLICE1_END
    SLICE2_END   = SLICE2_START + 3600

    def test_series_range_no_log_returns_empty_list(self):
        """ Selecting series with time range having no data in database (and
            not before or after start/end) no data points will be returned.
        """
        plugin = self.plugin()
        res = plugin._series('avg', start=self.t(0), end='7200', item='main.num')
        self.assertSeriesCount(0, res)
        self.assertSeries([], res)

    def test_series_now_no_log_now_returns_last_item_value_when_before_start(self):
        """ When selecting series having not data in database, but the item
            last_change is before start date the series will contain 2 data points:
            start time with item value, end time with item value
        """
        plugin = self.plugin()
        item_change_ts = plugin._timestamp(self.sh.return_item('main.num').last_change())
        res = plugin._series('avg', start=self.t(0), end='now', item='main.num')
        self.assertSeriesCount(2, res)
        self.assertSeries([(item_change_ts/TestDatabaseBase.TIME_FACTOR, 0.0), (res['series'][1][0]/TestDatabaseBase.TIME_FACTOR,0.0)], res)


    def test_series_avg(self):
        """ Test AVG selection with no aggregation and last value copied to end.
        """
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          ( 1, 10, 10),
          (11, 10, 20)
        ])
        res = plugin._series('avg', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 10), (11, 20), (12, 20)], res)

    def test_series_min(self):
        """ Test MIN selection with no aggregation and last value copied to end.
        """
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          ( 1, 10, 10),
          (11, 10, 20)
        ])
        res = plugin._series('min', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 10), (11, 20), (12, 20)], res)

    def test_series_max(self):
        """ Test MAX selection with no aggregation and last value copied to end.
        """
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          ( 1, 10, 10),
          (11, 10, 20)
        ])
        res = plugin._series('max', start=self.t(0), end=self.t(12), item='main.num')
        self.assertSeries([(1, 10), (11, 20), (12, 20)], res)

    def test_series_avg_aggregation(self):
        """ Test AVG selection with aggregation and last value copied to end.
        """
        values = self.log_slice(0, 1,
            self.log_slice_values_delta( 10, 100,  10),
            self.log_slice_values_delta(100,  10, -10),
            self.log_slice_values_delta( 10, 100,  10),
            self.log_slice_values_delta(100,  10, -10),
            self.log_slice_values_delta( 10, 100,  10),
            self.log_slice_values_delta(100,  10, -10),
        )
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', values)
        res = plugin._series('avg', start=self.t(10), end=self.t(50), item='main.num', count=5)
        self.assertSeries([(10, 75.0), (16, 25.0), (24, 80.0), (32, 45.0), (40, 45.0), (48, 96.67), (50, 96.67)], res)

    def test_series_min_aggregation(self):
        """ Test MIN selection with aggregation and last value copied to end.
        """
        values = self.log_slice(0, 1,
            self.log_slice_values_delta( 10, 100,  10),
            self.log_slice_values_delta(100,  10, -10),
            self.log_slice_values_delta( 10, 100,  10),
            self.log_slice_values_delta(100,  10, -10),
            self.log_slice_values_delta( 10, 100,  10),
            self.log_slice_values_delta(100,  10, -10),
        )
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', values)
        res = plugin._series('min', start=self.t(10), end=self.t(50), item='main.num', count=5)
        self.assertSeries([(10, 50.0), (16, 10.0), (24, 50.0), (32, 10.0), (40, 10.0), (48, 90.0), (50, 90.0)], res)

    def test_series_max_aggregation(self):
        """ Test MIN selection with aggregation and last value copied to end.
        """
        values = self.log_slice(0, 1,
            self.log_slice_values_delta( 10, 100,  10),
            self.log_slice_values_delta(100,  10, -10),
            self.log_slice_values_delta( 10, 100,  10),
            self.log_slice_values_delta(100,  10, -10),
            self.log_slice_values_delta( 10, 100,  10),
            self.log_slice_values_delta(100,  10, -10),
        )
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', values)
        res = plugin._series('max', start=self.t(10), end=self.t(50), item='main.num', count=5)
        self.assertSeries([(10, 100.0), (16, 40.0), (24, 100.0), (32, 80.0), (40, 80.0), (48, 100.0), (50, 100.0)], res)

