"""
Items of a tasmota device are marked invalid in the database log when the device drops off the broker.
"""

from datetime import timedelta

from .base import TasmotaTestBase


class TestInvalidateOnDisconnect(TasmotaTestBase):
    PARAMETERS = {'invalidate_on_disconnect': True}

    def test_lwt_offline_marks_state_item_invalid(self):
        plugin = self.plugin()
        plugin.on_mqtt_lwt_message('tele/dev1/LWT', True, 0, False)

        plugin.on_mqtt_lwt_message('tele/dev1/LWT', False, 0, False)

        self.assertEqual([(plugin.get_fullname(), 'lwt_offline')], self.gaps['dev1.power'].calls)

    def test_other_devices_are_untouched(self):
        plugin = self.plugin()
        plugin.on_mqtt_lwt_message('tele/dev1/LWT', True, 0, False)

        plugin.on_mqtt_lwt_message('tele/dev1/LWT', False, 0, False)

        self.assertEqual([], self.gaps['dev2.power'].calls)

    def test_online_item_and_event_items_are_not_marked(self):
        plugin = self.plugin()
        plugin.on_mqtt_lwt_message('tele/dev1/LWT', True, 0, False)

        plugin.on_mqtt_lwt_message('tele/dev1/LWT', False, 0, False)

        self.assertEqual([], self.gaps['dev1.online'].calls)
        self.assertEqual([], self.gaps['dev1.button'].calls)

    def test_retained_offline_marks_nothing(self):
        plugin = self.plugin()
        plugin.on_mqtt_lwt_message('tele/dev1/LWT', True, 0, False)

        plugin.on_mqtt_lwt_message('tele/dev1/LWT', False, 0, True)

        self.assertEqual([], self.gaps['dev1.power'].calls)

    def test_offline_of_device_never_seen_marks_nothing(self):
        plugin = self.plugin()

        plugin.on_mqtt_lwt_message('tele/dev1/LWT', False, 0, False)

        self.assertEqual([], self.gaps['dev1.power'].calls)

    def test_repeated_offline_opens_only_one_gap(self):
        plugin = self.plugin()
        plugin.on_mqtt_lwt_message('tele/dev1/LWT', True, 0, False)

        plugin.on_mqtt_lwt_message('tele/dev1/LWT', False, 0, False)
        plugin.on_mqtt_lwt_message('tele/dev1/LWT', False, 0, False)

        self.assertEqual(1, len(self.gaps['dev1.power'].calls))


class TestOptionOff(TasmotaTestBase):
    def test_lwt_offline_marks_nothing(self):
        plugin = self.plugin()
        plugin.on_mqtt_lwt_message('tele/dev1/LWT', True, 0, False)

        plugin.on_mqtt_lwt_message('tele/dev1/LWT', False, 0, False)

        self.assertEqual([], self.gaps['dev1.power'].calls)


class TestInvalidateOnTimeout(TasmotaTestBase):
    PARAMETERS = {'invalidate_on_timeout': True, 'invalidate_timeout_factor': 2.0}

    def silent_for(self, plugin, topic: str, seconds: int) -> None:
        """Make ``topic`` appear to have sent its last message ``seconds`` ago."""
        device = plugin.tasmota_devices[topic]
        device['last_seen'] = plugin.shtime.now().replace(tzinfo=None) - timedelta(seconds=seconds)

    def test_silence_beyond_factor_times_telemetry_period_marks_items_invalid(self):
        plugin = self.plugin()
        plugin.on_mqtt_lwt_message('tele/dev1/LWT', True, 0, False)
        self.silent_for(plugin, 'dev1', 601)

        plugin.check_online_status()

        self.assertEqual([(plugin.get_fullname(), 'timeout')], self.gaps['dev1.power'].calls)

    def test_silence_within_factor_times_telemetry_period_marks_nothing(self):
        plugin = self.plugin()
        plugin.on_mqtt_lwt_message('tele/dev1/LWT', True, 0, False)
        self.silent_for(plugin, 'dev1', 599)

        plugin.check_online_status()

        self.assertEqual([], self.gaps['dev1.power'].calls)

    def test_device_never_seen_marks_nothing(self):
        plugin = self.plugin()

        plugin.check_online_status()

        self.assertEqual([], self.gaps['dev1.power'].calls)

    def test_item_attribute_false_excludes_item_from_timeout_invalidation(self):
        plugin = self.plugin()
        plugin.on_mqtt_lwt_message('tele/dev3/LWT', True, 0, False)
        self.silent_for(plugin, 'dev3', 601)

        plugin.check_online_status()

        self.assertEqual([], self.gaps['dev3.power'].calls)

    def test_timeout_also_marks_device_that_already_went_offline_by_lwt(self):
        plugin = self.plugin()
        plugin.on_mqtt_lwt_message('tele/dev1/LWT', True, 0, False)
        plugin.on_mqtt_lwt_message('tele/dev1/LWT', False, 0, False)
        self.silent_for(plugin, 'dev1', 601)

        plugin.check_online_status()

        self.assertEqual([(plugin.get_fullname(), 'timeout')], self.gaps['dev1.power'].calls)


class TestItemAttributeEnablesTimeoutInvalidation(TasmotaTestBase):
    PARAMETERS = {'invalidate_on_timeout': False}

    def test_item_attribute_true_includes_item_although_plugin_default_is_off(self):
        plugin = self.plugin()
        plugin.on_mqtt_lwt_message('tele/dev4/LWT', True, 0, False)
        plugin.tasmota_devices['dev4']['last_seen'] = plugin.shtime.now().replace(tzinfo=None) - timedelta(seconds=601)

        plugin.check_online_status()

        self.assertEqual(1, len(self.gaps['dev4.power'].calls))
        self.assertEqual([], self.gaps['dev1.power'].calls)
