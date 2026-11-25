from plugins.uzsu.tests.base import TestUZSUBase

ITEM_PATH = 'main.temp.uzsu'


class TestUpdateItem(TestUZSUBase):
    """``update_item`` evaluates the dict just written to the item."""

    def setUp(self):
        self.plugin = self.plugin()
        self.item = self.sh.items.return_item(ITEM_PATH)

    def write(self, entries):
        self.item({'active': True, 'list': entries}, 'Visu')
        self.plugin.update_item(self.item, 'Visu')

    def test_new_list_is_used(self):
        self.write([{'value': 1, 'active': True, 'rrule': 'FREQ=DAILY', 'time': '07:00'}])

        self.assertEqual([e['value'] for e in self.plugin._items[self.item]['list']], [1])

    def test_remove_duplicates_deactivates_entry_replaced_by_new_value(self):
        old = {'value': 1, 'active': True, 'rrule': 'FREQ=DAILY', 'time': '07:00'}
        self.write([dict(old)])

        self.write([dict(old), {**old, 'value': 2}])

        entries = self.plugin._items[self.item]['list']
        self.assertEqual([(e['value'], e['active']) for e in entries], [(1, False), (2, True)])

    def assert_new_entry_wins(self, **keys):
        old = {'value': 1, 'active': True, 'time': '07:00', **keys}
        self.write([dict(old)])

        self.write([{**old, 'value': 2}, dict(old)])

        entries = self.plugin._items[self.item]['list']
        self.assertEqual([(e['value'], e['active']) for e in entries], [(2, True), (1, False)])

    def test_remove_duplicates_keeps_new_entry_listed_first(self):
        self.assert_new_entry_wins(rrule='FREQ=DAILY', holidays={'mode': 'ignore', 'scope': 'all'})

    def test_remove_duplicates_keeps_new_entry_if_holidays_are_migrated(self):
        self.assert_new_entry_wins(rrule='FREQ=DAILY')

    def test_remove_duplicates_keeps_new_entry_if_rrule_is_filled(self):
        self.assert_new_entry_wins(rrule='', holidays={'mode': 'ignore', 'scope': 'all'})
