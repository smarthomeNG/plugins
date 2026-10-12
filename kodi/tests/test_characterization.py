#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Characterization snapshot of the kodi plugin; regenerate with SDP_SNAPSHOT_UPDATE=1."""

import unittest

from tests.sdp_harness.characterize import characterize_plugin


def _reply(command, result):
    return {'jsonrpc': '2.0', 'id': f'99_{command}', 'result': result}, command


def _notification(method, data):
    return {'jsonrpc': '2.0', 'method': method, 'params': {'data': data, 'sender': 'xbmc'}}, None


PLAYER = {'player': {'playerid': 1, 'speed': 1}}

REPLIES = [
    _reply('Player.GetActivePlayers', [{'playerid': 1, 'type': 'video'}]),
    _reply('Player.GetActivePlayers', [{'playerid': 0, 'type': 'audio'}, {'playerid': 1, 'type': 'video'}]),
    _reply('Player.GetActivePlayers', []),
    _reply('Application.GetProperties', {'muted': True, 'volume': 42}),
    _reply('Favourites.GetFavourites', {'favourites': [{'title': 'Fav', 'type': 'media'}]}),
    _reply('Favourites.GetFavourites', {'favourites': None}),
    _reply('Player.GetItem', {'item': {'title': 'Song', 'type': 'audio', 'artist': ['Artist']}}),
    _reply('Player.GetItem', {'item': {'title': '', 'label': 'Label', 'type': 'video'}}),
    _reply(
        'Player.GetProperties',
        {
            'speed': 0,
            'percentage': 12.5,
            'currentaudiostream': {'name': 'a'},
            'audiostreams': [],
            'subtitleenabled': True,
            'currentsubtitle': {'name': 's'},
            'subtitles': [],
        },
    ),
    ({'jsonrpc': '2.0', 'id': '98_Player.GetItem', 'error': {'code': -1}}, 'Player.GetItem'),
    ({'jsonrpc': '2.0', 'id': '97_Player.GetItem', 'result': None}, 'Player.GetItem'),
    ('not json', None),
]

NOTIFICATIONS = [
    _notification('Player.OnPlay', {'item': {'type': 'movie', 'title': 'Film'}, **PLAYER}),
    _notification('Player.OnPlay', {'item': {'type': 'channel', 'channeltype': 'tv', 'title': 'News'}, **PLAYER}),
    _notification('Player.OnPause', {'item': {'type': 'movie'}, **PLAYER}),
    _notification('Player.OnResume', {'item': {'type': 'movie'}, **PLAYER}),
    _notification('Player.OnStop', {'item': {'type': 'movie'}, 'end': True}),
    _notification('GUI.OnScreensaverActivated', {}),
    _notification('Application.OnVolumeChanged', {'muted': False, 'volume': 77}),
]


class TestKodiCharacterization(unittest.TestCase):
    def test_matches_snapshot(self):
        characterize_plugin(
            self,
            'kodi',
            'kodi',
            'ALL',
            {'host': 'sim'},
            replies=False,
            record_transport=True,
            inbound={'kodi_replies': REPLIES, 'kodi_notifications': NOTIFICATIONS},
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
