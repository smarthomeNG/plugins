
from plugins.database import Database
from plugins.database.tests.base import TestDatabaseBase

class TestDatabaseSingle(TestDatabaseBase):

    def test_single_no_log_returns_none(self):
        plugin = self.plugin()
        res = plugin._single('avg', start=0, item='main.num')
        self.assertIsNone(res)

    def test_single_avg(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num',[
          ( 3600,  7200, 10),
          ( 7200, 10800, 20)
        ])
        res = plugin._single('avg', start=0, end='now', item='main.num')
        self.assertSingle(15, res)

    def test_single_min(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num',[
          ( 3600,  7200, 10),
          ( 7200, 10800, 20)
        ])
        res = plugin._single('min', start=0, end='now', item='main.num')
        self.assertSingle(10, res)

    def test_single_max(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num',[
          ( 3600,  7200, 10),
          ( 7200, 10800, 20)
        ])
        res = plugin._single('max', start=0, end='now', item='main.num')
        self.assertSingle(20, res)

    def test_single_on(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num',[
          ( 3600,  7200, 10),
          ( 7200, 10800, 20)
        ])
        res = plugin._single('on', start=0, end='now', item='main.num')
        self.assertSingle(1, res)
