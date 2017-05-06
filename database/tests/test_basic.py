
from plugins.database import Database
from plugins.database.tests.base import TestDatabaseBase

class TestDatabaseBasic(TestDatabaseBase):

    def test_id_not_creating_items(self):
        plugin = self.plugin()
        self.assertIsNone(plugin.id(self.sh.return_item('main.num'), False))
        self.assertIsNone(plugin.id(self.sh.return_item('main.str'), False))
        self.assertIsNone(plugin.id(self.sh.return_item('main.bool'), False))

    def test_id_creating_items(self):
        plugin = self.plugin()
        self.assertEqual(1, plugin.id(self.sh.return_item('main.num'), True))
        self.assertEqual(2, plugin.id(self.sh.return_item('main.str'), True))
        self.assertEqual(3, plugin.id(self.sh.return_item('main.bool'), True))

    def test_insertItem_creating_item(self):
        plugin = self.plugin()
        self.assertEqual(1, plugin.insertItem('manually.inserted'))

    def test_readItem_reads_unknown_as_none(self):
        plugin = self.plugin()
        res = plugin.readItem(1)
        self.assertIsNone(res)

    def test_readItem_returns_existing_item(self):
        plugin = self.plugin()
        res = plugin.readItem(plugin.insertItem('manually.inserted'))
        self.assertEqual(1, res[0])
        self.assertEqual('manually.inserted', res[1])

    def test_updateItem(self):
        plugin = self.plugin()
        id = plugin.insertItem('manually.inserted')
        plugin.updateItem(id, time=0, val='test', it='str')
        res = plugin.readItem(id)
        self.assertEqual(id, res[0])
        self.assertEqual(0, res[2])
        self.assertEqual('test', res[3])

    def test_deleteItem(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        plugin.deleteItem(plugin.id(item, True))
        self.assertIsNone(plugin.id(item, False))

    def test_readItems(self):
        plugin = self.plugin()
        self.create_item(plugin, 'main.num')
        self.create_item(plugin, 'main.str')
        self.create_item(plugin, 'main.bool')
        res = plugin.readItems()
        self.assertEqual(3, len(res))
        self.assertEqual('main.num', res[0][1])
        self.assertEqual('main.str', res[1][1])
        self.assertEqual('main.bool', res[2][1])

    def test_readLog_empty_result(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        res = plugin.readLog(id, time=0)
        self.assertEqual(0, len(res))

    def test_insertLog_num(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        res = plugin.readLog(id, time=0)
        self.assertEqual(1, len(res))
        self.assertEqual(0, res[0][0])
        self.assertEqual(3600, res[0][2])
        self.assertEqual(None, res[0][3])
        self.assertEqual(10, res[0][4])
        self.assertEqual(1, res[0][5])

    def test_updateLog(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        plugin.updateLog(id, time=0, duration=7200, val=20, it='num')
        res = plugin.readLog(id, time=0)
        self.assertEqual(1, len(res))
        self.assertEqual(0, res[0][0])
        self.assertEqual(7200, res[0][2])
        self.assertEqual(None, res[0][3])
        self.assertEqual(20, res[0][4])
        self.assertEqual(1, res[0][5])

    def test_deleteLog(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        plugin.deleteLog(id, time=0)
        res = plugin.readLog(id, time=0)
        self.assertEqual(0, len(res))

    def test_readLogs(self):
        plugin = self.plugin()
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=   0, duration=3600, val=10, it='num')
        plugin.insertLog(id, time=3600, duration=7200, val=20, it='num')
        plugin.insertLog(id, time=7200, duration=3600, val=15, it='num')
        res = plugin.readLogs(id)
        self.assertEqual(3, len(res))
        self.assertEqual(0, res[0][0])
        self.assertEqual(3600, res[0][2])
        self.assertEqual(None, res[0][3])
        self.assertEqual(10, res[0][4])
        self.assertEqual(1, res[0][5])
        self.assertEqual(3600, res[1][0])
        self.assertEqual(7200, res[1][2])
        self.assertEqual(None, res[1][3])
        self.assertEqual(20, res[1][4])
        self.assertEqual(1, res[1][5])
        self.assertEqual(7200, res[2][0])
        self.assertEqual(3600, res[2][2])
        self.assertEqual(None, res[2][3])
        self.assertEqual(15, res[2][4])
        self.assertEqual(1, res[2][5])

