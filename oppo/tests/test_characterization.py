#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Characterization snapshot of the oppo plugin; regenerate with SDP_SNAPSHOT_UPDATE=1."""

import unittest

from tests.sdp_harness.characterize import characterize_plugin


class TestOppoCharacterization(unittest.TestCase):
    def test_matches_snapshot(self):
        characterize_plugin(self, 'oppo', 'oppo', 'UDP-203', {'model': 'UDP-203', 'host': 'sim'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
