"""Notifications triggered by item attributes."""

from .base import BarkTestBase

ITEMS = """
door:
    type: bool
    bark_values:
        - true: 'Tür zu'
        - false: 'Tür offen'

gate:
    # no type: a 'foo' item, fed with 1 and 0
    bark_values:
        - 1: 'Tor zu'
        - 0: 'Tor offen'

heating:
    type: str
    bark_text: 'Heizung: VAL'

pump:
    type: num
    bark_values:
        - 0: 'Pumpe aus'
    bark_text: 'Pumpe Stufe VAL'
    bark_title: 'Pumpe (VAL)'
    bark_url: 'http://visu.local/pump/VAL'

repeating:
    type: str
    enforce_updates: true
    bark_text: 'VAL'

plain:
    type: bool
"""


class TestItemNotifications(BarkTestBase):
    def setUp(self):
        super().setUp()
        self.plugin = self.load_plugin(items=ITEMS)

    def write(self, path, value):
        self.rig.item(path)(value)

    def bodies(self):
        return [payload['body'] for payload in self.payloads()]

    def test_bool_item_sends_text_of_its_value(self):
        self.write('door', True)
        self.write('door', False)

        self.assertEqual(self.bodies(), ['Tür zu', 'Tür offen'])

    def test_untyped_item_matches_numeric_values(self):
        self.write('gate', 1)
        self.write('gate', 0)

        self.assertEqual(self.bodies(), ['Tor zu', 'Tor offen'])

    def test_value_without_text_sends_nothing(self):
        self.write('gate', 2)

        self.assertEqual(self.payloads(), [])

    def test_text_gets_the_value_inserted(self):
        self.write('heating', 'Abtauen')

        self.assertEqual(self.bodies(), ['Heizung: Abtauen'])

    def test_values_take_precedence_over_text(self):
        self.write('pump', 2)
        self.write('pump', 0)

        self.assertEqual(self.bodies(), ['Pumpe Stufe 2', 'Pumpe aus'])

    def test_title_and_url_get_the_value_inserted(self):
        self.write('pump', 2)

        payload = self.payloads()[0]
        self.assertEqual(payload['title'], 'Pumpe (2)')
        self.assertEqual(payload['url'], 'http://visu.local/pump/2')

    def test_update_without_change_sends_nothing(self):
        self.write('door', True)
        self.write('door', True)

        self.assertEqual(self.bodies(), ['Tür zu'])

    def test_item_with_enforced_updates_sends_repeated_values(self):
        self.write('repeating', 'Fehler')
        self.write('repeating', 'Fehler')

        self.assertEqual(self.bodies(), ['Fehler', 'Fehler'])

    def test_item_without_attributes_sends_nothing(self):
        self.write('plain', True)

        self.assertEqual(self.payloads(), [])

    def test_stopped_plugin_sends_nothing(self):
        self.plugin.stop()

        self.write('door', True)

        self.assertEqual(self.payloads(), [])


class TestMalformedValues(BarkTestBase):
    def test_list_with_entry_lacking_a_value_is_rejected_leaving_the_text(self):
        # lib.metadata rejects the attribute as a whole if one entry is no "value: text" pair
        items = """
broken:
    type: bool
    bark_values:
        - 'Tür offen'
        - true: 'Tür zu'
    bark_text: 'Tür VAL'
"""
        self.load_plugin(items=items)

        self.rig.item('broken')(True)

        self.assertEqual([payload['body'] for payload in self.payloads()], ['Tür True'])
        self.assertTrue(any('bark_values' in message for message in self.rig.logs.messages()))
