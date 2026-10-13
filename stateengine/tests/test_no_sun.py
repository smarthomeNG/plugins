#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Behaviour without sh.sun (core has no lat/lon configured or no ephemeris backend installed):
sun values stay None and sun_tracking() falls back to a default sun altitude.
"""

import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
import tests.common as common

common.register_shng_log_levels()

from plugins.stateengine.tests.mock_helper import make_sh, MockAbItem
from plugins.stateengine import StateEngineCurrent, StateEngineDefaults, StateEngineEval


class TestWithoutSun(unittest.TestCase):
    def setUp(self):
        StateEngineDefaults.logger = logging.getLogger('test.se')
        self.sh = make_sh()
        self.sh.sun = False
        StateEngineCurrent.init(self.sh)

    def test_current_sun_values_are_none(self):
        self.assertIsNone(StateEngineCurrent.values.get_sun_azimut())
        self.assertIsNone(StateEngineCurrent.values.get_sun_altitude())

    def test_update_does_not_raise(self):
        StateEngineCurrent.update()
        self.assertIsNone(StateEngineCurrent.values.get_sun_altitude())

    def test_sun_tracking_uses_fallback_altitude(self):
        se_eval = StateEngineEval.SeEval(MockAbItem(self.sh))
        expected = se_eval.sun_tracking()
        StateEngineCurrent.values._SeCurrent__sun_altitude = StateEngineDefaults.sun_altitude_fallback
        self.assertEqual(se_eval.sun_tracking(), expected)


if __name__ == '__main__':
    unittest.main()
