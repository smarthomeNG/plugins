#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Serial settings the viessmann protocol gives its transport."""

import unittest

from lib.model.sdp.carriers import ConnectionHooks, DeviceConfig
from lib.model.sdp.connection import SDPConnectionSerial
from lib.model.sdp.globals import CONN_SER_DIR
from plugins.viessmann.protocol import SDPProtocolViessmann


def transport_config(**params) -> DeviceConfig:
    proto = SDPProtocolViessmann(
        DeviceConfig.from_params({'serialport': '/dev/null', 'conn_type': CONN_SER_DIR, **params}), ConnectionHooks()
    )
    return proto._connection._config


class TestProtocolSetup(unittest.TestCase):
    def test_p300_serial_settings(self):
        config = transport_config()

        self.assertEqual(
            (4800, 8, 'E', 2, 0.5), (config.baudrate, config.bytesize, config.parity, config.stopbits, config.timeout)
        )

    def test_kw_serial_settings(self):
        config = transport_config(viess_proto='KW')

        self.assertEqual(
            (4800, 8, 'E', 2, 1), (config.baudrate, config.bytesize, config.parity, config.stopbits, config.timeout)
        )

    def test_unknown_protocol_uses_p300(self):
        self.assertEqual(0.5, transport_config(viess_proto='XY').timeout)

    def test_connection_defaults(self):
        config = transport_config()

        self.assertEqual(
            (True, True, 0, 3), (config.autoconnect, config.binary, config.connect_retries, config.connect_cycle)
        )

    def test_plugin_settings_win(self):
        self.assertEqual(9600, transport_config(baudrate=9600).baudrate)

    def test_transport_is_serial(self):
        proto = SDPProtocolViessmann(DeviceConfig.from_params({'serialport': '/dev/null'}), ConnectionHooks())

        self.assertIsInstance(proto._connection, SDPConnectionSerial)

    def test_protocol_reads_through_transport(self):
        proto = SDPProtocolViessmann(DeviceConfig.from_params({'serialport': '/dev/null'}), ConnectionHooks())

        self.assertEqual(proto._connection._read_bytes, proto._read_bytes)

    def test_p300_init_retries(self):
        proto = SDPProtocolViessmann(
            DeviceConfig.from_params({'serialport': '/dev/null', 'p300_init_retries': 4.0}), ConnectionHooks()
        )

        self.assertEqual(4, proto._p300_init_retries)


if __name__ == '__main__':
    unittest.main(verbosity=2)
