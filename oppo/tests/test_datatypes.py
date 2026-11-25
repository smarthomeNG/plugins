#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for plugins/oppo/datatypes.py DT_* classes.

DT_onoff.get_send_data returned 'OF' instead of 'OFF' for a falsy value.
commands.py's control.power reply_pattern includes '@POFF OK (OFF)',
proving the real device protocol expects 'OFF' - writing False built the
command '#POF' (missing the second F), which the device does not
recognize, so turning the player off silently failed.
"""

import unittest

from plugins.oppo.datatypes import DT_onoff


class TestDTOnoff(unittest.TestCase):
    def test_send_true_returns_on(self):
        self.assertEqual(DT_onoff().get_send_data(True), 'ON')

    def test_send_false_returns_off(self):
        self.assertEqual(DT_onoff().get_send_data(False), 'OFF')


if __name__ == '__main__':
    unittest.main(verbosity=2)
