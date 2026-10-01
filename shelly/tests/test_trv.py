"""
Shelly TRV (SHTRV-01, Gen1): read-only attributes, fed with payloads as published by the device.
"""

import unittest

from .base import ShellyTestBase

TRV_ID = 'shellytrv-ABC123'

TRV_ANNOUNCE = {
    'id': TRV_ID,
    'model': 'SHTRV-01',
    'mac': 'AABBCCABC123',
    'ip': '192.168.2.17',
    'new_fw': False,
    'fw_ver': '20240619-130912/v2.2.4@ee290818',
}

TRV_STATUS = {
    'tmp': {'value': 20.3, 'units': 'C', 'is_valid': True},
    'target_t': {'enabled': True, 'value': 20.0, 'units': 'C'},
    'temperature_offset': 0.0,
    'bat': 99,
}

TRV_INFO = {
    'wifi_sta': {'connected': True, 'ssid': 'SSID', 'ip': '192.168.2.17', 'rssi': -47},
    'cloud': {'enabled': True, 'connected': True},
    'mqtt': {'connected': True},
    'time': '07:59',
    'unixtime': 1730098774,
    'serial': 22,
    'has_update': False,
    'mac': 'AABBCCABC123',
    'cfg_changed_cnt': 5,
    'actions_stats': {'skipped': 0},
    'thermostats': [
        {
            'pos': 12.0,
            'target_t': {'enabled': True, 'value': 20.0, 'value_op': 8.0, 'units': 'C'},
            'tmp': {'value': 20.3, 'units': 'C', 'is_valid': True},
            'schedule': True,
            'schedule_profile': 3,
            'boost_minutes': 5,
            'window_open': True,
        }
    ],
    'calibrated': True,
    'bat': {'value': 99, 'voltage': 4.085},
    'charger': False,
    'update': {'status': 'unknown', 'has_update': False},
    'ram_total': 97280,
    'ram_free': 30584,
    'fs_size': 65536,
    'fs_free': 59324,
    'uptime': 55124,
    'fw_info': {'device': TRV_ID, 'fw': '20240619-130912/v2.2.4@ee290818'},
    'ps_mode': 0,
    'dbg_flags': 0,
}


class TestTrvStatus(ShellyTestBase):
    def setUp(self):
        self.plugin = self.plugin_instance = self.plugin()
        self.plugin.on_mqtt_announce(f'shellies/{TRV_ID}/announce', TRV_ANNOUNCE)

    def test_status_sets_measured_temperature(self):
        self.plugin.on_mqtt_gen1_message(f'shellies/{TRV_ID}/status', TRV_STATUS)

        self.assertEqual(self.sh.return_item('trv.temp')(), 20.3)

    def test_status_sets_target_temperature(self):
        self.plugin.on_mqtt_gen1_message(f'shellies/{TRV_ID}/status', TRV_STATUS)

        self.assertEqual(self.sh.return_item('trv.target_t')(), 20.0)

    def test_status_sets_temperature_offset(self):
        self.plugin.on_mqtt_gen1_message(f'shellies/{TRV_ID}/status', {**TRV_STATUS, 'temperature_offset': -1.5})

        self.assertEqual(self.sh.return_item('trv.temperature_offset')(), -1.5)

    def test_status_sets_battery_percent(self):
        self.plugin.on_mqtt_gen1_message(f'shellies/{TRV_ID}/status', TRV_STATUS)

        self.assertEqual(self.sh.return_item('trv.battery')(), 99)


class TestTrvInfo(ShellyTestBase):
    def setUp(self):
        self.plugin = self.plugin()
        self.plugin.on_mqtt_announce(f'shellies/{TRV_ID}/announce', TRV_ANNOUNCE)

    def publish_info(self, info: dict = TRV_INFO):
        self.plugin.on_mqtt_gen1_message(f'shellies/{TRV_ID}/info', info)

    def test_info_sets_thermostat_attributes(self):
        self.publish_info()

        expected = {
            'temp': 20.3,
            'target_t': 20.0,
            'valve_pos': 12.0,
            'window_open': True,
            'boost_minutes': 5,
            'schedule': True,
            'schedule_profile': 3,
        }
        actual = {name: self.sh.return_item(f'trv.{name}')() for name in expected}
        self.assertEqual(actual, expected)

    def test_info_sets_battery_percent(self):
        self.publish_info()

        self.assertEqual(self.sh.return_item('trv.battery')(), 99)


class TestTrvPayloadsAreRecognized(ShellyTestBase):
    def setUp(self):
        self.plugin = self.plugin()
        self.plugin.on_mqtt_announce(f'shellies/{TRV_ID}/announce', TRV_ANNOUNCE)

    def test_status_and_info_log_nothing_as_unhandled(self):
        with self.assertNoLogs('plugins.shelly', level='INFO'):
            self.plugin.on_mqtt_gen1_message(f'shellies/{TRV_ID}/status', TRV_STATUS)
            self.plugin.on_mqtt_gen1_message(f'shellies/{TRV_ID}/info', TRV_INFO)


class TestUnhandledStatusLoggedPerInstance(ShellyTestBase):
    def test_second_plugin_instance_logs_unhandled_status_again(self):
        unknown_status = {'unknown_key': 1, 'target_t': {'value': 20.0}}
        for _ in range(2):
            plugin = self.plugin()
            plugin.on_mqtt_announce(f'shellies/{TRV_ID}/announce', TRV_ANNOUNCE)

            with self.assertLogs('plugins.shelly', level='INFO'):
                plugin.on_mqtt_gen1_message(f'shellies/{TRV_ID}/info', unknown_status)


if __name__ == '__main__':
    unittest.main(verbosity=2)
