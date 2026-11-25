"""
Items of all devices are marked invalid in the database log when the zigbee2mqtt bridge goes offline.
"""

from .base import Zigbee2MqttTestBase

STATE_TOPIC = 'zigbee2mqtt/bridge/state'


class TestInvalidateOnDisconnect(Zigbee2MqttTestBase):
    PARAMETERS = {'invalidate_on_disconnect': True}

    def test_bridge_offline_marks_device_items_invalid(self):
        plugin = self.plugin()
        plugin.on_mqtt_msg(STATE_TOPIC, 'online', 0, True)

        plugin.on_mqtt_msg(STATE_TOPIC, 'offline', 0, False)

        self.assertEqual([(plugin.get_fullname(), 'bridge_offline')], self.gaps['dev1.temp'].calls)

    def test_items_of_every_device_are_marked(self):
        plugin = self.plugin()
        plugin.on_mqtt_msg(STATE_TOPIC, 'online', 0, True)

        plugin.on_mqtt_msg(STATE_TOPIC, 'offline', 0, False)

        self.assertEqual(1, len(self.gaps['dev2.temp'].calls))

    def test_write_only_and_bridge_items_are_not_marked(self):
        plugin = self.plugin()
        plugin.on_mqtt_msg(STATE_TOPIC, 'online', 0, True)

        plugin.on_mqtt_msg(STATE_TOPIC, 'offline', 0, False)

        self.assertEqual([], self.gaps['dev1.setpoint'].calls)
        self.assertEqual([], self.gaps['bridge.online'].calls)

    def test_retained_offline_marks_nothing(self):
        plugin = self.plugin()
        plugin.on_mqtt_msg(STATE_TOPIC, 'online', 0, True)

        plugin.on_mqtt_msg(STATE_TOPIC, 'offline', 0, True)

        self.assertEqual([], self.gaps['dev1.temp'].calls)

    def test_offline_of_bridge_never_seen_online_marks_nothing(self):
        plugin = self.plugin()

        plugin.on_mqtt_msg(STATE_TOPIC, 'offline', 0, False)

        self.assertEqual([], self.gaps['dev1.temp'].calls)

    def test_json_state_payload_is_understood(self):
        plugin = self.plugin()
        plugin.on_mqtt_msg(STATE_TOPIC, '{"state": "online"}', 0, True)

        plugin.on_mqtt_msg(STATE_TOPIC, '{"state": "offline"}', 0, False)

        self.assertEqual(1, len(self.gaps['dev1.temp'].calls))

    def test_repeated_offline_opens_only_one_gap(self):
        plugin = self.plugin()
        plugin.on_mqtt_msg(STATE_TOPIC, 'online', 0, True)

        plugin.on_mqtt_msg(STATE_TOPIC, 'offline', 0, False)
        plugin.on_mqtt_msg(STATE_TOPIC, 'offline', 0, False)

        self.assertEqual(1, len(self.gaps['dev1.temp'].calls))


class TestOptionOff(Zigbee2MqttTestBase):
    def test_bridge_offline_marks_nothing(self):
        plugin = self.plugin()
        plugin.on_mqtt_msg(STATE_TOPIC, 'online', 0, True)

        plugin.on_mqtt_msg(STATE_TOPIC, 'offline', 0, False)

        self.assertEqual([], self.gaps['dev1.temp'].calls)
