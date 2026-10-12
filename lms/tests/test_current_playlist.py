#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Commands on the current playlist use the playlist ID last reported by the player."""

import tempfile
import unittest

from tests.sdp_harness import load_sdp_plugin

MAC = 'aa:bb:cc:dd:ee:ff'

ITEMS = f"""
player:
    lms_custom1: '{MAC}'
    playlist_id:
        type: num
        lms_command: player.playlist.current_id
        lms_read: true
    delete_playlist:
        type: bool
        lms_command: player.playlist.delete_current
        lms_write: true
"""


class TestCurrentPlaylist(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rig = load_sdp_plugin(self._tmp.name, 'plugins.lms', 'lms', ITEMS, params={'host': 'sim'})
        self.rig.plugin.run()

    def tearDown(self):
        self.rig.plugin.stop()
        self._tmp.cleanup()

    def test_delete_uses_reported_playlist_id(self):
        self.rig.plugin.on_data_received('sim', f'{MAC} playlist playlistsinfo id:7')

        self.rig.item('player.delete_playlist')(True, 'test')

        self.assertIn(f'{MAC} playlists delete playlist_id:7', self.rig.connection.payloads[-1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
