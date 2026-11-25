#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Tests for plugins/denon/datatypes.py DT_* classes."""

import unittest

from plugins.denon.datatypes import (
    DT_DenonDisplay,
    DT_DenonVol,
    DT_DenonStandby,
    DT_DenonStandby1,
    DT_convert0,
    DT_DenonCustominput,
)


class TestDTDenonDisplay(unittest.TestCase):
    def test_infotype_0_slices_at_4(self):
        # data[3:4] == '0' -> should return data[4:]
        data = 'ABC0REST'
        self.assertEqual(DT_DenonDisplay().get_shng_data(data), 'REST')

    def test_infotype_1_slices_at_5(self):
        # data[3:4] == '1' -> should return data[5:]
        data = 'ABC1XREST'
        self.assertEqual(DT_DenonDisplay().get_shng_data(data), 'REST')

    def test_infotype_other_digit_slices_at_6(self):
        # data[3:4] not '0' or '1' -> data[6:]
        data = 'ABC2XYREST'
        self.assertEqual(DT_DenonDisplay().get_shng_data(data), 'REST')


class TestDTDenonVol(unittest.TestCase):
    def test_two_digit_value_returned_as_int(self):
        # 2-digit values (no fractional 5 suffix) go through the else
        # branch - must come back as int, matching get_send_data's contract
        result = DT_DenonVol().get_shng_data('50')
        self.assertEqual(result, 50)
        self.assertIsInstance(result, int)

    def test_three_digit_value_returned_as_float(self):
        result = DT_DenonVol().get_shng_data('505')
        self.assertEqual(result, 50.5)


class TestDTDenonStandby(unittest.TestCase):
    def test_off_returns_int_zero(self):
        self.assertEqual(DT_DenonStandby().get_shng_data('OFF'), 0)

    def test_non_off_returns_int_not_str(self):
        result = DT_DenonStandby().get_shng_data('5H')
        self.assertEqual(result, 5)
        self.assertIsInstance(result, int)


class TestDTDenonStandby1(unittest.TestCase):
    def test_off_returns_int_zero(self):
        self.assertEqual(DT_DenonStandby1().get_shng_data('OFF'), 0)

    def test_non_off_returns_int_not_str(self):
        result = DT_DenonStandby1().get_shng_data('05M')
        self.assertEqual(result, 5)
        self.assertIsInstance(result, int)


class TestDTConvert0(unittest.TestCase):
    def test_off_returns_int_zero(self):
        self.assertEqual(DT_convert0().get_shng_data('OFF'), 0)

    def test_non_special_value_returned_as_int(self):
        result = DT_convert0().get_shng_data('042')
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)


class TestDTDenonCustominput(unittest.TestCase):
    def test_well_formed_entry_is_stored(self):
        dt = DT_DenonCustominput()
        result = dt.get_shng_data('SAT Satellite')
        self.assertEqual(result, {'SAT': 'Satellite'})

    def test_malformed_entry_without_space_does_not_raise(self):
        dt = DT_DenonCustominput()
        # must not raise IndexError; malformed entry is simply skipped
        result = dt.get_shng_data('MALFORMED')
        self.assertEqual(result, {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
