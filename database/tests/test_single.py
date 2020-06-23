
from plugins.database import Database
from plugins.database.tests.base import TestDatabaseBase

class TestDatabaseSingle(TestDatabaseBase):

    def test_single_no_log_returns_none(self):
        plugin = self.plugin()
        res = plugin._single('avg', start=0, item='main.num')
        self.assertIsNone(res)

    def test_single_avg(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          (1, 2, 10),
          (2, 3, 20)
        ])
        self.dump_log(plugin, 'main.num')
        res = plugin._single('avg', start=self.t(0), end='now', item='main.num')
        self.assertSingle(15, res)

    def test_single_min(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          (1, 2, 10),
          (2, 3, 20)
        ])
        res = plugin._single('min', start=self.t(0), end='now', item='main.num')
        self.assertSingle(10, res)

    def test_single_max(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          (1, 2, 10),
          (2, 3, 20)
        ])
        res = plugin._single('max', start=self.t(0), end='now', item='main.num')
        self.assertSingle(20, res)

    def test_single_sum(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          (1, 2, 10),
          (2, 3, 20)
        ])
        res = plugin._single('sum', start=self.t(0), end='now', item='main.num')
        self.assertSingle(30, res)

    def test_single_count(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          (1, 2, 10),
          (2, 3, 20)
        ])
        res = plugin._single('count', start=self.t(0), end='now', item='main.num')
        self.assertSingle(2, res)

    def test_single_count_eq_10(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          (1, 2, 10),
          (2, 3, 20)
        ])
        res = plugin._single('count=10', start=self.t(0), end='now', item='main.num')
        self.assertSingle(1, res)

    def test_single_count_gt_10(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          (1, 2, 10),
          (2, 3, 20)
        ])
        res = plugin._single('count>10', start=self.t(0), end='now', item='main.num')
        self.assertSingle(1, res)

    def test_single_count_lt_20(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          (1, 2, 10),
          (2, 3, 20)
        ])
        res = plugin._single('count<20', start=self.t(0), end='now', item='main.num')
        self.assertSingle(1, res)

    def test_single_raw(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          (1, 2, 10),
          (2, 3, 20)
        ])
        res = plugin._single('raw', start=self.t(0), end='now', item='main.num')
        self.assertSingle(20, res)

    def test_single_on(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [
          (1, 2, 10),
          (2, 3, 20)
        ])
        res = plugin._single('on', start=0, end='now', item='main.num')
        self.assertSingle(1, res)

    def test_single_returns_last_value_outside_range(self):
        """ When selecting single value and the database contains one last
            value return it
        """
        plugin = self.plugin()
        self.create_log(plugin, 'main.num',[
          (1, 2, 10),
          (2, 3, 20),
          (3, None, 30)
        ])
        self.dump_log(plugin, 'main.num')
        res = plugin._single('avg', start=self.t(2), end=self.t(4), item='main.num')
        self.assertSingle(25, res)

