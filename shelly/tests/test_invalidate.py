"""
Items of a shelly device are marked invalid in the database log when the device drops off the broker.
"""

from tests import common

from .base import ShellyTestBase
from .test_trv import TRV_ANNOUNCE, TRV_ID


class InvalidateTestBase(ShellyTestBase):
    ITEMS_FILE = common.BASE + '/plugins/shelly/tests/test_items_invalidate.yaml'

    def discovered_plugin(self):
        plugin = self.plugin()
        plugin.on_mqtt_announce(f'shellies/{TRV_ID}/announce', TRV_ANNOUNCE)
        return plugin

    @staticmethod
    def go_offline(plugin, retain: bool = False) -> None:
        plugin.on_mqtt_online(f'shellies/{TRV_ID}/online', False, 0, retain)


class TestInvalidateOnDisconnect(InvalidateTestBase):
    PARAMETERS = {'invalidate_on_disconnect': True}

    def test_online_false_marks_state_item_invalid(self):
        plugin = self.discovered_plugin()

        self.go_offline(plugin)

        self.assertEqual([(plugin.get_fullname(), 'lwt_offline')], self.gaps['trv.temp'].calls)

    def test_online_item_is_not_marked(self):
        plugin = self.discovered_plugin()

        self.go_offline(plugin)

        self.assertEqual([], self.gaps['trv.online'].calls)

    def test_retained_offline_marks_nothing(self):
        plugin = self.discovered_plugin()

        self.go_offline(plugin, retain=True)

        self.assertEqual([], self.gaps['trv.temp'].calls)

    def test_offline_of_device_not_yet_discovered_marks_nothing(self):
        plugin = self.plugin()

        self.go_offline(plugin)

        self.assertEqual([], self.gaps['trv.temp'].calls)

    def test_repeated_offline_opens_only_one_gap(self):
        plugin = self.discovered_plugin()

        self.go_offline(plugin)
        self.go_offline(plugin)

        self.assertEqual(1, len(self.gaps['trv.temp'].calls))

    def test_item_attribute_false_excludes_item(self):
        plugin = self.discovered_plugin()

        self.go_offline(plugin)

        self.assertEqual([], self.gaps['trv.battery'].calls)


class TestOptionOff(InvalidateTestBase):
    def test_online_false_marks_nothing(self):
        plugin = self.discovered_plugin()

        self.go_offline(plugin)

        self.assertEqual([], self.gaps['trv.temp'].calls)

    def test_item_attribute_true_includes_item_although_plugin_default_is_off(self):
        plugin = self.discovered_plugin()

        self.go_offline(plugin)

        self.assertEqual(1, len(self.gaps['trv.target_t'].calls))
