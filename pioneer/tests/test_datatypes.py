#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Tests for plugins/pioneer/datatypes.py DT_* classes."""

import unittest

from plugins.pioneer.datatypes import DT_PioInitVol, DT_PioStandby, DT_PioStandby2


class TestDTPioInitVol(unittest.TestCase):
    def test_shng_data_high_range_does_not_raise(self):
        # data arrives as a string; get_shng_data converted it to int only
        # for the branch comparisons, not for the arithmetic itself -
        # str - int crashed with TypeError for any non-sentinel value
        result = DT_PioInitVol().get_shng_data('185')
        self.assertEqual(result, 12.0)

    def test_shng_data_low_range_does_not_raise(self):
        result = DT_PioInitVol().get_shng_data('001')
        self.assertEqual(result, -80.0)

    def test_send_shng_round_trip(self):
        dt = DT_PioInitVol()
        sent = dt.get_send_data(0)
        self.assertEqual(dt.get_shng_data(sent), 0.0)


class TestDTPioStandby(unittest.TestCase):
    def test_round_trip_15(self):
        # get_send_data(15) encodes to '0150'; reading that back must
        # return 15, not 150 (a bare int(data) with no /10 decoding)
        dt = DT_PioStandby()
        sent = dt.get_send_data(15)
        self.assertEqual(dt.get_shng_data(sent), 15)


class TestDTPioStandby2(unittest.TestCase):
    def test_recognized_value_still_works(self):
        self.assertEqual(DT_PioStandby2().get_shng_data('0011'), 1)

    def test_unrecognized_value_raises_instead_of_silent_none(self):
        with self.assertRaises(ValueError):
            DT_PioStandby2().get_shng_data('9999')


if __name__ == '__main__':
    unittest.main(verbosity=2)
