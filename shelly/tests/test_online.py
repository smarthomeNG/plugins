"""
The online topic of a device sets the item with shelly_attr online.
"""

from tests import common

from .base import ShellyTestBase
from .test_trv import TRV_ANNOUNCE, TRV_ID


class TestOnlineItem(ShellyTestBase):
    ITEMS_FILE = common.BASE + '/plugins/shelly/tests/test_items_invalidate.yaml'

    def setUp(self):
        self.plugin = self.plugin()
        self.plugin.on_mqtt_announce(f'shellies/{TRV_ID}/announce', TRV_ANNOUNCE)

    def publish_online(self, online: bool) -> None:
        self.plugin.on_mqtt_online(f'shellies/{TRV_ID}/online', online, 0, False)

    def test_online_false_sets_online_item_false(self):
        self.publish_online(False)

        self.assertFalse(self.sh.return_item('trv.online')())

    def test_online_true_sets_online_item_true(self):
        self.publish_online(False)

        self.publish_online(True)

        self.assertTrue(self.sh.return_item('trv.online')())


class TestOnlineBeforeAnnounce(ShellyTestBase):
    ITEMS_FILE = common.BASE + '/plugins/shelly/tests/test_items_invalidate.yaml'

    def test_announce_sets_online_item_to_state_received_before_it(self):
        plugin = self.plugin()
        plugin.on_mqtt_online(f'shellies/{TRV_ID}/online', False, 0, False)

        plugin.on_mqtt_announce(f'shellies/{TRV_ID}/announce', TRV_ANNOUNCE)

        self.assertFalse(self.sh.return_item('trv.online')())
