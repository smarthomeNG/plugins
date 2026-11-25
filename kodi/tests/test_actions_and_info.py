#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Kodi status queries, power/quit and other actions, info.* commands."""

import os
import tempfile
import unittest

from tests.sdp_harness import load_sdp_plugin
from tests.sdp_harness.characterize import items_yaml_from_struct

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ACTION_METHODS = {
    'Player.PlayPause',
    'Player.Stop',
    'Player.Seek',
    'Player.SetSpeed',
    'Player.SetAudioStream',
    'Player.SetSubtitle',
    'Player.GoTo',
    'Application.SetMute',
    'Application.SetVolume',
    'Input.ExecuteAction',
}

INFO_COMMANDS = (
    'info.player',
    'info.state',
    'info.media',
    'info.title',
    'info.streams',
    'info.subtitles',
    'info.macro',
)


class TestKodiCommandsWithoutParams(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        items = items_yaml_from_struct(PLUGIN_DIR, 'ALL')
        self.rig = load_sdp_plugin(
            self._tmp.name, 'plugins.kodi', 'kodi', items, params={'host': 'sim'}, record_transport=True
        )
        self.plugin = self.rig.plugin
        self.plugin.run()
        self.rig.connection.sent.clear()

    def tearDown(self):
        self.plugin.stop()
        self._tmp.cleanup()

    def methods(self):
        return [d['data']['method'] for d in self.rig.connection.sent]

    def test_status_queries_are_sent(self):
        for command in ('status.get_actplayer', 'status.ping', 'status.get_settings'):
            self.plugin.send_command(command)

        self.assertEqual(['Player.GetActivePlayers', 'JSONRPC.Ping', 'Settings.GetSettings'], self.methods())

    def test_power_and_quit_are_not_read(self):
        self.plugin.send_command('control.power')
        self.plugin.send_command('control.quit')
        self.rig.item('dev.control.read')(True, 'test')

        self.assertNotIn('System.Shutdown', self.methods())
        self.assertNotIn('Application.Quit', self.methods())

    def test_truthy_power_and_quit_run_the_action(self):
        self.rig.item('dev.control.power')(True, 'test')
        self.rig.item('dev.control.quit')(True, 'test')

        self.assertEqual(['System.Shutdown', 'Application.Quit'], self.methods())

    def test_falsy_power_and_quit_do_nothing(self):
        for path in ('dev.control.power', 'dev.control.quit'):
            self.rig.item(path)(True, self.plugin.get_fullname())
            self.rig.item(path)(False, 'test')

        self.assertEqual([], self.methods())

    def test_read_all_sends_no_actions(self):
        self.plugin.read_all_commands()

        self.assertEqual(set(), ACTION_METHODS & set(self.methods()))
        self.assertIn('Player.GetActivePlayers', self.methods())

    def test_action_commands_are_not_read(self):
        for command in ('control.playpause', 'control.stop', 'control.mute', 'control.goto', 'control.action'):
            self.plugin.send_command(command)

        self.assertEqual([], self.methods())

    def test_state_still_reaches_control_items(self):
        self.plugin.dispatch_data('control.mute', True, 'test')
        self.plugin.dispatch_data('control.volume', 42, 'test')

        self.assertEqual((True, 42), (self.rig.item('dev.control.mute')(), self.rig.item('dev.control.volume')()))

    def test_writes_still_send_actions(self):
        self.rig.item('dev.control.mute')(True, 'test')
        self.rig.item('dev.control.goto')('next', 'test')

        self.assertEqual(['Application.SetMute', 'Player.GoTo'], self.methods())

    def test_ping_reply_sets_ping_item(self):
        reply = {'jsonrpc': '2.0', 'id': '1_JSONRPC.Ping', 'result': 'pong'}

        self.plugin.on_data_received('test', reply, 'JSONRPC.Ping')

        self.assertIs(True, self.rig.item('dev.status.ping')())

    def test_struct_matches_command_flags(self):
        ignored = [r.getMessage() for r in self.rig.logs.records if 'which is not allowed' in r.getMessage()]

        self.assertEqual([], ignored)

    def test_info_items_receive_dispatched_values(self):
        self.plugin.dispatch_data('info.state', 'Playing', 'test')
        self.plugin.dispatch_data('info.title', 'Film', 'test')

        self.assertEqual(('Playing', 'Film'), (self.rig.item('dev.info.state')(), self.rig.item('dev.info.title')()))

    def test_update_requests_status(self):
        self.rig.item('dev.status.update')(True, 'test')

        self.assertEqual(['Player.GetActivePlayers', 'Application.GetProperties'], self.methods())

    def test_plugin_commands_are_valid_but_not_readable(self):
        self.assertTrue(self.plugin.is_valid_command('info.player'))
        self.assertFalse(self.plugin.is_valid_command('info.player', True))
        self.assertTrue(self.plugin.is_valid_command('status.update', False))

    def test_info_commands_are_not_requested(self):
        for command in INFO_COMMANDS:
            self.plugin.send_command(command)
        self.rig.item('dev.info.macro')(True, 'test')

        self.assertEqual([], self.methods())


if __name__ == '__main__':
    unittest.main(verbosity=2)
