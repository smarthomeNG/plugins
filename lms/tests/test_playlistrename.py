#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests that DT_LMSPlaylistrename.get_send_data() surfaces malformed input
instead of silently sending the unmodified, wrong-wire-format string to
the device. A bare `except Exception: pass` around the IndexError from
missing values[1] meant the reassignment never completed and the
original, unconverted string was returned with no signal anything went
wrong.
"""

import unittest

from plugins.lms.datatypes import DT_LMSPlaylistrename


class TestDTLMSPlaylistrename(unittest.TestCase):
    def test_well_formed_input_builds_wire_format(self):
        result = DT_LMSPlaylistrename().get_send_data('42 NewName')
        self.assertEqual(result, 'playlist_id:42 newname:NewName')

    def test_malformed_input_without_newname_raises(self):
        with self.assertRaises(ValueError):
            DT_LMSPlaylistrename().get_send_data('42')


if __name__ == '__main__':
    unittest.main(verbosity=2)
