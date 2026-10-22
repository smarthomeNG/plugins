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

"""Shared helpers of the deebot plugin tests."""

import os

from plugins.deebot import Deebot

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
PARAMETERS = {
    'account': 'me@example.org',
    'password': 'pw',
    'country': 'DE',
    'device': '',
    'enable_map': True,
    'room_names': [],
    'room_preselect': [],
    'map_css': '',
    'map_trace': True,
}


def make_plugin(sh, **parameters) -> Deebot:
    Deebot._parameters = {**PARAMETERS, **parameters}
    Deebot._shortname = 'deebot'
    return Deebot(sh)


def item(sh, name):
    return sh.return_item(f'vac.{name}')


def write(plugin, sh, name, value):
    """Set the item like a logic would and deliver the update to the plugin like shng does for updating items."""
    target = item(sh, name)
    target(value, 'logic')
    plugin.update_item(target, 'logic')
