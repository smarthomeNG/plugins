#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Characterization snapshot of the viessmann plugin; regenerate with SDP_SNAPSHOT_UPDATE=1."""

import unittest

from tests.sdp_harness.characterize import characterize_plugin


def _respond(data_dict):
    """Reply to reads with value bytes 01 02 .. of the command's length."""
    data = data_dict.get('data') or {}
    if data.get('value') is not None:
        return None
    return bytearray(range(1, int(data.get('len') or 1) + 1))


class TestViessmannCharacterization(unittest.TestCase):
    def test_matches_snapshot(self):
        characterize_plugin(
            self,
            'viessmann',
            'viessmann',
            'V200KO1B',
            {'model': 'V200KO1B', 'serialport': '/dev/null'},
            replies=False,
            responder=_respond,
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
