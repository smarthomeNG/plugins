#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Selecting audio streams and subtitles by item: what Kodi reports and what is sent back."""

import os
import tempfile
import unittest

from tests.sdp_harness import load_sdp_plugin
from tests.sdp_harness.characterize import items_yaml_from_struct

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AUDIO_STREAMS = [
    {'index': 0, 'language': 'ger', 'name': 'MP3 stereo'},
    {'index': 1, 'language': 'eng', 'name': 'AC3 5.1'},
]
SUBTITLES = [
    {'index': 0, 'language': 'ger', 'name': 'ger Deutsch'},
    {'index': 1, 'language': '', 'name': 'English (Forced)'},
    {'index': 2, 'language': '', 'name': ''},
]


def properties_reply(**result):
    props = {
        'speed': 1,
        'percentage': 5.0,
        'audiostreams': AUDIO_STREAMS,
        'currentaudiostream': AUDIO_STREAMS[1],
        'subtitles': SUBTITLES,
        'subtitleenabled': True,
        'currentsubtitle': SUBTITLES[0],
    }
    props.update(result)
    return {'jsonrpc': '2.0', 'id': '1_Player.GetProperties', 'result': props}


class KodiRig(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        items = items_yaml_from_struct(PLUGIN_DIR, 'ALL')
        self.rig = load_sdp_plugin(
            self._tmp.name, 'plugins.kodi', 'kodi', items, params={'host': 'sim'}, record_transport=True
        )
        self.plugin = self.rig.plugin
        self.plugin.run()
        self.plugin._playerid = 1
        self.rig.connection.sent.clear()

    def tearDown(self):
        self.plugin.stop()
        self._tmp.cleanup()

    def value(self, path):
        return self.rig.item(f'dev.{path}')()

    def receive_properties(self, **result):
        self.plugin.on_data_received('test', properties_reply(**result), 'Player.GetProperties')

    def sent_params(self):
        return [d['data']['params'] for d in self.rig.connection.sent]


class TestReportedSelection(KodiRig):
    def test_audio_item_holds_the_current_stream_index(self):
        self.receive_properties()

        self.assertEqual(1, self.value('control.audio'))

    def test_subtitle_item_holds_the_current_subtitle_index(self):
        self.receive_properties()

        self.assertEqual(0, self.value('control.subtitle'))

    def test_subtitle_item_is_off_if_subtitles_are_disabled(self):
        self.receive_properties(subtitleenabled=False)

        self.assertEqual('off', self.value('control.subtitle'))

    def test_subtitle_item_is_off_without_a_current_subtitle(self):
        self.receive_properties(currentsubtitle={})

        self.assertEqual('off', self.value('control.subtitle'))

    def test_no_audio_stream_is_reported_as_empty(self):
        self.receive_properties(currentaudiostream={})

        self.assertEqual('', self.value('control.audio'))


class TestNameLists(KodiRig):
    def test_audio_names_follow_the_stream_indexes(self):
        self.receive_properties()

        self.assertEqual(['ger - MP3 stereo', 'eng - AC3 5.1'], self.value('info.audio_names'))

    def test_subtitle_names_do_not_repeat_the_language_and_fall_back_to_the_index(self):
        self.receive_properties()

        self.assertEqual(['ger Deutsch', 'English (Forced)', '#2'], self.value('info.subtitle_names'))

    def test_lists_are_emptied_when_playback_stops(self):
        self.receive_properties()

        self.plugin.on_data_received(
            'test', {'jsonrpc': '2.0', 'method': 'Player.OnStop', 'params': {'data': {}}}, None
        )

        self.assertEqual(
            ([], [], [], []),
            (
                self.value('info.streams'),
                self.value('info.subtitles'),
                self.value('info.audio_names'),
                self.value('info.subtitle_names'),
            ),
        )


class TestWritingSelection(KodiRig):
    def test_digit_strings_are_sent_as_indexes(self):
        self.rig.item('dev.control.audio')('0', 'test')
        self.rig.item('dev.control.subtitle')(' 2 ', 'test')

        self.assertEqual(
            [{'playerid': 1, 'stream': 0}, {'playerid': 1, 'subtitle': 2, 'enable': True}], self.sent_params()
        )

    def test_integers_and_keywords_are_sent_unchanged(self):
        self.rig.item('dev.control.audio')(2, 'test')
        self.rig.item('dev.control.audio')('next', 'test')
        self.rig.item('dev.control.subtitle')('off', 'test')

        self.assertEqual([2, 'next'], [p['stream'] for p in self.sent_params()[:2]])
        self.assertEqual('off', self.sent_params()[2]['subtitle'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
