
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
        res = plugin._series('avg', start='0', end='7200', item='main.num')
        self.assertSeriesCount(0, res)
        self.assertSeries([], res)

    def test_series_now_no_log_now_returns_last_item_value_when_before_start(self):
        """ When selecting series having not data in database, but the item
            last_change is before start date the series will contain 2 data points:
            start time with item value, end time with item value
        """
        plugin = self.plugin()
        item_change_ts = plugin._timestamp(self.sh.return_item('main.num').last_change())
        res = plugin._series('avg', start='0', end='now', item='main.num')
        self.assertSeriesCount(2, res)
        self.assertSeries([(item_change_ts, 0.0), (res['series'][1][0],0.0)], res)


    def test_series_avg(self):
        """ When the aggregation is too low the items are returned as is. The
            last value is copied to the end date and will be returned as additional
            item.
        """
        plugin = self.plugin()
        self.create_log(plugin, 'main.num',[
          ( 3600,  7200, 10),
          ( 7200, 10800, 20)
        ])
        res = plugin._series('avg', start='0', end='7201', item='main.num')
        self.assertSeries([(3600, 10), (7200, 20), (7201, 20)], res)

    def test_series_min(self):
        """ When the aggregation is too low the items are returned as is. The
            last value is copied to the end date and will be returned as additional
            item.
        """
        plugin = self.plugin()
        self.create_log(plugin, 'main.num',[
          ( 3600,  7200, 10),
          ( 7200, 10800, 20)
        ])
        res = plugin._series('min', start='0', end='7201', item='main.num')
        self.assertSeries([(3600, 10), (7200, 20), (7201, 20)], res)

    def test_series_max(self):
        """ When the aggregation is too low the items are returned as is. The
            last value is copied to the end date and will be returned as additional
            item.
        """
        plugin = self.plugin()
        self.create_log(plugin, 'main.num',[
          ( 3600,  7200, 10),
          ( 7200, 10800, 20)
        ])
        res = plugin._series('max', start='0', end='7201', item='main.num')
        self.assertSeries([(3600, 10), (7200, 20), (7201, 20)], res)

