#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Verbose mode activation on connect."""

import os
import tempfile
import unittest

from tests.sdp_harness import load_sdp_plugin
from tests.sdp_harness.characterize import items_yaml_from_struct

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WITHOUT_VERBOSE = """
dev:
    hdmiresolution:
        type: str
        oppo_command: general.hdmiresolution
        oppo_read: true
"""


class TestOnConnect(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rig = None

    def tearDown(self):
        if self.rig:
            self.rig.plugin.stop()
        self._tmp.cleanup()

    def connect(self, items):
        self.rig = load_sdp_plugin(self._tmp.name, 'plugins.oppo', 'oppo', items, params={'host': 'sim'})
        self.rig.plugin.run()
        return self.rig

    def test_bound_verbose_item_activates_verbose_mode(self):
        rig = self.connect(items_yaml_from_struct(PLUGIN_DIR, 'UDP-203'))

        self.assertIn('#SVM 2\r', rig.connection.payloads)

    def test_without_verbose_item_connects_without_verbose_mode(self):
        rig = self.connect(WITHOUT_VERBOSE)

        self.assertNotIn('#SVM', ''.join(rig.connection.payloads))
        self.assertIsNotNone(rig.job('read_initial_values'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
