#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests that _process_additional_data() dispatches the power-on readback for
zone 4, not just zones 1-3. update_item() explicitly loops
`for zone in range(1, 5)` (zones 1-4), so the plugin models 4 zones, but the
zone-power if/elif chain in _process_additional_data() only covered
'zone1'/'zone2'/'zone3.control.power' - a zone4 power-on event never
triggered the mute/sleep/standby/settings readback zones 1-3 get.
"""

import unittest
from unittest.mock import MagicMock, patch

from lib.model.sdp.globals import PLUGIN_ATTR_MODEL
from plugins.denon import denon


def _make_plugin():
    plugin = object.__new__(denon)
    plugin.logger = MagicMock()
    plugin._parameters = {PLUGIN_ATTR_MODEL: ''}
    plugin.send_command = MagicMock()
    plugin.read_all_commands = MagicMock()
    return plugin


class TestZone4PowerDispatch(unittest.TestCase):
    def test_zone4_power_on_triggers_readback(self):
        plugin = _make_plugin()
        with patch('plugins.denon.time.sleep'):
            plugin._process_additional_data('zone4.control.power', None, True, 0)

        plugin.send_command.assert_any_call('zone4.control.mute')
        plugin.send_command.assert_any_call('zone4.control.sleep')
        plugin.send_command.assert_any_call('zone4.control.standby')
        plugin.read_all_commands.assert_called_once_with('ALL.zone4.settings')


if __name__ == '__main__':
    unittest.main(verbosity=2)
