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

"""
Pytest configuration for the deebot plugin tests.

lib/item/__init__.py only re-exports Items, not Item, which the shared test mock (tests/mock/core.py) still uses.
Same workaround as plugins/jsonread/tests/conftest.py.
"""

import lib.item
import lib.item.item

if not hasattr(lib.item, 'Item'):
    lib.item.Item = lib.item.item.Item

import os

import pytest

from tests.mock.core import MockSmartHome

from .helpers import FIXTURES_DIR, make_plugin


@pytest.fixture
def sh(tmp_path):
    sh = MockSmartHome()
    sh._var_dir = str(tmp_path)
    sh.with_items_from(os.path.join(FIXTURES_DIR, 'items.yaml'))
    return sh


@pytest.fixture
def plugin(sh):
    plugin = make_plugin(sh)
    for item in sh.items.return_items():
        plugin.parse_item(item)
    return plugin
