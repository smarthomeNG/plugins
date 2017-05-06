import common
import unittest

from plugins.database import Database
from tests.mock.core import MockSmartHome

class TestDatabaseBase(unittest.TestCase):

    def plugin(self):
        self.sh = MockSmartHome()
        self.sh.with_dbapi('sqlite', 'sqlite3')
        self.sh.with_items_from(common.BASE + '/plugins/database/tests/test_items.conf')
        plugin = Database(self.sh, 'sqlite', {'database' : ':memory:'})
        for item in self.sh.return_items():
            plugin.parse_item(item)
        return plugin

    def create_item(self, plugin, name):
        return plugin.id(self.sh.return_item(name), True)

    def create_log(self, plugin, name, tuples):
        id = self.create_item(plugin, name)
        for t in tuples:
            plugin.insertLog(id, time=t[0], duration=t[1]-t[0], val=t[2], it='num')

    def assertSingle(self, expected, actual):
        self.assertEquals(expected, actual)

