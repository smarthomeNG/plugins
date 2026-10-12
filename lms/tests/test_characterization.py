#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Characterization snapshot of the lms plugin; regenerate with SDP_SNAPSHOT_UPDATE=1."""

import unittest

from tests.sdp_harness.characterize import characterize_plugin


class TestLmsCharacterization(unittest.TestCase):
    def test_matches_snapshot(self):
        characterize_plugin(self, 'lms', 'lms', 'ALL', {'host': 'sim'}, root_attrs={'lms_custom1': 'aa:bb:cc:dd:ee:ff'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
