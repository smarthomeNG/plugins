#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Custom input names rename INPUT and VIDEOSELECT lookups and their list items."""

import os
import tempfile
import unittest

from tests.sdp_harness import load_sdp_plugin
from tests.sdp_harness.characterize import items_yaml_from_struct

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCustomInputnames(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        items = items_yaml_from_struct(PLUGIN_DIR, 'AVR-X6300H')
        self.rig = load_sdp_plugin(
            self._tmp.name, 'plugins.denon', 'denon', items, params={'model': 'AVR-X6300H', 'host': 'sim'}
        )
        self.rig.plugin.run()
        self.rig.item('dev.general.custom_inputnames')({'SAT/CBL': 'MyBox'}, 'test')

    def tearDown(self):
        self.rig.plugin.stop()
        self._tmp.cleanup()

    def test_input_lookup_renamed(self):
        self.assertEqual('MyBox', self.rig.plugin.get_lookup('INPUT')['SAT/CBL'])
        self.assertIn('MyBox', self.rig.item('dev.zone1.control.input.lookup')())

    def test_videoselect_lookup_renamed(self):
        self.assertEqual('MyBox', self.rig.plugin.get_lookup('VIDEOSELECT')['SAT/CBL'])
        self.assertIn('MyBox', self.rig.item('dev.zone1.settings.video.videoinput.lookup')())


if __name__ == '__main__':
    unittest.main(verbosity=2)
