#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

"""Data the web interface sends to its page."""

import cherrypy
import pytest

from plugins.deebot.credentials import CredentialStore
from plugins.deebot.session import DeebotSession, SessionStatus
from plugins.deebot.webif import WebInterface

from .helpers import make_plugin


@pytest.fixture
def webif(sh):
    plugin = make_plugin(sh)
    for each in sh.return_items():
        plugin.parse_item(each)
    webif = WebInterface.__new__(WebInterface)
    webif.plugin = plugin
    return webif


def test_status_without_session_is_stopped(webif):
    assert webif.get_status_data()['status'] == 'stopped'


def test_values_list_items_per_feature(webif, sh):
    webif.plugin._publish('battery', 77)
    webif.plugin._publish('error_code', 105)

    values = {v['name']: v for v in webif.get_status_data()['values']}

    assert values['battery'] == {'name': 'battery', 'value': '77', 'items': ['vac.battery']}
    assert values['error_code']['items'] == []


def test_structured_values_are_shown_as_json(webif):
    webif.plugin._publish('position', {'x': 1, 'y': 2, 'angle': 3})

    value = next(v for v in webif.get_status_data()['values'] if v['name'] == 'position')['value']

    assert value == '{"x": 1, "y": 2, "angle": 3}'


def test_map_is_not_part_of_the_status_data(webif):
    webif.plugin._publish('map_svg', '<svg/>')

    data = webif.get_status_data()

    assert 'map' not in data
    assert all(v['name'] != 'map_svg' for v in data['values'])


def test_map_version_changes_only_with_the_map(webif):
    assert webif.get_status_data()['map_version'] == ''

    webif.plugin._publish('map_svg', '<svg/>')
    first = webif.get_status_data()['map_version']
    webif.plugin._publish('map_svg', '<svg/>')
    same = webif.get_status_data()['map_version']
    webif.plugin._publish('map_svg', '<svg><g/></svg>')
    changed = webif.get_status_data()['map_version']

    assert first and first == same
    assert changed not in ('', first)


def test_map_is_served_as_svg_image(webif):
    webif.plugin._publish('map_svg', '<svg/>')

    body = webif.map_svg(v='1')

    assert body == b'<svg/>'
    assert cherrypy.response.headers['Content-Type'] == 'image/svg+xml'


def test_missing_map_is_not_found(webif):
    with pytest.raises(cherrypy.HTTPError) as error:
        webif.map_svg()

    assert error.value.status == 404


def test_items_data_lists_only_plugin_items(webif, sh):
    rows = {row['path']: row for row in webif.get_items_data()}

    assert set(rows) == {
        'vac.battery',
        'vac.state',
        'vac.fan_speed',
        'vac.start',
        'vac.clean_rooms',
        'vac.rooms',
        'vac.map_svg',
    }
    assert rows['vac.start']['writable'] is True
    assert rows['vac.battery']['writable'] is False


def test_verification_message_is_shown_only_while_verification_is_pending(webif):
    webif.plugin.verification_message = 'code requested'

    assert webif.get_status_data()['verification_message'] == ''


def test_verification_message_is_shown_while_verification_is_pending(webif, tmp_path):
    session = DeebotSession(CredentialStore(tmp_path / 'deebot.json'), 'a', 'b', 'DE', '', lambda *_: None, True)
    session.status = SessionStatus.VERIFICATION_REQUIRED
    webif.plugin.session = session
    webif.plugin.verification_message = 'code requested'

    assert webif.get_status_data()['verification_message'] == 'code requested'
