#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Characterization snapshot of the pioneer plugin; regenerate with SDP_SNAPSHOT_UPDATE=1."""

import unittest

from tests.sdp_harness.characterize import characterize_plugin


class TestPioneerCharacterization(unittest.TestCase):
    def test_matches_snapshot(self):
        characterize_plugin(self, 'pioneer', 'pioneer', 'SC-LX87', {'model': 'SC-LX87', 'host': 'sim'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
